"""
schemas.compliance — code compliance check results.

The Compliance Agent reads jurisdiction-specific code excerpts (passed in
via the prompt) and checks the proposed Brief + Layout + MEP for issues.
Output is a list of CheckResults: passed, failed, or warning, with
human-readable explanation and optional fix suggestion.

This agent does NOT auto-fix. It surfaces issues for the orchestrator (or
the user) to resolve. In best-effort mode, the orchestrator may proceed
with warnings present.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


CheckStatus = Literal["pass", "warning", "fail"]


class CheckResult(BaseModel):
    """One code-check result."""
    check_id: str           # e.g. "ibc.1004.5.egress_width", "ada.404.2.5.door_clear_width"
    code_ref: str           # human-readable ref
    status: CheckStatus
    description: str        # what was checked, what was found
    affected_spaces: list[str] = Field(default_factory=list)  # space names
    suggested_fix: Optional[str] = None


class ComplianceReport(BaseModel):
    """Full compliance check across all checked codes."""

    codes_checked: list[str]   # e.g. ["IBC", "ADA", "ASHRAE-90.1"]
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def passes(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == "warning")

    @property
    def failures(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def is_compliant(self) -> bool:
        """True iff no failures (warnings allowed in best-effort mode)."""
        return self.failures == 0
