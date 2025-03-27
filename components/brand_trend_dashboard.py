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

    # Only sum numeric sentiment columns (exclude "Brand")
    sentiment_cols = [col for col in summary.columns if col not in ["Brand"]]
    summary["Total"] = summary[sentiment_cols].sum(axis=1)

    # Avoid divide-by-zero issues
    summary["Complaint %"] = round((summary.get("Complaint", 0) / summary["Total"].replace(0, 1)) * 100, 1)

    return summary

def display_brand_dashboard(insights):
    st.header("📊 Brand-Level Insight Summary")
    st.markdown("🧮 **Complaint %** shows the share of negative mentions (Complaint) out of all brand mentions.")

    summary_df = summarize_brand_insights(insights)
    st.dataframe(summary_df, use_container_width=True)

    if st.checkbox("Show sentiment breakdown by brand"):
        st.bar_chart(summary_df.set_index("Brand")[["Praise", "Neutral", "Complaint"]])
