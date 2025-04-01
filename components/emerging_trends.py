# emerging_trends.py — detects emerging issues based on spikes and sentiment shifts
import pandas as pd
import json
from datetime import datetime
import streamlit as st

def load_trend_data(path="trend_log.jsonl"):
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
    except Exception as e:
        st.warning(f"⚠️ Could not load trend log: {e}")
    return pd.DataFrame(rows)

def detect_spiking_subtags(df, window_days=7, threshold=2.0):
    df["_logged_at"] = pd.to_datetime(df["_logged_at"], errors="coerce")
    recent = df[df["_logged_at"] >= pd.Timestamp.now() - pd.Timedelta(days=window_days)]
    prior = df[df["_logged_at"] < pd.Timestamp.now() - pd.Timedelta(days=window_days)]

    recent_counts = recent["type_subtag"].value_counts()
    prior_counts = prior["type_subtag"].value_counts().add(1)  # avoid div/0

    spike_ratio = (recent_counts / prior_counts).sort_values(ascending=False)
    spikes = spike_ratio[spike_ratio > threshold]

    return spikes.round(2).to_dict()

def detect_sentiment_flips(df):
    df["_logged_at"] = pd.to_datetime(df["_logged_at"], errors="coerce")
    df["day"] = df["_logged_at"].dt.date

    grouped = df.groupby(["day", "target_brand", "brand_sentiment"]).size().unstack(fill_value=0)
    sentiment_flips = {}

    for brand in grouped.index.get_level_values("target_brand").unique():
        brand_data = grouped.xs(brand, level="target_brand", drop_level=False)
        if "Praise" in brand_data.columns and "Complaint" in brand_data.columns:
            praise_trend = brand_data["Praise"].rolling(3).mean()
            complaint_trend = brand_data["Complaint"].rolling(3).mean()
            if len(praise_trend) > 0 and len(complaint_trend) > 0:
                if praise_trend.iloc[-1] < complaint_trend.iloc[-1]:
                    sentiment_flips[brand] = "Complaint > Praise trend reversal"

    return sentiment_flips

def detect_emerging_topics(insights):
    df = pd.DataFrame(insights)
    if df.empty or '_logged_at' not in df.columns:
        return {"spikes": {}, "flips": {}}

    spikes = detect_spiking_subtags(df)
    flips = detect_sentiment_flips(df)
    return {"spikes": spikes, "flips": flips}

def render_emerging_topics(results):
    spikes = results.get("spikes", {})
    flips = results.get("flips", {})

    if not spikes and not flips:
        st.info("No emerging topics found in this cycle.")
        return

    if spikes:
        st.subheader("📈 Subtag Spike Alerts")
        for k, v in spikes.items():
            st.markdown(f"- **{k}** spiked by **{v}x**")

    if flips:
        st.subheader("⚠️ Sentiment Reversals")
        for brand, note in flips.items():
            st.markdown(f"- **{brand}**: {note}")