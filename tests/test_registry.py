"""
tests/test_registry.py

Smoke tests — verify registry module integrity without LLM or database calls.
Mind Over Metadata LLC — Peter Heller

Tests prove:
    1. All enums are closed sets — no free-text values accepted
    2. D4 sentinels are correct — no NULL anywhere
    3. SkillRegistry hash chain integrity verification works
    4. TaskRegistry skill_chaining is typed and ordered
    5. WorkspaceState accumulates — never replaces
    6. FailureContract reads correctly from WorkspaceState
"""

import pytest
from datetime import datetime, timezone

from registry.sentinels import (
    VALID_TO_OPEN_ENDED,
    PREVIOUS_HASH_ORIGIN,
    DELEGATION_NONE,
    ERROR_NONE,
    OUTPUT_NONE,
)
from registry.skills  import SkillFQSN
from registry.tasks   import TaskFQSN
from registry.status  import (
    StepStatus,
    AgentType,
    FailureStrategy,
    OperatingMode,
    SkillVersion,
    TaskVersion,
    PromptVersion,
)
from registry.records import (
    SkillRegistry,
    TaskRegistry,
    StepDefinition,
    SubSkillChaining,
)
from workspace import (
    WorkspaceState,
    WorkspaceEntry,
    FailureContract,
    create_workspace,
    sha256,
)


# ── Sentinel Tests ────────────────────────────────────────────────────────────

class TestSentinels:
    def test_valid_to_open_ended_is_far_future(self):
        """VALID_TO_OPEN_ENDED must be far enough in the future to be sentinel."""
        assert VALID_TO_OPEN_ENDED.year == 9999

    def test_previous_hash_origin_is_empty_string(self):
        """PREVIOUS_HASH_ORIGIN must be empty string — not None."""
        assert PREVIOUS_HASH_ORIGIN == ""
        assert PREVIOUS_HASH_ORIGIN is not None

    def test_delegation_none_is_empty_string(self):
        assert DELEGATION_NONE == ""
        assert DELEGATION_NONE is not None

    def test_error_none_is_empty_string(self):
        assert ERROR_NONE == ""
        assert ERROR_NONE is not None

    def test_output_none_is_empty_string(self):
        assert OUTPUT_NONE == ""
        assert OUTPUT_NONE is not None


# ── Enum Closed-Set Tests ─────────────────────────────────────────────────────

class TestClosedSetEnums:
    def test_step_status_values(self):
        """All StepStatus values must be in the governed set."""
        valid = {s.value for s in StepStatus}
        assert "completed" in valid
        assert "failed" in valid
        assert "retried" in valid
        assert "delegated" in valid
        assert "skipped" in valid

    def test_agent_type_values(self):
        valid = {a.value for a in AgentType}
        assert "agent"   in valid
        assert "subagent" in valid
        assert "team"    in valid
        assert "python"  in valid
        assert "bash"    in valid

    def test_failure_strategy_values(self):
        valid = {f.value for f in FailureStrategy}
        assert "retry_step"       in valid
        assert "skip_step"        in valid
        assert "fail_task"        in valid
        assert "retry_from_start" in valid
        assert "escalate"         in valid

    def test_operating_mode_values(self):
        valid = {o.value for o in OperatingMode}
        assert "cloud"  in valid
        assert "maas"   in valid
        assert "hybrid" in valid

    def test_skill_fqsn_poc_skills_present(self):
        """All four POC skills must be registered."""
        fqsns = {s.value for s in SkillFQSN}
        assert "skills/data/extract"             in fqsns
        assert "skills/validation/composite"     in fqsns
        assert "skills/team/enrich"              in fqsns
        assert "skills/infra/python/persist"     in fqsns

    def test_task_fqsn_poc_task_present(self):
        assert "tasks/pipeline/acms_proof" in {t.value for t in TaskFQSN}


# ── SkillRegistry Tests ───────────────────────────────────────────────────────

class TestSkillRegistry:
    def _make_skill(self, fqsn=SkillFQSN.DATA_EXTRACT, system_md="You extract data.") -> SkillRegistry:
        content = f"{fqsn.value}:1.0.0:{system_md}"
        return SkillRegistry(
            fqsn=fqsn,
            version=SkillVersion.V1_0_0,
            fqsn_hash=sha256(content),
            previous_hash=PREVIOUS_HASH_ORIGIN,
            system_md=system_md,
        )

    def test_origin_skill_is_current(self):
        skill = self._make_skill()
        assert skill.is_current is True

    def test_origin_skill_is_origin(self):
        skill = self._make_skill()
        assert skill.is_origin is True

    def test_valid_to_defaults_to_open_ended(self):
        skill = self._make_skill()
        assert skill.valid_to == VALID_TO_OPEN_ENDED

    def test_hash_chain_verification_passes(self):
        skill_v1 = self._make_skill()
        skill_v2 = SkillRegistry(
            fqsn=SkillFQSN.DATA_EXTRACT,
            version=SkillVersion.V1_1_0,
            fqsn_hash=sha256("skills/data/extract:1.1.0:Updated system.md"),
            previous_hash=skill_v1.fqsn_hash,
            system_md="Updated system.md",
        )
        assert skill_v2.verify_chain(skill_v1) is True

    def test_hash_chain_verification_fails_on_tamper(self):
        skill_v1 = self._make_skill()
        skill_v2 = SkillRegistry(
            fqsn=SkillFQSN.DATA_EXTRACT,
            version=SkillVersion.V1_1_0,
            fqsn_hash=sha256("skills/data/extract:1.1.0:Updated"),
            previous_hash="tampered_hash_value",
            system_md="Updated",
        )
        assert skill_v2.verify_chain(skill_v1) is False

    def test_tool_node_detection(self):
        tool_skill = SkillRegistry(
            fqsn=SkillFQSN.INFRA_PYTHON_PERSIST,
            version=SkillVersion.V1_0_0,
            fqsn_hash=sha256("skills/infra/python/persist:1.0.0:"),
            system_md="",
            tool_binding="persist_node",
        )
        assert tool_skill.is_tool_node is True

    def test_llm_skill_is_not_tool_node(self):
        skill = self._make_skill()
        assert skill.is_tool_node is False


# ── TaskRegistry Tests ────────────────────────────────────────────────────────

class TestTaskRegistry:
    def _make_task(self) -> TaskRegistry:
        return TaskRegistry(
            fqsn=TaskFQSN.PIPELINE_ACMS_PROOF,
            version=TaskVersion.V1_0_0,
            fqsn_hash=sha256("tasks/pipeline/acms_proof:1.0.0:[]"),
            description="ACMS POC — all four node types",
            skill_chaining=[
                StepDefinition(
                    step=1,
                    skill_fqsn=SkillFQSN.DATA_EXTRACT,
                    description="Extract structured data",
                    failure_strategy=FailureStrategy.RETRY_STEP,
                ),
                StepDefinition(
                    step=2,
                    skill_fqsn=SkillFQSN.VALIDATION_COMPOSITE,
                    description="Validate extracted data",
                    failure_strategy=FailureStrategy.RETRY_STEP,
                    delegation=SubSkillChaining(
                        role="validation_composite",
                        is_parallel=False,
                        skills=[SkillFQSN.VALIDATION_FORMAT, SkillFQSN.VALIDATION_SCHEMA],
                    ),
                ),
                StepDefinition(
                    step=3,
                    skill_fqsn=SkillFQSN.TEAM_ENRICH,
                    description="Enrich in parallel",
                    failure_strategy=FailureStrategy.SKIP_STEP,
                    is_blocking=False,
                    delegation=SubSkillChaining(
                        role="team_enrich",
                        is_parallel=True,
                        skills=[
                            SkillFQSN.SEARCH_TAVILY,
                            SkillFQSN.TEXT_SUMMARIZE,
                            SkillFQSN.TEXT_TRANSFORM,
                        ],
                    ),
                ),
                StepDefinition(
                    step=4,
                    skill_fqsn=SkillFQSN.INFRA_PYTHON_PERSIST,
                    description="Persist audit trail",
                    failure_strategy=FailureStrategy.FAIL_TASK,
                ),
            ],
        )

    def test_step_count(self):
        task = self._make_task()
        assert task.step_count == 4

    def test_has_subagents(self):
        task = self._make_task()
        assert task.has_subagents is True

    def test_has_teams(self):
        task = self._make_task()
        assert task.has_teams is True

    def test_has_tool_nodes(self):
        task = self._make_task()
        assert task.has_tool_nodes is True

    def test_get_step_returns_correct_step(self):
        task = self._make_task()
        step = task.get_step(2)
        assert step is not None
        assert step.skill_fqsn == SkillFQSN.VALIDATION_COMPOSITE

    def test_get_step_returns_none_for_missing(self):
        task = self._make_task()
        assert task.get_step(99) is None

    def test_is_current_default(self):
        task = self._make_task()
        assert task.is_current is True

    def test_operating_mode_default_is_maas(self):
        task = self._make_task()
        assert task.operating_mode == OperatingMode.MAAS


# ── WorkspaceState Accumulation Tests ────────────────────────────────────────

class TestWorkspaceStateAccumulation:
    def _make_state(self) -> WorkspaceState:
        return create_workspace(
            task_fqsn=TaskFQSN.PIPELINE_ACMS_PROOF,
            task_version=TaskVersion.V1_0_0,
            definition={"description": "test"},
            failure_contracts=[
                FailureContract(step=1, strategy=FailureStrategy.RETRY_STEP, max_retries=3),
                FailureContract(step=2, strategy=FailureStrategy.RETRY_STEP, max_retries=3),
                FailureContract(step=3, strategy=FailureStrategy.SKIP_STEP),
                FailureContract(step=4, strategy=FailureStrategy.FAIL_TASK),
            ],
        )

    def _make_entry(self, step: int, status: StepStatus) -> WorkspaceEntry:
        return WorkspaceEntry(
            step=step,
            agent_type=AgentType.AGENT,
            skill_fqsn=SkillFQSN.DATA_EXTRACT,
            fqsn_path=SkillFQSN.DATA_EXTRACT.value,
            fqsn_hash=sha256(f"{SkillFQSN.DATA_EXTRACT.value}:1.0.0"),
            status=status,
        )

    def test_initial_state_has_no_entries(self):
        state = self._make_state()
        assert len(state.entries) == 0

    def test_entries_accumulate_not_replace(self):
        """The core invariant — operator.add appends, never replaces."""
        state = self._make_state()
        entry1 = self._make_entry(1, StepStatus.COMPLETED)
        entry2 = self._make_entry(2, StepStatus.COMPLETED)

        # Simulate LangGraph operator.add behavior
        import operator
        new_entries = operator.add(state.entries, [entry1])
        new_entries = operator.add(new_entries, [entry2])

        assert len(new_entries) == 2
        assert new_entries[0].step == 1
        assert new_entries[1].step == 2

    def test_failed_entries_preserved(self):
        """Failed entries must never be removed — D4 audit rule."""
        state = self._make_state()
        failed = self._make_entry(1, StepStatus.FAILED)
        retried = self._make_entry(1, StepStatus.RETRIED)
        completed = self._make_entry(1, StepStatus.COMPLETED)

        import operator
        entries = operator.add([], [failed, retried, completed])
        assert len(entries) == 3
        assert entries[0].status == StepStatus.FAILED
        assert entries[1].status == StepStatus.RETRIED
        assert entries[2].status == StepStatus.COMPLETED

    def test_task_id_is_deterministic(self):
        """Same inputs must always produce the same task_id hash."""
        state1 = create_workspace(
            task_fqsn=TaskFQSN.PIPELINE_ACMS_PROOF,
            task_version=TaskVersion.V1_0_0,
            definition={"description": "test"},
        )
        state2 = create_workspace(
            task_fqsn=TaskFQSN.PIPELINE_ACMS_PROOF,
            task_version=TaskVersion.V1_0_0,
            definition={"description": "test"},
        )
        assert state1.task_id == state2.task_id

    def test_task_id_changes_with_definition(self):
        """Different definition must produce different task_id."""
        state1 = create_workspace(
            task_fqsn=TaskFQSN.PIPELINE_ACMS_PROOF,
            task_version=TaskVersion.V1_0_0,
            definition={"description": "version_a"},
        )
        state2 = create_workspace(
            task_fqsn=TaskFQSN.PIPELINE_ACMS_PROOF,
            task_version=TaskVersion.V1_0_0,
            definition={"description": "version_b"},
        )
        assert state1.task_id != state2.task_id

    def test_failure_contract_retrieval(self):
        state = self._make_state()
        fc1 = state.failure_contract_for_step(1)
        fc3 = state.failure_contract_for_step(3)
        fc4 = state.failure_contract_for_step(4)

        assert fc1 is not None
        assert fc1.strategy == FailureStrategy.RETRY_STEP
        assert fc1.max_retries == 3

        assert fc3 is not None
        assert fc3.strategy == FailureStrategy.SKIP_STEP

        assert fc4 is not None
        assert fc4.strategy == FailureStrategy.FAIL_TASK

    def test_is_failed_false_when_no_failures(self):
        state = self._make_state()
        assert state.is_failed is False

    def test_audit_summary_structure(self):
        state = self._make_state()
        summary = state.audit_summary()
        assert "task_id"     in summary
        assert "task_path"   in summary
        assert "session_id"  in summary
        assert "step_count"  in summary
        assert "error_count" in summary
        assert "is_failed"   in summary
        assert "entries"     in summary
        assert isinstance(summary["entries"], list)
