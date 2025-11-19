# ✅ cluster_synthesizer.py — FAISS-free, with GPT cluster metadata cache

import os
import json
import hashlib
from collections import defaultdict, Counter

import numpy as np
from sklearn.cluster import DBSCAN
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

CACHE_DIR = ".cache"
CACHE_PATH = os.path.join(CACHE_DIR, "cluster_metadata.json")

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        CLUSTER_META_CACHE = json.load(f)
else:
    CLUSTER_META_CACHE = {}

# Lazy global model to avoid heavy startup
_model = None


def get_model():
    """
    Lazily load SentenceTransformer model.
    We only load when clustering is actually invoked.
    """
    global _model
    if _model is not None:
        return _model

    # Skip loading in Streamlit if you want to keep things light:
    if os.getenv("RUNNING_IN_STREAMLIT") == "1":
        print("⚠️ RUNNING_IN_STREAMLIT=1 — skipping cluster_synthesizer model load.")
        _model = None
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("intfloat/e5-base-v2")
    except Exception as e:
        print("❌ Failed to load SentenceTransformer in cluster_synthesizer:", e)
        _model = None

    return _model


COHERENCE_THRESHOLD = 0.68
RECLUSTER_EPS = 0.30


def cluster_by_subtag_then_embed(insights, min_cluster_size=3):
    """
    Group insights by type_subtag (or fallback) and cluster each group with embeddings.
    Returns a list of (cluster, meta_dict) tuples.
    """
    model = get_model()
    if not model:
        print("⚠️ Embedding model unavailable in cluster_synthesizer. Skipping clustering.")
        return []

    grouped = defaultdict(list)
    for i in insights:
        subtags = i.get("type_subtags") or [i.get("type_subtag", "General")]
        if not isinstance(subtags, list):
            subtags = [subtags]
        for subtag in subtags:
            grouped[subtag].append(i)

    all_clusters = []
    for subtag, group in grouped.items():
        if len(group) < min_cluster_size:
            continue

        clusters = cluster_insights(group, min_cluster_size=min_cluster_size)
        for c in clusters:
            coherent, score = is_semantically_coherent(c, return_score=True)
            if coherent:
                all_clusters.append(
                    (c, {"coherent": True, "was_reclustered": False, "avg_similarity": score})
                )
            else:
                subclusters = split_incoherent_cluster(c)
                for sub in subclusters:
                    sub_coherent, sub_score = is_semantically_coherent(sub, return_score=True)
                    all_clusters.append(
                        (
                            sub,
                            {
                                "coherent": sub_coherent,
                                "was_reclustered": True,
                                "avg_similarity": sub_score,
                            },
                        )
                    )
    return all_clusters


def cluster_insights(insights, min_cluster_size=3, eps=0.38):
    """
    Cluster insights using DBSCAN on SentenceTransformer embeddings.
    """
    model = get_model()
    if not model:
        print("⚠️ Embedding model unavailable. Returning no clusters.")
        return []

    texts = [
        f"{i.get('text')} | Tags: {i.get('type_tag')}, {i.get('journey_stage')}, {i.get('persona')}"
        for i in insights
    ]
    embeddings = model.encode(texts, convert_to_numpy=True)

    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric="cosine").fit(
        embeddings
    )
    labels = clustering.labels_

    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)

    return list(clustered.values())


def is_semantically_coherent(cluster, return_score=False):
    """
    Compute average pairwise cosine similarity in a cluster, compare to COHERENCE_THRESHOLD.
    """
    model = get_model()
    if not model:
        return (False, 0.0) if return_score else False

    if len(cluster) <= 2:
        return (True, 1.0) if return_score else True

    texts = [i.get("text", "") for i in cluster]
    embeddings = model.encode(texts, convert_to_numpy=True)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
    normalized = embeddings / norms
    sim_matrix = np.dot(normalized, normalized.T)

    upper_triangle = sim_matrix[np.triu_indices(len(texts), k=1)]
    avg_similarity = float(upper_triangle.mean()) if len(upper_triangle) else 0.0

    if return_score:
        return avg_similarity >= COHERENCE_THRESHOLD, avg_similarity
    return avg_similarity >= COHERENCE_THRESHOLD


def split_incoherent_cluster(cluster):
    """
    Recluster an incoherent cluster with smaller eps, or fall back to tiny subclusters.
    """
    model = get_model()
    if not model:
        return [cluster]

    if len(cluster) <= 3:
        return [cluster]

    subclusters = cluster_insights(cluster, min_cluster_size=2, eps=RECLUSTER_EPS)
    final = []
    for c in subclusters:
        if len(c) <= 2:
            final.extend([[i] for i in c])
        else:
            final.append(c)
    return final


def _compute_cluster_id(cluster):
    key = "|".join(sorted(i.get("fingerprint", i.get("text", "")) or "" for i in cluster))
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def generate_cluster_metadata(cluster):
    """
    Use GPT (if configured) to generate Title / Theme / Problem for a cluster,
    cached by cluster_id.
    """
    cluster_id = _compute_cluster_id(cluster)
    if cluster_id in CLUSTER_META_CACHE:
        return CLUSTER_META_CACHE[cluster_id]

    combined = "\n".join(i.get("text", "") for i in cluster[:6])
    prompt = (
        "You are a senior product manager reviewing a cluster of user feedback. "
        "For the following grouped posts, generate:\n"
        "1. A concise title (max 10 words)\n"
        "2. A theme tag\n"
        "3. A clear problem statement that could go in a PRD\n"
        f"\nPosts:\n{combined}\n\n"
        "Format your response as:\n"
        "Title: ...\nTheme: ...\nProblem: ..."
    )

    if client is None:
        metadata = {
            "title": "Untitled Cluster",
            "theme": "General",
            "problem": "OpenAI key not configured; problem summary unavailable.",
        }
        CLUSTER_META_CACHE[cluster_id] = metadata
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(CLUSTER_META_CACHE, f, indent=2)
        return metadata

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a senior product strategist."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        content = response.choices[0].message.content.strip()
        lines = content.split("\n")

        def _extract(prefix, default):
            for line in lines:
                if line.lower().startswith(prefix.lower()):
                    return line.split(":", 1)[-1].strip() or default
            return default

        metadata = {
            "title": _extract("Title", "Untitled Cluster"),
            "theme": _extract("Theme", "General"),
            "problem": _extract("Problem", "No problem statement provided."),
        }

        CLUSTER_META_CACHE[cluster_id] = metadata
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(CLUSTER_META_CACHE, f, indent=2)
        return metadata

    except Exception as e:
        return {
            "title": "(GPT Error)",
            "theme": "Unknown",
            "problem": str(e),
        }


def synthesize_cluster(cluster):
    """
    Turn a cluster (list of insight dicts) into a summarized card.
    """
    metadata = generate_cluster_metadata(cluster)

    brand = cluster[0].get("target_brand") or "Unknown"
    type_tag = cluster[0].get("type_tag") or "Insight"

    quotes = [f"- _{i.get('text', '')[:220]}_" for i in cluster[:3]]

    idea_counter = defaultdict(int)
    for i in cluster:
        for idea in i.get("ideas", []):
            if idea and len(idea.strip()) > 10 and not idea.lower().startswith("customer"):
                idea_counter[idea.strip()] += 1
    top_ideas = sorted(idea_counter.items(), key=lambda x: -x[1])[:5]

    scores = [i.get("score", 0) for i in cluster] or [0]
    min_score = round(float(min(scores)), 2)
    max_score = round(float(max(scores)), 2)

    action_types = Counter(i.get("action_type", "Unclear") for i in cluster)
    competitors = sorted({c for i in cluster for c in (i.get("mentions_competitor") or [])})
    topics = sorted({t for i in cluster for t in (i.get("topic_focus") or [])})
    cluster_id = _compute_cluster_id(cluster)

    avg_cluster_ready = float(
        np.mean([i.get("cluster_ready_score", 0) for i in cluster])
        if cluster
        else 0.0
    )

    return {
        "title": metadata["title"],
        "theme": metadata["theme"],
        "problem_statement": metadata["problem"],
        "brand": brand,
        "type": type_tag,
        "personas": list({i.get("persona", "Unknown") for i in cluster}),
        "effort_levels": list({i.get("effort", "Unknown") for i in cluster}),
        "sentiments": list({i.get("brand_sentiment", "Neutral") for i in cluster}),
        "opportunity_tags": list({i.get("opportunity_tag", "General Insight") for i in cluster}),
        "quotes": quotes,
        "top_ideas": [i[0] for i in top_ideas],
        "score_range": f"{min_score}–{max_score}",
        "insight_count": len(cluster),
        "avg_cluster_ready": round(avg_cluster_ready, 2),
        "action_type_distribution": dict(action_types),
        "topic_focus_tags": topics,
        "mentions_competitor": competitors,
        "cluster_id": cluster_id,
    }


def generate_synthesized_insights(insights):
    """
    Entry point: from raw insights → cluster summary cards.
    """
    raw_cluster_tuples = cluster_by_subtag_then_embed(insights)
    summaries = []
    for cluster, meta in raw_cluster_tuples:
        card = synthesize_cluster(cluster)
        card["coherent"] = meta["coherent"]
        card["was_reclustered"] = meta["was_reclustered"]
        card["avg_similarity"] = f"{meta['avg_similarity']:.2f}"
        summaries.append(card)
    return summaries
