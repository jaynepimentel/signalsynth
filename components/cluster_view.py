# ✅ cluster_view.py — Updated with safe key access to avoid crashes
import streamlit as st
import os
import json
import hashlib
from slugify import slugify
from collections import Counter
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import (
    generate_cluster_prd_docx,
    generate_cluster_prfaq_docx,
    generate_cluster_brd_docx
)

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Live Shopping": "#BC6FF1", "Search": "#118AB2",
    "Fulfillment": "#8ECAE6", "Returns": "#FFB703", "Discovery": "#90BE6D"
}

def badge(label):
    color = BADGE_COLORS.get(label, "#ccc")
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

CACHE_DIR = ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cluster_cache_key(insights):
    key = hashlib.md5(json.dumps(insights, sort_keys=True).encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"cluster_{key}.json")

def display_clustered_insight_cards(insights):
    if not insights:
        st.info("No insights to cluster.")
        return

    st.subheader("🧠 Clustered Insight Themes")

    cache_file = get_cluster_cache_key(insights)
    clusters, cards = None, None

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                clusters = data.get("clusters")
                cards = data.get("cards")
            st.caption("⚡️ Loaded clusters from cache")
        except Exception as e:
            st.warning(f"⚠️ Failed to load cache: {e}")

    if not clusters or not cards:
        with st.spinner("Clustering and generating summaries..."):
            clusters = cluster_insights(insights)
            cards = generate_synthesized_insights(insights)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"clusters": clusters, "cards": cards}, f, indent=2)
            st.caption("💾 Clusters cached for faster reloads")
        except Exception as e:
            st.warning(f"⚠️ Failed to write cluster cache: {e}")

    if not cards or not clusters:
        st.warning("No clusters found.")
        return

    clusters_per_page = 3
    total_pages = (len(cards) + clusters_per_page - 1) // clusters_per_page
    current_page = st.number_input("📚 Page", min_value=1, max_value=total_pages, value=1, step=1)
    start_idx = (current_page - 1) * clusters_per_page
    end_idx = start_idx + clusters_per_page
    st.caption(f"🔀 Showing clusters {start_idx + 1} to {min(end_idx, len(cards))} of {len(cards)}")

    min_len = min(len(cards), len(clusters))
    for idx, card in enumerate(cards[start_idx:end_idx], start=start_idx):
        if idx >= min_len:
            st.warning(f"⚠️ Cluster index {idx} out of range")
            continue

        cluster = clusters[idx]
        with st.container():
            st.markdown(f"### 📌 {card.get('title', 'Untitled')} — {card.get('brand', 'Unknown')}")
            st.markdown(f"**Problem Statement:** {card.get('problem_statement', '(none)')}")
            st.markdown(f"**Mentions:** {card.get('insight_count', 0)} | Score Range: {card.get('score_range', '?')}")

            persona_counts = Counter(i.get("persona", "Unknown") for i in cluster)
            brand_counts = Counter(i.get("target_brand", "Unknown") for i in cluster)
            if persona_counts:
                persona_text = " | ".join([f"👤 {k}: {v}" for k, v in persona_counts.items()])
                st.caption(f"**Persona Breakdown:** {persona_text}")
            if brand_counts:
                brand_text = " | ".join([f"🏷️ {k}: {v}" for k, v in brand_counts.items()])
                st.caption(f"**Brand Mentions:** {brand_text}")

            tag_fields = ["type_tag", "effort", "journey_stage", "brand_sentiment", "clarity"]
            dominant = {}
            for tag in tag_fields:
                values = [i.get(tag) for i in cluster if i.get(tag)]
                if values:
                    most_common = Counter(values).most_common(1)[0][0]
                    dominant[tag] = most_common

            if dominant:
                st.markdown("**🧷 Cluster Tags:** " + " ".join([badge(v) for v in dominant.values()]), unsafe_allow_html=True)

            if card.get("quotes"):
                st.markdown("**📣 Example Quotes:**")
                for quote in card["quotes"]:
                    st.markdown(quote)

            if card.get("top_ideas"):
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            filename = slugify(card.get('title', f"cluster-{idx}"))[:64]
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("📄 Generate PRD", key=f"generate_prd_{idx}"):
                    with st.spinner("Generating PRD..."):
                        try:
                            prd_path = generate_cluster_prd_docx(cluster, filename + "-prd")
                            if prd_path and os.path.exists(prd_path):
                                with open(prd_path, "rb") as f:
                                    st.download_button("⬇️ Download PRD", f, file_name=os.path.basename(prd_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"cluster_prd_download_{idx}")
                        except Exception as e:
                            st.error(f"PRD generation failed: {e}")

            with col2:
                if st.button("📰 Generate PRFAQ", key=f"generate_prfaq_{idx}"):
                    with st.spinner("Generating PRFAQ..."):
                        try:
                            prfaq_path = generate_cluster_prfaq_docx(cluster, filename + "-prfaq")
                            if prfaq_path and os.path.exists(prfaq_path):
                                with open(prfaq_path, "rb") as f:
                                    st.download_button("⬇️ Download PRFAQ", f, file_name=os.path.basename(prfaq_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"cluster_prfaq_download_{idx}")
                        except Exception as e:
                            st.error(f"PRFAQ generation failed: {e}")

            with col3:
                if st.button("📘 Generate BRD", key=f"generate_brd_{idx}"):
                    with st.spinner("Generating BRD..."):
                        try:
                            brd_path = generate_cluster_brd_docx(cluster, filename + "-brd")
                            if brd_path and os.path.exists(brd_path):
                                with open(brd_path, "rb") as f:
                                    st.download_button("⬇️ Download BRD", f, file_name=os.path.basename(brd_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"cluster_brd_download_{idx}")
                        except Exception as e:
                            st.error(f"BRD generation failed: {e}")

            st.markdown("---")
