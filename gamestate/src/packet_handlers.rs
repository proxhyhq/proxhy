use crate::enums::*;
use crate::reader::PacketReader;
use crate::state::GameState;
use pyo3::prelude::*;
use pyo3::types::PyDict;

impl GameState {
    pub fn handle_clientbound(
        &mut self,
        py: Python<'_>,
        packet_id: i32,
        packet_data: &[u8],
    ) -> PyResult<()> {
        let mut reader = PacketReader::new(packet_data);
        match packet_id {
            0x00 => {
                // Keep Alive
                let _ = reader.read_varint();
            }
            0x01 => {
                // Join Game
                self.player_entity_id = reader.read_int();
                let gamemode_byte = reader.read_ubyte();
                self.is_hardcore = (gamemode_byte & 0x08) != 0;
                self.gamemode =
                    Gamemode::try_from(gamemode_byte & 0x07).unwrap_or(Gamemode::Survival);
                self.dimension =
                    Dimension::try_from(reader.read_byte()).unwrap_or(Dimension::Overworld);
                self.difficulty =
                    Difficulty::try_from(reader.read_ubyte()).unwrap_or(Difficulty::Normal);
                self.max_players = reader.read_ubyte();
                self.level_type = reader.read_string();
                self.reduced_debug_info = reader.read_bool();

                self.chunks.bind(py).cast::<PyDict>()?.clear();
                self.entities.bind(py).cast::<PyDict>()?.clear();
                self.players.bind(py).cast::<PyDict>()?.clear();
            }
            0x02 => {
                // Chat Message
                let _ = reader.read_string();
                let _ = reader.read_byte();
            }
            0x03 => {
                // Time Update
                self.world_age = reader.read_long();
                self.time_of_day = reader.read_long();
            }
            0x04 => {
                // Entity Equipment
                let _entity_id = reader.read_varint();
                let _slot = reader.read_short();
                let _start = reader.pos();
                let item_id = reader.read_short();
                if item_id != -1 {
                    let _count = reader.read_byte();
                    let _damage = reader.read_short();
                    // Just scan past NBT... wait, I need to parse the slot here.
                    // Instead of scanning, let's call the FFI py_slot_unpack if we need a Py<PyAny> SlotData.
                }
                // But wait, the Equipment in Entity needs a Py<PyAny> slot.
                // We'll leave equipment parsing for a follow-up once we wire up the petty FFI or just call petty._petty.py_slot_unpack.
            }
            0x05 => {
                // Spawn Position
                let pos = reader.read_position();
                self.spawn_position = Py::new(py, pos)?;
            }
            0x06 => {
                // Update Health
                self.base_health = reader.read_float();
                self.food = reader.read_varint();
                self.food_saturation = reader.read_float();
            }
            0x07 => {
                // Respawn
                self.dimension =
                    Dimension::try_from(reader.read_int()).unwrap_or(Dimension::Overworld);
                self.difficulty =
                    Difficulty::try_from(reader.read_ubyte()).unwrap_or(Difficulty::Normal);
                let gamemode_byte = reader.read_ubyte();
                self.gamemode =
                    Gamemode::try_from(gamemode_byte & 0x07).unwrap_or(Gamemode::Survival);
                self.level_type = reader.read_string();

                self.chunks.bind(py).cast::<PyDict>()?.clear();
                self.entities.bind(py).cast::<PyDict>()?.clear();
            }
            0x08 => {
                // Player Position And Look
                let x = reader.read_double();
                let y = reader.read_double();
                let z = reader.read_double();
                let yaw = reader.read_float();
                let pitch = reader.read_float();
                let flags = reader.read_byte();

                let mut pos = self.position.borrow_mut(py);
                if (flags & 0x01) != 0 {
                    pos.x += x;
                } else {
                    pos.x = x;
                }
                if (flags & 0x02) != 0 {
                    pos.y += y;
                } else {
                    pos.y = y;
                }
                if (flags & 0x04) != 0 {
                    pos.z += z;
                } else {
                    pos.z = z;
                }

                let mut rot = self.rotation.borrow_mut(py);
                if (flags & 0x08) != 0 {
                    rot.yaw += yaw;
                } else {
                    rot.yaw = yaw;
                }
                if (flags & 0x10) != 0 {
                    rot.pitch += pitch;
                } else {
                    rot.pitch = pitch;
                }
            }
            0x09 => {
                // Held Item Change
                self.held_item_slot = reader.read_byte() as i16;
            }
            0x0A => {
                // Use Bed
                let _entity_id = reader.read_varint();
                let _pos = reader.read_position();
                // TODO: Update entity position if needed
            }
            0x0B => {
                // Animation
                let _ = reader.read_varint();
                let _ = reader.read_ubyte();
            }
            0x0C => {
                // Spawn Player
                let _entity_id = reader.read_varint();
                let _uuid_high = reader.read_long();
                let _uuid_low = reader.read_long();
                let _x = reader.read_int() as f64 / 32.0;
                let _y = reader.read_int() as f64 / 32.0;
                let _z = reader.read_int() as f64 / 32.0;
                let _yaw = reader.read_ubyte() as f32; // angle
                let _pitch = reader.read_ubyte() as f32; // angle
                let _current_item = reader.read_short();
                let _metadata = reader.parse_metadata();
                // TODO: Insert into entities map
            }
            0x0D => {
                // Collect Item
                let _ = reader.read_varint();
                let _ = reader.read_varint();
            }
            0x0E => {
                // Spawn Object
                let _entity_id = reader.read_varint();
                let _entity_type = reader.read_byte();
                let _x = reader.read_int() as f64 / 32.0;
                let _y = reader.read_int() as f64 / 32.0;
                let _z = reader.read_int() as f64 / 32.0;
                let _pitch = reader.read_ubyte() as f32;
                let _yaw = reader.read_ubyte() as f32;
                let data = reader.read_int();
                if data != 0 {
                    let _vx = reader.read_short() as f64 / 8000.0;
                    let _vy = reader.read_short() as f64 / 8000.0;
                    let _vz = reader.read_short() as f64 / 8000.0;
                }
            }
            0x0F => {
                // Spawn Mob
                let _entity_id = reader.read_varint();
                let _entity_type = reader.read_ubyte();
                let _x = reader.read_int() as f64 / 32.0;
                let _y = reader.read_int() as f64 / 32.0;
                let _z = reader.read_int() as f64 / 32.0;
                let _yaw = reader.read_ubyte() as f32;
                let _pitch = reader.read_ubyte() as f32;
                let _head_pitch = reader.read_ubyte() as f32;
                let _vx = reader.read_short() as f64 / 8000.0;
                let _vy = reader.read_short() as f64 / 8000.0;
                let _vz = reader.read_short() as f64 / 8000.0;
                let _metadata = reader.parse_metadata();
            }
            0x10 => {
                // Spawn Painting
                let _entity_id = reader.read_varint();
                let _title = reader.read_string();
                let _pos = reader.read_position();
                let _direction = reader.read_ubyte();
            }
            0x11 => {
                // Spawn Experience Orb
                let _entity_id = reader.read_varint();
                let _x = reader.read_int() as f64 / 32.0;
                let _y = reader.read_int() as f64 / 32.0;
                let _z = reader.read_int() as f64 / 32.0;
                let _count = reader.read_short();
            }
            0x12 => {
                // Entity Velocity
                let _entity_id = reader.read_varint();
                let _vx = reader.read_short() as f64 / 8000.0;
                let _vy = reader.read_short() as f64 / 8000.0;
                let _vz = reader.read_short() as f64 / 8000.0;
            }
            0x13 => {
                // Destroy Entities
                let count = reader.read_varint();
                let entities_dict = self.entities.bind(py).cast::<PyDict>()?;
                for _ in 0..count {
                    let entity_id = reader.read_varint();
                    let _ = entities_dict.del_item(entity_id);
                }
            }
            0x14 => {
                // Entity
                let _entity_id = reader.read_varint();
            }
            0x15 => {
                // Entity Relative Move
                let _entity_id = reader.read_varint();
                let _dx = reader.read_byte() as f64 / 32.0;
                let _dy = reader.read_byte() as f64 / 32.0;
                let _dz = reader.read_byte() as f64 / 32.0;
                let _on_ground = reader.read_bool();
            }
            0x16 => {
                // Entity Look
                let _entity_id = reader.read_varint();
                let _yaw = reader.read_ubyte() as f32;
                let _pitch = reader.read_ubyte() as f32;
                let _on_ground = reader.read_bool();
            }
            0x17 => {
                // Entity Look And Relative Move
                let _entity_id = reader.read_varint();
                let _dx = reader.read_byte() as f64 / 32.0;
                let _dy = reader.read_byte() as f64 / 32.0;
                let _dz = reader.read_byte() as f64 / 32.0;
                let _yaw = reader.read_ubyte() as f32;
                let _pitch = reader.read_ubyte() as f32;
                let _on_ground = reader.read_bool();
            }
            0x18 => {
                // Entity Teleport
                let _entity_id = reader.read_varint();
                let _x = reader.read_int() as f64 / 32.0;
                let _y = reader.read_int() as f64 / 32.0;
                let _z = reader.read_int() as f64 / 32.0;
                let _yaw = reader.read_ubyte() as f32;
                let _pitch = reader.read_ubyte() as f32;
                let _on_ground = reader.read_bool();
            }
            0x19 => {
                // Entity Head Look
                let _entity_id = reader.read_varint();
                let _head_yaw = reader.read_ubyte() as f32;
            }
            0x1A => {
                // Entity Status
                let _entity_id = reader.read_int();
                let status = reader.read_byte();
                if status == 22 {
                    self.reduced_debug_info = true;
                } else if status == 23 {
                    self.reduced_debug_info = false;
                }
            }
            0x1B => {
                // Attach Entity
                let _entity_id = reader.read_int();
                let _vehicle_id = reader.read_int();
                let _ = reader.read_bool();
            }
            0x1C => {
                // Entity Metadata
                let _entity_id = reader.read_varint();
                let _metadata = reader.parse_metadata();
            }
            0x1D => {
                // Entity Effect
                let _entity_id = reader.read_varint();
                let _effect_id = reader.read_byte();
                let _amplifier = reader.read_byte();
                let _duration = reader.read_varint();
                let _hide_particles = reader.read_bool();
            }
            0x1E => {
                // Remove Entity Effect
                let _entity_id = reader.read_varint();
                let _effect_id = reader.read_byte();
            }
            0x1F => {
                // Set Experience
                self.experience_bar = reader.read_float();
                self.experience_level = reader.read_varint();
                self.total_experience = reader.read_varint();
            }
            0x20 => {
                // Entity Properties
                let _entity_id = reader.read_varint();
                let num_properties = reader.read_int();
                for _ in 0..num_properties {
                    let _key = reader.read_string();
                    let _value = reader.read_double();
                    let num_modifiers = reader.read_varint();
                    for _ in 0..num_modifiers {
                        let _uuid_hi = reader.read_long();
                        let _uuid_lo = reader.read_long();
                        let _amount = reader.read_double();
                        let _operation = reader.read_byte();
                    }
                }
            }
            0x21 => {
                // Chunk Data
                let _chunk_x = reader.read_int();
                let _chunk_z = reader.read_int();
                let _ground_up_continuous = reader.read_bool();
                let _primary_bitmask = reader.read_ushort();
                let size = reader.read_varint();
                let _data = reader.read_bytes(size as usize);
            }
            0x22 => {
                // Multi Block Change
                let _chunk_x = reader.read_int();
                let _chunk_z = reader.read_int();
                let record_count = reader.read_varint();
                for _ in 0..record_count {
                    let _horizontal_pos = reader.read_ubyte();
                    let _y = reader.read_ubyte();
                    let _block_id = reader.read_varint();
                }
            }
            0x23 => {
                // Block Change
                let _pos = reader.read_position();
                let _block_id = reader.read_varint();
            }
            0x24 => {
                // Block Action
                let _pos = reader.read_position();
                let _ = reader.read_ubyte();
                let _ = reader.read_ubyte();
                let _ = reader.read_varint();
            }
            0x25 => {
                // Block Break Animation
                let _entity_id = reader.read_varint();
                let _pos = reader.read_position();
                let _destroy_stage = reader.read_byte();
            }
            0x26 => {
                // Map Chunk Bulk
                let _sky_light_sent = reader.read_bool();
                let chunk_count = reader.read_varint();
                for _ in 0..chunk_count {
                    let _chunk_x = reader.read_int();
                    let _chunk_z = reader.read_int();
                    let _primary_bitmask = reader.read_ushort();
                }
                // Then read actual chunk data
                // For now, we skip reading because sizes are not clearly delimited here without bitmasks.
                // Wait, if we don't skip the right bytes, the rest of the stream is corrupted.
                // We'll need to accurately read sizes or skip based on primary_bitmask!
                // We will implement this later.
            }
            0x27 => {
                // Explosion
                let _x = reader.read_float();
                let _y = reader.read_float();
                let _z = reader.read_float();
                let _ = reader.read_float();
                let record_count = reader.read_int();
                for _ in 0..record_count {
                    let _bx = reader.read_byte();
                    let _by = reader.read_byte();
                    let _bz = reader.read_byte();
                }
                let pmx = reader.read_float();
                let pmy = reader.read_float();
                let pmz = reader.read_float();
                let mut pos = self.position.borrow_mut(py);
                pos.x += pmx as f64;
                pos.y += pmy as f64;
                pos.z += pmz as f64;
            }
            0x28 => {
                // Effect
                let _ = reader.read_int();
                let _ = reader.read_position();
                let _ = reader.read_int();
                let _ = reader.read_bool();
            }
            0x29 => {
                // Sound Effect
                let _ = reader.read_string();
                let _ = reader.read_int();
                let _ = reader.read_int();
                let _ = reader.read_int();
                let _ = reader.read_float();
                let _ = reader.read_ubyte();
            }
            0x2A => {
                // Particle
                let particle_id = reader.read_int();
                let _ = reader.read_bool();
                let _ = reader.read_float();
                let _ = reader.read_float();
                let _ = reader.read_float();
                let _ = reader.read_float();
                let _ = reader.read_float();
                let _ = reader.read_float();
                let _ = reader.read_float();
                let _ = reader.read_int();
                if particle_id == 36 {
                    let _ = reader.read_varint();
                    let _ = reader.read_varint();
                } else if particle_id == 37 || particle_id == 38 {
                    let _ = reader.read_varint();
                }
            }
            0x2B => {
                // Change Game State
                let reason = reader.read_ubyte();
                let value = reader.read_float();
                if reason == 1 {
                    self.is_raining = false;
                } else if reason == 2 {
                    self.is_raining = true;
                } else if reason == 3 {
                    self.gamemode = Gamemode::try_from(value as u8).unwrap_or(Gamemode::Survival);
                } else if reason == 7 {
                    self.rain_strength = value;
                } else if reason == 8 {
                    self.thunder_strength = value;
                }
            }
            0x2C => {
                // Spawn Global Entity
                let _entity_id = reader.read_varint();
                let _entity_type = reader.read_byte();
                let _x = reader.read_int() as f64 / 32.0;
                let _y = reader.read_int() as f64 / 32.0;
                let _z = reader.read_int() as f64 / 32.0;
            }
            0x2D => {
                // Open Window
                let _window_id = reader.read_ubyte();
                let window_type = reader.read_string();
                let _title = reader.read_string();
                let _slot_count = reader.read_ubyte();
                if window_type == "EntityHorse" {
                    let _entity_id = reader.read_int();
                }
            }
            0x2E => {
                // Close Window
                let _window_id = reader.read_ubyte();
            }
            0x2F => {
                // Set Slot
                let _window_id = reader.read_byte();
                let _slot = reader.read_short();
                let item_id = reader.read_short();
                if item_id != -1 {
                    let _count = reader.read_byte();
                    let _damage = reader.read_short();
                    let _nbt = reader.scan_nbt_bytes();
                }
            }
            0x30 => {
                // Window Items
                let _window_id = reader.read_ubyte();
                let count = reader.read_short();
                for _ in 0..count {
                    let item_id = reader.read_short();
                    if item_id != -1 {
                        let _count = reader.read_byte();
                        let _damage = reader.read_short();
                        let _nbt = reader.scan_nbt_bytes();
                    }
                }
            }
            0x31 => {
                // Window Property
                let _window_id = reader.read_ubyte();
                let _property = reader.read_short();
                let _value = reader.read_short();
            }
            0x32 => {
                // Confirm Transaction
                let _window_id = reader.read_ubyte();
                let _action_number = reader.read_short();
                let _accepted = reader.read_bool();
            }
            0x33 => {
                // Update Sign
                let _pos = reader.read_position();
                let _line1 = reader.read_string();
                let _line2 = reader.read_string();
                let _line3 = reader.read_string();
                let _line4 = reader.read_string();
            }
            0x34 => {
                // Maps
                let _map_id = reader.read_varint();
                let _scale = reader.read_byte();
                let count = reader.read_varint();
                for _ in 0..count {
                    let _dir_type = reader.read_byte();
                    let _x = reader.read_byte();
                    let _z = reader.read_byte();
                }
                let columns = reader.read_byte();
                if columns > 0 {
                    let _rows = reader.read_byte();
                    let _x = reader.read_byte();
                    let _z = reader.read_byte();
                    let length = reader.read_varint();
                    let _data = reader.read_bytes(length as usize);
                }
            }
            0x35 => {
                // Update Block Entity
                let _pos = reader.read_position();
                let _action = reader.read_ubyte();
                // The rest of the payload is NBT
            }
            0x36 => {
                // Sign Editor Open
                let _pos = reader.read_position();
            }
            0x37 => {
                // Statistics
                let count = reader.read_varint();
                for _ in 0..count {
                    let _name = reader.read_string();
                    let _value = reader.read_varint();
                }
            }
            0x38 => {
                // Player List Item
                let action = reader.read_varint();
                let num_players = reader.read_varint();
                for _ in 0..num_players {
                    let _uuid_hi = reader.read_long();
                    let _uuid_lo = reader.read_long();
                    if action == 0 {
                        // ADD_PLAYER
                        let _name = reader.read_string();
                        let num_props = reader.read_varint();
                        for _ in 0..num_props {
                            let _prop_name = reader.read_string();
                            let _prop_value = reader.read_string();
                            let is_signed = reader.read_bool();
                            if is_signed {
                                let _signature = reader.read_string();
                            }
                        }
                        let _gamemode = reader.read_varint();
                        let _ping = reader.read_varint();
                        let has_display_name = reader.read_bool();
                        if has_display_name {
                            let _display_name = reader.read_string();
                        }
                    } else if action == 1 {
                        // UPDATE_GAMEMODE
                        let _gamemode = reader.read_varint();
                    } else if action == 2 {
                        // UPDATE_LATENCY
                        let _ping = reader.read_varint();
                    } else if action == 3 {
                        // UPDATE_DISPLAY_NAME
                        let has_display_name = reader.read_bool();
                        if has_display_name {
                            let _display_name = reader.read_string();
                        }
                    } else if action == 4 { // REMOVE_PLAYER
                    }
                }
            }
            0x39 => {
                // Player Abilities
                let _flags = reader.read_byte();
                self.flying_speed = reader.read_float();
                self.field_of_view_modifier = reader.read_float();
            }
            0x3A => {
                // Tab-Complete
                let count = reader.read_varint();
                for _ in 0..count {
                    let _match_str = reader.read_string();
                }
            }
            0x3B => {
                // Scoreboard Objective
                let _objective_name = reader.read_string();
                let mode = reader.read_byte();
                if mode != 1 {
                    let _display_text = reader.read_string();
                    let _objective_type = reader.read_string();
                }
            }
            0x3C => {
                // Update Score
                let _score_name = reader.read_string();
                let action = reader.read_byte();
                let _objective_name = reader.read_string();
                if action != 1 {
                    let _value = reader.read_varint();
                }
            }
            0x3D => {
                // Display Scoreboard
                let _position = reader.read_byte();
                let _score_name = reader.read_string();
            }
            0x3E => {
                // Teams
                let _team_name = reader.read_string();
                let mode = reader.read_byte();
                if mode == 0 || mode == 2 {
                    let _display_name = reader.read_string();
                    let _prefix = reader.read_string();
                    let _suffix = reader.read_string();
                    let _friendly_fire = reader.read_byte();
                    let _name_tag_visibility = reader.read_string();
                    let _color = reader.read_byte();
                }
                if mode == 0 || mode == 3 || mode == 4 {
                    let count = reader.read_varint();
                    for _ in 0..count {
                        let _member = reader.read_string();
                    }
                }
            }
            0x3F => {
                // Plugin Message
                let _channel = reader.read_string();
            }
            0x40 => {
                // Disconnect
                let _reason = reader.read_string();
            }
            0x41 => {
                // Server Difficulty
                let difficulty_val = reader.read_ubyte();
                self.difficulty =
                    Difficulty::try_from(difficulty_val).unwrap_or(Difficulty::Normal);
            }
            0x42 => {
                // Combat Event
                let event_id = reader.read_varint();
                if event_id == 1 {
                    // End Combat
                    let _duration = reader.read_varint();
                    let _entity_id = reader.read_int();
                } else if event_id == 2 {
                    // Entity Dead
                    let _player_id = reader.read_varint();
                    let _entity_id = reader.read_int();
                    let _message = reader.read_string();
                }
            }
            0x43 => {
                // Camera
                self.camera_entity_id = Some(reader.read_varint());
            }
            0x44 => {
                // World Border
                let action = reader.read_varint();
                if action == 0 {
                    // Set Size
                    let _diameter = reader.read_double();
                } else if action == 1 {
                    // Lerp Size
                    let _old_diameter = reader.read_double();
                    let _new_diameter = reader.read_double();
                    let _speed = reader.read_varlong();
                } else if action == 2 {
                    // Set Center
                    let _x = reader.read_double();
                    let _z = reader.read_double();
                } else if action == 3 {
                    // Initialize
                    let _x = reader.read_double();
                    let _z = reader.read_double();
                    let _old_diameter = reader.read_double();
                    let _new_diameter = reader.read_double();
                    let _speed = reader.read_varlong();
                    let _portal_teleport_boundary = reader.read_varint();
                    let _warning_time = reader.read_varint();
                    let _warning_blocks = reader.read_varint();
                } else if action == 4 {
                    // Set Warning Time
                    let _warning_time = reader.read_varint();
                } else if action == 5 {
                    // Set Warning Blocks
                    let _warning_blocks = reader.read_varint();
                }
            }
            0x45 => {
                // Title
                let action = reader.read_varint();
                if action == 0 || action == 1 || action == 2 {
                    let _text = reader.read_string();
                } else if action == 3 {
                    let _fade_in = reader.read_int();
                    let _stay = reader.read_int();
                    let _fade_out = reader.read_int();
                }
            }
            0x46 => {
                // Set Compression
                self.compression_threshold = reader.read_varint();
            }
            0x47 => {
                // Player List Header And Footer
                self.tab_header = reader.read_string();
                self.tab_footer = reader.read_string();
            }
            0x48 => {
                // Resource Pack Send
                let _url = reader.read_string();
                let _hash = reader.read_string();
            }
            0x49 => {
                // Update Entity NBT
                let _entity_id = reader.read_varint();
                let _nbt = reader.scan_nbt_bytes();
            }
            _ => {}
        }
        Ok(())
    }

    pub fn handle_serverbound(
        &mut self,
        py: Python<'_>,
        packet_id: i32,
        packet_data: &[u8],
    ) -> PyResult<()> {
        let mut reader = PacketReader::new(packet_data);
        match packet_id {
            0x03 => {
                // Player
                self.on_ground = reader.read_bool();
            }
            0x04 => {
                // Player Position
                let mut pos = self.position.borrow_mut(py);
                pos.x = reader.read_double();
                pos.y = reader.read_double();
                pos.z = reader.read_double();
                self.on_ground = reader.read_bool();
            }
            0x05 => {
                // Player Look
                let mut rot = self.rotation.borrow_mut(py);
                rot.yaw = reader.read_float();
                rot.pitch = reader.read_float();
                self.on_ground = reader.read_bool();
            }
            0x06 => {
                // Player Position And Look
                let mut pos = self.position.borrow_mut(py);
                pos.x = reader.read_double();
                pos.y = reader.read_double();
                pos.z = reader.read_double();
                let mut rot = self.rotation.borrow_mut(py);
                rot.yaw = reader.read_float();
                rot.pitch = reader.read_float();
                self.on_ground = reader.read_bool();
            }
            0x09 => {
                // Held Item Change
                self.held_item_slot = reader.read_short();
            }
            0x0B => {
                // Entity Action
                let _entity_id = reader.read_varint();
                let action_id = reader.read_varint();
                let _jump_boost = reader.read_varint();

                if action_id == 0 {
                    // Start sneaking
                    self.player_flags |= entity_flag::CROUCHED;
                } else if action_id == 1 {
                    // Stop sneaking
                    self.player_flags &= !entity_flag::CROUCHED;
                } else if action_id == 3 {
                    // Start sprinting
                    self.player_flags |= entity_flag::SPRINTING;
                } else if action_id == 4 {
                    // Stop sprinting
                    self.player_flags &= !entity_flag::SPRINTING;
                }
            }
            _ => {}
        }
        Ok(())
    }
}
