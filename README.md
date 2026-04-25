# bim-platform

Successor to BIM Studio. End-to-end AI-driven IFC building generation across
arbitrary architectural typology.

## The pipeline

```
        ┌──────────────────────────────────────────────────────────┐
        │                       USER PROMPT                         │
        │      "3-story office complex in Shanghai with retail"     │
        └──────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────────────────────┐
        │                     ▼                                      │
        │   ┌──────────────────────────────────────────┐            │
        │   │  DESIGN  (bim_platform.design)           │            │
        │   │  Image-DB retrieval → GPT-Image-2        │            │
        │   │  Outputs: floor plan PNGs + exterior     │            │
        │   │  Multi-floor: floor n conditioned on n-1 │            │
        │   └──────────────────────────────────────────┘            │
        │                     │                                      │
        │                     ▼                                      │
        │   ┌──────────────────────────────────────────┐            │
        │   │  TRANSLATE  (bim_platform.translate)     │            │
        │   │  Floor plan PNG → Layout JSON via VLM    │            │
        │   │  Output: schemas.layout.Layout           │            │
        │   └──────────────────────────────────────────┘            │
        │                     │                                      │
        │                     ▼                                      │
        │   ┌──────────────────────────────────────────┐            │
        │   │  BUILD  (bim_platform.build)             │            │
        │   │  Brief + Layout-Validator + Facade +     │            │
        │   │  MEP + Compliance + Structural agents    │            │
        │   │  → IFC writer (library + procedural)     │            │
        │   └──────────────────────────────────────────┘            │
        │                     │                                      │
        │                     ▼                                      │
        │   IFC file + xeokit viewer                                 │
        └────────────────────────────────────────────────────────────┘
```

## Design rules

These are inviolable. Every architecture decision must respect them.

### 1. Three phases, three boundaries

Design, Translate, Build are independent modules. They communicate ONLY
through Pydantic schemas defined in `bim_platform.schemas`. No shared state,
no implicit coupling. Any phase can be tested or replaced independently.

### 2. Schemas are the spine

Everything that crosses a phase boundary is a Pydantic model. If a piece of
data isn't in a schema, it can't cross a boundary. This is what makes the
system testable, debuggable, and refactorable.

### 3. Best-effort generation, never refusal

The system never refuses a user request. If the IFC component library lacks
specific components (e.g., basketball hoop, MRI machine), the renderer falls
back to procedural primitives — generic boxes, extrusions, transformed
solids — to construct what the user asked for. The user is not warned about
inventory gaps. Quality scales with library coverage but never zeroes out.

### 4. Typology-agnostic core, typology-specific prompts

The schemas, orchestrator, agent loop, and IFC writer must be typology-
agnostic. They handle "rooms" or "zones" or "floorplates" without knowing
whether they describe a house or a hospital. Typology-specific knowledge
(what features a Victorian has, what an MRI suite needs) lives in PROMPTS,
not in code branches. Adding a new typology = adding new prompts + maybe
new primitive shapes + maybe new IFC components — never adding new agent
classes or modifying schemas.

### 5. Library-first, procedural-fallback

For every IFC element the renderer creates: try IFC library lookup first,
fall back to procedural primitive on no match. Track which is which so
generated buildings can report their library-vs-procedural ratio (useful
for prioritizing which IFC files to upload next).

### 6. Library mechanism reused from BIM Studio

The IFC component library is a postgres database. Users upload IFC files
through a disassemble UI; an extractor parses each file and indexes its
components by category, family, dimensions, and quality. This subsystem is
ported verbatim from BIM Studio's `extractor/` and `database/` modules.

## Repo layout

```
bim-platform/
├── pyproject.toml
├── README.md                              ← you are here
├── bim_platform/
│   ├── schemas/                           ← Pydantic data contracts
│   │   ├── brief.py                       ← typology-agnostic Brief
│   │   ├── layout.py                      ← Floor + Room/Zone
│   │   ├── facade.py                      ← extended ExteriorFeature
│   │   ├── mep.py                         ← residential + commercial MEP
│   │   ├── compliance.py                  ← code-check results
│   │   ├── structural.py                  ← grid + columns + lateral
│   │   ├── building_spec.py               ← merged renderer input
│   │   └── pipeline.py                    ← AgentRun + PipelineResult
│   ├── typology.py                        ← typology ontology
│   ├── library/                           ← IFC component library
│   │   ├── db.py                          ← postgres connection
│   │   ├── extractor.py                   ← upload → component rows (port)
│   │   ├── index.py                       ← search by category, dims, etc.
│   │   └── transplant.py                  ← copy geometry into target IFC
│   ├── build/
│   │   ├── orchestrator.py                ← pipeline + edit API
│   │   ├── agents/
│   │   │   ├── brief.py
│   │   │   ├── layout_validator.py        ← validates external Layout
│   │   │   ├── facade.py
│   │   │   ├── mep.py
│   │   │   ├── compliance.py              ← NEW
│   │   │   └── structural.py              ← NEW
│   │   ├── prompts/                       ← typology-keyed prompts
│   │   │   ├── residential/
│   │   │   ├── office/
│   │   │   ├── retail/
│   │   │   ├── education/
│   │   │   ├── healthcare/
│   │   │   ├── hospitality/
│   │   │   └── industrial/
│   │   └── render/
│   │       ├── ifc_writer.py              ← redesigned generate.py
│   │       └── primitives/
│   │           ├── walls.py
│   │           ├── openings.py
│   │           ├── roofs.py
│   │           ├── residential.py
│   │           └── commercial.py
│   ├── translate/                         ← Translate phase (week 9)
│   ├── design/                            ← Design phase (week 7)
│   ├── server/                            ← Flask + xeokit (port from bim-studio)
│   └── cli.py                             ← end-to-end command line
├── tests/                                 ← pytest, no API calls in unit tests
└── scripts/
    ├── ingest_ifc.py                      ← upload an IFC into library
    └── coverage_report.py                 ← what's in the library?
```

## Roadmap

### Phase 0 — foundations (weeks 1-2)
- Repo skeleton ✓
- Schema design (Brief, Layout, Facade, MEP, Compliance, Structural, BuildingSpec)
- Typology ontology populated for residential.single_family, office.class_a,
  office.suburban, retail.standalone, retail.mixed_use_ground,
  education.k12, education.higher_ed, healthcare.clinic, healthcare.hospital,
  hospitality.hotel, hospitality.restaurant, industrial.warehouse
- IFC library subsystem ported from BIM Studio
- Orchestrator + Brief agent + Layout-Validator + Facade + MEP ported
- IFC writer rewritten with library-first + procedural-fallback
- Geometry-transplant axis-convention fix from the start
- Residential parity smoke test

### Phase 1 — commercial typology (weeks 3-4)
- Commercial agent prompts (office, retail)
- Commercial primitives (curtain wall, structural glazing, parapets,
  mechanical screens, canopies)
- Commercial fixture placement (workstation grids, conference rooms,
  core-and-shell)
- Commercial MEP (VAV, FCU, AHU, chilled water loops, busways)
- First office demo

### Phase 2 — compliance + structural (weeks 5-6)
- Compliance Agent reads jurisdiction codebook excerpts
- Structural Agent picks grid, columns, lateral system, foundations
- Code-check passes (egress sizing, occupant load, ADA, fire ratings)
- Mixed-use building demo

### Phase 3 — Design phase (weeks 7-8)
- Image database (curate ~1000 references across typologies)
- GPT-Image-2 integration
- Multi-floor generation with previous-floor conditioning
- One typology with image-guided design working end-to-end

### Phase 4 — Translate phase (weeks 9-10)
- VLM extractor (Claude Sonnet vision) for floor plan PNGs → Layout JSON
- Handles residential vernacular plans + commercial column-grid plans
- Iteration loop with Design

### Phase 5 — integration + polish (weeks 11-12)
- Web UI redesign (three-phase pipeline)
- xeokit + IFC fidelity improvements
- End-to-end demos across multiple typologies
- v1.0

## What's NOT here

A few things deliberately excluded:

- **No texture/material rendering.** IFC stores material properties (colors,
  IFC material library refs). Photorealistic texturing is downstream of IFC
  and out of scope. If realistic renders are needed, pipe IFC into Blender/
  Unreal as a separate workflow.
- **No real-time collaboration.** Single-user generation. Multi-user editing
  on the same building is a post-v1 concern.
- **No 4D scheduling, 5D cost.** Just spatial geometry + MEP. Construction
  scheduling and quantity takeoff are out of scope.
- **No automatic BIM-360 / ACC sync.** Output is a local IFC file. Cloud
  integrations are post-v1.

## Status

Phase 0 in progress. Most recent commit: initial schema design.
