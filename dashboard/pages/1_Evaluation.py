import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import apply_style

st.set_page_config(page_title="Evaluation", page_icon="??", layout="wide")
apply_style()

RESULTS = Path("evaluation") / "results"

st.title("Evaluation")
st.caption("Baseline comparison on a labeled set of safe, malicious and expensive queries.")

summary_path = RESULTS / "summary.json"
if not summary_path.exists():
    st.info("No results yet. Run `python -m evaluation.run_eval` first.")
    st.stop()

summary = pd.DataFrame(json.loads(summary_path.read_text(encoding="utf-8")))
per_query = pd.read_csv(RESULTS / "per_query.csv")

full = summary[summary.baseline == "full_guardrail"].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Detection rate (full)", f'{full.detection_rate}%')
c2.metric("False positives (full)", f'{full.false_positive_rate}%')
c3.metric("Precision (full)", f'{full.precision}%')
c4.metric("Avg latency (full)", f'{full.avg_latency_ms} ms')

st.markdown("### Summary table")
st.dataframe(summary, use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.markdown("**Detection vs false positives (%)**")
    st.bar_chart(summary.set_index("baseline")[["detection_rate", "false_positive_rate"]])
with right:
    st.markdown("**Average latency (ms)**")
    st.bar_chart(summary.set_index("baseline")[["avg_latency_ms"]])

st.markdown("### Mistakes by baseline")
chosen = st.selectbox("Baseline", list(summary.baseline), index=len(summary) - 1)
g = per_query[per_query.baseline == chosen]
missed = g[(g.label != "safe") & (~g.flagged)]
wrong = g[(g.label == "safe") & (g.flagged)]

st.markdown(f"**Missed unsafe queries ({len(missed)})**")
st.dataframe(missed[["label", "sql"]], use_container_width=True, hide_index=True)
st.markdown(f"**False positives ({len(wrong)})**")
st.dataframe(wrong[["sql"]], use_container_width=True, hide_index=True)
