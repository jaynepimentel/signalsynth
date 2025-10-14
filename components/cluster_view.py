# components/cluster_view.py — precomputed-first, cloud-safe, with heuristic fallback (no embeddings)

import os
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

from components.cluster_synthesizer import cluster_insights, generate_synthesized_insights
from components.ai_suggester import (
    generate_cluster_prd_docx,
    generate_cluster_prfaq_docx,
    generate_cluster_brd_docx,
)

RUNNING_IN_STREAMLIT = os.getenv("RUNNING_IN_STREAMLIT", "0") == "1"

# ---------- Cache & artifacts ----------
CACHE_DIR = os.getenv("SS_CACHE_DIR", os.path.join(tempfile.gettempdir(), ".cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "clusters_cards.json")
CLUSTER_CACHE_TTL_DAYS = int(os.getenv("CLUSTER_CACHE_TTL", "7"))

# ---------- Helpers ----------
def _is_expired(path: str, days: int) -> bool:
    if not os.path.exists(path): return True
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime) > timedelta(days=days)

def _atomic_save(data: dict, path: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _valid(payload: dict | None) -> bool:
    if not payload or not isinstance(payload, dict): return False
    clusters = payload.get("clusters") or []
    cards = payload.get("cards") or []
    if not clusters or not cards: return False
    if abs(len(clusters) - len(cards)) > max(2, 0.25 * max(len(clusters), len(cards))):
        return False
    return True

def _load_cache() -> dict | None:
    if not os.path.exists(CACHE_FILE): return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _find_artifact(name: str) -> str | None:
    # cwd
    p = Path(name)
    if p.exists(): return str(p)
    # signalsynth/ subdir
    alt = Path("signalsynth") / name
    if alt.exists(): return str(alt)
    # walk up 3 levels
    here = Path(__file__).resolve().parent
    root = here
    for _ in range(3):
        cand = root / name
        if cand.exists(): return str(cand)
        cand2 = root / "signalsynth" / name
        if cand2.exists(): return str(cand2)
        root = root.parent
    return None

def _load_precomputed() -> dict | None:
    path = _find_artifact("precomputed_clusters.json")
    if not path: return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if _valid(data) else None
    except Exception:
        return None

def _rebuild_from_insights(insights: list[dict]) -> dict:
    # Only for local dev (embeddings available)
    clusters = cluster_insights(insights)
    cards = generate_synthesized_insights(insights)
    data = {"clusters": clusters, "cards": cards, "built_at": datetime.now().isoformat()}
    _atomic_save(data, CACHE_FILE)
    return data

# ---------- Heuristic fallback (no embeddings required) ----------
def _heuristic_clusters(insights: list[dict], max_clusters: int = 12) -> dict:
    """
    Groups insights by (topic_subtag → type_subtag → brand_sentiment) to create pseudo-clusters
    when embeddings are unavailable. Produces a payload with 'clusters' and 'cards'.
    """
    from collections import defaultdict, Counter

    buckets = defaultdict(list)
    for i in insights:
        t = (i.get("type_subtag") or "General")
        topics = i.get("topic_focus") or []
        topic = topics[0] if topics else "General"
        senti = i.get("brand_sentiment") or "Neutral"
        key = (topic, t, senti)
        buckets[key].append(i)

    # sort buckets by size desc, limit
    groups = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)[:max_clusters]

    clusters = []
    cards = []
    for (topic, subtag, senti), group in groups:
        clusters.append(group)
        # synthesize a simple card
        text_samples = [g.get("text", "") for g in group[:3]]
        quotes = [f"- _{s[:220]}_" for s in text_samples if s]

        brands = {g.get("target_brand", "Unknown") for g in group}
        personas = list({g.get("persona", "General") for g in group})
        efforts = list({g.get("effort", "Unknown") for g in group})
        sents = list({g.get("brand_sentiment", "Neutral") for g in group})
        topics_all = sorted({tt for g in group for tt in (g.get("topic_focus") or [])})

        scores = [float(g.get("score", 0)) for g in group]
        score_range = f"{round(min(scores),2)}–{round(max(scores),2)}" if scores else "N/A"

        cards.append({
            "title": f"{topic} / {subtag}",
            "theme": topic,
            "problem_statement": f"Grouped by {topic} · {subtag} · {senti} (heuristic cluster)",
            "brand": "Multiple" if len(brands) > 1 else next(iter(brands)) if brands else "Unknown",
            "personas": personas,
            "effort_levels": efforts,
            "sentiments": sents,
            "opportunity_tags": [g.get("opportunity_tag","General Insight") for g in group if g.get("opportunity_tag")][:3],
            "topic_focus_tags": topics_all[:6],
            "quotes": quotes,
            "top_ideas": [idea for g in group for idea in (g.get("ideas") or [])][:5],
            "score_range": score_range,
            "insight_count": len(group),
            "avg_cluster_ready": float(sum(g.get("cluster_ready_score",0) for g in group))/max(1,len(group)),
            "action_type_distribution": dict(Counter(g.get("action_type","Unclear") for g in group)),
            "mentions_competitor": sorted({c for g in group for c in (g.get("mentions_competitor") or [])}),
            "coherent": True,
            "was_reclustered": False,
            "avg_similarity": "N/A (heuristic)",
        })

    return {"clusters": clusters, "cards": cards, "built_at": datetime.now().isoformat()}

# ---------- UI ----------
def display_clustered_insight_cards(insights: list[dict]) -> None:
    st.subheader("🧱 Clustered Insight Mode")

    if not insights:
        st.info("No insights to cluster.")
        return

    # Controls
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        rebuild = st.button("🔄 Rebuild (local compute)", disabled=RUNNING_IN_STREAMLIT)
    with c2:
        clear = st.button("🧹 Clear Cache")

    if RUNNING_IN_STREAMLIT:
        st.caption("Cloud-safe mode: using precomputed clusters or heuristic grouping; local rebuild disabled.")

    if clear:
        try:
            if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
            st.success("Cluster cache cleared.")
        except Exception as e:
            st.error(f"Could not clear cache: {e}")

    # 1) Try existing cache
    payload = _load_cache()
    if not (payload and not _is_expired(CACHE_FILE, CLUSTER_CACHE_TTL_DAYS) and _valid(payload)):
        # 2) Try precomputed artifact
        payload = _load_precomputed()

    # 3) Fallbacks
    if not payload:
        if rebuild and not RUNNING_IN_STREAMLIT:
            with st.spinner("Generating clusters from current insights…"):
                payload = _rebuild_from_insights(insights)
        else:
            # Heuristic grouping (no embeddings) so the page still renders
            payload = _heuristic_clusters(insights)
            _atomic_save(payload, CACHE_FILE)
            st.info("Rendered heuristic clusters (no embeddings). Commit precomputed_clusters.json for richer groups.")

    # Validate + trim
    clusters = payload.get("clusters") or []
    cards = payload.get("cards") or []
    n = min(len(cards), len(clusters))
    if n == 0:
        st.warning("No cluster data available.")
        return
    if n < len(cards) or n < len(clusters):
        cards, clusters = cards[:n], clusters[:n]
        st.info(f"⚠️ Mismatch detected: trimmed to {n} aligned items.")

    st.caption(f"Showing {n} clusters")

    # Render clusters
    for idx in range(n):
        card = cards[idx]
        cluster = clusters[idx]

        with st.container():
            st.markdown(
                f"### 📌 {card.get('title','Untitled')} — {card.get('brand','Unknown')} "
                f"({card.get('theme','N/A')})"
            )
            st.markdown(f"**Problem:** {card.get('problem_statement','No summary available.')}")

            personas = ", ".join(card.get("personas", []) or [])
            efforts  = ", ".join(card.get("effort_levels", []) or [])
            sents    = ", ".join(card.get("sentiments", []) or [])
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

            quotes = card.get("quotes") or []
            if quotes:
                st.markdown("**📣 Example Quotes:**")
                for q in quotes[:3]: st.markdown(q)

            ideas = card.get("top_ideas") or []
            if ideas:
                st.markdown("**💡 Top Suggestions:**")
                for idea in ideas: st.markdown(f"- {idea}")

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
