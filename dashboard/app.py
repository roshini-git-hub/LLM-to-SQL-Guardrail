import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from common import apply_style, call_api, load_log, show_response, COLORS

st.set_page_config(page_title="SQL Guardrail", page_icon="???", layout="wide")
apply_style()

st.sidebar.title("??? SQL Guardrail")
page = st.sidebar.radio("Page", ["Ask a question", "Analyze SQL", "Audit log"])
st.sidebar.markdown(
    '<p class="small">Risk-aware LLM-to-SQL guardrail: AST validation, '
    'cost estimation and risk-based approval.</p>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- Ask
if page == "Ask a question":
    st.title("Ask a question")
    st.caption("Natural language ? local LLM ? guardrail ? result")

    question = st.text_input(
        "Your question",
        placeholder="e.g. How many orders are there for each status?",
    )
    if st.button("Run", type="primary") and question.strip():
        with st.spinner("Generating SQL and checking it..."):
            data = call_api("/ask", {"question": question})
        if data:
            show_response(data["final"])
            if data["repairs_used"]:
                st.info(f'The query was repaired {data["repairs_used"]} time(s).')
                with st.expander("Show every attempt"):
                    for i, attempt in enumerate(data["attempts"], 1):
                        st.markdown(f"**Attempt {i}: {attempt['decision']}**")
                        st.code(attempt["sql"], language="sql")
                        for reason in attempt["reasons"]:
                            st.markdown(f"- {reason}")

# ------------------------------------------------------------ Analyze
elif page == "Analyze SQL":
    st.title("Analyze SQL")
    st.caption("Paste any SQL; the guardrail validates, costs and scores it.")

    sql = st.text_area(
        "SQL",
        height=150,
        value="SELECT name, city FROM customers LIMIT 10",
    )
    if st.button("Analyze", type="primary") and sql.strip():
        with st.spinner("Analyzing..."):
            data = call_api("/query", {"sql": sql})
        if data:
            show_response(data)

# ---------------------------------------------------------- Audit log
else:
    st.title("Audit log")
    df = load_log()
    if df.empty:
        st.info("No requests logged yet. Run a query first.")
    else:
        total = len(df)
        allowed = int((df["decision"] == "ALLOW").sum())
        review = int((df["decision"] == "REVIEW").sum())
        blocked = int((df["decision"] == "BLOCK").sum())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total requests", total)
        m2.metric("Allowed", allowed)
        m3.metric("Review", review)
        m4.metric("Blocked", blocked)

        left, right = st.columns(2)
        with left:
            st.markdown("**Decisions**")
            st.bar_chart(df["decision"].value_counts())
        with right:
            st.markdown("**Risk score over time**")
            st.line_chart(df.set_index("time")["score"])

        choice = st.multiselect(
            "Filter by decision",
            ["ALLOW", "REVIEW", "BLOCK"],
            default=["ALLOW", "REVIEW", "BLOCK"],
        )
        shown = df[df["decision"].isin(choice)].sort_values("time", ascending=False)
        shown = shown[["time", "decision", "score", "question", "sql", "repairs_used", "elapsed_ms"]]
        st.dataframe(shown, use_container_width=True, hide_index=True)
