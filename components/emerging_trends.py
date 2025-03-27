# emerging_trends.py — spike and sentiment shift detection with keyword-level AI hooks
import pandas as pd
import json
from datetime import datetime
from collections import defaultdict

def load_trend_data(path="trend_log.jsonl"):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return pd.DataFrame(rows)

def detect_spiking_subtags(df, window_days=7, threshold=2.0):
    df["_logged_at"] = pd.to_datetime(df["_logged_at"])
    recent = df[df["_logged_at"] >= pd.Timestamp.now() - pd.Timedelta(days=window_days)]
    prior = df[df["_logged_at"] < pd.Timestamp.now() - pd.Timedelta(days=window_days)]

    recent_counts = recent["type_subtag"].value_counts()
    prior_counts = prior["type_subtag"].value_counts().add(1)  # avoid div/0

    spike_ratio = (recent_counts / prior_counts).sort_values(ascending=False)
    spikes = spike_ratio[spike_ratio > threshold]

    return spikes.round(2).to_dict()

def detect_keyword_spikes(df, keyword_field="_trend_keywords", window_days=7, threshold=2.0):
    df["_logged_at"] = pd.to_datetime(df["_logged_at"])
    df = df.explode(keyword_field)
    df = df.dropna(subset=[keyword_field])

    recent = df[df["_logged_at"] >= pd.Timestamp.now() - pd.Timedelta(days=window_days)]
    prior = df[df["_logged_at"] < pd.Timestamp.now() - pd.Timedelta(days=window_days)]

    recent_counts = recent[keyword_field].value_counts()
    prior_counts = prior[keyword_field].value_counts().add(1)

    ratio = (recent_counts / prior_counts).sort_values(ascending=False)
    return ratio[ratio > threshold].round(2).to_dict()

def detect_sentiment_flips(df):
    df["_logged_at"] = pd.to_datetime(df["_logged_at"])
    df["day"] = df["_logged_at"].dt.date

    grouped = df.groupby(["day", "target_brand", "brand_sentiment"]).size().unstack(fill_value=0)
    sentiment_flips = {}

    for brand in grouped.index.get_level_values("target_brand").unique():
        brand_data = grouped.xs(brand, level="target_brand", drop_level=False)
        if "Praise" in brand_data.columns and "Complaint" in brand_data.columns:
            praise_trend = brand_data["Praise"].rolling(3).mean()
            complaint_trend = brand_data["Complaint"].rolling(3).mean()
            if len(praise_trend) > 3 and praise_trend.iloc[-1] < complaint_trend.iloc[-1]:
                sentiment_flips[brand] = "Complaint > Praise trend reversal"

    return sentiment_flips

def get_emerging_signals(path="trend_log.jsonl"):
    df = load_trend_data(path)
    if df.empty:
        return {}, {}, {}

    spikes = detect_spiking_subtags(df)
    flips = detect_sentiment_flips(df)

    keyword_spikes = {}
    if "_trend_keywords" in df.columns:
        try:
            keyword_spikes = detect_keyword_spikes(df)
        except Exception as e:
            print(f"⚠️ Keyword spike detection failed: {e}")

    return spikes, flips, keyword_spikes
