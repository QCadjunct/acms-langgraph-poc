"""
registry/sentinels.py

D4 Named Defaults — eliminates NULL from two-value predicate logic.
Every sentinel is named. The name IS the documentation.

Architecture Standard: Mind Over Metadata LLC — Peter Heller
    Two-value predicate logic: a fact is either current or it is not.
    NULL is not a value — it is the absence of a value.
    Absence is not a valid state in a governed system.
    Every column that could be NULL gets a named sentinel instead.

D4 Rule: valid_to == VALID_TO_OPEN_ENDED means the record IS current.
         valid_to <  VALID_TO_OPEN_ENDED means the record WAS current.
         No NULL. No ambiguity. No three-value logic.
"""

from datetime import datetime

# ── Temporal Sentinels ────────────────────────────────────────────────────────

# Open-ended interval — replaces NULL in valid_to and deprecated_at.
# Last microsecond of 9999-12-31 UTC.
# SQL equivalent: DEFAULT '9999-12-31 23:59:59.999999'
# D4 meaning: "this record has no known end date — it is current"
VALID_TO_OPEN_ENDED: datetime = datetime(9999, 12, 31, 23, 59, 59, 999999)

# ── Hash Chain Sentinels ──────────────────────────────────────────────────────

# Origin hash — replaces NULL for the first version in a hash chain.
# Meaning: "this is the origin version — no predecessor exists"
# A non-empty previous_hash means "verify this against the predecessor"
PREVIOUS_HASH_ORIGIN: str = ""

# Origin diff — replaces NULL for the first version diff.
# Meaning: "this is the origin version — no diff exists"
DIFF_ORIGIN: dict = {}

# ── Agent Delegation Sentinels ────────────────────────────────────────────────

# No delegation — replaces NULL in WorkspaceEntry.delegated_to
# Meaning: "this step was executed directly — not delegated to a subagent or team"
DELEGATION_NONE: str = ""

# No error — replaces NULL in WorkspaceEntry.error
# Meaning: "this step completed without error"
ERROR_NONE: str = ""

# No output — replaces NULL in WorkspaceEntry.output for tool nodes
# Meaning: "this step produced no output — not the same as failed"
OUTPUT_NONE: str = ""
