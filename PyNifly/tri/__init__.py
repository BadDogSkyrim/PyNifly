# ***** BEGIN GPL LICENSE BLOCK *****
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <http://www.gnu.org/licenses/>
#
# ***** END GPL LICENCE BLOCK *****
# --------------------------------------------------------------------------
"""
Imports & exports tri files and the Bodyslide variant of tri files.

This module has no Blender dependencies. It just pulls the data out of the file and puts it 
in a python-friendly format.

Code adapted by Bad Dog from tri export/importer
Original author listed as:
"Core script by kapaer, modvertice support by deedes"
updated by anon (me) to work with newer blender ( version 2.63+), I hope
"""

from contextlib import suppress
import bpy
from .import_tri import ImportTRI


def nifly_menu_import_tri(self, context):
    self.layout.operator(ImportTRI.bl_idname, text="Tri file with pyNifly (.tri)")


def register():
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_tri)
    bpy.utils.register_class(ImportTRI)

    bpy.types.WindowManager.pynifly_last_import_path_tri = bpy.props.StringProperty(
        name="Last TRI Import Path",
        subtype='DIR_PATH',
        default=""
    )


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_tri)
    with suppress(RuntimeError):
        bpy.utils.unregister_class(ImportTRI)

    # Unregister last import path properties
    with suppress(AttributeError):
        del bpy.types.WindowManager.pynifly_last_import_path_tri