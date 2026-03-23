"""
ui/aces_monitor.py

ACMS Monitor — Three-Panel Marimo Notebook.
Marimo rule: create UIElements in one cell, access .value in a separate downstream cell.

Architecture Standard: Mind Over Metadata LLC — Peter Heller
Run as notebook:  marimo edit ui/aces_monitor.py
Run as app:       marimo run  ui/aces_monitor.py
"""

import marimo as mo

app = mo.App(width="full", app_title="ACMS Monitor — Mind Over Metadata LLC")


# ── Cell 1: marimo ────────────────────────────────────────────────────────────
@app.cell
def _mo():
    import marimo as mo
    return (mo,)


# ── Cell 2: imports ───────────────────────────────────────────────────────────
@app.cell
def _imports():
    import os, json, duckdb
    import polars as pl
    import pandas as pd
    from ui.data.loader import (
        load_sessions, load_registry,
        sessions_to_df, entries_to_df,
        skill_records_to_df, using_live_db,
    )
    return (
        os, json, duckdb, pl, pd,
        load_sessions, load_registry,
        sessions_to_df, entries_to_df,
        skill_records_to_df, using_live_db,
    )


# ── Cell 3: top-level controls (CREATE only) ──────────────────────────────────
@app.cell
def _controls(mo):
    session_count = mo.ui.slider(5, 50, value=10, step=5, label="Sessions")
    mock_seed     = mo.ui.number(start=1, stop=999, value=42, label="Seed")
    refresh_btn   = mo.ui.button(label="⟳ Refresh", kind="success")
    return session_count, mock_seed, refresh_btn


# ── Cell 4: load data (READ controls) ─────────────────────────────────────────
@app.cell
def _load_data(
    session_count, mock_seed, refresh_btn,
    load_sessions, load_registry,
    sessions_to_df, entries_to_df, skill_records_to_df,
):
    _ = refresh_btn.value
    sessions   = load_sessions(count=session_count.value, seed=mock_seed.value)
    registry   = load_registry(seed=mock_seed.value)
    session_df = sessions_to_df(sessions)
    entry_df   = entries_to_df(sessions)
    skill_df   = skill_records_to_df(registry)
    return sessions, registry, session_df, entry_df, skill_df


# ── Cell 5: header ────────────────────────────────────────────────────────────
@app.cell
def _header(mo, using_live_db):
    _src = (
        mo.md("🟢 **Live PostgreSQL**").callout(kind="success")
        if using_live_db()
        else mo.md("🟡 **Mock data** — set `ACMS_DATABASE_URL` in `.env`").callout(kind="warn")
    )
    header = mo.vstack([
        mo.md("# 🏛️ ACMS Monitor"),
        mo.md("**Mind Over Metadata LLC** — Peter Heller &nbsp;|&nbsp; `QCadjunct/acms-langgraph-poc`"),
        _src,
    ])
    return (header,)


# ── Cell 6: KPIs ──────────────────────────────────────────────────────────────
@app.cell
def _kpis(mo, session_df, entry_df):
    total      = len(session_df)
    completed  = session_df.filter(session_df["status"] == "completed").height
    failed     = session_df.filter(session_df["is_failed"]).height
    retried    = (entry_df.filter(entry_df["status"] == "retried").height
                  if not entry_df.is_empty() else 0)
    avg_ms     = round(float(session_df["total_ms"].mean() or 0), 0)
    error_rate = round((failed / total * 100) if total > 0 else 0.0, 1)
    kpis = mo.hstack([
        mo.stat(label="Sessions",     value=str(total)),
        mo.stat(label="Completed",    value=str(completed),       bordered=True),
        mo.stat(label="Failed",       value=str(failed),          bordered=True),
        mo.stat(label="Retries",      value=str(retried),         bordered=True),
        mo.stat(label="Avg Duration", value=f"{avg_ms:.0f} ms",   bordered=True),
        mo.stat(label="Error Rate",   value=f"{error_rate}%",     bordered=True),
    ], justify="start")
    return (kpis,)


# ══════════════════════════════════════════════════════════════════════════════
# PANEL 1 — AUDIT TRAIL
# ══════════════════════════════════════════════════════════════════════════════

# Cell 7: Panel 1 widgets (CREATE)
@app.cell
def _p1_widgets(mo):
    p1_status  = mo.ui.dropdown(
        options=["all", "completed", "failed"], value="all", label="Status")
    p1_mode    = mo.ui.dropdown(
        options=["all", "maas", "cloud", "hybrid"], value="all", label="Mode")
    p1_agents  = mo.ui.multiselect(
        options=["agent", "subagent", "team", "python"],
        value=["agent", "subagent", "team", "python"],
        label="Agent types")
    return p1_status, p1_mode, p1_agents


# Cell 8: Panel 1 content (READ widgets)
@app.cell
def _p1_content(mo, duckdb, pd, session_df, entry_df, p1_status, p1_mode, p1_agents):
    # Filter sessions
    _sf = session_df
    if p1_status.value != "all":
        _sf = _sf.filter(_sf["status"] == p1_status.value)
    if p1_mode.value != "all":
        _sf = _sf.filter(_sf["operating_mode"] == p1_mode.value)

    # Filter entries
    _ef = entry_df
    if not _ef.is_empty() and p1_agents.value:
        _ef = _ef.filter(_ef["agent_type"].is_in(p1_agents.value))

    session_table = mo.ui.table(_sf.to_pandas(), label="Sessions",
                                pagination=True, page_size=8)
    entry_table   = mo.ui.table(
        _ef.to_pandas() if not _ef.is_empty() else pd.DataFrame(),
        label="Step entries", pagination=True, page_size=10)

    # DuckDB aggregations
    if not entry_df.is_empty():
        _con = duckdb.connect()
        _con.register("entries", entry_df.to_arrow())
        _dur = _con.execute("""
            SELECT agent_type,
                   ROUND(AVG(duration_ms),0) AS avg_ms,
                   ROUND(MIN(duration_ms),0) AS min_ms,
                   ROUND(MAX(duration_ms),0) AS max_ms,
                   COUNT(*) AS count
            FROM entries GROUP BY agent_type ORDER BY avg_ms DESC
        """).pl()
        _sta = _con.execute("""
            SELECT status, COUNT(*) AS count
            FROM entries GROUP BY status ORDER BY count DESC
        """).pl()
        _con.close()
        dur_table = mo.ui.table(_dur.to_pandas(), label="Duration by agent type")
        sta_table = mo.ui.table(_sta.to_pandas(), label="Status distribution")
    else:
        dur_table = mo.md("_No entry data_")
        sta_table = mo.md("_No entry data_")

    panel1 = mo.vstack([
        mo.md("## 📋 Audit Trail Explorer"),
        mo.hstack([p1_status, p1_mode, p1_agents], justify="start"),
        mo.md("### Sessions"),
        session_table,
        mo.md("### Step Entries"),
        entry_table,
        mo.md("### Aggregations"),
        mo.hstack([dur_table, sta_table]),
    ])
    return (panel1,)


# ══════════════════════════════════════════════════════════════════════════════
# PANEL 2 — REGISTRY ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

# Cell 9: Panel 2 widgets (CREATE)
@app.cell
def _p2_widgets(mo, skill_df):
    _domains = (sorted(skill_df["domain"].unique().to_list())
                if not skill_df.is_empty() else [])
    p2_domain   = mo.ui.multiselect(options=_domains, value=[], label="Domain")
    p2_current  = mo.ui.checkbox(value=True, label="Current versions only")
    return p2_domain, p2_current


# Cell 10: Panel 2 content (READ widgets)
@app.cell
def _p2_content(mo, duckdb, pd, skill_df, registry, p2_domain, p2_current):
    _sf2 = skill_df
    if not _sf2.is_empty():
        if p2_current.value:
            _sf2 = _sf2.filter(_sf2["is_current"])
        if p2_domain.value:
            _sf2 = _sf2.filter(_sf2["domain"].is_in(p2_domain.value))

    skill_table = mo.ui.table(
        _sf2.to_pandas() if not _sf2.is_empty() else pd.DataFrame(),
        label="Skill records", pagination=True, page_size=10)

    if not skill_df.is_empty():
        _con2 = duckdb.connect()
        _con2.register("skills", skill_df.to_arrow())
        _dom = _con2.execute("""
            SELECT domain,
                   COUNT(*) AS total,
                   SUM(CASE WHEN is_current THEN 1 ELSE 0 END) AS current,
                   SUM(CASE WHEN is_tool_node THEN 1 ELSE 0 END) AS tool_nodes,
                   ROUND(AVG(system_md_length),0) AS avg_md_chars
            FROM skills GROUP BY domain ORDER BY total DESC
        """).pl()
        _ver = _con2.execute("""
            SELECT fqsn, COUNT(*) AS versions,
                   MIN(valid_from) AS first_registered,
                   MAX(valid_from) AS last_updated
            FROM skills GROUP BY fqsn ORDER BY versions DESC, fqsn
        """).pl()
        _con2.close()
        dom_table = mo.ui.table(_dom.to_pandas(), label="By domain")
        ver_table = mo.ui.table(_ver.to_pandas(), label="Version history")
    else:
        dom_table = mo.md("_No registry data_")
        ver_table = mo.md("_No registry data_")

    _tasks = registry.get("task_records", [])
    import polars as _pl
    task_table = (mo.ui.table(_pl.DataFrame(_tasks).to_pandas(), label="Task records")
                  if _tasks else mo.md("_No task records_"))

    panel2 = mo.vstack([
        mo.md("## 📊 Registry Analytics"),
        mo.hstack([p2_domain, p2_current], justify="start"),
        mo.md("### Domain Summary"),
        mo.hstack([dom_table, ver_table]),
        mo.md("### Skill Records"),
        skill_table,
        mo.md("### Task Records"),
        task_table,
    ])
    return (panel2,)


# ══════════════════════════════════════════════════════════════════════════════
# PANEL 3 — PIPELINE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

# Cell 11: Panel 3 widgets (CREATE)
@app.cell
def _p3_widgets(mo, sessions):
    if sessions:
        _labels = [
            f"{s['session_id'][:8]} | {s['status'].upper()} | "
            f"{s['total_duration_ms']:.0f}ms | {s['error_count']} err"
            for s in sessions
        ]
        p3_select = mo.ui.dropdown(
            options={lbl: i for i, lbl in enumerate(_labels)},
            value=0,
            label="Select session",
        )
    else:
        p3_select = mo.ui.dropdown(options={"(none)": 0}, value=0, label="Session")
    return (p3_select,)


# Cell 12: Panel 3 content (READ widgets)
@app.cell
def _p3_content(mo, pd, sessions, p3_select):
    def _mermaid(s: dict) -> str:
        lines = ["graph TD", "    START([START])"]
        prev  = "START"
        _colors = {
            "completed": "#96ceb4", "failed": "#ff6b35",
            "retried": "#fdcb6e",   "skipped": "#dfe6e9",
        }
        _icons = {"agent": "🤖", "subagent": "🔲", "team": "👥",
                  "python": "🐍", "bash": "🔧"}
        for e in s.get("entries", []):
            step   = e.get("step", 0)
            atype  = e.get("agent_type", "agent")
            skill  = e.get("fqsn_path", "").split("/")[-1]
            status = e.get("status", "")
            key    = f"s{step}_{e['entry_id'][:4]}"
            icon   = _icons.get(atype, "▪")
            color  = _colors.get(status, "#dfe6e9")
            lines.append(f'    {key}["{icon} {skill}<br/>{atype}·{status}"]')
            lines.append(f"    {prev} --> {key}")
            lines.append(f"    style {key} fill:{color},color:#000")
            prev = key
            for i, sub in enumerate(e.get("sub_entries", [])[:3]):
                sk  = f"sub{step}_{i}"
                ss  = sub.get("fqsn_path", "").split("/")[-1]
                sc  = _colors.get(sub.get("status",""), "#f5f5f5")
                lines.append(f'    {sk}(("{ss}"))')
                lines.append(f"    {key} -.-> {sk}")
                lines.append(f"    style {sk} fill:{sc},color:#000")
        lines.append("    END_NODE([END])")
        lines.append(f"    {prev} --> END_NODE")
        return "\n".join(lines)

    if sessions:
        _idx = p3_select.value if p3_select.value is not None else 0
        _s   = sessions[_idx]
        cards = mo.hstack([
            mo.stat("Session",  _s["session_id"][:8]),
            mo.stat("Status",   _s["status"].upper(),              bordered=True),
            mo.stat("Duration", f"{_s['total_duration_ms']:.0f}ms",bordered=True),
            mo.stat("Steps",    str(_s["step_count"]),             bordered=True),
            mo.stat("Errors",   str(_s["error_count"]),            bordered=True),
            mo.stat("Mode",     _s.get("operating_mode",""),       bordered=True),
        ], justify="start")

        diagram = mo.mermaid(_mermaid(_s))

        _rows = [{
            "step":        e.get("step"),
            "agent_type":  e.get("agent_type"),
            "skill":       e.get("fqsn_path","").split("/")[-1],
            "status":      e.get("status"),
            "duration_ms": f"{e.get('duration_ms',0):.0f}",
            "retry":       e.get("retry_count",0),
            "subs":        len(e.get("sub_entries",[])),
            "error":       (e.get("error","") or "")[:60],
        } for e in _s.get("entries",[])]
        detail = mo.ui.table(pd.DataFrame(_rows), label="Step entries")
    else:
        cards   = mo.md("_No sessions_")
        diagram = mo.md("_No data_")
        detail  = mo.md("_No entries_")

    panel3 = mo.vstack([
        mo.md("## 🔄 Pipeline Dashboard"),
        mo.md("_ACMS monitor console — watching tasks execute in real time_"),
        p3_select,
        cards,
        mo.md("### Execution Graph"),
        diagram,
        mo.md("### Step Detail"),
        detail,
    ])
    return (panel3,)


# ── Cell 13: assemble tabs ────────────────────────────────────────────────────
@app.cell
def _tabs(mo, panel1, panel2, panel3):
    tabs = mo.ui.tabs({
        "📋 Audit Trail": panel1,
        "📊 Registry":    panel2,
        "🔄 Pipeline":    panel3,
    })
    return (tabs,)


# ── Cell 14: render ───────────────────────────────────────────────────────────
@app.cell
def _render(mo, header, kpis, session_count, mock_seed, refresh_btn, tabs):
    mo.vstack([
        header,
        mo.hstack([session_count, mock_seed, refresh_btn], justify="start"),
        kpis,
        tabs,
    ])


if __name__ == "__main__":
    app.run()
