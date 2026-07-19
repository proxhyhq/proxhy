use crate::types::{Chunk, ChunkSection, Vec3i};
/// Zero-copy Minecraft Protocol v47 packet buffer reader.
/// All methods operate on a &[u8] slice via Cursor — no Python FFI.
use std::io::{Cursor, Read};

pub struct PacketReader<'a> {
    pub cur: Cursor<&'a [u8]>,
}

impl<'a> PacketReader<'a> {
    #[inline]
    pub fn new(data: &'a [u8]) -> Self {
        Self {
            cur: Cursor::new(data),
        }
    }

    #[inline]
    pub fn pos(&self) -> usize {
        self.cur.position() as usize
    }

    #[inline]
    pub fn remaining(&self) -> usize {
        self.cur.get_ref().len().saturating_sub(self.pos())
    }

    #[inline]
    pub fn read_byte(&mut self) -> i8 {
        let mut b = [0u8; 1];
        let _ = self.cur.read_exact(&mut b);
        b[0] as i8
    }

    #[inline]
    pub fn read_ubyte(&mut self) -> u8 {
        let mut b = [0u8; 1];
        let _ = self.cur.read_exact(&mut b);
        b[0]
    }

    #[inline]
    pub fn read_bool(&mut self) -> bool {
        self.read_ubyte() != 0
    }

    #[inline]
    pub fn read_short(&mut self) -> i16 {
        let mut b = [0u8; 2];
        let _ = self.cur.read_exact(&mut b);
        i16::from_be_bytes(b)
    }

    #[inline]
    pub fn read_ushort(&mut self) -> u16 {
        let mut b = [0u8; 2];
        let _ = self.cur.read_exact(&mut b);
        u16::from_be_bytes(b)
    }

    #[inline]
    pub fn read_int(&mut self) -> i32 {
        let mut b = [0u8; 4];
        let _ = self.cur.read_exact(&mut b);
        i32::from_be_bytes(b)
    }

    #[inline]
    pub fn read_uint(&mut self) -> u32 {
        let mut b = [0u8; 4];
        let _ = self.cur.read_exact(&mut b);
        u32::from_be_bytes(b)
    }

    #[inline]
    pub fn read_long(&mut self) -> i64 {
        let mut b = [0u8; 8];
        let _ = self.cur.read_exact(&mut b);
        i64::from_be_bytes(b)
    }

    #[inline]
    pub fn read_ulong(&mut self) -> u64 {
        let mut b = [0u8; 8];
        let _ = self.cur.read_exact(&mut b);
        u64::from_be_bytes(b)
    }

    #[inline]
    pub fn read_float(&mut self) -> f32 {
        let mut b = [0u8; 4];
        let _ = self.cur.read_exact(&mut b);
        f32::from_be_bytes(b)
    }

    #[inline]
    pub fn read_double(&mut self) -> f64 {
        let mut b = [0u8; 8];
        let _ = self.cur.read_exact(&mut b);
        f64::from_be_bytes(b)
    }

    /// Minecraft VarInt (up to 5 bytes, big-endian 7-bit groups with MSB continuation).
    #[inline]
    pub fn read_varint(&mut self) -> i32 {
        let mut result = 0;
        let mut num_read = 0;
        loop {
            let read = self.read_ubyte();
            let value = (read & 0b01111111) as i32;
            result |= value << (7 * num_read);
            num_read += 1;
            if num_read > 5 {
                break;
            }
            if (read & 0b10000000) == 0 {
                break;
            }
        }
        result
    }

    pub fn read_varlong(&mut self) -> i64 {
        let mut result = 0;
        let mut num_read = 0;
        loop {
            let read = self.read_ubyte();
            let value = (read & 0b01111111) as i64;
            result |= value << (7 * num_read);
            num_read += 1;
            if num_read > 10 {
                break;
            }
            if (read & 0b10000000) == 0 {
                break;
            }
        }
        result
    }

    /// Read a Minecraft-protocol angle byte → degrees.
    #[inline]
    pub fn read_angle(&mut self) -> f32 {
        let b = self.read_ubyte();
        360.0 * (b as f32) / 256.0
    }

    /// Length-prefixed UTF-8 string (VarInt length prefix).
    pub fn read_string(&mut self) -> String {
        let len = self.read_varint() as usize;
        let mut buf = vec![0u8; len];
        let _ = self.cur.read_exact(&mut buf);
        String::from_utf8_lossy(&buf).into_owned()
    }

    /// UUID as 16 raw bytes → hex-with-dashes string.
    pub fn read_uuid_str(&mut self) -> String {
        let mut b = [0u8; 16];
        let _ = self.cur.read_exact(&mut b);
        format!(
            "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
            b[0],b[1],b[2],b[3], b[4],b[5], b[6],b[7], b[8],b[9], b[10],b[11],b[12],b[13],b[14],b[15]
        )
    }

    /// Minecraft block position (64-bit encoded x/y/z).
    pub fn read_position(&mut self) -> Vec3i {
        let v = self.read_ulong();
        let mut x = (v >> 38) as i64;
        let mut y = ((v >> 26) & 0xFFF) as i64;
        let mut z = (v & 0x3FFFFFF) as i64;
        if x >= (1 << 25) {
            x -= 1 << 26;
        }
        if y >= (1 << 11) {
            y -= 1 << 12;
        }
        if z >= (1 << 25) {
            z -= 1 << 26;
        }
        Vec3i { x, y, z }
    }

    /// Read `n` raw bytes.
    pub fn read_bytes(&mut self, n: usize) -> Vec<u8> {
        let mut buf = vec![0u8; n];
        let _ = self.cur.read_exact(&mut buf);
        buf
    }

    /// Read remaining bytes.
    pub fn read_remaining(&mut self) -> Vec<u8> {
        let mut buf = Vec::new();
        let _ = self.cur.read_to_end(&mut buf);
        buf
    }

    /// Read a VarInt-prefixed byte array.
    pub fn read_byte_array(&mut self) -> Vec<u8> {
        let len = self.read_varint() as usize;
        self.read_bytes(len)
    }

    // ─────────────────────────────────────────────────────────────────────
    // Entity metadata (Protocol v47 format)
    // ─────────────────────────────────────────────────────────────────────

    /// Read entity metadata entries into a Vec<(index, type_id, raw_bytes_for_python)>.
    /// We store the raw value as a Python-compatible type based on type_id.
    pub fn read_metadata_raw(&mut self) -> Vec<(u8, u8, MetadataRawValue)> {
        let mut entries = Vec::new();
        loop {
            let header = self.read_ubyte();
            if header == 0x7F {
                break;
            }
            let index = header & 0x1F;
            let type_id = (header >> 5) & 0x07;
            let value = self.read_metadata_value(type_id);
            entries.push((index, type_id, value));
        }
        entries
    }

    fn read_metadata_value(&mut self, type_id: u8) -> MetadataRawValue {
        match type_id {
            0 => MetadataRawValue::Byte(self.read_byte()),
            1 => MetadataRawValue::Short(self.read_short()),
            2 => MetadataRawValue::Int(self.read_int()),
            3 => MetadataRawValue::Float(self.read_float()),
            4 => MetadataRawValue::String(self.read_string()),
            5 => {
                // Slot: consume slot bytes inline
                let start = self.pos();
                let item_id = self.read_short();
                let mut _nbt_bytes = Vec::new();
                if item_id != -1 {
                    let _count = self.read_byte();
                    let _damage = self.read_short();
                    _nbt_bytes = self.scan_nbt_bytes();
                }
                let end = self.pos();
                let all = self.cur.get_ref();
                MetadataRawValue::SlotBytes(all[start..end].to_vec())
            }
            6 => {
                let x = self.read_int();
                let y = self.read_int();
                let z = self.read_int();
                MetadataRawValue::Pos(x, y, z)
            }
            7 => {
                let pitch = self.read_float();
                let yaw = self.read_float();
                let roll = self.read_float();
                MetadataRawValue::Orient(pitch, yaw, roll)
            }
            _ => MetadataRawValue::Unknown,
        }
    }

    /// Scan past an NBT compound tag, returning the raw bytes consumed.
    /// Used to skip/copy NBT data without full parsing.
    pub fn scan_nbt_bytes(&mut self) -> Vec<u8> {
        let start = self.pos();
        let tag_byte = self.read_ubyte();
        if tag_byte == 0 {
            return vec![0u8];
        }
        // Read root compound name (short-prefixed string)
        let name_len = self.read_ushort() as usize;
        let _ = self.read_bytes(name_len);
        self.scan_compound_payload();
        let end = self.pos();
        self.cur.get_ref()[start..end].to_vec()
    }

    pub fn parse_metadata(&mut self) -> Option<()> {
        loop {
            let item = self.read_ubyte();
            if item == 127 {
                break;
            }
            let type_id = item >> 5;
            match type_id {
                0 => {
                    self.read_byte();
                }
                1 => {
                    self.read_short();
                }
                2 => {
                    self.read_int();
                }
                3 => {
                    self.read_float();
                }
                4 => {
                    self.read_string();
                }
                5 => {
                    let id = self.read_short();
                    if id != -1 {
                        self.read_byte();
                        self.read_short();
                        self.scan_nbt_bytes();
                    }
                }
                6 => {
                    self.read_int();
                    self.read_int();
                    self.read_int();
                }
                7 => {
                    self.read_float();
                    self.read_float();
                    self.read_float();
                }
                _ => {}
            }
        }
        None
    }

    fn scan_tag_payload(&mut self, type_id: u8) {
        match type_id {
            0 => {} // End
            1 => {
                let _ = self.read_byte();
            }
            2 => {
                let _ = self.read_short();
            }
            3 => {
                let _ = self.read_int();
            }
            4 => {
                let _ = self.read_long();
            }
            5 => {
                let _ = self.read_float();
            }
            6 => {
                let _ = self.read_double();
            }
            7 => {
                let n = self.read_int();
                let _ = self.read_bytes(n.max(0) as usize);
            } // byte array
            8 => {
                let n = self.read_ushort();
                let _ = self.read_bytes(n as usize);
            } // string
            9 => {
                // list
                let elem_type = self.read_ubyte();
                let count = self.read_int().max(0) as usize;
                for _ in 0..count {
                    self.scan_tag_payload(elem_type);
                }
            }
            10 => self.scan_compound_payload(),
            11 => {
                let n = self.read_int();
                let _ = self.read_bytes((n.max(0) as usize) * 4);
            } // int array
            12 => {
                let n = self.read_int();
                let _ = self.read_bytes((n.max(0) as usize) * 8);
            } // long array
            _ => {}
        }
    }

    fn scan_compound_payload(&mut self) {
        loop {
            let type_id = self.read_ubyte();
            if type_id == 0 {
                break;
            }
            let name_len = self.read_ushort() as usize;
            let _ = self.read_bytes(name_len);
            self.scan_tag_payload(type_id);
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // Chunk data parsing (Protocol v47, compressed column format)
    // ─────────────────────────────────────────────────────────────────────

    /// Parse a full chunk column from the given byte slice.
    /// `data` is the uncompressed chunk section data.
    pub fn parse_chunk_sections(
        chunk: &mut Chunk,
        data: &[u8],
        primary_bitmask: u16,
        add_bitmask: u16,
        sky_light: bool,
    ) {
        let mut offset = 0usize;
        let _total_sections = primary_bitmask.count_ones() as usize;

        // Block data: 8192 bytes per section (4096 × 2 bytes LE)
        for section_y in 0..16 {
            if primary_bitmask & (1 << section_y) == 0 {
                continue;
            }
            if offset + 8192 > data.len() {
                break;
            }
            let sec =
                chunk.sections[section_y].get_or_insert_with(|| Box::new(ChunkSection::new()));
            sec.blocks.copy_from_slice(&data[offset..offset + 8192]);
            offset += 8192;
        }

        // Block light: 2048 bytes per section
        for section_y in 0..16 {
            if primary_bitmask & (1 << section_y) == 0 {
                continue;
            }
            if offset + 2048 > data.len() {
                break;
            }
            let sec =
                chunk.sections[section_y].get_or_insert_with(|| Box::new(ChunkSection::new()));
            sec.block_light
                .copy_from_slice(&data[offset..offset + 2048]);
            offset += 2048;
        }

        // Sky light: 2048 bytes per section (overworld only)
        if sky_light {
            for section_y in 0..16 {
                if primary_bitmask & (1 << section_y) == 0 {
                    continue;
                }
                if offset + 2048 > data.len() {
                    break;
                }
                let sec =
                    chunk.sections[section_y].get_or_insert_with(|| Box::new(ChunkSection::new()));
                sec.sky_light = Some(data[offset..offset + 2048].to_vec());
                offset += 2048;
            }
        }

        // Add data: 2048 bytes per section (extended block IDs, mostly 0 in 1.8)
        for _section_y in 0..16 {
            if add_bitmask & (1 << _section_y) == 0 {
                continue;
            }
            offset += 2048; // skip
        }

        // Biomes (only for full chunks = primary_bitmask has all 16)
        if primary_bitmask.count_ones() == 16 && offset + 256 <= data.len() {
            chunk.biomes.copy_from_slice(&data[offset..offset + 256]);
        }
    }
}

/// Raw metadata value (before conversion to Python objects).
pub enum MetadataRawValue {
    Byte(i8),
    Short(i16),
    Int(i32),
    Float(f32),
    String(std::string::String),
    SlotBytes(Vec<u8>),
    Pos(i32, i32, i32),
    Orient(f32, f32, f32),
    Unknown,
}
