"""
ui/data/loader.py

Data loader — mock with live PostgreSQL fallback.
Same API regardless of data source. UI never knows the difference.

Architecture Standard: Mind Over Metadata LLC — Peter Heller

Strategy:
    1. Check ACMS_DATABASE_URL environment variable.
    2. If present and reachable → query PostgreSQL REPLICA_2.
    3. If absent or unreachable → return mock data silently.
    4. UI receives identical dict structure either way.
"""

import os
import json
import asyncio
from datetime import datetime, timezone

import polars as pl
import pyarrow as pa

from ui.data.mock import generate_mock_sessions, generate_mock_registry


# ── Connection Check ───────────────────────────────────────────────────────────

def _db_url() -> str | None:
    return os.environ.get("ACMS_DATABASE_URL") or None


async def _db_reachable(url: str) -> bool:
    try:
        import asyncpg
        conn = await asyncio.wait_for(asyncpg.connect(url), timeout=2.0)
        await conn.close()
        return True
    except Exception:
        return False


def using_live_db() -> bool:
    """Returns True if a live database connection is available."""
    url = _db_url()
    if not url:
        return False
    try:
        return asyncio.get_event_loop().run_until_complete(_db_reachable(url))
    except Exception:
        return False


# ── Session Data ───────────────────────────────────────────────────────────────

async def _load_sessions_live(url: str, limit: int) -> list[dict]:
    import asyncpg
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch(
            """
            SELECT task_id, task_fqsn, task_version, session_id,
                   operating_mode, entries,
                   created_at, completed_at, status,
                   (SELECT COUNT(*) FROM jsonb_array_elements(entries)) AS step_count,
                   (SELECT COUNT(*) FROM jsonb_array_elements(entries) e
                    WHERE e->>'status' IN ('failed','retried')) AS error_count,
                   EXTRACT(EPOCH FROM (completed_at - created_at)) * 1000 AS total_duration_ms
            FROM workspace_state
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        sessions = []
        for row in rows:
            s = dict(row)
            s["entries"] = json.loads(s["entries"]) if isinstance(s["entries"], str) else s["entries"]
            s["is_failed"] = s["status"] == "failed"
            sessions.append(s)
        return sessions
    finally:
        await conn.close()


def load_sessions(count: int = 20, seed: int = 42) -> list[dict]:
    """
    Load sessions — live if database available, mock otherwise.
    Returns list of session dicts. Source is transparent to callers.
    """
    url = _db_url()
    if url:
        try:
            loop = asyncio.new_event_loop()
            sessions = loop.run_until_complete(_load_sessions_live(url, count))
            loop.close()
            if sessions:
                return sessions
        except Exception:
            pass
    return generate_mock_sessions(count=count, seed=seed)


def load_registry(seed: int = 42) -> dict:
    """Load registry records — live if available, mock otherwise."""
    url = _db_url()
    if url:
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_load_registry_live(url))
            loop.close()
            if result:
                return result
        except Exception:
            pass
    return generate_mock_registry(seed=seed)


async def _load_registry_live(url: str) -> dict:
    import asyncpg
    conn = await asyncpg.connect(url)
    try:
        skill_rows = await conn.fetch(
            "SELECT fqsn, version, fqsn_hash, previous_hash, valid_from, valid_to,"
            " (tool_binding <> '') AS is_tool_node,"
            " (valid_to = '9999-12-31 23:59:59.999999+00') AS is_current,"
            " LENGTH(system_md) AS system_md_length,"
            " SPLIT_PART(fqsn, '/', 2) AS domain"
            " FROM skill_record ORDER BY fqsn, valid_from"
        )
        task_rows = await conn.fetch(
            "SELECT fqsn, version, fqsn_hash, previous_hash, description,"
            " operating_mode, valid_from, valid_to,"
            " (valid_to = '9999-12-31 23:59:59.999999+00') AS is_current"
            " FROM task_record ORDER BY fqsn, valid_from"
        )
        return {
            "skill_records": [dict(r) for r in skill_rows],
            "task_records":  [dict(r) for r in task_rows],
        }
    finally:
        await conn.close()


# ── Polars DataFrames ──────────────────────────────────────────────────────────

def sessions_to_df(sessions: list[dict]) -> pl.DataFrame:
    """
    Flatten sessions into a Polars DataFrame — one row per session.
    Suitable for Panel 1 summary table and Panel 3 timeline.
    """
    rows = []
    for s in sessions:
        rows.append({
            "session_id":      str(s.get("session_id", ""))[:8],
            "task_fqsn":       s.get("task_fqsn", ""),
            "status":          s.get("status", ""),
            "operating_mode":  s.get("operating_mode", ""),
            "step_count":      int(s.get("step_count", 0)),
            "error_count":     int(s.get("error_count", 0)),
            "is_failed":       bool(s.get("is_failed", False)),
            "total_ms":        float(s.get("total_duration_ms", 0.0)),
            "created_at":      s.get("created_at", ""),
        })
    return pl.DataFrame(rows)


def entries_to_df(sessions: list[dict]) -> pl.DataFrame:
    """
    Flatten all WorkspaceEntry records into a Polars DataFrame.
    One row per entry across all sessions — for step-level analysis.
    """
    rows = []
    for s in sessions:
        session_id = str(s.get("session_id", ""))[:8]
        status = s.get("status", "")
        for entry in s.get("entries", []):
            rows.append({
                "session_id":   session_id,
                "session_status": status,
                "step":         int(entry.get("step", 0)),
                "agent_type":   entry.get("agent_type", ""),
                "skill":        entry.get("fqsn_path", "").split("/")[-1],
                "skill_fqsn":   entry.get("fqsn_path", ""),
                "status":       entry.get("status", ""),
                "retry_count":  int(entry.get("retry_count", 0)),
                "duration_ms":  float(entry.get("duration_ms", 0.0)),
                "has_sub":      len(entry.get("sub_entries", [])) > 0,
                "error":        entry.get("error", ""),
            })
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def skill_records_to_df(registry: dict) -> pl.DataFrame:
    """Skill registry records as Polars DataFrame for Panel 2."""
    records = registry.get("skill_records", [])
    if not records:
        return pl.DataFrame()
    rows = []
    for r in records:
        rows.append({
            "fqsn":              r.get("fqsn", ""),
            "domain":            r.get("domain", r.get("fqsn", "").split("/")[1] if "/" in r.get("fqsn","") else ""),
            "version":           r.get("version", ""),
            "is_current":        bool(r.get("is_current", False)),
            "is_tool_node":      bool(r.get("is_tool_node", False)),
            "system_md_length":  int(r.get("system_md_length", 0)),
            "valid_from":        str(r.get("valid_from", ""))[:10],
        })
    return pl.DataFrame(rows)
