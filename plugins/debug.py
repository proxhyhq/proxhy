import asyncio
import json
from collections import deque
from dataclasses import is_dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from platformdirs import user_log_path

from petty.protocol.datatypes import TextComponent
from plugins.boundaries import BoundaryRegion
from plugins.commands import command

if TYPE_CHECKING:
    from proxhy.plugin import ProxhyPlugin


def _json_default(obj: object) -> object:
    """
    Fallback serializer for the debug export's json.dump call.

    Handles the non-stdlib types found throughout gamestate/statcheck state
    (jitclass Vec3d/Vec3i, dataclasses, Enums, deques, asyncio.Task, etc.).
    json re-invokes this on whatever is returned, so returning a dict/list
    of still-unserializable values is fine; it recurses until everything
    bottoms out.
    """
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, asyncio.Task):
        return f"<Task done={obj.done()}>"
    if is_dataclass(obj) and not isinstance(obj, type):
        return vars(obj)
    if hasattr(obj, "x") and hasattr(obj, "y") and hasattr(obj, "z"):
        return {"x": obj.x, "y": obj.y, "z": obj.z}
    if isinstance(obj, (set, frozenset, deque)):
        return list(obj)
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"
    return str(obj)


def _dump_boundary_region(region: BoundaryRegion) -> dict:
    """
    Full debug snapshot of a boundary region: computed segments plus a raw
    per-face block scan (every block visited, not just the ones that ended
    up producing a segment), so gaps/missing segments can be diagnosed from
    the exported file instead of re-joining the game.
    """
    face_node_ids = {
        "min_x": (0, 1, 2, 3),
        "max_x": (4, 5, 6, 7),
        "min_z": (0, 2, 4, 6),
        "max_z": (1, 3, 5, 7),
    }

    face_scans = {}
    for face_name, ids in face_node_ids.items():
        n1, n2, n3, n4 = region.get_nodes(list(ids))

        # mirrors BoundaryRegion._get_segments_on_face's direction/range detection
        if n1.z == n2.z == n3.z == n4.z:
            direction = "x"
            fixed = n1.z
            start, end = min(n1.x, n2.x, n3.x), max(n1.x, n2.x, n3.x)
        elif n1.x == n2.x == n3.x == n4.x:
            direction = "z"
            fixed = n1.x
            start, end = min(n1.z, n2.z, n3.z), max(n1.z, n2.z, n3.z)
        else:
            continue

        top, bottom = max(n1.y, n2.y, n3.y), min(n1.y, n2.y, n3.y)

        columns = []
        for coord in range(start, end + 1):
            blocks = []
            for y in range(bottom, top + 1):
                x, z = (coord, fixed) if direction == "x" else (fixed, coord)
                info = region._analyze_block(x, y, z)
                blocks.append(
                    {
                        "y": y,
                        "type": info["type"].name,
                        "orientation": info["orientation"].name
                        if "orientation" in info
                        else None,
                        "shape": info["shape"].name if "shape" in info else None,
                    }
                )
            columns.append({"coord": coord, "blocks": blocks})

        face_scans[face_name] = {
            "direction": direction,
            "fixed": fixed,
            "coord_range": [start, end],
            "y_range": [bottom, top],
            "columns": columns,
        }

    return {
        "c1": {"x": region.c1.x, "y": region.c1.y, "z": region.c1.z},
        "c2": {"x": region.c2.x, "y": region.c2.y, "z": region.c2.z},
        "team": getattr(region, "team", None),
        "mirrored": getattr(region, "mirrored", None),
        "initialized_segments": region.initialized_segments,
        "displayed": region.displayed,
        "segment_count": len(region.segments),
        "segments": [
            {
                "x": s.x,
                "y": s.y,
                "z": s.z,
                "direction": s.direction.name,
                "side": s.side.name,
                "type": s.type.name,
                "corner": s.corner.name,
                "block_face": s.block_face.name,
                "metadata": s.metadata,
            }
            for s in region.segments
        ],
        "face_scans": face_scans,
    }


class DebugPlugin:
    @command("boundarydebug", "dumpboundaries")
    async def export_boundary_debug(self: ProxhyPlugin) -> None:
        """Exports gamestate, loaded boundaries, and other debug info to a file."""
        data = self._build_boundary_debug_export()

        debug_dir = user_log_path("proxhy") / "debug"
        try:
            debug_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.exception(f"Failed to create debug directory: {e}")
            self.downstream.chat("Could not create debug directory! See output log.")
            return

        filename = f"boundary_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = debug_dir / filename

        try:
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=_json_default)
        except OSError as e:
            self.logger.exception(f"Failed to write debug export {filepath}: {e}")
            self.downstream.chat("Could not export debug info! See output log.")
            return

        n_regions = len(self.boundary_regions)
        n_segments = sum(len(r.segments) for r in self.boundary_regions)
        self.logger.info(f"Exported boundary debug info to {filepath}")
        self.downstream.chat(
            TextComponent("Exported boundary debug info (")
            .color("green")
            .append(
                TextComponent(f"{n_regions} regions, {n_segments} segments").color(
                    "yellow"
                )
            )
            .append(") to ")
            .append(TextComponent(str(filepath)).color("gold"))
        )

    def _build_boundary_debug_export(self: ProxhyPlugin) -> dict:
        """Assembles the full debug snapshot dumped by /boundarydebug."""
        game_players_export = {}
        if hasattr(self, "game_players"):
            for username, gp in self.game_players.items():
                game_players_export[username] = {
                    "uuid": str(gp.uuid),
                    "team": gp.team.name if gp.team else None,
                    "status": gp.status,
                    "respawn_time": gp.respawn_time,
                }

        generator_entities = []
        for entity in self.gamestate.entities.values():
            if entity.entity_type != 78:  # armor stand
                continue
            name_meta = entity.metadata.get(2)
            generator_entities.append(
                {
                    "entity_id": entity.entity_id,
                    "position": {
                        "x": entity.position.x,
                        "y": entity.position.y,
                        "z": entity.position.z,
                    },
                    "name": str(name_meta.value) if name_meta else None,
                }
            )

        return {
            "exported_at": datetime.now().isoformat(),
            "game": {
                "server": self.game.server,
                "gametype": self.game.gametype,
                "mode": self.game.mode,
                "map": self.game.map.name if self.game.map else None,
                "lobbyname": self.game.lobbyname,
                "started": self.game.started,
                "team_count": self.get_bedwars_team_count(),
                "teams_populated": self.teams_populated,
                "last_game_start": self.last_game_start,
                "game_recently_started": self.game_recently_started(),
            },
            "flags": {
                "log_boundaries": self.log_boundaries,
                "log_generators": self.log_generators,
                "output_generator_logs": self.output_generator_logs,
                "render_boundaries": self.render_boundaries,
                "send_chat_notifs": self.send_chat_notifs,
                "BOUNDARY_CULL_RADIUS": self.BOUNDARY_CULL_RADIUS,
                "CHECK_BOUNDARIES_TIME": self.CHECK_BOUNDARIES_TIME,
                "CPB_WINDOW": self.CPB_WINDOW,
                "GEN_CHECK_TIME": self.GEN_CHECK_TIME,
            },
            "map_data": getattr(self, "map_data", None),
            "learned_boundary": {
                "corner1": [
                    self.boundary_corner_1.x,
                    self.boundary_corner_1.y,
                    self.boundary_corner_1.z,
                ],
                "corner2": [
                    self.boundary_corner_2.x,
                    self.boundary_corner_2.y,
                    self.boundary_corner_2.z,
                ],
            },
            "n_total_boundaries": self.n_total_boundaries,
            "n_initialized_boundary_regions": len(self.boundary_regions),
            "base_parity": getattr(self, "base_parity", None),
            "team_spawnpoints": self.team_spawnpoints,
            "entities_teleported": self.entities_teleported,
            "recently_placed": [
                {"x": p.x, "y": p.y, "z": p.z} for p in self.recently_placed
            ],
            "placed_mappings": list(self.placed_mappings),
            "player": {
                "position": {
                    "x": self.gamestate.position.x,
                    "y": self.gamestate.position.y,
                    "z": self.gamestate.position.z,
                },
                "rotation": {
                    "yaw": self.gamestate.rotation.yaw,
                    "pitch": self.gamestate.rotation.pitch,
                },
                "dimension": self.gamestate.dimension.name,
                "gamemode": self.gamestate.gamemode.name,
            },
            "loaded_chunks": [[cx, cz] for (cx, cz) in self.gamestate.chunks],
            "game_players": game_players_export,
            "generator_entities": generator_entities,
            "teams": self.gamestate.teams,
            "boundary_regions": [_dump_boundary_region(r) for r in self.boundary_regions],
        }

    @command("game")
    async def _command_game(self: ProxhyPlugin):
        """Display current game info."""
        self.downstream.chat(TextComponent("Game:").color("green"))
        for key in type(self.game).__annotations__:
            if value := getattr(self.game, key):
                self.downstream.chat(
                    TextComponent(f"{key.capitalize()}: ")
                    .color("aqua")
                    .append(TextComponent(str(value)).color("yellow"))
                )

    @command("nicked")
    async def _command_nicked(self: ProxhyPlugin):
        msg = (
            TextComponent("Nicked:")
            .color("yellow")
            .appends(
                TextComponent(f"{(nicked := self.nick is not None)}").color(
                    "green" if nicked else "red"
                )
            )
        )
        if nicked:
            msg = msg.appends(
                TextComponent("(")
                .color("yellow")
                .append(TextComponent(self.nick).color("aqua"))
                .append(TextComponent(")").color("yellow"))
            )

        return msg

    @command("rqgame")
    async def _command_rqgame(self: ProxhyPlugin):
        """Display requeue game info."""
        self.downstream.chat(TextComponent("Requeue Game:").color("green"))
        for key in type(self.rq_game).__annotations__:
            if value := getattr(self.rq_game, key):
                self.downstream.chat(
                    TextComponent(f"{key.capitalize()}: ")
                    .color("aqua")
                    .append(TextComponent(str(value)).color("yellow"))
                )

    @command("teams")
    async def _command_teams(self: ProxhyPlugin):
        """[DEBUG] Print out all current teams known to Proxhy."""
        print("\n")
        for team_name, team in self.gamestate.teams.items():
            print(f"{team_name}: {team}")
        print("\n")

    @command("player_list")
    async def _command_player_list(self: ProxhyPlugin):
        """[DEBUG] List all players known to Proxhy."""
        print([(p.name, p.uuid) for p in self.gamestate.player_list.values()])

    @command("iphone_ringtone")
    async def _command_iphone_ringtone(self: ProxhyPlugin):
        """[DEBUG] Play the iPhone ringtone sound."""
        await self._iphone_ringtone()

    @command("samsung_ringtone")
    async def _command_samsung_ringtone(self: ProxhyPlugin):
        """[DEBUG] Play the Samsung ringtone sound."""
        await self._samsung_ringtone()

    @command("pos")
    async def _command_pos(self: ProxhyPlugin):
        """Get your current position."""
        self.downstream.chat(
            f"{self.gamestate.position.x} {self.gamestate.position.y} {self.gamestate.position.z}"
        )

    # @subscribe("chat:server:.*")
    # async def log_chat_msg(self, _match, buff: Buffer):
    #     buff = Buffer(buff.getvalue())
    #     print(buff.unpack(Chat))

    # @listen_server(0x38)
    # async def log_0x38(self, buff: Buffer):
    #     action = buff.unpack(VarInt)  # which of the 5 actions
    #     count = buff.unpack(VarInt)  # number of players affected
    #     print(f"\n0x38 Player Info packet: action={action}, count={count}")

    #     for _ in range(count):
    #         uuid = buff.unpack(UUID)
    #         print(f" - UUID: {uuid}")

    #         if action == 0:  # ADD_PLAYER
    #             name = buff.unpack(String)
    #             props_count = buff.unpack(VarInt)
    #             props = []
    #             for _ in range(props_count):
    #                 key = buff.unpack(String)
    #                 value = buff.unpack(String)
    #                 signed = buff.unpack(Boolean)
    #                 sig = buff.unpack(String) if signed else None
    #                 props.append((key, value, sig))
    #             gamemode = buff.unpack(VarInt)
    #             ping = buff.unpack(VarInt)
    #             has_display = buff.unpack(Boolean)
    #             display = buff.unpack(Chat) if has_display else None
    #             print(
    #                 f"   ADD_PLAYER name={name}, gamemode={gamemode}, ping={ping}, display={display}, len(props)={len(props)}"
    #             )

    #         elif action == 1:  # UPDATE_GAMEMODE
    #             gamemode = buff.unpack(VarInt)
    #             print(f"   UPDATE_GAMEMODE -> {gamemode}")

    #         elif action == 2:  # UPDATE_LATENCY
    #             ping = buff.unpack(VarInt)
    #             print(f"   UPDATE_LATENCY -> {ping} ms")

    #         elif action == 3:  # UPDATE_DISPLAY_NAME
    #             has_display = buff.unpack(Boolean)
    #             display = buff.unpack(Chat) if has_display else None
    #             print(f"   UPDATE_DISPLAY_NAME -> {display}")

    #         elif action == 4:  # REMOVE_PLAYER
    #             pass
    #             print("   REMOVE_PLAYER")

    #         else:
    #             pass
    #             print(f"   Unknown action {action}")
    #     print("")
