import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import apply_style

st.set_page_config(page_title="Results", page_icon="??", layout="wide")
apply_style()

R = Path("evaluation") / "results"

st.title("?? Results")
st.write(
    "How well does the guardrail work? We tested it against simpler kinds of protection on "
    "lists of queries that were labeled in advance as good, harmful or heavy."
)

SETS = {
    "Final test (written last, rules frozen, run once)": "final_summary_frozen.csv",
    "Held-out test (first run, before tuning)": "holdout_before_fix.csv",
    "Development test (used while building)": "summary.csv",
}
available = {name: f for name, f in SETS.items() if (R / f).exists()}
if not available:
    st.info("No results yet. Run `python -m evaluation.run_final` first.")
    st.stop()

name = st.selectbox("Which test?", list(available))
df = pd.read_csv(R / available[name])

APPROACH = {
    "no_guardrail": "No protection",
    "regex_blacklist": "Keyword filter",
    "db_role_only": "Database permissions only",
    "ast_only": "Rules only (no cost check)",
    "full_guardrail": "Full guardrail (this project)",
}
BAD = "Bad queries stopped (%)"
GOOD = "Good queries wrongly blocked (%)"
TIME = "Average time (ms)"

view = pd.DataFrame({
    "Approach": df["baseline"].map(APPROACH),
    BAD: df["detection_rate"],
    GOOD: df["false_positive_rate"],
    TIME: df["avg_latency_ms"],
})

full = df[df["baseline"] == "full_guardrail"].iloc[0]
role = df[df["baseline"] == "db_role_only"].iloc[0]

st.success(
    f"The full guardrail stopped **{full['detection_rate']}%** of harmful or heavy queries, "
    f"while wrongly blocking **{full['false_positive_rate']}%** of good ones."
)
st.info(
    f"Database permissions alone stopped **{role['detection_rate']}%**, and averaged "
    f"**{role['avg_latency_ms']} ms** per query because heavy queries run until they time out. "
    f"The guardrail's checks averaged **{full['avg_latency_ms']} ms**."
)

st.markdown("#### The five approaches side by side")
st.dataframe(view, use_container_width=True, hide_index=True)

chart = view.set_index("Approach")[[BAD, GOOD]]
try:
    st.bar_chart(chart, stack=False)
except TypeError:
    st.bar_chart(chart)

with st.expander("How to read this"):
    st.markdown(
        f"- **{BAD}**: out of all the harmful or heavy queries, how many were caught. Higher is better.\n"
        f"- **{GOOD}**: out of all the harmless queries, how many were stopped by mistake. Lower is better.\n"
        f"- **{TIME}**: extra time per query. For the guardrail this covers the checks only, not running the query.\n"
        "- **No protection** is the starting point: it stops nothing.\n"
        "- **Keyword filter** looks for words like DROP or DELETE.\n"
        "- **Database permissions only** uses a read-only account with a time limit.\n"
        "- **Rules only** checks the structure of the SQL but not how heavy it is."
    )

with st.expander("Why is it not perfect? (about the final test)"):
    st.markdown(
        "On the final test, one runaway query was missed, and some harmless queries were blocked "
        "because the functions they used were not on the approved list. Both were fixed afterwards, "
        "but those fixes are not counted in the numbers above, so the numbers stay honest. "
        "The development and held-out tests were used while building the rules, so they look "
        "better than the final test and should be read with that in mind."
    )

st.caption("The test lists are small and written by hand, so treat the percentages as a comparison "
           "between approaches, not as a promise for every real database.")
