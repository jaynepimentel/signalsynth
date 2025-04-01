# cluster_view.py — Optimized for performance, preserving GPT tools, bundling, and doc generation
import streamlit as st
import os
import json
import hashlib
from collections import Counter
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import (
    generate_cluster_prd_docx,
    generate_cluster_prfaq_docx,
    generate_cluster_brd_docx,
    generate_gpt_doc,
    generate_multi_signal_prd
)

# Visual badge coloring
BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Live Shopping": "#BC6FF1", "Search": "#118AB2",
    "Fulfillment": "#8ECAE6", "Returns": "#FFB703", "Discovery": "#90BE6D",
    "Unclear": "#888", "UI": "#58A4B0", "Feature": "#C8553D", "Policy": "#A26769", "Marketplace": "#5FAD56"
}

def badge(label):
    color = BADGE_COLORS.get(label, "#ccc")
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

CACHE_DIR = ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)

PRECOMPUTED_CLUSTERS = "precomputed_clusters.json"

def get_cluster_cache_key(insights):
    key = hashlib.md5(json.dumps(insights, sort_keys=True).encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"cluster_{key}.json")

@st.cache_data(show_spinner=False)
def load_clusters(insights):
    clusters = cluster_insights(insights)
    cards = generate_synthesized_insights(insights)
    return clusters, cards

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
                clusters, cards = data.get("clusters"), data.get("cards")
            st.caption("⚡️ Loaded from cache")
        except:
            os.remove(cache_file)

    if not clusters or not cards:
        with st.spinner("🔄 Clustering..."):
            clusters, cards = load_clusters(insights)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"clusters": clusters, "cards": cards}, f)

    clusters_per_page = 3
    total_pages = (len(cards) + clusters_per_page - 1) // clusters_per_page
    current_page = st.number_input("📚 Page", 1, total_pages, 1)
    start_idx = (current_page - 1) * clusters_per_page
    end_idx = min(start_idx + clusters_per_page, len(cards))

    st.caption(f"🔀 Showing clusters {start_idx + 1}–{end_idx} of {len(cards)}")

    for idx in range(start_idx, end_idx):
        card, cluster = cards[idx], clusters[idx]

        with st.container():
            st.markdown(f"### 📌 {card.get('title', 'Untitled')} — {card.get('brand', 'Unknown')}")
            st.markdown(f"**Summary:** {card.get('summary', '(none)')}")
            st.caption(f"Mentions: {card.get('insight_count', len(cluster))} | Score Range: {card.get('score_range', '?')}")

            tags = []
            for field in ["type", "effort_levels", "sentiments", "opportunity_tags", "topic_focus_tags"]:
                values = card.get(field)
                tags += [badge(v) for v in values] if isinstance(values, list) else [badge(values)] if values else []
            st.markdown("**🧷 Tags:** " + " ".join(tags), unsafe_allow_html=True)

            if card.get("quotes"):
                st.markdown("**📣 Quotes:**")
                for quote in card["quotes"][:3]:
                    st.markdown(quote)

            if card.get("top_ideas"):
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            with st.expander("✨ AI Tools"):
                texts = "\n\n".join(i["text"] for i in cluster[:8])

                if st.button("🧼 Clarify", key=f"clarify_{idx}"):
                    st.markdown(f"> {generate_gpt_doc(texts, 'Clarify clearly.')}")

                if st.button("🏷️ Suggest Tags", key=f"tags_{idx}"):
                    tags_suggested = generate_gpt_doc(texts, 'Suggest 3–5 tags.')
                    st.info(tags_suggested)

                if st.button("📦 Combined PRD", key=f"bundle_{idx}"):
                    path = generate_multi_signal_prd([i["text"] for i in cluster[:8]], f"bundle-{idx}")
                    if path:
                        with open(path, "rb") as f:
                            st.download_button("⬇️ PRD", f, os.path.basename(path))

            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("❌ Not relevant", key=f"irrelevant_{idx}"):
                    st.success("Feedback noted.")
            with col2:
                doc_type = st.selectbox("Generate:", ["PRD", "BRD", "PRFAQ"], key=f"doc_{idx}")
                if st.button("📄 Generate", key=f"gen_doc_{idx}"):
                    filename = f"cluster_{idx}_{card.get('title', 'untitled')[:40].replace(' ', '_')}"
                    generate_fn = {"PRD": generate_cluster_prd_docx, "BRD": generate_cluster_brd_docx, "PRFAQ": generate_cluster_prfaq_docx}[doc_type]
                    path = generate_fn(card, filename)
                    if path:
                        with open(path, "rb") as f:
                            st.download_button(f"⬇️ {doc_type}", f, os.path.basename(path))

            st.markdown("---")
