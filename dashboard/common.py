import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API = "http://127.0.0.1:8000"
LOG_PATH = Path("data") / "audit.jsonl"

COLORS = {"ALLOW": "#2EA043", "REVIEW": "#D29922", "BLOCK": "#F85149"}

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.badge {display:inline-block; padding:6px 18px; border-radius:999px;
        font-weight:700; letter-spacing:1px; color:#fff; font-size:1.05rem;}
.reason {background:#161B22; border:1px solid #30363D; border-left:4px solid #7C5CFF;
         border-radius:8px; padding:8px 14px; margin:6px 0; color:#E6EDF3;}
.small {color:#8B949E; font-size:0.9rem;}
[data-testid="stMetric"] {background:#161B22; border:1px solid #30363D;
         border-radius:12px; padding:14px 18px;}
</style>
"""


def apply_style():
    st.markdown(CSS, unsafe_allow_html=True)


def call_api(path: str, payload: dict):
    try:
        r = requests.post(API + path, json=payload, timeout=300)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the API. Is `uvicorn app.main:app --reload` running?")
    except Exception as e:
        st.error(f"Request failed: {e}")
    return None


def show_response(resp: dict):
    decision = resp["decision"]
    color = COLORS.get(decision, "#8B949E")

    c1, c2, c3 = st.columns([1, 1, 2])
    c1.markdown(
        f'<span class="badge" style="background:{color}">{decision}</span>',
        unsafe_allow_html=True,
    )
    c2.metric("Risk score", f'{resp["score"]} / 100')
    if resp.get("elapsed_ms") is not None:
        c3.metric("Execution time", f'{resp["elapsed_ms"]:.1f} ms')

    st.code(resp["sql"], language="sql")

    if resp["reasons"]:
        st.markdown("**Why**")
        for reason in resp["reasons"]:
            st.markdown(f'<div class="reason">{reason}</div>', unsafe_allow_html=True)

    if resp["rows"]:
        df = pd.DataFrame(resp["rows"], columns=resp["columns"])
        st.markdown(f"**Result** ({len(df)} rows)")
        st.dataframe(df, use_container_width=True)


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    records = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip damaged lines
    df = pd.DataFrame(records)
    if not df.empty:
        df["time"] = pd.to_datetime(df["ts"], unit="s")
    return df
