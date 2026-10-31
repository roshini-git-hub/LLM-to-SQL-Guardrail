import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from common import apply_style, load_log, show_verdict

st.set_page_config(page_title="History", page_icon="\U0001F4DC", layout="wide")
apply_style()

st.title("\U0001F4DC History")
st.write("Every request the guardrail has checked, newest first.")

df = load_log()
if df.empty:
    st.info("Nothing has been checked yet. Go to **Try it** and run something.")
    st.stop()

df = df.sort_values("time", ascending=False).reset_index(drop=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Checked", len(df))
m2.metric("Safe to run", int((df["decision"] == "ALLOW").sum()))
m3.metric("Needed a check", int((df["decision"] == "REVIEW").sum()))
m4.metric("Blocked", int((df["decision"] == "BLOCK").sum()))

LABELS = {"ALLOW": "\u2705 Safe", "REVIEW": "\u26a0\ufe0f Review", "BLOCK": "\u26d4 Blocked"}

choice = st.radio("Show", ["All", "Safe", "Review", "Blocked"], horizontal=True)
wanted = {"All": ["ALLOW", "REVIEW", "BLOCK"], "Safe": ["ALLOW"],
          "Review": ["REVIEW"], "Blocked": ["BLOCK"]}[choice]
df = df[df["decision"].isin(wanted)].reset_index(drop=True)

if df.empty:
    st.info("Nothing in this group yet.")
    st.stop()


def request_text(row):
    q = row.get("question")
    text = q if isinstance(q, str) and q else row.get("sql", "")
    return text[:90]


view = pd.DataFrame({
    "When": df["time"].dt.strftime("%d %b, %H:%M:%S"),
    "Request": df.apply(request_text, axis=1),
    "Verdict": df["decision"].map(LABELS),
    "Risk (0-100)": df["score"],
})
st.dataframe(view, use_container_width=True, hide_index=True)

st.markdown("#### Look at one request")
idx = st.selectbox(
    "Pick a request",
    list(range(len(df))),
    format_func=lambda i: f'{view.loc[i, "When"]}  |  {view.loc[i, "Verdict"]}  |  {view.loc[i, "Request"]}',
)
rec = df.iloc[idx].to_dict()
show_verdict(rec)
st.markdown("**The SQL that was checked**")
st.code(rec.get("sql", ""), language="sql")
