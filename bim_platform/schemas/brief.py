"""
schemas.brief — the Brief Agent's output. Typology-agnostic.

The Brief is the design intent: what's being built, where, for whom, in
what style. It doesn't describe rooms in detail (that's Layout's job) but
it does establish the program — what spaces the building must contain.

Schema design rules:
  - typology_key matches an entry in bim_platform.typology
  - program_items are typed (ProgramItem) so schools and houses use the
    same shape: a name + count + optional sqft + tags
  - palette_keys are loose strings — different typologies use different
    keys (residential uses ext_wall/trim/roof/accent/window_glass; office
    uses curtain_wall/spandrel/mullion/canopy)
  - everything is optional except typology_key and program_items so the
    Brief Agent can emit partial briefs that downstream agents fill in
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ProgramItem(BaseModel):
    """A space type the building must contain."""
    name: str                       # e.g. "bedroom", "open_office", "or_suite"
    count: int = 1                  # how many of this space type
    sqft_each: Optional[float] = None  # average sqft per instance, if specified
    tags: list[str] = Field(default_factory=list)  # ["accessible", "private", "exterior"]
    notes: Optional[str] = None     # free-form ("master with ensuite")


class Brief(BaseModel):
    """Design intent for the building. Output of the Brief Agent."""

    # Required core
    typology_key: str               # e.g. "residential.single_family"
    program_items: list[ProgramItem]

    # Spatial envelope
    floors_count: int = 1
    total_sqft: Optional[float] = None
    site_constraints: Optional[str] = None  # "tight urban lot", "large suburban site"

    # Style / aesthetic
    architectural_style: Optional[str] = None  # "queen anne victorian", "class a corporate"
    style_notes: Optional[str] = None          # expanded description
    style_palette: dict[str, str] = Field(default_factory=dict)  # key -> hex color

    # Location / context
    location: Optional[str] = None
    climate_zone: Optional[str] = None  # ASHRAE climate zone
    front_elevation: str = "south"

    # User-facing identity
    name: str = "Building"
    rationale: Optional[str] = None  # why these decisions

    # Coverage hints — Brief Agent can flag bits it had to guess
    inferred_fields: list[str] = Field(default_factory=list)
