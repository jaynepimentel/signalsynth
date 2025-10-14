# cluster_view.py — robust cluster view with atomic cache and mismatch guards

import streamlit as st
import json
import os
import hashlib
from datetime import datetime, timedelta
from components.cluster_synthesizer import generate_synthesized_insights, cluster_insights
from components.ai_suggester import (
    generate_cluster_prd_docx, generate_cluster_prfaq_docx, generate_cluster_brd_docx
)

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Live Shopping": "#BC6FF1", "Search/Relevancy": "#118AB2", "Fulfillment": "#8ECAE6",
    "Returns/Policy": "#FFB703", "Discovery": "#90BE6D", "Unclear": "#888",
    "UI": "#58A4B0", "Feature": "#C8553D", "Policy": "#A26769", "Marketplace": "#5FAD56",
    "Vault": "#5F0F40", "Pop Report": "#636E72", "Payments": "#6C5CE7", "UPI": "#D63031",
}

def badge(label):
    color = BADGE_COLORS.get(label, "#ccc")
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

CACHE_DIR = ".cache"
CACHE_FILE = os.path.join(CACHE_DIR, "clusters_cards.json")
CLUSTER_CACHE_TTL_DAYS = int(os.getenv("CLUSTER_CACHE_TTL", "7"))
os.makedirs(CACHE_DIR, exist_ok=True)

def _is_expired(path, ttl_days):
    if not os.path.exists(path): return True
    last_modified = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - last_modified) > timedelta(days=ttl_days)

def _atomic_save(data, path):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _load_cache():
    if not os.path.exists(CACHE_FILE): return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.info(f"⚠️ Cache unreadable, will rebuild: {e}")
        return None

def _should_rebuild(payload):
    if payload is None: return True
    if _is_expired(CACHE_FILE, CLUSTER_CACHE_TTL_DAYS): return True
    # Basic schema check
    if not isinstance(payload, dict): return True
    clusters = payload.get("clusters") or []
    cards = payload.get("cards") or []
    # Rebuild if lengths are zero or radically mismatched
    if not clusters or not cards: return True
    if abs(len(clusters) - len(cards)) > max(2, 0.25*max(len(clusters), len(cards))):
        return True
    return False

def _rebuild_cache(insights):
    # Compute both from the same input to keep them aligned
    clusters = cluster_insights(insights)
    cards = generate_synthesized_insights(insights)
    data = {"clusters": clusters, "cards": cards, "built_at": datetime.now().isoformat()}
    _atomic_save(data, CACHE_FILE)
    return data

def display_clustered_insight_cards(insights):
    if not insights:
        st.info("No insights to cluster.")
        return

    st.subheader("🧱 Clustered Insight Mode")

    # Manual toggle to (re)build clusters
    left, right = st.columns([1,1])
    with left:
        rebuild = st.button("🔄 Rebuild Clusters Now")
    with right:
        clear_cache = st.button("🧹 Clear Cluster Cache")

    if clear_cache:
        try:
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
                st.success("Cache cleared.")
        except Exception as e:
            st.error(f"Could not clear cache: {e}")

    payload = _load_cache()
    if rebuild or _should_rebuild(payload):
        with st.spinner("Generating cluster groups…"):
            payload = _rebuild_cache(insights)
            st.success("Clusters generated.")

    clusters = payload.get("clusters", []) if payload else []
    cards = payload.get("cards", []) if payload else []

    if not cards or not clusters:
        st.warning("No cluster data available.")
        return

    # Iterate safely over both
    n = min(len(cards), len(clusters))
    st.caption(f"Showing {n} clusters (of cards={len(cards)}, groups={len(clusters)})")

    for idx in range(n):
        card = cards[idx]
        cluster = clusters[idx]
        with st.container():
            st.markdown(f"### 📌 {card.get('title','Untitled')} — {card.get('brand','Unknown')} ({card.get('theme','N/A')})")
            st.markdown(f"**Problem:** {card.get('problem_statement', 'No summary available.')}")

            personas = ", ".join(card.get('personas', []) or [])
            efforts  = ", ".join(card.get('effort_levels', []) or [])
            sents    = ", ".join(card.get('sentiments', []) or [])
            st.markdown(f"**Persona(s):** {personas or '—'} | Effort: {efforts or '—'} | Sentiments: {sents or '—'}")

            st.markdown(f"**Mentions:** {len(cluster)} | Score Range: {card.get('score_range','N/A')} | Avg Similarity: {card.get('avg_similarity','N/A')}")
            st.markdown(f"**Was Reclustered:** {'✅' if card.get('was_reclustered') else '❌'} | Coherent: {'✅' if card.get('coherent') else '❌'}")

            if card.get("opportunity_tags"):
                st.markdown("**🎯 Opportunities:** " + ", ".join(card["opportunity_tags"]))
            if card.get("topic_focus_tags"):
                st.markdown("**🔍 Topics:** " + ", ".join(card["topic_focus_tags"]))

            quotes = card.get("quotes") or []
            if quotes:
                st.markdown("**📣 Example Quotes:**")
                for quote in quotes[:3]:
                    st.markdown(quote)

            ideas = card.get("top_ideas") or []
            if ideas:
                st.markdown("**💡 Top Suggestions:**")
                for idea in ideas:
                    st.markdown(f"- {idea}")

            doc_options = ["PRD", "BRD", "PRFAQ"]
            doc_type = st.selectbox(
                "Generate document for this cluster:",
                doc_options,
                key=f"cluster_doc_type_{idx}"
            )

            if st.button(f"Generate {doc_type}", key=f"generate_cluster_doc_{idx}"):
                with st.spinner(f"Generating {doc_type}..."):
                    fn = {
                        "PRD": generate_cluster_prd_docx,
                        "BRD": generate_cluster_brd_docx,
                        "PRFAQ": generate_cluster_prfaq_docx
                    }.get(doc_type)
                    if fn:
                        filename = (card.get('title') or 'cluster')[:64]
                        file_path = fn(card, filename)
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
