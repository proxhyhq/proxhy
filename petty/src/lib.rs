use pyo3::prelude::*;

mod item_data;
mod nbt;
mod slot;

/// The petty Rust extension module.
#[pymodule]
mod _petty {
    // NBT types
    #[pymodule_export]
    use super::nbt::{
        PyTagByte, PyTagByteArray, PyTagCompound, PyTagDouble, PyTagEnd, PyTagFloat, PyTagInt,
        PyTagIntArray, PyTagList, PyTagLong, PyTagLongArray, PyTagShort, PyTagString,
    };

    // NBT functions
    #[pymodule_export]
    use super::nbt::{py_dumps, py_from_dict, py_loads, py_read_nbt_size, py_to_dict};

    // Slot / Item types
    #[pymodule_export]
    use super::slot::{py_slot_pack, py_slot_unpack, PyItem, PySlotData};
}

pyo3_stub_gen::define_stub_info_gatherer!(stub_info);
