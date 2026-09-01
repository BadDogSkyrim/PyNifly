"""Starfield external .mesh path policy: where a BSGeometry's geometry file goes, and what it's
called.

Pure path handling -- no Blender, no DLL -- so the rules are testable at the pyn level.

Starfield .mesh paths are exactly ONE directory deep. All 364,377 vanilla meshes are
``<20hex>\\<20hex>`` (every name exactly 41 characters), Outfit Studio writes
``NifName\\ShapeName_Index``, and PyNifly's own shipping assets use ``FSF\\LykaiosMaleHead``. No
tool has ever written a deeper path, so we don't either -- see `resolve_mesh_name`.

The stored path is the verbatim ``meshName``: no ``geometries\\`` root and no ``.mesh``
extension, both of which the caller adds when resolving an output file.
"""

import hashlib
import re

# The meshName string must be <= 46 characters or the shape renders invisible in game. Documented
# in the ExoRace author's "Creating a Playable Race" guide and recorded in the Bethesda Library
# (Starfield -> Meshes). Never truncate to fit -- a truncated path resolves to nothing, which is
# the same invisible shape.
MESH_NAME_MAX = 46

# Vanilla names are two 20-hex-character components. Generated names match that shape: 41
# characters total, leaving room for the facebones '_fb' suffix under the cap.
HASH_COMPONENT_LEN = 20

SEP = '\\'

# Characters illegal in a Windows filename. Note ':' in particular: Starfield block names are
# 'Name:index' (e.g. 'MaleHead:0'), and writing a .mesh to a path containing ':' silently
# creates an NTFS alternate data stream instead of a real file -- the geometry then loads
# nowhere and the shape is invisible in-game/CK.
_ILLEGAL_FILENAME_CHARS = '<>:"/\\|?*'

_DUP_SUFFIX = re.compile(r'\.\d{3}$')


def sanitize_mesh_component(name):
    """Make `name` safe as a single .mesh path component: strip Blender's '.001'/'.002'
    duplicate-name suffix, replace any character illegal in a Windows filename (notably ':'
    from Starfield's 'Name:index' block names) with '_', and trim trailing dots/spaces. Never
    returns empty (falls back to 'mesh')."""
    name = _DUP_SUFFIX.sub('', name)  # Blender appends '.001' etc. to disambiguate names
    cleaned = ''.join('_' if (c in _ILLEGAL_FILENAME_CHARS or ord(c) < 32) else c
                      for c in name)
    cleaned = cleaned.rstrip('. ')
    return cleaned or 'mesh'


def generate_mesh_name(seed_path, obj_name):
    """Generate a vanilla-shaped ``<20hex>\\<20hex>`` meshName for a shape that has no stored
    path, seeded from `seed_path` (the .blend file, or the export nif when the .blend is unsaved)
    and the object's **raw** Blender name.

    Raw, '.001' and all, on purpose: it's what makes freshly split objects distinct before the
    author renames them, so Head/Head.001/Head.002 never share one .mesh. `sanitize_mesh_component`
    strips '.001' -- correct for a name a human typed, wrong as a uniqueness key.

    The game neither computes nor verifies this name (the only hashing in the Starfield pipeline
    is the CRC-32 resource id for materials), so the digest is ours to choose. Including
    `seed_path` keeps two mods that each contain a 'Head' from colliding in the shared
    ``geometries\\`` tree.
    """
    seed = f"{str(seed_path).lower()}\n{obj_name}"
    digest = hashlib.sha1(seed.encode('utf-8')).hexdigest()
    return (digest[:HASH_COMPONENT_LEN] + SEP
            + digest[HASH_COMPONENT_LEN:HASH_COMPONENT_LEN * 2])


def resolve_mesh_name(stored, obj_name, seed_path):
    """The meshName to write for a shape, from its stored `mesh_path` property.

    - empty            -> a generated ``<20hex>\\<20hex>`` (see `generate_mesh_name`)
    - ``FSF``          -> ``FSF\\<obj_name sanitized>``
    - ``FSF\\WolfHead`` -> verbatim; the author owns keeping it distinct

    Raises ValueError if `stored` is more than one directory deep. We don't know that the engine
    rejects it, but nothing in vanilla or the tooling has ever written such a path, one level does
    everything we need, and the failure mode would be an invisible shape -- the class of bug this
    project keeps paying for.
    """
    stored = (stored or '').replace('/', SEP).strip()
    if not stored:
        return generate_mesh_name(seed_path, obj_name)

    parts = [p for p in stored.split(SEP) if p]
    if len(parts) > 2:
        raise ValueError(
            f"Starfield .mesh paths are one directory deep; '{stored}' has more. "
            f"Use '<folder>' to name the file after the shape, or '<folder>\\<name>'.")
    if len(parts) == 2:
        return parts[0] + SEP + parts[1]
    return parts[0] + SEP + sanitize_mesh_component(obj_name)


def mesh_name_error(name):
    """Return a message if `name` can't be used as a meshName, else None. Currently the
    46-character cap, which silently makes the shape invisible in game."""
    if len(name) > MESH_NAME_MAX:
        return (f"Starfield .mesh path '{name}' is {len(name)} characters; the limit is "
                f"{MESH_NAME_MAX} and a longer path makes the shape invisible in game. "
                f"Shorten the object or folder name.")
    return None


def unique_mesh_name(name, used):
    """`name`, or `name_1` / `name_2` / ... if `used` (a path -> owner mapping) already claims it.

    Generated names can't collide -- distinct objects digest differently -- but explicit ones can,
    when the author typed the same path on two shapes or two objects sanitize alike. Silently
    letting the second write win produces a nif that loads and renders the wrong geometry, so the
    caller disambiguates and warns.
    """
    if name not in used:
        return name
    n = 1
    while f"{name}_{n}" in used:
        n += 1
    return f"{name}_{n}"
