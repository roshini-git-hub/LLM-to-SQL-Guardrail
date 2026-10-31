import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from common import apply_style, call_api, explain_reason, show_response

st.set_page_config(page_title="Try it", page_icon="\U0001F9EA", layout="wide")
apply_style()

st.title("\U0001F9EA Try it")
st.write("Ask a question in plain English, or paste SQL directly. Click an example to fill the box.")

ASK_EXAMPLES = [
    ("\u2705 Orders per status", "How many orders are there for each status?"),
    ("\u2705 Average price", "What is the average product price in each category?"),
    ("\u2705 Top customers", "Which 3 customers have spent the most in total? Show their names and total spent."),
    ("\u26d4 Private data", "Show every employee salary"),
]

SQL_EXAMPLES = [
    ("\u2705 Normal query", "SELECT name, city FROM customers LIMIT 10"),
    ("\u2705 Uses CASE", "SELECT name, CASE WHEN price > 500 THEN 'high' ELSE 'low' END AS tier FROM products LIMIT 20"),
    ("\u26d4 Sneaky second command", "SELECT name FROM customers; DROP TABLE orders"),
    ("\u26d4 Private table", "SELECT salary FROM employees"),
    ("\u26d4 Private columns via *", "SELECT * FROM customers LIMIT 5"),
    ("\u26d4 Heavy query", "SELECT c.name, oi.quantity FROM customers c, order_items oi LIMIT 10"),
]

st.session_state.setdefault("ask_text", "")
st.session_state.setdefault("sql_text", "SELECT name, city FROM customers LIMIT 10")


def set_value(key, value):
    st.session_state[key] = value


tab_ask, tab_sql = st.tabs(["\U0001F4AC Ask in plain English", "\U0001F4DD Paste SQL"])

with tab_ask:
    st.markdown("**Examples**")
    cols = st.columns(len(ASK_EXAMPLES))
    for col, (label, text) in zip(cols, ASK_EXAMPLES):
        col.button(label, key=f"ask_{label}", on_click=set_value, args=("ask_text", text),
                   width="stretch")

    question = st.text_input("Your question", key="ask_text",
                             placeholder="e.g. How many orders are there for each status?")
    if st.button("Check and run", type="primary", key="run_ask"):
        if not question.strip():
            st.warning("Type a question first, or click an example.")
        else:
            with st.spinner("The assistant is writing SQL and the guardrail is checking it..."):
                data = call_api("/ask", {"question": question})
            if data:
                st.markdown("---")
                show_response(data["final"])
                if data["repairs_used"]:
                    n = data["repairs_used"]
                    st.info(
                        f"The first query had a fixable problem, so the guardrail sent it back with "
                        f"the reason and the assistant tried again ({n} time{'s' if n > 1 else ''})."
                    )
                    with st.expander("See every attempt"):
                        for i, attempt in enumerate(data["attempts"], 1):
                            st.markdown(f"**Attempt {i}**")
                            st.code(attempt["sql"], language="sql")
                            for r in attempt["reasons"]:
                                st.markdown(f"- {explain_reason(r)}")

with tab_sql:
    st.markdown("**Examples**")
    cols = st.columns(3)
    for i, (label, text) in enumerate(SQL_EXAMPLES):
        cols[i % 3].button(label, key=f"sql_{label}", on_click=set_value, args=("sql_text", text),
                           width="stretch")

    sql = st.text_area("SQL command", key="sql_text", height=130)
    if st.button("Check and run", type="primary", key="run_sql"):
        if not sql.strip():
            st.warning("Paste a SQL command first, or click an example.")
        else:
            with st.spinner("Checking..."):
                data = call_api("/query", {"sql": sql})
            if data:
                st.markdown("---")
                show_response(data)
