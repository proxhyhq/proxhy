import uuid as uuid_mod
from typing import Any, Literal

from petty.models import *  # noqa: F403
from petty.protocol.datatypes import *  # noqa: F403
from petty.protocol.datatypes import (
    UUID,
    Angle,
    Boolean,
    Byte,
    Chat,
    Double,
    Float,
    Int,
    Long,
    Position,
    Short,
    Slot,
    SlotData,
    String,
    UnsignedByte,
    UnsignedShort,
    VarInt,
)

# NOTE: these imports come from the Rust-backed `gamestate` package itself
# (i.e. the compiled `gamestate._gamestate` extension, re-exported through
# `gamestate/__init__.py`), NOT from the old dead `gamestate.models` /
# `gamestate.enums` pure-Python/numba modules. At runtime `self.entities`,
# `self.players`, etc. hold instances of these Rust classes, so isinstance()
# checks and constructors below must be checked against them.
from gamestate import (
    Dimension,
    Entity,
    EquipmentSlot,
    GameStateReason,
    MetadataValue,
    Player,
    PlayerAbilityFlags,
    PlayerInfo,
    PlayerListAction,
    TeamMode,
    TitleAction,
    Vec3i,
    WorldBorderAction,
)
from gamestate.constants import MOB_TYPES
from proxhy.utils import uuid_version

# (packet_id, packet_data) tuple returned by the packet-building helpers below.
type Packet = tuple[int, bytes]


class StateBuilders:
    def _build_join_game(
        self, eid: int | None = None, gamemode: Literal[1, 2, 3, 4] | None = None
    ) -> Packet:
        """Build Join Game packet (0x01)."""
        game_mode = gamemode or self.gamemode.value
        if self.is_hardcore:
            game_mode |= 8
        data = (
            Int.pack(eid or self.player_entity_id)
            + UnsignedByte.pack(game_mode)
            + Byte.pack(self.dimension.value)
            + UnsignedByte.pack(self.difficulty.value)
            + UnsignedByte.pack(self.max_players)
            + String.pack(self.level_type)
            + Boolean.pack(self.reduced_debug_info)
        )
        return (1, data)

    def _build_server_difficulty(self) -> Packet:
        """Build Server Difficulty packet (0x41)."""
        return (65, UnsignedByte.pack(self.difficulty.value))

    def _build_player_abilities(self) -> Packet:
        """Build Player Abilities packet (0x39)."""
        data = (
            Byte.pack(int(self.abilities))
            + Float.pack(self.flying_speed)
            + Float.pack(self.field_of_view_modifier)
        )
        return (57, data)

    def _build_held_item_change(self) -> Packet:
        """Build Held Item Change packet (0x09)."""
        return (9, Byte.pack(self.held_item_slot))

    def _build_spawn_position(self) -> Packet:
        """Build Spawn Position packet (0x05)."""
        pos = (self.spawn_position.x, self.spawn_position.y, self.spawn_position.z)
        return (5, Position.pack(pos))

    def _build_player_position_and_look(self) -> Packet:
        """Build Player Position And Look packet (0x08)."""
        data = (
            Double.pack(self.position.x)
            + Double.pack(self.position.y)
            + Double.pack(self.position.z)
            + Float.pack(self.rotation.yaw)
            + Float.pack(self.rotation.pitch)
            + Byte.pack(0)
        )
        return (8, data)

    def _build_update_health(self) -> Packet:
        """Build Update Health packet (0x06)."""
        data = (
            Float.pack(self.base_health)
            + VarInt.pack(self.food)
            + Float.pack(self.food_saturation)
        )
        return (6, data)

    def _build_set_experience(self) -> Packet:
        """Build Set Experience packet (0x1F)."""
        data = (
            Float.pack(self.experience_bar)
            + VarInt.pack(self.experience_level)
            + VarInt.pack(self.total_experience)
        )
        return (31, data)

    def _build_time_update(self) -> Packet:
        """Build Time Update packet (0x03)."""
        data = Long.pack(self.world_age) + Long.pack(self.time_of_day)
        return (3, data)

    def _build_world_border(self) -> Packet:
        """Build World Border packet (0x44) with Initialize action."""
        data = (
            VarInt.pack(WorldBorderAction.Initialize.value)
            + Double.pack(self.world_border.center_x)
            + Double.pack(self.world_border.center_z)
            + Double.pack(self.world_border.old_radius)
            + Double.pack(self.world_border.new_radius)
            + VarInt.pack(self.world_border.speed)
            + VarInt.pack(self.world_border.portal_boundary)
            + VarInt.pack(self.world_border.warning_time)
            + VarInt.pack(self.world_border.warning_blocks)
        )
        return (68, data)

    def _build_player_list_items(self) -> list[Packet]:
        """Build Player List Item packets (0x38) for all players."""
        if not self.player_list:
            return []
        packets: list[Packet] = []
        data = VarInt.pack(PlayerListAction.AddPlayer.value)
        data += VarInt.pack(len(self.player_list))
        for uuid, info in self.player_list.items():
            data += self._pack_uuid(uuid)
            data += String.pack(info.name)
            data += VarInt.pack(len(info.properties))
            for prop in info.properties:
                data += String.pack(prop.get("name", ""))
                data += String.pack(prop.get("value", ""))
                has_sig = prop.get("signature") is not None
                data += Boolean.pack(has_sig)
                if has_sig:
                    data += String.pack(prop["signature"])
            data += VarInt.pack(info.gamemode)
            data += VarInt.pack(info.ping)
            has_display = info.display_name is not None
            data += Boolean.pack(has_display)
            if has_display and info.display_name is not None:
                data += Chat.pack(info.display_name)
        packets.append((56, data))
        return packets

    def _build_player_list_header_footer(self) -> Packet:
        """Build Player List Header And Footer packet (0x47)."""
        data = String.pack(self.tab_header) + String.pack(self.tab_footer)
        return (71, data)

    def _build_scoreboard_objectives(self) -> list[Packet]:
        """Build Scoreboard Objective packets (0x3B)."""
        packets: list[Packet] = []
        for obj in self.objectives.values():
            data = (
                String.pack(obj.name)
                + Byte.pack(0)
                + String.pack(obj.display_text)
                + String.pack(obj.objective_type)
            )
            packets.append((59, data))
        return packets

    def _build_scoreboard_scores(self) -> list[Packet]:
        """Build Update Score packets (0x3C)."""
        packets: list[Packet] = []
        for objective_name, scores in self.scores.items():
            for score_name, score in scores.items():
                data = (
                    String.pack(score_name)
                    + Byte.pack(0)
                    + String.pack(objective_name)
                    + VarInt.pack(score.value)
                )
                packets.append((60, data))
        return packets

    def _build_display_scoreboards(self) -> list[Packet]:
        """Build Display Scoreboard packets (0x3D)."""
        packets: list[Packet] = []
        for position, score_name in self.display_slots.items():
            data = Byte.pack(position) + String.pack(score_name)
            packets.append((61, data))
        return packets

    def _build_teams(self) -> list[Packet]:
        """Build Teams packets (0x3E)."""
        packets: list[Packet] = []
        for team in self.teams.values():
            data = (
                String.pack(team.name)
                + Byte.pack(TeamMode.Create.value)
                + String.pack(team.display_name)
                + String.pack(team.prefix)
                + String.pack(team.suffix)
                + Byte.pack(team.friendly_fire)
                + String.pack(team.name_tag_visibility)
                + Byte.pack(team.color)
                + VarInt.pack(len(team.members))
            )
            for member in team.members:
                data += String.pack(member)
            packets.append((62, data))
        return packets

    def _build_chunk_data(self) -> list[Packet]:
        """Build Map Chunk Bulk packets (0x26) for all loaded chunks.

        Chunks are batched into multiple 0x26 packets to stay under the
        client's 21-bit (~2 MB) packet-length VarInt limit.  We cap the
        uncompressed chunk *data* portion of each batch so that even with
        modest zlib compression it stays well below the wire limit.
        """
        MAX_UNCOMPRESSED_DATA = 1500000
        sky_light_sent = self.dimension == Dimension.Overworld
        chunk_metas: list[tuple[int, int, int]] = []
        chunk_datas: list[bytes] = []
        for (chunk_x, chunk_z), chunk in self.chunks.items():
            primary_bitmask = 0
            for i, section in enumerate(chunk.sections):
                if section is not None:
                    primary_bitmask |= 1 << i
            if primary_bitmask == 0:
                continue
            chunk_data = b""
            for section in chunk.sections:
                if section is not None:
                    chunk_data += bytes(section.blocks)
            for section in chunk.sections:
                if section is not None:
                    chunk_data += bytes(section.block_light)
            if sky_light_sent:
                for section in chunk.sections:
                    if section is not None and section.sky_light is not None:
                        chunk_data += bytes(section.sky_light)
            chunk_data += bytes(chunk.biomes)
            chunk_metas.append((chunk_x, chunk_z, primary_bitmask))
            chunk_datas.append(chunk_data)
        if not chunk_metas:
            return []
        packets: list[Packet] = []
        batch_start = 0
        batch_data_size = 0
        for i, cd in enumerate(chunk_datas):
            if batch_data_size + len(cd) > MAX_UNCOMPRESSED_DATA and i > batch_start:
                packets.append(
                    self._pack_chunk_bulk(
                        sky_light_sent,
                        chunk_metas[batch_start:i],
                        chunk_datas[batch_start:i],
                    )
                )
                batch_start = i
                batch_data_size = 0
            batch_data_size += len(cd)
        packets.append(
            self._pack_chunk_bulk(
                sky_light_sent, chunk_metas[batch_start:], chunk_datas[batch_start:]
            )
        )
        return packets

    @staticmethod
    def _pack_chunk_bulk(
        sky_light_sent: bool, metas: list[tuple[int, int, int]], datas: list[bytes]
    ) -> Packet:
        """Serialise one 0x26 Map Chunk Bulk packet from pre-built parts."""
        buf = Boolean.pack(sky_light_sent) + VarInt.pack(len(metas))
        for cx, cz, bitmask in metas:
            buf += Int.pack(cx) + Int.pack(cz) + UnsignedShort.pack(bitmask)
        for cd in datas:
            buf += cd
        return (38, buf)

    def _build_block_entities(self) -> list[Packet]:
        """Build Update Block Entity packets (0x35)."""
        packets: list[Packet] = []
        for (x, y, z), block_entity in self.block_entities.items():
            data = (
                Position.pack((x, y, z))
                + UnsignedByte.pack(block_entity.action)
                + block_entity.nbt_data
            )
            packets.append((53, data))
        return packets

    def _build_entity_spawns(self) -> list[Packet]:
        """Build spawn packets for all entities."""
        packets: list[Packet] = []
        for entity in self.entities.values():
            if entity.entity_id == self.player_entity_id:
                continue
            if isinstance(entity, Player):
                packets.append(self._build_spawn_player(entity))
            elif entity.entity_type in MOB_TYPES:
                packets.append(self._build_spawn_mob(entity))
            else:
                if entity.entity_type == 2:
                    item_meta = entity.metadata.get(10)
                    if item_meta is None:
                        continue
                    if isinstance(item_meta, MetadataValue):
                        if not isinstance(item_meta.value, SlotData):
                            continue
                        if item_meta.value.item is None:
                            continue
                    elif isinstance(item_meta, SlotData):
                        if item_meta.item is None:
                            continue
                    else:
                        continue
                packets.append(self._build_spawn_object(entity))
        return packets

    def _build_spawn_player(self, player: Player) -> Packet:
        """Build Spawn Player packet (0x0C)."""
        data = (
            VarInt.pack(player.entity_id)
            + self._pack_uuid(player.uuid)
            + Int.pack(int(player.position.x * 32))
            + Int.pack(int(player.position.y * 32))
            + Int.pack(int(player.position.z * 32))
            + Angle.pack(player.rotation.yaw)
            + Angle.pack(player.rotation.pitch)
            + Short.pack(player.current_item)
            + self._pack_metadata(player.metadata)
        )
        return (12, data)

    def build_entity_teleports(self) -> list[Packet]:
        """Build Entity Teleport (0x18) packets for all tracked entities.

        Used to correct entity positions after a gap where relative move
        packets may have been missed (e.g. during broadcast client login).
        """
        packets: list[Packet] = []
        for entity in self.entities.values():
            if entity.entity_id == self.player_entity_id:
                continue
            packets.append(
                (
                    24,
                    VarInt.pack(entity.entity_id)
                    + Int.pack(int(entity.position.x * 32))
                    + Int.pack(int(entity.position.y * 32))
                    + Int.pack(int(entity.position.z * 32))
                    + Angle.pack(entity.rotation.yaw)
                    + Angle.pack(entity.rotation.pitch)
                    + Boolean.pack(entity.on_ground),
                )
            )
        return packets

    def _build_npc_player_spawns(self) -> list[Packet]:
        """Build packets to spawn NPC players (players not in tab list).

        Hypixel and other servers spawn NPCs as players, then remove them from
        the tab list. To respawn them, we need to:
        1. Add them to the tab list (required before Spawn Player)
        2. Spawn them
        3. Send their metadata
        4. Send their equipment
        5. Remove them from the tab list after a delay (via build_npc_removal_packets)
        """
        packets: list[Packet] = []
        self._last_synced_npc_uuids = []
        for uuid, player in self.players.items():
            if player.entity_id == self.player_entity_id:
                continue
            if uuid not in self.player_list:
                self._last_synced_npc_uuids.append(uuid)
                npc_team_name = None
                for team_name, team in self.teams.items():
                    if player.name in team.members:
                        npc_team_name = team_name
                        break
                add_data = VarInt.pack(PlayerListAction.AddPlayer.value)
                add_data += VarInt.pack(1)
                add_data += self._pack_uuid(uuid)
                add_data += String.pack(player.name or "")
                add_data += VarInt.pack(len(player.properties))
                for prop in player.properties:
                    add_data += String.pack(prop.get("name", ""))
                    add_data += String.pack(prop.get("value", ""))
                    has_sig = prop.get("signature") is not None
                    add_data += Boolean.pack(has_sig)
                    if has_sig:
                        add_data += String.pack(prop["signature"])
                add_data += VarInt.pack(0)
                add_data += VarInt.pack(0)
                add_data += Boolean.pack(False)
                packets.append((56, add_data))
                if npc_team_name:
                    team_data = String.pack(npc_team_name)
                    team_data += Byte.pack(3)
                    team_data += VarInt.pack(1)
                    team_data += String.pack(player.name or "")
                    packets.append((62, team_data))
                packets.append(self._build_spawn_player(player))
                head_yaw = player.head_yaw if player.head_yaw else player.rotation.yaw
                packets.append(
                    (25, VarInt.pack(player.entity_id) + Angle.pack(head_yaw))
                )
                if player.metadata:
                    meta_data = VarInt.pack(player.entity_id) + self._pack_metadata(
                        player.metadata
                    )
                    packets.append((28, meta_data))
                equip = player.equipment
                slots = [
                    (EquipmentSlot.Held.value, equip.held),
                    (EquipmentSlot.Boots.value, equip.boots),
                    (EquipmentSlot.Leggings.value, equip.leggings),
                    (EquipmentSlot.Chestplate.value, equip.chestplate),
                    (EquipmentSlot.Helmet.value, equip.helmet),
                ]
                for slot_id, item in slots:
                    if item.item:
                        equip_data = (
                            VarInt.pack(player.entity_id)
                            + Short.pack(slot_id)
                            + Slot.pack(item)
                        )
                        packets.append((4, equip_data))
        return packets

    def _build_npc_removal_packet(self) -> Packet:
        """Build a packet to remove NPCs from the tab list.

        Call this after a delay (e.g., 1-2 seconds) following a sync operation
        to remove NPCs from the tab list once the client has loaded their skins.
        """
        data = VarInt.pack(PlayerListAction.RemovePlayer.value)
        data += VarInt.pack(len(self._last_synced_npc_uuids))
        for uuid in self._last_synced_npc_uuids:
            data += self._pack_uuid(uuid)
        return (56, data)

    def _build_spawn_mob(self, entity: Entity) -> Packet:
        """Build Spawn Mob packet (0x0F)."""
        data = (
            VarInt.pack(entity.entity_id)
            + UnsignedByte.pack(entity.entity_type)
            + Int.pack(int(entity.position.x * 32))
            + Int.pack(int(entity.position.y * 32))
            + Int.pack(int(entity.position.z * 32))
            + Angle.pack(entity.rotation.yaw)
            + Angle.pack(entity.rotation.pitch)
            + Angle.pack(entity.head_yaw)
            + Short.pack(int(entity.velocity.x * 8000))
            + Short.pack(int(entity.velocity.y * 8000))
            + Short.pack(int(entity.velocity.z * 8000))
            + self._pack_metadata(entity.metadata)
        )
        return (15, data)

    def _build_spawn_object(self, entity: Entity) -> Packet:
        """Build Spawn Object packet (0x0E)."""
        data = (
            VarInt.pack(entity.entity_id)
            + Byte.pack(entity.entity_type)
            + Int.pack(int(entity.position.x * 32))
            + Int.pack(int(entity.position.y * 32))
            + Int.pack(int(entity.position.z * 32))
            + Angle.pack(entity.rotation.pitch)
            + Angle.pack(entity.rotation.yaw)
            + Int.pack(entity.object_data)
        )
        if entity.object_data != 0:
            data += (
                Short.pack(int(entity.velocity.x * 8000))
                + Short.pack(int(entity.velocity.y * 8000))
                + Short.pack(int(entity.velocity.z * 8000))
            )
        return (14, data)

    def _build_entity_metadata(self) -> list[Packet]:
        """Build Entity Metadata packets (0x1C) for all entities."""
        packets: list[Packet] = []
        for entity in self.entities.values():
            if entity.entity_id == self.player_entity_id:
                continue
            if entity.metadata:
                data = VarInt.pack(entity.entity_id) + self._pack_metadata(
                    entity.metadata
                )
                packets.append((28, data))
        return packets

    def _build_entity_equipment(self) -> list[Packet]:
        """Build Entity Equipment packets (0x04) for all entities."""
        packets: list[Packet] = []
        for entity in self.entities.values():
            if entity.entity_id == self.player_entity_id:
                continue
            equip = entity.equipment
            slots = [
                (EquipmentSlot.Held.value, equip.held),
                (EquipmentSlot.Boots.value, equip.boots),
                (EquipmentSlot.Leggings.value, equip.leggings),
                (EquipmentSlot.Chestplate.value, equip.chestplate),
                (EquipmentSlot.Helmet.value, equip.helmet),
            ]
            for slot_id, item in slots:
                if item.item:
                    data = (
                        VarInt.pack(entity.entity_id)
                        + Short.pack(slot_id)
                        + Slot.pack(item)
                    )
                    packets.append((4, data))
        return packets

    def _build_entity_effects(self) -> list[Packet]:
        """Build Entity Effect packets (0x1D) for all entities."""
        packets: list[Packet] = []
        for entity in self.entities.values():
            if entity.entity_id == self.player_entity_id:
                continue
            for effect in entity.effects.values():
                data = (
                    VarInt.pack(entity.entity_id)
                    + Byte.pack(effect.effect_id)
                    + Byte.pack(effect.amplifier)
                    + VarInt.pack(effect.duration)
                    + Boolean.pack(effect.hide_particles)
                )
                packets.append((29, data))
        return packets

    def _build_entity_properties(self) -> list[Packet]:
        """Build Entity Properties packets (0x20) for all entities."""
        packets: list[Packet] = []
        for entity in self.entities.values():
            if entity.entity_id == self.player_entity_id:
                continue
            if not entity.attributes:
                continue
            data = VarInt.pack(entity.entity_id)
            data += Int.pack(len(entity.attributes))
            for attr in entity.attributes.values():
                data += String.pack(attr.key)
                data += Double.pack(attr.value)
                data += VarInt.pack(len(attr.modifiers))
                for mod in attr.modifiers:
                    data += self._pack_uuid(mod.uuid)
                    data += Double.pack(mod.amount)
                    data += Byte.pack(mod.operation)
            packets.append((32, data))
        return packets

    def _build_player_inventory(self) -> Packet:
        """Build Window Items packet (0x30) for player inventory."""
        slots = self.player_inventory.slots
        max_slot = max(slots.keys()) if slots else 44
        data = UnsignedByte.pack(0)
        data += Short.pack(max_slot + 1)
        for i in range(max_slot + 1):
            slot_data = slots.get(i, SlotData())
            data += Slot.pack(slot_data)
        return (48, data)

    def _build_open_window(self) -> list[Packet]:
        """Build Open Window (0x2D) and Window Items (0x30) packets."""
        packets: list[Packet] = []
        if not self.open_window:
            return packets
        win = self.open_window
        data = (
            UnsignedByte.pack(win.window_id)
            + String.pack(win.window_type)
            + Chat.pack(win.title)
            + UnsignedByte.pack(win.slot_count)
        )
        if win.window_type == "EntityHorse" and win.entity_id is not None:
            data += Int.pack(win.entity_id)
        packets.append((45, data))
        slots = win.slots
        max_slot = max(slots.keys()) if slots else win.slot_count - 1
        items_data = UnsignedByte.pack(win.window_id)
        items_data += Short.pack(max_slot + 1)
        for i in range(max_slot + 1):
            slot_data = slots.get(i, SlotData())
            items_data += Slot.pack(slot_data)
        packets.append((48, items_data))
        for prop, value in win.properties.items():
            prop_data = (
                UnsignedByte.pack(win.window_id) + Short.pack(prop) + Short.pack(value)
            )
            packets.append((49, prop_data))
        return packets

    def _build_statistics(self) -> Packet:
        """Build Statistics packet (0x37)."""
        data = VarInt.pack(len(self.statistics.stats))
        for name, value in self.statistics.stats.items():
            data += String.pack(name) + VarInt.pack(value)
        return (55, data)

    def _build_title(self) -> list[Packet]:
        """Build Title packets (0x45)."""
        packets: list[Packet] = []
        times_data = (
            VarInt.pack(TitleAction.SetTimes.value)
            + Int.pack(self.title.fade_in)
            + Int.pack(self.title.stay)
            + Int.pack(self.title.fade_out)
        )
        packets.append((69, times_data))
        if self.title.subtitle:
            subtitle_data = VarInt.pack(TitleAction.SetSubtitle.value) + Chat.pack(
                self.title.subtitle
            )
            packets.append((69, subtitle_data))
        title_data = VarInt.pack(TitleAction.SetTitle.value) + Chat.pack(
            self.title.title
        )
        packets.append((69, title_data))
        return packets

    def _build_game_state_changes(self) -> list[Packet]:
        """Build Change Game State packets (0x2B) for weather."""
        packets: list[Packet] = []
        if self.is_raining:
            data = UnsignedByte.pack(GameStateReason.BeginRaining.value) + Float.pack(
                0.0
            )
            packets.append((43, data))
            if self.rain_strength > 0:
                data = UnsignedByte.pack(GameStateReason.FadeValue.value) + Float.pack(
                    self.rain_strength
                )
                packets.append((43, data))
        return packets

    def _build_maps(self) -> list[Packet]:
        """Build Map packets (0x34) for all maps."""
        packets: list[Packet] = []
        for map_data in self.maps.values():
            data = VarInt.pack(map_data.map_id)
            data += Byte.pack(map_data.scale)
            data += VarInt.pack(len(map_data.icons))
            for icon in map_data.icons:
                dir_type = (icon.get("direction", 0) & 15) << 4 | icon.get(
                    "type", 0
                ) & 15
                data += Byte.pack(dir_type)
                data += Byte.pack(icon.get("x", 0))
                data += Byte.pack(icon.get("z", 0))
            data += UnsignedByte.pack(128)
            data += UnsignedByte.pack(128)
            data += Byte.pack(0)
            data += Byte.pack(0)
            data += VarInt.pack(128 * 128)
            data += bytes(map_data.pixels)
            packets.append((52, data))
        return packets

    def _build_resource_pack(self) -> Packet:
        """Build Resource Pack Send packet (0x48)."""
        data = String.pack(self.resource_pack.url) + String.pack(
            self.resource_pack.hash
        )
        return (72, data)

    def _build_camera(self) -> Packet:
        """Build Camera packet (0x43)."""
        return (67, VarInt.pack(self.camera_entity_id or self.player_entity_id))

    def _build_block_break_animations(self) -> list[Packet]:
        """Build Block Break Animation packets (0x25)."""
        packets: list[Packet] = []
        for entity_id, (pos, stage) in self.block_break_animations.items():
            data = (
                VarInt.pack(entity_id)
                + Position.pack((pos.x, pos.y, pos.z))
                + Byte.pack(stage)
            )
            packets.append((37, data))
        return packets

    def _pack_uuid(self, uuid_str: str) -> bytes:
        """Pack a UUID string into bytes."""
        return UUID.pack(uuid_mod.UUID(uuid_str))

    def _pack_metadata(self, metadata: dict[int, MetadataValue | Any]) -> bytes:
        """Pack entity metadata into bytes, preserving original types."""
        data = b""
        for index, entry in metadata.items():
            if index < 0:
                continue
            if isinstance(entry, MetadataValue):
                type_id = entry.type_id
                value = entry.value
                if type_id < 0:
                    continue
                data += UnsignedByte.pack(type_id << 5 | index & 31)
                if type_id == 0:
                    data += Byte.pack(value)
                elif type_id == 1:
                    data += Short.pack(value)
                elif type_id == 2:
                    data += Int.pack(value)
                elif type_id == 3:
                    data += Float.pack(value)
                elif type_id == 4:
                    data += String.pack(value)
                elif type_id == 5:
                    data += Slot.pack(value)
                elif type_id == 6:
                    data += Int.pack(value.x) + Int.pack(value.y) + Int.pack(value.z)
                elif type_id == 7:
                    data += (
                        Float.pack(value[0])
                        + Float.pack(value[1])
                        + Float.pack(value[2])
                    )
            else:
                value = entry
                if isinstance(value, int):
                    if -128 <= value <= 127:
                        data += UnsignedByte.pack(0 << 5 | index & 31)
                        data += Byte.pack(value)
                    elif -32768 <= value <= 32767:
                        data += UnsignedByte.pack(1 << 5 | index & 31)
                        data += Short.pack(value)
                    else:
                        data += UnsignedByte.pack(2 << 5 | index & 31)
                        data += Int.pack(value)
                elif isinstance(value, float):
                    data += UnsignedByte.pack(3 << 5 | index & 31)
                    data += Float.pack(value)
                elif isinstance(value, str):
                    data += UnsignedByte.pack(4 << 5 | index & 31)
                    data += String.pack(value)
                elif isinstance(value, SlotData):
                    data += UnsignedByte.pack(5 << 5 | index & 31)
                    data += Slot.pack(value)
                elif isinstance(value, Vec3i):
                    data += UnsignedByte.pack(6 << 5 | index & 31)
                    data += Int.pack(value.x) + Int.pack(value.y) + Int.pack(value.z)
                elif isinstance(value, tuple) and len(value) == 3:
                    data += UnsignedByte.pack(7 << 5 | index & 31)
                    data += (
                        Float.pack(value[0])
                        + Float.pack(value[1])
                        + Float.pack(value[2])
                    )
        data += UnsignedByte.pack(127)
        return data

    def get_entity(self, entity_id: int) -> Entity | None:
        """Get an entity by its ID."""
        return self.entities.get(entity_id)

    def get_player_by_uuid(self, uuid: str) -> Player | None:
        """Get a player entity by UUID."""
        return self.players.get(uuid)

    def get_player_by_name_from_player_list(self, name: str) -> PlayerInfo | None:
        """Get a player list entry (tab list info) by player name."""
        for player in self.player_list.values():
            if player.name == name:
                return player
        return None

    def real_players(self) -> set[str]:
        """Return the set of real (non-NPC) player names currently in the tab list."""
        return {
            p.name
            for p in self.player_list.values()
            if uuid_version(p.uuid) not in (None, 2)
        }

    def get_held_item(self) -> SlotData | None:
        """Get the currently held item (hotbar slot corresponding to held_item_slot)."""
        return self.player_inventory.slots.get(36 + self.held_item_slot)

    def get_armor(self) -> list[SlotData | None]:
        """Get armor slots [helmet, chestplate, leggings, boots]."""
        return [
            self.player_inventory.slots.get(5),
            self.player_inventory.slots.get(6),
            self.player_inventory.slots.get(7),
            self.player_inventory.slots.get(8),
        ]

    @property
    def health(self) -> float:
        """Health including absorption hearts."""
        health = self.base_health
        player_entity = self.entities.get(self.player_entity_id)
        if player_entity and 17 in player_entity.metadata:
            health += player_entity.metadata[17].value
        return health

    def send_update(self) -> list[Packet]:
        """
        Generate a list of packets that would update a client's game state
        to exactly match the current stored state.

        Returns:
            A list of tuples (packet_id, packet_data) that can be sent to a client.
            These should be sent in order to properly synchronize the game state.

        Usage:
            packets = game_state.send_update()
            for packet_id, packet_data in packets:
                client.send_packet(packet_id, packet_data)
        """
        packets: list[Packet] = []
        packets.append(self._build_join_game())
        packets.append(self._build_server_difficulty())
        packets.append(self._build_player_abilities())
        packets.append(self._build_held_item_change())
        packets.append(self._build_spawn_position())
        packets.append(self._build_player_position_and_look())
        packets.append(self._build_update_health())
        packets.append(self._build_set_experience())
        packets.append(self._build_time_update())
        packets.append(self._build_world_border())
        packets.extend(self._build_player_list_items())
        if self.tab_header or self.tab_footer:
            packets.append(self._build_player_list_header_footer())
        packets.extend(self._build_scoreboard_objectives())
        packets.extend(self._build_scoreboard_scores())
        packets.extend(self._build_display_scoreboards())
        packets.extend(self._build_teams())
        packets.extend(self._build_chunk_data())
        packets.extend(self._build_block_entities())
        packets.extend(self._build_entity_spawns())
        packets.extend(self._build_entity_metadata())
        packets.extend(self._build_entity_equipment())
        packets.extend(self._build_entity_effects())
        packets.extend(self._build_entity_properties())
        packets.extend(self._build_npc_player_spawns())
        packets.append(self._build_player_inventory())
        if self.open_window:
            packets.extend(self._build_open_window())
        if self.statistics.stats:
            packets.append(self._build_statistics())
        if self.title.visible:
            packets.extend(self._build_title())
        packets.extend(self._build_game_state_changes())
        packets.extend(self._build_maps())
        if self.resource_pack.url:
            packets.append(self._build_resource_pack())
        if self.camera_entity_id and self.camera_entity_id != self.player_entity_id:
            packets.append(self._build_camera())
        packets.extend(self._build_block_break_animations())
        return packets

    def sync_spectator(self, eid: int | None = None) -> list[Packet]:
        """
        To use for broadcasting; generate a list of packets that would update a
        player's view to be a spectator of this game state.

        Some packets are commented out because I copy pasted this from send_update()

        Returns:
            A list of tuples (packet_id, packet_data) that can be sent to a client.
            These should be sent in order to properly synchronize the game state.

        Usage:
            packets = game_state.send_update()
            for packet_id, packet_data in packets:
                client.send_packet(packet_id, packet_data)
        """
        packets: list[Packet] = []
        packets.append(self._build_join_game(eid, 3))
        packets.append(self._build_server_difficulty())
        packets.append(self._build_player_position_and_look())
        packets.append(self._build_time_update())
        packets.append(self._build_world_border())
        packets.extend(self._build_player_list_items())
        if self.tab_header or self.tab_footer:
            packets.append(self._build_player_list_header_footer())
        packets.extend(self._build_scoreboard_objectives())
        packets.extend(self._build_scoreboard_scores())
        packets.extend(self._build_display_scoreboards())
        packets.extend(self._build_teams())
        packets.extend(self._build_chunk_data())
        packets.extend(self._build_block_entities())
        packets.extend(self._build_entity_spawns())
        packets.extend(self._build_entity_metadata())
        packets.extend(self._build_entity_equipment())
        packets.extend(self._build_entity_effects())
        packets.extend(self._build_entity_properties())
        packets.extend(self._build_npc_player_spawns())
        if self.title.visible:
            packets.extend(self._build_title())
        packets.extend(self._build_game_state_changes())
        packets.extend(self._build_maps())
        if self.resource_pack.url:
            packets.append(self._build_resource_pack())
        packets.extend(self._build_block_break_animations())
        return packets

    def sync_broadcast_spectator(self, eid: int) -> list[Packet]:
        """Build packets to sync a broadcast spectator client.

        Broadcast spectators should be presented to the client as being in
        ADVENTURE mode (so they cannot break blocks) but still be allowed to
        fly using vanilla behaviour (double-tap space to start/stop flying).
        This function builds a similar set of packets to `sync_spectator` but:

        - sets gamemode to ADVENTURE (2)
        - includes a Player Abilities packet (0x39) with INVULNERABLE and
          ALLOW_FLYING set, CREATIVE_MODE unset, and FLYING unset so the client
          uses the normal double-tap to start flying behaviour.
        """
        packets: list[Packet] = []
        packets.append(self._build_join_game(eid, 2))
        packets.append(self._build_server_difficulty())
        abilities = PlayerAbilityFlags.INVULNERABLE | PlayerAbilityFlags.ALLOW_FLYING
        packets.append(
            (
                57,
                Byte.pack(int(abilities))
                + Float.pack(self.flying_speed)
                + Float.pack(self.field_of_view_modifier),
            )
        )
        packets.append(self._build_player_position_and_look())
        packets.append(self._build_time_update())
        packets.append(self._build_world_border())
        packets.extend(self._build_player_list_items())
        if self.tab_header or self.tab_footer:
            packets.append(self._build_player_list_header_footer())
        packets.extend(self._build_scoreboard_objectives())
        packets.extend(self._build_scoreboard_scores())
        packets.extend(self._build_display_scoreboards())
        packets.extend(self._build_teams())
        packets.extend(self._build_chunk_data())
        packets.extend(self._build_block_entities())
        packets.extend(self._build_entity_spawns())
        packets.extend(self._build_entity_metadata())
        packets.extend(self._build_entity_equipment())
        packets.extend(self._build_entity_effects())
        packets.extend(self._build_entity_properties())
        packets.extend(self._build_npc_player_spawns())
        if self.title.visible:
            packets.extend(self._build_title())
        packets.extend(self._build_game_state_changes())
        packets.extend(self._build_maps())
        if self.resource_pack.url:
            packets.append(self._build_resource_pack())
        packets.extend(self._build_block_break_animations())
        return packets
