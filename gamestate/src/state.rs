use crate::enums::*;
use crate::types::*;
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3::types::{PyDict, PyList};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use std::collections::HashSet;

#[gen_stub_pyclass]
#[pyclass(name = "GameState")]
pub struct GameState {
    #[pyo3(get, set)]
    pub player_entity_id: i32,
    #[pyo3(get, set)]
    pub player_uuid: String,
    #[pyo3(get, set)]
    pub player_name: String,
    #[pyo3(get, set)]
    pub gamemode: Gamemode,
    #[pyo3(get, set)]
    pub is_hardcore: bool,
    #[pyo3(get, set)]
    pub dimension: Dimension,
    #[pyo3(get, set)]
    pub difficulty: Difficulty,
    #[pyo3(get, set)]
    pub max_players: u8,
    #[pyo3(get, set)]
    pub level_type: String,
    #[pyo3(get, set)]
    pub reduced_debug_info: bool,

    #[pyo3(get, set)]
    pub position: Py<Vec3d>,
    #[pyo3(get, set)]
    pub rotation: Py<Rotation>,
    #[pyo3(get, set)]
    pub on_ground: bool,

    #[pyo3(get, set)]
    pub base_health: f32,
    #[pyo3(get, set)]
    pub food: i32,
    #[pyo3(get, set)]
    pub food_saturation: f32,

    #[pyo3(get, set)]
    pub experience_bar: f32,
    #[pyo3(get, set)]
    pub experience_level: i32,
    #[pyo3(get, set)]
    pub total_experience: i32,

    #[pyo3(get, set)]
    pub abilities: PlayerAbilityFlags,
    #[pyo3(get, set)]
    pub flying_speed: f32,
    #[pyo3(get, set)]
    pub field_of_view_modifier: f32,

    #[pyo3(get, set)]
    pub held_item_slot: i16,
    #[pyo3(get, set)]
    pub player_flags: u8,

    #[pyo3(get, set)]
    pub spawn_position: Py<Vec3i>,

    #[pyo3(get, set)]
    pub world_age: i64,
    #[pyo3(get, set)]
    pub time_of_day: i64,
    #[pyo3(get, set)]
    pub is_raining: bool,
    #[pyo3(get, set)]
    pub rain_strength: f32,
    #[pyo3(get, set)]
    pub thunder_strength: f32,

    #[pyo3(get, set)]
    pub entities: Py<PyAny>, // dict[int, Entity]
    #[pyo3(get, set)]
    pub players: Py<PyAny>, // dict[str, Player]
    #[pyo3(get, set)]
    pub player_list: Py<PyAny>, // dict[str, PlayerInfo]

    // We will keep chunks in Rust memory for fast access, and expose a getter/setter if needed, or just let Rust handle it.
    // However, the python code accesses `self.chunks`. We need a Py<PyAny> for it, or wrap Chunk in #[pyclass].
    // Wait, Chunk and ChunkSection are not #[pyclass] in types.rs! They are just structs.
    // If python accesses them, they should be #[pyclass] or we provide methods.
    // Let's check `types.rs` ... Ah, I did not make `Chunk` a #[pyclass]. I'll fix that.
    #[pyo3(get, set)]
    pub chunks: Py<PyAny>, // dict[(int, int), Chunk]

    #[pyo3(get, set)]
    pub player_inventory: Py<Window>,
    #[pyo3(get, set)]
    pub open_window: Option<Py<Window>>,
    #[pyo3(get, set)]
    pub cursor_item: Option<Py<PyAny>>, // SlotData

    #[pyo3(get, set)]
    pub objectives: Py<PyAny>, // dict[str, ScoreboardObjective]
    #[pyo3(get, set)]
    pub scores: Py<PyAny>, // dict[str, dict[str, Score]]
    #[pyo3(get, set)]
    pub display_slots: Py<PyAny>, // dict[int, str]
    #[pyo3(get, set)]
    pub teams: Py<PyAny>, // dict[str, Team]

    #[pyo3(get, set)]
    pub maps: Py<PyAny>, // dict[int, MapData]
    #[pyo3(get, set)]
    pub block_entities: Py<PyAny>, // dict[(int, int, int), BlockEntity]

    #[pyo3(get, set)]
    pub world_border: Py<WorldBorder>,
    #[pyo3(get, set)]
    pub title: Py<TitleState>,

    #[pyo3(get, set)]
    pub tab_header: String,
    #[pyo3(get, set)]
    pub tab_footer: String,

    #[pyo3(get, set)]
    pub statistics: Py<Statistics>,
    #[pyo3(get, set)]
    pub resource_pack: Py<ResourcePack>,
    #[pyo3(get, set)]
    pub plugin_channels: Py<PluginChannel>,

    #[pyo3(get, set)]
    pub villager_trades: Py<PyAny>, // list[VillagerTrade]

    #[pyo3(get, set)]
    pub compression_threshold: i32,
    #[pyo3(get, set)]
    pub block_break_animations: Py<PyAny>, // dict[int, tuple[Vec3i, int]]

    #[pyo3(get, set)]
    pub camera_entity_id: Option<i32>,
    #[pyo3(get, set)]
    pub _last_synced_npc_uuids: Vec<String>,
}

impl GameState {
    pub fn init_default(py: Python<'_>) -> PyResult<Self> {
        let player_inventory = Py::new(
            py,
            Window {
                window_id: 0,
                window_type: "minecraft:player".to_string(),
                title: "Inventory".to_string(),
                slot_count: 45,
                slots: PyDict::new(py).into(),
                entity_id: None,
                properties: PyDict::new(py).into(),
            },
        )?;

        Ok(Self {
            player_entity_id: 0,
            player_uuid: String::new(),
            player_name: String::new(),
            gamemode: Gamemode::Survival,
            is_hardcore: false,
            dimension: Dimension::Overworld,
            difficulty: Difficulty::Normal,
            max_players: 20,
            level_type: "default".to_string(),
            reduced_debug_info: false,
            position: Py::new(py, Vec3d::default())?,
            rotation: Py::new(py, Rotation::default())?,
            on_ground: false,
            base_health: 20.0,
            food: 20,
            food_saturation: 5.0,
            experience_bar: 0.0,
            experience_level: 0,
            total_experience: 0,
            abilities: PlayerAbilityFlags(0),
            flying_speed: 0.05,
            field_of_view_modifier: 0.1,
            held_item_slot: 0,
            player_flags: 0,
            spawn_position: Py::new(py, Vec3i::default())?,
            world_age: 0,
            time_of_day: 0,
            is_raining: false,
            rain_strength: 0.0,
            thunder_strength: 0.0,
            entities: PyDict::new(py).into(),
            players: PyDict::new(py).into(),
            player_list: PyDict::new(py).into(),
            chunks: PyDict::new(py).into(),
            player_inventory,
            open_window: None,
            cursor_item: None,
            objectives: PyDict::new(py).into(),
            scores: PyDict::new(py).into(),
            display_slots: PyDict::new(py).into(),
            teams: PyDict::new(py).into(),
            maps: PyDict::new(py).into(),
            block_entities: PyDict::new(py).into(),
            world_border: Py::new(
                py,
                WorldBorder {
                    center_x: 0.0,
                    center_z: 0.0,
                    old_radius: 60000000.0,
                    new_radius: 60000000.0,
                    speed: 0,
                    portal_boundary: 29999984,
                    warning_time: 15,
                    warning_blocks: 5,
                },
            )?,
            title: Py::new(
                py,
                TitleState {
                    title: String::new(),
                    subtitle: String::new(),
                    fade_in: 10,
                    stay: 70,
                    fade_out: 20,
                    visible: false,
                },
            )?,
            tab_header: String::new(),
            tab_footer: String::new(),
            statistics: Py::new(
                py,
                Statistics {
                    stats: PyDict::new(py).into(),
                },
            )?,
            resource_pack: Py::new(
                py,
                ResourcePack {
                    url: String::new(),
                    hash: String::new(),
                    status: 0,
                },
            )?,
            plugin_channels: Py::new(
                py,
                PluginChannel {
                    registered: HashSet::new(),
                },
            )?,
            villager_trades: PyList::empty(py).into(),
            compression_threshold: -1,
            block_break_animations: PyDict::new(py).into(),
            camera_entity_id: None,
            _last_synced_npc_uuids: Vec::new(),
        })
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl GameState {
    #[new]
    pub fn new(py: Python<'_>) -> PyResult<Self> {
        Self::init_default(py)
    }

    pub fn reset(&mut self, py: Python<'_>) -> PyResult<()> {
        let default = Self::init_default(py)?;
        *self = default;
        Ok(())
    }

    pub fn update_clientbound(
        &mut self,
        py: Python<'_>,
        packet_id: i32,
        packet_data: PyBackedBytes,
    ) -> PyResult<()> {
        // Delegate to the actual implementation in packet_handlers.rs
        self.handle_clientbound(py, packet_id, &packet_data)
    }

    pub fn update_serverbound(
        &mut self,
        py: Python<'_>,
        packet_id: i32,
        packet_data: PyBackedBytes,
    ) -> PyResult<()> {
        // Delegate to the actual implementation in packet_handlers.rs
        self.handle_serverbound(py, packet_id, &packet_data)
    }
}
