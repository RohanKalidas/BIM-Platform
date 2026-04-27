"""
build.export.pascal — convert a BuildingSpec to a PascalScene.

Pascal's coordinate system uses Y-up (Three.js convention); BuildingSpec
uses Z-up. The exporter swaps Y↔Z when emitting wall/slab points.

Mapping rules:
  Brief.name                  → SiteNode label, BuildingNode label
  Layout.floors[i]            → LevelNode
  Layout.floors[i].spaces[j]  → ZoneNode (informational tag) +
                                4 WallNodes outlining the rectangle +
                                1 SlabNode for the floor
  Space.doors                 → ItemNode (itemType="door") parented to wall
  Space.windows               → ItemNode (itemType="window") parented to wall
  Brief.program furniture     → ItemNode (itemType="furniture") parented to slab
  Facade.roof_type            → RoofNode covering the building footprint

Walls between adjacent spaces are deduplicated: if Space A's east wall
coincides with Space B's west wall, only one wall is emitted (party wall).
For now the exporter is conservative and emits per-room walls; dedup is
a future optimization.

Furniture placement uses heuristics from BIM Studio's fixture_placement.py
(centered with margins) but Pascal's spatial grid will reject collisions
so we don't have to be perfect — Pascal will nudge or reject.
"""
from __future__ import annotations
import logging
import math
from typing import Optional

from ..schemas.building_spec import BuildingSpec
from ..schemas.layout import Floor, Space, Door, Window
from ..schemas.pascal_scene import (
    PascalScene, SiteNode, BuildingNode, LevelNode,
    WallNode, SlabNode, RoofNode, ItemNode, ZoneNode, _gen_id,
)

logger = logging.getLogger(__name__)


# Default furniture per space_type. Each entry: (modelKey, itemType, w, d, h).
# Used when the BuildingSpec doesn't provide explicit fixtures. Best-effort —
# items get placed in plausible positions, Pascal's collision system trims.
DEFAULT_FURNITURE: dict[str, list[tuple[str, str, float, float, float]]] = {
    "living_room": [
        ("sofa.modern_3seat", "furniture", 2.20, 0.90, 0.80),
        ("coffee_table.rect", "furniture", 1.20, 0.60, 0.40),
        ("tv_unit.wall", "furniture", 1.80, 0.40, 0.55),
    ],
    "bedroom": [
        ("bed.queen", "furniture", 1.60, 2.10, 0.55),
        ("nightstand.simple", "furniture", 0.50, 0.40, 0.55),
        ("wardrobe.tall", "furniture", 1.20, 0.60, 2.10),
    ],
    "master_bedroom": [
        ("bed.king", "furniture", 1.95, 2.10, 0.55),
        ("nightstand.simple", "furniture", 0.50, 0.40, 0.55),
        ("nightstand.simple", "furniture", 0.50, 0.40, 0.55),
        ("dresser.modern", "furniture", 1.50, 0.55, 0.85),
    ],
    "kitchen": [
        ("counter.base", "furniture", 2.40, 0.60, 0.90),
        ("stove.range", "fixture", 0.60, 0.60, 0.90),
        ("fridge.tall", "fixture", 0.70, 0.70, 1.80),
    ],
    "dining_room": [
        ("dining_table.rect_6", "furniture", 1.80, 0.90, 0.75),
    ],
    "bathroom": [
        ("toilet.standard", "fixture", 0.40, 0.65, 0.80),
        ("sink.pedestal", "fixture", 0.55, 0.45, 0.85),
        ("shower.rect", "fixture", 0.90, 0.90, 2.00),
    ],
    "home_office": [
        ("desk.rect", "furniture", 1.50, 0.70, 0.75),
        ("chair.office", "furniture", 0.60, 0.60, 1.00),
    ],
    # Commercial
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
        ("desk.executive", "furniture", 1.80, 0.80, 0.75),
        ("chair.office", "furniture", 0.60, 0.60, 1.00),
    ],
}


def export_to_pascal(spec: BuildingSpec) -> PascalScene:
    """
    Convert a BuildingSpec to a PascalScene ready for JSON serialization.

    Returns a PascalScene whose .to_json_dict() can be json.dumped and
    imported by Pascal Editor's JSON import.
    """
    scene = PascalScene()

    # ── Site ─────────────────────────────────────────────────────────
    site = SiteNode(id=_gen_id("site"), metadata={"name": spec.name})
    scene.add(site)
    scene.rootNodeIds.append(site.id)

    # ── Building ─────────────────────────────────────────────────────
    building = BuildingNode(
        id=_gen_id("building"),
        parentId=site.id,
        metadata={
            "name": spec.name,
            "typology": spec.typology_key,
            "style": spec.metadata.get("architectural_style"),
        },
    )
    scene.add(building)
    site.children.append(building.id)

    # ── Levels ───────────────────────────────────────────────────────
    palette = spec.metadata.get("style_palette", {})
    floor_color = palette.get("floor", "#E8DCC4")
    wall_color = palette.get("ext_wall", "#F0E8D6")
    int_wall_color = palette.get("int_wall", wall_color)
    roof_color = palette.get("roof", "#3A3A3A")

    max_x = 0.0
    max_z = 0.0  # Pascal's "depth" axis = our +Y in BuildingSpec; converted

    for floor in spec.floors:
        level = LevelNode(
            id=_gen_id("level"),
            parentId=building.id,
            elevation=floor.elevation,
            height=floor.height or 2.7,
            metadata={"name": floor.name},
        )
        scene.add(level)
        building.children.append(level.id)

        for space in floor.spaces:
            _emit_space(scene, level, space, floor,
                        wall_color, int_wall_color, floor_color)
            # Track building extents for the roof
            extent_x = space.x + space.width
            extent_z = space.y + space.depth
            if extent_x > max_x:
                max_x = extent_x
            if extent_z > max_z:
                max_z = extent_z

    # ── Roof ─────────────────────────────────────────────────────────
    facade_meta = spec.metadata.get("exterior_features", [])
    roof_style_str = "flat"
    pitch_deg = 0.0
    # Best-effort roof inference: if facade has a gable feature, pitch the roof
    for f in facade_meta:
        if f.get("type") == "gable":
            roof_style_str = "gable"
            pitch_deg = 30.0
            break
        elif f.get("type") in ("hip_roof", "hip"):
            roof_style_str = "hip"
            pitch_deg = 25.0
            break
    # Override from explicit metadata if present
    rt = spec.metadata.get("roof_type")
    if rt in ("flat", "gable", "hip", "shed"):
        roof_style_str = rt
        pitch_deg = spec.metadata.get("roof_pitch_deg", 30.0 if rt != "flat" else 0.0)

    if spec.floors:
        top_floor = spec.floors[-1]
        roof_elevation = top_floor.elevation + (top_floor.height or 2.7)
        roof = RoofNode(
            id=_gen_id("roof"),
            parentId=building.id,
            # Pascal: x and z are horizontal; y is up
            points=[
                (0.0, 0.0),
                (max_x, 0.0),
                (max_x, max_z),
                (0.0, max_z),
            ],
            style=roof_style_str,
            pitch=pitch_deg,
            color=roof_color,
            metadata={"elevation": roof_elevation},
        )
        scene.add(roof)
        building.children.append(roof.id)

    return scene


def _emit_space(
    scene: PascalScene,
    level: LevelNode,
    space: Space,
    floor: Floor,
    ext_wall_color: str,
    int_wall_color: str,
    floor_color: str,
) -> None:
    """Emit walls + slab + zone tag + furniture for a single Space."""
    x0, z0 = space.x, space.y
    x1 = space.x + space.width
    z1 = space.y + space.depth
    height = space.height or floor.height or 2.7

    # ── Slab ─────────────────────────────────────────────────────────
    slab = SlabNode(
        id=_gen_id("slab"),
        parentId=level.id,
        points=[(x0, z0), (x1, z0), (x1, z1), (x0, z1)],
        thickness=0.15,
        color=floor_color,
        metadata={"space": space.name},
    )
    scene.add(slab)
    level.children.append(slab.id)

    # ── Walls (4 sides) ──────────────────────────────────────────────
    # Each wall: north (z=z1), south (z=z0), east (x=x1), west (x=x0)
    walls_def = [
        ("south", [(x0, z0), (x1, z0)], "south"),
        ("north", [(x1, z1), (x0, z1)], "north"),
        ("east",  [(x1, z0), (x1, z1)], "east"),
        ("west",  [(x0, z1), (x0, z0)], "west"),
    ]
    walls_by_side: dict[str, WallNode] = {}
    for label, pts, side_key in walls_def:
        wall = WallNode(
            id=_gen_id("wall"),
            parentId=level.id,
            points=pts,
            height=height,
            thickness=0.20 if space.exterior else 0.10,
            color=ext_wall_color if space.exterior else int_wall_color,
            metadata={"space": space.name, "side": label},
        )
        scene.add(wall)
        level.children.append(wall.id)
        walls_by_side[side_key] = wall

    # ── Doors and windows on walls ──────────────────────────────────
    for door in space.doors:
        wall = walls_by_side.get(door.wall)
        if wall is None:
            continue
        item = ItemNode(
            id=_gen_id("item"),
            parentId=wall.id,
            itemType="door",
            modelKey="door.flush_36",
            t=door.position,
            width=door.width,
            depth=0.05,
            height=2.10,
        )
        scene.add(item)
        wall.children.append(item.id)

    for window in space.windows:
        wall = walls_by_side.get(window.wall)
        if wall is None:
            continue
        item = ItemNode(
            id=_gen_id("item"),
            parentId=wall.id,
            itemType="window",
            modelKey="window.casement",
            t=window.position,
            width=window.width,
            depth=0.05,
            height=window.height,
            sill=window.sill,
        )
        scene.add(item)
        wall.children.append(item.id)

    # ── Zone (informational tag) ─────────────────────────────────────
    zone = ZoneNode(
        id=_gen_id("zone"),
        parentId=level.id,
        points=[(x0, z0), (x1, z0), (x1, z1), (x0, z1)],
        label=space.name,
        spaceType=space.space_type,
    )
    scene.add(zone)
    level.children.append(zone.id)

    # ── Furniture (heuristic placement) ──────────────────────────────
    items = DEFAULT_FURNITURE.get(space.space_type, [])
    _place_items(scene, slab, space, items)


def _place_items(
    scene: PascalScene,
    slab: SlabNode,
    space: Space,
    items: list[tuple[str, str, float, float, float]],
) -> None:
    """
    Place furniture in a row along the back wall, with margins. This is
    intentionally simple — Pascal's spatial grid will catch collisions and
    we can iterate on placement quality later.

    Items are positioned in the slab's local frame: (0,0) is the slab's
    SW corner; +x is east, +z is north. Pascal's slab system expects this.
    """
    if not items:
        return

    margin = 0.6
    available_w = max(0.5, space.width - 2 * margin)
    n = len(items)
    spacing = available_w / max(1, n)

    for i, (model_key, item_type, w, d, h) in enumerate(items):
        local_x = margin + spacing * (i + 0.5) - w / 2
        local_z = space.depth - margin - d  # along back wall (north)
        local_x = max(0.1, min(local_x, space.width - w - 0.1))
        local_z = max(0.1, min(local_z, space.depth - d - 0.1))

        item = ItemNode(
            id=_gen_id("item"),
            parentId=slab.id,
            itemType=item_type,
            modelKey=model_key,
            position=(local_x, local_z),
            rotation=0.0,
            width=w, depth=d, height=h,
        )
        scene.add(item)
        slab.children.append(item.id)
