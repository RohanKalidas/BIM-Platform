"""
schemas.structural — structural strategy and grid.

The Structural Agent picks system, grid spacing, column locations,
lateral system, foundation type. The IFC writer creates IfcColumn,
IfcBeam, IfcSlab, IfcFooting elements from this.

For small residential, structural is mostly implicit (wood frame walls
work as structure). For commercial, structural is explicit and the grid
defines how the floorplate gets organized.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class GridLine(BaseModel):
    """A column grid line (numbered or lettered)."""
    label: str          # "1", "2", "A", "B", etc.
    axis: Literal["x", "y"]
    position: float     # meters from origin


class Column(BaseModel):
    """A structural column at a grid intersection."""
    grid_x: str         # e.g. "1"
    grid_y: str         # e.g. "A"
    x: float
    y: float
    width: float = 0.6  # square column default
    depth: float = 0.6
    floors_supported: list[str] = Field(default_factory=list)


class StructuralStrategy(BaseModel):
    """Structural Agent output. Lightweight for residential, full for commercial."""

    system: str = "wood_frame_platform"
        # wood_frame_platform, wood_frame_balloon, light_gauge_steel,
        # masonry_bearing, steel_frame, steel_braced_frame, steel_moment_frame,
        # concrete_frame, concrete_shear_wall, concrete_flat_slab,
        # tilt_up_concrete, pemb (pre-engineered metal building)
    lateral_system: Optional[str] = None
        # braced_frame, moment_frame, shear_wall, dual_system
    foundation: str = "spread_footings"
        # spread_footings, mat_slab, drilled_piers, driven_piles, basement_walls

    # Grid (optional — only used by commercial typologies)
    grid_x_lines: list[GridLine] = Field(default_factory=list)
    grid_y_lines: list[GridLine] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)

    # Floor system
    floor_system: str = "wood_joist"
        # wood_joist, wood_truss, steel_joist, steel_beam_with_metal_deck,
        # concrete_one_way, concrete_two_way, post_tensioned, hollow_core
    typical_bay_x_m: float = 6.0  # for commercial grid spacing
    typical_bay_y_m: float = 6.0

    # Roof
    roof_structure: str = "wood_truss"
        # wood_truss, wood_rafter, steel_joist, steel_truss, concrete_slab

    seismic_design_category: Optional[str] = None  # "A".."F" per ASCE 7
    rationale: Optional[str] = None
