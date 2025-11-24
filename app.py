# app.py — SignalSynth (enhanced UI: Payments/UPI/high-ASP, evidence KPIs, carrier/ISP filters)

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from slugify import slugify

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="SignalSynth", layout="wide")

# ─────────────────────────────────────────────
# Component imports
# ─────────────────────────────────────────────
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.cluster_view import display_clustered_insight_cards
from components.emerging_trends import detect_emerging_topics, render_emerging_topics
from components.journey_heatmap import display_journey_heatmap
from components.insight_explorer import display_insight_explorer
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
from components.floating_filters import render_floating_filters

# ─────────────────────────────────────────────
# Env & model
# ─────────────────────────────────────────────
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    """
    Prefer a local copy if you've saved it (fast/offline); fall back to hub name.
    """
    try:
        from sentence_transformers import SentenceTransformer
        # try local first
        try:
            return SentenceTransformer("models/all-MiniLM-L6-v2")
        except Exception:
            return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        st.warning(f"⚠️ Failed to load embedding model: {e}")
        return None

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def coerce_bool(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if str(value).lower() in {"true", "yes", "1"}:
        return "Yes"
    if str(value).lower() in {"false", "no", "0"}:
        return "No"
    return "Unknown"

def normalize_insight(i, suggestion_cache):
    i["ideas"] = suggestion_cache.get(i.get("text",""), [])
    # Default fields
    i["persona"] = i.get("persona", "Unknown")
    i["journey_stage"] = i.get("journey_stage", "Unknown")
    i["type_tag"] = i.get("type_tag", "Unclassified")
    i["brand_sentiment"] = i.get("brand_sentiment", "Neutral")
    i["clarity"] = i.get("clarity", "Unknown")
    i["effort"] = i.get("effort", "Unknown")
    i["target_brand"] = i.get("target_brand", "Unknown")
    i["action_type"] = i.get("action_type", "Unclear")
    i["opportunity_tag"] = i.get("opportunity_tag", "General Insight")

    # Topic focus safe-list
    if isinstance(i.get("topic_focus"), list):
        i["topic_focus_list"] = sorted({t for t in i["topic_focus"] if isinstance(t, str) and t})
    elif isinstance(i.get("topic_focus"), str) and i["topic_focus"].strip():
        i["topic_focus_list"] = [i["topic_focus"].strip()]
    else:
        i["topic_focus_list"] = []

    # Payments / UPI / High-ASP flags (as Yes/No strings for filtering)
    i["_payment_issue_str"] = coerce_bool(i.get("_payment_issue", False))
    i["_upi_flag_str"] = coerce_bool(i.get("_upi_flag", False))
    i["_high_end_flag_str"] = coerce_bool(i.get("_high_end_flag", False))

    # Carrier, program, customs
    i["carrier"] = (i.get("carrier") or "Unknown").upper() if isinstance(i.get("carrier"), str) else "Unknown"
    i["intl_program"] = (i.get("intl_program") or "Unknown").upper() if isinstance(i.get("intl_program"), str) else "Unknown"
    i["customs_flag_str"] = coerce_bool(i.get("customs_flag", False))

    # Evidence collapse & dates
    i["evidence_count"] = i.get("evidence_count", 1)
    i["last_seen"] = i.get("last_seen") or i.get("_logged_date") or i.get("post_date") or "Unknown"
    return i

def get_field_values(insight, field):
    """
    Return a list of values for a given field to support multiselect filters across
    scalars, lists, and comma-separated strings.
    """
    val = insight.get(field, None)
    if val is None:
        return ["Unknown"]
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val)
    if "," in s:
        return [v.strip() for v in s.split(",") if v.strip()]
    return [s.strip() or "Unknown"]

def match_multiselect_filters(insight, active_filters, filter_fields):
    for label, field in filter_fields.items():
        selected = active_filters.get(field, [])
        if not selected or "All" in selected:
            continue
        values = get_field_values(insight, field)
        if not any(v in selected for v in values):
            return False
    return True

def kpi_chip(label, value, help_text=None):
    with st.container():
        st.metric(label=label, value=value, help=help_text)

# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

st.markdown("""
    <style>
      [data-testid="collapsedControl"] { display: none }
      section[data-testid="stSidebar"] { width: 0px !important; display: none }
      .kpi-row { margin-bottom: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# Onboarding
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth! What’s here now?", expanded=True):
        st.markdown("""
- **New tags & filters:** Payments, UPI, High-ASP, Carrier, International Program, Customs Flag.
- **Evidence collapse:** duplicates merged with `evidence_count` and `last_seen`.
- **Decision Tiles in Clusters:** Each theme has the *Decision, Risk, and Suggested Owner*.
- **Topic Focus** now supports multi-value list filtering.
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

# ─────────────────────────────────────────────
# Data load
# ─────────────────────────────────────────────
try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    try:
        with open("gpt_suggestion_cache.json", "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}

    # Normalize
    normalized = [normalize_insight(i, cache) for i in scraped_insights]

    # KPIs
    total = len(normalized)
    complaints = sum(1 for i in normalized if i.get("brand_sentiment") == "Complaint")
    payments = sum(1 for i in normalized if i.get("_payment_issue_str") == "Yes")
    upi = sum(1 for i in normalized if i.get("_upi_flag_str") == "Yes")
    high_asp = sum(1 for i in normalized if i.get("_high_end_flag_str") == "Yes")
    collapsed_total = len(normalized)  # already post-dedupe from precompute

    st.success(f"✅ Loaded {total} insights")

except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
    st.stop()

# KPI Row
c1, c2, c3, c4, c5 = st.columns(5)
with c1: kpi_chip("All Insights", f"{total:,}")
with c2: kpi_chip("Complaints", f"{complaints:,}")
with c3: kpi_chip("Payments Signals", f"{payments:,}", "Includes payment declines & wire/ACH friction")
with c4: kpi_chip("UPI Mentions", f"{upi:,}", "Seller unpaid-item complaints")
with c5: kpi_chip("High-ASP Flags", f"{high_asp:,}", "Mentions of $1k+, 5k, 10k, etc.")

# ─────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────
filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity",
    "Effort Estimate": "effort",
    "Topic Focus": "topic_focus_list",        # list-aware
    "Action Type": "action_type",
    "Opportunity Tag": "opportunity_tag",
    # new ops/compliance filters:
    "Carrier": "carrier",                     # UPS/USPS/FEDEX/DPD/DHL/Unknown
    "Intl Program": "intl_program",           # ISP/GSP/Unknown
    "Customs Flag": "customs_flag_str",       # Yes/No/Unknown
    # new money-risk filters:
    "Payments Flag": "_payment_issue_str",    # Yes/No/Unknown
    "UPI Flag": "_upi_flag_str",              # Yes/No/Unknown
    "High-ASP Flag": "_high_end_flag_str",    # Yes/No/Unknown
}

# Quick toggles (pills) for exec speed
qt1, qt2, qt3 = st.columns([1,1,1])
with qt1:
    q_pay = st.toggle("💳 Payments only", value=False, help="Show payment declines & wire/ACH friction")
with qt2:
    q_upi = st.toggle("🚫 UPI only", value=False, help="Show seller unpaid-item complaints")
with qt3:
    q_high = st.toggle("💎 High-ASP only", value=False, help="Flagged as high-value context")

# Build quick-filtered base list
quick_filtered = normalized
if q_pay:
    quick_filtered = [i for i in quick_filtered if i.get("_payment_issue_str") == "Yes"]
if q_upi:
    quick_filtered = [i for i in quick_filtered if i.get("_upi_flag_str") == "Yes"]
if q_high:
    quick_filtered = [i for i in quick_filtered if i.get("_high_end_flag_str") == "Yes"]

# ─────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────
tabs = st.tabs([
    "📌 Insights", "🧱 Clusters", "📈 Trends",
    "📺 Journey Heatmap", "🔎 Explorer", "🔥 Emerging", "🧠 Strategic Tools"
])

# 📌 INSIGHTS
with tabs[0]:
    st.header("📌 Individual Insights")
    try:
        filters = render_floating_filters(quick_filtered, filter_fields, key_prefix="insights")
        filtered = [i for i in quick_filtered if match_multiselect_filters(i, filters, filter_fields)]
        model = get_model()
        render_insight_cards(filtered, model, key_prefix="insights")
    except Exception as e:
        st.error(f"❌ Insights tab error: {e}")

# 🧱 CLUSTERS (with Decision Tiles from component)
with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    try:
        model = get_model()
        if model:
            display_clustered_insight_cards(quick_filtered)
        else:
            st.warning("⚠️ Embedding model not available. Skipping clustering.")
    except Exception as e:
        st.error(f"❌ Cluster view error: {e}")

# 📈 TRENDS
with tabs[2]:
    st.header("📈 Trends + Brand Summary")
    try:
        display_insight_charts(quick_filtered)
        display_brand_dashboard(quick_filtered)
    except Exception as e:
        st.error(f"❌ Trends tab error: {e}")

# 📺 HEATMAP
with tabs[3]:
    st.header("📺 Journey Heatmap")
    try:
        display_journey_heatmap(quick_filtered)
    except Exception as e:
        st.error(f"❌ Journey Heatmap error: {e}")

# 🔎 EXPLORER
with tabs[4]:
    st.header("🔎 Insight Explorer")
    try:
        explorer_filters = render_floating_filters(quick_filtered, filter_fields, key_prefix="explorer")
        explorer_filtered = [i for i in quick_filtered if match_multiselect_filters(i, explorer_filters, filter_fields)]
        results = display_insight_explorer(explorer_filtered)
        if results:
            model = get_model()
            render_insight_cards(results[:50], model, key_prefix="explorer")
    except Exception as e:
        st.error(f"❌ Explorer tab error: {e}")

# 🔥 EMERGING
with tabs[5]:
    st.header("🔥 Emerging Topics")
    try:
        render_emerging_topics(detect_emerging_topics(quick_filtered))
    except Exception as e:
        st.error(f"❌ Emerging tab error: {e}")

# 🧠 STRATEGIC
with tabs[6]:
    st.header("🧠 Strategic Tools")
    try:
        display_spark_suggestions(quick_filtered)
        display_signal_digest(quick_filtered)
        display_impact_heatmap(quick_filtered)
        display_journey_breakdown(quick_filtered)
        display_brand_comparator(quick_filtered)
        display_prd_bundler(quick_filtered)
    except Exception as e:
        st.error(f"❌ Strategic Tools tab error: {e}")
