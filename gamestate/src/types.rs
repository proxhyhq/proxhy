// pyo3-stub-gen (as of 0.23) doesn't implement PyStubType for PyClassInitializer<T>,
// so Player::__new__ below still uses the tuple-return subclass-init style pyo3 has
// deprecated in favor of PyClassInitializer. The deprecated call site is inside pyo3's
// own macro expansion, which a function- or impl-scoped #[allow(deprecated)] doesn't
// reach, hence the module-level allow.
#![allow(deprecated)]
//! All data model types from gamestate/models.py, ported to Rust #[pyclass].
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

// ─────────────────────────────────────────────────────────────────────────────
// Vec3d / Vec3i / Rotation
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Vec3d", from_py_object)]
#[derive(Debug, Clone, Default)]
pub struct Vec3d {
    #[pyo3(get, set)]
    pub x: f64,
    #[pyo3(get, set)]
    pub y: f64,
    #[pyo3(get, set)]
    pub z: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl Vec3d {
    #[new]
    #[pyo3(signature = (x=0.0, y=0.0, z=0.0))]
    pub fn __new__(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }

    fn __sub__(&self, other: &Self) -> Self {
        Self {
            x: self.x - other.x,
            y: self.y - other.y,
            z: self.z - other.z,
        }
    }
    fn __add__(&self, other: &Self) -> Self {
        Self {
            x: self.x + other.x,
            y: self.y + other.y,
            z: self.z + other.z,
        }
    }
    fn __mul__(&self, scalar: f64) -> Self {
        Self {
            x: self.x * scalar,
            y: self.y * scalar,
            z: self.z * scalar,
        }
    }
    fn __truediv__(&self, scalar: f64) -> Self {
        Self {
            x: self.x / scalar,
            y: self.y / scalar,
            z: self.z / scalar,
        }
    }
    fn __floordiv__(&self, scalar: f64) -> Self {
        Self {
            x: (self.x / scalar).floor(),
            y: (self.y / scalar).floor(),
            z: (self.z / scalar).floor(),
        }
    }
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        match other.extract::<PyRef<'_, Self>>() {
            Ok(other) => self.x == other.x && self.y == other.y && self.z == other.z,
            Err(_) => false,
        }
    }
    fn __ne__(&self, other: &Bound<'_, PyAny>) -> bool {
        !self.__eq__(other)
    }
    fn __repr__(&self) -> String {
        format!("Vec3d({}, {}, {})", self.x, self.y, self.z)
    }
    fn copy(&self) -> Self {
        self.clone()
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "Vec3i", from_py_object)]
#[derive(Debug, Clone, Default)]
pub struct Vec3i {
    #[pyo3(get, set)]
    pub x: i64,
    #[pyo3(get, set)]
    pub y: i64,
    #[pyo3(get, set)]
    pub z: i64,
}

#[gen_stub_pymethods]
#[pymethods]
impl Vec3i {
    #[new]
    #[pyo3(signature = (x=0, y=0, z=0))]
    pub fn __new__(x: i64, y: i64, z: i64) -> Self {
        Self { x, y, z }
    }

    fn __sub__(&self, other: &Self) -> Self {
        Self {
            x: self.x - other.x,
            y: self.y - other.y,
            z: self.z - other.z,
        }
    }
    fn __add__(&self, other: &Self) -> Self {
        Self {
            x: self.x + other.x,
            y: self.y + other.y,
            z: self.z + other.z,
        }
    }
    fn __mul__(&self, scalar: i64) -> Self {
        Self {
            x: self.x * scalar,
            y: self.y * scalar,
            z: self.z * scalar,
        }
    }
    fn __floordiv__(&self, scalar: i64) -> Self {
        Self {
            x: self.x / scalar,
            y: self.y / scalar,
            z: self.z / scalar,
        }
    }
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        match other.extract::<PyRef<'_, Self>>() {
            Ok(other) => self.x == other.x && self.y == other.y && self.z == other.z,
            Err(_) => false,
        }
    }
    fn __ne__(&self, other: &Bound<'_, PyAny>) -> bool {
        !self.__eq__(other)
    }
    fn __repr__(&self) -> String {
        format!("Vec3i({}, {}, {})", self.x, self.y, self.z)
    }
    fn copy(&self) -> Self {
        self.clone()
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "Rotation", from_py_object)]
#[derive(Debug, Clone, Default)]
pub struct Rotation {
    #[pyo3(get, set)]
    pub yaw: f32,
    #[pyo3(get, set)]
    pub pitch: f32,
}

#[gen_stub_pymethods]
#[pymethods]
impl Rotation {
    #[new]
    #[pyo3(signature = (yaw=0.0, pitch=0.0))]
    pub fn __new__(yaw: f32, pitch: f32) -> Self {
        Self { yaw, pitch }
    }
    fn __repr__(&self) -> String {
        format!("Rotation(yaw={}, pitch={})", self.yaw, self.pitch)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MetadataValue
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "MetadataValue")]
#[derive(Debug)]
pub struct MetadataValue {
    #[pyo3(get, set)]
    pub type_id: i32,
    #[pyo3(get, set)]
    pub value: Py<PyAny>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MetadataValue {
    #[new]
    fn __new__(type_id: i32, value: Py<PyAny>) -> Self {
        Self { type_id, value }
    }
    fn __repr__(&self) -> String {
        format!("MetadataValue(type_id={})", self.type_id)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// PlayerInfo
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "PlayerInfo")]
#[derive(Debug)]
pub struct PlayerInfo {
    #[pyo3(get, set)]
    pub uuid: String,
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub properties: Vec<Py<PyAny>>,
    #[pyo3(get, set)]
    pub gamemode: i32,
    #[pyo3(get, set)]
    pub ping: i32,
    #[pyo3(get, set)]
    pub display_name: Option<Py<PyAny>>, // TextComponent | None
}

#[gen_stub_pymethods]
#[pymethods]
impl PlayerInfo {
    #[new]
    #[pyo3(signature = (uuid="".to_string(), name="".to_string(), properties=None, gamemode=0, ping=0, display_name=None))]
    fn __new__(
        uuid: String,
        name: String,
        properties: Option<Vec<Py<PyAny>>>,
        gamemode: i32,
        ping: i32,
        display_name: Option<Py<PyAny>>,
    ) -> Self {
        Self {
            uuid,
            name,
            properties: properties.unwrap_or_default(),
            gamemode,
            ping,
            display_name,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// EntityEquipment
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "EntityEquipment")]
#[derive(Debug)]
pub struct EntityEquipment {
    #[pyo3(get, set)]
    pub held: Py<PyAny>,
    #[pyo3(get, set)]
    pub boots: Py<PyAny>,
    #[pyo3(get, set)]
    pub leggings: Py<PyAny>,
    #[pyo3(get, set)]
    pub chestplate: Py<PyAny>,
    #[pyo3(get, set)]
    pub helmet: Py<PyAny>,
}

impl EntityEquipment {
    pub fn new_empty(py: Python<'_>) -> PyResult<Self> {
        let empty = empty_slot(py)?;
        Ok(Self {
            held: empty.clone_ref(py),
            boots: empty.clone_ref(py),
            leggings: empty.clone_ref(py),
            chestplate: empty.clone_ref(py),
            helmet: empty,
        })
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl EntityEquipment {
    #[new]
    fn __new__(
        held: Py<PyAny>,
        boots: Py<PyAny>,
        leggings: Py<PyAny>,
        chestplate: Py<PyAny>,
        helmet: Py<PyAny>,
    ) -> Self {
        Self {
            held,
            boots,
            leggings,
            chestplate,
            helmet,
        }
    }
}

/// Create an empty SlotData Python object.
pub fn empty_slot(py: Python<'_>) -> PyResult<Py<PyAny>> {
    let slot_mod = py.import("petty.models")?;
    let slot_data_cls = slot_mod.getattr("SlotData")?;
    Ok(slot_data_cls.call0()?.into())
}

// ─────────────────────────────────────────────────────────────────────────────
// EntityEffect
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "EntityEffect")]
#[derive(Debug)]
pub struct EntityEffect {
    #[pyo3(get, set)]
    pub effect_id: i32,
    #[pyo3(get, set)]
    pub amplifier: i32,
    #[pyo3(get, set)]
    pub duration: i32,
    #[pyo3(get, set)]
    pub hide_particles: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl EntityEffect {
    #[new]
    #[pyo3(signature = (effect_id=0, amplifier=0, duration=0, hide_particles=false))]
    fn __new__(effect_id: i32, amplifier: i32, duration: i32, hide_particles: bool) -> Self {
        Self {
            effect_id,
            amplifier,
            duration,
            hide_particles,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// AttributeModifier / EntityAttribute
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "AttributeModifier")]
#[derive(Debug)]
pub struct AttributeModifier {
    #[pyo3(get, set)]
    pub uuid: String,
    #[pyo3(get, set)]
    pub amount: f64,
    #[pyo3(get, set)]
    pub operation: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl AttributeModifier {
    #[new]
    #[pyo3(signature = (uuid="".to_string(), amount=0.0, operation=0))]
    fn __new__(uuid: String, amount: f64, operation: i32) -> Self {
        Self {
            uuid,
            amount,
            operation,
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "EntityAttribute")]
#[derive(Debug)]
pub struct EntityAttribute {
    #[pyo3(get, set)]
    pub key: String,
    #[pyo3(get, set)]
    pub value: f64,
    #[pyo3(get, set)]
    pub modifiers: Vec<Py<PyAny>>, // list[AttributeModifier]
}

#[gen_stub_pymethods]
#[pymethods]
impl EntityAttribute {
    #[new]
    #[pyo3(signature = (key="".to_string(), value=0.0, modifiers=None))]
    fn __new__(key: String, value: f64, modifiers: Option<Vec<Py<PyAny>>>) -> Self {
        Self {
            key,
            value,
            modifiers: modifiers.unwrap_or_default(),
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Entity
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Entity", subclass)]
#[derive(Debug)]
pub struct Entity {
    #[pyo3(get, set)]
    pub entity_id: i32,
    #[pyo3(get, set)]
    pub entity_type: i32,
    #[pyo3(get, set)]
    pub uuid: String,
    #[pyo3(get, set)]
    pub position: Py<Vec3d>,
    #[pyo3(get, set)]
    pub rotation: Py<Rotation>,
    #[pyo3(get, set)]
    pub head_yaw: f32,
    #[pyo3(get, set)]
    pub velocity: Py<Vec3d>,
    #[pyo3(get, set)]
    pub on_ground: bool,
    #[pyo3(get, set)]
    pub metadata: Py<PyAny>, // dict[int, MetadataValue]
    #[pyo3(get, set)]
    pub equipment: Py<EntityEquipment>,
    #[pyo3(get, set)]
    pub effects: Py<PyAny>, // dict[int, EntityEffect]
    #[pyo3(get, set)]
    pub attributes: Py<PyAny>, // dict[str, EntityAttribute]
    #[pyo3(get, set)]
    pub passengers: Vec<i32>,
    #[pyo3(get, set)]
    pub vehicle_id: Option<i32>,
    #[pyo3(get, set)]
    pub object_data: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl Entity {
    #[new]
    #[pyo3(signature = (entity_id=0, entity_type=0, uuid="".to_string(), position=None, rotation=None, head_yaw=0.0, velocity=None, on_ground=false, metadata=None, equipment=None, effects=None, attributes=None, passengers=None, vehicle_id=None, object_data=0))]
    #[allow(clippy::too_many_arguments)]
    fn __new__(
        py: Python<'_>,
        entity_id: i32,
        entity_type: i32,
        uuid: String,
        position: Option<Py<Vec3d>>,
        rotation: Option<Py<Rotation>>,
        head_yaw: f32,
        velocity: Option<Py<Vec3d>>,
        on_ground: bool,
        metadata: Option<Py<PyAny>>,
        equipment: Option<Py<EntityEquipment>>,
        effects: Option<Py<PyAny>>,
        attributes: Option<Py<PyAny>>,
        passengers: Option<Vec<i32>>,
        vehicle_id: Option<i32>,
        object_data: i32,
    ) -> PyResult<Self> {
        let position = position.unwrap_or_else(|| Py::new(py, Vec3d::default()).unwrap());
        let rotation = rotation.unwrap_or_else(|| Py::new(py, Rotation::default()).unwrap());
        let velocity = velocity.unwrap_or_else(|| Py::new(py, Vec3d::default()).unwrap());
        let equipment = equipment
            .unwrap_or_else(|| Py::new(py, EntityEquipment::new_empty(py).unwrap()).unwrap());
        let metadata = metadata.unwrap_or_else(|| PyDict::new(py).into());
        let effects = effects.unwrap_or_else(|| PyDict::new(py).into());
        let attributes = attributes.unwrap_or_else(|| PyDict::new(py).into());
        Ok(Self {
            entity_id,
            entity_type,
            uuid,
            position,
            rotation,
            head_yaw,
            velocity,
            on_ground,
            metadata,
            equipment,
            effects,
            attributes,
            passengers: passengers.unwrap_or_default(),
            vehicle_id,
            object_data,
        })
    }

    fn __repr__(&self) -> String {
        format!("Entity(id={}, type={})", self.entity_id, self.entity_type)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Player (extends Entity)
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Player", extends = Entity)]
#[derive(Debug)]
pub struct Player {
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub current_item: i32,
    #[pyo3(get, set)]
    pub properties: Vec<Py<PyAny>>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Player {
    #[new]
    #[pyo3(signature = (entity_id=0, uuid="".to_string(), position=None, rotation=None, head_yaw=0.0, velocity=None, on_ground=false, metadata=None, equipment=None, effects=None, attributes=None, passengers=None, vehicle_id=None, object_data=0, name="".to_string(), current_item=0, properties=None))]
    #[allow(clippy::too_many_arguments)]
    fn __new__(
        py: Python<'_>,
        entity_id: i32,
        uuid: String,
        position: Option<Py<Vec3d>>,
        rotation: Option<Py<Rotation>>,
        head_yaw: f32,
        velocity: Option<Py<Vec3d>>,
        on_ground: bool,
        metadata: Option<Py<PyAny>>,
        equipment: Option<Py<EntityEquipment>>,
        effects: Option<Py<PyAny>>,
        attributes: Option<Py<PyAny>>,
        passengers: Option<Vec<i32>>,
        vehicle_id: Option<i32>,
        object_data: i32,
        name: String,
        current_item: i32,
        properties: Option<Vec<Py<PyAny>>>,
    ) -> PyResult<(Player, Entity)> {
        let base = Entity::__new__(
            py,
            entity_id,
            0,
            uuid,
            position,
            rotation,
            head_yaw,
            velocity,
            on_ground,
            metadata,
            equipment,
            effects,
            attributes,
            passengers,
            vehicle_id,
            object_data,
        )?;
        Ok((
            Player {
                name,
                current_item,
                properties: properties.unwrap_or_default(),
            },
            base,
        ))
    }

    fn __repr__(slf: PyRef<'_, Self>) -> String {
        let base = slf.as_ref();
        format!("Player(id={}, name={:?})", base.entity_id, slf.name)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Chunk / ChunkSection
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct ChunkSection {
    pub blocks: Vec<u8>,            // 8192 bytes: 4096 blocks × 2 bytes LE
    pub block_light: Vec<u8>,       // 2048 bytes
    pub sky_light: Option<Vec<u8>>, // 2048 bytes, overworld only
}

impl ChunkSection {
    #[allow(clippy::new_without_default)]
    pub fn new() -> Self {
        Self {
            blocks: vec![0u8; 8192],
            block_light: vec![0u8; 2048],
            sky_light: None,
        }
    }

    #[inline]
    pub fn get_block(&self, x: usize, y: usize, z: usize) -> u16 {
        let idx = ((y * 16 + z) * 16 + x) * 2;
        self.blocks[idx] as u16 | ((self.blocks[idx + 1] as u16) << 8)
    }

    #[inline]
    pub fn set_block(&mut self, x: usize, y: usize, z: usize, block_state: u16) {
        let idx = ((y * 16 + z) * 16 + x) * 2;
        self.blocks[idx] = (block_state & 0xFF) as u8;
        self.blocks[idx + 1] = ((block_state >> 8) & 0xFF) as u8;
    }
}

#[derive(Debug)]
pub struct Chunk {
    pub x: i32,
    pub z: i32,
    pub sections: [Option<Box<ChunkSection>>; 16],
    pub biomes: Vec<u8>, // 256 bytes
    pub has_sky_light: bool,
}

impl Chunk {
    pub fn new(x: i32, z: i32, has_sky_light: bool) -> Self {
        const NONE: Option<Box<ChunkSection>> = None;
        Self {
            x,
            z,
            sections: [NONE; 16],
            biomes: vec![0u8; 256],
            has_sky_light,
        }
    }

    pub fn get_block(&self, x: usize, y: usize, z: usize) -> u16 {
        let section_y = y / 16;
        match &self.sections[section_y] {
            None => 0,
            Some(s) => s.get_block(x, y % 16, z),
        }
    }

    pub fn set_block(&mut self, x: usize, y: usize, z: usize, block_state: u16) {
        let section_y = y / 16;
        if self.sections[section_y].is_none() {
            let mut sec = Box::new(ChunkSection::new());
            if self.has_sky_light {
                sec.sky_light = Some(vec![0u8; 2048]);
            }
            self.sections[section_y] = Some(sec);
        }
        self.sections[section_y]
            .as_mut()
            .unwrap()
            .set_block(x, y % 16, z, block_state);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Window
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Window")]
#[derive(Debug)]
pub struct Window {
    #[pyo3(get, set)]
    pub window_id: i32,
    #[pyo3(get, set)]
    pub window_type: String,
    #[pyo3(get, set)]
    pub title: String,
    #[pyo3(get, set)]
    pub slot_count: i32,
    #[pyo3(get, set)]
    pub slots: Py<PyAny>, // dict[int, SlotData]
    #[pyo3(get, set)]
    pub entity_id: Option<i32>,
    #[pyo3(get, set)]
    pub properties: Py<PyAny>, // dict[int, int]
}

#[gen_stub_pymethods]
#[pymethods]
impl Window {
    #[new]
    #[pyo3(signature = (window_id=0, window_type="".to_string(), title="".to_string(), slot_count=0, slots=None, entity_id=None, properties=None))]
    #[allow(clippy::too_many_arguments)]
    fn __new__(
        py: Python<'_>,
        window_id: i32,
        window_type: String,
        title: String,
        slot_count: i32,
        slots: Option<Py<PyAny>>,
        entity_id: Option<i32>,
        properties: Option<Py<PyAny>>,
    ) -> Self {
        Self {
            window_id,
            window_type,
            title,
            slot_count,
            slots: slots.unwrap_or_else(|| PyDict::new(py).into()),
            entity_id,
            properties: properties.unwrap_or_else(|| PyDict::new(py).into()),
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Scoreboard types
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "ScoreboardObjective")]
#[derive(Debug)]
pub struct ScoreboardObjective {
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub display_text: String,
    #[pyo3(get, set)]
    pub objective_type: String,
}

#[gen_stub_pymethods]
#[pymethods]
impl ScoreboardObjective {
    #[new]
    #[pyo3(signature = (name="".to_string(), display_text="".to_string(), objective_type="integer".to_string()))]
    fn __new__(name: String, display_text: String, objective_type: String) -> Self {
        Self {
            name,
            display_text,
            objective_type,
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "Score")]
#[derive(Debug)]
pub struct Score {
    #[pyo3(get, set)]
    pub score_name: String,
    #[pyo3(get, set)]
    pub objective_name: String,
    #[pyo3(get, set)]
    pub value: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl Score {
    #[new]
    #[pyo3(signature = (score_name="".to_string(), objective_name="".to_string(), value=0))]
    fn __new__(score_name: String, objective_name: String, value: i32) -> Self {
        Self {
            score_name,
            objective_name,
            value,
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "Team")]
#[derive(Debug)]
pub struct Team {
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub display_name: String,
    #[pyo3(get, set)]
    pub prefix: String,
    #[pyo3(get, set)]
    pub suffix: String,
    #[pyo3(get, set)]
    pub friendly_fire: i32,
    #[pyo3(get, set)]
    pub name_tag_visibility: String,
    #[pyo3(get, set)]
    pub color: i32,
    pub members: std::collections::HashSet<String>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Team {
    #[new]
    #[pyo3(signature = (name="".to_string(), display_name="".to_string(), prefix="".to_string(), suffix="".to_string(), friendly_fire=0, name_tag_visibility="always".to_string(), color=0, members=None))]
    #[allow(clippy::too_many_arguments)]
    fn __new__(
        name: String,
        display_name: String,
        prefix: String,
        suffix: String,
        friendly_fire: i32,
        name_tag_visibility: String,
        color: i32,
        members: Option<std::collections::HashSet<String>>,
    ) -> Self {
        Self {
            name,
            display_name,
            prefix,
            suffix,
            friendly_fire,
            name_tag_visibility,
            color,
            members: members.unwrap_or_default(),
        }
    }

    #[getter]
    fn members(&self, py: Python<'_>) -> Py<PyAny> {
        use pyo3::types::PySet;
        PySet::new(py, self.members.iter().collect::<Vec<_>>())
            .unwrap()
            .into()
    }

    #[setter]
    fn set_members(&mut self, members: std::collections::HashSet<String>) {
        self.members = members;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MapData
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "MapData")]
#[derive(Debug)]
pub struct MapData {
    #[pyo3(get, set)]
    pub map_id: i32,
    #[pyo3(get, set)]
    pub scale: i32,
    #[pyo3(get, set)]
    pub icons: Vec<Py<PyAny>>,
    pub pixels: Vec<u8>, // 128*128
}

#[gen_stub_pymethods]
#[pymethods]
impl MapData {
    #[new]
    #[pyo3(signature = (map_id=0, scale=0, icons=None, pixels=None))]
    fn __new__(
        map_id: i32,
        scale: i32,
        icons: Option<Vec<Py<PyAny>>>,
        pixels: Option<Vec<u8>>,
    ) -> Self {
        Self {
            map_id,
            scale,
            icons: icons.unwrap_or_default(),
            pixels: pixels.unwrap_or_else(|| vec![0u8; 128 * 128]),
        }
    }

    #[getter]
    fn pixels(&self, py: Python<'_>) -> Py<PyAny> {
        use pyo3::types::PyByteArray;
        PyByteArray::new(py, &self.pixels).into()
    }

    fn update_region(
        &mut self,
        x: i32,
        z: i32,
        width: i32,
        height: i32,
        data: pyo3::pybacked::PyBackedBytes,
    ) {
        let mut idx = 0usize;
        for row in 0..height {
            for col in 0..width {
                let px = x + col;
                let pz = z + row;
                if (0..128).contains(&px) && (0..128).contains(&pz) {
                    self.pixels[(pz * 128 + px) as usize] = data[idx];
                }
                idx += 1;
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// BlockEntity
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "BlockEntity")]
#[derive(Debug)]
pub struct BlockEntity {
    #[pyo3(get, set)]
    pub position: Py<Vec3i>,
    #[pyo3(get, set)]
    pub action: i32,
    pub nbt_data: Vec<u8>,
}

#[gen_stub_pymethods]
#[pymethods]
impl BlockEntity {
    #[new]
    #[pyo3(signature = (position=None, action=0, nbt_data=None))]
    fn __new__(
        py: Python<'_>,
        position: Option<Py<Vec3i>>,
        action: i32,
        nbt_data: Option<Vec<u8>>,
    ) -> Self {
        Self {
            position: position.unwrap_or_else(|| Py::new(py, Vec3i::default()).unwrap()),
            action,
            nbt_data: nbt_data.unwrap_or_default(),
        }
    }

    #[getter]
    fn nbt_data(&self, py: Python<'_>) -> Py<PyAny> {
        use pyo3::types::PyBytes;
        PyBytes::new(py, &self.nbt_data).into()
    }

    #[setter]
    fn set_nbt_data(&mut self, data: Vec<u8>) {
        self.nbt_data = data;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// WorldBorder
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "WorldBorder")]
#[derive(Debug)]
pub struct WorldBorder {
    #[pyo3(get, set)]
    pub center_x: f64,
    #[pyo3(get, set)]
    pub center_z: f64,
    #[pyo3(get, set)]
    pub old_radius: f64,
    #[pyo3(get, set)]
    pub new_radius: f64,
    #[pyo3(get, set)]
    pub speed: i64,
    #[pyo3(get, set)]
    pub portal_boundary: i64,
    #[pyo3(get, set)]
    pub warning_time: i64,
    #[pyo3(get, set)]
    pub warning_blocks: i64,
}

#[gen_stub_pymethods]
#[pymethods]
impl WorldBorder {
    #[new]
    fn __new__() -> Self {
        Self {
            center_x: 0.0,
            center_z: 0.0,
            old_radius: 60000000.0,
            new_radius: 60000000.0,
            speed: 0,
            portal_boundary: 29999984,
            warning_time: 15,
            warning_blocks: 5,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// TitleState
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "TitleState")]
#[derive(Debug)]
pub struct TitleState {
    #[pyo3(get, set)]
    pub title: String,
    #[pyo3(get, set)]
    pub subtitle: String,
    #[pyo3(get, set)]
    pub fade_in: i32,
    #[pyo3(get, set)]
    pub stay: i32,
    #[pyo3(get, set)]
    pub fade_out: i32,
    #[pyo3(get, set)]
    pub visible: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl TitleState {
    #[new]
    fn __new__() -> Self {
        Self {
            title: String::new(),
            subtitle: String::new(),
            fade_in: 10,
            stay: 70,
            fade_out: 20,
            visible: false,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Statistics / ResourcePack / PluginChannel / VillagerTrade
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Statistics")]
#[derive(Debug)]
pub struct Statistics {
    #[pyo3(get, set)]
    pub stats: Py<PyAny>, // dict[str, int]
}

#[gen_stub_pymethods]
#[pymethods]
impl Statistics {
    #[new]
    fn __new__(py: Python<'_>) -> Self {
        Self {
            stats: PyDict::new(py).into(),
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "ResourcePack")]
#[derive(Debug)]
pub struct ResourcePack {
    #[pyo3(get, set)]
    pub url: String,
    #[pyo3(get, set)]
    pub hash: String,
    #[pyo3(get, set)]
    pub status: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl ResourcePack {
    #[new]
    fn __new__() -> Self {
        Self {
            url: String::new(),
            hash: String::new(),
            status: 0,
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "PluginChannel")]
#[derive(Debug)]
pub struct PluginChannel {
    pub registered: std::collections::HashSet<String>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PluginChannel {
    #[new]
    fn __new__() -> Self {
        Self {
            registered: std::collections::HashSet::new(),
        }
    }

    #[getter]
    fn registered(&self, py: Python<'_>) -> Py<PyAny> {
        use pyo3::types::PySet;
        PySet::new(py, self.registered.iter().collect::<Vec<_>>())
            .unwrap()
            .into()
    }

    #[setter]
    fn set_registered(&mut self, registered: std::collections::HashSet<String>) {
        self.registered = registered;
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "VillagerTrade")]
#[derive(Debug)]
pub struct VillagerTrade {
    #[pyo3(get, set)]
    pub input_item_1: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    pub output_item: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    pub has_second_item: bool,
    #[pyo3(get, set)]
    pub input_item_2: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    pub trade_disabled: bool,
    #[pyo3(get, set)]
    pub trade_uses: i32,
    #[pyo3(get, set)]
    pub max_trade_uses: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl VillagerTrade {
    #[new]
    #[pyo3(signature = (input_item_1=None, output_item=None, has_second_item=false, input_item_2=None, trade_disabled=false, trade_uses=0, max_trade_uses=0))]
    fn __new__(
        input_item_1: Option<Py<PyAny>>,
        output_item: Option<Py<PyAny>>,
        has_second_item: bool,
        input_item_2: Option<Py<PyAny>>,
        trade_disabled: bool,
        trade_uses: i32,
        max_trade_uses: i32,
    ) -> Self {
        Self {
            input_item_1,
            output_item,
            has_second_item,
            input_item_2,
            trade_disabled,
            trade_uses,
            max_trade_uses,
        }
    }
}
