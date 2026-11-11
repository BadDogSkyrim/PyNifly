# Plan for generating crowd race variants

Problem: Past games made it (relatively) easy to combine tint layers to produce characters
with different looks. E.g. Skyrim had a base texture, a skin tone (color overlay only),
and then a set of slots - eye lower, eye upper, cheek, cheek lower, forehead, etc. - each
of which took a mask and a color. Different variants could be created by mixing different
layers and colors.

Starfield makes that much harder. The base color is a full-color layer, which has one
variant per skin tone; there are only two useable layers that can be overlayed on that.
Crowd NPCs don't even have that - they just have one layer that has to have all the tints
built in.

I want to be be able to make a bunch of crowd variants without having to build every
variant by hand.

# Solution

## Build off the base race

(Just thought of this, this may be best)

Look at the base race (FSFFoxRace for FSFFoxCrowdRace) for skin tone and tint layer
options. Look at dermaesthetic, ComplexionMask1, Complexion1, and Scar layers at least.
Run through every combination, picking one from each layer. Generate a aldebo texture from
the combination and store in the target directory (Textures\Actors\FSFFox\crowd for
foxes). Name can be `crowd_{variant}_sk{n}_color` or similar. (Humans and so far furries
don't need different male/female textures, which is weird.)

The crowd heads also need the mesh generated will all headparts. This is probably going to
happen manually for now. So I might create 10 crowd heads with different morphs and
different head parts (hair, and I think hats are included in crowd heads?). 

Then we'd want to create 10 * (the number of generated textures) crowd head records. Each
would take one of the head nifs and sub in one of the textures either with a material swap
in the plugin or by re-generating the nif with a different material. 

Then we'd populate the crowd head leveled lists with the new heads, at a given 
probability - up to 100%, meaning all crowd NPCs are replaced.
