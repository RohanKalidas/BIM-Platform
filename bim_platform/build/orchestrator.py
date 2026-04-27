"""
build.orchestrator — the MAS pipeline.

Two public entry points:

  generate_building(prompt, *, external_layout=None) -> PipelineResult
      Runs Brief → Layout-Validator → (Facade ‖ MEP) → merge.

  edit_building(previous, edit_request, *, target, cascade=False) -> PipelineResult
      Surgical edit. Re-runs only the specified target (and cascades only
      when the caller asks).

Edit targets:
  palette   — pure metadata edit (no LLM call)
  materials — palette + facade-feature material tweaks (1 Haiku call)
  facade    — full facade redesign (1 Haiku call)
  mep       — MEP strategy re-pick (1 Haiku call)
  layout    — layout re-plan (1 Haiku call) [+ cascade to facade+MEP]
  brief     — brief update (1 Sonnet call) [+ cascade to all]
"""
from __future__ import annotations
import concurrent.futures
import logging
import re
import time
from typing import Optional

from ..schemas.brief import Brief
from ..schemas.layout import Layout
from ..schemas.facade import Facade
from ..schemas.mep import MEPStrategy
from ..schemas.building_spec import BuildingSpec
from ..schemas.pipeline import AgentRun, PipelineResult
from .agents import (
    run_brief_agent, run_layout_validator,
    run_facade_agent, run_mep_agent,
)

logger = logging.getLogger(__name__)


# ── Generate ────────────────────────────────────────────────────────────
def generate_building(
    prompt: str,
    *,
    external_layout: Optional[Layout] = None,
    parallel_specialists: bool = True,
) -> PipelineResult:
    """
    Run the full MAS pipeline.

    Args:
        prompt: user's natural-language building request
        external_layout: pre-existing layout (from Translate phase or upload).
            When provided, the Layout-Validator validates it instead of
            generating one from scratch.
        parallel_specialists: run Facade + MEP in parallel (default True).

    Returns:
        PipelineResult with .spec, .brief, .layout, .facade, .mep populated.
    """
    started = time.time()
    runs: list[AgentRun] = []

    logger.info("Step 1/4: Brief agent reading user prompt...")
    brief, brief_run = run_brief_agent(prompt)
    runs.append(brief_run)
    logger.info("  → typology=%s style=%r %d floors %.0f sqft",
                brief.typology_key, brief.architectural_style,
                brief.floors_count, brief.total_sqft or 0)

    logger.info("Step 2/4: Layout-Validator %s...",
                "validating external layout" if external_layout else "generating layout")
    layout, layout_run = run_layout_validator(brief, external_layout=external_layout)
    runs.append(layout_run)
    logger.info("  → %d floors, %.1fm × %.1fm footprint, %d spaces",
                len(layout.floors), layout.footprint_width, layout.footprint_depth,
                sum(len(f.spaces) for f in layout.floors))

    logger.info("Step 3+4/4: Facade + MEP agents %s...",
                "in parallel" if parallel_specialists else "sequentially")
    if parallel_specialists:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            facade_future = pool.submit(run_facade_agent, brief, layout)
            mep_future    = pool.submit(run_mep_agent,    brief, layout)
            facade, facade_run = facade_future.result()
            mep, mep_run       = mep_future.result()
    else:
        facade, facade_run = run_facade_agent(brief, layout)
        mep,    mep_run    = run_mep_agent(brief, layout)
    runs.extend([facade_run, mep_run])
    logger.info("  → %d facade features, hvac=%s",
                len(facade.exterior_features), mep.hvac_type)

    spec = merge_to_spec(brief, layout, facade, mep)
    total = time.time() - started
    logger.info("Pipeline done in %.2fs (%d agent calls)", total, len(runs))

    return PipelineResult(
        spec=spec,
        brief=brief, layout=layout, facade=facade, mep=mep,
        runs=runs,
        total_duration_s=round(total, 2),
        fresh_agents=[r.agent for r in runs],
    )


def merge_to_spec(
    brief: Brief, layout: Layout, facade: Facade, mep: MEPStrategy,
) -> BuildingSpec:
    """Combine the four agent outputs into a single BuildingSpec."""
    # Facade palette overrides Brief palette for shared keys.
    palette = dict(brief.style_palette)
    palette.update(facade.style_palette)

    return BuildingSpec(
        name=brief.name,
        typology_key=brief.typology_key,
        floors=layout.floors,
        metadata={
            "architectural_style": brief.architectural_style or "",
            "style_notes": brief.style_notes or "",
            "style_palette": palette,
            "exterior_features": [
                f.model_dump(exclude_none=True) for f in facade.exterior_features
            ],
            "roof_type": facade.roof_type,
            "roof_pitch_deg": facade.roof_pitch_deg,
            "cladding": facade.cladding,
            "mep_strategy": mep.model_dump(exclude_none=True),
            "location": brief.location,
            "climate_zone": brief.climate_zone,
            "total_sqft": brief.total_sqft,
            "front_elevation": brief.front_elevation,
            "program": [pi.name for pi in brief.program_items for _ in range(pi.count)],
            "rationale": {
                "brief":  brief.rationale,
                "facade": facade.rationale,
                "mep":    mep.rationale,
            },
        },
    )


# ── Edit ────────────────────────────────────────────────────────────────

# Standalone palette parser (no LLM). Handles 40+ named colors + material
# keywords + per-key targeting (ext_wall / trim / roof / accent / window_glass).
_NAMED_COLORS = {
    "white": "#F5F5F5", "cream": "#F0E8D6", "beige": "#E8DCC4",
    "tan": "#D2B48C", "gray": "#808080", "grey": "#808080",
    "dark gray": "#3A3A3A", "dark grey": "#3A3A3A",
    "light gray": "#C0C0C0", "light grey": "#C0C0C0",
    "black": "#1A1A1A", "charcoal": "#36454F",
    "red": "#B22222", "brick": "#8B3A2F",
    "brick red": "#8B3A2F", "red brick": "#8B3A2F",
    "rust": "#8B4513", "orange": "#D35400", "terracotta": "#A0522D",
    "brown": "#5C4033", "dark brown": "#3D2817",
    "blue": "#2C5282", "navy": "#1A2E4C", "dark blue": "#1A2E4C",
    "light blue": "#A8C6DF", "teal": "#2C7A7B",
    "green": "#3A5F3A", "dark green": "#1F3529",
    "forest green": "#1F3529", "sage": "#87A96B", "olive": "#6B7B3A",
    "wood": "#8B6F47", "natural wood": "#A78860",
    "oak": "#A17C52", "walnut": "#5C4033",
    "clapboard": "#E8DCC4", "stone": "#8A8578",
    "stucco": "#D8CFBE", "siding": "#C8BFA3",
}

_KEY_HINTS = [
    ("ext_wall", ["wall", "exterior", "ext", "siding", "cladding",
                  "clapboard", "brick", "stone", "stucco", "facade", "face"]),
    ("trim",     ["trim", "molding", "fascia", "frame"]),
    ("roof",     ["roof", "shingle", "tile"]),
    ("accent",   ["accent", "door", "shutter", "feature"]),
    ("window_glass", ["window", "glass", "glazing"]),
]


def _apply_palette_hints(palette: dict, edit_request: str) -> dict:
    """Parse a natural-language palette edit into a dict update."""
    req = edit_request.lower()

    matches = []
    for color_name in sorted(_NAMED_COLORS, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(color_name) + r"\b", req):
            matches.append((m.start(), color_name, _NAMED_COLORS[color_name]))
    if not matches:
        logger.warning("palette parser: no colors recognized in %r", edit_request)
        return palette

    # Dedupe overlapping (longer match wins): "dark green" vs "green"
    matches.sort(key=lambda x: (x[0], -len(x[1])))
    filtered = []
    claimed_end = -1
    for pos, name, hex_v in matches:
        if pos < claimed_end:
            continue
        filtered.append((pos, name, hex_v))
        claimed_end = pos + len(name)

    updated = dict(palette)
    for pos, name, hex_v in filtered:
        end = pos + len(name)
        after = edit_request[end: end + 25].lower()
        for sep in (",", ";", "."):
            if sep in after:
                after = after.split(sep)[0]
                break
        before = edit_request[max(0, pos - 25): pos].lower()
        for sep in (",", ";", "."):
            if sep in before:
                before = before.rsplit(sep, 1)[-1]

        best_key = None
        best_dist = 9999
        for key, hints in _KEY_HINTS:
            for h in hints:
                if h in after:
                    d = after.find(h)
                    if d < best_dist:
                        best_dist, best_key = d, key
                if h in before:
                    d = 100 + (len(before) - before.rfind(h))
                    if d < best_dist:
                        best_dist, best_key = d, key
        updated[best_key or "ext_wall"] = hex_v
        logger.info("palette: %r → %s = %s", name, best_key or "ext_wall", hex_v)
    return updated


def edit_building(
    previous: PipelineResult,
    edit_request: str,
    *,
    target: str,
    cascade: bool = False,
) -> PipelineResult:
    """
    Re-run only the targeted specialist by default. Preserves everything else.

    Targets: palette, materials, facade, mep, layout, brief.
    """
    started = time.time()
    runs = list(previous.runs)
    fresh: list[str] = []

    brief = previous.brief
    layout = previous.layout
    facade = previous.facade or Facade()
    mep = previous.mep or MEPStrategy()

    def _replace_run(label: str, new_run: AgentRun) -> None:
        nonlocal runs
        runs = [r for r in runs if r.agent != label]
        new_run.cached = False
        runs.append(new_run)
        fresh.append(label)

    if target == "palette":
        logger.info("Edit: palette-only rewrite (no LLM)")
        palette = dict(facade.style_palette or brief.style_palette)
        palette = _apply_palette_hints(palette, edit_request)
        facade = facade.model_copy(update={"style_palette": palette})

    elif target == "materials":
        logger.info("Edit: materials (facade with feature-list freeze)")
        original_notes = brief.style_notes
        try:
            brief.style_notes = (
                f"{original_notes}\n\nMATERIALS EDIT (keep exterior_features list "
                f"EXACTLY the same, only change style_palette and feature "
                f"color_key params): {edit_request}"
            )
            new_facade, run = run_facade_agent(brief, layout)
        finally:
            brief.style_notes = original_notes
        facade = new_facade
        _replace_run("facade_agent", run)

    elif target == "facade":
        logger.info("Edit: facade redesign")
        original_notes = brief.style_notes
        try:
            brief.style_notes = f"{original_notes}\n\nFACADE EDIT: {edit_request}"
            facade, run = run_facade_agent(brief, layout)
        finally:
            brief.style_notes = original_notes
        _replace_run("facade_agent", run)

    elif target == "mep":
        logger.info("Edit: MEP re-pick")
        original_notes = brief.style_notes
        try:
            brief.style_notes = f"{original_notes}\n\nMEP EDIT: {edit_request}"
            mep, run = run_mep_agent(brief, layout)
        finally:
            brief.style_notes = original_notes
        _replace_run("mep_agent", run)

    elif target == "layout":
        logger.info("Edit: layout re-plan (cascade=%s)", cascade)
        original_notes = brief.style_notes
        try:
            brief.style_notes = f"{original_notes}\n\nLAYOUT EDIT: {edit_request}"
            layout, run = run_layout_validator(brief)
        finally:
            brief.style_notes = original_notes
        _replace_run("layout_validator", run)
        if cascade:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                facade_f = pool.submit(run_facade_agent, brief, layout)
                mep_f    = pool.submit(run_mep_agent,    brief, layout)
                facade, frun = facade_f.result()
                mep,    mrun = mep_f.result()
            _replace_run("facade_agent", frun)
            _replace_run("mep_agent",    mrun)

    elif target == "brief":
        logger.info("Edit: brief update (cascade=%s)", cascade)
        prompt = (
            f"PREVIOUS BRIEF:\n{brief.model_dump_json(indent=2)}\n\n"
            f"EDIT REQUEST:\n{edit_request}\n\n"
            "Produce an updated Brief JSON. Change ONLY what the edit request "
            "asks for. Keep everything else as it was unless the edit forces "
            "a change. Be conservative."
        )
        brief, run = run_brief_agent(prompt)
        _replace_run("brief_agent", run)
        if cascade:
            layout, lrun = run_layout_validator(brief)
            _replace_run("layout_validator", lrun)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                facade_f = pool.submit(run_facade_agent, brief, layout)
                mep_f    = pool.submit(run_mep_agent,    brief, layout)
                facade, frun = facade_f.result()
                mep,    mrun = mep_f.result()
            _replace_run("facade_agent", frun)
            _replace_run("mep_agent",    mrun)

    else:
        raise ValueError(
            f"Unknown edit target: {target!r}. Use palette, materials, "
            f"facade, mep, layout, or brief."
        )

    # Mark non-fresh runs as cached
    for r in runs:
        if r.agent not in fresh:
            r.cached = True

    spec = merge_to_spec(brief, layout, facade, mep)
    total = time.time() - started
    logger.info("Edit done in %.2fs (target=%s, cascade=%s)", total, target, cascade)

    return PipelineResult(
        spec=spec,
        brief=brief, layout=layout, facade=facade, mep=mep,
        runs=runs,
        total_duration_s=round(total, 2),
        fresh_agents=fresh,
    )
