"""
Import/Export Settings
"""
from dataclasses import dataclass


@dataclass
class ImportSettings:
    # Rename bones to conform to blender's conventions. User preference. Export should
    # follow import, or armature, or be set by user.
    rename_bones: bool = True

    # Rename bones to conform to NifTools' conventions. User preference. Export should
    # follow import, or armature, or be set by user.
    rename_bones_niftools: bool = False

    # Rotate bones to match the limbs in humanoid skeletons. User preference. Export
    # should follow import of armature.
    rotate_bones_pretty: bool = False

    # Use Blender's natural scale and coordinate system. User preference. Export should
    # follow import.
    blender_xf: bool = False

    # import only

    # Create additional bones to fill in missing bones in the nif, using our reference
    # skeletons. Generally not useful for non-human skeletons. 
    create_bones: bool = True

    # Import tri files that match nif files when found. Per-import user preference. 
    import_tris: bool = True

    # Import animations embedded in a nif file. Per-import user preference. 
    import_animations: bool = True

    # If a mesh is selected, import the nif as a shape key on that mesh if possible.
    # Per-import preference.
    import_shapekeys: bool = True

    # Skin the imported mesh by rigging it to the armature found in the nif. Per-import
    # preference.
    apply_skinning: bool = True

    # When a connect point has an associated editor marker, import the editor marker and
    # use it to represent the connect point. Per-import preference.
    smart_editor_markers: bool = True

    # Create a new collection for the imported objects. Per-import preference.
    create_collection: bool = False

    # Only import meshes from the nif. Per-import preference.
    mesh_only: bool = False

    # Import collisions from the nif. Per-import preference.
    import_collisions: bool = True

    # Create armature from the pose position in the nif (thie NiNode transforms) rather
    # than the rest position (the bone transforms). Per-import preference.
    import_pose: bool = False

    # Reference skeleton to use for missing bones when create_bones is enabled.
    reference_skeleton: str = ""


@dataclass
class ExportSettings:
    # Rename bones to conform to blender's conventions. User preference. Export should
    # follow import, or armature, or be set by user.
    rename_bones: bool = True

    # Rename bones to conform to NifTools' conventions. User preference. Export should
    # follow import, or armature, or be set by user.
    rename_bones_niftools: bool = False

    # Rotate bones to match the limbs in humanoid skeletons. User preference. Export
    # should follow import of armature.
    rotate_bones_pretty: bool = False

    # Use Blender's natural scale and coordinate system. User preference. Export should
    # follow import.
    blender_xf: bool = False

    # Export only

    # Target game. Usually should match the import, or be implied by armature bones,
    # object partitions, or the shader. Can be set by user. Export only.
    game: str = "FO4"

    # Export the mesh and armature in posed position. Set by user, but can be remembered
    # from one export to the next. Export only.
    export_pose: bool = False

    # Keep the armature's bone hierarchy in the exported nif. Must be set by user, should
    # be sticky. Export only.
    preserve_hierarchy: bool = False

    # Extension to add to chargen tri files. Export only.
    chargen_extension: str = "chargen"

    # Write bodytri data to the nif if bodytri shape keys are found.
    write_bodytri: bool = True

    # Apply modifiers to meshes when exporting. 
    export_modifiers: bool = False

    # Export Blender animations on the exported objects.
    export_animations: bool = True

    # Export vertex color/alpha data if any.
    export_colors: bool = True


# Custom properties that store import/export settings on objects.
PYN_BLENDER_XF_PROP = "PYN_BLENDER_XF"
PYN_GAME_PROP = "PYN_GAME"
PYN_PRESERVE_HIERARCHY_PROP = "PYN_PRESERVE_HIERARCHY"
PYN_RENAME_BONES_NIFTOOLS_PROP = 'PYN_RENAME_BONES_NIFTOOLS'
PYN_RENAME_BONES_PROP = "PYN_RENAME_BONES"
PYN_ROTATE_BONES_PRETTY_PROP = "PYN_ROTATE_BONES_PRETTY"
PYN_WRITE_BODYTRI_ED_PROP = "PYN_WRITE_BODYTRI_ED"
PYN_EXPORT_POSE_PROP = "PYN_EXPORT_POSE"
PYN_CHARGEN_EXT_PROP = "PYN_CHARGEN_EXT"

