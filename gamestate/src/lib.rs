use pyo3::prelude::*;

pub mod constants;
pub mod enums;
pub mod packet_handlers;
pub mod reader;
pub mod state;
pub mod types;

#[pymodule]
mod _gamestate {
    #[pymodule_export]
    use super::enums::{
        CombatEventType, Difficulty, Dimension, EntityFlags, EntityStatus, EquipmentSlot,
        GameStateReason, Gamemode, PlayerAbilityFlags, PlayerListAction, TeamMode, TitleAction,
        WorldBorderAction,
    };

    #[pymodule_export]
    use super::state::GameState;

    #[pymodule_export]
    use super::types::{
        AttributeModifier, BlockEntity, Entity, EntityAttribute, EntityEffect, EntityEquipment,
        MapData, MetadataValue, Player, PlayerInfo, PluginChannel, ResourcePack, Rotation, Score,
        ScoreboardObjective, Statistics, Team, TitleState, Vec3d, Vec3i, VillagerTrade, Window,
        WorldBorder,
    };
}

pyo3_stub_gen::define_stub_info_gatherer!(stub_info);
