"""
ui/data/mock.py

Deterministic mock WorkspaceState generator.
Runs without a database connection — full UI development on any node.

Architecture Standard: Mind Over Metadata LLC — Peter Heller

Four scenarios — exercise every UI code path:
    1. Happy path          — all four steps complete
    2. Retry then success  — step 1 fails, retries, recovers
    3. Team partial fail   — one team member fails, non-blocking
    4. Hard failure        — persist fails, FAIL_TASK, session failed
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from registry.skills import SkillFQSN
from registry.tasks  import TaskFQSN
from registry.status import StepStatus, AgentType, OperatingMode
from registry.sentinels import (
    DELEGATION_NONE, ERROR_NONE, OUTPUT_NONE, VALID_TO_OPEN_ENDED
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ms(base: datetime, offset_ms: float) -> datetime:
    return base + timedelta(milliseconds=offset_ms)


# ── Entry Builders ─────────────────────────────────────────────────────────────

def _agent(step, skill, status, dur=820.0, retry=0, error=ERROR_NONE, t=None):
    t = t or _utcnow()
    return {
        "entry_id": str(uuid4()), "step": step,
        "agent_type": AgentType.AGENT.value,
        "skill_fqsn": skill.value, "fqsn_path": skill.value,
        "fqsn_hash": _sha256(f"{skill.value}:1.0.0"),
        "status": status.value, "retry_count": retry,
        "delegated_to": DELEGATION_NONE, "sub_entries": [],
        "tool_output": OUTPUT_NONE, "tool_exit_code": 0, "error": error,
        "started_at": t.isoformat(), "completed_at": _ms(t, dur).isoformat(),
        "duration_ms": dur,
    }


def _subagent(step, skill, status, sub_skills, dur=1640.0, t=None):
    t = t or _utcnow()
    per = dur / len(sub_skills)
    sub_entries = [
        _agent(i + 1, s, status, per, t=_ms(t, i * per))
        for i, s in enumerate(sub_skills)
    ]
    return {
        "entry_id": str(uuid4()), "step": step,
        "agent_type": AgentType.SUBAGENT.value,
        "skill_fqsn": skill.value, "fqsn_path": skill.value,
        "fqsn_hash": _sha256(f"{skill.value}:1.0.0"),
        "status": status.value, "retry_count": 0,
        "delegated_to": skill.value, "sub_entries": sub_entries,
        "tool_output": OUTPUT_NONE, "tool_exit_code": 0, "error": ERROR_NONE,
        "started_at": t.isoformat(), "completed_at": _ms(t, dur).isoformat(),
        "duration_ms": dur,
    }


def _team(step, skill, members, dur=2100.0, t=None):
    t = t or _utcnow()
    member_results = [
        {"role": role, "skill_fqsn": s.value, "status": st.value,
         "output": f"output_{role}" if st == StepStatus.COMPLETED else OUTPUT_NONE,
         "error": ERROR_NONE if st == StepStatus.COMPLETED else f"{role} timeout",
         "completed_at": _ms(t, dur * 0.9).isoformat()}
        for role, s, st in members
    ]
    sub_entries = [
        _agent(i + 1, s, st, dur * 0.85, t=t)
        for i, (_, s, st) in enumerate(members)
    ]
    overall = (StepStatus.COMPLETED
               if any(st == StepStatus.COMPLETED for _, _, st in members)
               else StepStatus.FAILED)
    return {
        "entry_id": str(uuid4()), "step": step,
        "agent_type": AgentType.TEAM.value,
        "skill_fqsn": skill.value, "fqsn_path": skill.value,
        "fqsn_hash": _sha256(f"{skill.value}:1.0.0"),
        "status": overall.value, "retry_count": 0,
        "delegated_to": "+".join(r for r, _, _ in members),
        "sub_entries": sub_entries,
        "team_result": {
            "team_skill_fqsn": skill.value,
            "member_results": member_results,
            "aggregated_output": {r: f"output_{r}" for r, _, st in members
                                  if st == StepStatus.COMPLETED},
        },
        "tool_output": OUTPUT_NONE, "tool_exit_code": 0, "error": ERROR_NONE,
        "started_at": t.isoformat(), "completed_at": _ms(t, dur).isoformat(),
        "duration_ms": dur,
    }


def _python(step, skill, status, rows=1, dur=45.0, t=None):
    t = t or _utcnow()
    return {
        "entry_id": str(uuid4()), "step": step,
        "agent_type": AgentType.PYTHON.value,
        "skill_fqsn": skill.value, "fqsn_path": skill.value,
        "fqsn_hash": _sha256(f"{skill.value}:1.0.0"),
        "status": status.value, "retry_count": 0,
        "delegated_to": DELEGATION_NONE, "sub_entries": [],
        "tool_output": f"rows_written={rows}" if status == StepStatus.COMPLETED else OUTPUT_NONE,
        "tool_exit_code": 0 if status == StepStatus.COMPLETED else 1,
        "error": ERROR_NONE if status == StepStatus.COMPLETED else "asyncpg connection timeout",
        "started_at": t.isoformat(), "completed_at": _ms(t, dur).isoformat(),
        "duration_ms": dur,
    }


# ── Session Scenarios ──────────────────────────────────────────────────────────

_TEAM_MEMBERS_ALL_OK = [
    ("researcher",  SkillFQSN.SEARCH_TAVILY,   StepStatus.COMPLETED),
    ("synthesizer", SkillFQSN.TEXT_SUMMARIZE,  StepStatus.COMPLETED),
    ("formatter",   SkillFQSN.TEXT_TRANSFORM,  StepStatus.COMPLETED),
]
_TEAM_MEMBERS_ONE_FAIL = [
    ("researcher",  SkillFQSN.SEARCH_TAVILY,   StepStatus.FAILED),
    ("synthesizer", SkillFQSN.TEXT_SUMMARIZE,  StepStatus.COMPLETED),
    ("formatter",   SkillFQSN.TEXT_TRANSFORM,  StepStatus.COMPLETED),
]
_SUB_SKILLS = [SkillFQSN.VALIDATION_FORMAT, SkillFQSN.VALIDATION_SCHEMA]


def _happy(base, task_id):
    t = base
    entries = [
        _agent(1,   SkillFQSN.DATA_EXTRACT,          StepStatus.COMPLETED, 743.0,  t=t),
        _subagent(2, SkillFQSN.VALIDATION_COMPOSITE, StepStatus.COMPLETED, _SUB_SKILLS, 1420.0, t=_ms(t, 743)),
        _team(3,    SkillFQSN.TEAM_ENRICH,           _TEAM_MEMBERS_ALL_OK, 2180.0, t=_ms(t, 2163)),
        _python(4,  SkillFQSN.INFRA_PYTHON_PERSIST,  StepStatus.COMPLETED, 1, 38.0, t=_ms(t, 4343)),
    ]
    total_ms = 4381.0
    return _session(task_id, base, total_ms, entries, 0, False, "completed", OperatingMode.MAAS)


def _retry_success(base, task_id):
    t = base
    entries = [
        _agent(1, SkillFQSN.DATA_EXTRACT, StepStatus.FAILED,    612.0, 0,
               "JSON parse error — malformed LLM output", t=t),
        _agent(1, SkillFQSN.DATA_EXTRACT, StepStatus.RETRIED,   5012.0, 1, t=_ms(t, 617)),
        _agent(1, SkillFQSN.DATA_EXTRACT, StepStatus.COMPLETED, 891.0,  1, t=_ms(t, 5629)),
        _subagent(2, SkillFQSN.VALIDATION_COMPOSITE, StepStatus.COMPLETED, _SUB_SKILLS, 1610.0, t=_ms(t, 6520)),
        _team(3, SkillFQSN.TEAM_ENRICH, _TEAM_MEMBERS_ALL_OK, 2340.0, t=_ms(t, 8130)),
        _python(4, SkillFQSN.INFRA_PYTHON_PERSIST, StepStatus.COMPLETED, 1, 41.0, t=_ms(t, 10470)),
    ]
    total_ms = 10511.0
    return _session(task_id, base, total_ms, entries, 1, False, "completed", OperatingMode.MAAS)


def _team_partial(base, task_id):
    t = base
    entries = [
        _agent(1, SkillFQSN.DATA_EXTRACT, StepStatus.COMPLETED, 801.0, t=t),
        _subagent(2, SkillFQSN.VALIDATION_COMPOSITE, StepStatus.COMPLETED, _SUB_SKILLS, 1380.0, t=_ms(t, 801)),
        _team(3, SkillFQSN.TEAM_ENRICH, _TEAM_MEMBERS_ONE_FAIL, 2200.0, t=_ms(t, 2181)),
        _python(4, SkillFQSN.INFRA_PYTHON_PERSIST, StepStatus.COMPLETED, 1, 39.0, t=_ms(t, 4381)),
    ]
    total_ms = 4420.0
    return _session(task_id, base, total_ms, entries, 1, False, "completed", OperatingMode.HYBRID)


def _hard_fail(base, task_id):
    t = base
    entries = [
        _agent(1, SkillFQSN.DATA_EXTRACT, StepStatus.COMPLETED, 760.0, t=t),
        _subagent(2, SkillFQSN.VALIDATION_COMPOSITE, StepStatus.COMPLETED, _SUB_SKILLS, 1290.0, t=_ms(t, 760)),
        _team(3, SkillFQSN.TEAM_ENRICH, _TEAM_MEMBERS_ALL_OK, 2050.0, t=_ms(t, 2050)),
        _python(4, SkillFQSN.INFRA_PYTHON_PERSIST, StepStatus.FAILED, 0, 5001.0, t=_ms(t, 4100)),
    ]
    total_ms = 9101.0
    return _session(task_id, base, total_ms, entries, 1, True, "failed", OperatingMode.MAAS)


def _session(task_id, base, total_ms, entries, errors, is_failed, status, mode):
    return {
        "task_id": task_id,
        "task_fqsn": TaskFQSN.PIPELINE_ACMS_PROOF.value,
        "task_version": "1.0.0",
        "session_id": str(uuid4()),
        "operating_mode": mode.value,
        "step_count": len(entries),
        "error_count": errors,
        "is_failed": is_failed,
        "status": status,
        "created_at": base.isoformat(),
        "completed_at": _ms(base, total_ms).isoformat(),
        "total_duration_ms": total_ms,
        "entries": entries,
    }


_SCENARIO_FNS = [_happy, _retry_success, _team_partial, _happy,
                 _happy, _retry_success, _team_partial, _hard_fail,
                 _happy, _retry_success]


def generate_mock_sessions(count: int = 10, seed: int = 42, hours_back: int = 24) -> list[dict]:
    """
    Deterministic mock sessions. Same seed = same data.
    Spread over hours_back hours in the past, newest first.
    """
    rng = random.Random(seed)
    now = _utcnow()
    sessions = []
    for i in range(count):
        offset = rng.randint(0, hours_back * 60)
        base = now - timedelta(minutes=offset)
        task_id = _sha256(f"mock_task_{seed}_{i}")
        sessions.append(_SCENARIO_FNS[i % len(_SCENARIO_FNS)](base, task_id))
    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return sessions


def generate_mock_registry(seed: int = 42) -> dict:
    """Mock skill and task registry records for Panel 2."""
    rng = random.Random(seed)
    now = _utcnow()
    skill_records = []
    for skill in list(SkillFQSN):
        created = now - timedelta(days=rng.randint(30, 90))
        v1_hash = _sha256(f"{skill.value}:1.0.0:origin")
        record = {
            "fqsn": skill.value, "version": "1.0.0",
            "fqsn_hash": v1_hash, "previous_hash": "",
            "valid_from": created.isoformat(),
            "valid_to": VALID_TO_OPEN_ENDED.isoformat(),
            "is_current": True, "is_tool_node": "infra" in skill.value,
            "system_md_length": rng.randint(400, 1200),
            "domain": skill.value.split("/")[1],
        }
        skill_records.append(record)
        if rng.random() > 0.6:
            v2_created = created + timedelta(days=rng.randint(5, 20))
            v2_hash = _sha256(f"{skill.value}:1.1.0:updated")
            record["valid_to"] = v2_created.isoformat()
            record["is_current"] = False
            skill_records.append({
                **record,
                "version": "1.1.0", "fqsn_hash": v2_hash,
                "previous_hash": v1_hash,
                "valid_from": v2_created.isoformat(),
                "valid_to": VALID_TO_OPEN_ENDED.isoformat(),
                "is_current": True,
                "system_md_length": rng.randint(400, 1200),
            })
    return {
        "skill_records": skill_records,
        "task_records": [{
            "fqsn": TaskFQSN.PIPELINE_ACMS_PROOF.value,
            "version": "1.0.0",
            "fqsn_hash": _sha256("tasks/pipeline/acms_proof:1.0.0"),
            "previous_hash": "",
            "description": "ACMS Proof of Concept — all four node types",
            "operating_mode": "maas",
            "step_count": 4,
            "has_subagents": True,
            "has_teams": True,
            "valid_from": (now - timedelta(days=45)).isoformat(),
            "valid_to": VALID_TO_OPEN_ENDED.isoformat(),
            "is_current": True,
        }],
    }
