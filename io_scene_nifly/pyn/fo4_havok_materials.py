"""Fallout 4 collision materials.

A Havok shape's userData (hknpShape +0x18) names its material: the CRC of the material's
Havok name, the MNAM of a MATT record ("MetalLight"), lowercased, through Bethesda's CRC32
(reflected, init 0, no final XOR).  Blender shows the name; a value that isn't the CRC of
any name here is shown as hex ("0xFCB37EA0") and round-trips as that number.
"""

# The MNAM of every MATT record in Fallout4.esm and its 6 DLC masters.
FO4_HAVOK_MATERIALS = (
    'ActorArmored', 'ActorArmoredCrab', 'ActorGeneric', 'ActorGhost', 'ActorGlowing',
    'ActorInsect', 'ActorInsectSmall', 'ActorMetal', 'ActorMetalArmoredPower', 'ActorMetalLarge',
    'ActorMetalSmall', 'ActorSkeleton', 'ActorSkin', 'ActorSkinLarge', 'ActorSkinSmall',
    'ArmorHeavy', 'ArmorLight', 'Arrow', 'Axe1Hand', 'Basket', 'Book', 'Bottle', 'BottleSmall',
    'Brick', 'Carpet', 'CeramicMedium', 'CHAIN', 'Cloth', 'ClothCushion', 'Coin', 'Concrete',
    'ConcreteStairs', 'debug', 'Dirt', 'DirtStairs', 'DLC03MaterialMetalBearTrap',
    'DLC03MaterialVRFloor', 'DLC04_Material_ArcadeSledBall_Ball',
    'DLC04_Material_ArcadeSledBall_Track', 'DLC04_Material_RubberBasketBall',
    'DLC05MaterialBallTrackBall', 'DLC05MaterialBallTrackMetal',
    'DLC05MaterialBallTrackMetalFunnel', 'DLC05MaterialBallTrackWood', 'Generic', 'Glass',
    'GlassStairs', 'Grass', 'GrassStairs', 'Gravel', 'Ice', 'Insect', 'Insect Wing',
    'InsectFloor', 'MaterialActorSynthGen1', 'MaterialBaseball', 'MaterialBodyBone',
    'MaterialCeramicCoffeeMug', 'MaterialClipboard', 'MaterialGroundDirtLeaves',
    'MaterialGroundGrassBush', 'MaterialGroundMetalA', 'MaterialGroundTileVinyl',
    'MaterialGroundTileVinylSanctuaryHills', 'MaterialMetalAuto', 'MaterialMetalBucket',
    'MaterialMetalCanTin', 'MaterialMetalChairFolding', 'MaterialMetalGasLine',
    'MaterialMetalGateVault', 'MaterialMetalLunchbox', 'MaterialMetalShoppingCart',
    'MaterialMetalSign', 'MaterialMetalStairs', 'MaterialMetalTray',
    'MaterialMetalVertibirdChassisLarge', 'MaterialMetalVertibirdChassisSmall',
    'MaterialMetalWeight', 'MaterialOtherBone', 'MaterialPaperBoxCardboard',
    'MaterialPaperBoxSmall', 'MaterialPaperMagazine', 'MaterialPlasticBin',
    'MaterialPlasticBowlingBall', 'MaterialPlasticLarge', 'MaterialPlasticTrafficCone',
    'MaterialRubberBall', 'MaterialRubberTire', 'MaterialStoneSubwayPillarLarge',
    'MaterialSubwayGate', 'MaterialWeaponBlockBladeMedium', 'MaterialWeaponBlockBladeSmall',
    'MaterialWeaponCasing', 'MaterialWeaponCasingMinigun', 'MaterialWeaponCasingPistol',
    'MaterialWeaponCasingRifle', 'MaterialWeaponCasingShotgun', 'MaterialWeaponMetalBlade1Hand',
    'MaterialWeaponMetalBlade1HandSmall', 'MaterialWeaponMetalGrenade', 'MaterialWeaponMetalMine',
    'MaterialWeaponPistol', 'MaterialWeaponRifle', 'MaterialWeaponRifleLarge',
    'MaterialWoodBoard', 'MaterialWoodBroom', 'MaterialWoodCrate', 'Meat', 'Metal', 'MetalBarrel',
    'MetalBarrelTrashCan', 'MetalBarrelTrashCanOffice', 'MetalHeavy', 'MetalHollow', 'MetalLight',
    'MetalSolid', 'MetalStairs', 'Mud', 'Organic', 'OrganicLarge', 'OtherParent', 'Paper',
    'Plastic', 'PotsPans', 'Sand', 'Sandbag', 'ShieldHeavy', 'ShieldLight', 'Skin', 'Snow',
    'SnowStairs', 'Stone', 'StoneAsStairs', 'StoneBoulderLarge', 'StoneBoulderMedium',
    'StoneBoulderSmall', 'StoneBroken', 'StoneBrokenStairs', 'StoneHeavy', 'StoneStairs', 'WARD',
    'Water', 'WaterPuddle', 'Weapon', 'WeaponBlade2Hand', 'WeaponBlockBlunt', 'WeaponBlunt1Hand',
    'WeaponBlunt2Hand', 'WeaponBowsStaves', 'Web', 'Wood', 'WoodAsStairs', 'WoodBarrel',
    'WoodHeavy', 'WoodLight', 'WoodStairs',
)

# What a new convex shape is made of when nothing says: vanilla's most common polytope
# material (4,002 shapes).
DEFAULT_MATERIAL = "Metal"


def bethesda_crc(name: str) -> int:
    """Bethesda's CRC32 of a lowercased name: reflected, init 0, no final XOR."""
    c = 0
    for b in name.lower().encode("utf-8"):
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
    return c


_BY_ID = {bethesda_crc(n): n for n in FO4_HAVOK_MATERIALS}


def material_id(name: str) -> int:
    """The userData for a material name, or for a hex value as material_name gives it."""
    name = name.strip()
    if name.lower().startswith("0x"):
        return int(name, 16) & 0xFFFFFFFF
    return bethesda_crc(name)


def material_name(value: int) -> str:
    """The material name for a userData value, or the value in hex if it has none."""
    return _BY_ID.get(value, f"0x{value:08X}")
