"""
schemas.pipeline — agent execution telemetry and pipeline result envelope.

Identical pattern to BIM Studio: each agent call produces an AgentRun
record (timing, tokens, label), the orchestrator aggregates them in a
PipelineResult, and edits return updated PipelineResults with cached
runs preserved verbatim.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

from .brief import Brief
from .layout import Layout
from .facade import Facade
from .mep import MEPStrategy
from .compliance import ComplianceReport
from .structural import StructuralStrategy
from .building_spec import BuildingSpec


class AgentRun(BaseModel):
    """One agent invocation's telemetry."""
    agent: str            # "brief_agent", "layout_validator", etc.
    duration_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False  # True if reused from a previous PipelineResult
    notes: Optional[str] = None


class PipelineResult(BaseModel):
    """Full pipeline output. Returned by generate() and edit()."""

    spec: BuildingSpec

    # All component outputs (may be None if not run for this typology)
    brief: Brief
    layout: Layout
    facade: Optional[Facade] = None
    mep: Optional[MEPStrategy] = None
    structural: Optional[StructuralStrategy] = None
    compliance: Optional[ComplianceReport] = None

    runs: list[AgentRun] = Field(default_factory=list)
    total_duration_s: float = 0.0

    # For the surgical edit API: which agents are fresh vs cached this turn
    fresh_agents: list[str] = Field(default_factory=list)
