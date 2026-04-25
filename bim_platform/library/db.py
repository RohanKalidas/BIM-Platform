"""
library.db — PostgreSQL access for the IFC component library.

Ported from BIM Studio's database/db.py with two changes:
  - Neo4j removed (the new platform uses postgres only for now)
  - Schema migrated to bim_platform tables (see schema.sql in scripts/)

Components are stored across two tables:
  projects   — one row per uploaded IFC file
  components — one row per IFC element extracted from a file

The same context manager pattern is preserved for compatibility with
ported transplant and extractor code.
"""
from __future__ import annotations
import os
import logging
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ── connection pool ─────────────────────────────────────────────────────
_pg_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "bim_platform"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
        )
    return _pg_pool


@contextmanager
def get_db_connection(cursor_factory=None):
    """
    Yields (conn, cursor). Auto-commits on clean exit, rolls back on exception.

    Usage:
        with get_db_connection(cursor_factory=psycopg2.extras.RealDictCursor) as (conn, cur):
            cur.execute("SELECT * FROM components WHERE category = %s", (cat,))
            rows = cur.fetchall()
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield conn, cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    finally:
        pool.putconn(conn)


def close_pool():
    """Close all connections in the pool. Call at process exit."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None
