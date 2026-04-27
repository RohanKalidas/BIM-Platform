"""
tests.test_stub — offline smoke tests. No API calls.

Validates:
  - schemas round-trip cleanly
  - merge_to_spec produces correct shape
  - palette parser handles single + multi-color edits
  - Pascal exporter produces a structurally valid scene
  - edit() preserves cached agents and only re-runs the target

Run:
    python -m tests.test_stub
or:
    pytest tests/test_stub.py
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from unittest.mock import patch

from bim_platform.schemas import (
    Brief, ProgramItem, Layout, Floor, Space, Door, Window,
    Facade, ExteriorFeature, MEPStrategy, BuildingSpec, AgentRun,
    PipelineResult,
)
from bim_platform.build.orchestrator import (
    merge_to_spec, edit_building, _apply_palette_hints,
)
from bim_platform.build.export_pascal import export_to_pascal


# ── Sample fixtures ─────────────────────────────────────────────────────
SAMPLE_BRIEF = Brief(
    typology_key="residential.single_family",
    name="Sample House",
    program_items=[
        ProgramItem(name="living_room", count=1),
        ProgramItem(name="kitchen", count=1),
        ProgramItem(name="bedroom", count=2),
        ProgramItem(name="bathroom", count=1),
    ],
    floors_count=1,
    total_sqft=1200.0,
    architectural_style="craftsman bungalow",
    style_notes="Craftsman with a forward gable and front porch with square columns.",
    style_palette={
        "ext_wall": "#5C7A52",
        "trim":     "#F0E8D6",
        "roof":     "#3B2F2F",
        "accent":   "#8B4513",
        "window_glass": "#2C3E50",
    },
    location="Pasadena, CA",
    climate_zone="3B",
    front_elevation="south",
)

SAMPLE_LAYOUT = Layout(
    floors=[
        Floor(
            name="Ground", elevation=0.0, height=2.7,
            spaces=[
                Space(name="Living Room", space_type="living_room",
                      x=0.0, y=0.0, width=5.0, depth=4.0, exterior=True,
                      doors=[Door(wall="south", position=0.5, width=0.9, leads_to="exterior")],
                      windows=[Window(wall="south", position=0.2, width=1.6, height=1.4, sill=0.9)]),
                Space(name="Kitchen", space_type="kitchen",
                      x=5.0, y=0.0, width=4.0, depth=4.0, exterior=True),
                Space(name="Bedroom 1", space_type="bedroom",
                      x=0.0, y=4.0, width=4.0, depth=4.0, exterior=True),
                Space(name="Bedroom 2", space_type="bedroom",
                      x=4.0, y=4.0, width=3.5, depth=4.0, exterior=True),
                Space(name="Bathroom", space_type="bathroom",
                      x=7.5, y=4.0, width=2.5, depth=4.0, exterior=True),
                Space(name="Hallway", space_type="hallway",
                      x=0.0, y=8.0, width=10.0, depth=1.5, exterior=False),
            ],
        ),
    ],
    footprint_width=10.0, footprint_depth=9.5, source="test",
)

SAMPLE_FACADE = Facade(
    exterior_features=[
        ExteriorFeature(type="gable", side="south", position=0.5, width=4.0, height=2.0),
        ExteriorFeature(type="porch", sides=["south"], depth=1.8, column_count=4),
        ExteriorFeature(type="chimney", position=[5.5, 2.0], width=0.8, height=4.5),
    ],
    style_palette={},
    roof_type="gable",
    roof_pitch_deg=25.0,
    cladding="clapboard",
)

SAMPLE_MEP = MEPStrategy(
    hvac_type="heat_pump_central",
    hvac_zones=1,
    equipment_location="utility_room",
    hot_water="tank_electric",
    electrical_panel_amps=200,
    sprinklers=False,
    smoke_detectors=True,
    heating_fuel="heat_pump",
)


# ── Tests ───────────────────────────────────────────────────────────────
def test_schemas_validate():
    j = SAMPLE_BRIEF.model_dump_json()
    Brief.model_validate_json(j)
    SAMPLE_LAYOUT.model_validate_json(SAMPLE_LAYOUT.model_dump_json())
    SAMPLE_FACADE.model_validate_json(SAMPLE_FACADE.model_dump_json())
    SAMPLE_MEP.model_validate_json(SAMPLE_MEP.model_dump_json())
    print("✓ schemas validate and round-trip")


def test_merge_to_spec():
    spec = merge_to_spec(SAMPLE_BRIEF, SAMPLE_LAYOUT, SAMPLE_FACADE, SAMPLE_MEP)
    assert spec.name == "Sample House"
    assert spec.typology_key == "residential.single_family"
    assert len(spec.floors) == 1
    assert len(spec.metadata["exterior_features"]) == 3
    assert "ext_wall" in spec.metadata["style_palette"]
    assert spec.metadata["mep_strategy"]["hvac_type"] == "heat_pump_central"
    assert spec.metadata["roof_type"] == "gable"
    print(f"✓ merge_to_spec produces correct shape ({len(spec.floors)} floors, "
          f"{len(spec.metadata['exterior_features'])} features)")


def test_palette_parser():
    # Single color → ext_wall
    pal = {"ext_wall": "#aaa", "trim": "#bbb", "roof": "#ccc"}
    out = _apply_palette_hints(pal, "Change to red brick")
    assert out["ext_wall"] == "#8B3A2F", f"got {out['ext_wall']}"
    assert out["trim"] == "#bbb"  # preserved

    # Multi-key
    out = _apply_palette_hints(pal, "White trim, dark green walls, charcoal roof")
    assert out["trim"] == "#F5F5F5"
    assert out["ext_wall"] == "#1F3529"
    assert out["roof"] == "#36454F"
    print("✓ palette parser handles single + multi-color edits")


def test_pascal_export():
    spec = merge_to_spec(SAMPLE_BRIEF, SAMPLE_LAYOUT, SAMPLE_FACADE, SAMPLE_MEP)
    scene = export_to_pascal(spec)

    # Top-level shape: just "nodes" and "rootNodeIds"
    assert set(scene.keys()) == {"nodes", "rootNodeIds"}, f"got keys {scene.keys()}"
    assert len(scene["rootNodeIds"]) == 1

    # Tally node types from the flat dict
    types = [n["type"] for n in scene["nodes"].values()]
    assert types.count("site") == 1
    assert types.count("building") == 1
    assert types.count("level") == 1
    # 6 spaces × (1 slab + 1 ceiling + 4 walls) = 36 nodes per floor
    assert types.count("slab") == 6,    f"expected 6 slabs, got {types.count('slab')}"
    assert types.count("ceiling") == 6, f"expected 6 ceilings, got {types.count('ceiling')}"
    assert types.count("wall") == 24,   f"expected 24 walls, got {types.count('wall')}"

    # Check Pascal-specific fields are present
    site = next(n for n in scene["nodes"].values() if n["type"] == "site")
    assert "polygon" in site
    assert site["polygon"]["type"] == "polygon"
    assert site["object"] == "node"

    a_wall = next(n for n in scene["nodes"].values() if n["type"] == "wall")
    assert "start" in a_wall and "end" in a_wall
    assert a_wall["object"] == "node"
    assert a_wall["backSide"] in ("exterior", "interior")

    # JSON-serializable
    js = json.dumps(scene)
    assert len(js) > 1000
    print(f"✓ Pascal export: {len(scene['nodes'])} nodes, JSON {len(js)} bytes")


def test_edit_palette_no_llm():
    """Palette edit should not call any LLM."""
    base = PipelineResult(
        spec=merge_to_spec(SAMPLE_BRIEF, SAMPLE_LAYOUT, SAMPLE_FACADE, SAMPLE_MEP),
        brief=SAMPLE_BRIEF, layout=SAMPLE_LAYOUT,
        facade=SAMPLE_FACADE, mep=SAMPLE_MEP,
        runs=[
            AgentRun(agent="brief_agent", duration_s=1.0, input_tokens=100, output_tokens=200),
            AgentRun(agent="layout_validator", duration_s=2.0, input_tokens=300, output_tokens=400),
            AgentRun(agent="facade_agent", duration_s=1.5, input_tokens=200, output_tokens=300),
            AgentRun(agent="mep_agent", duration_s=1.2, input_tokens=150, output_tokens=250),
        ],
        total_duration_s=5.7,
    )

    n_calls = {"any": 0}
    def boom(*a, **k):
        n_calls["any"] += 1
        raise RuntimeError("should not be called for palette edit")

    with patch("bim_platform.build.orchestrator.run_facade_agent", side_effect=boom), \
         patch("bim_platform.build.orchestrator.run_mep_agent",    side_effect=boom), \
         patch("bim_platform.build.orchestrator.run_layout_validator", side_effect=boom), \
         patch("bim_platform.build.orchestrator.run_brief_agent",  side_effect=boom):
        result = edit_building(base, "Change to red brick, white trim", target="palette")

    assert n_calls["any"] == 0
    pal = result.spec.metadata["style_palette"]
    assert pal["ext_wall"] == "#8B3A2F"
    assert pal["trim"] == "#F5F5F5"
    print("✓ palette edit makes 0 LLM calls and applies correct hex values")


def test_edit_facade_only():
    """Facade edit should rerun facade only — brief, layout, mep all cached."""
    base = PipelineResult(
        spec=merge_to_spec(SAMPLE_BRIEF, SAMPLE_LAYOUT, SAMPLE_FACADE, SAMPLE_MEP),
        brief=SAMPLE_BRIEF, layout=SAMPLE_LAYOUT,
        facade=SAMPLE_FACADE, mep=SAMPLE_MEP,
        runs=[
            AgentRun(agent="brief_agent", duration_s=1.0, input_tokens=100, output_tokens=200),
            AgentRun(agent="layout_validator", duration_s=2.0, input_tokens=300, output_tokens=400),
            AgentRun(agent="facade_agent", duration_s=1.5, input_tokens=200, output_tokens=300),
            AgentRun(agent="mep_agent", duration_s=1.2, input_tokens=150, output_tokens=250),
        ],
        total_duration_s=5.7,
    )

    counts = {"facade": 0, "mep": 0, "layout": 0, "brief": 0}
    def fake_facade(*a, **k):
        counts["facade"] += 1
        return SAMPLE_FACADE, AgentRun(agent="facade_agent", duration_s=1.0, input_tokens=10, output_tokens=20)
    def boom(name):
        def _(*a, **k):
            counts[name] += 1
            raise RuntimeError(f"{name} should not be called")
        return _

    with patch("bim_platform.build.orchestrator.run_facade_agent", side_effect=fake_facade), \
         patch("bim_platform.build.orchestrator.run_mep_agent",    side_effect=boom("mep")), \
         patch("bim_platform.build.orchestrator.run_layout_validator", side_effect=boom("layout")), \
         patch("bim_platform.build.orchestrator.run_brief_agent",  side_effect=boom("brief")):
        result = edit_building(base, "Add a cupola", target="facade")

    assert counts == {"facade": 1, "mep": 0, "layout": 0, "brief": 0}
    assert "facade_agent" in result.fresh_agents
    assert "brief_agent" not in result.fresh_agents
    print("✓ facade edit reruns facade only, others cached")


def test_edit_layout_no_cascade_default():
    base = PipelineResult(
        spec=merge_to_spec(SAMPLE_BRIEF, SAMPLE_LAYOUT, SAMPLE_FACADE, SAMPLE_MEP),
        brief=SAMPLE_BRIEF, layout=SAMPLE_LAYOUT,
        facade=SAMPLE_FACADE, mep=SAMPLE_MEP,
        runs=[
            AgentRun(agent="brief_agent", duration_s=1.0, input_tokens=100, output_tokens=200),
            AgentRun(agent="layout_validator", duration_s=2.0, input_tokens=300, output_tokens=400),
            AgentRun(agent="facade_agent", duration_s=1.5, input_tokens=200, output_tokens=300),
            AgentRun(agent="mep_agent", duration_s=1.2, input_tokens=150, output_tokens=250),
        ],
        total_duration_s=5.7,
    )
    counts = {"facade": 0, "mep": 0, "layout": 0}
    def fake_layout(*a, **k):
        counts["layout"] += 1
        return SAMPLE_LAYOUT, AgentRun(agent="layout_validator", duration_s=1.0, input_tokens=10, output_tokens=20)
    def fake_other(name):
        def _(*a, **k):
            counts[name] += 1
            raise RuntimeError(f"{name} should not be called without cascade")
        return _

    with patch("bim_platform.build.orchestrator.run_layout_validator", side_effect=fake_layout), \
         patch("bim_platform.build.orchestrator.run_facade_agent",     side_effect=fake_other("facade")), \
         patch("bim_platform.build.orchestrator.run_mep_agent",        side_effect=fake_other("mep")):
        edit_building(base, "Add a fourth bedroom", target="layout")

    assert counts == {"facade": 0, "mep": 0, "layout": 1}
    print("✓ layout edit (cascade=False) reruns layout only")


def main() -> int:
    print("Running stub tests (no API calls)...\n")
    test_schemas_validate()
    test_merge_to_spec()
    test_palette_parser()
    test_pascal_export()
    test_edit_palette_no_llm()
    test_edit_facade_only()
    test_edit_layout_no_cascade_default()
    print("\nAll stub tests passed ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
