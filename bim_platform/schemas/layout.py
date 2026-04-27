"""
schemas.layout — floor plan structure. Typology-agnostic.

A Layout is one or more Floors, each containing Spaces. "Space" replaces
the residential-only "Room" concept. A Space is any contiguous functional
area — could be a bedroom, an open office bullpen, a 50-station factory
floor, an MRI suite, or a basketball court.

Coordinate system:
  +X east (right), +Y north (up in plan view), +Z up (gravity opposite)
  All units are meters. Floor elevations are absolute z heights.

Layout is the OUTPUT of either:
  - the (deprecated, residential-only) Layout Agent, OR
  - the Translate phase reading a floor plan PNG, OR
  - direct user upload of structured layout data.

In all cases, downstream agents (Facade, MEP, Compliance, Structural)
treat Layout as ground truth and don't regenerate it.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


# Cardinal walls — used for door_wall, window_walls, etc.
WallSide = Literal["north", "south", "east", "west"]


class Door(BaseModel):
    """A door opening on one of a Space's walls."""
    wall: WallSide
    position: float = 0.5    # 0..1 fraction along the wall
    width: float = 0.9       # meters
    leads_to: Optional[str] = None  # name of adjacent Space, or "exterior"


class Window(BaseModel):
    """A window opening on one of a Space's walls."""
    wall: WallSide
    position: float = 0.5
    width: float = 1.2
    height: float = 1.4
    sill: float = 0.9


class Space(BaseModel):
    """
    A functional area on a floor. Replaces the residential-specific Room.

    A Space is rectangular in plan (matches IFC IfcSpace conventions and
    keeps the renderer simple). Non-rectangular spaces are decomposed into
    multiple adjacent rectangular Spaces.
    """
    name: str                # "Living Room", "Open Office", "OR-3", "Court A"
    space_type: str          # "living_room", "open_office", "or", "basketball_court"
                             #   — typically a program name from the Brief
    x: float                 # SW corner x
    y: float                 # SW corner y
    width: float             # extent in +x
    depth: float             # extent in +y

    # Default 2.7m residential, often 4.2m+ commercial; layout validator
    # may override based on typology.
    height: Optional[float] = None

    exterior: bool = False   # at least one wall is on the building envelope
    doors: list[Door] = Field(default_factory=list)
    windows: list[Window] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)  # "core", "back_of_house", etc.


class Floor(BaseModel):
    """One floor of the building."""
    name: str                # "Ground", "Level 2", "Mezzanine", "Roof"
    elevation: float = 0.0   # absolute z of the floor slab
    height: float = 2.7      # floor-to-floor (residential default; commercial 4.2)
    spaces: list[Space] = Field(default_factory=list)

    # Optional commercial extras
    has_core: bool = False
    core_extents: Optional[tuple[float, float, float, float]] = None
        # (x, y, width, depth) of the central core, if applicable


class Layout(BaseModel):
    """The full floor plan structure. Output of Translate or LayoutAgent."""
    floors: list[Floor]
    footprint_width: float   # overall building width
    footprint_depth: float   # overall building depth

    # Provenance: where did this layout come from?
    source: Literal["translate_vlm", "layout_agent", "user_upload", "test"] = "test"
    confidence: float = 1.0  # Translate sets <1.0 when VLM was unsure
    issues: list[str] = Field(default_factory=list)
        # Validator-noted issues. Empty = clean; non-empty = best-effort still
        # proceeds but agents should be aware.
