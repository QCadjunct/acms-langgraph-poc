"""
registry/__init__.py

ACMS Registry Package — public API.
Mind Over Metadata LLC — Peter Heller

Import from here. Not from submodules directly.
"""

from registry.sentinels import (
    VALID_TO_OPEN_ENDED,
    PREVIOUS_HASH_ORIGIN,
    DIFF_ORIGIN,
    DELEGATION_NONE,
    ERROR_NONE,
    OUTPUT_NONE,
)

from registry.skills import SkillFQSN

from registry.tasks import TaskFQSN

from registry.status import (
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

from registry.db import (
    DatabaseRegistry,
    DatabaseConfig,
    DatabaseRole,
    SslMode,
    SCHEMA_DDL,
)

__all__ = [
    # Sentinels
    "VALID_TO_OPEN_ENDED",
    "PREVIOUS_HASH_ORIGIN",
    "DIFF_ORIGIN",
    "DELEGATION_NONE",
    "ERROR_NONE",
    "OUTPUT_NONE",
    # FQSN enums
    "SkillFQSN",
    "TaskFQSN",
    # Status enums
    "StepStatus",
    "AgentType",
    "FailureStrategy",
    "OperatingMode",
    "SkillVersion",
    "TaskVersion",
    "PromptVersion",
    # Registry records
    "SkillRegistry",
    "TaskRegistry",
    "StepDefinition",
    "SubSkillChaining",
    # Database
    "DatabaseRegistry",
    "DatabaseConfig",
    "DatabaseRole",
    "SslMode",
    "SCHEMA_DDL",
]
