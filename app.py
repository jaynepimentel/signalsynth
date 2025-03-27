# app.py — SignalSynth UI with Explorer and Cluster modes, fixed expander nesting

import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import Counter
from slugify import slugify
import tempfile

from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_jira_bug_ticket
)

# Setup
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))
st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")

# Load insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found. Please run `precompute_insights.py`.")
    st.stop()

# Sidebar: Filters
st.sidebar.header("⚙️ Settings")
use_gpt = st.sidebar.checkbox("💡 Enable GPT-4 PM Suggestions", value=OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("⚠️ Missing OpenAI API Key — GPT disabled.")

st.sidebar.header("🔍 Filter Insights")
filter_fields = {
    "Scrum Team": "team",
    "Workflow Stage": "status",
    "Effort Estimate": "effort",
    "Insight Type": "type_tag",
    "Persona": "persona",
    "Target Brand": "target_brand",
    "Brand Sentiment": "brand_sentiment"
}
filters = {}
for label, key in filter_fields.items():
    options = ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights))
    filters[key] = st.sidebar.selectbox(label, options)

show_trends_only = st.sidebar.checkbox("Highlight Emerging Topics Only", value=False)

# Dashboards
st.subheader("📊 Brand Summary")
display_brand_dashboard(scraped_insights)

st.subheader("📈 Insight Trends")
display_insight_charts(scraped_insights)

# Detect trends
topic_keywords = ["vault", "psa", "graded", "fanatics", "cancel", "authenticity", "shipping", "refund"]
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
    match = all(filters[k] == "All" or i.get(k) == filters[k] for k in filters)
    if match and (not show_trends_only or any(word in text for word in rising_trends)):
        filtered.append(i)

# 🔍 Explorer Mode (not nested in expander anymore)
st.subheader("🧭 Insight Explorer Mode")
display_insight_explorer(filtered)

# 📌 Clustered Insight Mode
with st.expander("🧱 Clustered Insight Mode", expanded=False):
    display_clustered_insight_cards(filtered)

# Pagination
INSIGHTS_PER_PAGE = 10
total_pages = max(1, (len(filtered) + INSIGHTS_PER_PAGE - 1) // INSIGHTS_PER_PAGE)
if "page" not in st.session_state:
    st.session_state.page = 1

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅️ Previous"):
        st.session_state.page = max(1, st.session_state.page - 1)
with col2:
    st.markdown(f"**Page {st.session_state.page} of {total_pages}**")
with col3:
    if st.button("Next ➡️"):
        st.session_state.page = min(total_pages, st.session_state.page + 1)

start_idx = (st.session_state.page - 1) * INSIGHTS_PER_PAGE
paged_insights = filtered[start_idx:start_idx + INSIGHTS_PER_PAGE]

# Individual Insights
st.subheader("📌 Individual Insights")
for idx, i in enumerate(paged_insights, start=start_idx):
    summary = i.get("summary") or i.get("text", "")[:80]
    st.markdown(f"### 🧠 Insight: {summary}")

    st.caption(
        f"Score: {i.get('score', 0)} | Type: {i.get('type_tag')} > {i.get('type_subtag', '')} "
        f"({i.get('type_confidence')}%) | Effort: {i.get('effort')} | Brand: {i.get('target_brand')} | "
        f"Sentiment: {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%) | Persona: {i.get('persona')}"
    )

    with st.expander(f"🧠 Full Insight ({i.get('status', 'Unknown')})"):
        text = i.get("text", "")
        brand = i.get("target_brand", "eBay")
        st.markdown("**User Quote:**")
        st.markdown(f"> {text}")

        if use_gpt and OPENAI_KEY_PRESENT:
            with st.spinner("💡 Generating PM Suggestions..."):
                try:
                    i["ideas"] = generate_pm_ideas(text, brand)
                except Exception as e:
                    i["ideas"] = [f"[❌ GPT error: {str(e)}]"]

        if i.get("ideas"):
            st.markdown("**💡 PM Suggestions:**")
            for idea in i["ideas"]:
                st.markdown(f"- {idea}")

        filename = slugify(summary)[:64]
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if st.button(f"📄 Generate PRD", key=f"btn_prd_{idx}"):
                with st.spinner("Creating PRD..."):
                    file_path = generate_prd_docx(text, brand, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button("⬇️ Download PRD", f, file_name=os.path.basename(file_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_prd_{idx}")

        with col_b:
            if st.button(f"📄 Generate BRD", key=f"btn_brd_{idx}"):
                with st.spinner("Creating BRD..."):
                    file_path = generate_brd_docx(text, brand, filename + "-brd")
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button("⬇️ Download BRD", f, file_name=os.path.basename(file_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_brd_{idx}")

        with col_c:
            if st.button(f"🐞 Generate JIRA", key=f"btn_jira_{idx}"):
                with st.spinner("Creating JIRA ticket..."):
                    jira = generate_jira_bug_ticket(text, brand)
                    st.download_button("⬇️ Download JIRA", jira, file_name=f"jira-{filename}.md", mime="text/markdown", key=f"dl_jira_{idx}")

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")