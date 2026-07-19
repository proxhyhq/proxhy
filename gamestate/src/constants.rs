/// Minecraft Protocol v47 (1.8.x) entity mob type IDs.
/// Used to distinguish Spawn Mob vs Spawn Object packets.
pub const MOB_TYPES: &[u8] = &[
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 90, 91, 92, 93,
    94, 95, 96, 97, 98, 99, 100, 101, 120,
];

#[inline(always)]
pub fn is_mob_type(entity_type: u8) -> bool {
    MOB_TYPES.contains(&entity_type)
}
