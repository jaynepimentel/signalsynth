# app.py — Merged SignalSynth with full filters, GPT, clusters, dashboards, PRD buttons, and pagination

import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import defaultdict
from slugify import slugify
from datetime import datetime, timedelta
import pandas as pd

from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_explorer import display_insight_explorer
from components.cluster_synthesizer import generate_synthesized_insights
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
os.environ["RUNNING_IN_STREAMLIT"] = "1"

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("\ud83d\udcf1 SignalSynth: Collectibles Insight Engine")

if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"\u2705 Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("\u274c No precomputed insights found. Please run `precompute_insights.py`.")
    st.stop()

if "cached_ideas" not in st.session_state:
    st.session_state.cached_ideas = {}

# GPT toggle
st.sidebar.header("\u2699\ufe0f Settings")
use_gpt = st.sidebar.checkbox("\ud83d\udca1 Enable GPT-4 PM Suggestions", value=OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("\u26a0\ufe0f Missing OpenAI API Key — GPT disabled.")

# --- Date Filter
st.markdown("### \ud83d\uddd3\ufe0f Date Filter")
time_filter = st.radio("Show Insights From:", ["All Time", "Last 7 Days", "Last 30 Days", "Custom Range"], horizontal=True)

if time_filter == "Last 7 Days":
    start_date = datetime.today().date() - timedelta(days=7)
    end_date = datetime.today().date()
elif time_filter == "Last 30 Days":
    start_date = datetime.today().date() - timedelta(days=30)
    end_date = datetime.today().date()
elif time_filter == "Custom Range":
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime(2024, 1, 1).date(), key="main_start")
    with col2:
        end_date = st.date_input("End Date", value=datetime.today().date(), key="main_end")
else:
    start_date = datetime(2020, 1, 1).date()
    end_date = datetime.today().date()

# --- Filters
mobile_filters_expanded = st.checkbox("\ud83d\uded9 Show Filters Inline (Mobile Friendly)", value=False)

filter_fields = {
    "Effort Estimate": "effort",
    "Insight Type": "type_tag",
    "Persona": "persona",
    "Target Brand": "target_brand",
    "Brand Sentiment": "brand_sentiment",
    "Journey Stage": "journey_stage",
    "Clarity": "clarity"
}

if mobile_filters_expanded:
    st.markdown("### \ud83d\udd0e Filter Insights")
    filters = {
        key: st.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)), key=f"mobile_{key}")
        for label, key in filter_fields.items()
    }
else:
    st.sidebar.header("Filter by Metadata")
    filters = {
        key: st.sidebar.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)), key=f"sidebar_{key}")
        for label, key in filter_fields.items()
    }

search_query = st.text_input("\ud83d\udd0d Search inside insights (optional)").strip().lower()

# --- Emerging Trends
st.subheader("\ud83d\udd25 Emerging Trends & Sentiment Shifts")
try:
    spikes, flips, keyword_spikes = get_emerging_signals()
except ValueError:
    spikes, flips = get_emerging_signals()
    keyword_spikes = {}

if not (spikes or flips or keyword_spikes):
    st.info("No recent emerging trends detected yet.")

trend_terms = set()
if spikes:
    st.markdown("**\ud83d\udcc8 Spiking Subtags**")
    for tag, ratio in spikes.items():
        trend_terms.add(tag.lower())
        st.markdown(f"- **{tag}** spiked ×{ratio}")
if flips:
    st.markdown("**\ud83d\udcc9 Sentiment Flips**")
    for brand, msg in flips.items():
        st.markdown(f"- **{brand}** → {msg}")
if keyword_spikes:
    st.markdown("**\ud83d\udcca Keyword Spikes**")
    for word, ratio in keyword_spikes.items():
        trend_terms.add(word.lower())
        st.markdown(f"- `{word}` ↑ {ratio}x")

# --- Filter Insights
filtered_insights = []
for i in scraped_insights:
    try:
        date_obj = datetime.fromisoformat(i.get("_logged_at", "2023-01-01")).date()
    except:
        continue
    if not (start_date <= date_obj <= end_date):
        continue
    if any(filters[key] != "All" and i.get(key, "Unknown") != filters[key] for key in filter_fields.values()):
        continue
    if search_query and search_query not in i.get("text", "").lower():
        continue
    filtered_insights.append(i)

st.markdown(f"### \ud83d\udccb Showing {len(filtered_insights)} filtered insights")

# Pagination Setup
page_size = 10
max_page = max(1, len(filtered_insights) // page_size + int(len(filtered_insights) % page_size > 0))
page = st.number_input("Page", min_value=1, max_value=max_page, value=1)
start_idx = (page - 1) * page_size
end_idx = start_idx + page_size
paged_insights = filtered_insights[start_idx:end_idx]

# --- View Switch
st.subheader("\ud83d\udecd\ufe0f Explore Insights")
view_mode = st.radio("View Mode:", ["Explorer", "Clusters", "Raw List"], horizontal=True)

if view_mode == "Explorer":
    display_insight_explorer(paged_insights)
elif view_mode == "Clusters":
    st.subheader("\ud83e\uddd0 Clustered Insights")
    clusters = generate_synthesized_insights(paged_insights)
    for c in clusters:
        st.markdown(f"#### {c['title']}")
        st.markdown(f"_Brand: {c['brand']} — {c['summary']}_")
        st.markdown("**Quotes:**")
        for q in c["quotes"]:
            st.markdown(q)
        if c["top_ideas"]:
            st.markdown("**Top Suggestions:**")
            for idea in c["top_ideas"]:
                st.markdown(f"- {idea}")
        st.markdown("---")
else:
    for i in paged_insights:
        st.markdown(f"- _{i.get('text', '')}_")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Generate PRD", key=f"prd_{i['text'][:20]}"):
                prd = generate_prd_docx(i['text'])
                st.success("PRD generated!")
        with col2:
            if st.button("Generate BRD", key=f"brd_{i['text'][:20]}"):
                brd = generate_brd_docx(i['text'])
                st.success("BRD generated!")
        with col3:
            if st.button("Generate JIRA", key=f"jira_{i['text'][:20]}"):
                jira = generate_jira_bug_ticket(i['text'])
                st.success("JIRA ticket generated!")

# --- Brand Dashboard
with st.expander("\ud83d\udcca Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(filtered_insights)

st.sidebar.markdown("---")
st.sidebar.caption("\ud83d\udd00 Powered by strategic signal + customer voice \u2728")
