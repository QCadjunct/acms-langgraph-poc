"""
registry/tasks.py

Global Task Registry — Fully Qualified Task Names (FQTN).
The filesystem path IS the identifier. The enum value IS the FQTN.

Architecture Standard: Mind Over Metadata LLC — Peter Heller
    A Task IS a workflow. The task definition IS the spec.
    skill_chaining is the happy path — ordered, typed, governed.
    Failure contract is the exception path — conditional edges, governed by spec.
    Sub-skill chaining is delegation — subagent or team handles it internally.
    Change the task = new version = new hash = RegistryEvent fires.

Task Taxonomy (three levels):
    L1 — domain     (pipeline, text, data, research)
    L2 — subdomain  (acms_proof, full_chain, extract_validate)
    L3 — name       (leaf — the task itself)

POC Task:
    tasks/pipeline/acms_proof
        Proves ALL of:
            Single Agent node
            Subagent delegation (Task-Call-Task)
            Team parallel execution ($WFLAND barrier)
            Python tool node (deterministic, audited)
            Failure contract (governed by spec, not code)
            Complete audit trail (WorkspaceState → PostgreSQL)
"""

from enum import Enum


class TaskFQSN(str, Enum):

    # ── Pipeline Tasks ────────────────────────────────────────────────────────

    PIPELINE_ACMS_PROOF    = "tasks/pipeline/acms_proof"
    # THE POC TASK — proves the ACMS/LangGraph thesis.
    #
    # skill_chaining (happy path):
    #     Step 1: DATA_EXTRACT           ← Agent node
    #     Step 2: VALIDATION_COMPOSITE   ← Subagent node (Task-Call-Task)
    #     Step 3: TEAM_ENRICH            ← Team node ($WFLAND barrier)
    #     Step 4: INFRA_PYTHON_PERSIST   ← Python tool node
    #
    # sub_skill_chaining (VALIDATION_COMPOSITE internal):
    #     Step 2a: VALIDATION_FORMAT
    #     Step 2b: VALIDATION_SCHEMA
    #
    # member_skill_chaining (TEAM_ENRICH internal):
    #     researcher:  [SEARCH_TAVILY]
    #     synthesizer: [TEXT_SUMMARIZE]
    #     formatter:   [TEXT_TRANSFORM]
    #
    # failure_contract:
    #     If VALIDATION_COMPOSITE fails → retry DATA_EXTRACT (max 3)
    #     If retry exhausted → INFRA_PYTHON_PERSIST with FAILED status
    #     If TEAM_ENRICH member fails → log + continue (non-blocking)
    #     If INFRA_PYTHON_PERSIST fails → raise (blocking — audit required)

    PIPELINE_FULL_CHAIN    = "tasks/pipeline/full_chain"
    # Full production pipeline — all skill domains.
    # Phase 2 — defined now, implemented later.

    PIPELINE_INGEST_ONLY   = "tasks/pipeline/ingest_only"
    # Lightweight ingest — extract + validate only.

    # ── Text Tasks ────────────────────────────────────────────────────────────

    TEXT_TRANSFORM         = "tasks/text/transform"
    # Single-step text transformation.

    TEXT_VALIDATE_TRANSFORM = "tasks/text/validate_transform"
    # Validate then transform — two-step sequential.

    TEXT_SUMMARIZE_CLASSIFY = "tasks/text/summarize_classify"
    # Summarize then classify — two-step sequential.

    # ── Data Tasks ────────────────────────────────────────────────────────────

    DATA_EXTRACT_STRUCTURE  = "tasks/data/extract_structure"
    # Extract raw input → structure into schema.

    DATA_EXTRACT_VALIDATE_ENRICH = "tasks/data/extract_validate_enrich"
    # Full data pipeline — extract → validate → enrich.

    # ── Research Tasks ────────────────────────────────────────────────────────

    RESEARCH_FULL          = "tasks/research/full"
    # Full research pipeline — search + synthesize + validate + format.
    # Phase 2.
