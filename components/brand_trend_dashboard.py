# brand_trend_dashboard.py — Enhanced brand dashboard with trend chart and sentiment share
import pandas as pd
import streamlit as st
import altair as alt

def summarize_brand_insights(insights):
    rows = []
    for i in insights:
        brand = i.get("target_brand", "Unknown")
        sentiment = i.get("brand_sentiment", "Neutral")
        logged_at = i.get("_logged_at")
        rows.append((brand, sentiment, logged_at))

    df = pd.DataFrame(rows, columns=["Brand", "Sentiment", "Date"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    sentiment_counts = df.groupby(["Brand", "Sentiment"]).size().unstack(fill_value=0).reset_index()

    # Add Complaint %
    sentiment_cols = [col for col in sentiment_counts.columns if col not in ["Brand"]]
    sentiment_counts["Total"] = sentiment_counts[sentiment_cols].sum(axis=1)
    sentiment_counts["Complaint %"] = round((sentiment_counts.get("Complaint", 0) / sentiment_counts["Total"].replace(0, 1)) * 100, 1)

    return df, sentiment_counts

def display_brand_dashboard(insights):
    st.header("📊 Brand-Level Insight Summary")
    st.markdown("🧮 **Complaint %** shows the share of negative mentions out of total sentiment mentions for each brand.")

    df, summary = summarize_brand_insights(insights)

    # Brand Filter
    brand_list = sorted(df["Brand"].dropna().unique())
    selected_brands = st.multiselect("🔎 Filter by Brand", options=brand_list, default=brand_list)
    filtered_df = df[df["Brand"].isin(selected_brands)]
    filtered_summary = summary[summary["Brand"].isin(selected_brands)]

    # Summary Table
    st.dataframe(filtered_summary.sort_values("Complaint %", ascending=False), use_container_width=True)

    # Trend Over Time Chart
    if st.checkbox("📈 Show Volume Trend Over Time by Brand"):
        daily_counts = (
            filtered_df.groupby([pd.Grouper(key="Date", freq="W"), "Brand"])
            .size()
            .reset_index(name="Mentions")
        )
        chart = alt.Chart(daily_counts).mark_line(point=True).encode(
            x=alt.X("Date:T", title="Week"),
            y=alt.Y("Mentions:Q"),
            color="Brand:N"
        ).properties(height=350)
        st.altair_chart(chart, use_container_width=True)

    # Sentiment Stacked Chart
    if st.checkbox("📊 Show Sentiment Breakdown by Brand"):
        melted = filtered_df.groupby(["Brand", "Sentiment"]).size().reset_index(name="Count")
        chart = alt.Chart(melted).mark_bar().encode(
            x=alt.X("Brand:N"),
            y=alt.Y("Count:Q"),
            color=alt.Color("Sentiment:N"),
            tooltip=["Brand", "Sentiment", "Count"]
        ).properties(height=350)
        st.altair_chart(chart, use_container_width=True)
