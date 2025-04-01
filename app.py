# app.py — Final merged version with fixes for deployment, seaborn safe, clustering optional, and unique key_prefixes
import os
import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from slugify import slugify
from sentence_transformers import SentenceTransformer, util

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="SignalSynth", layout="wide")

# Core component imports
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

# Embedding model cache
@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    try:
        model = SentenceTransformer("models/all-MiniLM-L6-v2")
        return model.to("cpu")
    except Exception as e:
        st.warning(f"⚠️ Failed to load embedding model: {e}")
        return None

model = get_model()

# UI Header
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# Hide sidebar
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

# Onboarding expander
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth! What Can You Do Here?", expanded=True):
        st.markdown("""
        SignalSynth helps you transform user signals into strategic action.

        **💥 Key Features:**
        - Filter by brand, persona, journey stage, and sentiment
        - Generate PRD, BRD, PRFAQ, or JIRA ticket for any insight
        - Visualize trend shifts and brand sentiment
        - Bundle, clarify, and tag insights
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

# Load insights + suggestions
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

# Filter field config
filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Effort Estimate": "effort",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity"
}

# Define tabs
TABS = [
    "📌 Insights", "🧱 Clusters", "🔎 Explorer", "📈 Trends",
    "🔥 Emerging", "🧠 Strategic Tools", "📺 Journey Heatmap"
]
tabs = st.tabs(TABS)

# Tab 0: Full Insight View
with tabs[0]:
    st.header("📌 Individual Insights")
    filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="insights")
    filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]
    render_insight_cards(filtered, model, key_prefix="insights")

# Tab 1: Clusters
with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    if model:
        display_clustered_insight_cards(scraped_insights)
    else:
        st.warning("⚠️ Embedding model not available. Skipping clustering.")

# Tab 2: Explorer + keyword
with tabs[2]:
    st.header("🔎 Insight Explorer")
    explorer_filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="explorer")
    explorer_filtered = [i for i in scraped_insights if all(explorer_filters[k] == "All" or str(i.get(k, "Unknown")) == explorer_filters[k] for k in explorer_filters)]
    results = display_insight_explorer(explorer_filtered)
    if results:
        render_insight_cards(results[:50], model, key_prefix="explorer")

# Tab 3: Brand + Type Trends
with tabs[3]:
    st.header("📈 Trends + Brand Summary")
    display_insight_charts(scraped_insights)
    display_brand_dashboard(scraped_insights)

# Tab 4: Emerging Topics
with tabs[4]:
    st.header("🔥 Emerging Topics")
    render_emerging_topics(detect_emerging_topics(scraped_insights))

# Tab 5: Strategic Tools
with tabs[5]:
    st.header("🧠 Strategic Tools")
    display_spark_suggestions(scraped_insights)
    display_signal_digest(scraped_insights)
    display_impact_heatmap(scraped_insights)
    display_journey_breakdown(scraped_insights)
    display_brand_comparator(scraped_insights)
    display_prd_bundler(scraped_insights)

# Tab 6: Journey Heatmap
with tabs[6]:
    st.header("📺 Journey Heatmap")
    display_journey_heatmap(scraped_insights)
