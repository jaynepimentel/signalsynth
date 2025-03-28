# ✅ app.py — SignalSynth full UX without Date Filtering
import os
import json
import streamlit as st
import hashlib
from dotenv import load_dotenv
import pandas as pd
from collections import Counter
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket,
    generate_gpt_doc
)
from components.emerging_trends import get_emerging_signals

load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "1"
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📱 SignalSynth: Collectibles Insight Engine")

try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
    st.stop()

# Session state initialization
for state_var, default_val in [("cached_ideas", {}), ("search_query", ""), ("view_mode", "Explorer"), ("power_mode", False)]:
    if state_var not in st.session_state:
        st.session_state[state_var] = default_val

# Filters setup
filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Effort Estimate": "effort",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity",
    "Opportunity Tag": "opportunity_tag"
}

mobile_filters_expanded = st.checkbox("🛍 Show Filters Inline (Mobile Friendly)", value=False)
if mobile_filters_expanded:
    st.markdown("### 🔎 Filter Insights")
    filters = {key: st.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)), key=f"mobile_{key}")
               for label, key in filter_fields.items()}
else:
    st.sidebar.header("Filter by Metadata")
    filters = {key: st.sidebar.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)), key=f"sidebar_{key}")
               for label, key in filter_fields.items()}

active_filters = [(label, val) for label, key in filter_fields.items() if (val := filters[key]) != "All"]
if active_filters:
    st.markdown("#### 🔖 Active Filters:")
    cols = st.columns(len(active_filters))
    for idx, (label, val) in enumerate(active_filters):
        with cols[idx]:
            st.markdown(f"`{label}: {val}`")

st.session_state.search_query = st.text_input("🔍 Search inside insights (optional)", value=st.session_state.search_query).strip().lower()

# Emerging trends
st.subheader("🔥 Emerging Trends & Sentiment Shifts")
try:
    spikes, flips, keyword_spikes = get_emerging_signals()
except Exception as e:
    spikes, flips, keyword_spikes = {}, {}, {}
    st.warning(f"⚠️ Failed to detect trends: {e}")

if not (spikes or flips or keyword_spikes):
    st.info("No recent emerging trends detected yet.")

# Filter + Search without date logic
filtered_insights = [i for i in scraped_insights if
                     all(filters[key] == "All" or i.get(key, "Unknown") == filters[key] for key in filter_fields.values()) and
                     (not st.session_state.search_query or st.session_state.search_query in i.get("text", "").lower())]

st.markdown(f"### 📋 Showing {len(filtered_insights)} filtered insights")

# Pagination
page_size = 10
max_page = max(1, len(filtered_insights) // page_size + (len(filtered_insights) % page_size > 0))
page = st.number_input("Page", min_value=1, max_value=max_page, value=1)
start_idx, end_idx = (page - 1) * page_size, page * page_size
paged_insights = filtered_insights[start_idx:end_idx]

# View mode selection
st.subheader("🧭 Explore Insights")
st.session_state.view_mode = st.radio("View Mode:", ["Explorer", "Clusters", "Raw List"], horizontal=True)

if st.session_state.view_mode == "Explorer":
    display_insight_explorer(paged_insights)
elif st.session_state.view_mode == "Clusters":
    display_clustered_insight_cards(paged_insights)
else:
    for i in paged_insights:
        text = i.get("text", "")
        highlighted_text = text.replace(st.session_state.search_query, f"**{st.session_state.search_query}**") if st.session_state.search_query else text
        st.markdown(f"- _{highlighted_text}_")

with st.expander("📊 Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(filtered_insights)

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")
