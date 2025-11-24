# cluster_view.py - Cluster cards with guaranteed GPT ideas and unique quotes

import os
import json
import tempfile
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import streamlit as st

from components.cluster_synthesizer import cluster_insights, generate_synthesized_insights
from components.ai_suggester import (
    generate_cluster_prd_docx,
    generate_cluster_prfaq_docx,
    generate_cluster_brd_docx,
    generate_pm_ideas,
)

RUNNING_IN_STREAMLIT = os.getenv("RUNNING_IN_STREAMLIT", "0") == "1"
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

# Cache and artifacts
CACHE_DIR = os.getenv("SS_CACHE_DIR", os.path.join(tempfile.gettempdir(), ".cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "clusters_cards.json")
CLUSTER_CACHE_TTL_DAYS = int(os.getenv("CLUSTER_CACHE_TTL", "7"))

CLUSTER_ARTIFACT = "precomputed_clusters.json"


# ---------- Helper functions ----------

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


def _valid(payload: Optional[dict]) -> bool:
    if not payload or not isinstance(payload, dict):
        return False
    clusters = payload.get("clusters") or []
    cards = payload.get("cards") or []
    if not clusters or not cards:
        return False
    if abs(len(clusters) - len(cards)) > max(2, 0.25 * max(len(clusters), len(cards))):
        return False
    return True


def _load_cache() -> Optional[dict]:
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _find_artifact(name: str) -> Optional[str]:
    p = Path(name)
    if p.exists():
        return str(p)

    alt = Path("signalsynth") / name
    if alt.exists():
        return str(alt)

    here = Path(__file__).resolve().parent
    root = here
    for _ in range(3):
        cand = root / name
        if cand.exists():
            return str(cand)
        cand2 = root / "signalsynth" / name
        if cand2.exists():
            return str(cand2)
        root = root.parent
    return None


def _load_precomputed() -> Optional[dict]:
    path = _find_artifact(CLUSTER_ARTIFACT)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "clusters" in data and "cards" in data:
            return data
        # older format where root is list of clusters
        if isinstance(data, list):
            return {"clusters": data, "cards": []}
        return None
    except Exception:
        return None


def _rebuild_from_insights(insights: List[Dict[str, Any]]) -> dict:
    # Only for local dev (embeddings available)
    clusters = cluster_insights(insights)
    cards = generate_synthesized_insights(insights)
    data = {
        "clusters": clusters,
        "cards": cards,
        "built_at": datetime.now().isoformat(),
    }
    _atomic_save(data, CACHE_FILE)
    return data


def _heuristic_clusters(insights: List[Dict[str, Any]], max_clusters: int = 12) -> dict:
    """
    Heuristic grouping, used as a last resort when no precomputed clusters exist.
    Groups by (topic_focus[0], type_subtag, brand_sentiment).
    """
    from collections import defaultdict, Counter

    buckets = defaultdict(list)
    for i in insights:
        t = i.get("type_subtag") or "General"
        topics = i.get("topic_focus") or []
        topic = topics[0] if topics else "General"
        senti = i.get("brand_sentiment") or "Neutral"
        key = (topic, t, senti)
        buckets[key].append(i)

    groups = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)[:max_clusters]

    clusters = []
    cards = []
    for (topic, subtag, senti), group in groups:
        clusters.append({"insights": group, "theme": topic, "sentiment": senti})
        text_samples = [g.get("text", "") for g in group[:3]]
        quotes = [
            f"- _{_truncate(s)}_"
            for s in text_samples
            if s
        ]

        brands = {g.get("target_brand", "Unknown") for g in group}
        personas = list({g.get("persona", "General") for g in group})
        efforts = list({g.get("effort", "Unknown") for g in group})
        sents = list({g.get("brand_sentiment", "Neutral") for g in group})
        topics_all = sorted({tt for g in group for tt in (g.get("topic_focus") or [])})

        scores = [float(g.get("score", 0)) for g in group]
        score_range = (
            f"{round(min(scores), 2)}–{round(max(scores), 2)}" if scores else "N/A"
        )

        cards.append(
            {
                "title": f"{topic} / {subtag}",
                "theme": topic,
                "problem_statement": f"Grouped by {topic} · {subtag} · {senti} (heuristic cluster)",
                "brand": "Multiple"
                if len(brands) > 1
                else next(iter(brands))
                if brands
                else "Unknown",
                "personas": personas,
                "effort_levels": efforts,
                "sentiments": sents,
                "topic_focus_tags": topics_all[:6],
                "quotes": quotes,
                "top_ideas": [],
                "score_range": score_range,
                "insight_count": len(group),
                "coherent": True,
                "was_reclustered": False,
                "avg_similarity": "N/A (heuristic)",
            }
        )

    return {"clusters": clusters, "cards": cards, "built_at": datetime.now().isoformat()}


def _truncate(text: str, max_chars: int = 220) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3].rsplit(" ", 1)[0] + "..."


def _extract_cluster_insights(cluster: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Be flexible about cluster structure.
    Prefer 'insights', then 'items', then 'examples', then treat cluster itself as list.
    """
    if isinstance(cluster, dict):
        for key in ("insights", "items", "examples"):
            val = cluster.get(key)
            if isinstance(val, list) and val:
                return val
    if isinstance(cluster, list):
        return cluster
    return []


def _dedupe_quotes(insights: List[Dict[str, Any]], max_quotes: int = 3) -> List[str]:
    seen = set()
    quotes: List[str] = []
    for ins in insights:
        text = (ins.get("text") or "").strip()
        if not text:
            continue
        key = text[:200]
        if key in seen:
            continue
        seen.add(key)
        quotes.append(_truncate(text))
        if len(quotes) >= max_quotes:
            break
    return quotes


def _aggregate_actions_from_insights(
    insights: List[Dict[str, Any]],
    max_actions: int = 8,
) -> List[str]:
    seen = set()
    actions: List[str] = []
    for ins in insights:
        ideas = ins.get("ideas") or []
        if isinstance(ideas, str):
            ideas = [ideas]
        for idea in ideas:
            idea_str = str(idea).strip()
            if not idea_str:
                continue
            key = idea_str.lower()
            if key in seen:
                continue
            seen.add(key)
            pretty = textwrap.shorten(idea_str, width=260, placeholder="...")
            actions.append(pretty)
            if len(actions) >= max_actions:
                return actions
    return actions


def _ensure_cluster_ideas(
    card: Dict[str, Any],
    cluster_insights: List[Dict[str, Any]],
) -> List[str]:
    """
    Guarantee that a cluster has GPT generated ideas.
    Priority:
    1. Use card['top_ideas'] if non empty.
    2. Aggregate ideas from member insights (which are GPT generated in precompute/insight view).
    3. If still empty and OpenAI key exists, call generate_pm_ideas on a cluster summary.
    """
    ideas = card.get("top_ideas") or []
    if isinstance(ideas, str):
        ideas = [ideas]
    ideas = [str(x).strip() for x in ideas if str(x).strip()]
    if ideas:
        card["top_ideas"] = ideas
        return ideas

    # Aggregate from member insights
    agg = _aggregate_actions_from_insights(cluster_insights)
    if agg:
        card["top_ideas"] = agg
        return agg

    if not OPENAI_KEY_PRESENT:
        card["top_ideas"] = []
        return []

    # Last resort: generate a few cluster-level suggestions from the theme and quotes
    title = card.get("title") or card.get("theme") or "Cluster"
    problem = card.get("problem_statement") or ""
    quotes = _dedupe_quotes(cluster_insights, max_quotes=2)

    prompt_text = (
        f"Cluster: {title}\n\n"
        f"Problem summary: {problem}\n\n"
        f"Example quotes:\n"
        + "\n".join(f"- {q}" for q in quotes)
    )

    try:
        ideas = generate_pm_ideas(prompt_text, card.get("brand", "eBay"))
        if isinstance(ideas, str):
            ideas = [ideas]
        ideas = [str(x).strip() for x in ideas if str(x).strip()]
        card["top_ideas"] = ideas
        return ideas
    except Exception as e:
        card["top_ideas"] = [f"[GPT error while generating cluster ideas: {str(e)}]"]
        return card["top_ideas"]


# ---------- UI ----------

def display_clustered_insight_cards(insights: List[Dict[str, Any]]) -> None:
    st.subheader("🧱 Clustered Insight Mode")

    if not insights:
        st.info("No insights to cluster.")
        return

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        rebuild = st.button("🔄 Rebuild (local compute)", disabled=RUNNING_IN_STREAMLIT)
    with c2:
        clear = st.button("🧹 Clear cache")

    if RUNNING_IN_STREAMLIT:
        st.caption(
            "Cloud safe mode is active. Using precomputed clusters or heuristic grouping. "
            "Local rebuild is disabled."
        )

    if clear:
        try:
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            st.success("Cluster cache cleared.")
        except Exception as e:
            st.error(f"Could not clear cache: {e}")

    # 1) Try cached payload
    payload = _load_cache()
    if not (payload and not _is_expired(CACHE_FILE, CLUSTER_CACHE_TTL_DAYS) and _valid(payload)):
        # 2) Try precomputed artifact
        payload = _load_precomputed()

    # 3) Fallbacks
    if not payload:
        if rebuild and not RUNNING_IN_STREAMLIT:
            with st.spinner("Generating clusters from current insights..."):
                payload = _rebuild_from_insights(insights)
        else:
            payload = _heuristic_clusters(insights)
            _atomic_save(payload, CACHE_FILE)
            st.info(
                "Rendered heuristic clusters (no embeddings). "
                "Commit precomputed_clusters.json for richer groupings."
            )

    clusters = payload.get("clusters") or []
    cards = payload.get("cards") or []
    n = min(len(cards), len(clusters))
    if n == 0:
        st.warning("No cluster data available.")
        return
    if n < len(cards) or n < len(clusters):
        cards, clusters = cards[:n], clusters[:n]
        st.info(f"Trimmed clusters and cards to {n} aligned entries due to mismatch.")

    st.caption(f"Showing {n} clusters")

    for idx in range(n):
        card = cards[idx]
        cluster = clusters[idx]
        cluster_insights = _extract_cluster_insights(cluster)

        with st.container():
            # Header
            title = card.get("title") or card.get("theme") or f"Cluster {idx}"
            brand = card.get("brand", "Unknown")
            theme = card.get("theme", "N/A")
            st.markdown(f"### 📌 {title} — {brand} ({theme})")

            problem = card.get("problem_statement") or "No summary available."
            st.markdown(f"**Problem:** {problem}")

            personas = ", ".join(card.get("personas", []) or [])
            efforts = ", ".join(card.get("effort_levels", []) or [])
            sents = ", ".join(card.get("sentiments", []) or [])
            st.markdown(
                f"**Persona(s):** {personas or '—'} | "
                f"Effort: {efforts or '—'} | "
                f"Sentiments: {sents or '—'}"
            )

            st.markdown(
                f"**Mentions:** {len(cluster_insights)} | "
                f"Score Range: {card.get('score_range','N/A')} | "
                f"Avg Similarity: {card.get('avg_similarity','N/A')}"
            )
            st.markdown(
                f"**Was Reclustered:** {'✅' if card.get('was_reclustered') else '❌'} | "
                f"Coherent: {'✅' if card.get('coherent') else '❌'}"
            )

            # Quotes: compute unique quotes from member insights so we avoid duplication
            quotes = _dedupe_quotes(cluster_insights, max_quotes=3)
            if quotes:
                st.markdown("**📣 Example quotes:**")
                for q in quotes:
                    st.markdown(f"> {q}")

            # Actions: ensure we have GPT generated ideas at the cluster level
            ideas = _ensure_cluster_ideas(card, cluster_insights)
            if ideas:
                st.markdown("**💡 Suggested PM actions for this cluster:**")
                for idea in ideas:
                    st.markdown(f"- {idea}")

            # Document generation
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
                filename = (title or "cluster")[:64]
                with st.spinner(f"Generating {doc_type}..."):
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
                        st.error("Document file was not created.")

        st.markdown("---")
