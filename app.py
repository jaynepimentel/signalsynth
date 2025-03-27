# app.py — SignalSynth with emerging insights, GPT, and improved UX

import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import defaultdict
from slugify import slugify
from datetime import datetime, timedelta
import pandas as pd

from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket
)
from components.emerging_trends import get_emerging_signals

# Setup
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
    st.error("❌ No precomputed insights found. Please run `precompute_insights.py`.")
    st.stop()

if "cached_ideas" not in st.session_state:
    st.session_state.cached_ideas = {}

# Sidebar settings
st.sidebar.header("⚙️ Settings")
use_gpt = st.sidebar.checkbox("💡 Enable GPT-4 PM Suggestions", value=OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("⚠️ Missing OpenAI API Key — GPT disabled.")

# 📆 Date Filter Shortcuts
st.sidebar.header("🗓️ Time Filter")
time_filter = st.sidebar.radio("Show Insights From:", ["All Time", "Last 7 Days", "Last 30 Days", "Custom Range"])
if time_filter == "Last 7 Days":
    start_date = datetime.today() - timedelta(days=7)
    end_date = datetime.today()
elif time_filter == "Last 30 Days":
    start_date = datetime.today() - timedelta(days=30)
    end_date = datetime.today()
elif time_filter == "Custom Range":
    start_date = st.sidebar.date_input("Start Date", value=datetime(2024, 1, 1))
    end_date = st.sidebar.date_input("End Date", value=datetime.today())
else:
    start_date = datetime(2020, 1, 1)
    end_date = datetime.today()

# 🔍 Insight filters
st.sidebar.header("Filter by Metadata")
filter_fields = {
    # "Scrum Team": "team",  # hidden
    # "Workflow Stage": "status",  # hidden
    "Effort Estimate": "effort",
    "Insight Type": "type_tag",
    "Persona": "persona",
    "Target Brand": "target_brand",
    "Brand Sentiment": "brand_sentiment",
    "Journey Stage": "journey_stage",
    "Clarity": "clarity"
}
filters = {
    key: st.sidebar.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)))
    for label, key in filter_fields.items()
}
show_trends_only = st.sidebar.checkbox("Highlight Emerging Topics Only", value=False)

# Brand Summary + Charts
st.subheader("📊 Brand Summary")
display_brand_dashboard(scraped_insights)

st.subheader("📈 Insight Charts")
display_insight_charts(scraped_insights)

# 🔥 Emerging Trends
st.subheader("🔥 Emerging Trends & Sentiment Shifts")
spikes, flips, keyword_spikes = get_emerging_signals()

trend_terms = set()
if spikes:
    st.markdown("**📈 Spiking Subtags**")
    for tag, ratio in spikes.items():
        trend_terms.add(tag.lower())
        st.markdown(f"- **{tag}** spiked ×{ratio}")
if flips:
    st.markdown("**📉 Sentiment Flips**")
    for brand, msg in flips.items():
        st.markdown(f"- **{brand}** → {msg}")
if keyword_spikes:
    st.markdown("**📊 Keyword Spikes**")
    for word, ratio in keyword_spikes.items():
        trend_terms.add(word.lower())
        st.markdown(f"- `{word}` ↑ {ratio}x")

# Match insights to trends + filters
filtered = []
for i in scraped_insights:
    text = i.get("text", "").lower()
    subtag = i.get("type_subtag", "").lower()
    keywords = i.get("_trend_keywords", [])
    insight_date = i.get("_logged_at") or i.get("timestamp") or "2024-01-01"
    try:
        ts = datetime.strptime(insight_date[:10], "%Y-%m-%d")
    except:
        ts = datetime(2024, 1, 1)
    if (
        all(filters[k] == "All" or i.get(k) == filters[k] for k in filters)
        and (not show_trends_only or subtag in trend_terms or any(k in trend_terms for k in keywords))
        and (start_date <= ts.date() <= end_date)
    ):
        filtered.append(i)

# 🧠 Show insights related to trends
st.subheader(f"📌 Insights Related to Filters ({len(filtered)} shown)")

# 📍 Pagination
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

# 🎨 Badges
BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Live Shopping": "#BC6FF1", "Search": "#118AB2"
}
def badge(label):
    color = BADGE_COLORS.get(label, "#ccc")
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

# 💬 Render insight cards
for idx, i in enumerate(paged_insights, start=start_idx):
    st.markdown(f"### 🧠 Insight: {i.get('title', i.get('text', '')[:60])}")
    tags = [badge(i.get(t)) for t in ["type_tag", "brand_sentiment", "effort", "journey_stage", "clarity"] if i.get(t)]
    st.markdown(" ".join(tags), unsafe_allow_html=True)
    st.caption(f"Score: {i.get('score', 0)} | PM Priority: {i.get('pm_priority_score', '?')} | Persona: {i.get('persona')} | Team: {i.get('team')}")
    if i.get("type_reason"):
        st.markdown(f"💡 _{i['type_reason']}_")

    with st.expander(f"🧠 Full Insight ({i.get('status', 'Unknown')})"):
        text = i.get("text", "")
        brand = i.get("target_brand", "eBay")
        st.markdown("**User Quote:**")
        st.markdown(f"> {text}")
        if i.get("url"):
            st.markdown(f"[🔗 View Original Post]({i['url']})")

        cache_key = f"{slugify(text)}_{brand}"
        if use_gpt and OPENAI_KEY_PRESENT and cache_key not in st.session_state.cached_ideas:
            with st.spinner("💡 Generating PM Suggestions..."):
                try:
                    st.session_state.cached_ideas[cache_key] = generate_pm_ideas(text, brand)
                except Exception as e:
                    st.session_state.cached_ideas[cache_key] = [f"[❌ GPT error: {str(e)}]"]

        ideas = st.session_state.cached_ideas.get(cache_key, i.get("ideas", []))
        if ideas:
            st.markdown("**💡 PM Suggestions:**")
            for idea in ideas:
                st.markdown(f"- {idea}")

        if i.get("clarity") == "Needs Clarification":
            st.warning("This insight may need refinement.")
            if st.button("🧼 Clarify This Insight", key=f"clarify_{idx}"):
                st.info("(This would re-run the insight through GPT to rephrase or flag it for triage.)")

        filename = slugify(i.get("title", i.get("text", "")[:40]))[:64]
        doc_type = st.selectbox("Select document type to generate:", ["PRD", "BRD", "PRFAQ", "JIRA"], key=f"doc_type_{idx}")
        if st.button(f"Generate {doc_type}", key=f"generate_doc_{idx}"):
            with st.spinner(f"Generating {doc_type}..."):
                if doc_type == "PRD":
                    file_path = generate_prd_docx(text, brand, filename)
                elif doc_type == "BRD":
                    file_path = generate_brd_docx(text, brand, filename + "-brd")
                elif doc_type == "PRFAQ":
                    file_path = generate_prfaq_docx(text, brand, filename + "-prfaq")
                elif doc_type == "JIRA":
                    file_content = generate_jira_bug_ticket(text, brand)
                    st.download_button("⬇️ Download JIRA", file_content, file_name=f"jira-{filename}.md", mime="text/markdown", key=f"dl_jira_{idx}")
                    file_path = None
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            f"⬇️ Download {doc_type}", f, file_name=os.path.basename(file_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_doc_{idx}")

# 🧱 Clustered Insight Mode
st.subheader("🧱 Clustered Insight Mode")
display_clustered_insight_cards(filtered)

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")
