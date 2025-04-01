# cluster_view.py — Enhanced cluster view with GPT tools, bundling, and doc generation
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

# Caching logic
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

    if not cards and os.path.exists(PRECOMPUTED_CLUSTERS):
        try:
            with open(PRECOMPUTED_CLUSTERS, "r", encoding="utf-8") as f:
                data = json.load(f)
                clusters = data.get("clusters")
                cards = data.get("cards")
            st.caption("📦 Loaded precomputed clusters")
        except Exception as e:
            st.warning(f"⚠️ Failed to load precomputed clusters: {e}")

    if not cards:
        with st.spinner("🔄 Clustering and summarizing live..."):
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
            st.markdown(f"**Summary:** {card.get('summary', '(none)')}")

            st.caption(f"Mentions: {card.get('insight_count', len(cluster))} | Score Range: {card.get('score_range', '?')}")

            persona_counts = Counter(i.get("persona", "Unknown") for i in cluster)
            brand_counts = Counter(i.get("target_brand", "Unknown") for i in cluster)
            if persona_counts:
                st.caption("**Persona Breakdown:** " + " | ".join([f"👤 {k}: {v}" for k, v in persona_counts.items()]))
            if brand_counts:
                st.caption("**Brand Mentions:** " + " | ".join([f"🏷️ {k}: {v}" for k, v in brand_counts.items()]))

            # Tag badges
            tags = []
            for tag_field in ["type", "effort_levels", "sentiments", "opportunity_tags", "topic_focus_tags"]:
                values = card.get(tag_field)
                if isinstance(values, list):
                    tags.extend([badge(v) for v in values])
                elif values:
                    tags.append(badge(values))
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

            st.markdown("")

            with st.expander("✨ AI Tools for This Cluster"):
                joined_text = "\n\n".join([i["text"] for i in cluster[:8]])

                if st.button(f"🧼 Clarify This Cluster", key=f"clarify_cluster_{idx}"):
                    with st.spinner("Rewriting for clarity..."):
                        clarified = generate_gpt_doc(
                            f"Rewrite these feedback snippets to clearly summarize the key customer concern:\n\n{joined_text}",
                            "You are rewriting vague customer feedback for clarity."
                        )
                        st.markdown("✅ Clarified Summary:")
                        st.markdown(f"> {clarified}")

                if st.button(f"🏷️ Suggest Tags for Cluster", key=f"tags_cluster_{idx}"):
                    with st.spinner("Suggesting tags..."):
                        tag_summary = generate_gpt_doc(
                            f"Suggest 3–5 product tags or themes that describe these user signals:\n\n{joined_text}",
                            "You are a PM classifying this feedback."
                        )
                        st.info("💡 Suggested Tags:")
                        st.markdown(f"`{tag_summary}`")

                if st.button(f"📦 Generate Combined PRD", key=f"bundle_cluster_prd_{idx}"):
                    path = generate_multi_signal_prd([i["text"] for i in cluster[:8]], filename=f"bundle-cluster-{idx}")
                    if path and os.path.exists(path):
                        with open(path, "rb") as f:
                            st.download_button(
                                "⬇️ Download Cluster PRD",
                                f,
                                file_name=os.path.basename(path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_bundle_prd_{idx}"
                            )

            st.markdown("")

            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button(f"❌ Not relevant", key=f"bad_cluster_{idx}"):
                    st.success("✅ Thanks for the feedback!")

            with col2:
                doc_type = st.selectbox("Generate doc:", ["PRD", "BRD", "PRFAQ"], key=f"doc_type_cluster_{idx}")
                if st.button("📄 Generate", key=f"generate_doc_cluster_{idx}"):
                    filename = f"cluster_{idx}_{card.get('title', 'untitled')[:40].replace(' ', '_')}"
                    with st.spinner(f"Generating {doc_type}..."):
                        if doc_type == "PRD":
                            path = generate_cluster_prd_docx(card, filename)
                        elif doc_type == "BRD":
                            path = generate_cluster_brd_docx(card, filename + "-brd")
                        elif doc_type == "PRFAQ":
                            path = generate_cluster_prfaq_docx(card, filename + "-prfaq")

                        if path and os.path.exists(path):
                            with open(path, "rb") as f:
                                st.download_button(
                                    label=f"⬇️ Download {doc_type}",
                                    data=f,
                                    file_name=os.path.basename(path),
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_cluster_{doc_type}_{idx}"
                                )

            st.markdown("---")
