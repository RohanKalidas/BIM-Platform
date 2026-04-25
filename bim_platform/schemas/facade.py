"""
schemas.facade — exterior features and facade strategy.

ExteriorFeature is a tagged-union-ish design. All features share a common
'type' field; specific feature types have specific extra fields. Pydantic's
extra='allow' lets each feature carry the params its primitive needs without
requiring a different schema per type.

Types covered (residential + commercial):
  Residential:
    turret, gable, dormer, bay_window, porch, portico, chimney, shutter,
    half_timber_band, balcony
  Commercial:
    parapet, mechanical_screen, canopy, awning, pergola,
    curtain_wall_panel, spandrel_band, mullion_pattern,
    cornice, base_band, vertical_fin, brise_soleil, louvre_screen
  Universal:
    column, pilaster, water_table, eave_overhang, finial

The Facade Agent picks features from the typology's primitive_libraries.
The IFC writer maps each feature.type to a primitive constructor.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ExteriorFeature(BaseModel):
    """One feature on the building exterior. Extra fields allowed per type."""
    model_config = ConfigDict(extra="allow")

    type: str                       # e.g. "turret", "parapet", "canopy"
    color_key: Optional[str] = None # palette key (ext_wall, trim, accent, etc.)


class Facade(BaseModel):
    """The Facade Agent's output — exterior features + palette overrides."""

    exterior_features: list[ExteriorFeature] = Field(default_factory=list)

    # Palette can be overridden by Facade (refines what Brief proposed).
    # Same loose key/hex dict — typology-specific keys.
    style_palette: dict[str, str] = Field(default_factory=dict)

    # Roof strategy (separate from individual gables/dormers).
    # "flat" | "gable" | "hip" | "shed" | "mansard" | "complex"
    roof_type: str = "flat"
    roof_pitch_deg: float = 0.0     # 0 for flat, e.g. 30 for gable

    # Cladding strategy ("brick", "clapboard", "stucco", "curtain_wall",
    # "metal_panel", "concrete_panel", "stone")
    cladding: str = "generic"

    rationale: Optional[str] = None
