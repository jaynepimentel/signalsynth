# insight_visualizer.py — summary charts and visual trends
import streamlit as st
import pandas as pd

def display_insight_charts(insights):
    if not insights:
        st.warning("No insights available to visualize.")
        return

    with st.expander("📈 Insight Trends & Distribution", expanded=False):
        st.subheader("Sentiment Distribution")
        sentiments = [i.get("brand_sentiment", "Neutral") for i in insights]
        st.bar_chart(pd.Series(sentiments).value_counts())

        st.subheader("Top Mentioned Brands")
        brands = [i.get("target_brand", "Unknown") for i in insights]
        st.bar_chart(pd.Series(brands).value_counts())

        st.subheader("Insight Type Distribution")
        insight_types = [i.get("type_tag", "Unknown") for i in insights]
        st.bar_chart(pd.Series(insight_types).value_counts())
