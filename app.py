# app.py — Debug-enhanced with diagnostics, safe filters, and date fallback

import os
import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
from slugify import slugify

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="SignalSynth", layout="wide")

# Component imports
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.emerging_trends import detect_emerging_topics, render_emerging_topics
from components.floating_filters import render_floating_filters
from components.journey_heatmap import display_journey_heatmap
from components.ai_suggester import (
    generate_pm_ideas, generate_prd_docx, generate_brd_docx,
    generate_prfaq_docx, generate_jira_bug_ticket, generate_gpt_doc,
    generate_multi_signal_prd
)
from components.strategic_tools import (
    display_signal_digest, display_journey_breakdown,
    display_brand_comparator, display_impact_heatmap,
    display_prd_bundler, display_spark_suggestions
)
from components.enhanced_insight_view import render_insight_cards

# Load env + OpenAI key
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

# Safe date parser with fallback
def safe_date_from_insight(i):
    for field in ["post_date", "_logged_date"]:
        value = i.get(field)
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except:
                continue
    return None

# Lazy embedding model loader
@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        st.warning(f"⚠️ Failed to load embedding model: {e}")
        return None

# Header UI
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# Hide sidebar
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

# Load insights
try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    with open("gpt_suggestion_cache.json", "r", encoding="utf-8") as f:
        cache = json.load(f)
    for i in scraped_insights:
        i["ideas"] = cache.get(i.get("text", ""), [])
    st.success(f"✅ Loaded {len(scraped_insights)} insights")
except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
    st.stop()

# Filters
filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Subtag": "type_subtag",
    "Effort Estimate": "effort",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity"
}

# Define tabs
tabs = st.tabs([
    "📌 Insights",
    "🗺 Journey Heatmap",
    "🧱 Clusters",
    "🔎 Explorer",
    "📈 Trends",
    "🔥 Emerging",
    "🧠 Strategic Tools"
])

# Global time range filter
st.sidebar.header("🕓 Time Range Filter")
min_date = st.sidebar.date_input("Start Date", datetime.now().date() - timedelta(days=30))
max_date = st.sidebar.date_input("End Date", datetime.now().date())

filtered_by_date = [i for i in scraped_insights if (d := safe_date_from_insight(i)) and min_date <= d <= max_date]

# DEBUG
st.sidebar.markdown(f"📊 Insights in date range: {len(filtered_by_date)}")
if filtered_by_date:
    st.sidebar.code(list(filtered_by_date[0].keys()))

# Tab 0 — Insights
with tabs[0]:
    st.header("📌 Individual Insights")
    try:
        filters = render_floating_filters(filtered_by_date, filter_fields, key_prefix="insights")
        filtered = [
            i for i in filtered_by_date
            if all(
                filters[k] == "All" or str(i.get(k, "Unknown")).strip().lower() == filters[k].strip().lower()
                for k in filters
            )
        ]

        complaint_count = sum(1 for i in filtered if i.get("brand_sentiment") == "Complaint")
        dev_count = sum(1 for i in filtered if i.get("is_dev_feedback"))
        st.markdown(f"✅ **Filtered Count**: {len(filtered)} — 🔥 **Complaint %**: {round(100 * complaint_count / len(filtered), 1) if filtered else 0}% — 🧑‍💻 **Dev Feedback**: {dev_count}")

        model = get_model()
        render_insight_cards(filtered, model, key_prefix="insights")
    except Exception as e:
        st.error(f"❌ Insights tab error: {e}")

# Tab 1 — Journey Heatmap
with tabs[1]:
    st.header("🗺 Journey Heatmap")
    try:
        display_journey_heatmap(filtered_by_date)
    except Exception as e:
        st.error(f"❌ Journey Heatmap error: {e}")

# Tab 2 — Clusters
with tabs[2]:
    st.header("🧱 Clustered Insight Mode")
    try:
        model = get_model()
        if model:
            display_clustered_insight_cards(filtered_by_date)
        else:
            st.warning("⚠️ Embedding model not available. Skipping clustering.")
    except Exception as e:
        st.error(f"❌ Cluster view error: {e}")

# Tab 3 — Explorer
with tabs[3]:
    st.header("🔎 Insight Explorer")
    try:
        explorer_filters = render_floating_filters(filtered_by_date, filter_fields, key_prefix="explorer")
        explorer_filtered = [
            i for i in filtered_by_date
            if all(
                explorer_filters[k] == "All" or str(i.get(k, "Unknown")).strip().lower() == explorer_filters[k].strip().lower()
                for k in explorer_filters
            )
        ]
        results = display_insight_explorer(explorer_filtered)
        if results:
            model = get_model()
            render_insight_cards(results[:50], model, key_prefix="explorer")
    except Exception as e:
        st.error(f"❌ Explorer tab error: {e}")

# Tab 4 — Trends
with tabs[4]:
    st.header("📈 Trends + Brand Summary")
    try:
        display_insight_charts(filtered_by_date)
        display_brand_dashboard(filtered_by_date)
    except Exception as e:
        st.error(f"❌ Trends tab error: {e}")

# Tab 5 — Emerging Topics
with tabs[5]:
    st.header("🔥 Emerging Topics")
    try:
        render_emerging_topics(detect_emerging_topics(filtered_by_date))
    except Exception as e:
        st.error(f"❌ Emerging tab error: {e}")

# Tab 6 — Strategic Tools
with tabs[6]:
    st.header("🧠 Strategic Tools")
    try:
        display_spark_suggestions(filtered_by_date)
        display_signal_digest(filtered_by_date)
        display_impact_heatmap(filtered_by_date)
        display_journey_breakdown(filtered_by_date)
        display_brand_comparator(filtered_by_date)
        display_prd_bundler(filtered_by_date)
    except Exception as e:
        st.error(f"❌ Strategic Tools tab error: {e}")
