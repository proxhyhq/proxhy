"""
Outline boundaries for "You can't place blocks here!"
regions around bases and diamond/emerald generators.

Implements many data collection pipelines, since
these bounding boxes are not easily exposed to the
client.
"""

import asyncio
import json
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

        # developer flag to enable features that make it
        # easier to get the boundary positions on new maps
        self.log_boundaries = True
        self.log_generators = True
        self.output_generator_logs = True

        # chat notifications for developer data collection pipelines
        self.send_chat_notifs = True

        self.teams_populated = False

        # corners relative to spawn position
        # based on direction facing when you spawned in
        self.boundary_corner_1 = Pos(0, 0, 0)
        self.boundary_corner_2 = Pos(0, 0, 0)

        # window in which to consider the "you can't place blocks here!" chat msg as being recent
        self.CPB_WINDOW = 0.2

        # how often should we check for nearby generators (in seconds)
        self.GEN_CHECK_TIME = 1

        if self.log_generators:
            self.create_task(self.loop_gen_check())

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
        # TODO: debug why it only works on some maps
        #   - known debug: this method is still getting called for those maps, not sure where it's exiting early tho
        #   - known debug: own spawnpoint WAS logged during these trials, so nearest spawnpoint is valid
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
            prev_tc = TextComponent(f"{prev['corner1']} -> {prev['corner2']}")

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
                .append(TextComponent(corner1))
                .color("yellow")
                .append(TextComponent(" -> "))
                .color("white")
                .append(TextComponent(corner2))
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
            # print("Looping...")
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
                # print(f"Found diamond gen at {pos_list}")

            elif "emerald" in name_text.casefold():
                updated = True
                self.map_data["generators"]["emerald"].append(pos_list)
                if self.output_generator_logs:
                    self.logger.log(
                        20,
                        f"Wrote new emerald generator for {self.game.map.name.upper()} at {pos_list}.",
                    )
                # print(f"Found emerald gen at {pos_list}")
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

        # else:
        # print("Did not find generators.")

    async def place_boundary(
        self: ProxhyPlugin,
        pos: tuple[float, float, float],
        b_type: Literal["corner", "edge"],
        rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ):
        # good edge case test maps for final boundary implementation:
        #   - apollo

        # armor stand internal id: 1E; network ID: 4E

        x_adjust = int(pos[0] * 32)  # "fixed-point number"
        y_adjust = int(pos[1] * 32)
        z_adjust = int(pos[2] * 32)

        # spawn mob packet
        self.downstream.send_packet(
            0x0F,
            VarInt.pack(999),  # Entity ID
            UnsignedByte.pack(78),  # Type: Armor Stand
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
        metadata = 0 if b_type == "edge" else 1
        self.downstream.send_packet(
            0x04,
            VarInt.pack(999),  # Entity ID (must match the spawn packet)
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
    X = 0
    Z = 1


class SegmentSide(Enum):
    POSITIVE = 1
    NEGATIVE = -1


class StairOrientation(Enum):
    UNKNOWN = 0
    NORTH = 1
    EAST = 2
    SOUTH = 3
    WEST = 4


class StairShape(Enum):
    TOP_HALF = 0
    BOTTOM_HALF = 1


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
        metadata: dict | None = None,
    ):
        super().__init__(x, y, z)
        self.direction = direction
        self.side = side
        self.type = type
        self.metadata = metadata

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


class BoundaryRegion:
    def __init__(self, c1: Pos, c2: Pos, gamestate: GameState):
        """Positions should be global positions in world, not local boundary boxes."""
        # a boundary region has a node at each corner of cuboid; 8 total
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

    def compute_boundary_segments(self):
        min_x_face = [0, 1, 2, 3]
        max_x_face = [4, 5, 6, 7]
        min_y_face = [0, 1, 4, 5]
        max_y_face = [2, 3, 6, 7]

        faces = [min_x_face, max_x_face, min_y_face, max_y_face]

        for f in faces:
            segments = self._get_segments_on_face(*f)

    def _get_segments_on_face(
        self, n1_id: int, n2_id: int, n3_id: int, n4_id: int
    ) -> list[BoundarySegment]:
        """
        Takes four nodes from self.nodes forming a cuboid face and returns the
        position and direction (x vs z) of each boundary marker in that plane.
        """
        # TODO: current wip implementation only takes vertical planes.
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
        # non-air needs to be appropriate boundary shape
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
                    break  # other y levels will also be unloaded
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
            segments.append(BoundarySegment(x, y, z, direction, side, BlockType.SLAB))
            return False
        if blocktype == BlockType.STAIR:
            segments.append(
                BoundarySegment(
                    x,
                    y,
                    z,
                    direction,
                    side,
                    BlockType.STAIR,
                    {
                        "orientation": block.get("orientation"),
                        "shape": block.get("shape"),
                    },
                )
            )
            return False
        if blocktype == BlockType.SOLID:
            segments.append(BoundarySegment(x, y, z, direction, side, BlockType.SOLID))
            return False

        return found_air

    def _link_segments(
        self, segments: list[BoundarySegment]
    ) -> list[deque[BoundarySegment]]:
        """
        Takes a list of unordered BoundarySegments and organizes them into several
        ordered deques representing specific lines traced by the boundary segments.
        Returns an unordered list of these ordered deques.
        """
        if len(segments) == 0:
            raise ValueError("segments is empty!")

        paths: list[deque[BoundarySegment]] = []
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
                paths.append(deque([s]))

        return paths
