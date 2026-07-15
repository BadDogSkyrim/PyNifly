"""Starfield morph.dat import/export as Blender shape keys.

morph.dat holds named per-vertex position deltas (chargen phenotype sliders and performance
FACS expression morphs). The pyn.sf_morph codec is Blender-independent; these operators bind it
to Blender shape keys on the active mesh.
"""
from contextlib import suppress

_needs_reload = "bpy" in locals()

import bpy
from . import import_sfmorph, export_sfmorph

if _needs_reload:
    import importlib
    import_sfmorph = importlib.reload(import_sfmorph)
    export_sfmorph = importlib.reload(export_sfmorph)

from .import_sfmorph import ImportSFMorph
from .export_sfmorph import ExportSFMorph


def nifly_menu_import_sfmorph(self, context):
    self.layout.operator(ImportSFMorph.bl_idname, text="Starfield morph with pyNifly (.dat)")


def nifly_menu_export_sfmorph(self, context):
    self.layout.operator(ExportSFMorph.bl_idname, text="Starfield morph with pyNifly (.dat)")


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_sfmorph)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_sfmorph)
    bpy.utils.register_class(ImportSFMorph)
    bpy.utils.register_class(ExportSFMorph)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_sfmorph)
    bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_sfmorph)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ImportSFMorph)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ExportSFMorph)
