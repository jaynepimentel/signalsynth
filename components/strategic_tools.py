# components/strategic_tools.py
import streamlit as st
import pandas as pd
import random
import altair as alt
from collections import Counter

# ─────────────────────────────────────────────
# 🔹 SPARK SUGGESTIONS

def display_spark_suggestions(insights):
    spark_ideas = [
        "🔍 Try comparing Fanatics vs. PSA on complaint types",
        "🪄 Generate a PRFAQ from the most recent Vault cluster",
        "📈 Check if sentiment flipped for Whatnot this week",
        "🧱 Look at Clusters to find recurring friction themes",
        "📌 Generate a PRD from your top scoring insight"
    ]
    st.markdown("#### ✨ Spark Suggestions")
    st.info(random.choice(spark_ideas))

# ─────────────────────────────────────────────
# 🔹 EXEC DIGEST

def display_signal_digest(insights):
    st.markdown("### 🧠 Executive Signal Digest")
    st.markdown("- Top complaint: **{}**".format(top_complaint_subtag(insights)))
    st.markdown("- Fastest rising tag: **{}**".format(spiking_topic(insights)))
    st.markdown("- Most mentioned brand: **{}**".format(most_mentioned_brand(insights)))
    st.markdown("- Average PM priority: **{}**".format(round(sum(i.get('pm_priority_score', 0) for i in insights)/len(insights), 2)))


def top_complaint_subtag(insights):
    tags = [i.get("type_subtag", "") for i in insights if i.get("brand_sentiment") == "Complaint"]
    return Counter(tags).most_common(1)[0][0] if tags else "N/A"

def spiking_topic(insights):
    keywords = ["vault", "refund", "cancel", "delay", "graded"]
    spike_count = Counter()
    for i in insights:
        text = i.get("text", "").lower()
        for k in keywords:
            if k in text:
                spike_count[k] += 1
    return spike_count.most_common(1)[0][0] if spike_count else "N/A"

def most_mentioned_brand(insights):
    brands = [i.get("target_brand", "Unknown") for i in insights]
    return Counter(brands).most_common(1)[0][0] if brands else "Unknown"

# ─────────────────────────────────────────────
# 🔹 JOURNEY STAGE BREAKDOWN

def display_journey_breakdown(insights):
    st.markdown("### 📍 Journey Stage Sentiment Breakdown")
    df = pd.DataFrame([
        {
            "Journey": i.get("journey_stage", "Unknown"),
            "Sentiment": i.get("brand_sentiment", "Neutral")
        }
        for i in insights
    ])
    if df.empty:
        st.warning("No journey stage data available.")
        return
    chart = alt.Chart(df).mark_bar().encode(
        x='Journey:N',
        color='Sentiment:N',
        y='count()'
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)

# ─────────────────────────────────────────────
# 🔹 BRAND / FEATURE COMPARATOR

def display_brand_comparator(insights):
    st.markdown("### 🆚 Brand or Feature Comparison")
    options = sorted(set(i.get("target_brand", "Unknown") for i in insights))
    a = st.selectbox("Select Brand A", options, index=0, key="compare_a")
    b = st.selectbox("Select Brand B", options, index=1 if len(options) > 1 else 0, key="compare_b")
    
    def sentiment_breakdown(brand):
        return Counter(i.get("brand_sentiment", "Neutral") for i in insights if i.get("target_brand") == brand)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"#### {a}")
        st.json(sentiment_breakdown(a))
    with col2:
        st.markdown(f"#### {b}")
        st.json(sentiment_breakdown(b))

# ─────────────────────────────────────────────
# 🔹 IMPACT HEATMAP

def display_impact_heatmap(insights):
    st.markdown("### 🎯 Impact Heatmap (Frustration vs. Opportunity)")
    df = pd.DataFrame([
        {
            "text": i.get("text", "")[:80],
            "frustration": i.get("severity_score", 50),
            "opportunity": i.get("pm_priority_score", 50)
        }
        for i in insights
    ])
    if df.empty:
        st.warning("No insights with scoring available.")
        return

    chart = alt.Chart(df).mark_circle(size=90).encode(
        x=alt.X("frustration", scale=alt.Scale(zero=False)),
        y=alt.Y("opportunity", scale=alt.Scale(zero=False)),
        tooltip=["text", "frustration", "opportunity"]
    ).interactive().properties(height=400)

    st.altair_chart(chart, use_container_width=True)

# ─────────────────────────────────────────────
# 🔹 MULTI-PRD BUNDLER

def display_prd_bundler(insights):
    st.markdown("### 📦 Bundle Insights into One PRD")
    options = [f"{i.get('title') or i.get('text')[:50]}" for i in insights]
    selected = st.multiselect("Select Insights to Combine", options, max_selections=5)
    if selected and st.button("🛠 Generate Consolidated PRD"):
        st.info("(This would call generate_multi_signal_prd and create a download link.)")
