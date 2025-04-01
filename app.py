import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import Counter
from slugify import slugify
from datetime import datetime
from sentence_transformers import SentenceTransformer, util
import torch

st.set_page_config(page_title="SignalSynth", layout="wide")

# Load embedding model with caching
@st.cache_resource(show_spinner="Loading sentence transformer model...")
def get_embedding_model():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    model = model.to(torch.device("cpu"))
    return model

model = get_embedding_model()

# Component imports
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.emerging_themes import detect_emerging_topics, render_emerging_topics
from components.floating_filters import render_floating_filters
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket,
    generate_gpt_doc,
    generate_multi_signal_prd
)
from components.strategic_tools import (
    display_signal_digest,
    display_journey_breakdown,
    display_brand_comparator,
    display_impact_heatmap,
    display_prd_bundler,
    display_spark_suggestions
)
from components.journey_heatmap import display_journey_heatmap

# App setup
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

st.title("📱 SignalSynth: Collectibles Insight Engine")
st.caption(f"🗕️ Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# Hide sidebar
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

# Intro guide
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth!", expanded=True):
        st.markdown("""
        SignalSynth transforms user signals into actionable insights.
        - Filter insights by multiple criteria
        - Generate strategic documents (PRD, BRD, PRFAQ, JIRA)
        - Explore trends, clusters, and emerging themes
        """)
        st.button("✅ Got it", on_click=lambda: st.session_state.update({"show_intro": False}))

# Load insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} insights")
else:
    st.error("❌ Insights file missing.")
    st.stop()

filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Effort Estimate": "effort",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity"
}

# Tabs
TABS = [
    "📌 Insights", "🧱 Clusters", "🔎 Explorer", "📈 Trends",
    "🔥 Emerging", "🧠 Strategic Tools", "📺 Journey Heatmap"
]
tabs = st.tabs(TABS)

# Tab: Individual Insights
with tabs[0]:
    st.header("📌 Individual Insights")
    filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="insights")
    filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]
    display_insight_explorer(filtered)

# Tab: Clusters
with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    display_clustered_insight_cards(scraped_insights)

# Tab: Explorer
with tabs[2]:
    st.header("🔎 Insight Explorer")
    filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="explorer")
    explorer_filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]
    display_insight_explorer(explorer_filtered[:50])

# Tab: Trends
with tabs[3]:
    st.header("📈 Trends + Brand Summary")
    display_insight_charts(scraped_insights)
    display_brand_dashboard(scraped_insights)

# Tab: Emerging Topics
with tabs[4]:
    st.header("🔥 Emerging Topics")
    trends = detect_emerging_topics(scraped_insights)
    render_emerging_topics(trends)

# Tab: Strategic Tools
with tabs[5]:
    st.header("🧠 Strategic Tools")
    display_spark_suggestions(scraped_insights)
    display_signal_digest(scraped_insights)
    display_impact_heatmap(scraped_insights)
    display_journey_breakdown(scraped_insights)
    display_brand_comparator(scraped_insights)
    display_prd_bundler(scraped_insights)

# Tab: Journey Heatmap
with tabs[6]:
    st.header("📺 Journey Heatmap")
    display_journey_heatmap(scraped_insights)
