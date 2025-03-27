# cluster_view.py — Clustered Insight Mode with PRD + PRFAQ generation (fixed layout)

import streamlit as st
import os
from slugify import slugify
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import generate_cluster_prd_docx, generate_cluster_prfaq_docx

def display_clustered_insight_cards(insights):
    if not insights:
        st.info("No insights to cluster.")
        return

    st.subheader("🧠 Clustered Insight Themes")
    clusters = cluster_insights(insights)
    cards = generate_synthesized_insights(insights)

    if not cards:
        st.warning("No clusters found.")
        return

    for idx, card in enumerate(cards):
        cluster = clusters[idx]
        with st.container():
            st.markdown(f"### 📌 {card['title']} — {card['brand']}")
            st.markdown(f"**Summary:** {card['summary']}")
            st.markdown(f"**Mentions:** {len(cluster)} | Score Range: {card.get('score_range', '?')}")

            st.markdown("**Example Quotes:**")
            for quote in card["quotes"]:
                st.markdown(quote)

            if card["top_ideas"]:
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            filename = slugify(card['title'])[:64]
            col1, col2 = st.columns(2)

            with col1:
                generate_button = st.button(f"📝 Generate PRD", key=f"btn_prd_{idx}")
                if generate_button:
                    with st.spinner("Creating PRD..."):
                        file_path = generate_cluster_prd_docx(cluster, filename)
                        if os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    "⬇️ Download PRD",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_prd_{idx}"
                                )
                        else:
                            st.error("❌ PRD file was not created.")

            with col2:
                generate_prfaq = st.button(f"📢 Generate PRFAQ", key=f"btn_prfaq_{idx}")
                if generate_prfaq:
                    with st.spinner("Creating PRFAQ..."):
                        file_path = generate_cluster_prfaq_docx(cluster, filename)
                        if os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    "⬇️ Download PRFAQ",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_prfaq_{idx}"
                                )
                        else:
                            st.error("❌ PRFAQ file was not created.")