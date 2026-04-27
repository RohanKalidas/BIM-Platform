"""
library.index — coverage queries over the postgres component index.

Used by:
  - the orchestrator, to decide whether to pull library components or
    fall back to procedural primitives
  - scripts/coverage_report.py for human-readable inventory reports

Best-effort philosophy: even if a typology has zero matching components,
generation still proceeds. This module just answers "do you have inventory
for X?" — it does NOT block generation.
"""
from __future__ import annotations
import psycopg2.extras
from .db import get_db_connection


def category_counts() -> dict[str, int]:
    """Return {category: count} across all done projects."""
    with get_db_connection(cursor_factory=psycopg2.extras.RealDictCursor) as (conn, cur):
        cur.execute("""
            SELECT c.category, COUNT(*) as n
            FROM components c
            JOIN projects p ON p.id = c.project_id
            WHERE p.status = 'done'
              AND p.filename NOT LIKE 'generated_%%'
            GROUP BY c.category
            ORDER BY n DESC
        """)
        return {row["category"]: row["n"] for row in cur.fetchall()}


def total_components() -> int:
    """Total components in the library."""
    with get_db_connection() as (conn, cur):
        cur.execute("""
            SELECT COUNT(*) FROM components c
            JOIN projects p ON p.id = c.project_id
            WHERE p.status = 'done' AND p.filename NOT LIKE 'generated_%%'
        """)
        return cur.fetchone()[0]


def coverage_for_typology(typology) -> dict[str, int]:
    """
    Return {category: count} for the categories the typology cares about.
    Categories with zero components are included so the caller can see gaps.
    """
    counts = category_counts()
    return {cat: counts.get(cat, 0) for cat in typology.component_categories}


def has_any_components(typology) -> bool:
    """Quick check: does the library have ANY components for this typology?"""
    return any(coverage_for_typology(typology).values())
