# insight_visualizer.py — advanced visual diagnostics with AI-aware trends and volatility
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime

def display_insight_charts(insights):
    if not insights:
        st.warning("No insights available to visualize.")
        return

    df = pd.DataFrame(insights)
    df['_date'] = pd.to_datetime(df.get('_logged_at') or df.get('timestamp') or datetime.today(), errors='coerce')

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
            trend = df.set_index('_date').resample('7D')['pm_priority_score'].mean().dropna()
            if not trend.empty:
                st.line_chart(trend, use_container_width=True)

        st.subheader("📊 Complaint vs Praise Over Time")
        if 'brand_sentiment' in df.columns:
            sent_trend = df.groupby([pd.Grouper(key='_date', freq='W'), 'brand_sentiment']).size().unstack(fill_value=0)
            if not sent_trend.empty:
                st.area_chart(sent_trend, use_container_width=True)

        if '_trend_keywords' in df.columns:
            st.subheader("🔥 Top Emerging Keywords")
            keyword_df = df.explode('_trend_keywords')
            top_kw = keyword_df['_trend_keywords'].value_counts().head(10)
            if not top_kw.empty:
                st.bar_chart(top_kw)

        if 'effort' in df.columns:
            st.subheader("💼 Effort Breakdown")
            st.bar_chart(df['effort'].value_counts())

        if 'journey_stage' in df.columns:
            st.subheader("🧭 Journey Stage Breakdown")
            st.bar_chart(df['journey_stage'].value_counts())

        # 🔥 Enhancement #2: Persona × Journey Stage Heatmap
        if 'persona' in df.columns and 'journey_stage' in df.columns:
            st.subheader("🧩 Persona × Journey Stage Heatmap")
            if 'pm_priority_score' not in df.columns:
                df['pm_priority_score'] = 50  # default if missing

            heatmap_df = df.pivot_table(
                index='persona',
                columns='journey_stage',
                values='pm_priority_score',
                aggfunc='mean'
            ).fillna(0)

            if heatmap_df.empty:
                st.info("Not enough data to render heatmap.")
            else:
                fig, ax = plt.subplots(figsize=(10, 4))
                sns.heatmap(heatmap_df, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=0.5)
                st.pyplot(fig)
