"""bim_platform.library — IFC component storage, search, transplant."""
from .db import get_db_connection, close_pool
from .transplant import GeometryLibrary
from .index import (
    category_counts, total_components,
    coverage_for_typology, has_any_components,
)

__all__ = [
    "get_db_connection", "close_pool",
    "GeometryLibrary",
    "category_counts", "total_components",
    "coverage_for_typology", "has_any_components",
]
