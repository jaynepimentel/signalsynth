# cluster_view.py — updated for complete metadata and manager-level cluster support

import streamlit as st
import json
import os
from slugify import slugify
from components.ai_suggester import generate_cluster_prd_docx, generate_cluster_prfaq_docx

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

    for idx, card in enumerate(cards[:10]):  # Limit to 10 clusters to avoid UI overload
        cluster = clusters[idx]
        with st.container():
            st.markdown(f"### 📌 {card['title']} — {card['brand']} ({card.get('theme', 'Theme N/A')})")
            st.markdown(f"**Problem:** {card.get('problem_statement', 'No summary available.')}\n\n")
            st.markdown(f"**Persona(s):** {', '.join(card.get('personas', []))} | Effort: {', '.join(card.get('effort_levels', []))} | Sentiments: {', '.join(card.get('sentiments', []))}")
            st.markdown(f"**Mentions:** {len(cluster)} | Score Range: {card.get('score_range', 'N/A')} | Avg Similarity: {card.get('avg_similarity', 'N/A')}\n")
            st.markdown(f"**Was Reclustered:** {'✅' if card.get('was_reclustered') else '❌'} | Coherent: {'✅' if card.get('coherent') else '❌'}")

            st.markdown("**Example Quotes:**")
            for quote in card.get("quotes", [])[:3]:
                st.markdown(quote)

            if card.get("top_ideas"):
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            filename = slugify(card['title'])[:64]
            doc_type = st.selectbox("Generate document for this cluster:", ["PRD", "PRFAQ"], key=f"cluster_doc_type_{idx}")

            if st.button(f"Generate {doc_type}", key=f"generate_cluster_doc_{idx}"):
                with st.spinner(f"Generating {doc_type}..."):
                    if doc_type == "PRD":
                        file_path = generate_cluster_prd_docx(cluster, filename)
                    elif doc_type == "PRFAQ":
                        file_path = generate_cluster_prfaq_docx(cluster, filename)
                    else:
                        file_path = None

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
