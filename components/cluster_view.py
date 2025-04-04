# cluster_view.py — Final merged version with advanced metadata, GPT tools, and cache loading

import streamlit as st
import json
import os
import hashlib
from slugify import slugify
from collections import Counter
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import (
    generate_cluster_prd_docx, generate_cluster_prfaq_docx, generate_cluster_brd_docx,
    generate_gpt_doc, generate_multi_signal_prd
)

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Live Shopping": "#BC6FF1", "Search": "#118AB2", "Fulfillment": "#8ECAE6",
    "Returns": "#FFB703", "Discovery": "#90BE6D", "Unclear": "#888",
    "UI": "#58A4B0", "Feature": "#C8553D", "Policy": "#A26769", "Marketplace": "#5FAD56",
    "Buyer": "#38B000", "Seller": "#FF6700", "Collector": "#9D4EDD",
    "Vault": "#5F0F40", "PSA": "#FFB703", "Live": "#1D3557", "Post-Event": "#264653",
    "Canada": "#F72585", "Japan": "#7209B7", "Europe": "#3A0CA3"
}

def badge(label):
    color = BADGE_COLORS.get(label, "#ccc")
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

CACHE_DIR = ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)

@st.cache_data(show_spinner=False)
def load_cached_clusters():
    try:
        with open(".cache/clusters.json", "r", encoding="utf-8") as f1, \
             open(".cache/cards.json", "r", encoding="utf-8") as f2:
            return json.load(f1), json.load(f2)
    except Exception as e:
        st.error(f"❌ Failed to load cluster cache: {e}")
        return [], []

def display_clustered_insight_cards(insights):
    if not insights:
        st.info("No insights to cluster.")
        return

    st.subheader("🧱 Clustered Insight Mode")

    if "clusters_ready" not in st.session_state:
        st.session_state.clusters_ready = False

    if not st.session_state.clusters_ready:
        if st.button("🔍 Load Precomputed Clusters"):
            st.session_state.clusters_ready = True
        else:
            st.info("Click the button above to view grouped insight themes.")
            return

    with st.spinner("Loading cluster summaries..."):
        clusters, cards = load_cached_clusters()

    if not cards or not clusters:
        st.warning("No cluster data available.")
        return

    for idx, card in enumerate(cards[:10]):
        cluster = clusters[idx]
        with st.container():
            st.markdown(f"### 📌 {card['title']} — {card['brand']} ({card.get('theme', 'Theme N/A')})")
            st.markdown(f"**Problem:** {card.get('problem_statement', 'No summary available.')}")
            st.markdown(f"**Persona(s):** {', '.join(card.get('personas', []))} | Effort: {', '.join(card.get('effort_levels', []))} | Sentiments: {', '.join(card.get('sentiments', []))}")
            st.markdown(f"**Mentions:** {len(cluster)} | Score Range: {card.get('score_range', 'N/A')} | Avg Similarity: {card.get('avg_similarity', 'N/A')}")
            st.markdown(f"**Was Reclustered:** {'✅' if card.get('was_reclustered') else '❌'} | Coherent: {'✅' if card.get('coherent') else '❌'}")

            if card.get("opportunity_tags"):
                st.markdown("**🎯 Opportunities:** " + ", ".join(card["opportunity_tags"]))
            if card.get("topic_focus_tags"):
                st.markdown("**🔍 Topics:** " + ", ".join(card["topic_focus_tags"]))

            st.markdown("**📣 Example Quotes:**")
            for quote in card.get("quotes", [])[:3]:
                st.markdown(quote)

            if card.get("top_ideas"):
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            filename = slugify(card['title'])[:64]
            doc_type = st.selectbox("Generate document for this cluster:", ["PRD", "BRD", "PRFAQ"], key=f"cluster_doc_type_{idx}")

            if st.button(f"Generate {doc_type}", key=f"generate_cluster_doc_{idx}"):
                with st.spinner(f"Generating {doc_type}..."):
                    generate_fn = {
                        "PRD": generate_cluster_prd_docx,
                        "BRD": generate_cluster_brd_docx,
                        "PRFAQ": generate_cluster_prfaq_docx
                    }.get(doc_type)
                    if generate_fn:
                        file_path = generate_fn(card, filename)
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    f"⬇️ Download {doc_type}",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_cluster_doc_{idx}"
                                )
                        else:
                            st.error("❌ Document file was not created.")

            st.markdown("---")
