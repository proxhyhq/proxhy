/// Rust implementation of Slot (SlotData + Item) parsing and packing.
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};

use crate::item_data::ITEMS;

// ─────────────────────────────────────────────────────────────────────────────
// Item lookup table  (id → (name, display_name, data))
// ─────────────────────────────────────────────────────────────────────────────

pub fn item_from_id(id: u16) -> Option<(u16, &'static str, &'static str, u16)> {
    ITEMS
        .iter()
        .find(|&&(item_id, _, _, _)| item_id == id)
        .copied()
}

// ─────────────────────────────────────────────────────────────────────────────
// Python classes
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Item", from_py_object)]
#[derive(Clone, Debug)]
pub struct PyItem {
    #[pyo3(get, set)]
    pub id: i32,
    #[pyo3(get, set)]
    pub name: std::string::String,
    #[pyo3(get, set)]
    pub display_name: std::string::String,
    #[pyo3(get, set)]
    pub data: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyItem {
    #[new]
    fn __new__(
        id: i32,
        name: std::string::String,
        display_name: std::string::String,
        data: i32,
    ) -> Self {
        Self {
            id,
            name,
            display_name,
            data,
        }
    }

    #[classmethod]
    fn from_id(_cls: &Bound<'_, pyo3::types::PyType>, id: i32) -> Option<Self> {
        item_from_id(id as u16).map(|(item_id, name, display_name, data)| PyItem {
            id: item_id as i32,
            name: name.to_string(),
            display_name: display_name.to_string(),
            data: data as i32,
        })
    }

    #[classmethod]
    fn from_name(_cls: &Bound<'_, pyo3::types::PyType>, name: &str) -> Option<Self> {
        let search = if name.starts_with("minecraft:") {
            name.to_string()
        } else {
            format!("minecraft:{}", name)
        };
        ITEMS
            .iter()
            .find(|&&(_, item_name, _, _)| item_name == search)
            .map(|&(id, item_name, display_name, data)| PyItem {
                id: id as i32,
                name: item_name.to_string(),
                display_name: display_name.to_string(),
                data: data as i32,
            })
    }

    #[classmethod]
    fn from_display_name(
        _cls: &Bound<'_, pyo3::types::PyType>,
        display_name: &str,
    ) -> Option<Self> {
        ITEMS
            .iter()
            .find(|&&(_, _, dn, _)| dn == display_name)
            .map(|&(id, name, dn, data)| PyItem {
                id: id as i32,
                name: name.to_string(),
                display_name: dn.to_string(),
                data: data as i32,
            })
    }

    fn __repr__(&self) -> std::string::String {
        format!("Item(id={}, name={:?})", self.id, self.name)
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "SlotData", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct PySlotData {
    #[pyo3(get, set)]
    pub item: Option<PyItem>,
    #[pyo3(get, set)]
    pub count: i32,
    #[pyo3(get, set)]
    pub damage: i32,
    #[pyo3(get, set)]
    pub nbt: Vec<u8>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PySlotData {
    #[new]
    #[pyo3(signature = (item=None, count=1, damage=0, nbt=None))]
    fn __new__(item: Option<PyItem>, count: i32, damage: i32, nbt: Option<Vec<u8>>) -> Self {
        if item.is_none() {
            Self {
                item: None,
                count: 0,
                damage: 0,
                nbt: Vec::new(),
            }
        } else {
            Self {
                item,
                count,
                damage,
                nbt: nbt.unwrap_or_default(),
            }
        }
    }

    fn __repr__(&self) -> std::string::String {
        match &self.item {
            None => "SlotData(empty)".to_string(),
            Some(item) => format!(
                "SlotData(item={:?}, count={}, damage={})",
                item.name, self.count, self.damage
            ),
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// NBT reading helper for slot data
// ─────────────────────────────────────────────────────────────────────────────

/// Read NBT bytes from a byte slice starting at `offset`. Returns (nbt_bytes, bytes_consumed).
pub fn read_slot_nbt(data: &[u8]) -> (Vec<u8>, usize) {
    if data.is_empty() || data[0] == 0 {
        // TAG_End or empty
        return (Vec::new(), 1.min(data.len()));
    }
    // Use the NBT reader to find exact size
    let mut reader = crate::nbt::NbtReaderPub::new(data);
    match reader.read_root_size() {
        Ok(consumed) => (data[..consumed].to_vec(), consumed),
        Err(_) => (Vec::new(), 1.min(data.len())),
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Slot parse/pack functions exposed to Python and used by gamestate
// ─────────────────────────────────────────────────────────────────────────────

/// Parse a SlotData from a raw bytes slice.
/// Returns (SlotData, bytes_consumed).
pub fn parse_slot(data: &[u8]) -> (PySlotData, usize) {
    if data.len() < 2 {
        return (
            PySlotData {
                item: None,
                count: 0,
                damage: 0,
                nbt: Vec::new(),
            },
            0,
        );
    }
    let item_id = i16::from_be_bytes([data[0], data[1]]);
    if item_id == -1 {
        return (
            PySlotData {
                item: None,
                count: 0,
                damage: 0,
                nbt: Vec::new(),
            },
            2,
        );
    }
    if data.len() < 5 {
        return (
            PySlotData {
                item: None,
                count: 0,
                damage: 0,
                nbt: Vec::new(),
            },
            2,
        );
    }
    let count = data[2] as i8 as i32;
    let damage = i16::from_be_bytes([data[3], data[4]]) as i32;
    let nbt_start = 5;
    let (nbt_bytes, nbt_consumed) = read_slot_nbt(&data[nbt_start..]);
    let total = nbt_start + nbt_consumed;

    let item = item_from_id(item_id as u16).map(|(id, name, display_name, item_data)| PyItem {
        id: id as i32,
        name: name.to_string(),
        display_name: display_name.to_string(),
        data: item_data as i32,
    });

    let slot = PySlotData {
        item,
        count,
        damage,
        nbt: nbt_bytes,
    };
    (slot, total)
}

/// Pack a SlotData to bytes.
pub fn pack_slot(slot: &PySlotData) -> Vec<u8> {
    match &slot.item {
        None => (-1i16).to_be_bytes().to_vec(),
        Some(item) => {
            let mut buf = Vec::with_capacity(7 + slot.nbt.len());
            buf.extend_from_slice(&(item.id as i16).to_be_bytes());
            buf.push(slot.count as u8);
            buf.extend_from_slice(&(slot.damage as i16).to_be_bytes());
            if slot.nbt.is_empty() {
                buf.push(0); // TAG_End
            } else {
                buf.extend_from_slice(&slot.nbt);
            }
            buf
        }
    }
}

// Python-callable wrappers
#[gen_stub_pyfunction]
#[pyfunction]
pub fn py_slot_unpack(py: Python<'_>, data: PyBackedBytes) -> PyResult<(Py<PyAny>, usize)> {
    let (slot, consumed) = parse_slot(&data);
    Ok((Py::new(py, slot)?.into_any(), consumed))
}

#[gen_stub_pyfunction]
#[pyfunction]
pub fn py_slot_pack(slot: &PySlotData) -> Vec<u8> {
    pack_slot(slot)
}
