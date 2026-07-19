//! Minecraft protocol primitive data types.
//!
//! Each type exposes two `#[staticmethod]`s:
//!   - `pack(value) -> bytes`   – serialise a Python value to Minecraft wire bytes
//!   - `unpack(buff) -> T`      – deserialise from a file-like Python object (BytesIO / Buffer)
//!
//! `Buffer` remains a thin Python subclass of `BytesIO` — not the hot path.

use pyo3::{
    prelude::*,
    types::{PyBytes, PyDict},
};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

// ── helpers ──────────────────────────────────────────────────────────────────

/// Read exactly `n` bytes from a Python file-like object.
fn read_bytes(buff: &Bound<'_, PyAny>, n: usize) -> PyResult<Vec<u8>> {
    let obj = buff.call_method1("read", (n,))?;
    let bytes: Vec<u8> = obj.extract()?;
    if bytes.len() != n {
        return Err(pyo3::exceptions::PyEOFError::new_err(format!(
            "expected {n} bytes, got {}",
            bytes.len()
        )));
    }
    Ok(bytes)
}

fn mk_bytes(py: Python<'_>, data: &[u8]) -> Py<PyBytes> {
    PyBytes::new(py, data).unbind()
}

// ── VarInt ────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "VarInt", subclass)]
pub struct VarInt;

#[gen_stub_pymethods]
#[pymethods]
impl VarInt {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: i32) -> Py<PyBytes> {
        let mut buf = Vec::with_capacity(5);
        let mut val = if value < 0 {
            (1u64 << 32).wrapping_add(value as u64)
        } else {
            value as u64
        };
        while val >= 0x80 {
            buf.push(0x80 | (val & 0x7F) as u8);
            val >>= 7;
        }
        buf.push((val & 0x7F) as u8);
        mk_bytes(py, &buf)
    }

    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<i32> {
        let mut total: u32 = 0;
        let mut shift = 0u32;
        loop {
            let data = read_bytes(buff, 1)?;
            let byte = data[0];
            total |= ((byte & 0x7F) as u32) << shift;
            if byte & 0x80 == 0 {
                break;
            }
            shift += 7;
            if shift >= 35 {
                return Err(pyo3::exceptions::PyValueError::new_err("VarInt too large"));
            }
        }
        Ok(if total & (1 << 31) != 0 {
            (total as i64 - (1i64 << 32)) as i32
        } else {
            total as i32
        })
    }
}

// ── UnsignedShort ─────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "UnsignedShort")]
pub struct UnsignedShort;

#[gen_stub_pymethods]
#[pymethods]
impl UnsignedShort {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: u16) -> Py<PyBytes> {
        mk_bytes(py, &value.to_be_bytes())
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<u16> {
        let b = read_bytes(buff, 2)?;
        Ok(u16::from_be_bytes([b[0], b[1]]))
    }
}

// ── Short ─────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Short")]
pub struct Short;

#[gen_stub_pymethods]
#[pymethods]
impl Short {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: i16) -> Py<PyBytes> {
        mk_bytes(py, &value.to_be_bytes())
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<i16> {
        let b = read_bytes(buff, 2)?;
        Ok(i16::from_be_bytes([b[0], b[1]]))
    }
}

// ── Long ──────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Long")]
pub struct Long;

#[gen_stub_pymethods]
#[pymethods]
impl Long {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: i64) -> Py<PyBytes> {
        mk_bytes(py, &value.to_be_bytes())
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<i64> {
        let b = read_bytes(buff, 8)?;
        Ok(i64::from_be_bytes(b.try_into().unwrap()))
    }
}

// ── Byte ──────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Byte")]
pub struct Byte;

#[gen_stub_pymethods]
#[pymethods]
impl Byte {
    /// Accepts int, float, or raw bytes (pass-through).
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        if let Ok(b) = value.extract::<Vec<u8>>() {
            return Ok(mk_bytes(py, &b));
        }
        let i: i8 = if let Ok(f) = value.extract::<f64>() {
            f as i8
        } else {
            value.extract::<i8>()?
        };
        Ok(mk_bytes(py, &i.to_be_bytes()))
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<i8> {
        let b = read_bytes(buff, 1)?;
        Ok(b[0] as i8)
    }
}

// ── UnsignedByte ──────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "UnsignedByte")]
pub struct UnsignedByte;

#[gen_stub_pymethods]
#[pymethods]
impl UnsignedByte {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        if let Ok(b) = value.extract::<Vec<u8>>() {
            return Ok(mk_bytes(py, &b));
        }
        let i: u8 = if let Ok(f) = value.extract::<f64>() {
            f as u8
        } else {
            value.extract::<u8>()?
        };
        Ok(mk_bytes(py, &[i]))
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<u8> {
        let b = read_bytes(buff, 1)?;
        Ok(b[0])
    }
}

// ── ByteArray ─────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "ByteArray")]
pub struct ByteArray;

#[gen_stub_pymethods]
#[pymethods]
impl ByteArray {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: Vec<u8>) -> Py<PyBytes> {
        let len_encoded = VarInt::pack(py, value.len() as i32);
        let len_bytes = len_encoded.bind(py).as_bytes();
        let mut out = Vec::with_capacity(len_bytes.len() + value.len());
        out.extend_from_slice(len_bytes);
        out.extend_from_slice(&value);
        mk_bytes(py, &out)
    }
    #[staticmethod]
    pub fn unpack(py: Python<'_>, buff: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        let length = VarInt::unpack(buff)? as usize;
        Ok(mk_bytes(py, &read_bytes(buff, length)?))
    }
}

// ── Boolean ───────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Boolean")]
pub struct Boolean;

#[gen_stub_pymethods]
#[pymethods]
impl Boolean {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: bool) -> Py<PyBytes> {
        mk_bytes(py, &[if value { 1 } else { 0 }])
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<bool> {
        let b = read_bytes(buff, 1)?;
        Ok(b[0] != 0)
    }
}

// ── Int ───────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Int")]
pub struct Int;

#[gen_stub_pymethods]
#[pymethods]
impl Int {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: i32) -> Py<PyBytes> {
        mk_bytes(py, &value.to_be_bytes())
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<i32> {
        let b = read_bytes(buff, 4)?;
        Ok(i32::from_be_bytes(b.try_into().unwrap()))
    }
}

// ── Float ─────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Float")]
pub struct Float;

#[gen_stub_pymethods]
#[pymethods]
impl Float {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: f32) -> Py<PyBytes> {
        mk_bytes(py, &value.to_be_bytes())
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<f32> {
        let b = read_bytes(buff, 4)?;
        Ok(f32::from_be_bytes(b.try_into().unwrap()))
    }
}

// ── Double ────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Double")]
pub struct Double;

#[gen_stub_pymethods]
#[pymethods]
impl Double {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: f64) -> Py<PyBytes> {
        mk_bytes(py, &value.to_be_bytes())
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<f64> {
        let b = read_bytes(buff, 8)?;
        Ok(f64::from_be_bytes(b.try_into().unwrap()))
    }
}

// ── Angle ─────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Angle")]
pub struct Angle;

#[gen_stub_pymethods]
#[pymethods]
impl Angle {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: f64) -> Py<PyBytes> {
        let encoded = (256.0 * ((value % 360.0) / 360.0)) as u8;
        mk_bytes(py, &[encoded])
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<f64> {
        let b = read_bytes(buff, 1)?;
        Ok(360.0 * b[0] as f64 / 256.0)
    }
}

// ── Position ──────────────────────────────────────────────────────────────────

use crate::models::Pos;

#[gen_stub_pyclass]
#[pyclass(name = "Position")]
pub struct Position;

#[gen_stub_pymethods]
#[pymethods]
impl Position {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        let (x, y, z): (i64, i64, i64) = if let Ok(pos) = value.extract::<PyRef<Pos>>() {
            (pos.x as i64, pos.y as i64, pos.z as i64)
        } else {
            value.extract::<(i64, i64, i64)>()?
        };
        let xm = (x & 0x3FFFFFF) as u64;
        let ym = (y & 0xFFF) as u64;
        let zm = (z & 0x3FFFFFF) as u64;
        let packed = (xm << 38) | (ym << 26) | zm;
        Ok(mk_bytes(py, &packed.to_be_bytes()))
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<Pos> {
        let b = read_bytes(buff, 8)?;
        let val = u64::from_be_bytes(b.try_into().unwrap());
        let mut x = (val >> 38) as i64;
        let mut y = ((val >> 26) & 0xFFF) as i64;
        let mut z = (val & 0x3FFFFFF) as i64;
        if x >= 1 << 25 {
            x -= 1 << 26;
        }
        if y >= 1 << 11 {
            y -= 1 << 12;
        }
        if z >= 1 << 25 {
            z -= 1 << 26;
        }
        Ok(Pos {
            x: x as i32,
            y: y as i32,
            z: z as i32,
        })
    }
}

// ── UUID ──────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "UUID")]
pub struct Uuid;

#[gen_stub_pymethods]
#[pymethods]
impl Uuid {
    /// Accepts a Python `uuid.UUID` — reads its `.bytes` property.
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        let bytes_obj = value.getattr("bytes")?;
        let bytes: Vec<u8> = bytes_obj.extract()?;
        Ok(mk_bytes(py, &bytes))
    }
    /// Returns a Python `uuid.UUID`.
    #[staticmethod]
    pub fn unpack(py: Python<'_>, buff: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let b = read_bytes(buff, 16)?;
        let uuid_mod = py.import("uuid")?;
        let uuid_cls = uuid_mod.getattr("UUID")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("bytes", PyBytes::new(py, &b))?;
        Ok(uuid_cls.call((), Some(&kwargs))?.unbind())
    }
}

// ── String ────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "String")]
pub struct PettyString;

#[gen_stub_pymethods]
#[pymethods]
impl PettyString {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: &str) -> Py<PyBytes> {
        let encoded = value.as_bytes();
        let len_py = VarInt::pack(py, encoded.len() as i32);
        let len_bytes = len_py.bind(py).as_bytes();
        let mut out = Vec::with_capacity(len_bytes.len() + encoded.len());
        out.extend_from_slice(len_bytes);
        out.extend_from_slice(encoded);
        mk_bytes(py, &out)
    }
    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<String> {
        let length = VarInt::unpack(buff)? as usize;
        let raw = read_bytes(buff, length)?;
        String::from_utf8(raw)
            .map_err(|e| pyo3::exceptions::PyUnicodeDecodeError::new_err(e.to_string()))
    }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

use crate::models::TextComponent;

#[gen_stub_pyclass]
#[pyclass(name = "Chat")]
pub struct Chat;

#[gen_stub_pymethods]
#[pymethods]
impl Chat {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        let json_str: String = if let Ok(tc) = value.extract::<PyRef<TextComponent>>() {
            tc.to_json_str()
        } else if let Ok(s) = value.extract::<String>() {
            format!(r#"{{"text":"{}"}}"#, s.replace('"', r#"\""#))
        } else {
            // dict or anything else: use orjson
            let orjson = py.import("orjson")?;
            let dumped: Vec<u8> = orjson.call_method1("dumps", (value,))?.extract()?;
            String::from_utf8(dumped)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
        };
        Ok(PettyString::pack(py, &json_str))
    }

    /// Pack with trailing position byte `0x00` (chat message position).
    #[staticmethod]
    pub fn pack_msg(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
        let packed = Chat::pack(py, value)?;
        let mut out = packed.bind(py).as_bytes().to_vec();
        out.push(0x00);
        Ok(mk_bytes(py, &out))
    }

    /// Unpack to plain text string (strips §-colour codes).
    #[staticmethod]
    pub fn unpack(py: Python<'_>, buff: &Bound<'_, PyAny>) -> PyResult<String> {
        let json_str = PettyString::unpack(buff)?;
        let orjson = py.import("orjson")?;
        let data = orjson.call_method1("loads", (json_str.as_str(),))?;
        let text = chat_to_plain_text(&data)?;
        Ok(strip_section_codes(&text))
    }

    /// Unpack to a `TextComponent` object.
    #[staticmethod]
    pub fn unpack_component(py: Python<'_>, buff: &Bound<'_, PyAny>) -> PyResult<TextComponent> {
        let json_str = PettyString::unpack(buff)?;
        let orjson = py.import("orjson")?;
        let data = orjson.call_method1("loads", (json_str.as_str(),))?;
        Ok(TextComponent::from_py_data(data.unbind()))
    }
}

pub(crate) fn chat_to_plain_text(data: &Bound<'_, PyAny>) -> PyResult<String> {
    use pyo3::types::{PyDict, PyList};
    let mut text = String::new();
    if let Ok(s) = data.extract::<String>() {
        return Ok(s);
    }
    if let Ok(list) = data.cast::<PyList>() {
        for item in list {
            text.push_str(&chat_to_plain_text(&item)?);
        }
        return Ok(text);
    }
    if let Ok(dict) = data.cast::<PyDict>() {
        if let Some(t) = dict.get_item("translate")? {
            text.push_str(&t.extract::<String>()?);
            if let Some(with) = dict.get_item("with")?
                && let Ok(list) = with.cast::<PyList>()
            {
                let parts: Vec<String> = list
                    .iter()
                    .map(|a| chat_to_plain_text(&a))
                    .collect::<PyResult<_>>()?;
                text.push_str(&parts.join(", "));
            }
        }
        if let Some(t) = dict.get_item("text")? {
            text.push_str(&t.extract::<String>()?);
        }
        if let Some(extra) = dict.get_item("extra")? {
            text.push_str(&chat_to_plain_text(&extra)?);
        }
    }
    Ok(text)
}

pub(crate) fn strip_section_codes(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\u{00a7}' {
            chars.next();
        } else {
            out.push(c);
        }
    }
    out
}

// ── Slot ──────────────────────────────────────────────────────────────────────

use crate::models::{Item, SlotData};

#[gen_stub_pyclass]
#[pyclass(name = "Slot")]
pub struct Slot;

#[gen_stub_pymethods]
#[pymethods]
impl Slot {
    #[staticmethod]
    pub fn pack(py: Python<'_>, value: PyRef<'_, SlotData>) -> PyResult<Py<PyBytes>> {
        if value.item.is_none() {
            return Ok(Short::pack(py, -1));
        }
        let item = value.item.as_ref().unwrap();
        let mut out = Short::pack(py, item.id as i16).bind(py).as_bytes().to_vec();
        out.push(value.count as i8 as u8);
        out.extend_from_slice(&(value.damage as i16).to_be_bytes());
        if value.nbt.is_empty() {
            out.push(0); // TAG_End
        } else {
            out.extend_from_slice(&value.nbt);
        }
        Ok(mk_bytes(py, &out))
    }

    #[staticmethod]
    pub fn unpack(buff: &Bound<'_, PyAny>) -> PyResult<SlotData> {
        let item_id = Short::unpack(buff)?;
        if item_id == -1 {
            return Ok(SlotData::empty());
        }
        let count = Byte::unpack(buff)? as i32;
        let damage = Short::unpack(buff)? as i32;
        let nbt_bytes = read_nbt_bytes(buff)?;
        match Item::from_id_rust(item_id as i32) {
            None => Ok(SlotData::empty()),
            Some(item) => Ok(SlotData {
                item: Some(item),
                count,
                damage,
                nbt: nbt_bytes,
            }),
        }
    }
}

/// Peek at tag type; if non-zero, read the full raw NBT payload from the buffer.
fn read_nbt_bytes(buff: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    let tag_byte = read_bytes(buff, 1)?;
    if tag_byte[0] == 0 {
        return Ok(Vec::new());
    }
    // Seek back to include the tag byte, then read all remaining bytes.
    let start: i64 = buff.call_method0("tell")?.extract::<i64>()? - 1;
    buff.call_method1("seek", (start,))?;
    let remaining: Vec<u8> = buff.call_method0("read")?.extract()?;
    if remaining.is_empty() {
        return Ok(Vec::new());
    }
    let consumed = crate::nbt::measure_nbt_bytes(&remaining)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    buff.call_method1("seek", (start + consumed as i64,))?;
    Ok(remaining[..consumed].to_vec())
}
