import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import apply_style

st.set_page_config(page_title="Small model benchmark", page_icon="\U0001F4CA", layout="wide")
apply_style()

RESULTS = Path("evaluation") / "results"
LABELS = {
    "small_alone": "1. Small model alone",
    "small_guardrail_no_repair": "2. + guardrail (no repair)",
    "small_plus_guardrail": "3. + guardrail + repair",
    "large_alone": "4. Larger model alone",
}

st.title("What the guardrail adds to a small model")
st.caption("The same questions, the same small local model, with and without the guardrail, "
           "on two unrelated databases. Nothing in the code names a table or column.")

files = sorted(RESULTS.glob("bench_*_summary.csv"))
if not files:
    st.info("No results yet. Run `python -m evaluation.run_nl` and "
            "`python -m evaluation.run_nl --db college_db` first.")
    st.stop()

summary = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
summary["setup_label"] = summary["setup"].map(LABELS)

db = st.selectbox("Database", sorted(summary["db"].unique()))
s = summary[summary.db == db].set_index("setup_label")

cols = st.columns(len(s))
for col, (label, row) in zip(cols, s.iterrows()):
    col.metric(label, f"{row.correct_pct:.0f}% correct",
               f"{int(row.violations_let_through)} of {int(row.unsafe_questions)} unsafe requests let through",
               delta_color="off" if row.violations_let_through == 0 else "inverse")

left, right = st.columns(2)
with left:
    st.markdown("**Answerable questions (%)**")
    chart = s[["execution_success_pct", "correct_pct"]].rename(
        columns={"execution_success_pct": "Query ran", "correct_pct": "Correct answer"})
    st.bar_chart(chart, stack=False, color=["#7C5CFF", "#2EA043"])
with right:
    st.markdown("**Unsafe requests that got through (count)**")
    st.bar_chart(s[["violations_let_through"]].rename(
        columns={"violations_let_through": "Violations let through"}), color="#F85149")

st.dataframe(s.reset_index()[["setup_label", "model", "execution_success_pct", "correct_pct",
                              "violations_let_through", "avg_repairs", "avg_latency_ms"]],
             width="stretch", hide_index=True)

per_q = RESULTS / f"bench_{db}_per_question.csv"
if per_q.exists():
    with st.expander("Every question and the SQL each setup produced"):
        d = pd.read_csv(per_q)
        d["setup"] = d["setup"].map(LABELS)
        st.dataframe(d[["kind", "question", "setup", "executed", "correct", "violation",
                        "repairs", "final_sql"]], width="stretch", hide_index=True)
