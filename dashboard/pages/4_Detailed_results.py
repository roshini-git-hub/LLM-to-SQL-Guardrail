import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import apply_style

st.set_page_config(page_title="Evaluation", page_icon="\U0001F4CA", layout="wide")
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
st.dataframe(summary, width="stretch", hide_index=True)

left, right = st.columns(2)
with left:
    st.markdown("**Detection vs false positives (%)**")
    st.bar_chart(summary.set_index("baseline")[["detection_rate", "false_positive_rate"]], stack=False)
with right:
    st.markdown("**Average latency (ms)**")
    st.bar_chart(summary.set_index("baseline")[["avg_latency_ms"]])

st.markdown("### Mistakes by baseline")
chosen = st.selectbox("Baseline", list(summary.baseline), index=len(summary) - 1)
g = per_query[per_query.baseline == chosen]
missed = g[(g.label != "safe") & (~g.flagged)]
wrong = g[(g.label == "safe") & (g.flagged)]

st.markdown(f"**Missed unsafe queries ({len(missed)})**")
st.dataframe(missed[["label", "sql"]], width="stretch", hide_index=True)
st.markdown(f"**False positives ({len(wrong)})**")
st.dataframe(wrong[["sql"]], width="stretch", hide_index=True)

# ---------------------------------------------------------------- held-out set
holdout_path = RESULTS / "holdout_summary.csv"
if holdout_path.exists():
    st.markdown("---")
    st.markdown("### Held-out test set")
    st.caption("Queries written after the rules were designed, including evasion attempts.")
    holdout = pd.read_csv(holdout_path)
    st.dataframe(holdout, width="stretch", hide_index=True)
    st.bar_chart(
        holdout.set_index("baseline")[["detection_rate", "false_positive_rate"]],
        stack=False,
    )

# ---------------------------------------------------------------- held-out set
holdout_path = RESULTS / "holdout_summary.csv"
before_path = RESULTS / "holdout_before_fix.csv"
if holdout_path.exists():
    st.markdown("---")
    st.markdown("### Held-out test set")
    st.caption("Queries written after the rules were designed, including evasion attempts.")

    if before_path.exists():
        st.markdown("**Before tuning** (first run on unseen queries)")
        st.dataframe(pd.read_csv(before_path), width="stretch", hide_index=True)
        st.markdown("**After tuning** (the held-out set has now been used for fixes)")

    holdout = pd.read_csv(holdout_path)
    st.dataframe(holdout, width="stretch", hide_index=True)
    st.bar_chart(
        holdout.set_index("baseline")[["detection_rate", "false_positive_rate"]],
        stack=False,
    )

# ---------------------------------------------------------------- final set
final_path = RESULTS / "final_summary_frozen.csv"
if final_path.exists():
    st.markdown("---")
    st.markdown("### Final test set (run once, rules frozen)")
    st.caption("Queries written last, using attack styles not tested before. No tuning followed this run.")
    final = pd.read_csv(final_path)
    st.dataframe(final, width="stretch", hide_index=True)
    st.bar_chart(
        final.set_index("baseline")[["detection_rate", "false_positive_rate"]],
        stack=False,
    )


# ---------------------------------------------------------------- post-fix rerun
postfix_path = RESULTS / "final_summary_postfix.csv"
if postfix_path.exists():
    st.markdown("### After post-evaluation fixes (not independent)")
    st.caption("Same queries re-run after adding allowlist entries and a recursive-query rule. "
               "These changes were made after seeing the results above, so this shows the fix works, not new generalization.")
    st.dataframe(pd.read_csv(postfix_path), width="stretch", hide_index=True)


# ---------------------------------------------------------------- post-fix rerun
postfix_path = RESULTS / "final_summary_postfix.csv"
if postfix_path.exists():
    st.markdown("### After post-evaluation fixes (not independent)")
    st.caption("Same queries re-run after adding allowlist entries and rules for star expansion, "
               "row locking and recursive queries. These changes were made after seeing the results "
               "above, so this shows the fixes work, not new generalization.")
    st.dataframe(pd.read_csv(postfix_path), width="stretch", hide_index=True)
