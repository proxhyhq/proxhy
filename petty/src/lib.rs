use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

mod datatypes;
mod models;
mod nbt;

#[pymodule]
fn _petty(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ── datatypes ────────────────────────────────────────────────────────────
    m.add_class::<datatypes::VarInt>()?;
    m.add_class::<datatypes::UnsignedShort>()?;
    m.add_class::<datatypes::Short>()?;
    m.add_class::<datatypes::Long>()?;
    m.add_class::<datatypes::Byte>()?;
    m.add_class::<datatypes::UnsignedByte>()?;
    m.add_class::<datatypes::ByteArray>()?;
    m.add_class::<datatypes::Boolean>()?;
    m.add_class::<datatypes::Int>()?;
    m.add_class::<datatypes::Float>()?;
    m.add_class::<datatypes::Double>()?;
    m.add_class::<datatypes::Angle>()?;
    m.add_class::<datatypes::Position>()?;
    m.add_class::<datatypes::Uuid>()?;
    m.add_class::<datatypes::PettyString>()?;
    m.add_class::<datatypes::Chat>()?;
    m.add_class::<datatypes::Slot>()?;

    // ── models ───────────────────────────────────────────────────────────────
    m.add_class::<models::Pos>()?;
    m.add_class::<models::Item>()?;
    m.add_class::<models::SlotData>()?;
    m.add_class::<models::TextComponent>()?;

    // ── nbt ──────────────────────────────────────────────────────────────────
    m.add_class::<nbt::TagType>()?;
    m.add_class::<nbt::TagEnd>()?;
    m.add_class::<nbt::TagByte>()?;
    m.add_class::<nbt::TagShort>()?;
    m.add_class::<nbt::TagInt>()?;
    m.add_class::<nbt::TagLong>()?;
    m.add_class::<nbt::TagFloat>()?;
    m.add_class::<nbt::TagDouble>()?;
    m.add_class::<nbt::TagByteArray>()?;
    m.add_class::<nbt::TagString>()?;
    m.add_class::<nbt::TagList>()?;
    m.add_class::<nbt::TagCompound>()?;
    m.add_class::<nbt::TagIntArray>()?;
    m.add_class::<nbt::TagLongArray>()?;
    m.add_class::<nbt::NBTReader>()?;
    m.add_class::<nbt::NBTWriter>()?;

    // NBT exceptions (registered as subclasses of Python Exception, not PyClass)
    let nbt_error = py.get_type::<nbt::NBTError>();
    m.add("NBTError", nbt_error)?;
    let nbt_parse_error = py.get_type::<nbt::NBTParseError>();
    m.add("NBTParseError", nbt_parse_error)?;
    let nbt_write_error = py.get_type::<nbt::NBTWriteError>();
    m.add("NBTWriteError", nbt_write_error)?;

    m.add_function(wrap_pyfunction!(nbt::load, m)?)?;
    m.add_function(wrap_pyfunction!(nbt::loads, m)?)?;
    m.add_function(wrap_pyfunction!(nbt::dump, m)?)?;
    m.add_function(wrap_pyfunction!(nbt::dumps, m)?)?;
    m.add_function(wrap_pyfunction!(nbt::from_dict, m)?)?;
    m.add_function(wrap_pyfunction!(nbt::to_dict, m)?)?;

    // Initialise item mapping from embedded JSON (one-time cost at import).
    models::init_item_mapping()?;

    Ok(())
}

define_stub_info_gatherer!(stub_info);
