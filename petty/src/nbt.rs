/// Rust NBT implementation for petty.
/// Mirrors the Python petty.nbt API exactly.
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3::types::{PyBool, PyBytes, PyDict, PyList};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};
use std::io::{Cursor, Read};

// ─────────────────────────────────────────────────────────────────────────────
// Internal Rust NBT tree
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum NbtTag {
    End,
    Byte(i8),
    Short(i16),
    Int(i32),
    Long(i64),
    Float(f32),
    Double(f64),
    ByteArray(Vec<i8>),
    String(std::string::String),
    List(u8, Vec<NbtTag>), // (element_type, items)
    Compound(Vec<(std::string::String, NbtTag)>),
    IntArray(Vec<i32>),
    LongArray(Vec<i64>),
}

impl NbtTag {
    pub fn tag_type_id(&self) -> u8 {
        match self {
            NbtTag::End => 0,
            NbtTag::Byte(_) => 1,
            NbtTag::Short(_) => 2,
            NbtTag::Int(_) => 3,
            NbtTag::Long(_) => 4,
            NbtTag::Float(_) => 5,
            NbtTag::Double(_) => 6,
            NbtTag::ByteArray(_) => 7,
            NbtTag::String(_) => 8,
            NbtTag::List(_, _) => 9,
            NbtTag::Compound(_) => 10,
            NbtTag::IntArray(_) => 11,
            NbtTag::LongArray(_) => 12,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Reader
// ─────────────────────────────────────────────────────────────────────────────

struct NbtReader<'a> {
    cur: Cursor<&'a [u8]>,
}

impl<'a> NbtReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self {
            cur: Cursor::new(data),
        }
    }

    fn read_byte(&mut self) -> Result<i8, std::io::Error> {
        let mut buf = [0u8; 1];
        self.cur.read_exact(&mut buf)?;
        Ok(buf[0] as i8)
    }

    fn read_ubyte(&mut self) -> Result<u8, std::io::Error> {
        let mut buf = [0u8; 1];
        self.cur.read_exact(&mut buf)?;
        Ok(buf[0])
    }

    fn read_short(&mut self) -> Result<i16, std::io::Error> {
        let mut buf = [0u8; 2];
        self.cur.read_exact(&mut buf)?;
        Ok(i16::from_be_bytes(buf))
    }

    fn read_int(&mut self) -> Result<i32, std::io::Error> {
        let mut buf = [0u8; 4];
        self.cur.read_exact(&mut buf)?;
        Ok(i32::from_be_bytes(buf))
    }

    fn read_long(&mut self) -> Result<i64, std::io::Error> {
        let mut buf = [0u8; 8];
        self.cur.read_exact(&mut buf)?;
        Ok(i64::from_be_bytes(buf))
    }

    fn read_float(&mut self) -> Result<f32, std::io::Error> {
        let mut buf = [0u8; 4];
        self.cur.read_exact(&mut buf)?;
        Ok(f32::from_be_bytes(buf))
    }

    fn read_double(&mut self) -> Result<f64, std::io::Error> {
        let mut buf = [0u8; 8];
        self.cur.read_exact(&mut buf)?;
        Ok(f64::from_be_bytes(buf))
    }

    fn read_string(&mut self) -> Result<std::string::String, std::io::Error> {
        let len = self.read_short()? as usize;
        let mut buf = vec![0u8; len];
        self.cur.read_exact(&mut buf)?;
        Ok(std::string::String::from_utf8_lossy(&buf).into_owned())
    }

    fn read_byte_array(&mut self) -> Result<Vec<i8>, std::io::Error> {
        let len = self.read_int()? as usize;
        let mut buf = vec![0u8; len];
        self.cur.read_exact(&mut buf)?;
        Ok(buf.into_iter().map(|b| b as i8).collect())
    }

    fn read_int_array(&mut self) -> Result<Vec<i32>, std::io::Error> {
        let len = self.read_int()? as usize;
        let mut result = Vec::with_capacity(len);
        for _ in 0..len {
            result.push(self.read_int()?);
        }
        Ok(result)
    }

    fn read_long_array(&mut self) -> Result<Vec<i64>, std::io::Error> {
        let len = self.read_int()? as usize;
        let mut result = Vec::with_capacity(len);
        for _ in 0..len {
            result.push(self.read_long()?);
        }
        Ok(result)
    }

    fn read_list(&mut self) -> Result<NbtTag, std::io::Error> {
        let type_id = self.read_ubyte()?;
        let len = self.read_int()? as usize;
        let mut items = Vec::with_capacity(len);
        for _ in 0..len {
            items.push(self.read_payload(type_id)?);
        }
        Ok(NbtTag::List(type_id, items))
    }

    fn read_compound(&mut self) -> Result<NbtTag, std::io::Error> {
        let mut entries = Vec::new();
        loop {
            let type_id = self.read_ubyte()?;
            if type_id == 0 {
                break;
            }
            let name = self.read_string()?;
            let tag = self.read_payload(type_id)?;
            entries.push((name, tag));
        }
        Ok(NbtTag::Compound(entries))
    }

    fn read_payload(&mut self, type_id: u8) -> Result<NbtTag, std::io::Error> {
        match type_id {
            0 => Ok(NbtTag::End),
            1 => Ok(NbtTag::Byte(self.read_byte()?)),
            2 => Ok(NbtTag::Short(self.read_short()?)),
            3 => Ok(NbtTag::Int(self.read_int()?)),
            4 => Ok(NbtTag::Long(self.read_long()?)),
            5 => Ok(NbtTag::Float(self.read_float()?)),
            6 => Ok(NbtTag::Double(self.read_double()?)),
            7 => Ok(NbtTag::ByteArray(self.read_byte_array()?)),
            8 => Ok(NbtTag::String(self.read_string()?)),
            9 => self.read_list(),
            10 => self.read_compound(),
            11 => Ok(NbtTag::IntArray(self.read_int_array()?)),
            12 => Ok(NbtTag::LongArray(self.read_long_array()?)),
            _ => Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("Unknown NBT tag type: {}", type_id),
            )),
        }
    }

    fn read_root(&mut self) -> Result<(std::string::String, NbtTag), std::io::Error> {
        let type_id = self.read_ubyte()?;
        if type_id != 10 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("Expected TAG_Compound (10) at root, got {}", type_id),
            ));
        }
        let name = self.read_string()?;
        let compound = self.read_compound()?;
        Ok((name, compound))
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Writer
// ─────────────────────────────────────────────────────────────────────────────

struct NbtWriter {
    buf: Vec<u8>,
}

impl NbtWriter {
    fn new() -> Self {
        Self { buf: Vec::new() }
    }

    fn write_byte(&mut self, v: i8) {
        self.buf.push(v as u8);
    }
    fn write_ubyte(&mut self, v: u8) {
        self.buf.push(v);
    }

    fn write_short(&mut self, v: i16) {
        self.buf.extend_from_slice(&v.to_be_bytes());
    }
    fn write_int(&mut self, v: i32) {
        self.buf.extend_from_slice(&v.to_be_bytes());
    }
    fn write_long(&mut self, v: i64) {
        self.buf.extend_from_slice(&v.to_be_bytes());
    }
    fn write_float(&mut self, v: f32) {
        self.buf.extend_from_slice(&v.to_be_bytes());
    }
    fn write_double(&mut self, v: f64) {
        self.buf.extend_from_slice(&v.to_be_bytes());
    }

    fn write_string(&mut self, s: &str) {
        let encoded = s.as_bytes();
        self.write_short(encoded.len() as i16);
        self.buf.extend_from_slice(encoded);
    }

    fn write_byte_array(&mut self, arr: &[i8]) {
        self.write_int(arr.len() as i32);
        for &b in arr {
            self.buf.push(b as u8);
        }
    }

    fn write_int_array(&mut self, arr: &[i32]) {
        self.write_int(arr.len() as i32);
        for &v in arr {
            self.write_int(v);
        }
    }

    fn write_long_array(&mut self, arr: &[i64]) {
        self.write_int(arr.len() as i32);
        for &v in arr {
            self.write_long(v);
        }
    }

    fn write_tag_with_header(&mut self, name: &str, tag: &NbtTag) {
        self.write_ubyte(tag.tag_type_id());
        self.write_string(name);
        self.write_payload(tag);
    }

    fn write_payload(&mut self, tag: &NbtTag) {
        match tag {
            NbtTag::End => {}
            NbtTag::Byte(v) => self.write_byte(*v),
            NbtTag::Short(v) => self.write_short(*v),
            NbtTag::Int(v) => self.write_int(*v),
            NbtTag::Long(v) => self.write_long(*v),
            NbtTag::Float(v) => self.write_float(*v),
            NbtTag::Double(v) => self.write_double(*v),
            NbtTag::ByteArray(v) => self.write_byte_array(v),
            NbtTag::String(s) => self.write_string(s),
            NbtTag::List(type_id, items) => {
                self.write_ubyte(*type_id);
                self.write_int(items.len() as i32);
                for item in items {
                    self.write_payload(item);
                }
            }
            NbtTag::Compound(entries) => {
                for (name, tag) in entries {
                    self.write_tag_with_header(name, tag);
                }
                self.write_ubyte(0); // TAG_End
            }
            NbtTag::IntArray(v) => self.write_int_array(v),
            NbtTag::LongArray(v) => self.write_long_array(v),
        }
    }

    fn write_root(&mut self, name: &str, compound: &NbtTag) {
        self.write_ubyte(10); // TAG_Compound
        self.write_string(name);
        self.write_payload(compound);
    }

    fn finish(self) -> Vec<u8> {
        self.buf
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Python ↔ Rust conversion helpers
// ─────────────────────────────────────────────────────────────────────────────

fn nbt_tag_to_py(py: Python<'_>, tag: &NbtTag) -> PyResult<Py<PyAny>> {
    match tag {
        NbtTag::End => PyTagEnd::new(py),
        NbtTag::Byte(v) => Ok(Py::new(
            py,
            PyTagByte {
                value: *v as i64,
                name: None,
            },
        )?
        .into_any()),
        NbtTag::Short(v) => Ok(Py::new(
            py,
            PyTagShort {
                value: *v as i64,
                name: None,
            },
        )?
        .into_any()),
        NbtTag::Int(v) => Ok(Py::new(
            py,
            PyTagInt {
                value: *v as i64,
                name: None,
            },
        )?
        .into_any()),
        NbtTag::Long(v) => Ok(Py::new(
            py,
            PyTagLong {
                value: *v,
                name: None,
            },
        )?
        .into_any()),
        NbtTag::Float(v) => Ok(Py::new(
            py,
            PyTagFloat {
                value: *v as f64,
                name: None,
            },
        )?
        .into_any()),
        NbtTag::Double(v) => Ok(Py::new(
            py,
            PyTagDouble {
                value: *v,
                name: None,
            },
        )?
        .into_any()),
        NbtTag::ByteArray(v) => Ok(Py::new(
            py,
            PyTagByteArray {
                value: v.iter().map(|&b| b as i64).collect(),
                name: None,
            },
        )?
        .into_any()),
        NbtTag::String(s) => Ok(Py::new(
            py,
            PyTagString {
                value: s.clone(),
                name: None,
            },
        )?
        .into_any()),
        NbtTag::List(type_id, items) => {
            let mut py_items = Vec::with_capacity(items.len());
            for item in items {
                py_items.push(nbt_tag_to_py(py, item)?);
            }
            Ok(Py::new(
                py,
                PyTagList {
                    tag_type: *type_id as i64,
                    value: py_items,
                    name: None,
                },
            )?
            .into_any())
        }
        NbtTag::Compound(entries) => {
            let mut py_entries: Vec<(std::string::String, Py<PyAny>)> =
                Vec::with_capacity(entries.len());
            for (k, v) in entries {
                let py_tag = nbt_tag_to_py(py, v)?;
                py_entries.push((k.clone(), py_tag));
            }
            Ok(Py::new(
                py,
                PyTagCompound {
                    value: py_entries,
                    name: None,
                },
            )?
            .into_any())
        }
        NbtTag::IntArray(v) => Ok(Py::new(
            py,
            PyTagIntArray {
                value: v.iter().map(|&x| x as i64).collect(),
                name: None,
            },
        )?
        .into_any()),
        NbtTag::LongArray(v) => Ok(Py::new(
            py,
            PyTagLongArray {
                value: v.clone(),
                name: None,
            },
        )?
        .into_any()),
    }
}

fn py_to_nbt_tag(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<NbtTag> {
    if let Ok(tag) = obj.extract::<PyRef<PyTagEnd>>() {
        let _ = tag;
        return Ok(NbtTag::End);
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagByte>>() {
        return Ok(NbtTag::Byte(tag.value as i8));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagShort>>() {
        return Ok(NbtTag::Short(tag.value as i16));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagInt>>() {
        return Ok(NbtTag::Int(tag.value as i32));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagLong>>() {
        return Ok(NbtTag::Long(tag.value));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagFloat>>() {
        return Ok(NbtTag::Float(tag.value as f32));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagDouble>>() {
        return Ok(NbtTag::Double(tag.value));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagByteArray>>() {
        return Ok(NbtTag::ByteArray(
            tag.value.iter().map(|&v| v as i8).collect(),
        ));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagString>>() {
        return Ok(NbtTag::String(tag.value.clone()));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagList>>() {
        let mut items = Vec::with_capacity(tag.value.len());
        for py_item in &tag.value {
            items.push(py_to_nbt_tag(py, py_item.bind(py))?);
        }
        return Ok(NbtTag::List(tag.tag_type as u8, items));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagCompound>>() {
        let mut entries = Vec::with_capacity(tag.value.len());
        for (k, v) in &tag.value {
            entries.push((k.clone(), py_to_nbt_tag(py, v.bind(py))?));
        }
        return Ok(NbtTag::Compound(entries));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagIntArray>>() {
        return Ok(NbtTag::IntArray(
            tag.value.iter().map(|&v| v as i32).collect(),
        ));
    }
    if let Ok(tag) = obj.extract::<PyRef<PyTagLongArray>>() {
        return Ok(NbtTag::LongArray(tag.value.clone()));
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "Expected an NBT tag, got {:?}",
        obj.get_type().name()
    )))
}

/// Convert a Python dict/value recursively to an NbtTag.
pub fn py_value_to_nbt(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<NbtTag> {
    // Already an NBT tag?
    if let Ok(tag) = py_to_nbt_tag(py, obj) {
        return Ok(tag);
    }

    // bool check before int (bool is subclass of int in Python)
    if let Ok(b) = obj.cast::<PyBool>() {
        return Ok(NbtTag::Byte(if b.is_true() { 1 } else { 0 }));
    }

    if let Ok(v) = obj.extract::<i64>() {
        if v >= i8::MIN as i64 && v <= i8::MAX as i64 {
            return Ok(NbtTag::Byte(v as i8));
        } else if v >= i16::MIN as i64 && v <= i16::MAX as i64 {
            return Ok(NbtTag::Short(v as i16));
        } else if v >= i32::MIN as i64 && v <= i32::MAX as i64 {
            return Ok(NbtTag::Int(v as i32));
        } else {
            return Ok(NbtTag::Long(v));
        }
    }

    if let Ok(v) = obj.extract::<f64>() {
        return Ok(NbtTag::Double(v));
    }

    if let Ok(s) = obj.extract::<std::string::String>() {
        return Ok(NbtTag::String(s));
    }

    if let Ok(list) = obj.cast::<PyList>() {
        if list.is_empty() {
            return Ok(NbtTag::List(0, vec![]));
        }
        // Peek at the first element to decide encoding
        let first = list.get_item(0)?;
        if first.extract::<bool>().is_ok() || first.extract::<i64>().is_ok() {
            // Try int arrays
            let ints: PyResult<Vec<i64>> = list.iter().map(|item| item.extract::<i64>()).collect();
            if let Ok(ints) = ints {
                if ints
                    .iter()
                    .all(|&v| v >= i8::MIN as i64 && v <= i8::MAX as i64)
                {
                    return Ok(NbtTag::ByteArray(
                        ints.into_iter().map(|v| v as i8).collect(),
                    ));
                } else if ints
                    .iter()
                    .all(|&v| v >= i32::MIN as i64 && v <= i32::MAX as i64)
                {
                    return Ok(NbtTag::IntArray(
                        ints.into_iter().map(|v| v as i32).collect(),
                    ));
                } else {
                    return Ok(NbtTag::LongArray(ints));
                }
            }
        }
        // Generic list — convert each element
        let mut items = Vec::with_capacity(list.len());
        for item in list.iter() {
            items.push(py_value_to_nbt(py, &item)?);
        }
        let type_id = items.first().map(|t| t.tag_type_id()).unwrap_or(0);
        return Ok(NbtTag::List(type_id, items));
    }

    if let Ok(dict) = obj.cast::<PyDict>() {
        let mut entries = Vec::with_capacity(dict.len());
        for (k, v) in dict.iter() {
            let key: std::string::String = k.extract()?;
            let tag = py_value_to_nbt(py, &v)?;
            entries.push((key, tag));
        }
        return Ok(NbtTag::Compound(entries));
    }

    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "Unsupported type for NBT: {}",
        obj.get_type()
            .name()
            .map(|s| s.to_string())
            .unwrap_or_else(|_| "unknown".to_string())
    )))
}

fn nbt_tag_to_py_value(py: Python<'_>, tag: &NbtTag) -> PyResult<Py<PyAny>> {
    match tag {
        NbtTag::Byte(v) => Ok((*v as i64).into_pyobject(py)?.into()),
        NbtTag::Short(v) => Ok((*v as i64).into_pyobject(py)?.into()),
        NbtTag::Int(v) => Ok((*v as i64).into_pyobject(py)?.into()),
        NbtTag::Long(v) => Ok((*v).into_pyobject(py)?.into()),
        NbtTag::Float(v) => Ok((*v as f64).into_pyobject(py)?.into()),
        NbtTag::Double(v) => Ok((*v).into_pyobject(py)?.into()),
        NbtTag::String(s) => Ok(s.as_str().into_pyobject(py)?.into()),
        NbtTag::ByteArray(v) => {
            let list: Vec<i64> = v.iter().map(|&b| b as i64).collect();
            Ok(list.into_pyobject(py)?.into())
        }
        NbtTag::IntArray(v) => {
            let list: Vec<i64> = v.iter().map(|&x| x as i64).collect();
            Ok(list.into_pyobject(py)?.into())
        }
        NbtTag::LongArray(v) => Ok(v.clone().into_pyobject(py)?.into()),
        NbtTag::List(_, items) => {
            let py_list = PyList::empty(py);
            for item in items {
                py_list.append(nbt_tag_to_py_value(py, item)?)?;
            }
            Ok(py_list.into())
        }
        NbtTag::Compound(entries) => {
            let dict = PyDict::new(py);
            for (k, v) in entries {
                dict.set_item(k.as_str(), nbt_tag_to_py_value(py, v)?)?;
            }
            Ok(dict.into())
        }
        NbtTag::End => Ok(py.None()),
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Public Rust parsing / serialization helpers (used by gamestate)
// ─────────────────────────────────────────────────────────────────────────────

#[allow(dead_code)]
pub fn parse_nbt_from_slice(data: &[u8]) -> Result<NbtTag, std::io::Error> {
    // Detect gzip/zlib
    let owned;
    let slice: &[u8] = if data.starts_with(&[0x1f, 0x8b]) {
        owned = decompress_gzip(data)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        &owned
    } else if data.starts_with(&[0x78, 0x9c])
        || data.starts_with(&[0x78, 0x01])
        || data.starts_with(&[0x78, 0xda])
    {
        owned = decompress_zlib(data)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        &owned
    } else {
        data
    };

    let mut reader = NbtReader::new(slice);
    let (_name, compound) = reader.read_root()?;
    Ok(compound)
}

pub fn serialize_nbt_to_vec(name: &str, compound: &NbtTag) -> Vec<u8> {
    let mut writer = NbtWriter::new();
    writer.write_root(name, compound);
    writer.finish()
}

fn decompress_gzip(data: &[u8]) -> Result<Vec<u8>, std::string::String> {
    use std::io::Read;
    let mut decoder = flate2::read::GzDecoder::new(data);
    let mut out = Vec::new();
    decoder.read_to_end(&mut out).map_err(|e| e.to_string())?;
    Ok(out)
}

fn decompress_zlib(data: &[u8]) -> Result<Vec<u8>, std::string::String> {
    use std::io::Read;
    let mut decoder = flate2::read::ZlibDecoder::new(data);
    let mut out = Vec::new();
    decoder.read_to_end(&mut out).map_err(|e| e.to_string())?;
    Ok(out)
}

// ─────────────────────────────────────────────────────────────────────────────
// Python pyclass wrappers — mirrors petty.nbt Python classes
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "TagEnd")]
pub struct PyTagEnd {
    #[pyo3(get, set)]
    pub name: Option<std::string::String>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyTagEnd {
    #[new]
    pub fn __new__() -> Self {
        Self { name: None }
    }
    fn __repr__(&self) -> std::string::String {
        "TagEnd(None: None)".to_string()
    }
}

impl PyTagEnd {
    #[allow(clippy::new_ret_no_self)]
    pub fn new(py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(Py::new(py, PyTagEnd { name: None })?.into_any())
    }
}

macro_rules! simple_tag {
    ($cls:ident, $pyname:literal, $field:ty, $default:expr) => {
        #[gen_stub_pyclass]
        #[pyclass(name = $pyname)]
        pub struct $cls {
            #[pyo3(get, set)]
            pub name: Option<std::string::String>,
            #[pyo3(get, set)]
            pub value: $field,
        }

        #[gen_stub_pymethods]
        #[pymethods]
        impl $cls {
            #[new]
            #[pyo3(signature = (name=None, value=$default))]
            fn __new__(name: Option<std::string::String>, value: $field) -> Self {
                Self { name, value }
            }
            fn __repr__(&self) -> std::string::String {
                format!("{}({:?}: {:?})", $pyname, self.name, self.value)
            }
        }
    };
}

simple_tag!(PyTagByte, "TagByte", i64, 0);
simple_tag!(PyTagShort, "TagShort", i64, 0);
simple_tag!(PyTagInt, "TagInt", i64, 0);
simple_tag!(PyTagLong, "TagLong", i64, 0);
simple_tag!(PyTagFloat, "TagFloat", f64, 0.0);
simple_tag!(PyTagDouble, "TagDouble", f64, 0.0);
simple_tag!(
    PyTagString,
    "TagString",
    std::string::String,
    std::string::String::new()
);

#[gen_stub_pyclass]
#[pyclass(name = "TagByteArray")]
pub struct PyTagByteArray {
    #[pyo3(get, set)]
    pub name: Option<std::string::String>,
    #[pyo3(get, set)]
    pub value: Vec<i64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyTagByteArray {
    #[new]
    #[pyo3(signature = (name=None, value=None))]
    fn __new__(name: Option<std::string::String>, value: Option<Vec<i64>>) -> Self {
        Self {
            name,
            value: value.unwrap_or_default(),
        }
    }
    fn __repr__(&self) -> std::string::String {
        format!("TagByteArray({:?}: {} bytes)", self.name, self.value.len())
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "TagIntArray")]
pub struct PyTagIntArray {
    #[pyo3(get, set)]
    pub name: Option<std::string::String>,
    #[pyo3(get, set)]
    pub value: Vec<i64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyTagIntArray {
    #[new]
    #[pyo3(signature = (name=None, value=None))]
    fn __new__(name: Option<std::string::String>, value: Option<Vec<i64>>) -> Self {
        Self {
            name,
            value: value.unwrap_or_default(),
        }
    }
    fn __repr__(&self) -> std::string::String {
        format!("TagIntArray({:?}: {} ints)", self.name, self.value.len())
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "TagLongArray")]
pub struct PyTagLongArray {
    #[pyo3(get, set)]
    pub name: Option<std::string::String>,
    #[pyo3(get, set)]
    pub value: Vec<i64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyTagLongArray {
    #[new]
    #[pyo3(signature = (name=None, value=None))]
    fn __new__(name: Option<std::string::String>, value: Option<Vec<i64>>) -> Self {
        Self {
            name,
            value: value.unwrap_or_default(),
        }
    }
    fn __repr__(&self) -> std::string::String {
        format!("TagLongArray({:?}: {} longs)", self.name, self.value.len())
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "TagList")]
pub struct PyTagList {
    #[pyo3(get, set)]
    pub name: Option<std::string::String>,
    #[pyo3(get, set)]
    pub tag_type: i64,
    #[pyo3(get, set)]
    pub value: Vec<Py<PyAny>>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyTagList {
    #[new]
    #[pyo3(signature = (name=None, tag_type=0, value=None))]
    fn __new__(
        name: Option<std::string::String>,
        tag_type: i64,
        value: Option<Vec<Py<PyAny>>>,
    ) -> Self {
        Self {
            name,
            tag_type,
            value: value.unwrap_or_default(),
        }
    }

    fn append(&mut self, py: Python<'_>, tag: Py<PyAny>) {
        if self.value.is_empty() {
            // Auto-detect type from tag class
            // We use tag_type_id from the class name
            if let Ok(bound) = tag.bind(py).extract::<PyRef<PyTagByte>>() {
                let _ = bound;
                self.tag_type = 1;
            } else if let Ok(b) = tag.bind(py).extract::<PyRef<PyTagShort>>() {
                let _ = b;
                self.tag_type = 2;
            } else if let Ok(b) = tag.bind(py).extract::<PyRef<PyTagInt>>() {
                let _ = b;
                self.tag_type = 3;
            } else if let Ok(b) = tag.bind(py).extract::<PyRef<PyTagLong>>() {
                let _ = b;
                self.tag_type = 4;
            } else if let Ok(b) = tag.bind(py).extract::<PyRef<PyTagCompound>>() {
                let _ = b;
                self.tag_type = 10;
            }
        }
        self.value.push(tag);
    }

    fn __repr__(&self) -> std::string::String {
        format!(
            "TagList({:?}, type={}, {} entries)",
            self.name,
            self.tag_type,
            self.value.len()
        )
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "TagCompound")]
pub struct PyTagCompound {
    #[pyo3(get, set)]
    pub name: Option<std::string::String>,
    /// Ordered (key, tag_object) pairs — preserves insertion order like Python dict
    pub value: Vec<(std::string::String, Py<PyAny>)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyTagCompound {
    #[new]
    #[pyo3(signature = (name=None, value=None))]
    fn __new__(
        _py: Python<'_>,
        name: Option<std::string::String>,
        value: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let mut entries = Vec::new();
        if let Some(d) = value {
            for (k, v) in d.iter() {
                entries.push((k.extract::<std::string::String>()?, v.into()));
            }
        }
        Ok(Self {
            name,
            value: entries,
        })
    }

    fn __getitem__(&self, py: Python<'_>, key: &str) -> PyResult<Py<PyAny>> {
        for (k, v) in &self.value {
            if k == key {
                return Ok(v.clone_ref(py));
            }
        }
        Err(pyo3::exceptions::PyKeyError::new_err(key.to_string()))
    }

    fn __setitem__(&mut self, key: std::string::String, value: Py<PyAny>) {
        for (k, v) in &mut self.value {
            if k == &key {
                *v = value;
                return;
            }
        }
        self.value.push((key, value));
    }

    fn __contains__(&self, key: &str) -> bool {
        self.value.iter().any(|(k, _)| k == key)
    }

    fn __len__(&self) -> usize {
        self.value.len()
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, py: Python<'_>, key: &str, default: Option<Py<PyAny>>) -> Py<PyAny> {
        for (k, v) in &self.value {
            if k == key {
                return v.clone_ref(py);
            }
        }
        default.unwrap_or_else(|| py.None())
    }

    fn keys(&self, py: Python<'_>) -> Py<PyAny> {
        let list: Vec<&str> = self.value.iter().map(|(k, _)| k.as_str()).collect();
        list.into_pyobject(py).unwrap().into()
    }

    fn values(&self, py: Python<'_>) -> Py<PyAny> {
        let list: Vec<Py<PyAny>> = self.value.iter().map(|(_, v)| v.clone_ref(py)).collect();
        list.into_pyobject(py).unwrap().into()
    }

    fn items(&self, py: Python<'_>) -> Py<PyAny> {
        let list: Vec<(&str, Py<PyAny>)> = self
            .value
            .iter()
            .map(|(k, v)| (k.as_str(), v.clone_ref(py)))
            .collect();
        list.into_pyobject(py).unwrap().into()
    }

    fn __repr__(&self) -> std::string::String {
        format!("TagCompound({:?}, {} entries)", self.name, self.value.len())
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Python module functions: loads, dumps, from_dict, to_dict
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyfunction]
#[pyfunction(name = "loads")]
pub fn py_loads(py: Python<'_>, data: PyBackedBytes) -> PyResult<PyTagCompound> {
    // Detect compression
    let owned;
    let slice: &[u8] = if data.starts_with(&[0x1f, 0x8b]) {
        owned = decompress_gzip(&data).map_err(pyo3::exceptions::PyValueError::new_err)?;
        &owned
    } else if data.starts_with(&[0x78, 0x9c])
        || data.starts_with(&[0x78, 0x01])
        || data.starts_with(&[0x78, 0xda])
    {
        owned = decompress_zlib(&data).map_err(pyo3::exceptions::PyValueError::new_err)?;
        &owned
    } else {
        &data
    };

    let mut reader = NbtReader::new(slice);
    let (name, compound) = reader
        .read_root()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    // Convert compound entries to Python
    let entries = if let NbtTag::Compound(entries) = compound {
        entries
    } else {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Expected compound tag at root",
        ));
    };

    let mut py_entries = Vec::with_capacity(entries.len());
    for (k, v) in entries {
        py_entries.push((k, nbt_tag_to_py(py, &v)?));
    }
    Ok(PyTagCompound {
        name: Some(name),
        value: py_entries,
    })
}

#[gen_stub_pyfunction]
#[pyfunction(name = "dumps")]
#[pyo3(signature = (tag, compression=None, _little_endian=false))]
pub fn py_dumps(
    py: Python<'_>,
    tag: &Bound<'_, PyAny>,
    compression: Option<&str>,
    _little_endian: bool,
) -> PyResult<Py<PyAny>> {
    let compound_ref = tag.extract::<PyRef<PyTagCompound>>()?;
    let name = compound_ref.name.clone().unwrap_or_default();

    // Rebuild NbtTag::Compound from the Python PyTagCompound
    let mut entries = Vec::with_capacity(compound_ref.value.len());
    for (k, v) in &compound_ref.value {
        entries.push((k.clone(), py_to_nbt_tag(py, v.bind(py))?));
    }
    drop(compound_ref);

    let nbt_compound = NbtTag::Compound(entries);
    let raw = serialize_nbt_to_vec(&name, &nbt_compound);

    let out_bytes = match compression {
        Some("gzip") => {
            use std::io::Write;
            let mut encoder =
                flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
            encoder
                .write_all(&raw)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
            encoder
                .finish()
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?
        }
        Some("zlib") => {
            use std::io::Write;
            let mut encoder =
                flate2::write::ZlibEncoder::new(Vec::new(), flate2::Compression::default());
            encoder
                .write_all(&raw)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
            encoder
                .finish()
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?
        }
        None => raw,
        Some(other) => {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown compression: {}",
                other
            )));
        }
    };

    Ok(PyBytes::new(py, &out_bytes).into())
}

#[gen_stub_pyfunction]
#[pyfunction(name = "from_dict")]
#[pyo3(signature = (data, name=""))]
pub fn py_from_dict(
    py: Python<'_>,
    data: &Bound<'_, PyDict>,
    name: &str,
) -> PyResult<PyTagCompound> {
    let mut entries = Vec::with_capacity(data.len());
    for (k, v) in data.iter() {
        let key: std::string::String = k.extract()?;
        let tag = py_value_to_nbt(py, &v)?;
        entries.push((key.clone(), nbt_tag_to_py(py, &tag)?));
    }
    Ok(PyTagCompound {
        name: Some(name.to_string()),
        value: entries,
    })
}

#[gen_stub_pyfunction]
#[pyfunction(name = "to_dict")]
pub fn py_to_dict(py: Python<'_>, tag: &Bound<'_, PyTagCompound>) -> PyResult<Py<PyAny>> {
    let tag_ref = tag.borrow();
    let dict = PyDict::new(py);
    for (k, v) in &tag_ref.value {
        let rust_tag = py_to_nbt_tag(py, v.bind(py))?;
        dict.set_item(k.as_str(), nbt_tag_to_py_value(py, &rust_tag)?)?;
    }
    Ok(dict.into())
}

// ─────────────────────────────────────────────────────────────────────────────
// Public reader for slot.rs to determine exact NBT size without allocation
// ─────────────────────────────────────────────────────────────────────────────

pub struct NbtReaderPub<'a> {
    inner: NbtReader<'a>,
}

impl<'a> NbtReaderPub<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Self {
            inner: NbtReader::new(data),
        }
    }

    /// Read the root compound tag and return the total number of bytes consumed.
    pub fn read_root_size(&mut self) -> Result<usize, std::io::Error> {
        let _root = self.inner.read_root()?;
        Ok(self.inner.cur.position() as usize)
    }
}

#[gen_stub_pyfunction]
#[pyfunction(name = "read_nbt_size")]
pub fn py_read_nbt_size(_py: Python<'_>, data: PyBackedBytes) -> PyResult<usize> {
    let mut reader = NbtReaderPub::new(&data);
    reader
        .read_root_size()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("NBT parse error: {}", e)))
}
