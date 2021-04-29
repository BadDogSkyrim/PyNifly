# PyNifly
Export/Import tools between Blender and the Nif format, using Bodyslide/Outfit Studio's Nifly layer

**Background**

Outfit Studio has working export/import for essentially all Bethesda games using nif files. I'm a modder and I've been using the niftools scripts for years, but I've started modding for Fallout 4 and there's no direct support for that at all.

BS/OS has separated much of their code to deal with nif files into a separate library, nifly. I've used this library and some additional OS code as the core of an export/import addon for Blender. 

My interest is primarily Skyrim, Skyrim SE, and Fallout 4 so I'll be focusing on supporting those games. But the underlying code supports FO3 and FONV as well, and I'll support them as I can.

**Status**

This is very early days. What works:
* Import/Export of basic models to and from Skyrim and FO4 nifs. 
* Import/export of skinned models using standard skeleton bones.
* Shape keys to export variants of a model (male and female, or Skyrim's 0 and 1 weights)

What should work but doesn't:
* Import/Export of models rigged to non-standard bones. Something to do with translations/rotations.
* Handling the different options for skinning models. FO4 and Skyrim both reposition body parts around the origin, and that works. But there are other ways of rigging models and I'm pretty sure not all the variants work.

Not yet implemented (but on deck):
* Tri files
* Partitions/segments
* Fallout 4's facebones files. I want to support them, but there's a bunch of fancy nodes in there that I don't understand.

Not yet implemented (and maybe never, unless I get a lot of help/advice):
* Animations. A lot of Skyrim's statics have animations built into the nifs.
* Collisions
