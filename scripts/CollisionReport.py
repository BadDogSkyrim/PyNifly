"""
CollisionReport.py
------------------
Walk a directory tree and report NIF files that contain collision data.

For bhkNPCollisionObject (FO4 native physics), uses bhkPhysicsSystem.geometry
to decode CollisionShapes and reports each shape's type, name, vertex count,
and face count.

For older collision types (bhkNiCollisionObject etc.), reports the block type
chain (collision -> body -> shape).

Usage:
    python CollisionReport.py <directory> [directory ...]

Output goes to stdout; redirect to a file for large trees.
"""

import os
import sys
import logging
from pathlib import Path

# Path setup: this script lives in scripts/, project root is one level up.
_scripts_dir = Path(__file__).resolve().parent
_pyn_dir = _scripts_dir.parent / "io_scene_nifly"
if str(_pyn_dir) not in sys.path:
    sys.path.insert(0, str(_pyn_dir))

from pyn.pynifly import NifFile

# niflytools.py calls logging.basicConfig(level=DEBUG) and niflydll.py sets the
# pynifly logger to DEBUG during import.  Override both after import so batch
# scans aren't flooded with warnings and debug messages.
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("pynifly").setLevel(logging.ERROR)

log = logging.getLogger(__name__)


def _print(s: str) -> None:
    """Print a line, replacing unencodable characters rather than crashing."""
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))


def _shape_summary(s) -> str:
    """One-line description of a CollisionShape."""
    if s.shape_type == "compound":
        children = ", ".join(
            f"{c.shape_type}({len(c.verts)}v/{len(c.faces)}f)"
            for c in s.children
        )
        return f"compound[{children}]"
    return f"{s.shape_type} '{s.name}': {len(s.verts)}v / {len(s.faces)}f"


def _report_node(node_name: str, node, seen_ps_ids: set) -> list:
    """Return report lines for one node's collision, or [] if none."""
    try:
        coll = node.collision_object
    except Exception:
        return []
    if coll is None:
        return []

    ctype = coll.blockname
    lines = []

    if ctype == "bhkNPCollisionObject":
        ps = coll.physics_system
        if ps is None:
            lines.append(f"  {node_name}: {ctype} -> (no physics system)")
            return lines

        # A single bhkPhysicsSystem may be shared across several nodes.
        # Report its shapes only the first time we encounter it.
        ps_id = ps.id
        if ps_id in seen_ps_ids:
            lines.append(
                f"  {node_name}: {ctype} -> (shares physics system #{ps_id})"
            )
            return lines
        seen_ps_ids.add(ps_id)

        try:
            shapes = ps.geometry
        except Exception as exc:
            lines.append(f"  {node_name}: {ctype} -> ERROR decoding geometry: {exc}")
            return lines

        if not shapes:
            lines.append(f"  {node_name}: {ctype} -> (empty physics system)")
        else:
            lines.append(f"  {node_name}: {ctype} -> {len(shapes)} shape(s)")
            for s in shapes:
                lines.append(f"    {_shape_summary(s)}")

    else:
        # Older-style collision (bhkCollisionObject, bhkNiCollisionObject, etc.)
        parts = [ctype]
        try:
            body = coll.body
            if body is not None:
                parts.append(body.blockname)
                shape = getattr(body, "shape", None)
                if shape is not None:
                    parts.append(shape.blockname)
        except Exception:
            pass
        lines.append(f"  {node_name}: " + " -> ".join(parts))

    return lines


def report_nif(nif_path: Path) -> bool:
    """Print collision info for one NIF. Returns True if any collisions found."""
    try:
        nif = NifFile(str(nif_path))
    except Exception as exc:
        log.debug("%s: %s", nif_path, exc)
        return False

    # nif.nodes contains all named nodes. The root may or may not be among them.
    candidates = list(nif.nodes.items())
    root = nif.root
    if root is not None and root.name not in nif.nodes:
        candidates.insert(0, (root.name or "<root>", root))

    seen_ps_ids = set()
    output_lines = []
    for node_name, node in candidates:
        output_lines.extend(_report_node(node_name, node, seen_ps_ids))

    if output_lines:
        _print(str(nif_path))
        for line in output_lines:
            _print(line)
        return True
    return False


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {Path(sys.argv[0]).name} <directory> [directory ...]")
        sys.exit(1)

    total = 0
    with_collisions = 0
    for arg in sys.argv[1:]:
        root_dir = Path(arg)
        if not root_dir.is_dir():
            print(f"WARNING: not a directory: {root_dir}", file=sys.stderr)
            continue
        for dirpath, _dirs, files in os.walk(root_dir):
            for fname in sorted(files):
                if not fname.lower().endswith(".nif"):
                    continue
                total += 1
                if report_nif(Path(dirpath) / fname):
                    with_collisions += 1

    print(f"\n{with_collisions} of {total} NIF files have collisions.")


if __name__ == "__main__":
    main()
