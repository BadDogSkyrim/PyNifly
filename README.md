# PyNifly
Export/Import tools between Blender and the Nif format, using Bodyslide/Outfit Studio's Nifly layer. Works with official Blender versions 2.9 and higher. Can handle nifs for Skyrim LE, Skyrim SE, Fallout 4, and Fallout 76, Fallout New Vegas, and Fallout 3.

Full documentation in the wiki.

**Features**

* Supports FO4, Skyrim LE, Skyrim SE
* Handles tris and base mesh in one step. No need to separate UV seams or triangulate before exporting
* Handles expression and chargen tri files for Skyrim and FO4
* Import tris into an existing mesh or on their own
* Supports Bodyslide tri files on import and export for body morphs
* Handles multiple bodyweights in one step. Export _0 and _1 armor weights for Skyrim from a single mesh.
* Handles Skyrim and FO4 partitions and FO4 segments
* Handles skinned and unskinned meshes correctly. Exports head parts to SE correctly.
* Handles shaders correctly. Set them up in Blender and export.
* Import-and-forget. What you import will behave correctly on export without fiddling.

**Background**

Outfit Studio has working export/import for a bunch of the Bethesda games. I'm a modder and I've been using the niftools scripts for years, but I've started modding for Fallout 4 and there's no direct support for that at all.

BS/OS has separated much of their code to deal with nif files into a separate library, nifly. I've used this library and some additional OS code as the core of an export/import addon for Blender. 

My interest is primarily Skyrim, Skyrim SE, and Fallout 4 so I'll be focusing on supporting those games. 

**Status**

Import/Export of most nifs is complete works well. 

Import/Export of animations is currently under development.

Import/Export of Skyrim collisions is complete except for MOPP collisions. Those may never happen. Fallout 4 collisions are not implemented but there's a tool that ships with Fallout to help with that. Check the Collisions page of the wiki (https://github.com/BadDogSkyrim/PyNifly/wiki/Collisions) for more.
