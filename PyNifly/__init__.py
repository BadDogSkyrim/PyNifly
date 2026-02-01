"""NIF format export/import for Blender using Nifly"""

# Copyright © 2021, Bad Dog.

bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (4, 5, 0),
    "version": (22, 2, 0),   
    "location": "File > Import-Export",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

from . import nif
from . import tri
from . import hkx
from . import kf

def register():
    hkx.register()
    kf.register()
    nif.register()
    tri.register()

def unregister():
    hkx.unregister()
    kf.unregister()
    nif.unregister()
    tri.unregister()