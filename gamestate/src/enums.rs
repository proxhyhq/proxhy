#![allow(non_snake_case)]

/// Minecraft Protocol v47 enums — mirrors gamestate/enums.py exactly.
use pyo3::prelude::*;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyclass_enum, gen_stub_pymethods};

macro_rules! int_enum {
    ($name:ident, $pyname:literal, { $($variant:ident = $val:literal),+ $(,)? }) => {
        #[gen_stub_pyclass_enum]
        #[pyclass(name = $pyname, eq, eq_int, from_py_object)]
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
        pub enum $name {
            $($variant = $val),+
        }

        #[gen_stub_pymethods]
        #[pymethods]
        impl $name {
            #[getter]
            fn value(&self) -> i64 { *self as i64 }
            fn __int__(&self) -> i64 { *self as i64 }
            fn __repr__(&self) -> String { format!("<{}.{:?}: {}>", $pyname, self, *self as i64) }
            fn __str__(&self) -> String { format!("{}.{:?}", $pyname, self) }

            #[classattr]
            #[allow(non_snake_case)]
            fn __members__(py: Python<'_>) -> PyResult<Py<PyAny>> {
                use pyo3::types::PyDict;
                let d = PyDict::new(py);
                $(d.set_item(stringify!($variant), $name::$variant.into_pyobject(py)?)?;)+
                Ok(d.into())
            }
        }

        impl TryFrom<i64> for $name {
            type Error = ();
            fn try_from(v: i64) -> Result<Self, ()> {
                match v {
                    $($val => Ok($name::$variant),)+
                    _ => Err(()),
                }
            }
        }

        impl TryFrom<i32> for $name {
            type Error = ();
            fn try_from(v: i32) -> Result<Self, ()> { $name::try_from(v as i64) }
        }

        impl TryFrom<i16> for $name {
            type Error = ();
            fn try_from(v: i16) -> Result<Self, ()> { $name::try_from(v as i64) }
        }

        impl TryFrom<i8> for $name {
            type Error = ();
            fn try_from(v: i8) -> Result<Self, ()> { $name::try_from(v as i64) }
        }

        impl TryFrom<u8> for $name {
            type Error = ();
            fn try_from(v: u8) -> Result<Self, ()> { $name::try_from(v as i64) }
        }

        impl TryFrom<u16> for $name {
            type Error = ();
            fn try_from(v: u16) -> Result<Self, ()> { $name::try_from(v as i64) }
        }

        impl TryFrom<u32> for $name {
            type Error = ();
            fn try_from(v: u32) -> Result<Self, ()> { $name::try_from(v as i64) }
        }
    }
}

int_enum!(Dimension, "Dimension", {
    Nether = -1,
    Overworld = 0,
    End = 1,
});

int_enum!(Gamemode, "Gamemode", {
    Survival = 0,
    Creative = 1,
    Adventure = 2,
    Spectator = 3,
});

int_enum!(Difficulty, "Difficulty", {
    Peaceful = 0,
    Easy = 1,
    Normal = 2,
    Hard = 3,
});

int_enum!(EntityStatus, "EntityStatus", {
    SpawnMinecartTimerReset = 1,
    LivingEntityHurt = 2,
    LivingEntityDead = 3,
    IronGolemArms = 4,
    TamingHearts = 6,
    TamedSmoke = 7,
    WolfShake = 8,
    EatingAccepted = 9,
    SheepEating = 10,
    IronGolemRose = 11,
    VillagerHearts = 12,
    VillagerAngry = 13,
    VillagerHappy = 14,
    WitchMagic = 15,
    ZombieConverting = 16,
    FireworkExploding = 17,
    AnimalLove = 18,
    SquidReset = 19,
    ExplosionParticle = 20,
    GuardianSound = 21,
    ReducedDebugEnabled = 22,
    ReducedDebugDisabled = 23,
});

int_enum!(GameStateReason, "GameStateReason", {
    InvalidBed = 0,
    EndRaining = 1,
    BeginRaining = 2,
    ChangeGamemode = 3,
    EnterCredits = 4,
    DemoMessage = 5,
    ArrowHitPlayer = 6,
    FadeValue = 7,
    FadeTime = 8,
    MobAppearance = 10,
});

int_enum!(PlayerListAction, "PlayerListAction", {
    AddPlayer = 0,
    UpdateGamemode = 1,
    UpdateLatency = 2,
    UpdateDisplayName = 3,
    RemovePlayer = 4,
});

int_enum!(TeamMode, "TeamMode", {
    Create = 0,
    Remove = 1,
    UpdateInfo = 2,
    AddPlayers = 3,
    RemovePlayers = 4,
});

int_enum!(TitleAction, "TitleAction", {
    SetTitle = 0,
    SetSubtitle = 1,
    SetTimes = 2,
    Hide = 3,
    Reset = 4,
});

int_enum!(WorldBorderAction, "WorldBorderAction", {
    SetSize = 0,
    LerpSize = 1,
    SetCenter = 2,
    Initialize = 3,
    SetWarningTime = 4,
    SetWarningBlocks = 5,
});

int_enum!(CombatEventType, "CombatEventType", {
    EnterCombat = 0,
    EndCombat = 1,
    EntityDead = 2,
});

int_enum!(EquipmentSlot, "EquipmentSlot", {
    Held = 0,
    Boots = 1,
    Leggings = 2,
    Chestplate = 3,
    Helmet = 4,
});

// ─────────────────────────────────────────────────────────────────────────────
// Bit-flag enums (IntFlag equivalents)
// ─────────────────────────────────────────────────────────────────────────────

#[gen_stub_pyclass]
#[pyclass(name = "PlayerAbilityFlags", from_py_object)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PlayerAbilityFlags(pub u8);

pub mod player_ability {
    pub const INVULNERABLE: u8 = 0x01;
    pub const FLYING: u8 = 0x02;
    pub const ALLOW_FLYING: u8 = 0x04;
    pub const CREATIVE_MODE: u8 = 0x08;
}

#[gen_stub_pymethods]
#[pymethods]
impl PlayerAbilityFlags {
    #[new]
    fn __new__(value: u8) -> Self {
        Self(value)
    }

    fn __int__(&self) -> u8 {
        self.0
    }
    fn __repr__(&self) -> String {
        format!("<PlayerAbilityFlags: {:#04x}>", self.0)
    }
    fn __and__(&self, other: &Self) -> Self {
        Self(self.0 & other.0)
    }
    fn __or__(&self, other: &Self) -> Self {
        Self(self.0 | other.0)
    }
    fn __ior__(&mut self, other: &Self) {
        self.0 |= other.0;
    }
    fn __bool__(&self) -> bool {
        self.0 != 0
    }

    #[getter]
    fn value(&self) -> u8 {
        self.0
    }

    #[classattr]
    fn INVULNERABLE() -> PlayerAbilityFlags {
        PlayerAbilityFlags(player_ability::INVULNERABLE)
    }
    #[classattr]
    fn FLYING() -> PlayerAbilityFlags {
        PlayerAbilityFlags(player_ability::FLYING)
    }
    #[classattr]
    fn ALLOW_FLYING() -> PlayerAbilityFlags {
        PlayerAbilityFlags(player_ability::ALLOW_FLYING)
    }
    #[classattr]
    fn CREATIVE_MODE() -> PlayerAbilityFlags {
        PlayerAbilityFlags(player_ability::CREATIVE_MODE)
    }
}

#[gen_stub_pyclass]
#[pyclass(name = "EntityFlags", from_py_object)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EntityFlags(pub u8);

pub mod entity_flag {
    pub const ON_FIRE: u8 = 0x01;
    pub const CROUCHED: u8 = 0x02;
    pub const SPRINTING: u8 = 0x08;
    pub const EATING_DRINKING_BLOCKING: u8 = 0x10;
    pub const INVISIBLE: u8 = 0x20;
}

#[gen_stub_pymethods]
#[pymethods]
impl EntityFlags {
    #[new]
    fn __new__(value: u8) -> Self {
        Self(value)
    }

    fn __int__(&self) -> u8 {
        self.0
    }
    fn __repr__(&self) -> String {
        format!("<EntityFlags: {:#04x}>", self.0)
    }
    fn __and__(&self, other: u8) -> u8 {
        self.0 & other
    }
    fn __bool__(&self) -> bool {
        self.0 != 0
    }

    #[getter]
    fn value(&self) -> u8 {
        self.0
    }

    #[classattr]
    fn ON_FIRE() -> EntityFlags {
        EntityFlags(entity_flag::ON_FIRE)
    }
    #[classattr]
    fn CROUCHED() -> EntityFlags {
        EntityFlags(entity_flag::CROUCHED)
    }
    #[classattr]
    fn SPRINTING() -> EntityFlags {
        EntityFlags(entity_flag::SPRINTING)
    }
    #[classattr]
    fn EATING_DRINKING_BLOCKING() -> EntityFlags {
        EntityFlags(entity_flag::EATING_DRINKING_BLOCKING)
    }
    #[classattr]
    fn INVISIBLE() -> EntityFlags {
        EntityFlags(entity_flag::INVISIBLE)
    }
}
