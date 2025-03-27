# trend_over_time.py — time-series dashboard with AI-ready trend signal overlays
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
    df.sort_values(by="_logged_at", inplace=True)

    daily = df.groupby(pd.Grouper(key="_logged_at", freq="D"))

    st.subheader("Total Insight Volume Over Time")
    st.line_chart(daily.size())

    st.subheader("Top Brands Over Time")
    brand_counts = df.groupby([pd.Grouper(key="_logged_at", freq="D"), "target_brand"]).size().unstack(fill_value=0)
    top_brands = brand_counts.sum().sort_values(ascending=False).head(6).index.tolist()
    st.line_chart(brand_counts[top_brands])

    st.subheader("Top Subtags Over Time")
    subtag_counts = df.groupby([pd.Grouper(key="_logged_at", freq="D"), "type_subtag"]).size().unstack(fill_value=0)
    top_tags = subtag_counts.sum().sort_values(ascending=False).head(6).index.tolist()
    st.line_chart(subtag_counts[top_tags])

    st.subheader("Avg PM Priority Over Time")
    st.line_chart(daily["pm_priority_score"].mean())

    if "_trend_keywords" in df.columns:
        st.subheader("Keyword-Based Trend Signals")
        keyword_series = df.explode("_trend_keywords")
        if not keyword_series.empty:
            signal_counts = keyword_series.groupby([pd.Grouper(key="_logged_at", freq="D"), "_trend_keywords"]).size().unstack(fill_value=0)
            top_keywords = signal_counts.sum().sort_values(ascending=False).head(6).index.tolist()
            st.line_chart(signal_counts[top_keywords])
