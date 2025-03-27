import streamlit as st
import os
from slugify import slugify
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import generate_cluster_prd_docx

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
        with st.expander(f"📌 {card['title']} — {card['brand']}"):
            st.markdown(f"**Summary:** {card['summary']}")
            st.markdown(f"**Mentions:** {len(cluster)} | Score Range: {card.get('score_range', '?')}\n")

            st.markdown("**Example Quotes:**")
            for quote in card["quotes"]:
                st.markdown(quote)

            if card["top_ideas"]:
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            if st.button(f"📝 Generate PRD for this cluster", key=f"cluster_prd_{idx}"):
                with st.spinner("Generating PRD from cluster..."):
                    filename = slugify(card['title'])[:64]
                    file_path = generate_cluster_prd_docx(cluster, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                "⬇️ Download Cluster PRD",
                                f,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_cluster_prd_{idx}"
                            )
