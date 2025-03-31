# ✅ cluster_view.py — Streamlit-safe cluster explorer with robust cache + metadata display + feedback
import streamlit as st
import os
import json
import hashlib
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
            st.caption("⚡️ Loaded clusters from local cache")
        except Exception as e:
            st.warning(f"⚠️ Failed to load cluster cache: {e}")
            os.remove(cache_file)
            clusters, cards = None, None

    if not cards and os.path.exists(PRECOMPUTED_CLUSTERS):
        try:
            with open(PRECOMPUTED_CLUSTERS, "r", encoding="utf-8") as f:
                data = json.load(f)
                clusters = data.get("clusters")
                cards = data.get("cards")
            st.caption("📦 Loaded precomputed clusters")
        except Exception as e:
            st.warning(f"⚠️ Failed to load precomputed clusters: {e}")
            clusters, cards = None, None

    if not cards:
        with st.spinner("Clustering and summarizing live..."):
            cards = generate_synthesized_insights(insights)
            clusters = cluster_insights(insights)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"clusters": clusters, "cards": cards}, f, indent=2)
            st.caption("💾 Saved cluster cache")
        except Exception as e:
            st.warning(f"⚠️ Failed to write cluster cache: {e}")

    if not cards:
        st.warning("No clusters found or model unavailable.")
        return

    clusters_per_page = 3
    total_pages = (len(cards) + clusters_per_page - 1) // clusters_per_page
    current_page = st.number_input("📚 Page", min_value=1, max_value=total_pages, value=1, step=1)
    start_idx = (current_page - 1) * clusters_per_page
    end_idx = start_idx + clusters_per_page
    st.caption(f"🔀 Showing clusters {start_idx + 1} to {min(end_idx, len(cards))} of {len(cards)}")

    for idx, card in enumerate(cards[start_idx:end_idx], start=start_idx):
        cluster = clusters[idx] if clusters and idx < len(clusters) else []

        with st.container():
            st.markdown(f"### 📌 {card.get('title', 'Untitled')} — {card.get('brand', 'Unknown')}")
            st.markdown(f"**Problem Statement:** {card.get('problem_statement', '(none)')}")

            if card.get("diagnostic_only"):
                st.info("🔍 Diagnostic summary cluster (special view)")
                connections = card.get("connections", {})
                for connection, items in connections.items():
                    st.markdown(f"**Connection:** `{connection}`")
                    for item in items:
                        st.markdown(f"- {item['a']} ↔ {item['b']} (Similarity: {item['similarity']})")
                continue

            st.markdown(f"**Mentions:** {card.get('insight_count', 0)} | Score Range: {card.get('score_range', '?')}")

            persona_counts = Counter(i.get("persona", "Unknown") for i in cluster)
            brand_counts = Counter(i.get("target_brand", "Unknown") for i in cluster)
            if persona_counts:
                persona_text = " | ".join([f"👤 {k}: {v}" for k, v in persona_counts.items()])
                st.caption(f"**Persona Breakdown:** {persona_text}")
            if brand_counts:
                brand_text = " | ".join([f"🏷️ {k}: {v}" for k, v in brand_counts.items()])
                st.caption(f"**Brand Mentions:** {brand_text}")

            tags = []
            for tag in ["type", "effort_levels", "sentiments", "opportunity_tags"]:
                values = card.get(tag)
                if isinstance(values, list):
                    tags.extend([badge(v) for v in values])
                elif values:
                    tags.append(badge(values))

            # Add new tag fields
            if card.get("topic_focus_tags"):
                tags.extend([badge(t) for t in card["topic_focus_tags"]])
            if card.get("action_type_distribution"):
                tags.extend([badge(t) for t in card["action_type_distribution"].keys()])
            if card.get("mentions_competitor"):
                tags.extend([badge(f"⚔ {c.title()}") for c in card["mentions_competitor"]])

            if tags:
                st.markdown("**🧷 Cluster Tags:** " + " ".join(tags), unsafe_allow_html=True)

            if card.get("quotes"):
                st.markdown("**📣 Example Quotes:**")
                for quote in card["quotes"]:
                    st.markdown(quote)

            if card.get("top_ideas"):
                st.markdown("**💡 Top Suggestions:**")
                for idea in card["top_ideas"]:
                    st.markdown(f"- {idea}")

            if st.button(f"❌ This cluster isn't relevant (#{idx+1})", key=f"bad_cluster_{idx}"):
                st.success("✅ Thanks for the feedback! We'll use this to improve clustering logic.")

            st.markdown("---")
