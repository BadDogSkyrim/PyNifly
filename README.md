# PyNifly
Export/Import tools between Blender and the Nif format, using Bodyslide/Outfit Studio's Nifly layer. Works with official Blender versions 4.0 and later; animation import and export require Blender 4.4 or later. Can handle nifs for Skyrim LE, Skyrim SE, and Fallout 4. Limited support for Fallout 76, Fallout New Vegas, and Fallout 3. Experimental support for Starfield.

Windows only.

Full documentation in the wiki.

**Features**

* Supports Skyrim LE, Skyrim SE, and FO4. Starfield is experimental.
* Handles tris and base mesh in one step. No need to separate UV seams or triangulate before exporting
* Handles expression and chargen tri files for Skyrim and FO4
* Import tris into an existing mesh or on their own
* Supports Bodyslide tri files on import and export for body morphs
* Handles multiple bodyweights in one step. Export _0 and _1 armor weights for Skyrim from a single mesh.
* Handles Skyrim and FO4 partitions and FO4 segments
* Handles FO4 dismemberment, including generating the cut offsets a body needs to come apart in game
* Handles skinned and unskinned meshes correctly. Exports head parts to SE correctly.
* Handles shaders correctly. Set them up in Blender and export.
* Nif properties live in named panels in Blender, not scattered custom attributes
* Handles collisions. Represents them as meshes in Blender, and exports them back --
  including Skyrim MOPP collision and FO4's native physics
* Handles animations. Direct import/export to hkx files for FO4, SE, and LE, and
  exports hkx skeletons for Skyrim and FO4
* Handles animated nifs
* Special handling for FO4 connect points on weapons, armor, and workshop parts.
* Handles trees and other switch/multibound nodes
* Starfield: meshes, materials, facial morphs, and facebones
* Import-and-forget. What you import will behave correctly on export without fiddling.

**Background**

Outfit Studio has working export/import for a bunch of the Bethesda games. I'm a modder and I've been using the niftools scripts for years, but I've started modding for Fallout 4 and there's no direct support for that at all.

BS/OS has separated much of their code to deal with nif files into a separate library, nifly. I've used this library and some additional OS code as the core of an export/import addon for Blender. 

My interest is primarily Skyrim, Skyrim SE, and Fallout 4 so I'll be focusing on supporting those games. 

**Credits**

_Core technology_

- Ousnius for the nifly layer PyNifly is based on

_Critical information on nif/HKX encoding_

- Candoran2 
- DagobaKing
- Nikolivanov
- Nitaigao
- PredatorCZ

_Contributions to the tool_

- bitbanger
- jgernandt 
- Reddraconi
- ShroomTip
- ZenithVal
