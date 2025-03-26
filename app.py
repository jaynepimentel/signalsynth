# app.py — Streamlit with optional GPT-4 PM Suggestions

import os
import json
import streamlit as st
from dotenv import load_dotenv
from components.brand_trend_dashboard import display_brand_dashboard
from collections import Counter
from components.ai_suggester import generate_pm_ideas

load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")

# Load precomputed insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found. Please run precompute_insights.py locally.")
    st.stop()

# Sidebar toggle
st.sidebar.header("⚙️ Settings")
use_gpt = st.sidebar.checkbox("💡 Enable GPT-4 PM Suggestions", value=True and OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("⚠️ Missing OpenAI API Key — GPT suggestions will not work.")

# Sidebar filters
st.sidebar.header("🔍 Filter Insights")
team_filter = st.sidebar.selectbox("Scrum Team", ["All"] + sorted(set(i.get("team", "Unknown") for i in scraped_insights)))
status_filter = st.sidebar.selectbox("Workflow Stage", ["All"] + sorted(set(i.get("status", "Unknown") for i in scraped_insights)))
effort_filter = st.sidebar.selectbox("Effort Estimate", ["All"] + sorted(set(i.get("effort", "Unknown") for i in scraped_insights)))
type_filter = st.sidebar.selectbox("Insight Type", ["All"] + sorted(set(i.get("type_tag", "Unknown") for i in scraped_insights)))
persona_filter = st.sidebar.selectbox("Persona", ["All"] + sorted(set(i.get("persona", "Unknown") for i in scraped_insights)))
brand_filter = st.sidebar.selectbox("Target Brand", ["All"] + sorted(set(i.get("target_brand", "Unknown") for i in scraped_insights)))
sentiment_filter = st.sidebar.selectbox("Brand Sentiment", ["All"] + sorted(set(i.get("brand_sentiment", "Unknown") for i in scraped_insights)))
show_trends_only = st.sidebar.checkbox("Highlight Emerging Topics Only", value=False)

# Brand Dashboard
with st.expander("📊 Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(scraped_insights)

# Detect keyword-based rising trends
topic_keywords = ["vault", "psa", "graded", "funko", "cancel", "authenticity", "shipping", "refund"]
trend_counter = Counter()
for i in scraped_insights:
    text = i.get("text", "").lower()
    for word in topic_keywords:
        if word in text:
            trend_counter[word] += 1
rising_trends = [t for t, count in trend_counter.items() if count >= 5]

if rising_trends:
    with st.expander("🔥 Emerging Trends Detected", expanded=True):
        for t in sorted(rising_trends):
            st.markdown(f"- **{t.title()}** ({trend_counter[t]} mentions)")
else:
    st.info("No trends above threshold this cycle.")

# Filter insights
filtered = []
for i in scraped_insights:
    text = i.get("text", "").lower()
    if (
        (team_filter == "All" or i.get("team") == team_filter)
        and (status_filter == "All" or i.get("status") == status_filter)
        and (effort_filter == "All" or i.get("effort") == effort_filter)
        and (type_filter == "All" or i.get("type_tag") == type_filter)
        and (persona_filter == "All" or i.get("persona") == persona_filter)
        and (brand_filter == "All" or i.get("target_brand") == brand_filter)
        and (sentiment_filter == "All" or i.get("brand_sentiment") == sentiment_filter)
        and (not show_trends_only or any(word in text for word in rising_trends))
    ):
        filtered.append(i)

# Show insights
for idx, i in enumerate(filtered):
    summary = i.get("summary") or i.get("text", "")[:80]
    st.markdown(f"### 🧠 Insight: {summary}")

    st.caption(
        f"Score: {i.get('score', 0)} | Type: {i.get('type_tag')} > {i.get('type_subtag', '')} "
        f"({i.get('type_confidence')}%) | Effort: {i.get('effort')} | Brand: {i.get('target_brand')} | "
        f"Sentiment: {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%) | Persona: {i.get('persona')}"
    )

    if i.get("type_reason"):
        st.markdown(f"💡 *Reason:* _{i['type_reason']}_")

    with st.expander(f"🧠 Full Insight ({i.get('status', 'Unknown')})"):
        st.write(f"**Persona:** {i.get('persona', 'Unknown')}")
        st.write(f"**Scrum Team:** {i.get('team', 'Triage')} | Source: {i.get('source', 'N/A')} | "
                 f"Last Updated: {i.get('last_updated', 'N/A')} | Score: {i.get('score', 0)}")

        st.markdown("**User Quotes:**")
        for quote in i.get("cluster", []):
            st.markdown(f"- _{quote}_")

        # GPT-powered PM Suggestions
        if use_gpt and OPENAI_KEY_PRESENT:
            with st.spinner("💡 Generating PM Suggestions..."):
                try:
                    i["ideas"] = generate_pm_ideas(i["text"], i.get("target_brand"))
                except Exception as e:
                    i["ideas"] = [f"[❌ GPT error: {str(e)}]"]

        if i.get("ideas"):
            st.markdown("**💡 PM Suggestions:**")
            for idx2, idea in enumerate(i["ideas"]):
                st.markdown(f"- {idea}")
                st.button(
                    label=f"Create JIRA Ticket: {idea[:30]}...",
                    key=f"jira_{idx}_{idx2}",
                    help="(Simulated) This would create a JIRA epic with linked context."
                )

        if st.button(f"Generate PRD for: {summary[:30]}...", key=f"prd_{idx}"):
            st.success("✅ PRD Generated! (mock - would send to Airtable or JIRA)")

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")
