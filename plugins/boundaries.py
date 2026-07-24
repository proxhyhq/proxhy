"""
Outline boundaries for "You can't place blocks here!"
regions around bases and diamond/emerald generators.

Implements many data collection pipelines, since
these bounding boxes are not easily exposed to the
client.
"""

import asyncio
import json
import math
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# from plugins.commands import command
from typing import TYPE_CHECKING, Literal, cast, overload

from gamestate.models import Player
from gamestate.state import GameState
from petty.events import listen_client, listen_server, subscribe
from petty.protocol.datatypes import (
    Angle,
    Buffer,
    Byte,
    Double,
    Float,
    Int,
    Pos,
    Position,
    Short,
    Slot,
    TextComponent,
    UnsignedByte,
    VarInt,
)
from plugins.commands import command
from plugins.statcheck import BW_MAPS, GamePlayer
from proxhy.utils import uuid_version

if TYPE_CHECKING:
    import logging

    from proxhy.plugin import ProxhyPlugin


class BoundariesPlugin:
    def _init_boundaries(self: ProxhyPlugin):
        self.gamestate: GameState
        self.last_game_start: float = float("-inf")

        # last "You can't place blocks here!" message timestamp
        self.last_cpb: float = float("-inf")
        self.cpb_event = asyncio.Event()

        # x, y, z, yaw (looking)
        self.entities_teleported: dict[
            str, tuple[float, float, float, Literal[0, 90, -90, 180, -180]]
        ] = {}
        self.team_spawnpoints: dict[
            str, tuple[float, float, float, Literal[0, 90, -90, 180, -180]]
        ] = {}
        self.recently_placed: deque[Pos] = deque(maxlen=10)
        self.placed_mappings: deque[int] = deque(maxlen=10)
        self.boundary_regions: list[BoundaryRegion] = []

        # developer flag to enable features that make it
        # easier to get the boundary positions on new maps
        self.log_boundaries = True
        self.log_generators = True
        self.output_generator_logs = True

        # TODO: make this into a setting
        self.render_boundaries = True

        # chat notifications for developer data collection pipelines
        self.send_chat_notifs = True

        self.teams_populated = False

        # corners relative to spawn position
        # based on direction facing when you spawned in
        self.boundary_corner_1 = Pos(0, 0, 0)
        self.boundary_corner_2 = Pos(0, 0, 0)
        self.n_total_boundaries = 0

        # max number of blocks away to show boundary
        # TODO: make this into a setting(?)
        self.BOUNDARY_CULL_RADIUS = 30

        # how often to check if we're near a boundary
        self.CHECK_BOUNDARIES_TIME = 0.5

        # window in which to consider the "you can't place blocks here!" chat msg as being recent
        self.CPB_WINDOW = 0.2

        # how often should we check for nearby generators (in seconds)
        self.GEN_CHECK_TIME = 1

        self._next_boundary_entity_id: int = -999

        if self.log_generators:
            self.create_task(self.loop_gen_check())

        if self.render_boundaries:
            self.create_task(self.loop_boundaries_check())

    def _allocate_boundary_entity_id(self: ProxhyPlugin) -> int:
        self._next_boundary_entity_id -= 1
        return self._next_boundary_entity_id

    @subscribe(r"chat:server:The game starts in 1 second!")
    async def received_game_start_chat(self: ProxhyPlugin, match, buff: Buffer):
        self.downstream.send_packet(0x02, buff.getvalue())

        # reset team dicts at the start of the game
        self.entities_teleported = {}
        self.team_spawnpoints = {}

        self.last_game_start = time.time()
        self.teams_populated = False

        if self.game.map is None:
            self.logger.warning("self.game.map is None!")
            return

        try:
            self.map_data: dict = BW_MAPS[self.game.map.name]
            boundary = self.map_data.get("boundary")
            if boundary:
                corner1 = boundary.get("corner1")
                corner2 = boundary.get("corner2")
                if corner1 and corner2 and len(corner1) == 3 and len(corner2) == 3:
                    self.boundary_corner_1 = Pos(*corner1)
                    self.boundary_corner_2 = Pos(*corner2)

            self.map_data.setdefault("generators", {})
            self.map_data["generators"].setdefault("emerald", [])
            self.map_data["generators"].setdefault("diamond", [])

        except KeyError:
            self.logger.warning(f"Unknown map: '{self.game.map.name}'")
            return
        if self.render_boundaries:
            self.n_total_boundaries = (
                len(self.map_data["generators"]["emerald"])
                + len(self.map_data["generators"]["diamond"])
                + len(self.map_data.get("spawnpoints"))
            )
            self.initialize_all_boundaries()

    def game_recently_started(self: ProxhyPlugin, window: float = 5.0) -> bool:
        # game started less than `window` seconds ago
        return time.time() - self.last_game_start < window

    def get_bedwars_team_count(self: ProxhyPlugin) -> int | None:
        if not self.game.mode or "bedwars" not in self.game.mode:
            return None

        if "eight" in self.game.mode:
            return 8
        elif "four" in self.game.mode:
            return 4
        elif "two" in self.game.mode:
            return 2
        else:
            return None

    @subscribe("statcheck:all_players_statted")
    async def teams_now_populated(self: ProxhyPlugin, *_):
        self.teams_populated = True

        if len(self.entities_teleported.keys()) == 0:
            # preseumably we did teleport entities, but we didn't log them
            if self.log_boundaries:
                self.logger.warning(
                    "self.log_boundaries enabled; did not teleport any entities."
                )
            return

        # core loop: extract spawnpoints and clean dict of non-player entities
        for e in list(self.entities_teleported.keys()):
            # wrap in list to avoid deleting from dict white iterating
            try:
                game_player: GamePlayer = self.game_players[e]
                if e not in self.real_players():
                    raise KeyError

                team = game_player.team.name.lower()
                if team in self.team_spawnpoints:
                    continue

                x, y, z, yaw = self.entities_teleported[e]

                self.team_spawnpoints[team] = (x, y, z, yaw)
            except KeyError:
                # for redundancy, clean dict of non-player entities that might've snuck through
                del self.entities_teleported[e]

        # see if we got any new spawnpoints we didn't have saved to bedwars map data json beforehand
        team_count = self.get_bedwars_team_count()
        if team_count is None:
            self.logger.warning(f"Could not get team count for mode {self.game.mode}")
            return

        if self.map_data.get("spawnpoints") is None:
            self.map_data["spawnpoints"] = {}

        saved_spawnpoints = self.map_data["spawnpoints"]
        spawnpoints_added = 0
        for team, spawnpoint in self.team_spawnpoints.items():
            if team in saved_spawnpoints:
                continue
            saved_spawnpoints[team] = spawnpoint
            spawnpoints_added += 1

        if spawnpoints_added > 0:
            self._save_bedwars_map_data()

    def initialize_all_boundaries(self: ProxhyPlugin):
        boundary_corners = self._collect_all_boundary_corners()
        if len(self.boundary_regions):
            self.logger.warning(
                "Already initialized some boundaries! May re-initialize existing ones by mistake."
            )
        for c in boundary_corners:
            self.boundary_regions.append(
                BoundaryRegion(c[0], c[1], self.gamestate, self.logger)
            )

    def _collect_all_boundary_corners(self: ProxhyPlugin) -> list[tuple[Pos, Pos]]:
        """Collects boundary corners from bedwars_maps.json for bases and generators."""
        # diamond and emerald generators are a 7x7x7 cube
        # saved coordinate in file is at the top & center block
        emerald_centers = self.map_data["generators"]["emerald"]
        diamond_centers = self.map_data["generators"]["diamond"]

        gen_centers: list[list[float]]
        gen_centers = emerald_centers + diamond_centers

        boundary_corners: list[tuple[Pos, Pos]] = []
        for c in gen_centers:
            x, y, z = math.floor(c[0]), math.floor(c[1]), math.floor(c[2])
            corner1 = Pos(x + 3, y, z + 3)
            corner2 = Pos(x - 3, y - 6, z - 3)
            boundary_corners.append((corner1, corner2))

        spawnpoints: list[list[float]]
        spawnpoints = self.map_data["spawnpoints"].values()
        boundary_data: None | dict[str, list[int]] = self.map_data.get("boundary")
        if boundary_data is not None:
            rel_corner1 = Pos(
                boundary_data["corner1"][0],
                boundary_data["corner1"][1],
                boundary_data["corner1"][2],
            )
            rel_corner2 = Pos(
                boundary_data["corner2"][0],
                boundary_data["corner2"][1],
                boundary_data["corner2"][2],
            )
            for s in spawnpoints:
                spawn_x, spawn_y, spawn_z, spawn_yaw = (
                    math.floor(s[0]),
                    math.floor(s[1]),
                    math.floor(s[2]),
                    s[3],
                )
                yaw_int = int(spawn_yaw)
                yaw = self.validate_yaw(yaw_int)
                if yaw:
                    c1 = self.get_global_pos_yaw(
                        rel_corner1, Pos(spawn_x, spawn_y, spawn_z), yaw
                    )
                    c2 = self.get_global_pos_yaw(
                        rel_corner2, Pos(spawn_x, spawn_y, spawn_z), yaw
                    )
                    boundary_corners.append((c1, c2))
        return boundary_corners

    def validate_yaw(
        self: ProxhyPlugin, yaw: int | float, snap=True
    ) -> Literal[0, 90, -90, 180, -180] | None:
        yaw = int(yaw)
        if yaw not in {0, 90, -90, 180, -180}:
            if snap:
                snapped = round(yaw / 90) * 90 % 360  # 0, 90, 180, 270
                # cast so it knows its on the validated intervals
                return cast(
                    Literal[0, 90, -90, 180, -180],
                    {270: -90, 180: -180}.get(snapped, snapped),
                )
            else:
                self.logger.warning(
                    f"Received yaw on a non-90 degree increment! ({yaw})"
                )
                return
        return yaw

    @listen_server(0x18)  # on entity teleport
    async def save_player_spawnpoints(self: ProxhyPlugin, buff: Buffer):
        self.downstream.send_packet(0x18, buff.getvalue())

        if (
            self.game_recently_started()
            and self.log_boundaries
            and self.game.gametype == "bedwars"
        ):
            entity_id = buff.unpack(VarInt)
            entity = self.gamestate.get_entity(entity_id)
            if (
                entity is None
                or not isinstance(entity, Player)
                # or entity.name in self.entities_teleported.keys()
                or uuid_version(entity.uuid) == 2  # uuid == 2 for npcs
            ):
                return

            # divide by 32 because of stupid chud datatype fixed point number
            x = buff.unpack(Int) / 32.0
            y = buff.unpack(Int) / 32.0
            z = buff.unpack(Int) / 32.0

            yaw = buff.unpack(Angle)
            yaw = self.validate_yaw(yaw)
            if yaw is None:
                return

            self.entities_teleported[entity.name] = (x, y, z, yaw)

    def _save_bedwars_map_data(self: ProxhyPlugin) -> None:
        maps_path = Path(__file__).resolve().parents[1] / "assets" / "bedwars_maps.json"
        with maps_path.open("w", encoding="utf-8") as f:
            f.write("{\n")
            items = sorted(BW_MAPS.items())
            for index, (map_name, map_data) in enumerate(items):
                comma = "," if index < len(items) - 1 else ""
                f.write(
                    f"  {json.dumps(map_name, ensure_ascii=False)}: "
                    f"{json.dumps(map_data, ensure_ascii=False, separators=(',', ': '))}"
                    f"{comma}\n"
                )
            f.write("}\n")

    @listen_server(0x08, blocking=True)  # player move and look packet
    async def read_own_spawnpoint(self: ProxhyPlugin, buff: Buffer):
        self.downstream.send_packet(0x08, buff.getvalue())

        if (
            self.game_recently_started()
            and self.log_boundaries
            and self.game.gametype == "bedwars"
        ):
            x = buff.unpack(Double)
            y = buff.unpack(Double)
            z = buff.unpack(Double)

            yaw = self.validate_yaw(buff.unpack(Float))
            if yaw is None:
                return

            self.entities_teleported[self.nick_or_username] = (x, y, z, yaw)

    @subscribe(r"chat:server:You can't place blocks here!")
    async def received_cant_place_chat(self: ProxhyPlugin, match, buff: Buffer):
        self.downstream.send_packet(0x02, buff.getvalue())

        self.cpb_event.set()
        await asyncio.sleep(self.CPB_WINDOW)  # yield to the event loop
        if self.cpb_event.is_set():
            # might've gotten cleared in that sleep window
            self.cpb_event.clear()

    @staticmethod
    @overload
    def get_offset_position(pos: Pos, face: Literal[255]) -> None: ...

    @staticmethod
    @overload
    def get_offset_position(pos: Pos, face: Literal[0, 1, 2, 3, 4, 5]) -> Pos: ...

    @staticmethod
    def get_offset_position(
        pos: Pos, face: Literal[0, 1, 2, 3, 4, 5, 255]
    ) -> Pos | None:
        match face:
            case 0:
                return Pos(pos.x, pos.y - 1, pos.z)
            case 1:
                return Pos(pos.x, pos.y + 1, pos.z)
            case 2:
                return Pos(pos.x, pos.y, pos.z - 1)
            case 3:
                return Pos(pos.x, pos.y, pos.z + 1)
            case 4:
                return Pos(pos.x - 1, pos.y, pos.z)
            case 5:
                return Pos(pos.x + 1, pos.y, pos.z)
            case 255:
                return None

    @staticmethod
    def get_relative_pos_yaw(
        pos: Pos, anchor: Pos, yaw: Literal[0, 90, -90, 180, -180]
    ) -> Pos:
        # pos1 is arbitrary position
        # pos2 is centered position with yaw
        # 1. Calculate standard world deltas
        dx = pos.x - anchor.x
        dy = pos.y - anchor.y
        dz = pos.z - anchor.z

        # 2. Translate world deltas to local deltas based on yaw
        if yaw == 0:
            # Facing +Z: Forward is +Z, Right is +X
            local_x = dx
            local_z = dz
        elif yaw == 90:
            # Facing -X: Forward is -X, Right is +Z
            local_x = dz
            local_z = -dx
        elif yaw == 180 or yaw == -180:
            # Facing -Z: Forward is -Z, Right is -X
            local_x = -dx
            local_z = -dz
        elif yaw == -90:
            # Facing +X: Forward is +X, Right is -Z
            local_x = -dz
            local_z = dx
        else:
            raise ValueError(f"Unexpected yaw value: {yaw}")

        return Pos(local_x, dy, local_z)

    @staticmethod
    def get_global_pos_yaw(
        pos: Pos, anchor: Pos, yaw: Literal[0, 90, -90, 180, -180]
    ) -> Pos:
        local_x = pos.x
        local_y = pos.y
        local_z = pos.z

        if yaw == 0:
            world_x = anchor.x + local_x
            world_z = anchor.z + local_z
        elif yaw == 90:
            world_x = anchor.x - local_z
            world_z = anchor.z + local_x
        elif yaw == 180 or yaw == -180:
            world_x = anchor.x - local_x
            world_z = anchor.z - local_z
        elif yaw == -90:
            world_x = anchor.x + local_z
            world_z = anchor.z - local_x
        else:
            raise ValueError(f"Unexpected yaw value: {yaw}")

        return Pos(world_x, anchor.y + local_y, world_z)

    @listen_client(0x08, blocking=True)
    async def placed_block(self: ProxhyPlugin, buff: Buffer):
        self.upstream.send_packet(0x08, buff.getvalue())

        if self.log_boundaries and self.game.gametype == "bedwars":
            pos = buff.unpack(Position)
            face = buff.unpack(Byte)
            if face not in {0, 1, 2, 3, 4, 5}:
                return

            held_item = buff.unpack(Slot)

            if held_item.item and face != 255:
                adj_pos = self.get_offset_position(pos, face)
                self.recently_placed.appendleft(adj_pos)
                self.placed_mappings.appendleft(held_item.item.id)

    @command("getboundary")
    async def get_boundary(self: ProxhyPlugin):
        bc1x, bc1y, bc1z, bc2x, bc2y, bc2z = self._get_boundary()
        self.downstream.chat(
            f"Current boundary: ({bc1x}, {bc1y}, {bc1z}) -> ({bc2x}, {bc2y}, {bc2z})"
        )

    def _get_boundary(self: ProxhyPlugin):
        bc1x, bc1y, bc1z = (
            self.boundary_corner_1.x,
            self.boundary_corner_1.y,
            self.boundary_corner_1.z,
        )

        bc2x, bc2y, bc2z = (
            self.boundary_corner_2.x,
            self.boundary_corner_2.y,
            self.boundary_corner_2.z,
        )

        return bc1x, bc1y, bc1z, bc2x, bc2y, bc2z

    def update_boundary_size(self: ProxhyPlugin, block_deleted: int, pos: Pos):
        if self.map_data.get("spawnpoints") is None:
            if self.game.map is not None:
                self.logger.warning(
                    f"We don't have any spawnpoint positions for {self.game.map.name}!"
                )
            else:
                self.logger.warning("self.game.map is None!")
            return

        # how many blocks away do we accept that we could still be in a base
        max_dist = 20

        # find nearest base center w/ manhattan distance because spawn
        # block placement protections are cuboids

        # fmt: off
        distances = [
            (
                team,
                yaw,
                abs(pos.x - spawn_x) + abs(pos.y - spawn_y) + abs(pos.z - spawn_z)
            )
            for team, (spawn_x, spawn_y, spawn_z, yaw) in self.map_data["spawnpoints"].items()
        ]
        # fmt: on
        closest_team, yaw, min_dist = min(distances, key=lambda key: key[2])

        # we're more than max_dist blocks from the nearest base spawnpoint.
        # probably at a diamond gen or something, so don't expand the radius
        if min_dist > max_dist:
            return

        # check if the block deleted is already inside the known region
        spawn_x = int(self.map_data["spawnpoints"][closest_team][0])
        spawn_y = int(self.map_data["spawnpoints"][closest_team][1])
        spawn_z = int(self.map_data["spawnpoints"][closest_team][2])
        yaw = self.validate_yaw(self.map_data["spawnpoints"][closest_team][3])
        if yaw is not None:
            rel_pos = self.get_relative_pos_yaw(
                pos, Pos(spawn_x, spawn_y, spawn_z), yaw
            )
        else:
            return

        bc1x, bc1y, bc1z = (
            self.boundary_corner_1.x,
            self.boundary_corner_1.y,
            self.boundary_corner_1.z,
        )

        bc2x, bc2y, bc2z = (
            self.boundary_corner_2.x,
            self.boundary_corner_2.y,
            self.boundary_corner_2.z,
        )

        inside_x = min(bc1x, bc2x) <= rel_pos.x <= max(bc1x, bc2x)
        inside_y = min(bc1y, bc2y) <= rel_pos.y <= max(bc1y, bc2y)
        inside_z = min(bc1z, bc2z) <= rel_pos.z <= max(bc1z, bc2z)

        if inside_x and inside_y and inside_z:
            # we are already inside the boundary! no action required
            return
        else:
            # expand boundary
            prev_boundary = self._get_boundary()
            if not inside_x:
                if rel_pos.x > 0:
                    self.boundary_corner_1.x = rel_pos.x
                elif rel_pos.x < 0:
                    self.boundary_corner_2.x = rel_pos.x
            if not inside_y:
                if rel_pos.y > 0:
                    self.boundary_corner_1.y = rel_pos.y
                elif rel_pos.y < 0:
                    self.boundary_corner_2.y = rel_pos.y
            if not inside_z:
                if rel_pos.z > 0:
                    self.boundary_corner_1.z = rel_pos.z
                elif rel_pos.z < 0:
                    self.boundary_corner_2.z = rel_pos.z
            new_boundary = self._get_boundary()

            if self.send_chat_notifs:

                def fmt_val(old, new):
                    return f"§e{new}§r" if new != old else str(new)

                p, n = prev_boundary, new_boundary
                bc1 = f"({fmt_val(p[0], n[0])}, {fmt_val(p[1], n[1])}, {fmt_val(p[2], n[2])})"
                bc2 = f"({fmt_val(p[3], n[3])}, {fmt_val(p[4], n[4])}, {fmt_val(p[5], n[5])})"
                msg = f"Boundary: {bc1}§r -> {bc2}§r"

                self.downstream.chat(msg)

    async def try_update_boundary(self: ProxhyPlugin, block_deleted: int, pos: Pos):
        """
        Called when a block was deleted; checks if it's a 'You can't place blocks
        here!' message or if the block was deleted for some other reason. Also
        checks that the block deleted was wool.
        """
        if block_deleted != 35:  # wool
            return

        # it's possible we got message before server deleted block
        # if (time.time() - self.last_cpb) < self.CPB_WINDOW:
        #     self.update_boundary_size(block_deleted, pos)
        # else:
        # see if we get a "can't place blocks here" msg in the next self.CPB_WINDOW seconds
        try:
            await asyncio.wait_for(self.cpb_event.wait(), timeout=self.CPB_WINDOW)
            self.update_boundary_size(block_deleted, pos)
        except TimeoutError:
            # assume block got deleted for a different reason
            pass

    async def handle_block_removal(self: ProxhyPlugin, block_id: int, pos: Pos) -> None:
        # if the block is air (id=0) and was a block we recently placed
        # then the server deleted one of our recently placed blocks
        if block_id == 0 and pos in self.recently_placed:
            deque_id = self.recently_placed.index(pos)
            block_deleted = self.placed_mappings[deque_id]
            self.recently_placed.remove(pos)

            await self.try_update_boundary(block_deleted, pos)

    @listen_server(0x23, blocking=True)
    async def block_changed(self: ProxhyPlugin, buff: Buffer):
        self.downstream.send_packet(0x23, buff.getvalue())
        if self.log_boundaries and self.game.gametype == "bedwars":
            self.create_task(self._block_changed(buff))

    # rest of method shouldn't be blocking as it includes an asyncio.sleep call downstream
    async def _block_changed(self: ProxhyPlugin, buff: Buffer):
        pos = buff.unpack(Position)
        block_id = buff.unpack(VarInt)
        block_type = block_id >> 4

        await self.handle_block_removal(block_type, pos)

    @listen_server(0x22, blocking=True)
    async def multi_block_change(self: ProxhyPlugin, buff: Buffer):
        self.downstream.send_packet(0x22, buff.getvalue())

        if self.log_boundaries and self.game.gametype == "bedwars":
            self.create_task(self._block_changed(buff))

    # rest of method shouldn't be blocking as it includes an asyncio.sleep call downstream
    async def _multi_block_change(self: ProxhyPlugin, buff: Buffer):
        chunk_x, chunk_z = buff.unpack(Int), buff.unpack(Int)
        record_count = buff.unpack(VarInt)

        for _ in range(record_count):
            xz_pos = buff.unpack(UnsignedByte)
            y = buff.unpack(UnsignedByte)

            rel_x_pos = (0xF0 & xz_pos) >> 4
            rel_z_pos = 0x0F & xz_pos

            x = chunk_x * 16 + rel_x_pos
            z = chunk_z * 16 + rel_z_pos

            block_id = buff.unpack(VarInt)

            await self.handle_block_removal(block_id, Pos(x, y, z))

    @command("saveboundary")
    async def save_boundary(self: ProxhyPlugin):
        if self.game.gametype != "bedwars":
            self.downstream.chat("This command can only be used in a Bedwars game!")
            return

        if self.boundary_corner_1 == Pos(0, 0, 0) == self.boundary_corner_2:
            self.downstream.chat("Boundary is not updated yet! Aborting...")
            return

        if self.game.map is None:
            self.logger.warning("self.game.map is None")
            return

        if not hasattr(self, "map_data"):
            self.logger.warning("No map data loaded for the current map.")
            return

        corner1 = [
            self.boundary_corner_1.x,
            self.boundary_corner_1.y,
            self.boundary_corner_1.z,
        ]
        corner2 = [
            self.boundary_corner_2.x,
            self.boundary_corner_2.y,
            self.boundary_corner_2.z,
        ]

        prev: dict[str, list[int]] | None = self.map_data.get("boundary")
        if prev is None:
            prev_tc = TextComponent("None").color("red")
        else:
            prev_tc = TextComponent(
                f"({prev['corner1'][0]}, {prev['corner1'][1]}, {prev['corner1'][2]}) -> {prev['corner2'][0]}, {prev['corner2'][1]}, {prev['corner2'][2]}"
            )

        self.map_data.setdefault("boundary", {})
        self.map_data["boundary"]["corner1"] = corner1
        self.map_data["boundary"]["corner2"] = corner2

        self.logger.info(
            f"Saved boundary for {self.game.map.name}: {corner1} -> {corner2}"
        )

        maps_path = Path(__file__).resolve().parents[1] / "assets" / "bedwars_maps.json"

        try:
            with maps_path.open("w", encoding="utf-8") as f:
                json.dump(BW_MAPS, f, ensure_ascii=False, indent=4, sort_keys=True)
            msg_saved = (
                TextComponent("Saved boundary for ")
                .bold(False)
                .append(self.game.map.name.capitalize())
                .bold(True)
                .append(".")
                .bold(False)
            )
            msg_old = TextComponent("Old Boundary: ").append(prev_tc)
            msg_new = (
                TextComponent("New Boundary: ")
                .color("white")
                .append(TextComponent(f"({corner1[0]}, {corner1[1]}, {corner1[2]})"))
                .color("yellow")
                .append(TextComponent(" -> "))
                .color("white")
                .append(TextComponent(({corner2[0]}, {corner2[1]}, {corner2[2]})))
                .color("yellow")
            )
            self.downstream.chat(
                TextComponent("\n")
                .append(msg_saved)
                .append("\n")
                .append(msg_old)
                .append("\n")
                .append(msg_new)
                .append("\n")
            )
        except OSError as e:
            self.logger.exception(f"Failed to write {maps_path}: {e}")
            self.downstream.chat("Could not save boundary! See output log.")

    @command("gencheck")
    async def manual_generator_check(self: ProxhyPlugin) -> None:
        """manually update generator positions"""
        if self.game.gametype != "bedwars" or not hasattr(self, "map_data"):
            return

        # it's maybe possible but unlikely we haven't initialized these yet
        self.map_data.setdefault("generators", {})
        self.map_data["generators"].setdefault("emerald", [])
        self.map_data["generators"].setdefault("diamond", [])

        self.update_gen_positions()

    async def loop_gen_check(self: ProxhyPlugin):
        while True:
            await asyncio.sleep(self.GEN_CHECK_TIME)
            if (
                not self.game.started
                or self.game.gametype != "bedwars"
                or not hasattr(self, "map_data")
            ):
                continue
            self.update_gen_positions()

    def update_gen_positions(self: ProxhyPlugin):
        """
        Returns a dict of currently loaded diamond/emerald
        generator positions, sourced through proxhy gamestate.
        """
        if self.game.map is None:
            self.logger.warning("self.game.map is None")
            return

        updated = False
        for entity in self.gamestate.entities.values():
            pos_list = [entity.position.x, entity.position.y, entity.position.z]

            # filter armor stands
            if entity.entity_type != 78:
                continue

            # if we've already tracked this position
            if (
                pos_list in self.map_data["generators"]["diamond"]
                or pos_list in self.map_data["generators"]["emerald"]
            ):
                continue

            name_meta = entity.metadata.get(2)  # custom name in entity metadata
            if name_meta is None:
                # this essentially doesn't happen but it makes type checker happy
                continue

            name_text = str(name_meta.value)

            if "diamond" in name_text.casefold():
                updated = True
                self.map_data["generators"]["diamond"].append(pos_list)
                if self.output_generator_logs:
                    self.logger.log(
                        20,
                        f"Wrote new diamond generator for {self.game.map.name.upper()} at {pos_list}.",
                    )

            elif "emerald" in name_text.casefold():
                updated = True
                self.map_data["generators"]["emerald"].append(pos_list)
                if self.output_generator_logs:
                    self.logger.log(
                        20,
                        f"Wrote new emerald generator for {self.game.map.name.upper()} at {pos_list}.",
                    )
        if updated:
            n_teams = self.get_bedwars_team_count()
            n_emerald = 2 if n_teams in {2, 4} else 4
            n_diamond = 4 if n_teams in {4, 8} else 2

            self._save_bedwars_map_data()
            if len(self.map_data["generators"]["emerald"]) > n_emerald:
                self.logger.warning(
                    f">{n_emerald} emerald gens: {self.map_data['generators']['emerald']}"
                )
            if len(self.map_data["generators"]["diamond"]) > n_diamond:
                self.logger.warning(
                    f">{n_diamond} diamond gens: {self.map_data['generators']['diamond']}"
                )
            if (
                len(self.map_data["generators"]["diamond"]) == n_diamond
                and len(self.map_data["generators"]["emerald"]) == n_emerald
            ):
                if self.send_chat_notifs:
                    self.downstream.chat(
                        TextComponent(
                            f"Successfully logged {n_diamond} diamond generators and {n_emerald} emerald generators for map "
                        )
                        .color("green")
                        .bold(False)
                        .append(
                            TextComponent(self.game.map.name.upper())
                            .color("yellow")
                            .bold()
                            .append(TextComponent(".").color("green").bold(False))
                        )
                    )

    async def loop_boundaries_check(self: ProxhyPlugin):
        while True:
            await asyncio.sleep(self.CHECK_BOUNDARIES_TIME)
            if (
                not self.game.started
                or self.game.gametype != "bedwars"
                or not hasattr(self, "map_data")
                or len(self.boundary_regions) == self.n_total_boundaries
            ):
                continue
            await self.check_loaded_boundaries()

    # TODO: move this to another file?
    @staticmethod
    def distance_to(
        p1: tuple[float, float, float], p2: tuple[float, float, float]
    ) -> float:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        return math.sqrt(dx**2 + dy**2 + dz**2)

    async def check_loaded_boundaries(self: ProxhyPlugin):
        # first initialize any un-initialized boundaries if they're loaded
        if not len(self.boundary_regions):
            return
        for r in self.boundary_regions:
            if r.initialized_segments:
                continue
            c1_block = self.gamestate.get_block(r.c1.x, r.c1.y, r.c1.z)
            c2_block = self.gamestate.get_block(r.c2.x, r.c2.y, r.c2.z)
            if c1_block == -1 or c2_block == -1:
                # either boundary corner is unloaded
                continue

            # now we have an uninitialized boundary region with both corners loaded
            # we can safely initialize its segments

            # might be laggy but this is in a non-blocking task
            await asyncio.to_thread(r.initialize_segments)

        # check if any boundaries are close enough to render them
        player_position = (
            self.gamestate.position.x,
            self.gamestate.position.y,
            self.gamestate.position.z,
        )
        for r in self.boundary_regions:
            if not r.initialized_segments:
                continue

            dist_c1 = self.distance_to(player_position, tuple(r.c1))
            dist_c2 = self.distance_to(player_position, tuple(r.c2))

            boundary_dist = min([dist_c1, dist_c2])
            if not r.displayed:
                # check if we should display it
                if boundary_dist < self.BOUNDARY_CULL_RADIUS:
                    await self.render_boundary(r)

            elif r.displayed:
                # check if we should cull it
                if boundary_dist > self.BOUNDARY_CULL_RADIUS:
                    await self.unrender_boundary(r)

    async def render_boundary(self: ProxhyPlugin, region: BoundaryRegion):
        """Places all segments in a given boundary region in the world"""
        print("render_boundary")
        if not region.initialized_segments:
            raise ValueError("Cannot render a boundary with uninitialized segments!")

        for s in region:
            rot, offset = self._get_segment_rotation_and_offsets(s)
            # add 0.5 to center on block
            position = (
                s.x + offset[0] + 0.5,
                s.y + offset[1] + 0.5,
                s.z + offset[2] + 0.5,
            )
            is_corner = s.corner != SegmentCorner.NOT_CORNER
            await self.place_boundary_segment(position, is_corner, rot)

        region.displayed = True

    async def unrender_boundary(self, region: BoundaryRegion):
        """Removes all segments in a given rendered boundary region in the world."""
        pass

    def _get_segment_rotation_and_offsets(
        self: ProxhyPlugin, s: BoundarySegment
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """
        Gets the pitch, yaw, roll of boundary segment, and the coordinate offset to apply.
            Returns:
                tuple[
                    tuple[float, float, float]: pitch, yaw, roll (degrees)
                    tuple[float, float, float]: coordinate offset (x, y, z)
                ]
        """

        CORNER = SegmentCorner
        DIR = SegmentDirection
        SIDE = SegmentSide
        FACE = BlockFace

        TOP_FACE_ERR = "Unknown behavior for top face."

        def get_pitch() -> int:
            if s.block_face == FACE.BOTTOM:
                return 0
            elif s.block_face != FACE.TOP:
                return 90
            else:
                raise ValueError(TOP_FACE_ERR)

        def get_yaw() -> int:
            match s.block_face:
                case FACE.BOTTOM:
                    if s.corner == CORNER.NOT_CORNER:
                        # edge cases
                        state = (s.direction, s.side)
                        match state:
                            case DIR.Z, SIDE.NEGATIVE:
                                return 0
                            case DIR.X, SIDE.NEGATIVE:
                                return 90
                            case DIR.Z, SIDE.POSITIVE:
                                return 180
                            case DIR.X, SIDE.POSITIVE:
                                return 270
                            case _:
                                raise ValueError
                    else:
                        # corner cases
                        match s.corner:
                            case CORNER.NEG_POS:
                                return 0
                            case CORNER.NEG_NEG:
                                return 90
                            case CORNER.POS_NEG:
                                return 180
                            case CORNER.POS_POS:
                                return 270
                case FACE.NEG_Z:
                    return 0
                case FACE.POS_X:
                    return 90
                case FACE.POS_Z:
                    return 180
                case FACE.NEG_X:
                    return 270
                case FACE.TOP:
                    raise ValueError(TOP_FACE_ERR)

        def get_roll() -> int:
            if s.corner != CORNER.NOT_CORNER:
                return 0
            state = (s.block_face, s.side)
            match state:
                case FACE.BOTTOM, _:
                    return 0
                case FACE.NEG_Z, SIDE.NEGATIVE:
                    return 0
                case FACE.NEG_Z, SIDE.POSITIVE:
                    return 180
                case FACE.POS_X, SIDE.NEGATIVE:
                    return 0
                case FACE.POS_X, SIDE.POSITIVE:
                    return 180
                case FACE.POS_Z, SIDE.NEGATIVE:
                    return 180
                case FACE.POS_Z, SIDE.POSITIVE:
                    return 0
                case FACE.NEG_X, SIDE.NEGATIVE:
                    return 180
                case FACE.NEG_X, SIDE.POSITIVE:
                    return 0
                case FACE.TOP, _:
                    raise ValueError(TOP_FACE_ERR)
                case _:
                    raise ValueError(f"Unknown state {state}")

        pitch = get_pitch()
        yaw = get_yaw()
        roll = get_roll()

        # OFFSET_LOOKUP = {
        #     (0, 0, 0): (0, -1.75, 0),
        #     (0, 90, 0): (0, -1.75, 0),
        #     (0, 180, 0): (0, -1.75, 0),
        #     (0, 270, 0): (0, -1.75, 0),
        #     (90, 0, 0): (0, -1.43, -0.3),
        #     (90, 90, 0): (0.3, -1.43, 0),
        #     (90, 180, 0): (0, -1.43, 0.3),
        #     (90, 270, 0): (-0.3, -1.43, 0),
        #     (90, 0, 180): (0, -1.43, -0.3),
        #     (90, 90, 180): (0.3, -1.43, 0),
        #     (90, 180, 180): (0, -1.43, 0.3),
        #     (90, 270, 180): (-0.3, -1.43, 0),
        # }

        OFFSET_LOOKUP = {
            (0, 0, 0): (0, -1.75, 0),
            (0, 90, 0): (0, -1.75, 0),
            (0, 180, 0): (0, -1.75, 0),
            (0, 270, 0): (0, -1.75, 0),
            (90, 0, 0): (0, -1.43, 0.68),
            (90, 90, 0): (-0.68, -1.43, 0),
            (90, 180, 0): (0, -1.43, -0.68),
            (90, 270, 0): (0.68, -1.43, 0),
            (90, 0, 180): (0, -1.43, 0.68),
            (90, 90, 180): (-0.68, -1.43, 0),
            (90, 180, 180): (0, -1.43, -0.68),
            (90, 270, 180): (0.68, -1.43, 0),
        }

        offsets = OFFSET_LOOKUP.get((pitch, yaw, roll))
        if offsets is None:
            raise ValueError(f"Unknown rotation combination {pitch, yaw, roll}")

        return ((pitch, yaw, roll), offsets)

    # DEVELOPER DEBUG COMMAND; REMOVE LATER
    @command("place_boundary_here")
    async def place_boundary_here(
        self: ProxhyPlugin, pitch, yaw, roll, x_off, y_off, z_off
    ):
        ppos = (
            self.gamestate.position.x,
            self.gamestate.position.y,
            self.gamestate.position.z,
        )
        bpos = (
            math.floor(ppos[0]) + 0.5 + float(x_off),
            math.floor(ppos[1]) + 0.5 + float(y_off),
            math.floor(ppos[2]) + 0.5 + float(z_off),
        )
        rot = (float(pitch), float(yaw), float(roll))
        await self.place_boundary_segment(bpos, False, rot)

    async def place_boundary_segment(
        self: ProxhyPlugin,
        pos: tuple[float, float, float],
        is_corner: bool,
        rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ):
        # good edge case test maps for final boundary implementation:
        #   - apollo

        # armor stand internal id: 1E; network ID: 4E

        x_adjust = int(pos[0] * 32)  # "fixed-point number"
        y_adjust = int(pos[1] * 32)
        z_adjust = int(pos[2] * 32)

        # entity IDs are negative to avoid conflicts
        entity_id = self._allocate_boundary_entity_id()

        # spawn mob packet
        self.downstream.send_packet(
            0x0F,
            VarInt.pack(entity_id),
            UnsignedByte.pack(30),  # Type: Armor Stand
            Int.pack(x_adjust),
            Int.pack(y_adjust),
            Int.pack(z_adjust),
            Angle.pack(0),  # Yaw
            Angle.pack(0),  # Pitch
            Angle.pack(0),  # Head Pitch
            Short.pack(0),  # Velocity X
            Short.pack(0),  # Velocity Y
            Short.pack(0),  # Velocity Z
            # metadata inject
            # Index 0: Invisible
            UnsignedByte.pack(0x00),  # Header: Type 0, Index 0
            UnsignedByte.pack(0x20),  # Value: 0x20 bitmask
            # Index 10: Marker & NoGravity
            UnsignedByte.pack(0x0A),  # Header: Type 0, Index 10
            UnsignedByte.pack(0x12),  # Value: 0x10 (Marker) | 0x02 (NoGravity)
            # Index 11: Head Pose (Vector3f)
            UnsignedByte.pack(0xEB),  # Header: Type 7, Index 11
            Float.pack(rot[0]),  # Pitch (X)
            Float.pack(rot[1]),  # Yaw (Y)
            Float.pack(rot[2]),  # Roll (Z)
            UnsignedByte.pack(0x7F),  # Metadata Terminator
        )

        # entity equipment packet
        metadata = 0 if is_corner else 1
        self.downstream.send_packet(
            0x04,
            VarInt.pack(entity_id),
            Short.pack(4),  # Slot: 4 (Helmet)
            # -- SLOT DATA --
            Short.pack(97),  # Item ID: Monster Egg
            UnsignedByte.pack(1),  # Item Count: 1
            Short.pack(metadata),  # Item Damage/Metadata: 0/1 (stone/cobblestone)
            UnsignedByte.pack(0),  # NBT Terminator (Empty NBT compound)
        )


class BlockType(Enum):
    UNLOADED = -1
    AIR = 0
    SOLID = 1
    SLAB = 2
    STAIR = 3


class SegmentDirection(Enum):
    CORNER = 0
    X = 1
    Z = 2


class SegmentSide(Enum):
    CORNER = 0
    POSITIVE = 1
    NEGATIVE = -1


class SegmentCorner(Enum):
    """
    Nonzero means it's a corner.
    POS_POS: Corner points towards +x, +z
    POS_NEG: Points towards +x, -z
    NEG_POS: Points towards -x, +z
    NEG_NEG: Points towards -x, -z
    """

    NOT_CORNER = 0
    POS_POS = 1
    POS_NEG = 2
    NEG_POS = 3
    NEG_NEG = 4


class StairOrientation(Enum):
    UNKNOWN = 0
    NORTH = 1
    EAST = 2
    SOUTH = 3
    WEST = 4


class StairShape(Enum):
    TOP_HALF = 0
    BOTTOM_HALF = 1


class BoundaryFace(Enum):
    MIN_X = 0
    MAX_X = 1
    MIN_Y = 2
    MAX_Y = 3


class BlockFace(Enum):
    """
    Segments sit on the inner edge of air blocks. The default for
    segments is BOTTOM; the bottom of an air block means they'll
    appear directly on top of whatever block is beneath them.
    """

    BOTTOM = 0
    POS_X = 1
    POS_Z = 2
    NEG_X = 3
    NEG_Z = 4
    TOP = 5


@dataclass
class BoundarySegment(Pos):
    def __init__(
        self,
        x: int,
        y: int,
        z: int,
        direction: SegmentDirection,
        side: SegmentSide,
        type: BlockType,
        corner: SegmentCorner = SegmentCorner.NOT_CORNER,
        block_face: BlockFace = BlockFace.BOTTOM,
        metadata: dict | None = None,
    ):
        super().__init__(x, y, z)
        self.direction = direction
        self.side = side
        self.type = type
        self.corner = corner
        self.block_face = block_face
        self.metadata = metadata

    def pos_eq_other(self, other: BoundarySegment):
        if self.x == other.x and self.y == other.y and self.z == other.z:
            return True
        else:
            return False

    def pos_eq(self, pos: Pos):
        if self.x == pos.x and self.y == pos.y and self.z == pos.z:
            return True
        else:
            return False

    def get_adjacent_voxels(self):
        """
        Returns the eight positions adjacent & in line with direction:
            In front + 1 above + 1 below
            Behind + 1 above + 1 below
            Directly above; directly below
        """
        if self.direction == SegmentDirection.X:
            return [
                Pos(self.x + 1, self.y, self.z),
                Pos(self.x + 1, self.y + 1, self.z),
                Pos(self.x + 1, self.y - 1, self.z),
                Pos(self.x - 1, self.y, self.z),
                Pos(self.x - 1, self.y + 1, self.z),
                Pos(self.x - 1, self.y - 1, self.z),
                Pos(self.x, self.y + 1, self.z),
                Pos(self.x, self.y - 1, self.z),
            ]
        elif self.direction == SegmentDirection.Z:
            return [
                Pos(self.x, self.y, self.z + 1),
                Pos(self.x, self.y + 1, self.z + 1),
                Pos(self.x, self.y - 1, self.z + 1),
                Pos(self.x, self.y, self.z - 1),
                Pos(self.x, self.y + 1, self.z - 1),
                Pos(self.x, self.y - 1, self.z - 1),
                Pos(self.x, self.y + 1, self.z),
                Pos(self.x, self.y - 1, self.z),
            ]
        else:
            raise NotImplementedError("Corners not supported for get_adjacent_voxels")


class BoundaryChain:
    def __init__(self, iterable=(), maxlen=None):
        self._deque: deque[BoundarySegment] = deque(iterable, maxlen)
        self.merged = False

    def append(self, item):
        self._deque.append(item)

    def popleft(self):
        return self._deque.popleft()

    def __iter__(self):
        return iter(self._deque)

    def __len__(self):
        return len(self._deque)

    def __repr__(self):
        return f"BoundaryChain({list(self._deque)}, merged={self.merged})"

    def __getitem__(self, item):
        return self._deque[item]

    def appendleft(self, item):
        return self._deque.appendleft(item)

    def reverse(self):
        self._deque.reverse()

    def __add__(self, other):
        if not isinstance(other, (BoundaryChain, deque, list)):
            return NotImplemented
        other_deque = other._deque if isinstance(other, BoundaryChain) else other

        # build new object
        new_chain = BoundaryChain(list(self._deque) + list(other_deque))
        new_chain.merged = False
        return new_chain

    def __iadd__(self, other):
        if not isinstance(other, (BoundaryChain, deque, list)):
            return NotImplemented
        other_deque = other._deque if isinstance(other, BoundaryChain) else other
        self._deque.extend(other_deque)
        return self

    def __getattr__(self, name):
        # if BoundaryChain doesn't have the method look it up in deque
        return getattr(self._deque, name)


class BoundaryRegion:
    def __init__(
        self, c1: Pos, c2: Pos, gamestate: GameState, logger: logging.LoggerAdapter
    ):
        """Positions should be global positions in world, not local boundary boxes."""
        # a boundary region has a node at each corner of cuboid; 8 total
        self.c1 = c1
        self.c2 = c2

        self.nodes = (
            Pos(c1.x, c1.y, c1.z),
            Pos(c1.x, c1.y, c2.z),
            Pos(c1.x, c2.y, c1.z),
            Pos(c1.x, c2.y, c2.z),
            Pos(c2.x, c1.y, c1.z),
            Pos(c2.x, c1.y, c2.z),
            Pos(c2.x, c2.y, c1.z),
            Pos(c2.x, c2.y, c2.z),
        )

        # gamestate is necessary to query blocks at a location
        self.gamestate = gamestate
        self.logger = logger

        # this shouldn't take too long, but just to be safe, don't interrupt the packet stream
        self.initialized_segments: bool = False
        self.displayed: bool = False
        self.segments: list[BoundarySegment] = []

    def __iter__(self):
        yield from self.segments

    def validate_ids(self, ids: list[int]) -> None:
        if not all(0 <= i <= 7 for i in ids):
            raise ValueError("Invalid id received; must be int literal 0 through 7.")

    def get_node(self, id: int) -> Pos:
        self.validate_ids([id])
        return self.nodes[id]

    def get_nodes(self, ids: list[int]) -> list[Pos]:
        self.validate_ids(ids)

        out = []
        for id in ids:
            out.append(self.nodes[id])
        return out

    def initialize_segments(self):
        print("Initializing segments...")
        chains = self.compute_boundary_segments()
        self.segments = [
            segment for boundary_chain in chains for segment in boundary_chain
        ]
        self.initialized_segments = True
        print(f"Finished initializing segments with {len(self.segments)} segments.")

    def compute_boundary_segments(self) -> list[BoundaryChain]:
        min_x_face = [0, 1, 2, 3]
        max_x_face = [4, 5, 6, 7]
        min_z_face = [0, 2, 4, 6]
        max_z_face = [1, 3, 5, 7]

        faces = [min_x_face, max_x_face, min_z_face, max_z_face]
        chains: dict[BoundaryFace, list[BoundaryChain]] = {}

        for id, f in enumerate(faces):
            segments = self._get_segments_on_face(*f)
            linked = self._link_segments(segments)
            chains[BoundaryFace(id)] = linked

        unmerged_chains: list[BoundaryChain] = []
        for v in chains.values():
            unmerged_chains.extend(v)
        merged_chains = self._merge_chains(unmerged_chains)
        continuous_chains = [self._make_chain_continuous(c) for c in merged_chains]

        return continuous_chains

    def _make_chain_continuous(self, chain: BoundaryChain) -> BoundaryChain:
        """
        Adds vertical boundary segments where block elevation changes
        so the line appears continuous.
        """
        if len(chain) < 2:
            return chain

        flat_segments = list(chain)  # indexing middle deque elements is expensive

        out = BoundaryChain()
        for i in range(len(flat_segments) - 1):
            current_seg = flat_segments[i]
            next_seg = flat_segments[i + 1]

            out.append(current_seg)

            if current_seg.y != next_seg.y:
                connector = self._get_vertical_connector(current_seg, next_seg)
                out.append(connector)

        out.append(flat_segments[-1])
        return out

    def _get_vertical_connector(
        self, seg1: BoundarySegment, seg2: BoundarySegment
    ) -> BoundarySegment:
        # visit link below for a diagram to visualize this logic
        # https://drive.google.com/file/d/1Za_EJ_lQwuy1oSvR9RPwjHllaXweApbR/view?usp=sharing
        if (
            (
                seg1.side != seg2.side
                and SegmentSide.CORNER not in {seg1.side, seg2.side}
            )
            or (
                seg1.direction != seg2.direction
                and SegmentDirection.CORNER not in {seg1.direction, seg2.direction}
            )
            or seg1.y == seg2.y
        ):
            raise ValueError("Segments are not compatible.")

        if seg1.direction == seg2.direction == SegmentDirection.CORNER:
            raise ValueError(
                "Vertical connection unsupported between two adjacent corners."
            )

        if seg1.direction != seg2.direction:
            # one must be a corner
            if seg1.direction is SegmentDirection.CORNER:
                direction = seg2.direction
            else:
                direction = seg1.direction
        else:
            direction = seg1.direction

        if seg1.side != seg2.side:
            if seg1.side is SegmentSide.CORNER:
                side = seg2.side
            else:
                side = seg1.side
        else:
            side = seg1.side

        face: BlockFace
        lower = seg1 if seg1.y < seg2.y else seg2
        higher = seg1 if lower is seg2 else seg2
        if direction == SegmentDirection.X:
            if lower.x - higher.x > 0:
                face = BlockFace.POS_X
            else:
                face = BlockFace.NEG_X
        elif direction == SegmentDirection.Z:
            if lower.z - higher.z > 0:
                face = BlockFace.POS_Z
            else:
                face = BlockFace.NEG_Z
        else:
            raise ValueError("internal logic error in _get_vertical_connector")

        # TODO: should return type field really be lower.type?
        return BoundarySegment(
            lower.x,
            lower.y,
            lower.z,
            direction,
            side,
            lower.type,
            block_face=face,
        )

    def _merge_chains(self, chains: list[BoundaryChain]) -> list[BoundaryChain]:
        """Iteratively merges chains that intersect on corner boundaries."""
        while True:
            partially_merged: list[BoundaryChain] = []
            for chain in chains:
                if chain.merged:
                    continue
                for other_chain in chains:
                    if other_chain.merged or other_chain is chain:
                        continue

                    if chain[0].pos_eq_other(other_chain[0]):
                        # our head meets another chain's head
                        corner = self._merge_corner(other_chain[0], chain[0])

                        other_chain.popleft()
                        chain.popleft()

                        other_chain.reverse()
                        other_chain.append(corner)

                        # order: reversed other_chain (now tail-first) + chain
                        partially_merged.append(other_chain + chain)

                        chain.merged = True
                        other_chain.merged = True
                        break
                    elif chain[0].pos_eq_other(other_chain[-1]):
                        # our head meets another chain's tail
                        corner = self._merge_corner(other_chain[-1], chain[0])

                        other_chain.pop()
                        chain.popleft()
                        other_chain.append(corner)

                        partially_merged.append(other_chain + chain)

                        chain.merged = True
                        other_chain.merged = True
                        break
                    elif chain[-1].pos_eq_other(other_chain[0]):
                        # our tail meets another chain's head
                        corner = self._merge_corner(chain[-1], other_chain[0])

                        chain.pop()
                        other_chain.popleft()
                        chain.append(corner)

                        partially_merged.append(chain + other_chain)

                        chain.merged = True
                        other_chain.merged = True
                        break
                    elif chain[-1].pos_eq_other(other_chain[-1]):
                        # our tail meets another chain's tail
                        corner = self._merge_corner(chain[-1], other_chain[-1])

                        chain.pop()
                        other_chain.pop()

                        chain.append(corner)
                        other_chain.reverse()

                        # order: chain + reversed other_chain
                        partially_merged.append(chain + other_chain)

                        chain.merged = True
                        other_chain.merged = True
                        break

            unmerged = [c for c in chains if not c.merged]
            if len(unmerged) == len(chains):
                return chains  # no merges happened this pass

            partially_merged.extend(unmerged)

            chains = partially_merged

    def _merge_corner(
        self, s1: BoundarySegment, s2: BoundarySegment
    ) -> BoundarySegment:
        """Takes in two segments; returns their matching corner segment."""
        if not s1.pos_eq_other(s2):
            raise ValueError("Received two segments with different positions.")

        if s1.direction == s2.direction:
            raise ValueError("Received two segments that do not form a corner.")

        edge_info = {(s1.side, s1.direction), (s2.side, s2.direction)}
        pos = SegmentSide.POSITIVE
        neg = SegmentSide.NEGATIVE
        x = SegmentDirection.X
        z = SegmentDirection.Z

        if edge_info == {(pos, x), (pos, z)}:
            corner_type = SegmentCorner.POS_POS
        elif edge_info == {(neg, x), (pos, z)}:
            corner_type = SegmentCorner.POS_NEG
        elif edge_info == {(pos, x), (neg, z)}:
            corner_type = SegmentCorner.NEG_POS
        elif edge_info == {(neg, x), (neg, z)}:
            corner_type = SegmentCorner.NEG_NEG
        else:
            raise ValueError(f"Unknown corner type from edge info: {edge_info}.")

        return BoundarySegment(
            s1.x,
            s1.y,
            s1.z,
            SegmentDirection.CORNER,
            SegmentSide.CORNER,
            s1.type,
            corner_type,
        )

    def _get_segments_on_face(
        self, n1_id: int, n2_id: int, n3_id: int, n4_id: int
    ) -> list[BoundarySegment]:
        """
        Takes four nodes from self.nodes forming a cuboid face and returns the
        position and direction (x vs z) of each boundary marker in that plane.
        """
        # TODO: current implementation only takes vertical planes.
        # should it also accept xz planes for the top/bottom of the boundary?
        # how would the boundary line work?

        n1, n2, n3, n4 = self.get_nodes([n1_id, n2_id, n3_id, n4_id])

        # get the id of a node on the opposing plane to check what side of
        # the boundary this face is on
        given_ids = {n1_id, n2_id, n3_id, n4_id}
        all_ids = {0, 1, 2, 3, 4, 5, 6, 7}
        an_unused_id = (all_ids - given_ids).pop()
        opposite_node = self.get_node(an_unused_id)

        if n1.z == n2.z == n3.z == n4.z:
            direction = SegmentDirection.X
            if n1.z > opposite_node.z:
                side = SegmentSide.POSITIVE
            else:
                side = SegmentSide.NEGATIVE
        elif n1.x == n2.x == n3.x == n4.x:
            direction = SegmentDirection.Z
            if n1.x > opposite_node.x:
                side = SegmentSide.POSITIVE
            else:
                side = SegmentSide.NEGATIVE
        else:
            raise ValueError("Received nodes do not form a vertical plane.")

        segments: list[BoundarySegment] = []

        # don't need to check n4 because there are 2 sets of 2 y-coordinates in the 4 nodes
        top = max(n1.y, n2.y, n3.y)
        bottom = min(n1.y, n2.y, n3.y)

        if direction == SegmentDirection.X:
            right = max(n1.x, n2.x, n3.x)
            left = min(n1.x, n2.x, n3.x)
            self._scan_boundary_axis(
                segments, direction, side, left, right, n1.z, top, bottom
            )
        elif direction == SegmentDirection.Z:
            right = max(n1.z, n2.z, n3.z)
            left = min(n1.z, n2.z, n3.z)
            self._scan_boundary_axis(
                segments, direction, side, left, right, n1.x, top, bottom
            )
        else:
            raise ValueError(
                f"Unknown direction {direction}; expected {SegmentDirection.X} or {SegmentDirection.Z}."
            )

        return segments

    def _analyze_block(self, x: int, y: int, z: int) -> dict[str, Enum]:
        """
        Analyzes a block at the given world coordinates to determine its type and properties.

        Returns:
            dict: A dictionary containing boolean flags for block types and additional
                metadata for stairs (orientation and shape) if applicable.
        """
        state_id = self.gamestate.get_block(x, y, z)

        if state_id == -1:
            return {"type": BlockType.UNLOADED}

        block_id = state_id >> 4
        metadata = state_id & 0x0F

        # https://minecraft-ids.grahamedgecombe.com/
        AIR_ID = 0
        SLAB_IDS = {44, 126, 182, 205}
        STAIR_IDS = {53, 67, 108, 109, 114, 128, 134, 135, 136, 156, 163, 164, 180, 203}

        # evaluate block type
        if block_id == AIR_ID:
            return {"type": BlockType.AIR}
        elif block_id in SLAB_IDS:
            return {"type": BlockType.SLAB}
        elif block_id in STAIR_IDS:
            out: dict[str, Enum] = {"type": BlockType.STAIR}

            # append orientation and shape data lowest 2 bits (0x3) store the facing direction
            facing_map = {
                0: StairOrientation.EAST,
                1: StairOrientation.WEST,
                2: StairOrientation.SOUTH,
                3: StairOrientation.NORTH,
            }
            orientation = facing_map.get(metadata & 0x3, StairOrientation.UNKNOWN)
            # 3rd bit (0x4) indicates if stair is upside down (top half)
            shape = StairShape.TOP_HALF if (metadata & 0x4) else StairShape.BOTTOM_HALF
            out["orientation"] = orientation
            out["shape"] = shape
            return out
        else:
            return {"type": BlockType.SOLID}

    def _scan_boundary_axis(
        self,
        segments: list[BoundarySegment],
        direction: SegmentDirection,
        side: SegmentSide,
        start: int,
        end: int,
        fixed: int,
        top: int,
        bottom: int,
    ) -> None:
        # loop: work from the top down; if we see an air block, then
        # next non-air needs to be appropriate boundary shape
        for coord in range(start, end + 1):
            found_air = False
            for y in reversed(list(range(bottom, top + 1))):
                if direction == SegmentDirection.X:
                    block = self._analyze_block(coord, y, fixed)
                    x = coord
                    z = fixed
                elif direction == SegmentDirection.Z:
                    block = self._analyze_block(fixed, y, coord)
                    x = fixed
                    z = coord
                else:
                    raise ValueError(
                        f"Unknown direction '{direction}'; expected {SegmentDirection.X} or {SegmentDirection.Z}."
                    )

                blocktype = block.get("type")

                if blocktype == BlockType.UNLOADED:
                    continue
                if blocktype == BlockType.AIR:
                    found_air = True
                    continue

                found_air = self._append_segment_if_needed(
                    segments, x, y, z, direction, side, block, found_air
                )

    def _append_segment_if_needed(
        self,
        segments: list[BoundarySegment],
        x: int,
        y: int,
        z: int,
        direction: SegmentDirection,
        side: SegmentSide,
        block: dict[str, Enum],
        found_air: bool,
    ) -> bool:
        if not found_air:
            return False

        blocktype = block.get("type")
        if blocktype == BlockType.SLAB:
            segments.append(
                BoundarySegment(x, y + 1, z, direction, side, BlockType.SLAB)
            )
            return False
        if blocktype == BlockType.STAIR:
            segments.append(
                BoundarySegment(
                    x,
                    y + 1,
                    z,
                    direction,
                    side,
                    BlockType.STAIR,
                    metadata={
                        "orientation": block.get("orientation"),
                        "shape": block.get("shape"),
                    },
                )
            )
            return False
        if blocktype == BlockType.SOLID:
            segments.append(
                BoundarySegment(x, y + 1, z, direction, side, BlockType.SOLID)
            )
            return False

        return found_air

    def _link_segments(self, segments: list[BoundarySegment]) -> list[BoundaryChain]:
        """
        Takes a list of unordered BoundarySegments and organizes them into several
        ordered BoundaryChains representing specific lines traced by the boundary
        segments.
            Returns:
                an unordered list of BoundaryChains.
        """
        if len(segments) == 0:
            self.logger.warning("Received empty segments list!")
            return []
            # raise ValueError("segments is empty!")

        paths: list[BoundaryChain] = []
        for s in segments:
            done = False
            for path in paths:
                for pos in path[0].get_adjacent_voxels():
                    if s.pos_eq(pos):
                        path.appendleft(s)
                        done = True
                        break
                if not done:
                    for pos in path[-1].get_adjacent_voxels():
                        if s.pos_eq(pos):
                            path.append(s)
                            done = True
                            break
                if done:
                    break
            if not done:
                # made it through all paths; didn't find a path we belong to
                # paths.append(deque([s]))
                paths.append(BoundaryChain([s]))

        # consolodate/merge all paths that quietly met up
        merged = True
        while merged:
            merged = False
            for path_index, path in enumerate(paths):
                if not path:
                    continue

                for other_index, other_path in enumerate(paths):
                    if path_index == other_index or not other_path:
                        continue

                    path_start = path[0]
                    path_end = path[-1]
                    other_start = other_path[0]
                    other_end = other_path[-1]

                    if any(
                        other_start.pos_eq(pos)
                        for pos in path_start.get_adjacent_voxels()
                    ):
                        while other_path:
                            path.appendleft(other_path.popleft())
                        merged = True
                        break

                    if any(
                        other_end.pos_eq(pos)
                        for pos in path_start.get_adjacent_voxels()
                    ):
                        while other_path:
                            path.appendleft(other_path.pop())
                        merged = True
                        break

                    if any(
                        other_start.pos_eq(pos)
                        for pos in path_end.get_adjacent_voxels()
                    ):
                        while other_path:
                            path.append(other_path.popleft())
                        merged = True
                        break

                    if any(
                        other_end.pos_eq(pos) for pos in path_end.get_adjacent_voxels()
                    ):
                        while other_path:
                            path.append(other_path.pop())
                        merged = True
                        break

                if merged:
                    break

        # garbage cleanup: remove now-empty paths
        return [path for path in paths if path]
