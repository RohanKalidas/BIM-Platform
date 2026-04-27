"""bim_platform.schemas — Pydantic data contracts that span every phase."""
from .brief import Brief, ProgramItem
from .layout import Layout, Floor, Space, Door, Window, WallSide
from .facade import Facade, ExteriorFeature
from .mep import MEPStrategy, MEPZone
from .compliance import ComplianceReport, CheckResult, CheckStatus
from .structural import StructuralStrategy, GridLine, Column
from .building_spec import BuildingSpec
from .pipeline import AgentRun, PipelineResult

__all__ = [
    "Brief", "ProgramItem",
    "Layout", "Floor", "Space", "Door", "Window", "WallSide",
    "Facade", "ExteriorFeature",
    "MEPStrategy", "MEPZone",
    "ComplianceReport", "CheckResult", "CheckStatus",
    "StructuralStrategy", "GridLine", "Column",
    "BuildingSpec",
    "AgentRun", "PipelineResult",
]
