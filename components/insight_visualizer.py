# insight_visualizer.py — advanced visual diagnostics with AI-aware trends
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def display_insight_charts(insights):
    if not insights:
        st.warning("No insights available to visualize.")
        return

    df = pd.DataFrame(insights)
    df['_date'] = pd.to_datetime(df.get('_logged_at') or df.get('timestamp') or datetime.today())

    with st.expander("📈 Insight Trends & Distribution", expanded=False):
        st.subheader("Sentiment Distribution")
        st.bar_chart(df['brand_sentiment'].value_counts())

        st.subheader("Top Mentioned Brands")
        st.bar_chart(df['target_brand'].fillna("Unknown").value_counts())

        st.subheader("Insight Type Distribution")
        st.bar_chart(df['type_tag'].fillna("Unknown").value_counts())

        if 'topic_focus' in df.columns:
            st.subheader("Topic Focus Breakdown")
            flat_topics = [t for sub in df['topic_focus'].dropna() for t in (sub if isinstance(sub, list) else [])]
            if flat_topics:
                st.bar_chart(pd.Series(flat_topics).value_counts())

        # New: PM Priority Score Trend Over Time
        st.subheader("📊 PM Priority Score Trend (7d avg)")
        if 'pm_priority_score' in df.columns:
            df['_date'] = pd.to_datetime(df['_date'], errors='coerce')
            df_trend = df.set_index('_date').resample('7D')['pm_priority_score'].mean().dropna()
            st.line_chart(df_trend, use_container_width=True)

        # New: Complaint vs Praise Over Time
        st.subheader("📊 Complaint vs Praise Trend")
        if 'brand_sentiment' in df.columns:
            df_sent = df.copy()
            df_sent['_date'] = pd.to_datetime(df_sent['_date'], errors='coerce')
            sentiment_trend = df_sent.groupby([pd.Grouper(key="_date", freq="W"), 'brand_sentiment']).size().unstack().fillna(0)
            st.area_chart(sentiment_trend, use_container_width=True)
