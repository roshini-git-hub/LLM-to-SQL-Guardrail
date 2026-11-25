import json
import re
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API = "http://127.0.0.1:8000"
LOG_PATH = Path("data") / "audit.jsonl"

COLORS = {"ALLOW": "#2EA043", "REVIEW": "#D29922", "BLOCK": "#F85149"}

VERDICTS = {
    "ALLOW": ("Safe to run", "\u2705", "No problems were found, so the query was allowed to run."),
    "REVIEW": ("Needs a human check", "\u26a0\ufe0f", "Something looked risky, so the query was held back instead of running."),
    "BLOCK": ("Blocked", "\u26d4", "The query was stopped before it could touch the database."),
}

FRIENDLY = {
    "syntax_error": "The SQL is not valid, so it cannot be understood.",
    "multiple_statements": "More than one command was sent at once. Attackers use this to sneak in a second, harmful command.",
    "forbidden_statement": "Only reading data is allowed. This tries to change or manage the database.",
    "hidden_write": "A command that changes data is hidden inside the query.",
    "row_locking": "This would lock rows, which is not a read-only action.",
    "select_into": "This would create a new table, which is not a read-only action.",
    "blocked_table": "This asks for a table that is off-limits because it holds private data",
    "unknown_table": "This uses a table that is not part of the allowed data",
    "sensitive_column": "This asks for a private column",
    "star_on_restricted_table": "Asking for 'all columns' would also reveal private columns of a table.",
    "select_star": "Asking for 'all columns' returns more than is usually needed.",
    "forbidden_function": "This uses a function that is not on the approved list",
    "missing_limit": "There is no limit on how many rows can come back.",
    "table_not_found": "This uses a table that does not exist",
    "column_not_found": "This uses a column that does not exist",
    "sensitive_access": "This reads personal or sensitive data, so a person should approve it",
    "recursive_cte": "This is a self-repeating query that could run without end.",
}

WARN_RULES = {"select_star", "missing_limit", "sensitive_access"}
DETAIL_RULES = {"blocked_table", "unknown_table", "sensitive_column", "forbidden_function",
                "table_not_found", "column_not_found", "sensitive_access"}

CSS = """
<style>
html, body, [class*="css"] {font-size: 17px;}
.block-container {padding-top: 2rem; max-width: 1100px;}
.verdict {border: 2px solid; border-radius: 14px; padding: 18px 22px;
          margin: 8px 0 14px 0; background: #161B22;}
.vtitle {font-size: 1.7rem; font-weight: 700;}
.vtext {color: #C9D1D9; margin-top: 4px;}
.reason {background: #161B22; border: 1px solid #30363D; border-left: 4px solid #7C5CFF;
         border-radius: 8px; padding: 10px 14px; margin: 6px 0; color: #E6EDF3;}
.step {background: #161B22; border: 1px solid #30363D; border-radius: 12px;
       padding: 12px 14px; min-height: 120px;}
.step .t {font-weight: 700; margin-bottom: 2px;}
.step .d {color: #8B949E; font-size: 0.85rem; margin-bottom: 8px;}
.card {background: #161B22; border: 1px solid #30363D; border-radius: 14px;
       padding: 16px 18px; min-height: 150px;}
.card .n {color: #7C5CFF; font-weight: 800; font-size: 1.4rem;}
.card .t {font-weight: 700; font-size: 1.1rem;}
.card .d {color: #C9D1D9; margin-top: 4px;}
.hint {color: #8B949E; font-size: 0.9rem;}
[data-testid="stMetric"] {background: #161B22; border: 1px solid #30363D;
         border-radius: 12px; padding: 14px 18px;}
</style>
"""


def apply_style():
    st.markdown(CSS, unsafe_allow_html=True)


def get_roles():
    """Database roles the guardrail may act as (empty list if the service is down)."""
    try:
        return requests.get(API + "/roles", timeout=5).json().get("roles", [])
    except Exception:
        return []


def call_api(path: str, payload: dict):
    try:
        r = requests.post(API + path, json=payload, timeout=300)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the guardrail service. Start it in a separate window with: "
                 "uvicorn app.main:app --reload")
    except Exception as e:
        st.error(f"Something went wrong: {e}")
    return None


def explain_reason(text: str) -> str:
    """Turn a technical reason into plain English."""
    m = re.match(r"\[(\w+)\]\s*(.*)", text)
    if m:
        rule, detail = m.group(1), m.group(2)
        base = FRIENDLY.get(rule, detail)
        if rule in DETAIL_RULES:
            q = re.search(r"'([^']+)'", detail)
            if q:
                return f"{base} ({q.group(1)})."
            return base + "."
        return base
    if text.startswith("Planner rejected"):
        return "The database could not run this query, for example because it uses a column that does not exist."
    if text.startswith("Possible cartesian"):
        return ("Two tables are combined without saying how they relate, so every row is paired with "
                "every other row. The result grows enormously.")
    m = re.match(r"Large sequential scan on '([^']+)' \(~(\d+) rows\)", text)
    if m:
        return f"The database would have to read every row of '{m.group(1)}' (about {int(m.group(2)):,} rows)."
    m = re.match(r"Plan step estimated at ~(\d+) rows", text)
    if m:
        return f"One step of the plan would produce about {int(m.group(1)):,} rows, which is extremely heavy."
    m = re.match(r"(Very high|High|Moderate) estimated cost \(([\d,]+)\)", text)
    if m:
        return f"{m.group(1)} estimated workload for the database (cost score {m.group(2)})."
    if text.startswith("Execution failed"):
        return "The database stopped the query while it was running, for example because it took too long."
    if "cannot be answered" in text:
        return "The assistant could not answer this using only the data it is allowed to see."
    return text


def show_verdict(rec: dict):
    decision = rec.get("decision", "BLOCK")
    label, icon, text = VERDICTS.get(decision, ("Unknown", "\u2754", ""))
    color = COLORS.get(decision, "#8B949E")
    st.markdown(
        f'<div class="verdict" style="border-color:{color}">'
        f'<div class="vtitle" style="color:{color}">{icon} {label}</div>'
        f'<div class="vtext">{text}</div></div>',
        unsafe_allow_html=True,
    )
    score = int(rec.get("score", 0) or 0)
    st.progress(min(score, 100) / 100)
    st.caption(f"Risk score: {score} out of 100  (under 35 = safe, 35 to 69 = needs review, 70 and above = blocked)")

    reasons = rec.get("reasons") or []
    if reasons:
        st.markdown("**Why?**")
        for r in reasons:
            st.markdown(f'<div class="reason">{explain_reason(r)}</div>', unsafe_allow_html=True)
    elif decision == "ALLOW":
        st.markdown("Nothing suspicious was found.")


def _stages(resp: dict):
    reasons = resp.get("reasons", []) or []
    if any("cannot be answered" in r for r in reasons):
        return None
    hits = []
    for r in reasons:
        m = re.match(r"\[(\w+)\]", r)
        if m and m.group(1) not in WARN_RULES:
            hits.append(m.group(1))
    planner_failed = any(r.startswith("Planner rejected") for r in reasons)
    decision = resp.get("decision")

    rules = "fail" if hits else "ok"
    if hits:
        cost = "skip"
    elif planner_failed:
        cost = "fail"
    elif decision != "ALLOW":
        cost = "warn"
    else:
        cost = "ok"
    run = "ok" if decision == "ALLOW" else "skip"
    return rules, cost, decision, run


def show_steps(resp: dict):
    stages = _stages(resp)
    if stages is None:
        return
    rules, cost, decision, run = stages
    icons = {"ok": "\u2705", "fail": "\u274c", "warn": "\u26a0\ufe0f", "skip": "\u23ed\ufe0f"}
    words = {
        "rules": {"ok": "Passed", "fail": "Failed"},
        "cost": {"ok": "Light enough", "fail": "Could not be planned",
                 "warn": "Looks heavy", "skip": "Skipped"},
        "run": {"ok": "Ran with safe limits", "skip": "Did not run"},
    }
    v_label, v_icon, _ = VERDICTS.get(decision, ("Unknown", "\u2754", ""))
    items = [
        ("1. Rules check", "Is this query even allowed?", f'{icons[rules]} {words["rules"][rules]}'),
        ("2. Cost check", "How heavy would it be?", f'{icons[cost]} {words["cost"][cost]}'),
        ("3. Decision", "Allow, review or block?", f"{v_icon} {v_label}"),
        ("4. Run safely", "Read-only, time limit, row limit", f'{icons[run]} {words["run"][run]}'),
    ]
    st.markdown("**What the guardrail did**")
    cols = st.columns(4)
    for col, (title, desc, status) in zip(cols, items):
        col.markdown(
            f'<div class="step"><div class="t">{title}</div>'
            f'<div class="d">{desc}</div><div>{status}</div></div>',
            unsafe_allow_html=True,
        )


def show_response(resp: dict, with_steps: bool = True):
    show_verdict(resp)
    if with_steps:
        show_steps(resp)

    sql = resp.get("sql")
    if sql and sql != "CANNOT_ANSWER":
        st.markdown("**The SQL that was checked**")
        st.code(sql, language="sql")

    if resp.get("rows"):
        df = pd.DataFrame(resp["rows"], columns=resp["columns"])
        took = resp.get("elapsed_ms")
        suffix = f", ran in {took:.0f} ms" if took is not None else ""
        st.markdown(f"**Result** ({len(df)} rows{suffix})")
        st.dataframe(df, width="stretch")

    with st.expander("Technical details"):
        st.write("Raw reasons from the guardrail:")
        st.write(resp.get("reasons", []))


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    records = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame(records)
    if not df.empty:
        df["time"] = pd.to_datetime(df["ts"], unit="s")
    return df
