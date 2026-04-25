"""
schemas.building_spec — the merged spec the renderer consumes.

This is what `merge_to_spec(brief, layout, facade, mep, structural)` produces.
The IFC writer reads this and produces IFC. It's the single input to the
renderer; everything else is metadata.

The shape is intentionally similar to BIM Studio's <building_spec> tag so
the renderer can be ported with minimal changes. Differences:
  - typology_key replaces ad-hoc style strings
  - structural section is new
  - exterior_features list is richer (commercial features added)
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

from .layout import Floor


class BuildingSpec(BaseModel):
    """The merged spec the renderer consumes."""

    # Identity
    name: str
    typology_key: str
    floors: list[Floor]

    # Metadata blob the renderer reads. Loose because different typologies
    # need different fields. Required keys:
    #   - architectural_style (str)
    #   - style_palette (dict[str,str])
    #   - exterior_features (list[dict])
    #   - mep_strategy (dict)
    #   - structural (dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
