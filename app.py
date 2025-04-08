# ✅ Final version of app.py — Offline-safe + merged enhancements

import os
import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from slugify import slugify

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="SignalSynth", layout="wide")

# Component imports
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.emerging_trends import detect_emerging_topics, render_emerging_topics
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

# Embed model (offline-safe)
@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("models/all-MiniLM-L6-v2")
    except Exception as e:
        st.warning(f"\u26a0\ufe0f Failed to load embedding model: {e}")
        return None

# App header
st.title("\ud83d\udce1 SignalSynth: Collectibles Insight Engine")
st.caption(f"\ud83d\udcc5 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# Hide sidebar
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("\ud83e\udde0 Welcome to SignalSynth! What Can You Do Here?", expanded=True):
        st.markdown("""
        SignalSynth helps you transform user signals into strategic action.

        **\ud83d\udca5 Key Features:**
        - Filter by brand, persona, journey stage, topic, and sentiment
        - Generate PRD, BRD, PRFAQ, or JIRA ticket for any insight
        - Visualize trend shifts and brand sentiment
        - Bundle, clarify, and tag insights
        """)
        st.button("\u2705 Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

# Load insights
try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    with open("gpt_suggestion_cache.json", "r", encoding="utf-8") as f:
        cache = json.load(f)

    for i in scraped_insights:
        i["ideas"] = cache.get(i.get("text", ""), [])
        i["persona"] = i.get("persona", "Unknown")
        i["journey_stage"] = i.get("journey_stage", "Unknown")
        i["type_tag"] = i.get("type_tag", "Unclassified")
        i["brand_sentiment"] = i.get("brand_sentiment", "Neutral")
        i["clarity"] = i.get("clarity", "Unknown")
        i["effort"] = i.get("effort", "Unknown")
        i["target_brand"] = i.get("target_brand", "Unknown")
        i["topic_focus_str"] = ", ".join(i.get("topic_focus", [])) if isinstance(i.get("topic_focus"), list) else i.get("topic_focus", "None")
        i["action_type"] = i.get("action_type", "Unclear")
        i["opportunity_tag"] = i.get("opportunity_tag", "General Insight")

    st.success(f"\u2705 Loaded {len(scraped_insights)} insights")

except Exception as e:
    st.error(f"\u274c Failed to load insights: {e}")
    st.stop()

# Filter setup
filter_fields = {
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity",
    "Effort Estimate": "effort",
    "Target Brand": "target_brand",
    "Topic Focus": "topic_focus_str",
    "Action Type": "action_type",
    "Opportunity Tag": "opportunity_tag"
}

def render_multiselect_filters(insights, filter_fields, key_prefix=""):
    filters = {}
    with st.expander("\ud83e\udde0 Advanced Filters", expanded=True):
        field_items = list(filter_fields.items())
        for i in range(0, len(field_items), 3):
            cols = st.columns(min(3, len(field_items[i:i+3])))
            for col, (label, key) in zip(cols, field_items[i:i+3]):
                values = sorted({str(i.get(key, "Unknown")).strip() for i in insights})
                options = ["All"] + values
                default = ["All"]
                if "brand" in key:
                    for v in options:
                        if v.strip().lower() == "ebay":
                            default = [v]
                            break
                filters[key] = col.multiselect(label, options, default=default, key=f"{key_prefix}_filter_{key}")
    return filters

def match_multiselect_filters(insight, active_filters, filter_fields):
    for label, field in filter_fields.items():
        selected = active_filters.get(field, [])
        if not selected or "All" in selected:
            continue
        value = str(insight.get(field, "Unknown")).strip()
        values = [v.strip() for v in value.split(",")] if "," in value else [value]
        if not any(v in selected for v in values):
            return False
    return True

# Tab layout
tabs = st.tabs([
    "\ud83d\udccc Insights", "\ud83d\udec9 Journey Heatmap", "\ud83e\uddf1 Clusters",
    "\ud83d\udd0e Explorer", "\ud83d\udcc8 Trends", "\ud83d\udd25 Emerging", "\ud83e\udde0 Strategic Tools"
])

with tabs[0]:
    st.header("\ud83d\udccc Individual Insights")
    try:
        filters = render_multiselect_filters(scraped_insights, filter_fields, key_prefix="insights")
        filtered = [i for i in scraped_insights if match_multiselect_filters(i, filters, filter_fields)]
        model = get_model()
        render_insight_cards(filtered, model, key_prefix="insights")
    except Exception as e:
        st.error(f"\u274c Insights tab error: {e}")

with tabs[1]:
    st.header("\ud83d\udec9 Journey Heatmap")
    try:
        display_journey_heatmap(scraped_insights)
    except Exception as e:
        st.error(f"\u274c Journey Heatmap error: {e}")

with tabs[2]:
    st.header("\ud83e\uddf1 Clustered Insight Mode")
    try:
        model = get_model()
        if model:
            display_clustered_insight_cards(scraped_insights)
        else:
            st.warning("\u26a0\ufe0f Embedding model not available. Skipping clustering.")
    except Exception as e:
        st.error(f"\u274c Cluster view error: {e}")

with tabs[3]:
    st.header("\ud83d\udd0e Insight Explorer")
    try:
        explorer_filters = render_multiselect_filters(scraped_insights, filter_fields, key_prefix="explorer")
        explorer_filtered = [i for i in scraped_insights if match_multiselect_filters(i, explorer_filters, filter_fields)]
        results = display_insight_explorer(explorer_filtered)
        if results:
            model = get_model()
            render_insight_cards(results[:50], model, key_prefix="explorer")
    except Exception as e:
        st.error(f"\u274c Explorer tab error: {e}")

with tabs[4]:
    st.header("\ud83d\udcc8 Trends + Brand Summary")
    try:
        display_insight_charts(scraped_insights)
        display_brand_dashboard(scraped_insights)
    except Exception as e:
        st.error(f"\u274c Trends tab error: {e}")

with tabs[5]:
    st.header("\ud83d\udd25 Emerging Topics")
    try:
        render_emerging_topics(detect_emerging_topics(scraped_insights))
    except Exception as e:
        st.error(f"\u274c Emerging tab error: {e}")

with tabs[6]:
    st.header("\ud83e\udde0 Strategic Tools")
    try:
        display_spark_suggestions(scraped_insights)
        display_signal_digest(scraped_insights)
        display_impact_heatmap(scraped_insights)
        display_journey_breakdown(scraped_insights)
        display_brand_comparator(scraped_insights)
        display_prd_bundler(scraped_insights)
    except Exception as e:
        st.error(f"\u274c Strategic Tools tab error: {e}")
