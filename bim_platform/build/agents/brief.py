"""
build.agents.brief — Brief Agent. Classifies user prompt → typology, then
produces a typology-appropriate Brief (program list, sqft, style, palette).

Uses Sonnet because the typology classification + program inference require
broader world knowledge than Haiku reliably provides.
"""
from __future__ import annotations
from .base import _call_agent, ORCHESTRATOR_MODEL
from ...schemas.brief import Brief
from ...schemas.pipeline import AgentRun
from ... import typology as typ


BRIEF_SYSTEM_PROMPT = """You are the Brief Agent for a multi-agent architectural building generator.

Your job: read the user's prompt and produce a structured Brief JSON that
captures their design intent. Downstream specialist agents (Layout, Facade, MEP)
read your Brief verbatim and trust everything you put in it. Be opinionated:
when the user is terse, fill in sensible defaults rather than leaving fields blank.

Output a single JSON object matching this shape:
{
  "typology_key": "<one of the typologies below>",
  "name": "<short building name>",
  "program_items": [
    {"name": "<space type>", "count": <int>, "sqft_each": <float or null>, "tags": [...]}
  ],
  "floors_count": <int>,
  "total_sqft": <float or null>,
  "site_constraints": <string or null>,
  "architectural_style": "<style name, e.g. 'queen anne victorian'>",
  "style_notes": "<2-3 sentence expansion of features the building should have>",
  "style_palette": {
    "ext_wall": "#hexhex",
    "trim": "#hexhex",
    "roof": "#hexhex",
    "accent": "#hexhex",
    "window_glass": "#hexhex"
    // For commercial typologies, also include:
    //   "curtain_wall": "#hexhex", "spandrel": "#hexhex", "mullion": "#hexhex"
  },
  "location": "<city, region>",
  "climate_zone": "<ASHRAE zone if US, else null>",
  "front_elevation": "<one of north|south|east|west>",
  "rationale": "<1 sentence on why these decisions>"
}

VALID TYPOLOGY KEYS (pick the closest match):
{typology_list}

CRITICAL RULES:
1. If the user is terse ("Victorian cottage", "modern office tower"),
   EXPAND style_notes to specify the architectural features (turret, gable,
   curtain wall, parapet, etc.). The Facade Agent reads style_notes literally.
2. style_palette MUST include keys: ext_wall, trim, roof, accent, window_glass.
   Window_glass: dark blue-gray (#2C3E50) for traditional; near-clear (#A8B8C0)
   for modern/commercial. For commercial typologies, ALSO include curtain_wall,
   spandrel, mullion keys.
3. program_items must be appropriate for the chosen typology. Single-family
   homes have bedrooms/bathrooms; offices have open_office/conference_room;
   hospitals have exam_room/procedure_room/etc.
4. floors_count and total_sqft must be sensible for the typology. If user
   says "office tower," default to 10+ floors. "Cottage" defaults to 1.
5. front_elevation: pick the side facing the primary approach/street.
   Default to "south" if unspecified (good solar orientation).
6. rationale: one terse sentence. No marketing fluff.
"""


def _build_typology_list() -> str:
    """Format the typology registry into a list block for the prompt."""
    lines = []
    for t in typ.ALL_TYPOLOGIES:
        lines.append(f"  - {t.key}: {t.display_name} ({t.description})")
    return "\n".join(lines)


def run_brief_agent(user_prompt: str) -> tuple[Brief, AgentRun]:
    """Run the Brief Agent. Returns (Brief, AgentRun)."""
    system = BRIEF_SYSTEM_PROMPT.replace("{typology_list}", _build_typology_list())
    return _call_agent(
        system_prompt=system,
        user_prompt=f"User request:\n{user_prompt}\n\nProduce the Brief JSON:",
        schema=Brief,
        label="brief_agent",
        model=ORCHESTRATOR_MODEL,
    )
