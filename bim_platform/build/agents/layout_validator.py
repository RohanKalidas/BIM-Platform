"""
build.agents.layout_validator — Layout-Validator Agent.

In the new architecture, layout comes from outside the MAS — either the
Translate phase (which converts a floor plan PNG into Layout JSON) or
direct user input. The Layout-Validator's job:

  1. If an external_layout is provided, validate it against the Brief
     (room count matches program, total sqft is reasonable, etc.) and
     pass it through.
  2. If NO external_layout is provided (today's CLI use case), fall back
     to generating one from the Brief alone — this preserves backward
     compatibility with BIM Studio's behavior.

Uses Haiku — the layout generation is structured and benefits from speed.
"""
from __future__ import annotations
import logging
from typing import Optional
from .base import _call_agent
from ...schemas.layout import Layout
from ...schemas.brief import Brief
from ...schemas.pipeline import AgentRun

logger = logging.getLogger(__name__)


LAYOUT_GENERATE_PROMPT = """You are the Layout Agent. Read the Brief below and design a floor plan.

Output a single Layout JSON object:
{
  "floors": [
    {
      "name": "Ground",
      "elevation": 0.0,
      "height": 2.7,
      "spaces": [
        {
          "name": "Living Room",
          "space_type": "living_room",
          "x": 0.0, "y": 0.0,
          "width": 5.0, "depth": 4.0,
          "height": 2.7,
          "exterior": true,
          "doors": [{"wall": "south", "position": 0.5, "width": 0.9, "leads_to": "exterior"}],
          "windows": [{"wall": "south", "position": 0.3, "width": 1.6, "height": 1.4, "sill": 0.9}],
          "tags": []
        }
      ]
    }
  ],
  "footprint_width": 12.0,
  "footprint_depth": 9.0,
  "source": "layout_agent"
}

RULES:
1. Coordinate system: +X east, +Y north (in plan view), origin at SW corner.
   Z (vertical) is handled by floor.elevation.
2. Total floor area should be close to brief.total_sqft (within ~10%).
   Convert sqft to sqm: 1 sqft = 0.0929 sqm.
3. Every space in brief.program_items must appear in the layout (matching
   counts). Use space_type values that match Pascal's typical conventions:
   living_room, dining_room, kitchen, bedroom, master_bedroom, bathroom,
   hallway, entry, garage, laundry, home_office, open_office,
   conference_room, private_office, lobby, restroom, etc.
4. Spaces must NOT overlap. Adjacent spaces share walls (party walls are
   handled later by the renderer).
5. Multi-floor buildings: stack floors at consistent x/y so vertical
   circulation aligns. Stairs and elevators ideally appear on every floor
   at the same x/y.
6. exterior: true for any space with at least one wall on the building
   envelope. Hallways and bathrooms usually exterior=false.
7. Add doors and windows generously — every habitable space gets at least
   one door, exterior spaces get windows on outward-facing walls.
8. Hallways connect to all rooms on a floor; place doors so each room has
   access either to a hallway or to an adjacent room.
9. Bathrooms cluster near plumbing (kitchens, utility rooms) when
   possible — saves plumbing chase length.
10. door.wall and window.wall must be one of: north, south, east, west.
11. door.position and window.position are 0..1 fractions along the wall.
"""


LAYOUT_VALIDATE_PROMPT = """You are the Layout-Validator Agent. An external layout was provided.

Your job: check that the layout matches the Brief and is structurally
reasonable. Pass through valid layouts; if you find issues, emit the
layout WITH issues listed in the `issues` field — downstream agents will
proceed best-effort regardless.

Output the (possibly amended) Layout JSON. Add to the `issues` array any of:
  - "program mismatch: brief asks for X bedrooms, layout has Y"
  - "total sqft mismatch: brief total_sqft=A, layout sums to B"
  - "space '<name>' has zero area"
  - "spaces '<a>' and '<b>' overlap"
  - "<space>' has no door"
  - "exterior space '<name>' has no windows"

Don't reject — annotate. The orchestrator decides what to do.
"""


def run_layout_validator(
    brief: Brief,
    external_layout: Optional[Layout] = None,
) -> tuple[Layout, AgentRun]:
    """
    If external_layout is provided, validate it. Otherwise generate one.
    """
    if external_layout is not None:
        # Validate path
        user_msg = (
            f"BRIEF:\n{brief.model_dump_json(indent=2)}\n\n"
            f"EXTERNAL LAYOUT:\n{external_layout.model_dump_json(indent=2)}\n\n"
            f"Validate and return the layout (with issues annotated):"
        )
        return _call_agent(
            system_prompt=LAYOUT_VALIDATE_PROMPT,
            user_prompt=user_msg,
            schema=Layout,
            label="layout_validator",
        )

    # Generate path
    user_msg = (
        f"BRIEF:\n{brief.model_dump_json(indent=2)}\n\n"
        f"Generate the Layout JSON:"
    )
    return _call_agent(
        system_prompt=LAYOUT_GENERATE_PROMPT,
        user_prompt=user_msg,
        schema=Layout,
        label="layout_validator",
    )
