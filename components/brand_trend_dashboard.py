# brand_trend_dashboard.py — Brand-level summary dashboard for SignalSynth
import pandas as pd
import streamlit as st

def summarize_brand_insights(insights):
    rows = []
    for i in insights:
        brand = i.get("target_brand", "Unknown")
        sentiment = i.get("brand_sentiment", "Neutral")
        rows.append((brand, sentiment))

    df = pd.DataFrame(rows, columns=["Brand", "Sentiment"])
    summary = df.value_counts().unstack(fill_value=0).reset_index()
    return summary

def display_brand_dashboard(insights):
    st.header("📊 Brand-Level Insight Summary")
    summary_df = summarize_brand_insights(insights)
    st.dataframe(summary_df, use_container_width=True)

    if st.checkbox("Show sentiment breakdown by brand"):
        st.bar_chart(summary_df.set_index("Brand"))
