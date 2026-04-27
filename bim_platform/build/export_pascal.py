"""
build.export_pascal — convert a BuildingSpec to Pascal Editor's save format.

The format target is Pascal's "Save Build" output (NOT their published Zod
schemas, which describe internal node types but don't exactly match the
on-disk format).

Top-level shape:
  {
    "nodes": { id: NodeBlob },
    "rootNodeIds": [ "site_xxx" ]
  }

Each node has: id, type, object: "node", visible: bool, parentId, metadata.
Plus type-specific fields. Notable details:

  Site:     polygon: { type: "polygon", points: [[x,z], ...] }
            children: [<full nested Building>]   ← yes, nested object
  Building: position: [x,y,z], rotation: [x,y,z], children: ["level_id"]
  Level:    level: 0                              ← integer index
            children: [wall_ids..., slab_ids..., ceiling_ids...]
  Wall:     start: [x, z], end: [x, z]
            name, backSide: "exterior"|"interior", frontSide: same
  Slab:     polygon: [[x,z], ...]
            holes, holeMetadata, elevation, autoFromWalls
  Ceiling:  polygon, height, holes, holeMetadata, autoFromWalls

Coordinate system in Pascal save files:
  +X east, +Z south, +Y up (Three.js convention).
BuildingSpec uses (+X east, +Y north, +Z up). The exporter swaps so
north (+Y) becomes -Z, keeping orientation consistent.
"""
from __future__ import annotations
import logging
import secrets
import string

from ..schemas.building_spec import BuildingSpec

logger = logging.getLogger(__name__)


_ID_CHARS = string.ascii_lowercase + string.digits


def _gen_id(prefix: str) -> str:
    """Pascal IDs: '<type>_<16-char base36>'."""
    suffix = "".join(secrets.choice(_ID_CHARS) for _ in range(16))
    return f"{prefix}_{suffix}"


def _xy_to_xz(x: float, y: float) -> list[float]:
    """BuildingSpec (+X east, +Y north) → Pascal (+X east, +Z south)."""
    return [x, -y]


# ── Default furniture per space_type ──────────────────────────────────
DEFAULT_FURNITURE: dict[str, list[tuple[str, str, float, float, float]]] = {
    "living_room": [
        ("sofa.modern_3seat", "furniture", 2.20, 0.90, 0.80),
        ("coffee_table.rect", "furniture", 1.20, 0.60, 0.40),
        ("tv_unit.wall",      "furniture", 1.80, 0.40, 0.55),
    ],
    "bedroom": [
        ("bed.queen",         "furniture", 1.60, 2.10, 0.55),
        ("nightstand.simple", "furniture", 0.50, 0.40, 0.55),
        ("wardrobe.tall",     "furniture", 1.20, 0.60, 2.10),
    ],
    "master_bedroom": [
        ("bed.king",          "furniture", 1.95, 2.10, 0.55),
        ("nightstand.simple", "furniture", 0.50, 0.40, 0.55),
        ("nightstand.simple", "furniture", 0.50, 0.40, 0.55),
        ("dresser.modern",    "furniture", 1.50, 0.55, 0.85),
    ],
    "kitchen": [
        ("counter.base",      "furniture", 2.40, 0.60, 0.90),
        ("stove.range",       "fixture",   0.60, 0.60, 0.90),
        ("fridge.tall",       "fixture",   0.70, 0.70, 1.80),
    ],
    "dining_room": [
        ("dining_table.rect_6", "furniture", 1.80, 0.90, 0.75),
    ],
    "bathroom": [
        ("toilet.standard",   "fixture",   0.40, 0.65, 0.80),
        ("sink.pedestal",     "fixture",   0.55, 0.45, 0.85),
        ("shower.rect",       "fixture",   0.90, 0.90, 2.00),
    ],
    "home_office": [
        ("desk.rect",         "furniture", 1.50, 0.70, 0.75),
        ("chair.office",      "furniture", 0.60, 0.60, 1.00),
    ],
    "open_office": [
        ("workstation.systems", "furniture", 1.50, 1.50, 1.20),
        ("workstation.systems", "furniture", 1.50, 1.50, 1.20),
        ("workstation.systems", "furniture", 1.50, 1.50, 1.20),
        ("workstation.systems", "furniture", 1.50, 1.50, 1.20),
    ],
    "conference_room": [
        ("conference_table.10person", "furniture", 3.50, 1.20, 0.75),
    ],
    "private_office": [
        ("desk.executive",    "furniture", 1.80, 0.80, 0.75),
        ("chair.office",      "furniture", 0.60, 0.60, 1.00),
    ],
}


# ── Helpers to construct each node type ───────────────────────────────
def _site_polygon(extents_x: float, extents_z: float, padding: float = 5.0) -> dict:
    """Site bounding polygon, padded around the building footprint."""
    half_x = extents_x / 2 + padding
    half_z = extents_z / 2 + padding
    return {
        "type": "polygon",
        "points": [
            [-half_x, -half_z],
            [ half_x, -half_z],
            [ half_x,  half_z],
            [-half_x,  half_z],
        ],
    }


def _make_wall(level_id: str, start_xz: list[float], end_xz: list[float],
               name: str, exterior: bool) -> dict:
    """One wall node. Pascal stores exterior/interior on each side."""
    return {
        "id": _gen_id("wall"),
        "name": name,
        "type": "wall",
        "object": "node",
        "start": start_xz,
        "end": end_xz,
        "visible": True,
        "backSide":  "exterior" if exterior else "interior",
        "frontSide": "interior",
        "children": [],
        "metadata": {},
        "parentId": level_id,
    }


def _make_slab(level_id: str, polygon_xz: list[list[float]],
               name: str, elevation: float = 0.05) -> dict:
    return {
        "id": _gen_id("slab"),
        "name": name,
        "type": "slab",
        "object": "node",
        "polygon": polygon_xz,
        "holes": [],
        "holeMetadata": [],
        "elevation": elevation,
        "autoFromWalls": False,
        "visible": True,
        "metadata": {},
        "parentId": level_id,
    }


def _make_ceiling(level_id: str, polygon_xz: list[list[float]],
                  name: str, height: float = 2.5) -> dict:
    return {
        "id": _gen_id("ceiling"),
        "name": name,
        "type": "ceiling",
        "object": "node",
        "polygon": polygon_xz,
        "holes": [],
        "holeMetadata": [],
        "height": height,
        "autoFromWalls": False,
        "visible": True,
        "children": [],
        "metadata": {},
        "parentId": level_id,
    }


# ── Main exporter ─────────────────────────────────────────────────────
def export_to_pascal(spec: BuildingSpec) -> dict:
    """
    Convert a BuildingSpec to Pascal Editor's save-file format.

    Returns a plain dict suitable for json.dumps(). The shape matches
    what Pascal's "Load Build" expects.
    """
    nodes: dict[str, dict] = {}

    # Building footprint extents, used to center on Pascal's origin.
    if spec.floors and any(f.spaces for f in spec.floors):
        max_w = max((s.x + s.width)  for f in spec.floors for s in f.spaces)
        max_d = max((s.y + s.depth)  for f in spec.floors for s in f.spaces)
    else:
        max_w = max_d = 0.0
    cx, cy = max_w / 2.0, max_d / 2.0

    # ── Building node (will be both referenced by id AND nested in site) ──
    building_id = _gen_id("building")
    building_block = {
        "id": building_id,
        "type": "building",
        "object": "node",
        "visible": True,
        "children": [],   # filled below
        "metadata": {
            "name": spec.name,
            "typology": spec.typology_key,
            "style": spec.metadata.get("architectural_style") or "",
        },
        "parentId": None,
        "position": [0, 0, 0],
        "rotation": [0, 0, 0],
    }

    # ── Levels and their contents ────────────────────────────────────
    level_ids: list[str] = []
    for floor_idx, floor in enumerate(spec.floors):
        level_id = _gen_id("level")
        level_ids.append(level_id)
        level_children: list[str] = []

        for space in floor.spaces:
            x0 = space.x - cx
            x1 = space.x + space.width - cx
            y0 = space.y - cy
            y1 = space.y + space.depth - cy

            sw = _xy_to_xz(x0, y0)
            se = _xy_to_xz(x1, y0)
            ne = _xy_to_xz(x1, y1)
            nw = _xy_to_xz(x0, y1)

            polygon = [sw, se, ne, nw]

            slab = _make_slab(
                level_id, polygon,
                name=f"{space.name} Slab",
                elevation=floor.elevation + 0.05,
            )
            nodes[slab["id"]] = slab
            level_children.append(slab["id"])

            ceiling = _make_ceiling(
                level_id, polygon,
                name=f"{space.name} Ceiling",
                height=space.height or floor.height or 2.7,
            )
            nodes[ceiling["id"]] = ceiling
            level_children.append(ceiling["id"])

            # Four walls of this rectangular space
            for label, a, b in [
                ("south wall", sw, se),
                ("east wall",  se, ne),
                ("north wall", ne, nw),
                ("west wall",  nw, sw),
            ]:
                wall = _make_wall(
                    level_id, a, b,
                    name=f"{space.name} {label}",
                    exterior=space.exterior,
                )
                nodes[wall["id"]] = wall
                level_children.append(wall["id"])

        nodes[level_id] = {
            "id": level_id,
            "type": "level",
            "object": "node",
            "level": floor_idx,
            "visible": True,
            "children": level_children,
            "metadata": {"name": floor.name},
            "parentId": building_id,
        }

    building_block["children"] = level_ids
    nodes[building_id] = building_block

    # ── Site (root) ─────────────────────────────────────────────────
    site_id = _gen_id("site")
    nodes[site_id] = {
        "id": site_id,
        "type": "site",
        "object": "node",
        "polygon": _site_polygon(max_w, max_d),
        "visible": True,
        # Pascal saves nest the full building inline here, mirror it.
        "children": [building_block],
        "metadata": {},
        "parentId": None,
    }

    return {
        "nodes": nodes,
        "rootNodeIds": [site_id],
    }
