//! Domain model types: Pos, Item, SlotData, TextComponent.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyType};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::OnceLock;

// ── Item mapping ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize)]
pub struct ItemData {
    pub id: i32,
    pub name: String,
    pub display_name: String,
    pub data: i32,
}

static ITEM_MAPPING: OnceLock<Vec<ItemData>> = OnceLock::new();

pub fn init_item_mapping() -> PyResult<()> {
    if ITEM_MAPPING.get().is_some() {
        return Ok(());
    }
    let json = include_str!("items.json");
    let items: Vec<ItemData> = serde_json::from_str(json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    ITEM_MAPPING.set(items).ok();
    Ok(())
}

fn item_mapping() -> &'static [ItemData] {
    ITEM_MAPPING.get().map(Vec::as_slice).unwrap_or(&[])
}

// ── Pos ───────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Pos", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct Pos {
    #[pyo3(get, set)]
    pub x: i32,
    #[pyo3(get, set)]
    pub y: i32,
    #[pyo3(get, set)]
    pub z: i32,
}

#[gen_stub_pymethods]
#[pymethods]
impl Pos {
    #[new]
    #[pyo3(signature = (x=0, y=0, z=0))]
    pub fn new(x: i32, y: i32, z: i32) -> Self {
        Pos { x, y, z }
    }

    fn __repr__(&self) -> String {
        format!("Pos(x={}, y={}, z={})", self.x, self.y, self.z)
    }

    fn __eq__(&self, other: PyRef<'_, Pos>) -> bool {
        self.x == other.x && self.y == other.y && self.z == other.z
    }
}

// ── Item ──────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "Item", from_py_object)]
#[derive(Clone, Debug)]
pub struct Item {
    #[pyo3(get)]
    pub id: i32,
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub display_name: String,
    #[pyo3(get)]
    pub data: i32,
}

impl Item {
    fn from_data(d: &ItemData) -> Self {
        Item {
            id: d.id,
            name: d.name.clone(),
            display_name: d.display_name.clone(),
            data: d.data,
        }
    }

    pub fn from_id_rust(id: i32) -> Option<Self> {
        item_mapping()
            .iter()
            .find(|i| i.id == id)
            .map(Item::from_data)
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl Item {
    #[new]
    pub fn new(id: i32, name: String, display_name: String, data: i32) -> Self {
        Item {
            id,
            name,
            display_name,
            data,
        }
    }

    /// Construct an Item from its name. Raises ValueError if the item was not found.
    #[classmethod]
    pub fn from_name(_cls: &Bound<'_, PyType>, name: &str) -> PyResult<Self> {
        let name = if name.starts_with("minecraft:") {
            name.to_owned()
        } else {
            format!("minecraft:{name}")
        };
        item_mapping()
            .iter()
            .find(|i| i.name == name)
            // throw here; it is the caller's job to check display_name validity
            // either before calling this function or by catching the error
            .map(Item::from_data)
            .ok_or(PyValueError::new_err("Unknown item name: {name}"))
    }

    #[classmethod]
    pub fn from_display_name(_cls: &Bound<'_, PyType>, display_name: &str) -> PyResult<Self> {
        item_mapping()
            .iter()
            .find(|i| i.display_name == display_name)
            .map(Item::from_data)
            .ok_or(PyValueError::new_err(
                "Unknown item display name: {display_name}",
            ))
    }

    #[classmethod]
    pub fn from_id(_cls: &Bound<'_, PyType>, id: i32) -> Option<Self> {
        Self::from_id_rust(id)
    }

    fn __repr__(&self) -> String {
        format!("Item(id={}, name={:?})", self.id, self.name)
    }

    fn __eq__(&self, other: PyRef<'_, Item>) -> bool {
        self.id == other.id
            && self.name == other.name
            && self.display_name == other.display_name
            && self.data == other.data
    }
}

// ── SlotData ──────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "SlotData", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct SlotData {
    #[pyo3(get)]
    pub item: Option<Item>,
    #[pyo3(get)]
    pub count: i32,
    #[pyo3(get)]
    pub damage: i32,
    pub nbt: Vec<u8>,
}

impl SlotData {
    pub fn empty() -> Self {
        SlotData {
            item: None,
            count: 0,
            damage: 0,
            nbt: Vec::new(),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl SlotData {
    #[new]
    #[pyo3(signature = (item=None, count=1, damage=0, nbt=None))]
    pub fn new(item: Option<Item>, count: i32, damage: i32, nbt: Option<Vec<u8>>) -> Self {
        if item.is_none() {
            return SlotData::empty();
        }
        SlotData {
            item,
            count,
            damage,
            nbt: nbt.unwrap_or_default(),
        }
    }

    #[getter]
    fn nbt(&self, py: Python<'_>) -> Py<PyBytes> {
        PyBytes::new(py, &self.nbt).unbind()
    }

    fn __repr__(&self) -> String {
        match &self.item {
            None => "SlotData(None)".to_owned(),
            Some(i) => format!(
                "SlotData(item={}, count={}, damage={})",
                i.name, self.count, self.damage
            ),
        }
    }
}

// ── TextComponent ─────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "TextComponent")]
pub struct TextComponent {
    /// Internal JSON-serialisable dict stored as `Py<PyAny>`.
    #[pyo3(get)]
    pub(crate) data: Py<PyAny>,
}

// ── colour/format code tables ──────────────────────────────────────────────────

fn color_codes() -> &'static HashMap<&'static str, &'static str> {
    static MAP: OnceLock<HashMap<&'static str, &'static str>> = OnceLock::new();
    MAP.get_or_init(|| {
        let mut m = HashMap::new();
        m.insert("0", "black");
        m.insert("1", "dark_blue");
        m.insert("2", "dark_green");
        m.insert("3", "dark_aqua");
        m.insert("4", "dark_red");
        m.insert("5", "dark_purple");
        m.insert("6", "gold");
        m.insert("7", "gray");
        m.insert("8", "dark_gray");
        m.insert("9", "blue");
        m.insert("a", "green");
        m.insert("b", "aqua");
        m.insert("c", "red");
        m.insert("d", "light_purple");
        m.insert("e", "yellow");
        m.insert("f", "white");
        m
    })
}

fn format_codes() -> &'static HashMap<&'static str, &'static str> {
    static MAP: OnceLock<HashMap<&'static str, &'static str>> = OnceLock::new();
    MAP.get_or_init(|| {
        let mut m = HashMap::new();
        m.insert("k", "obfuscated");
        m.insert("l", "bold");
        m.insert("m", "strikethrough");
        m.insert("n", "underlined");
        m.insert("o", "italic");
        m.insert("r", "reset");
        m
    })
}

const CONTENT_FIELDS: &[&str] = &["text", "translate", "score", "selector", "keybind", "nbt"];

// ── TextComponent helpers ──────────────────────────────────────────────────────

impl TextComponent {
    pub fn from_py_data(data: Py<PyAny>) -> Self {
        TextComponent { data }
    }

    pub fn to_json_str(&self) -> String {
        Python::attach(|py| {
            let orjson = py.import("orjson").expect("orjson not installed");
            let dumped: Vec<u8> = orjson
                .call_method1("dumps", (&self.data,))
                .expect("orjson dumps failed")
                .extract()
                .expect("extract failed");
            String::from_utf8(dumped).expect("not utf8")
        })
    }
}

// ── Helper: normalise any component value to a dict ───────────────────────────

fn normalize_component<'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(tc) = component.extract::<PyRef<TextComponent>>() {
        return Ok(tc.data.bind(py).clone());
    }
    if let Ok(s) = component.extract::<String>() {
        let d = PyDict::new(py);
        d.set_item("text", s)?;
        return Ok(d.into_any());
    }
    if component.is_instance_of::<PyDict>() {
        return Ok(component.clone());
    }
    if let Ok(list) = component.cast::<PyList>() {
        if !list.is_empty() {
            let first = list.get_item(0)?;
            let fdict = if first.is_instance_of::<PyDict>() {
                first.clone().cast_into::<PyDict>()?
            } else {
                let d = PyDict::new(py);
                d.set_item("text", first.str()?.to_str()?)?;
                d
            };
            if list.len() > 1 {
                let extra = list.get_slice(1, list.len());
                fdict.set_item("extra", extra)?;
            }
            return Ok(fdict.into_any());
        }
        return Ok(PyDict::new(py).into_any());
    }
    let d = PyDict::new(py);
    d.set_item("text", component.str()?.to_str()?)?;
    Ok(d.into_any())
}

fn remove_content_fields(dict: &Bound<'_, PyDict>, except: Option<&str>) -> PyResult<()> {
    const REMOVABLE: &[&str] = &[
        "text",
        "translate",
        "score",
        "selector",
        "keybind",
        "nbt",
        "with",
        "fallback",
        "separator",
        "interpret",
        "block",
        "entity",
        "storage",
        "source",
    ];
    const TRANSLATE_KEEP: &[&str] = &["with", "fallback"];
    const SELECTOR_KEEP: &[&str] = &["separator"];
    const NBT_KEEP: &[&str] = &[
        "separator",
        "interpret",
        "block",
        "entity",
        "storage",
        "source",
    ];

    let keep_extra: &[&str] = match except {
        Some("translate") => TRANSLATE_KEEP,
        Some("selector") => SELECTOR_KEEP,
        Some("nbt") => NBT_KEEP,
        _ => &[],
    };

    for field in REMOVABLE {
        if Some(*field) == except {
            continue;
        }
        if keep_extra.contains(field) {
            continue;
        }
        dict.del_item(field).ok();
    }
    Ok(())
}

fn parse_component_to_text(data: &Bound<'_, PyAny>) -> PyResult<String> {
    let mut text = String::new();
    if let Ok(s) = data.extract::<String>() {
        return Ok(s);
    }
    if let Ok(list) = data.cast::<PyList>() {
        for item in list {
            text.push_str(&parse_component_to_text(&item)?);
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
                    .map(|a| parse_component_to_text(&a))
                    .collect::<PyResult<_>>()?;
                text.push_str(&parts.join(", "));
            }
        }
        if let Some(t) = dict.get_item("text")? {
            text.push_str(&t.extract::<String>()?);
        }
        if let Some(extra) = dict.get_item("extra")? {
            text.push_str(&parse_component_to_text(&extra)?);
        }
    }
    Ok(text)
}

fn strip_section_codes(s: &str) -> String {
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

// ── TextComponent pymethods ────────────────────────────────────────────────────

#[gen_stub_pymethods]
#[pymethods]
impl TextComponent {
    #[new]
    #[pyo3(signature = (data=None))]
    pub fn new(py: Python<'_>, data: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let dict = PyDict::new(py);
        if let Some(d) = data {
            if d.is_none() {
                // keep empty
            } else if let Ok(s) = d.extract::<String>() {
                dict.set_item("text", s)?;
            } else if let Ok(list) = d.cast::<PyList>() {
                if !list.is_empty() {
                    let first = list.get_item(0)?;
                    if let Ok(fdict) = first.cast::<PyDict>() {
                        for (k, v) in fdict.iter() {
                            dict.set_item(k, v)?;
                        }
                    } else {
                        dict.set_item("text", first.str()?.to_str()?)?;
                    }
                    if list.len() > 1 {
                        let rest = PyList::new(py, list.iter().skip(1).collect::<Vec<_>>())?;
                        dict.set_item("extra", rest)?;
                    }
                }
            } else if let Ok(tc) = d.extract::<PyRef<TextComponent>>() {
                let src = tc.data.bind(py).cast::<PyDict>()?.clone();
                for (k, v) in src.iter() {
                    dict.set_item(k, v)?;
                }
            } else if let Ok(src) = d.cast::<PyDict>() {
                for (k, v) in src.iter() {
                    dict.set_item(k, v)?;
                }
            }
        }
        // Ensure "type" field
        if dict.get_item("type")?.is_none() {
            for ct in CONTENT_FIELDS {
                if dict.get_item(ct)?.is_some() {
                    dict.set_item("type", if *ct == "score" { "score" } else { *ct })?;
                    break;
                }
            }
            if dict.get_item("type")?.is_none() {
                dict.set_item("type", "text")?;
            }
        }
        Ok(TextComponent {
            data: dict.into_any().unbind(),
        })
    }

    // ── content setters ───────────────────────────────────────────────────────

    pub fn set_text(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        text: String,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        dict.set_item("text", &text)?;
        dict.set_item("type", "text")?;
        remove_content_fields(&dict, Some("text"))?;
        Ok(slf.into())
    }

    #[pyo3(signature = (key, with_args=None, fallback=None))]
    pub fn set_translate(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        key: String,
        with_args: Option<&Bound<'_, PyList>>,
        fallback: Option<String>,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        dict.set_item("translate", &key)?;
        dict.set_item("type", "translatable")?;
        if let Some(args) = with_args {
            let normalised = PyList::empty(py);
            for arg in args.iter() {
                normalised.append(normalize_component(py, &arg)?)?;
            }
            dict.set_item("with", normalised)?;
        }
        if let Some(fb) = fallback {
            dict.set_item("fallback", fb)?;
        }
        remove_content_fields(&dict, Some("translate"))?;
        Ok(slf.into())
    }

    pub fn set_score(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        name: String,
        objective: String,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        let score_dict = PyDict::new(py);
        score_dict.set_item("name", name)?;
        score_dict.set_item("objective", objective)?;
        dict.set_item("score", score_dict)?;
        dict.set_item("type", "score")?;
        remove_content_fields(&dict, Some("score"))?;
        Ok(slf.into())
    }

    pub fn set_keybind(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        keybind: String,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        dict.set_item("keybind", keybind)?;
        dict.set_item("type", "keybind")?;
        remove_content_fields(&dict, Some("keybind"))?;
        Ok(slf.into())
    }

    // ── formatting ────────────────────────────────────────────────────────────

    pub fn color(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        color: String,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("color", color)?;
        Ok(slf.into())
    }

    #[pyo3(signature = (bold = true))]
    pub fn bold(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        bold: bool,
    ) -> PyResult<Py<TextComponent>> {
        slf.data.bind(py).cast::<PyDict>()?.set_item("bold", bold)?;
        Ok(slf.into())
    }

    #[pyo3(signature = (italic = true))]
    pub fn italic(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        italic: bool,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("italic", italic)?;
        Ok(slf.into())
    }

    #[pyo3(signature = (underlined = true))]
    pub fn underlined(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        underlined: bool,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("underlined", underlined)?;
        Ok(slf.into())
    }

    #[pyo3(signature = (strikethrough = true))]
    pub fn strikethrough(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        strikethrough: bool,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("strikethrough", strikethrough)?;
        Ok(slf.into())
    }

    #[pyo3(signature = (obfuscated = true))]
    pub fn obfuscated(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        obfuscated: bool,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("obfuscated", obfuscated)?;
        Ok(slf.into())
    }

    pub fn font(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        font: String,
    ) -> PyResult<Py<TextComponent>> {
        slf.data.bind(py).cast::<PyDict>()?.set_item("font", font)?;
        Ok(slf.into())
    }

    pub fn insertion(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        text: String,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("insertion", text)?;
        Ok(slf.into())
    }

    pub fn shadow_color(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        color: &Bound<'_, PyAny>,
    ) -> PyResult<Py<TextComponent>> {
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("shadow_color", color)?;
        Ok(slf.into())
    }

    pub fn click_event(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        action: String,
        value: String,
    ) -> PyResult<Py<TextComponent>> {
        let d = PyDict::new(py);
        d.set_item("action", action)?;
        d.set_item("value", value)?;
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("clickEvent", d)?;
        Ok(slf.into())
    }

    pub fn hover_text(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        text: &Bound<'_, PyAny>,
    ) -> PyResult<Py<TextComponent>> {
        let event = PyDict::new(py);
        event.set_item("action", "show_text")?;
        event.set_item("value", normalize_component(py, text)?)?;
        slf.data
            .bind(py)
            .cast::<PyDict>()?
            .set_item("hoverEvent", event)?;
        Ok(slf.into())
    }

    // ── children ──────────────────────────────────────────────────────────────

    pub fn append(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        component: &Bound<'_, PyAny>,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        let normalised = normalize_component(py, component)?;
        match dict.get_item("extra")? {
            Some(e) => e.cast::<PyList>()?.append(normalised)?,
            None => {
                let l = PyList::new(py, [normalised])?;
                dict.set_item("extra", l)?;
            }
        }
        Ok(slf.into())
    }

    pub fn prepend(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        component: &Bound<'_, PyAny>,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        let normalised = normalize_component(py, component)?;
        match dict.get_item("extra")? {
            Some(e) => e.cast::<PyList>()?.insert(0, normalised)?,
            None => dict.set_item("extra", PyList::new(py, [normalised])?)?,
        }
        Ok(slf.into())
    }

    pub fn extend(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        components: &Bound<'_, PyList>,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        let extra = match dict.get_item("extra")? {
            Some(e) => e.cast_into::<PyList>()?,
            None => {
                let l = PyList::empty(py);
                dict.set_item("extra", &l)?;
                l
            }
        };
        for comp in components.iter() {
            extra.append(normalize_component(py, &comp)?)?;
        }
        Ok(slf.into())
    }

    #[pyo3(signature = (component, separator = " "))]
    pub fn appends(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        component: &Bound<'_, PyAny>,
        separator: &str,
    ) -> PyResult<Py<TextComponent>> {
        let normalised = normalize_component(py, component)?;
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        // Prepend separator to the component's text
        let norm_dict = if let Ok(d) = normalised.cast::<PyDict>() {
            d.clone()
        } else {
            let d = PyDict::new(py);
            d.set_item("text", separator)?;
            d
        };
        if let Some(t) = norm_dict.get_item("text")? {
            norm_dict.set_item("text", format!("{separator}{}", t.extract::<String>()?))?;
        } else {
            norm_dict.set_item("text", separator)?;
        }
        match dict.get_item("extra")? {
            Some(e) => e.cast::<PyList>()?.append(&norm_dict)?,
            None => dict.set_item("extra", PyList::new(py, [&norm_dict])?)?,
        }
        Ok(slf.into())
    }

    pub fn clear_children(slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<Py<TextComponent>> {
        slf.data.bind(py).cast::<PyDict>()?.del_item("extra").ok();
        Ok(slf.into())
    }

    pub fn remove_child(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        index: usize,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        if let Some(extra) = dict.get_item("extra")? {
            let list = extra.cast::<PyList>()?;
            if index < list.len() {
                list.del_item(index)?;
                if list.is_empty() {
                    dict.del_item("extra")?;
                }
            }
        }
        Ok(slf.into())
    }

    pub fn replace_child(
        slf: PyRefMut<'_, Self>,
        py: Python<'_>,
        index: usize,
        component: &Bound<'_, PyAny>,
    ) -> PyResult<Py<TextComponent>> {
        let dict = slf.data.bind(py).cast::<PyDict>()?.clone();
        let normalised = normalize_component(py, component)?;
        if let Some(extra) = dict.get_item("extra")? {
            let list = extra.cast::<PyList>()?;
            if index < list.len() {
                list.set_item(index, normalised)?;
            }
        }
        Ok(slf.into())
    }

    pub fn flatten(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<Py<TextComponent>> {
        let self_dict = slf.data.bind(py).cast::<PyDict>()?.clone();

        let flattened = PyDict::new(py);
        for (k, v) in self_dict.iter() {
            if k.extract::<String>()? != "extra" {
                flattened.set_item(k, v)?;
            }
        }

        fn collect(
            py: Python<'_>,
            data: &Bound<'_, PyDict>,
            out: &Bound<'_, PyList>,
        ) -> PyResult<()> {
            if let Some(extra) = data.get_item("extra")? {
                for child in extra.cast::<PyList>()?.iter() {
                    let child_tc = TextComponent::new(py, Some(&child))?;
                    let child_dict = child_tc.data.bind(py).cast::<PyDict>()?.clone();
                    let flat_child = PyDict::new(py);
                    for (k, v) in child_dict.iter() {
                        if k.extract::<String>()? != "extra" {
                            flat_child.set_item(k, v)?;
                        }
                    }
                    out.append(&flat_child)?;
                    collect(py, &child_dict, out)?;
                }
            }
            Ok(())
        }

        let children = PyList::empty(py);
        collect(py, &self_dict, &children)?;
        if !children.is_empty() {
            flattened.set_item("extra", &children)?;
        }

        slf.data = flattened.into_any().unbind();
        Ok(slf.into())
    }

    // ── class-level colour/format code tables (read by external code) ──────────

    #[classattr]
    #[allow(non_snake_case)]
    fn COLOR_CODES(py: Python<'_>) -> PyResult<Py<PyDict>> {
        let d = PyDict::new(py);
        for (k, v) in color_codes() {
            d.set_item(k, v)?;
        }
        Ok(d.unbind())
    }

    #[classattr]
    #[allow(non_snake_case)]
    fn FORMAT_CODES(py: Python<'_>) -> PyResult<Py<PyDict>> {
        let d = PyDict::new(py);
        for (k, v) in format_codes() {
            d.set_item(k, v)?;
        }
        Ok(d.unbind())
    }

    // ── utility ───────────────────────────────────────────────────────────────

    pub fn copy(&self, py: Python<'_>) -> PyResult<TextComponent> {
        let orjson = py.import("orjson")?;
        let dumped: Vec<u8> = orjson.call_method1("dumps", (&self.data,))?.extract()?;
        let data = orjson.call_method1("loads", (dumped.as_slice(),))?;
        Ok(TextComponent {
            data: data.unbind(),
        })
    }

    pub fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let dict = self.data.bind(py).cast::<PyDict>()?.copy()?;
        Ok(dict.into_any().unbind())
    }

    pub fn to_json(&self) -> String {
        TextComponent::to_json_str(self)
    }

    pub fn is_empty(&self, py: Python<'_>) -> PyResult<bool> {
        let dict = self.data.bind(py).cast::<PyDict>()?.clone();
        Ok(!CONTENT_FIELDS
            .iter()
            .any(|f| dict.get_item(f).ok().flatten().is_some()))
    }

    pub fn get_children(&self, py: Python<'_>) -> PyResult<Vec<TextComponent>> {
        let dict = self.data.bind(py).cast::<PyDict>()?.clone();
        match dict.get_item("extra")? {
            None => Ok(vec![]),
            Some(extra) => {
                let list = extra.cast::<PyList>()?;
                list.iter()
                    .map(|item| TextComponent::new(py, Some(&item)))
                    .collect()
            }
        }
    }

    fn __repr__(&self) -> String {
        format!("TextComponent({})", TextComponent::to_json_str(self))
    }

    fn __str__(&self, py: Python<'_>) -> PyResult<String> {
        let data = self.data.bind(py);
        let text = parse_component_to_text(data)?;
        Ok(strip_section_codes(&text))
    }

    // ── from_legacy / to_legacy ───────────────────────────────────────────────

    #[classmethod]
    pub fn from_legacy(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        text: &str,
    ) -> PyResult<TextComponent> {
        let color_map = color_codes();
        let format_map = format_codes();

        let extra_list = PyList::empty(py);
        let mut color: Option<&'static str> = None;
        let mut bold = false;
        let mut italic = false;
        let mut underlined = false;
        let mut strikethrough = false;
        let mut obfuscated = false;
        let mut buffer = String::new();

        let mut chars = text.chars().peekable();
        while let Some(c) = chars.next() {
            if c == '\u{00a7}' {
                if let Some(code) = chars.next() {
                    // flush current buffer segment
                    if !buffer.is_empty() {
                        let d = PyDict::new(py);
                        d.set_item("text", buffer.as_str())?;
                        if let Some(c) = color {
                            d.set_item("color", c)?;
                        }
                        if bold {
                            d.set_item("bold", true)?;
                        }
                        if italic {
                            d.set_item("italic", true)?;
                        }
                        if underlined {
                            d.set_item("underlined", true)?;
                        }
                        if strikethrough {
                            d.set_item("strikethrough", true)?;
                        }
                        if obfuscated {
                            d.set_item("obfuscated", true)?;
                        }
                        extra_list.append(d)?;
                        buffer.clear();
                    }
                    let code_str = code.to_lowercase().to_string();
                    if let Some(&c) = color_map.get(code_str.as_str()) {
                        color = Some(c);
                        bold = false;
                        italic = false;
                        underlined = false;
                        strikethrough = false;
                    } else if code_str == "r" {
                        color = None;
                        bold = false;
                        italic = false;
                        underlined = false;
                        strikethrough = false;
                        obfuscated = false;
                    } else if let Some(&fmt) = format_map.get(code_str.as_str()) {
                        match fmt {
                            "bold" => bold = true,
                            "italic" => italic = true,
                            "underlined" => underlined = true,
                            "strikethrough" => strikethrough = true,
                            "obfuscated" => obfuscated = true,
                            _ => {}
                        }
                    }
                }
            } else {
                buffer.push(c);
            }
        }
        // flush remaining
        if !buffer.is_empty() {
            let d = PyDict::new(py);
            d.set_item("text", buffer.as_str())?;
            if let Some(c) = color {
                d.set_item("color", c)?;
            }
            if bold {
                d.set_item("bold", true)?;
            }
            if italic {
                d.set_item("italic", true)?;
            }
            if underlined {
                d.set_item("underlined", true)?;
            }
            if strikethrough {
                d.set_item("strikethrough", true)?;
            }
            if obfuscated {
                d.set_item("obfuscated", true)?;
            }
            extra_list.append(d)?;
        }

        if extra_list.len() == 1 {
            let child = extra_list.get_item(0)?;
            return TextComponent::new(py, Some(&child));
        }
        let root_dict = PyDict::new(py);
        root_dict.set_item("text", "")?;
        root_dict.set_item("type", "text")?;
        root_dict.set_item("extra", extra_list)?;
        Ok(TextComponent {
            data: root_dict.into_any().unbind(),
        })
    }

    pub fn to_legacy(&self, py: Python<'_>) -> PyResult<String> {
        let reverse_colors: HashMap<&str, &str> =
            color_codes().iter().map(|(&k, &v)| (v, k)).collect();
        let reverse_formats: HashMap<&str, &str> = format_codes()
            .iter()
            .filter(|&(_, &v)| v != "reset")
            .map(|(&k, &v)| (v, k))
            .collect();
        let mut parts = Vec::new();
        build_legacy(
            self.data.bind(py),
            &mut parts,
            &reverse_colors,
            &reverse_formats,
        )?;
        Ok(parts.join(""))
    }
}

fn build_legacy(
    data: &Bound<'_, PyAny>,
    parts: &mut Vec<String>,
    rc: &HashMap<&str, &str>,
    rf: &HashMap<&str, &str>,
) -> PyResult<()> {
    if let Ok(s) = data.extract::<String>() {
        parts.push(s);
        return Ok(());
    }
    if let Ok(list) = data.cast::<PyList>() {
        for item in list {
            build_legacy(&item, parts, rc, rf)?;
        }
        return Ok(());
    }
    if let Ok(dict) = data.cast::<PyDict>() {
        let mut prefix = String::new();
        if let Some(color) = dict
            .get_item("color")?
            .and_then(|c| c.extract::<String>().ok())
            && let Some(&code) = rc.get(color.as_str())
        {
            prefix.push('\u{00a7}');
            prefix.push_str(code);
        }
        for (fmt, code) in rf {
            if dict
                .get_item(fmt)?
                .and_then(|v| v.extract::<bool>().ok())
                .unwrap_or(false)
            {
                prefix.push('\u{00a7}');
                prefix.push_str(code);
            }
        }
        let text = dict
            .get_item("text")?
            .and_then(|t| t.extract::<String>().ok())
            .unwrap_or_default();
        if !text.is_empty() || !prefix.is_empty() {
            parts.push(format!("{prefix}{text}"));
        }
        if let Some(extra) = dict.get_item("extra")?
            && let Ok(list) = extra.cast::<PyList>()
        {
            for child in list {
                build_legacy(&child, parts, rc, rf)?;
            }
        }
    }
    Ok(())
}
