# components/cluster_view.py — robust cluster view (precomputed-first, atomic cache, mismatch guards)

import os
import json
import tempfile
from datetime import datetime, timedelta
import streamlit as st

from components.cluster_synthesizer import cluster_insights, generate_synthesized_insights
from components.ai_suggester import (
    generate_cluster_prd_docx,
    generate_cluster_prfaq_docx,
    generate_cluster_brd_docx,
)

# ---------- Styling (kept minimal) ----------
BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Live Shopping": "#BC6FF1", "Search/Relevancy": "#118AB2", "Fulfillment": "#8ECAE6",
    "Returns/Policy": "#FFB703", "Discovery": "#90BE6D",
    "UI": "#58A4B0", "Feature": "#C8553D", "Policy": "#A26769", "Marketplace": "#5FAD56",
    "Vault": "#5F0F40", "Pop Report": "#636E72", "Payments": "#6C5CE7", "UPI": "#D63031",
}

def badge(label: str) -> str:
    color = BADGE_COLORS.get(label, "#ccc")
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

# ---------- Cache & artifacts ----------
CACHE_DIR = os.getenv("SS_CACHE_DIR", os.path.join(tempfile.gettempdir(), ".cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "clusters_cards.json")
CLUSTER_CACHE_TTL_DAYS = int(os.getenv("CLUSTER_CACHE_TTL", "7"))

# Precomputed artifact committed to the repo (recommended on Cloud)
PRECOMPUTED_PATH = "precomputed_clusters.json"


# ---------- Helpers ----------
def _is_expired(path: str, days: int) -> bool:
    if not os.path.exists(path):
        return True
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime) > timedelta(days=days)

def _atomic_save(data: dict, path: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _valid(payload: dict | None) -> bool:
    if not payload or not isinstance(payload, dict):
        return False
    clusters = payload.get("clusters") or []
    cards = payload.get("cards") or []
    if not clusters or not cards:
        return False
    # tolerate tiny drift; hard guard on big mismatches
    if abs(len(clusters) - len(cards)) > max(2, 0.25 * max(len(clusters), len(cards))):
        return False
    return True

def _load_cache() -> dict | None:
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _load_precomputed() -> dict | None:
    if not os.path.exists(PRECOMPUTED_PATH):
        return None
    try:
        with open(PRECOMPUTED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if _valid(data) else None
    except Exception:
        return None

def _rebuild_from_insights(insights: list[dict]) -> dict:
    # Only call this locally (embeddings available). On Cloud, prefer precomputed.
    clusters = cluster_insights(insights)
    cards = generate_synthesized_insights(insights)
    data = {"clusters": clusters, "cards": cards, "built_at": datetime.now().isoformat()}
    _atomic_save(data, CACHE_FILE)
    return data


# ---------- Public UI ----------
def display_clustered_insight_cards(insights: list[dict]) -> None:
    st.subheader("🧱 Clustered Insight Mode")

    if not insights:
        st.info("No insights to cluster.")
        return

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        rebuild = st.button("🔄 Rebuild (local compute)")
    with col2:
        clear = st.button("🧹 Clear Cache")

    if clear:
        try:
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            st.success("Cluster cache cleared.")
        except Exception as e:
            st.error(f"Could not clear cache: {e}")

    # 1) Try cache (fast path)
    payload = _load_cache()
    if payload and not _is_expired(CACHE_FILE, CLUSTER_CACHE_TTL_DAYS) and _valid(payload):
        clusters, cards = payload["clusters"], payload["cards"]
    else:
        # 2) Try precomputed artifact (recommended for Streamlit Cloud)
        pc = _load_precomputed()
        if pc:
            clusters, cards = pc["clusters"], pc["cards"]
            # also refresh cache for later interactions
            _atomic_save(pc, CACHE_FILE)
        else:
            # 3) Last resort: compute now (local dev)
            if not rebuild:
                st.info(
                    "No valid cluster cache found. "
                    "Commit **precomputed_clusters.json** or click **Rebuild (local compute)** "
                    "when running locally with embeddings."
                )
                return
            with st.spinner("Generating clusters from current insights…"):
                payload = _rebuild_from_insights(insights)
                clusters, cards = payload["clusters"], payload["cards"]

    # Final safety: sync lengths and guard empty
    n = min(len(cards), len(clusters))
    if n == 0:
        st.warning("No cluster data available.")
        return
    if n < len(cards) or n < len(clusters):
        st.info(f"⚠️ Mismatch detected: trimming to {n} aligned items.")
        cards, clusters = cards[:n], clusters[:n]

    st.caption(f"Showing {n} clusters")

    # Render cards
    for idx in range(n):
        card = cards[idx]
        cluster = clusters[idx]

        with st.container():
            st.markdown(
                f"### 📌 {card.get('title','Untitled')} — {card.get('brand','Unknown')} "
                f"({card.get('theme','N/A')})"
            )
            st.markdown(f"**Problem:** {card.get('problem_statement', 'No summary available.')}")

            personas = ", ".join(card.get("personas", []) or [])
            efforts = ", ".join(card.get("effort_levels", []) or [])
            sents = ", ".join(card.get("sentiments", []) or [])
            st.markdown(
                f"**Persona(s):** {personas or '—'} | "
                f"Effort: {efforts or '—'} | "
                f"Sentiments: {sents or '—'}"
            )

            st.markdown(
                f"**Mentions:** {len(cluster)} | "
                f"Score Range: {card.get('score_range','N/A')} | "
                f"Avg Similarity: {card.get('avg_similarity','N/A')}"
            )
            st.markdown(
                f"**Was Reclustered:** {'✅' if card.get('was_reclustered') else '❌'} | "
                f"Coherent: {'✅' if card.get('coherent') else '❌'}"
            )

            if card.get("opportunity_tags"):
                st.markdown("**🎯 Opportunities:** " + ", ".join(card["opportunity_tags"]))
            if card.get("topic_focus_tags"):
                st.markdown("**🔍 Topics:** " + ", ".join(card["topic_focus_tags"]))

            quotes = card.get("quotes") or []
            if quotes:
                st.markdown("**📣 Example Quotes:**")
                for q in quotes[:3]:
                    st.markdown(q)

            ideas = card.get("top_ideas") or []
            if ideas:
                st.markdown("**💡 Top Suggestions:**")
                for idea in ideas:
                    st.markdown(f"- {idea}")

            # Doc generation
            doc_type = st.selectbox(
                "Generate document for this cluster:",
                ["PRD", "BRD", "PRFAQ"],
                key=f"doc_{idx}",
            )
            if st.button(f"Generate {doc_type}", key=f"gen_{idx}"):
                fn = {
                    "PRD": generate_cluster_prd_docx,
                    "BRD": generate_cluster_brd_docx,
                    "PRFAQ": generate_cluster_prfaq_docx,
                }[doc_type]
                filename = (card.get("title") or "cluster")[:64]
                with st.spinner(f"Generating {doc_type}…"):
                    path = fn(card, filename)
                    if path and os.path.exists(path):
                        with open(path, "rb") as f:
                            st.download_button(
                                f"⬇️ Download {doc_type}",
                                f,
                                file_name=os.path.basename(path),
                                key=f"dl_{idx}",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            )
                    else:
                        st.error("❌ Document file was not created.")

        st.markdown("---")
