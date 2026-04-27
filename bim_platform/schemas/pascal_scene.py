"""
schemas.pascal_scene — Pydantic mirror of Pascal Editor's Zod node schemas.

This is the export target for the BuildingSpec → Pascal exporter.

Pascal stores nodes as a flat dictionary keyed by id, with parent-child
relationships expressed via parentId fields and children id arrays.
We mirror that exactly so JSON export is straight model_dump().

Coordinate system (Pascal/Three.js convention):
  +X right, +Y up (vertical/gravity), +Z toward viewer.
  This is DIFFERENT from BuildingSpec which uses +Z up.
  The exporter handles the axis swap.

Source: https://github.com/pascalorg/editor (MIT-licensed, schemas in
packages/core/src/schema/). Field names follow Pascal's conventions.
"""
from __future__ import annotations
from typing import Any, Optional, Literal, Union
from pydantic import BaseModel, Field, ConfigDict
import secrets


def _gen_id(prefix: str) -> str:
    """Pascal id format: '<type>_<random hex>'. Compatible with their objectId helper."""
    return f"{prefix}_{secrets.token_hex(6)}"


# ── Base ────────────────────────────────────────────────────────────────
class PascalNode(BaseModel):
    """Base for every Pascal node. Mirrors BaseNode in @pascal-app/core."""
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    parentId: Optional[str] = None
    visible: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Site / Building / Level ────────────────────────────────────────────
class SiteNode(PascalNode):
    type: Literal["site"] = "site"
    children: list[str] = Field(default_factory=list)  # building ids


class BuildingNode(PascalNode):
    type: Literal["building"] = "building"
    children: list[str] = Field(default_factory=list)   # level ids
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)


class LevelNode(PascalNode):
    type: Literal["level"] = "level"
    children: list[str] = Field(default_factory=list)
    elevation: float = 0.0
    height: float = 2.7


# ── Wall ────────────────────────────────────────────────────────────────
class WallNode(PascalNode):
    """
    Pascal walls are defined by start+end points in plan view (XZ plane in
    Three.js terms). Pascal's WallSystem extrudes the wall up to `height`
    and along the line direction with `thickness`.
    """
    type: Literal["wall"] = "wall"
    children: list[str] = Field(default_factory=list)  # item ids (doors/windows)
    # Wall as polyline. Most walls are a single segment [start, end].
    points: list[tuple[float, float]] = Field(default_factory=list)
    height: float = 2.7
    thickness: float = 0.2
    # Optional cosmetic
    color: Optional[str] = None  # hex like "#aabbcc"


# ── Slab (floor) ───────────────────────────────────────────────────────
class SlabNode(PascalNode):
    """
    A floor surface. Defined by a polygon of (x,z) points in plan view,
    extruded down by `thickness`.
    """
    type: Literal["slab"] = "slab"
    children: list[str] = Field(default_factory=list)
    points: list[tuple[float, float]] = Field(default_factory=list)
    thickness: float = 0.2
    color: Optional[str] = None


# ── Ceiling ─────────────────────────────────────────────────────────────
class CeilingNode(PascalNode):
    type: Literal["ceiling"] = "ceiling"
    children: list[str] = Field(default_factory=list)
    points: list[tuple[float, float]] = Field(default_factory=list)
    thickness: float = 0.1
    color: Optional[str] = None


# ── Roof ────────────────────────────────────────────────────────────────
class RoofNode(PascalNode):
    """
    A roof. Pascal supports flat (parapet) and pitched roofs. Style is
    one of 'flat' | 'gable' | 'hip' | 'shed'.
    """
    type: Literal["roof"] = "roof"
    children: list[str] = Field(default_factory=list)
    points: list[tuple[float, float]] = Field(default_factory=list)
    style: Literal["flat", "gable", "hip", "shed"] = "flat"
    pitch: float = 0.0  # degrees; 0 for flat
    color: Optional[str] = None


# ── Item (door, window, furniture, fixture) ────────────────────────────
class ItemNode(PascalNode):
    """
    An item parented to a Wall, Slab, or Ceiling.

    Wall items: doors and windows. Use `t` (0..1) to position along the
    parent wall's length, plus opening dimensions.

    Slab items: furniture and fixtures. Use `position` for (x,z) offset
    within the parent slab's local frame, plus `rotation` and dimensions.

    Ceiling items: lights. Same as slab items but parented to ceiling.
    """
    type: Literal["item"] = "item"
    # category — what kind of item: "door" | "window" | "furniture" | "fixture" | "light"
    itemType: str = "furniture"
    # Library reference — the model name. Pascal viewer uses this to render
    # an appropriate mesh. If unknown, it falls back to a generic box.
    modelKey: Optional[str] = None  # e.g. "sofa.modern_3seat", "door.flush_36"
    # Wall placement
    t: Optional[float] = None        # 0..1 fraction along parent wall
    # Slab/ceiling placement
    position: Optional[tuple[float, float]] = None  # (x, z) in parent local
    rotation: float = 0.0  # radians, around vertical axis
    # Dimensions (meters)
    width: float = 1.0
    depth: float = 1.0
    height: float = 1.0
    # For openings (doors/windows) on walls
    sill: Optional[float] = None  # height above floor for windows
    color: Optional[str] = None


# ── Zone (program tag) ─────────────────────────────────────────────────
class ZoneNode(PascalNode):
    """
    A logical zone — a tagged region of a level. Maps to a BuildingSpec
    Space. The zone polygon is informational; walls / slabs are separate.
    """
    type: Literal["zone"] = "zone"
    children: list[str] = Field(default_factory=list)
    points: list[tuple[float, float]] = Field(default_factory=list)
    label: Optional[str] = None  # display name e.g. "Living Room"
    spaceType: Optional[str] = None  # programmatic tag e.g. "living_room"
    color: Optional[str] = None


# ── Scene envelope ─────────────────────────────────────────────────────
class PascalScene(BaseModel):
    """
    Top-level scene representation. This is what the exporter produces and
    what Pascal Editor's JSON import consumes (after wrapping in their
    expected schema version).

    nodes: flat dict of all nodes by id
    rootNodeIds: ids of the top-level Site nodes
    """
    schemaVersion: str = "0.5"
    nodes: dict[str, PascalNode] = Field(default_factory=dict)
    rootNodeIds: list[str] = Field(default_factory=list)

    def add(self, node: PascalNode) -> str:
        """Insert a node and return its id."""
        self.nodes[node.id] = node
        return node.id

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict ready for json.dumps."""
        return {
            "schemaVersion": self.schemaVersion,
            "nodes": {nid: n.model_dump(exclude_none=True) for nid, n in self.nodes.items()},
            "rootNodeIds": self.rootNodeIds,
        }


__all__ = [
    "PascalNode", "SiteNode", "BuildingNode", "LevelNode",
    "WallNode", "SlabNode", "CeilingNode", "RoofNode",
    "ItemNode", "ZoneNode", "PascalScene", "_gen_id",
]
