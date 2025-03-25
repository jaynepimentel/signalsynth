# trend_over_time.py — renders trend lines by brand, sentiment, subtag
import streamlit as st
import pandas as pd
import json
from datetime import datetime

def load_trend_data(path="trend_log.jsonl"):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data

def display_trend_dashboard():
    st.header("📈 Trend Explorer (Over Time)")

    data = load_trend_data()
    if not data:
        st.warning("No trend data logged yet.")
        return

    df = pd.DataFrame(data)
    df["_logged_at"] = pd.to_datetime(df["_logged_at"])

    # --- Volume over time ---
    st.subheader("Total Insight Volume Over Time")
    st.line_chart(df.groupby(pd.Grouper(key="_logged_at", freq="D")).size())

    # --- Brand-specific trends ---
    st.subheader("Top Brands Over Time")
    brand_counts = df.groupby([pd.Grouper(key="_logged_at", freq="D"), "target_brand"]).size().unstack(fill_value=0)
    st.line_chart(brand_counts)

    # --- Subtag spikes ---
    st.subheader("Subtag Mentions Over Time")
    subtag_counts = df.groupby([pd.Grouper(key="_logged_at", freq="D"), "type_subtag"]).size().unstack(fill_value=0)
    st.line_chart(subtag_counts)

    # --- PM Priority trend ---
    st.subheader("Avg PM Priority Over Time")
    st.line_chart(df.groupby(pd.Grouper(key="_logged_at", freq="D"))["pm_priority_score"].mean())
