# app.py — SignalSynth: Fully Enhanced Version (Filters + GPT + Clusters + Downloads + Pagination)

import os
import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_explorer import display_insight_explorer
from components.cluster_synthesizer import generate_synthesized_insights
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_jira_bug_ticket
)
from components.emerging_trends import get_emerging_signals

# Load environment
load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "1"
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📱 SignalSynth: Collectibles Insight Engine")

# Load data
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

# Date Filter
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

# Filter UI
filter_fields = {
    "Effort Estimate": "effort",
    "Insight Type": "type_tag",
    "Persona": "persona",
    "Target Brand": "target_brand",
    "Brand Sentiment": "brand_sentiment",
    "Journey Stage": "journey_stage",
    "Clarity": "clarity"
}
mobile_filters_expanded = st.checkbox("🛍 Show Filters Inline (Mobile Friendly)", value=False)
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

# Trend detection
st.subheader("🔥 Emerging Trends & Sentiment Shifts")
try:
    spikes, flips, keyword_spikes = get_emerging_signals()
except ValueError:
    spikes, flips = get_emerging_signals()
    keyword_spikes = {}

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

# Filter insights
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

st.markdown(f"### 📋 Showing {len(filtered_insights)} filtered insights")

# Pagination
page_size = 10
max_page = max(1, len(filtered_insights) // page_size + int(len(filtered_insights) % page_size > 0))
page = st.number_input("Page", min_value=1, max_value=max_page, value=1)
start_idx = (page - 1) * page_size
end_idx = start_idx + page_size
paged_insights = filtered_insights[start_idx:end_idx]

# View mode
st.subheader("🧭 Explore Insights")
view_mode = st.radio("View Mode:", ["Explorer", "Clusters", "Raw List"], horizontal=True)

if view_mode == "Explorer":
    display_insight_explorer(paged_insights)
elif view_mode == "Clusters":
    st.subheader("🧠 Clustered Insights")
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
            if st.button("Generate PRD", key=f"prd_{i['text'][:30]}"):
                prd_bytes = generate_prd_docx(i['text'])
                st.download_button("Download PRD", prd_bytes, file_name="insight_prd.docx")
        with col2:
            if st.button("Generate BRD", key=f"brd_{i['text'][:30]}"):
                brd_bytes = generate_brd_docx(i['text'])
                st.download_button("Download BRD", brd_bytes, file_name="insight_brd.docx")
        with col3:
            if st.button("Generate JIRA", key=f"jira_{i['text'][:30]}"):
                _ = generate_jira_bug_ticket(i['text'])
                st.success("JIRA ticket generated!")

# Brand summary
with st.expander("📊 Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(filtered_insights)

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")
