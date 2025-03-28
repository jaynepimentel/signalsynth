# cluster_view.py — Cluster UI with correct doc routing and full PRD/BRD/PRFAQ support

import streamlit as st
import os
from slugify import slugify
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import (
    generate_cluster_prd_docx,
    generate_cluster_prfaq_docx,
    generate_cluster_brd_docx
)

def display_clustered_insight_cards(insights):
    if not insights:
        st.info("No insights to cluster.")
        return

    st.subheader("🧠 Clustered Insight Themes")

    with st.spinner("Clustering and generating summaries..."):
        clusters = cluster_insights(insights)
        cards = generate_synthesized_insights(insights)

    if not cards:
        st.warning("No clusters found.")
        return

    for idx, card in enumerate(cards):
        cluster = clusters[idx]
        with st.container():
            st.markdown(f"### 📌 {card['title']} — {card['brand']}")
            st.markdown(f"**Problem Statement:** {card.get('problem_statement', '(none)')}")
            st.markdown(f"**Mentions:** {card['insight_count']} | Score Range: {card.get('score_range', '?')}")
            st.markdown(f"**Personas:** {', '.join(card.get('personas', []))}")
            st.markdown(f"**Effort Levels:** {', '.join(card.get('effort_levels', []))}")

            if card.get("quotes"):
                st.markdown("**📣 Example Quotes:**")
                for quote in card["quotes"]:
                    st.markdown(quote)

            if card.get("top_ideas"):
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            filename = slugify(card['title'])[:64]
            col1, col2, col3 = st.columns(3)

            with col1:
                try:
                    prd_path = generate_cluster_prd_docx(cluster, filename + "-prd")
                    if prd_path and os.path.exists(prd_path):
                        with open(prd_path, "rb") as f:
                            st.download_button(
                                "📄 Download PRD",
                                f,
                                file_name=os.path.basename(prd_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"cluster_prd_{idx}"
                            )
                except Exception as e:
                    st.error(f"PRD generation failed: {e}")

            with col2:
                try:
                    prfaq_path = generate_cluster_prfaq_docx(cluster, filename + "-prfaq")
                    if prfaq_path and os.path.exists(prfaq_path):
                        with open(prfaq_path, "rb") as f:
                            st.download_button(
                                "📰 Download PRFAQ",
                                f,
                                file_name=os.path.basename(prfaq_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"cluster_prfaq_{idx}"
                            )
                except Exception as e:
                    st.error(f"PRFAQ generation failed: {e}")

            with col3:
                try:
                    brd_path = generate_cluster_brd_docx(cluster, filename + "-brd")
                    if brd_path and os.path.exists(brd_path):
                        with open(brd_path, "rb") as f:
                            st.download_button(
                                "📘 Download BRD",
                                f,
                                file_name=os.path.basename(brd_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"cluster_brd_{idx}"
                            )
                except Exception as e:
                    st.error(f"BRD generation failed: {e}")

            st.markdown("---")
