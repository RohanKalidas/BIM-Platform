"""
build.agents.facade — Facade Agent. Picks exterior features and refines
the palette based on Brief style + Layout footprint.

Style-feature minimums are enforced in the prompt — Victorians MUST have
turret OR (gable+dormer); Modern MUST have parapet; etc. Same approach
that worked in BIM Studio, extended for commercial typologies.
"""
from __future__ import annotations
from .base import _call_agent
from ...schemas.facade import Facade
from ...schemas.brief import Brief
from ...schemas.layout import Layout
from ...schemas.pipeline import AgentRun


FACADE_PROMPT = """You are the Facade Agent. Pick exterior features that match
brief.architectural_style and lay them out sensibly using the Layout footprint.

Output a single Facade JSON:
{
  "exterior_features": [
    {"type": "turret", "corner": "sw", "radius": 1.8, "height": 5.8, "sides": 8, "spire": true, "color_key": "ext_wall", "cap_color_key": "roof"},
    {"type": "porch", "sides": ["south", "east"], "depth": 2.0, "column_count": 6, "column_size": 0.3, "column_style": "turned", "column_color_key": "trim", "has_roof": true},
    {"type": "gable", "side": "south", "position": 0.5, "width": 4.0, "height": 2.2, "color_key": "ext_wall"},
    {"type": "parapet", "height": 0.8, "thickness": 0.25, "color_key": "ext_wall"}
  ],
  "style_palette": { ...optional override of brief palette... },
  "roof_type": "flat" | "gable" | "hip" | "shed" | "mansard",
  "roof_pitch_deg": 0 | 25 | 30 | 35 | 45,
  "cladding": "brick" | "clapboard" | "stucco" | "curtain_wall" | "metal_panel" | "concrete_panel" | "stone",
  "rationale": "<terse 1-sentence>"
}

EVERY building MUST have 3-8 exterior_features. A plain box is never acceptable.

STYLE-FEATURE MINIMUMS (you MUST satisfy these for the named style):

Residential:
- victorian / queen_anne_victorian / italianate / gothic_revival:
    MUST include EITHER turret OR (gable + dormer);
    MUST include porch on front_elevation;
    SHOULD include chimney; MAY include bay_window, shutters
    roof_type=gable, pitch=35-45
- tudor / tudor_revival:
    MUST include half_timber_band on front_elevation;
    MUST include gable; SHOULD include chimney with substantial height (5m+)
    roof_type=gable, pitch=40-50
- colonial / neoclassical / federal:
    MUST include portico on front_elevation;
    SHOULD include shutters flanking front windows;
    SHOULD include chimney
    roof_type=gable or hip, pitch=25-35
- modern / contemporary / minimalist:
    MUST include parapet (flat roof);
    SHOULD include canopy at entry;
    MAY include vertical_fins
    roof_type=flat, pitch=0
- mid_century_modern:
    MUST include deep canopy on front_elevation (projection >= 1.5m);
    SHOULD include vertical_fins or pergola
    roof_type=flat or shed, pitch=0-10
- craftsman / bungalow:
    MUST include porch with square columns (column_size >= 0.25m);
    MUST include forward-facing gable
    roof_type=gable, pitch=20-30
- spanish / mediterranean:
    MUST include parapet (low height ~0.7m);
    SHOULD include awnings; MAY include pergola
    roof_type=flat or hip, pitch=0-15
- farmhouse / modern_farmhouse:
    MUST include full-width porch on front_elevation (depth >= 1.8m);
    MUST include gable; SHOULD include chimney; SHOULD include shutters
    roof_type=gable, pitch=30-45

Commercial:
- class_a / corporate / office_tower:
    MUST include curtain_wall_panel on at least 3 elevations;
    MUST include parapet; SHOULD include mechanical_screen on roof;
    MAY include canopy at ground entry
    roof_type=flat, pitch=0
    cladding=curtain_wall
- suburban_office:
    MUST include parapet;
    SHOULD include canopy at entry;
    cladding=brick or metal_panel
    roof_type=flat
- mixed_use_ground / retail_storefront:
    MUST include storefront_glazing on the street-facing elevation;
    MAY include awnings, canopies
    roof_type=flat
- standalone_retail / big_box:
    MUST include parapet (tall, hides rooftop equipment);
    SHOULD include canopy or sign band on street elevation
    roof_type=flat
- warehouse / industrial:
    MUST include loading_dock_canopy on at least one side;
    MAY include clerestory band
    roof_type=flat or shed

Institutional / Hospitality / Recreation:
- hospital / clinic / healthcare:
    MUST include canopy at main entry (covered drop-off);
    SHOULD include sun_shade or brise_soleil on south elevation
    roof_type=flat
- school / k12:
    MUST include canopy at main entry;
    SHOULD include sun_shade on classroom-side elevations
    roof_type=flat
- hotel:
    MUST include port_cochere or major canopy at main entry;
    SHOULD include balcony pattern on guest_room elevations
    roof_type=flat or hip

If brief.architectural_style doesn't match any above, infer the visual
signatures from the style name + style_notes and pick primitives accordingly.

PLACEMENT RULES:
- Turret goes at a CORNER (corner: sw|nw|se|ne)
- Shutters flank WINDOWS (use position + side)
- Gable is over an ENTRY or over the longest roof span
- Chimney sits where the fireplace is logical (interior wall or exterior wall near living room). Use position: [x_meters, y_meters] in the building's coordinate frame.
- Porch on brief.front_elevation
- column_count for porches: scale with porch length, ~1 column per 2m
- color_key references one of brief.style_palette keys: ext_wall, trim, roof,
  accent. Don't hardcode hex in features — let the palette control it.

Use the Layout footprint to pick plausible positions. Don't put a porch where
no door exists in the front-facing wall.
"""


def run_facade_agent(brief: Brief, layout: Layout) -> tuple[Facade, AgentRun]:
    """Run the Facade Agent with brief + layout context."""
    user_msg = (
        f"BRIEF:\n{brief.model_dump_json(indent=2)}\n\n"
        f"LAYOUT:\n{layout.model_dump_json(indent=2)}\n\n"
        f"Produce the Facade JSON:"
    )
    return _call_agent(
        system_prompt=FACADE_PROMPT,
        user_prompt=user_msg,
        schema=Facade,
        label="facade_agent",
    )
