# app.py — SignalSynth mobile-friendly with trends, filters, GPT, clusters

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
st.title("📱 SignalSynth: Collectibles Insight Engine")

if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found. Please run `precompute_insights.py`.")
    st.stop()

if "cached_ideas" not in st.session_state:
    st.session_state.cached_ideas = {}

# GPT toggle
st.sidebar.header("⚙️ Settings")
use_gpt = st.sidebar.checkbox("💡 Enable GPT-4 PM Suggestions", value=OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("⚠️ Missing OpenAI API Key — GPT disabled.")

# --- Inline Date Filter (Mobile Friendly)
st.markdown("### 🗓️ Date Filter")
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

# --- Mobile-Friendly Filter Toggle
mobile_filters_expanded = st.checkbox("🛍 Show Filters Inline (Mobile Friendly)", value=False)

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
    st.markdown("### 🔎 Filter Insights")
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

search_query = st.text_input("🔍 Search inside insights (optional)").strip().lower()

# Emerging trends
st.subheader("🔥 Emerging Trends & Sentiment Shifts")
spikes, flips, keyword_spikes = get_emerging_signals()

if not (spikes or flips or keyword_spikes):
    st.info("No recent emerging trends detected yet.")

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
