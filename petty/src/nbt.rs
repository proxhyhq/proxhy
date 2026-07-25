//! Minecraft NBT binary format — reader, writer, and convenience functions.

use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};
use std::io::{Cursor, Read};

// ── Exceptions ────────────────────────────────────────────────────────────────
// Using create_exception! to define Python exception subclasses.
// These are NOT #[pyclass]; they are registered in lib.rs via py.get_type().

pyo3::create_exception!(_petty, NBTError, PyException);
pyo3::create_exception!(_petty, NBTParseError, NBTError);
pyo3::create_exception!(_petty, NBTWriteError, NBTError);

// ── Tag type constants ────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "TagType", skip_from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TagType {
    #[pyo3(get)]
    pub value: u8,
}

impl TagType {
    pub const TAG_END: u8 = 0;
    pub const TAG_BYTE: u8 = 1;
    pub const TAG_SHORT: u8 = 2;
    pub const TAG_INT: u8 = 3;
    pub const TAG_LONG: u8 = 4;
    pub const TAG_FLOAT: u8 = 5;
    pub const TAG_DOUBLE: u8 = 6;
    pub const TAG_BYTE_ARRAY: u8 = 7;
    pub const TAG_STRING: u8 = 8;
    pub const TAG_LIST: u8 = 9;
    pub const TAG_COMPOUND: u8 = 10;
    pub const TAG_INT_ARRAY: u8 = 11;
    pub const TAG_LONG_ARRAY: u8 = 12;
}

#[gen_stub_pymethods]
#[pymethods]
impl TagType {
    #[new]
    pub fn new(value: u8) -> Self {
        TagType { value }
    }
    fn __repr__(&self) -> String {
        format!("TagType({})", self.value)
    }
}

// ── Internal NbtValue ─────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
enum NbtValue {
    End,
    Byte(i8),
    Short(i16),
    Int(i32),
    Long(i64),
    Float(f32),
    Double(f64),
    ByteArray(Vec<i8>),
    Str(String),
    List { tag_type: u8, items: Vec<NbtValue> },
    Compound(Vec<(String, NbtValue)>),
    IntArray(Vec<i32>),
    LongArray(Vec<i64>),
}

impl NbtValue {
    fn type_id(&self) -> u8 {
        match self {
            NbtValue::End => 0,
            NbtValue::Byte(_) => 1,
            NbtValue::Short(_) => 2,
            NbtValue::Int(_) => 3,
            NbtValue::Long(_) => 4,
            NbtValue::Float(_) => 5,
            NbtValue::Double(_) => 6,
            NbtValue::ByteArray(_) => 7,
            NbtValue::Str(_) => 8,
            NbtValue::List { .. } => 9,
            NbtValue::Compound(_) => 10,
            NbtValue::IntArray(_) => 11,
            NbtValue::LongArray(_) => 12,
        }
    }
}

// ── Reader ────────────────────────────────────────────────────────────────────

struct Reader<'a> {
    cur: Cursor<&'a [u8]>,
    le: bool,
}

impl<'a> Reader<'a> {
    fn new(data: &'a [u8], le: bool) -> Self {
        Reader {
            cur: Cursor::new(data),
            le,
        }
    }
    fn pos(&self) -> u64 {
        self.cur.position()
    }

    fn read_n(&mut self, n: usize) -> Result<Vec<u8>, String> {
        let mut buf = vec![0u8; n];
        self.cur.read_exact(&mut buf).map_err(|e| e.to_string())?;
        Ok(buf)
    }

    fn i8(&mut self) -> Result<i8, String> {
        Ok(self.read_n(1)?[0] as i8)
    }
    fn u8(&mut self) -> Result<u8, String> {
        Ok(self.read_n(1)?[0])
    }

    fn i16(&mut self) -> Result<i16, String> {
        let b = self.read_n(2)?;
        Ok(if self.le {
            i16::from_le_bytes([b[0], b[1]])
        } else {
            i16::from_be_bytes([b[0], b[1]])
        })
    }
    fn i32(&mut self) -> Result<i32, String> {
        let b: [u8; 4] = self.read_n(4)?.try_into().unwrap();
        Ok(if self.le {
            i32::from_le_bytes(b)
        } else {
            i32::from_be_bytes(b)
        })
    }
    fn i64(&mut self) -> Result<i64, String> {
        let b: [u8; 8] = self.read_n(8)?.try_into().unwrap();
        Ok(if self.le {
            i64::from_le_bytes(b)
        } else {
            i64::from_be_bytes(b)
        })
    }
    fn f32(&mut self) -> Result<f32, String> {
        let b: [u8; 4] = self.read_n(4)?.try_into().unwrap();
        Ok(if self.le {
            f32::from_le_bytes(b)
        } else {
            f32::from_be_bytes(b)
        })
    }
    fn f64(&mut self) -> Result<f64, String> {
        let b: [u8; 8] = self.read_n(8)?.try_into().unwrap();
        Ok(if self.le {
            f64::from_le_bytes(b)
        } else {
            f64::from_be_bytes(b)
        })
    }

    fn string(&mut self) -> Result<String, String> {
        let len = self.i16()? as usize;
        let raw = self.read_n(len)?;
        String::from_utf8(raw).map_err(|e| e.to_string())
    }

    fn payload(&mut self, tag: u8) -> Result<NbtValue, String> {
        Ok(match tag {
            0 => NbtValue::End,
            1 => NbtValue::Byte(self.i8()?),
            2 => NbtValue::Short(self.i16()?),
            3 => NbtValue::Int(self.i32()?),
            4 => NbtValue::Long(self.i64()?),
            5 => NbtValue::Float(self.f32()?),
            6 => NbtValue::Double(self.f64()?),
            7 => {
                let n = self.i32()? as usize;
                NbtValue::ByteArray(self.read_n(n)?.into_iter().map(|b| b as i8).collect())
            }
            8 => NbtValue::Str(self.string()?),
            9 => {
                let item_tag = self.u8()?;
                let count = self.i32()? as usize;
                let items = (0..count)
                    .map(|_| self.payload(item_tag))
                    .collect::<Result<_, _>>()?;
                NbtValue::List {
                    tag_type: item_tag,
                    items,
                }
            }
            10 => {
                let mut entries = Vec::new();
                loop {
                    let t = self.u8()?;
                    if t == 0 {
                        break;
                    }
                    let name = self.string()?;
                    entries.push((name, self.payload(t)?));
                }
                NbtValue::Compound(entries)
            }
            11 => {
                let n = self.i32()? as usize;
                NbtValue::IntArray((0..n).map(|_| self.i32()).collect::<Result<_, _>>()?)
            }
            12 => {
                let n = self.i32()? as usize;
                NbtValue::LongArray((0..n).map(|_| self.i64()).collect::<Result<_, _>>()?)
            }
            t => return Err(format!("unknown tag {t}")),
        })
    }

    fn read_root(&mut self) -> Result<(String, NbtValue), String> {
        let t = self.u8()?;
        if t != 10 {
            return Err(format!("expected Compound at root, got {t}"));
        }
        let name = self.string()?;
        let val = self.payload(10)?;
        Ok((name, val))
    }
}

// ── Writer ────────────────────────────────────────────────────────────────────

struct Writer {
    buf: Vec<u8>,
    le: bool,
}

impl Writer {
    fn new(le: bool) -> Self {
        Writer {
            buf: Vec::new(),
            le,
        }
    }

    fn w_i8(&mut self, v: i8) {
        self.buf.push(v as u8);
    }
    fn w_i16(&mut self, v: i16) {
        if self.le {
            self.buf.extend_from_slice(&v.to_le_bytes());
        } else {
            self.buf.extend_from_slice(&v.to_be_bytes());
        }
    }
    fn w_i32(&mut self, v: i32) {
        if self.le {
            self.buf.extend_from_slice(&v.to_le_bytes());
        } else {
            self.buf.extend_from_slice(&v.to_be_bytes());
        }
    }
    fn w_i64(&mut self, v: i64) {
        if self.le {
            self.buf.extend_from_slice(&v.to_le_bytes());
        } else {
            self.buf.extend_from_slice(&v.to_be_bytes());
        }
    }
    fn w_f32(&mut self, v: f32) {
        if self.le {
            self.buf.extend_from_slice(&v.to_le_bytes());
        } else {
            self.buf.extend_from_slice(&v.to_be_bytes());
        }
    }
    fn w_f64(&mut self, v: f64) {
        if self.le {
            self.buf.extend_from_slice(&v.to_le_bytes());
        } else {
            self.buf.extend_from_slice(&v.to_be_bytes());
        }
    }

    fn w_str(&mut self, s: &str) {
        let b = s.as_bytes();
        self.w_i16(b.len() as i16);
        self.buf.extend_from_slice(b);
    }

    fn w_tag(&mut self, val: &NbtValue, with_header: bool, name: &str) -> Result<(), String> {
        if with_header && !matches!(val, NbtValue::End) {
            self.buf.push(val.type_id());
            self.w_str(name);
        }
        match val {
            NbtValue::End => {}
            NbtValue::Byte(v) => self.w_i8(*v),
            NbtValue::Short(v) => self.w_i16(*v),
            NbtValue::Int(v) => self.w_i32(*v),
            NbtValue::Long(v) => self.w_i64(*v),
            NbtValue::Float(v) => self.w_f32(*v),
            NbtValue::Double(v) => self.w_f64(*v),
            NbtValue::ByteArray(v) => {
                self.w_i32(v.len() as i32);
                for b in v {
                    self.buf.push(*b as u8);
                }
            }
            NbtValue::Str(v) => self.w_str(v),
            NbtValue::List { tag_type, items } => {
                self.buf.push(*tag_type);
                self.w_i32(items.len() as i32);
                for item in items {
                    self.w_tag(item, false, "")?;
                }
            }
            NbtValue::Compound(entries) => {
                for (k, v) in entries {
                    self.w_tag(v, true, k)?;
                }
                self.buf.push(0); // TAG_End
            }
            NbtValue::IntArray(v) => {
                self.w_i32(v.len() as i32);
                for i in v {
                    self.w_i32(*i);
                }
            }
            NbtValue::LongArray(v) => {
                self.w_i32(v.len() as i32);
                for l in v {
                    self.w_i64(*l);
                }
            }
        }
        Ok(())
    }

    fn write_root(&mut self, name: &str, compound: &NbtValue) -> Result<(), String> {
        self.buf.push(10); // TAG_Compound
        self.w_str(name);
        self.w_tag(compound, false, "")
    }
}

// ── Python tag classes ────────────────────────────────────────────────────────

macro_rules! simple_tag {
    ($rust:ident, $py:literal, $vt:ty) => {
        #[gen_stub_pyclass]
        #[pyclass(name = $py, skip_from_py_object)]
        #[derive(Clone, Debug)]
        pub struct $rust {
            #[pyo3(get, set)]
            pub name: Option<String>,
            #[pyo3(get, set)]
            pub value: $vt,
        }
        #[gen_stub_pymethods]
        #[pymethods]
        impl $rust {
            #[new]
            #[pyo3(signature = (name=None, value=Default::default()))]
            pub fn new(name: Option<String>, value: $vt) -> Self {
                $rust { name, value }
            }
            fn __repr__(&self) -> String {
                format!("{}({:?}: {:?})", $py, self.name, self.value)
            }
        }
    };
}

simple_tag!(TagByte, "TagByte", i8);
simple_tag!(TagShort, "TagShort", i16);
simple_tag!(TagInt, "TagInt", i32);
simple_tag!(TagLong, "TagLong", i64);
simple_tag!(TagFloat, "TagFloat", f32);
simple_tag!(TagDouble, "TagDouble", f64);
simple_tag!(TagString, "TagString", String);
simple_tag!(TagByteArray, "TagByteArray", Vec<i8>);
simple_tag!(TagIntArray, "TagIntArray", Vec<i32>);
simple_tag!(TagLongArray, "TagLongArray", Vec<i64>);

#[gen_stub_pyclass]
#[pyclass(name = "TagEnd", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct TagEnd;

#[gen_stub_pymethods]
#[pymethods]
impl TagEnd {
    #[new]
    pub fn new() -> Self {
        TagEnd
    }
    fn __repr__(&self) -> String {
        "TagEnd".to_owned()
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "TagList")]
#[derive(Debug)]
pub struct TagList {
    #[pyo3(get, set)]
    pub name: Option<String>,
    #[pyo3(get, set)]
    pub tag_type: u8,
    pub value: Vec<Py<PyAny>>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TagList {
    #[new]
    #[pyo3(signature = (name=None, tag_type=0, value=None))]
    pub fn new(name: Option<String>, tag_type: u8, value: Option<Vec<Py<PyAny>>>) -> Self {
        TagList {
            name,
            tag_type,
            value: value.unwrap_or_default(),
        }
    }
    #[getter]
    fn value(&self, py: Python<'_>) -> Vec<Py<PyAny>> {
        self.value.iter().map(|v| v.clone_ref(py)).collect()
    }
    fn __repr__(&self) -> String {
        format!("TagList({:?}, {} entries)", self.name, self.value.len())
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "TagCompound")]
#[derive(Debug)]
pub struct TagCompound {
    #[pyo3(get, set)]
    pub name: Option<String>,
    pub(crate) inner: Vec<(String, Py<PyAny>)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TagCompound {
    #[new]
    #[pyo3(signature = (name=None, value=None))]
    pub fn new(
        _py: Python<'_>,
        name: Option<String>,
        value: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let mut inner = Vec::new();
        if let Some(d) = value {
            for (k, v) in d.iter() {
                inner.push((k.extract::<String>()?, v.unbind()));
            }
        }
        Ok(TagCompound { name, inner })
    }

    fn __getitem__(&self, py: Python<'_>, key: &str) -> PyResult<Py<PyAny>> {
        self.inner
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v.clone_ref(py))
            .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(key.to_owned()))
    }

    fn __setitem__(&mut self, key: String, value: Py<PyAny>) {
        if let Some(e) = self.inner.iter_mut().find(|(k, _)| *k == key) {
            e.1 = value;
        } else {
            self.inner.push((key, value));
        }
    }

    fn __contains__(&self, key: &str) -> bool {
        self.inner.iter().any(|(k, _)| k == key)
    }
    fn __len__(&self) -> usize {
        self.inner.len()
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, py: Python<'_>, key: &str, default: Option<Py<PyAny>>) -> PyResult<Py<PyAny>> {
        Ok(self
            .inner
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v.clone_ref(py))
            .or(default)
            .unwrap_or_else(|| py.None()))
    }

    fn keys(&self) -> Vec<String> {
        self.inner.iter().map(|(k, _)| k.clone()).collect()
    }
    fn values(&self, py: Python<'_>) -> Vec<Py<PyAny>> {
        self.inner.iter().map(|(_, v)| v.clone_ref(py)).collect()
    }
    fn items(&self, py: Python<'_>) -> Vec<(String, Py<PyAny>)> {
        self.inner
            .iter()
            .map(|(k, v)| (k.clone(), v.clone_ref(py)))
            .collect()
    }
    fn __repr__(&self) -> String {
        format!("TagCompound({:?}, {} entries)", self.name, self.inner.len())
    }
}

// ── NbtValue ↔ Python conversion ─────────────────────────────────────────────

fn nbt_to_py(py: Python<'_>, value: NbtValue, name: Option<String>) -> PyResult<Py<PyAny>> {
    Ok(match value {
        NbtValue::End => Py::new(py, TagEnd)?.into_any(),
        NbtValue::Byte(v) => Py::new(py, TagByte { name, value: v })?.into_any(),
        NbtValue::Short(v) => Py::new(py, TagShort { name, value: v })?.into_any(),
        NbtValue::Int(v) => Py::new(py, TagInt { name, value: v })?.into_any(),
        NbtValue::Long(v) => Py::new(py, TagLong { name, value: v })?.into_any(),
        NbtValue::Float(v) => Py::new(py, TagFloat { name, value: v })?.into_any(),
        NbtValue::Double(v) => Py::new(py, TagDouble { name, value: v })?.into_any(),
        NbtValue::ByteArray(v) => Py::new(py, TagByteArray { name, value: v })?.into_any(),
        NbtValue::Str(v) => Py::new(py, TagString { name, value: v })?.into_any(),
        NbtValue::IntArray(v) => Py::new(py, TagIntArray { name, value: v })?.into_any(),
        NbtValue::LongArray(v) => Py::new(py, TagLongArray { name, value: v })?.into_any(),
        NbtValue::List { tag_type, items } => {
            let py_items = items
                .into_iter()
                .map(|i| nbt_to_py(py, i, None))
                .collect::<PyResult<_>>()?;
            Py::new(
                py,
                TagList {
                    name,
                    tag_type,
                    value: py_items,
                },
            )?
            .into_any()
        }
        NbtValue::Compound(entries) => {
            let inner = entries
                .into_iter()
                .map(|(k, v)| Ok((k.clone(), nbt_to_py(py, v, Some(k))?)))
                .collect::<PyResult<_>>()?;
            Py::new(py, TagCompound { name, inner })?.into_any()
        }
    })
}

fn py_to_nbt(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<(String, NbtValue)> {
    macro_rules! try_tag {
        ($t:ty, $var:ident) => {
            if let Ok(t) = obj.extract::<PyRef<$t>>() {
                return Ok((
                    t.name.clone().unwrap_or_default(),
                    NbtValue::$var(t.value.clone()),
                ));
            }
        };
    }
    try_tag!(TagByte, Byte);
    try_tag!(TagShort, Short);
    try_tag!(TagInt, Int);
    try_tag!(TagLong, Long);
    try_tag!(TagFloat, Float);
    try_tag!(TagDouble, Double);
    try_tag!(TagByteArray, ByteArray);
    try_tag!(TagString, Str);
    try_tag!(TagIntArray, IntArray);
    try_tag!(TagLongArray, LongArray);

    if let Ok(t) = obj.extract::<PyRef<TagList>>() {
        let items = t
            .value
            .iter()
            .map(|v| py_to_nbt(py, v.bind(py)).map(|(_, val)| val))
            .collect::<PyResult<_>>()?;
        return Ok((
            t.name.clone().unwrap_or_default(),
            NbtValue::List {
                tag_type: t.tag_type,
                items,
            },
        ));
    }
    if let Ok(t) = obj.extract::<PyRef<TagCompound>>() {
        let entries = t
            .inner
            .iter()
            .map(|(k, v)| py_to_nbt(py, v.bind(py)).map(|(_, val)| (k.clone(), val)))
            .collect::<PyResult<_>>()?;
        return Ok((
            t.name.clone().unwrap_or_default(),
            NbtValue::Compound(entries),
        ));
    }
    Err(NBTWriteError::new_err(format!(
        "Unknown NBT tag: {}",
        obj.get_type().qualname()?
    )))
}

// ── NBTReader / NBTWriter ─────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "NBTReader")]
pub struct NBTReader {
    data: Vec<u8>,
    le: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl NBTReader {
    #[new]
    #[pyo3(signature = (data, little_endian=false))]
    pub fn new(data: Vec<u8>, little_endian: bool) -> Self {
        NBTReader {
            data,
            le: little_endian,
        }
    }

    pub fn read_root(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let mut r = Reader::new(&self.data, self.le);
        let (name, val) = r.read_root().map_err(NBTParseError::new_err)?;
        nbt_to_py(py, val, Some(name))
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "NBTWriter")]
pub struct NBTWriter {
    le: bool,
    buf: Vec<u8>,
}

#[gen_stub_pymethods]
#[pymethods]
impl NBTWriter {
    #[new]
    #[pyo3(signature = (little_endian=false))]
    pub fn new(little_endian: bool) -> Self {
        NBTWriter {
            le: little_endian,
            buf: Vec::new(),
        }
    }

    pub fn write_root(&mut self, py: Python<'_>, tag: &Bound<'_, PyAny>) -> PyResult<()> {
        let (name, compound) = py_to_nbt(py, tag)?;
        let mut w = Writer::new(self.le);
        w.write_root(&name, &compound)
            .map_err(NBTWriteError::new_err)?;
        self.buf = w.buf;
        Ok(())
    }

    pub fn get_data(&self, py: Python<'_>) -> Py<PyBytes> {
        PyBytes::new(py, &self.buf).unbind()
    }
}

// ── Module-level functions ────────────────────────────────────────────────────

fn decompress(data: &[u8]) -> Vec<u8> {
    use std::io::Read;
    if data.starts_with(&[0x1f, 0x8b]) {
        let mut dec = flate2::read::GzDecoder::new(data);
        let mut out = Vec::new();
        if dec.read_to_end(&mut out).is_ok() {
            return out;
        }
    }
    if data.starts_with(&[0x78]) {
        let mut dec = flate2::read::ZlibDecoder::new(data);
        let mut out = Vec::new();
        if dec.read_to_end(&mut out).is_ok() {
            return out;
        }
    }
    data.to_vec()
}

fn compress(data: &[u8], method: Option<&str>) -> Result<Vec<u8>, String> {
    use std::io::Write;
    match method {
        None => Ok(data.to_vec()),
        Some("gzip") => {
            let mut enc = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
            enc.write_all(data).map_err(|e| e.to_string())?;
            enc.finish().map_err(|e| e.to_string())
        }
        Some("zlib") => {
            let mut enc =
                flate2::write::ZlibEncoder::new(Vec::new(), flate2::Compression::default());
            enc.write_all(data).map_err(|e| e.to_string())?;
            enc.finish().map_err(|e| e.to_string())
        }
        Some(o) => Err(format!("Unknown compression: {o}")),
    }
}

#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (file_path, little_endian=false))]
pub fn load(py: Python<'_>, file_path: &str, little_endian: bool) -> PyResult<Py<PyAny>> {
    let data = std::fs::read(file_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    loads(py, data, little_endian)
}

#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (data, little_endian=false))]
pub fn loads(py: Python<'_>, data: Vec<u8>, little_endian: bool) -> PyResult<Py<PyAny>> {
    let decompressed = decompress(&data);
    let mut r = Reader::new(&decompressed, little_endian);
    let (name, val) = r.read_root().map_err(NBTParseError::new_err)?;
    nbt_to_py(py, val, Some(name))
}

#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (tag, file_path, compression=None, little_endian=false))]
pub fn dump(
    py: Python<'_>,
    tag: &Bound<'_, PyAny>,
    file_path: &str,
    compression: Option<&str>,
    little_endian: bool,
) -> PyResult<()> {
    let data = dumps(py, tag, compression, little_endian)?;
    std::fs::write(file_path, data.bind(py).as_bytes())
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
}

#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (tag, compression=None, little_endian=false))]
pub fn dumps(
    py: Python<'_>,
    tag: &Bound<'_, PyAny>,
    compression: Option<&str>,
    little_endian: bool,
) -> PyResult<Py<PyBytes>> {
    let (name, compound) = py_to_nbt(py, tag)?;
    let mut w = Writer::new(little_endian);
    w.write_root(&name, &compound)
        .map_err(NBTWriteError::new_err)?;
    let out = compress(&w.buf, compression).map_err(NBTWriteError::new_err)?;
    Ok(PyBytes::new(py, &out).unbind())
}

#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (data, name=None))]
pub fn from_dict(
    py: Python<'_>,
    data: &Bound<'_, PyDict>,
    name: Option<&str>,
) -> PyResult<TagCompound> {
    let inner = dict_to_inner(py, data)?;
    Ok(TagCompound {
        name: name.map(str::to_owned),
        inner,
    })
}

fn dict_to_inner(py: Python<'_>, dict: &Bound<'_, PyDict>) -> PyResult<Vec<(String, Py<PyAny>)>> {
    let mut out = Vec::new();
    for (k, v) in dict.iter() {
        let key = k.extract::<String>()?;
        let tag = value_to_tag(py, &v, Some(&key))?;
        out.push((key, tag));
    }
    Ok(out)
}

fn value_to_tag(py: Python<'_>, val: &Bound<'_, PyAny>, name: Option<&str>) -> PyResult<Py<PyAny>> {
    if val.is_instance_of::<PyBool>() {
        let b: bool = val.extract()?;
        return Ok(Py::new(
            py,
            TagByte {
                name: name.map(str::to_owned),
                value: b as i8,
            },
        )?
        .into_any());
    }
    if val.is_instance_of::<PyInt>() {
        let i: i64 = val.extract()?;
        return Ok(if (-128..=127).contains(&i) {
            Py::new(
                py,
                TagByte {
                    name: name.map(str::to_owned),
                    value: i as i8,
                },
            )?
            .into_any()
        } else if (-32768..=32767).contains(&i) {
            Py::new(
                py,
                TagShort {
                    name: name.map(str::to_owned),
                    value: i as i16,
                },
            )?
            .into_any()
        } else if i >= i32::MIN as i64 && i <= i32::MAX as i64 {
            Py::new(
                py,
                TagInt {
                    name: name.map(str::to_owned),
                    value: i as i32,
                },
            )?
            .into_any()
        } else {
            Py::new(
                py,
                TagLong {
                    name: name.map(str::to_owned),
                    value: i,
                },
            )?
            .into_any()
        });
    }
    if val.is_instance_of::<PyFloat>() {
        let f: f64 = val.extract()?;
        return Ok(Py::new(
            py,
            TagDouble {
                name: name.map(str::to_owned),
                value: f,
            },
        )?
        .into_any());
    }
    if let Ok(s) = val.extract::<String>() {
        return Ok(Py::new(
            py,
            TagString {
                name: name.map(str::to_owned),
                value: s,
            },
        )?
        .into_any());
    }
    if let Ok(list) = val.cast::<PyList>() {
        return list_to_tag(py, list, name);
    }
    if let Ok(dict) = val.cast::<PyDict>() {
        let inner = dict_to_inner(py, dict)?;
        return Ok(Py::new(
            py,
            TagCompound {
                name: name.map(str::to_owned),
                inner,
            },
        )?
        .into_any());
    }
    Err(NBTWriteError::new_err(format!(
        "Unsupported type: {}",
        val.get_type().qualname()?
    )))
}

fn list_to_tag(
    py: Python<'_>,
    list: &Bound<'_, PyList>,
    name: Option<&str>,
) -> PyResult<Py<PyAny>> {
    if list.is_empty() {
        return Ok(Py::new(
            py,
            TagList {
                name: name.map(str::to_owned),
                tag_type: 0,
                value: vec![],
            },
        )?
        .into_any());
    }
    let all_bools = list.iter().all(|v| v.is_instance_of::<PyBool>());
    let all_ints = !all_bools && list.iter().all(|v| v.is_instance_of::<PyInt>());
    if all_ints {
        let vals: Vec<i64> = list
            .iter()
            .map(|v| v.extract::<i64>())
            .collect::<PyResult<_>>()?;
        let (mn, mx) = (*vals.iter().min().unwrap(), *vals.iter().max().unwrap());
        if mn >= -128 && mx <= 127 {
            return Ok(Py::new(
                py,
                TagByteArray {
                    name: name.map(str::to_owned),
                    value: vals.into_iter().map(|v| v as i8).collect(),
                },
            )?
            .into_any());
        }
        if mn >= i32::MIN as i64 && mx <= i32::MAX as i64 {
            return Ok(Py::new(
                py,
                TagIntArray {
                    name: name.map(str::to_owned),
                    value: vals.into_iter().map(|v| v as i32).collect(),
                },
            )?
            .into_any());
        }
        return Ok(Py::new(
            py,
            TagLongArray {
                name: name.map(str::to_owned),
                value: vals,
            },
        )?
        .into_any());
    }
    let items: Vec<Py<PyAny>> = list
        .iter()
        .map(|v| value_to_tag(py, &v, None))
        .collect::<PyResult<_>>()?;
    Ok(Py::new(
        py,
        TagList {
            name: name.map(str::to_owned),
            tag_type: 0,
            value: items,
        },
    )?
    .into_any())
}

#[gen_stub_pyfunction]
#[pyfunction]
pub fn to_dict(py: Python<'_>, tag: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    let compound = tag.extract::<PyRef<TagCompound>>()?;
    let d = PyDict::new(py);
    for (k, v) in &compound.inner {
        d.set_item(k, tag_to_value(py, v.bind(py))?)?;
    }
    Ok(d.into_any().unbind())
}

fn tag_to_value(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    if let Ok(t) = obj.extract::<PyRef<TagByte>>() {
        return Ok(t.value.into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagShort>>() {
        return Ok(t.value.into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagInt>>() {
        return Ok(t.value.into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagLong>>() {
        return Ok(t.value.into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagFloat>>() {
        return Ok((t.value as f64).into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagDouble>>() {
        return Ok(t.value.into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagString>>() {
        return Ok(t.value.clone().into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagByteArray>>() {
        return Ok(t.value.clone().into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagIntArray>>() {
        return Ok(t.value.clone().into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagLongArray>>() {
        return Ok(t.value.clone().into_pyobject(py)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagList>>() {
        let items: Vec<Py<PyAny>> = t
            .value
            .iter()
            .map(|v| tag_to_value(py, v.bind(py)))
            .collect::<PyResult<_>>()?;
        return Ok(PyList::new(py, items)?.into_any().unbind());
    }
    if let Ok(t) = obj.extract::<PyRef<TagCompound>>() {
        let d = PyDict::new(py);
        for (k, v) in &t.inner {
            d.set_item(k, tag_to_value(py, v.bind(py))?)?;
        }
        return Ok(d.into_any().unbind());
    }
    Ok(py.None())
}

// ── Used by datatypes::Slot ───────────────────────────────────────────────────

/// Returns the number of bytes consumed by a single complete NBT tag starting at data[0].
pub fn measure_nbt_bytes(data: &[u8]) -> Result<usize, String> {
    let mut r = Reader::new(data, false);
    r.read_root()?;
    Ok(r.pos() as usize)
}
