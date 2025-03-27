# insight_visualizer.py — advanced visual diagnostics with AI-aware trends and volatility
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
        st.bar_chart(df['target_brand'].fillna("Unknown").value_counts().head(8))

        st.subheader("Insight Type Distribution")
        st.bar_chart(df['type_tag'].fillna("Unknown").value_counts().head(8))

        if 'topic_focus' in df.columns:
            st.subheader("Topic Focus Breakdown")
            flat_topics = [t for sub in df['topic_focus'].dropna() for t in (sub if isinstance(sub, list) else [])]
            if flat_topics:
                st.bar_chart(pd.Series(flat_topics).value_counts().head(10))

        st.subheader("📊 PM Priority Score Trend (7-day Avg)")
        if 'pm_priority_score' in df.columns:
            df['_date'] = pd.to_datetime(df['_date'], errors='coerce')
            trend = df.set_index('_date').resample('7D')['pm_priority_score'].mean().dropna()
            st.line_chart(trend, use_container_width=True)

        st.subheader("📊 Complaint vs Praise Over Time")
        if 'brand_sentiment' in df.columns:
            df['_date'] = pd.to_datetime(df['_date'], errors='coerce')
            sent_trend = df.groupby([pd.Grouper(key='_date', freq='W'), 'brand_sentiment']).size().unstack(fill_value=0)
            st.area_chart(sent_trend, use_container_width=True)

        if '_trend_keywords' in df.columns:
            st.subheader("🔥 Top Emerging Keywords")
            keyword_df = df.explode('_trend_keywords')
            top_kw = keyword_df['_trend_keywords'].value_counts().head(10)
            st.bar_chart(top_kw)

        if 'effort' in df.columns:
            st.subheader("💼 Effort Breakdown")
            st.bar_chart(df['effort'].value_counts())

        if 'journey_stage' in df.columns:
            st.subheader("🧭 Journey Stage Breakdown")
            st.bar_chart(df['journey_stage'].value_counts())
