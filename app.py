# ✅ app.py — SignalSynth full UX with robust Cluster Display
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
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

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
for state_var, default_val in [("current_cluster_index", 0), ("search_query", ""), ("view_mode", "Explorer")]:
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
filters = {key: st.sidebar.selectbox(label, ["All"] + sorted(set(i.get(key, "Unknown") for i in scraped_insights)), key=f"sidebar_{key}")
           for label, key in filter_fields.items()}

st.session_state.search_query = st.text_input("🔍 Search inside insights (optional)", value=st.session_state.search_query).strip().lower()

# Filter + Search
filtered_insights = [i for i in scraped_insights if
                     all(filters[key] == "All" or i.get(key, "Unknown") == filters[key] for key in filter_fields.values()) and
                     (not st.session_state.search_query or st.session_state.search_query in i.get("text", "").lower())]

# Emerging trends
st.subheader("🔥 Emerging Trends & Sentiment Shifts")
spikes, flips, keyword_spikes = get_emerging_signals()
if not (spikes or flips or keyword_spikes):
    st.info("No recent emerging trends detected yet.")

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
    synthesized_clusters = generate_synthesized_insights(paged_insights)
    synthesized_clusters.sort(key=lambda c: c.get("insight_count", 0), reverse=True)

    if synthesized_clusters:
        total_clusters = len(synthesized_clusters)
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅️ Previous"):
                st.session_state.current_cluster_index = max(0, st.session_state.current_cluster_index - 1)

        with col2:
            if st.button("Next ➡️"):
                st.session_state.current_cluster_index = min(total_clusters - 1, st.session_state.current_cluster_index + 1)

        cluster = synthesized_clusters[st.session_state.current_cluster_index]
        st.subheader(f"Cluster {st.session_state.current_cluster_index + 1}/{total_clusters}: {cluster.get('title', 'No Title')}")

        st.markdown(f"**Theme:** {cluster.get('theme', 'No Theme')}")
        st.markdown(f"**Problem Statement:** {cluster.get('problem_statement', 'No Problem Statement')}")

        if cluster.get('diagnostic_only'):
            st.info("🔍 Diagnostic summary cluster (special view)")
            connections = cluster.get('connections', {})
            for connection, items in connections.items():
                st.markdown(f"**Connection:** `{connection}`")
                for item in items:
                    st.markdown(f"- {item['a']} ↔ {item['b']} (Similarity: {item['similarity']})")
        else:
            st.markdown("**Quotes:**")
            for quote in cluster.get('quotes', []):
                st.markdown(quote)

            st.markdown(f"**Insights Count:** {cluster.get('insight_count', 0)}")
            st.markdown(f"**Average Similarity:** {cluster.get('avg_similarity', 'N/A')}")
    else:
        st.info("No valid clusters available.")
else:
    for i in paged_insights:
        text = i.get("text", "")
        highlighted_text = text.replace(st.session_state.search_query, f"**{st.session_state.search_query}**") if st.session_state.search_query else text
        st.markdown(f"- _{highlighted_text}_")

with st.expander("📊 Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(filtered_insights)

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")
