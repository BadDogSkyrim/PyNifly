#bl_info = {
#    "name": "Rename bones and vertex groups",
#    "description": "Renames a armature's bones from PyNifly convention to NifTools; also does vertex groups of associated objects",
#    "blender": (3, 0, 0),
#    "author": "Bad Dog",
#    "category": "Object",
#}

import bpy
from niflytools import skyrimDict


class PynRenamerNifTools(bpy.types.Operator):
    """Rename bones from PyNifly to NifTools"""
    bl_idname = "object.pynifly_rename_niftools"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Rename bones to NifTools"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.

        # The original script
        scene = context.scene
        for obj in scene.objects:
            if obj.type == "ARMATURE":
                for b in obj.data.bones:
                    try:
                        b.name = skyrimDict.byBlender[b.name].niftools
                        print(f"Renamed {b.name}")
                    except:
                        pass
                try:
                    obj.data.niftools.axis_forward = "Y"
                    obj.data.niftools.axis_up = "Z"
                except:
                    pass

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

def nifly_menu_rename_niftools(self, context):
    self.layout.operator(PynRenamerNifTools.bl_idname)



