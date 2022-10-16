# PyNifly
Export/Import tools between Blender and the Nif format, using Bodyslide/Outfit Studio's Nifly layer. Works with Blender 2.9 and 3.x. Can handle nifs for Skyrim LE, SE, Fallout 4, and FO76.

Full documentation in the wiki.

**Features**

* Supports FO4, Skyrim LE, Skyrim SE
* Handles tris and base mesh in one step. No need to separate UV seams or triangulate before exporting
* Handles expression and chargen tri files for Skyrim and FO4
* Import tris into an existing mesh or on their own
* Supports Bodyslide tri files on import and export for body morphs
* Handles multiple bodyweights in one step. Export _0 and _1 armor weights for Skyrim from a single mesh.
* Handles Skyrim and FO4 partitions and also FO4 segments
* Handles skinned and unskinned meshes correctly. Exports head parts to SE correctly.
* Handles shaders correctly. Set them up in Blender and export.
* Import-and-forget. What you import will behave correctly on export without fiddling.

**Background**

Outfit Studio has working export/import for a bunch of the Bethesda games. I'm a modder and I've been using the niftools scripts for years, but I've started modding for Fallout 4 and there's no direct support for that at all.

BS/OS has separated much of their code to deal with nif files into a separate library, nifly. I've used this library and some additional OS code as the core of an export/import addon for Blender. 

My interest is primarily Skyrim, Skyrim SE, and Fallout 4 so I'll be focusing on supporting those games. 

**Status**

This is a work in progress. Latest state of the world is documented in the wiki.

Current development involves supporting collisions.

Not yet implemented (and maybe never, unless I get a lot of help/advice):
* Animations. A lot of Skyrim's statics have animations built into the nifs.
