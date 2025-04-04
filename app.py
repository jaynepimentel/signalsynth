# app.py — Fully fixed with Topic Focus multi-match and strategic filter restructuring

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

@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        st.warning(f"⚠️ Failed to load embedding model: {e}")
        return None

st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth! What Can You Do Here?", expanded=True):
        st.markdown("""
        SignalSynth helps you transform user signals into strategic action.

        **💥 Key Features:**
        - Filter by brand, persona, journey stage, topic, and sentiment
        - Generate PRD, BRD, PRFAQ, or JIRA ticket for any insight
        - Visualize trend shifts and brand sentiment
        - Bundle, clarify, and tag insights
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

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
except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
    st.stop()

# Strategic filter structure
filter_fields = {
    # 📍 Experience
    "Persona": "persona",
    "Journey Stage": "journey_stage",

    # 🧠 Signal Quality
    "Insight Type": "type_tag",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity",
    "Effort Estimate": "effort",

    # 🧭 Strategic Focus
    "Target Brand": "target_brand",
    "Topic Focus": "topic_focus_str",
    "Action Type": "action_type",
    "Opportunity Tag": "opportunity_tag"
}

tabs = st.tabs([
    "📌 Insights",
    "🗺 Journey Heatmap",
    "🧱 Clusters",
    "🔎 Explorer",
    "📈 Trends",
    "🔥 Emerging",
    "🧠 Strategic Tools"
])

# Filter match that supports comma-separated values
def match_filters(insight, active_filters):
    for k in active_filters:
        selected = active_filters[k]
        field_val = str(insight.get(filter_fields[k], "Unknown"))
        if selected == "All":
            continue
        if "," in field_val:
            if selected not in [s.strip() for s in field_val.split(",")]:
                return False
        elif selected != field_val:
            return False
    return True

# Tab 0 — Insights
with tabs[0]:
    st.header("📌 Individual Insights")
    try:
        filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="insights")
        filtered = [i for i in scraped_insights if match_filters(i, filters)]
        model = get_model()
        render_insight_cards(filtered, model, key_prefix="insights")
    except Exception as e:
        st.error(f"❌ Insights tab error: {e}")

# Tab 1 — Journey Map
with tabs[1]:
    st.header("🗺 Journey Heatmap")
    try:
        display_journey_heatmap(scraped_insights)
    except Exception as e:
        st.error(f"❌ Journey Heatmap error: {e}")

# Tab 2 — Clusters
with tabs[2]:
    st.header("🧱 Clustered Insight Mode")
    try:
        model = get_model()
        if model:
            display_clustered_insight_cards(scraped_insights)
        else:
            st.warning("⚠️ Embedding model not available. Skipping clustering.")
    except Exception as e:
        st.error(f"❌ Cluster view error: {e}")

# Tab 3 — Explorer
with tabs[3]:
    st.header("🔎 Insight Explorer")
    try:
        explorer_filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="explorer")
        explorer_filtered = [i for i in scraped_insights if match_filters(i, explorer_filters)]
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
        display_insight_charts(scraped_insights)
        display_brand_dashboard(scraped_insights)
    except Exception as e:
        st.error(f"❌ Trends tab error: {e}")

# Tab 5 — Emerging
with tabs[5]:
    st.header("🔥 Emerging Topics")
    try:
        render_emerging_topics(detect_emerging_topics(scraped_insights))
    except Exception as e:
        st.error(f"❌ Emerging tab error: {e}")

# Tab 6 — Strategic Tools
with tabs[6]:
    st.header("🧠 Strategic Tools")
    try:
        display_spark_suggestions(scraped_insights)
        display_signal_digest(scraped_insights)
        display_impact_heatmap(scraped_insights)
        display_journey_breakdown(scraped_insights)
        display_brand_comparator(scraped_insights)
        display_prd_bundler(scraped_insights)
    except Exception as e:
        st.error(f"❌ Strategic Tools tab error: {e}")
