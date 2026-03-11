# system_md/

One `system.md` file per registered skill. The filename matches the FQSN leaf name.

## Structure

```
system_md/
    data_extract.md           ← skills/data/extract
    validation_format.md      ← skills/validation/format
    validation_schema.md      ← skills/validation/schema
    validation_composite.md   ← skills/validation/composite (coordinator)
    search_tavily.md          ← skills/search/tavily
    text_summarize.md         ← skills/text/summarize
    text_transform.md         ← skills/text/transform
    # Note: infra/python/persist has NO system.md — governed by function signature
```

## The Contract

Each `system.md` is the **behavioral contract** for its skill. It is:

- The sole source of truth for what the LLM does in that node
- Versioned in `SkillRegistry` — change it → new `fqsn_hash` → `RegistryEvent` fires
- The **Ignition Key** component 1 (with `TaskRegistry` + `SkillFQSN` registry)

## In the POC

The POC embeds `system.md` content directly in `tasks/acms_proof.py` for simplicity. In production, each file here is read at graph construction time via FQSN resolution:

```python
def load_system_md(fqsn: SkillFQSN) -> str:
    leaf = fqsn.value.split("/")[-1].replace("/", "_")
    path = Path(__file__).parent.parent / "system_md" / f"{leaf}.md"
    return path.read_text()
```

## Universal system.md Architecture

All four major agentic tool formats are the same behavioral contract:

| Tool | File | Standard |
|---|---|---|
| Claude Code | `SKILL.md` | This repo |
| Fabric | `system.md` | Daniel Miessler |
| OpenAI Codex | `AGENTS.md` | OpenAI |
| Gemini | `GEMINI.md` | Google |

The Universal `system.md` thesis: they are all the same thing. One format to govern them all.
