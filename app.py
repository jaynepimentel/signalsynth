import os
import json
import streamlit as st
from dotenv import load_dotenv
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.cluster_synthesizer import generate_synthesized_insights
from components.emerging_trends import get_emerging_signals

load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "1"

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📱 SignalSynth: Collectibles Insight Engine")

# Load insights
try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
    st.stop()

# Session state initialization
for state_var, default_val in [("search_query", ""), ("view_mode", "Explorer")]:
    if state_var not in st.session_state:
        st.session_state[state_var] = default_val

# Sidebar filters
st.sidebar.header("Filter by Metadata")
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
filters = {
    key: st.sidebar.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)), key=f"sidebar_{key}")
    for label, key in filter_fields.items()
}

st.session_state.search_query = st.text_input("🔍 Search insights (optional)", value=st.session_state.search_query).strip().lower()

# Apply filtering logic
filtered_insights = [
    i for i in scraped_insights
    if all(filters[key] == "All" or i.get(key, "Unknown") == filters[key] for key in filter_fields.values())
    and (not st.session_state.search_query or st.session_state.search_query in i.get("text", "").lower())
]

# Emerging trends section
st.subheader("🔥 Emerging Trends & Sentiment Shifts")
spikes, flips, keyword_spikes = get_emerging_signals()
if not (spikes or flips or keyword_spikes):
    st.info("No recent emerging trends detected yet.")

st.markdown(f"### 📋 Showing {len(filtered_insights)} filtered insights")

# View mode selection
st.subheader("🧭 Explore Insights")
st.session_state.view_mode = st.radio("View Mode:", ["Explorer", "Clusters", "Raw List"], horizontal=True)

if st.session_state.view_mode == "Explorer":
    display_insight_explorer(filtered_insights[:10])  # Adjust page size if needed
elif st.session_state.view_mode == "Clusters":
    display_clustered_insight_cards(filtered_insights)
else:
    for i in filtered_insights[:10]:  # Adjust page size if needed
        text = i.get("text", "")
        highlighted_text = text.replace(st.session_state.search_query, f"**{st.session_state.search_query}**") if st.session_state.search_query else text
        st.markdown(f"- _{highlighted_text}_")

# Brand dashboard
with st.expander("📊 Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(filtered_insights)

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")