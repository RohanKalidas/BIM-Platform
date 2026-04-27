"""
bim_platform.cli — command-line interface.

  bim generate "<prompt>" [--out building.json] [--external-layout layout.json]
  bim edit <prev.json> "<edit request>" --target <t> [--cascade] [--out new.json]
  bim export <result.json> --format pascal|spec [--out out.json]
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

from .schemas.layout import Layout
from .schemas.pipeline import PipelineResult
from .build.orchestrator import generate_building, edit_building
from .build.export_pascal import export_to_pascal


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_summary(result: PipelineResult) -> None:
    print()
    print("── Pipeline summary ──")
    print(f"  Total time: {result.total_duration_s}s")
    for r in result.runs:
        marker = "FRESH" if not r.cached else "cached"
        print(f"  {r.agent:20s} {marker:6s} {r.duration_s:>5.2f}s "
              f"in={r.input_tokens:>5} out={r.output_tokens:>5}")
    print(f"  Typology:  {result.brief.typology_key}")
    print(f"  Style:     {result.brief.architectural_style}")
    print(f"  Floors:    {len(result.layout.floors)}")
    print(f"  Spaces:    {sum(len(f.spaces) for f in result.layout.floors)}")
    print(f"  Footprint: {result.layout.footprint_width:.1f}m × "
          f"{result.layout.footprint_depth:.1f}m")
    if result.facade:
        print(f"  Facade features: {len(result.facade.exterior_features)}")
    if result.mep:
        print(f"  HVAC: {result.mep.hvac_type}, {result.mep.hvac_zones} zones")


def cmd_generate(args: argparse.Namespace) -> int:
    external_layout = None
    if args.external_layout:
        with open(args.external_layout) as f:
            external_layout = Layout.model_validate(json.load(f))
        print(f"Using external layout from {args.external_layout}")

    result = generate_building(
        args.prompt,
        external_layout=external_layout,
        parallel_specialists=not args.sequential,
    )
    _print_summary(result)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(result.model_dump_json(indent=2))
        print(f"\n→ Full PipelineResult written to {out_path}")

    if args.pascal:
        scene = export_to_pascal(result.spec)
        scene_path = Path(args.pascal)
        scene_path.write_text(json.dumps(scene.to_json_dict(), indent=2))
        n_nodes = len(scene.nodes)
        print(f"→ Pascal scene ({n_nodes} nodes) written to {scene_path}")
        print("  Import this JSON in Pascal Editor (https://pascaleditor.app or your local instance)")

    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    with open(args.prev) as f:
        prev = PipelineResult.model_validate(json.load(f))

    result = edit_building(
        prev, args.request, target=args.target, cascade=args.cascade,
    )
    _print_summary(result)

    if args.out:
        Path(args.out).write_text(result.model_dump_json(indent=2))
        print(f"\n→ Updated PipelineResult written to {args.out}")
    if args.pascal:
        scene = export_to_pascal(result.spec)
        Path(args.pascal).write_text(json.dumps(scene.to_json_dict(), indent=2))
        print(f"→ Pascal scene written to {args.pascal}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with open(args.input) as f:
        prev = PipelineResult.model_validate(json.load(f))

    if args.format == "pascal":
        scene = export_to_pascal(prev.spec)
        out = json.dumps(scene.to_json_dict(), indent=2)
    elif args.format == "spec":
        out = prev.spec.model_dump_json(indent=2)
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        return 2

    if args.out:
        Path(args.out).write_text(out)
        print(f"→ Wrote {args.format} to {args.out}")
    else:
        print(out)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="bim", description="bim-platform CLI")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="Generate a building from a prompt")
    gen.add_argument("prompt")
    gen.add_argument("--external-layout", help="path to a Layout JSON file")
    gen.add_argument("--out", help="path to write full PipelineResult JSON")
    gen.add_argument("--pascal", help="path to write Pascal scene JSON")
    gen.add_argument("--sequential", action="store_true",
                     help="Run Facade and MEP sequentially instead of parallel")
    gen.set_defaults(func=cmd_generate)

    edt = sub.add_parser("edit", help="Edit a previous generation")
    edt.add_argument("prev", help="path to a previous PipelineResult JSON")
    edt.add_argument("request", help="the edit request, in plain English")
    edt.add_argument("--target", required=True,
                     choices=["palette", "materials", "facade", "mep", "layout", "brief"])
    edt.add_argument("--cascade", action="store_true",
                     help="Also rerun downstream agents (only for layout/brief)")
    edt.add_argument("--out", help="path to write updated PipelineResult JSON")
    edt.add_argument("--pascal", help="path to write Pascal scene JSON")
    edt.set_defaults(func=cmd_edit)

    exp = sub.add_parser("export", help="Export a spec to a target format")
    exp.add_argument("input", help="path to a PipelineResult JSON")
    exp.add_argument("--format", required=True, choices=["pascal", "spec"])
    exp.add_argument("--out", help="path to write output (default: stdout)")
    exp.set_defaults(func=cmd_export)

    args = parser.parse_args()
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())