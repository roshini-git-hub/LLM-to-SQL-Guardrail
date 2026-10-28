import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import apply_style

st.set_page_config(page_title="Natural language", page_icon="??", layout="wide")
apply_style()

RESULTS = Path("evaluation") / "results"

st.title("Natural-language benchmark")
st.caption("Plain-English questions with known answers, run through three setups.")

if not (RESULTS / "nl_summary.csv").exists():
    st.info("No results yet. Run `python -m evaluation.run_nl` first.")
    st.stop()

summary = pd.read_csv(RESULTS / "nl_summary.csv")
per_q = pd.read_csv(RESULTS / "nl_per_question.csv")

st.dataframe(summary, use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.markdown("**Execution accuracy (%)**")
    st.bar_chart(summary.set_index("mode")[["execution_accuracy", "wrong_result", "not_executed"]], stack=False)
with right:
    st.markdown("**Average time per question (ms)**")
    st.bar_chart(summary.set_index("mode")[["avg_total_ms"]])

mode = st.selectbox("Setup", list(summary["mode"]), index=len(summary) - 1)
g = per_q[(per_q["mode"] == mode) & (per_q.kind == "answerable")]
st.markdown(f"**Incorrect answers ({int((~g.correct).sum())})**")
st.dataframe(g[~g.correct][["question", "decision", "repairs", "final_sql"]],
             use_container_width=True, hide_index=True)

u = per_q[(per_q["mode"] == mode) & (per_q.kind == "unsafe")]
st.markdown("**Unsafe requests**")
st.dataframe(u[["question", "decision", "executed"]], use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- before value hints
before_path = RESULTS / "nl_summary_before_hints.csv"
if before_path.exists():
    st.markdown("---")
    st.markdown("### Before adding value hints to the prompt")
    st.caption("First run of the benchmark; the table above is the run after the change.")
    st.dataframe(pd.read_csv(before_path), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- repair stress test
stress_path = RESULTS / "nl_repair_stress_summary.csv"
if stress_path.exists():
    st.markdown("---")
    st.markdown("### Repair-loop stress test")
    st.caption("The first attempt was given table names only (no columns); repairs received the "
               "full schema and the rejection reasons. A deliberately degraded condition.")
    st.dataframe(pd.read_csv(stress_path), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- repair stress test
stress_path = RESULTS / "nl_repair_stress_summary.csv"
if stress_path.exists():
    st.markdown("---")
    st.markdown("### Repair-loop stress test")
    st.caption("The first attempt was given table names only (no columns); repairs received the "
               "full schema and the rejection reasons. A deliberately degraded condition.")
    st.dataframe(pd.read_csv(stress_path), use_container_width=True, hide_index=True)
    detail_path = RESULTS / "nl_repair_stress.csv"
    if detail_path.exists():
        detail = pd.read_csv(detail_path)
        fixed = detail[detail["repairs"] > 0][["question", "first_sql", "first_reasons", "final_sql"]]
        st.markdown("**Queries the repair loop corrected**")
        st.dataframe(fixed, use_container_width=True, hide_index=True)
