import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from common import apply_style, load_log

st.set_page_config(page_title="SQL Guardrail", page_icon="\U0001F6E1", layout="wide")
apply_style()

st.title("\U0001F6E1\ufe0f SQL Guardrail")
st.markdown("### A security guard for your database")
st.write(
    "When you ask a question in plain English, an AI writes a database command (called SQL) "
    "to answer it. That command can be **wrong**, can try to reach **private data**, or can be "
    "so **heavy** that it slows the whole database down. This system checks every command "
    "**before** it runs."
)

st.markdown("#### How it works")
steps = [
    ("1", "Ask", "You type a question in plain English, or paste a SQL command."),
    ("2", "Check the rules", "Is the command allowed? No deleting, no private data, one command at a time."),
    ("3", "Check the weight", "The database estimates how much work the command would be, without running it."),
    ("4", "Decide", "Run it safely, hold it for a human check, or block it."),
]
cols = st.columns(4)
for col, (n, t, d) in zip(cols, steps):
    col.markdown(
        f'<div class="card"><div class="n">{n}</div><div class="t">{t}</div>'
        f'<div class="d">{d}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("#### The three possible answers")
c1, c2, c3 = st.columns(3)
c1.markdown(
    '<div class="verdict" style="border-color:#2EA043"><div class="vtitle" style="color:#2EA043">'
    '\u2705 Safe to run</div><div class="vtext">No problems found. The query runs, with a time limit '
    'and a row limit.</div></div>', unsafe_allow_html=True)
c2.markdown(
    '<div class="verdict" style="border-color:#D29922"><div class="vtitle" style="color:#D29922">'
    '\u26a0\ufe0f Needs a human check</div><div class="vtext">Something looked risky. It is held back '
    'instead of running.</div></div>', unsafe_allow_html=True)
c3.markdown(
    '<div class="verdict" style="border-color:#F85149"><div class="vtitle" style="color:#F85149">'
    '\u26d4 Blocked</div><div class="vtext">The query is stopped before it can touch the '
    'database.</div></div>', unsafe_allow_html=True)

log = load_log()
if not log.empty:
    st.markdown("#### So far")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Requests checked", len(log))
    m2.metric("Safe to run", int((log["decision"] == "ALLOW").sum()))
    m3.metric("Needed a check", int((log["decision"] == "REVIEW").sum()))
    m4.metric("Blocked", int((log["decision"] == "BLOCK").sum()))

st.markdown("#### Where to go next")
st.markdown(
    "- **Try it** (left menu): ask a question or paste SQL and watch the guardrail decide.\n"
    "- **History**: everything that has been checked, and why.\n"
    "- **Results**: how well it works compared with simpler protection.\n"
    "- **Detailed results** and **Question tests**: the full tables behind the results."
)

with st.expander("What do these words mean?"):
    st.markdown(
        "- **SQL**: the language used to ask a database for data.\n"
        "- **Query**: one SQL command.\n"
        "- **Query plan**: the database's own estimate of how it would run a query and how much work it is.\n"
        "- **Risk score**: a number from 0 to 100 combining everything the guardrail found.\n"
        "- **Read-only**: the system can look at data but cannot change or delete it.\n"
        "- **Repair**: when a mistake can be fixed safely, the AI is asked to try again with the reason. "
        "Security problems are never sent back, so the AI cannot probe the rules."
    )
