# app.py — Final merged version with enhancements, intro, journey heatmap, live OpenAI fallback
import os
import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from slugify import slugify
from sentence_transformers import SentenceTransformer, util

from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.emerging_themes import detect_emerging_topics, render_emerging_topics
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

load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

# Embedding model with caching
@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model.to("cpu")

model = get_model()

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

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

# Load precomputed insights + cached GPT suggestions
try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    with open("gpt_suggestion_cache.json", "r", encoding="utf-8") as f:
        cache = json.load(f)
    for i in scraped_insights:
        i["ideas"] = cache.get(i.get("text", ""), [])
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
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

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800"
}

def badge(label, color):
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

TABS = [
    "📌 Insights", "🧱 Clusters", "🔎 Explorer", "📈 Trends",
    "🔥 Emerging", "🧠 Strategic Tools", "📺 Journey Heatmap"
]
tabs = st.tabs(TABS)

# Tab 0: Insights Explorer with enhancements
with tabs[0]:
    from components.enhanced_insight_view import render_insight_cards
    st.header("📌 Individual Insights")
    filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="insights")
    filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]
    render_insight_cards(filtered, model)

# Tab 1: Clustered Insights
with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    display_clustered_insight_cards(scraped_insights)

# Tab 2: Keyword Explorer
with tabs[2]:
    st.header("🔎 Insight Explorer")
    results = display_insight_explorer(scraped_insights)
    if results:
        render_insight_cards(results[:50], model)

# Tab 3: Trends
with tabs[3]:
    st.header("📈 Trends + Brand Summary")
    display_insight_charts(scraped_insights)
    display_brand_dashboard(scraped_insights)

# Tab 4: Emerging Topics
with tabs[4]:
    st.header("🔥 Emerging Topics")
    trends = detect_emerging_topics(scraped_insights)
    render_emerging_topics(trends)

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
