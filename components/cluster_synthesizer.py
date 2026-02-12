import os
import re
import json
import hashlib
from collections import defaultdict, Counter

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Embeddings / clustering
from sklearn.cluster import DBSCAN

# sentence-transformers is optional - only used for local clustering
# Dashboard uses precomputed clusters so this is not needed at runtime
SentenceTransformer = None
util = None
try:
    from sentence_transformers import SentenceTransformer as ST, util as st_util
    SentenceTransformer = ST
    util = st_util
except ImportError:
    pass  # Expected on Streamlit Cloud - we use precomputed clusters

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

# === Tunables ===
EMBED_MODEL = os.getenv("SS_CLUSTER_EMBED_MODEL", "intfloat/e5-base-v2")
COHERENCE_THRESHOLD = float(os.getenv("SS_CLUSTER_COHERENCE", "0.78"))
RECLUSTER_EPS = float(os.getenv("SS_CLUSTER_RECLUSTER_EPS", "0.30"))
DBSCAN_EPS = float(os.getenv("SS_CLUSTER_EPS", "0.38"))
MIN_CLUSTER_SIZE = int(os.getenv("SS_CLUSTER_MIN", "3"))

COMMON_TOKENS = {
    "refund", "return", "buyer", "seller", "case", "issue", "problem", "help", "please",
    "ebay", "item", "order", "receive", "received", "lost", "mail", "package", "tracking",
    "policy", "days", "time", "message", "respond", "contact", "support"
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with", "is", "are",
    "was", "were", "it", "that", "this", "i", "you", "my", "we", "they", "them", "he",
    "she", "as", "at", "be", "by", "from", "if", "but", "so", "not", "no", "do", "did",
    "does"
}

# Only load embedding model if sentence-transformers is available
model = None
if SentenceTransformer is not None:
    try:
        model = SentenceTransformer(EMBED_MODEL)
    except Exception:
        model = None


def _informative_tokens(text: str) -> set:
    toks = [t.lower() for t in re.findall(r"[a-z0-9]+", text or "")]
    return {t for t in toks if t not in STOPWORDS}


def _word_overlap_penalty(cluster_texts: list[str]) -> float:
    """
    Compute how much the cluster is glued by very common tokens.
    Returns a penalty in [0, 0.15] that is subtracted from avg similarity.
    """
    if len(cluster_texts) < 2:
        return 0.0
    sets = [_informative_tokens(t) for t in cluster_texts]
    if not all(sets):
        return 0.0
    overlaps = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            inter = (sets[i] & sets[j] & COMMON_TOKENS)
            union = (sets[i] | sets[j]) or {""}
            jac = len(inter) / max(1, len(union))
            overlaps.append(jac)
    if not overlaps:
        return 0.0
    avg = sum(overlaps) / len(overlaps)
    return min(0.15, avg * 0.6)


def cluster_insights(insights, min_cluster_size: int = MIN_CLUSTER_SIZE, eps: float = DBSCAN_EPS):
    if not model or not insights:
        return []
    texts = [
        f"{i.get('text')} | Tags: {i.get('type_tag')}, {i.get('journey_stage')}, {i.get('persona')}"
        for i in insights
    ]
    embeddings = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric="cosine").fit(
        embeddings.cpu().numpy()
    )
    labels = clustering.labels_
    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)
    return list(clustered.values())


def is_semantically_coherent(cluster, return_score=False, fast_mode=True):
    """Check cluster coherence. fast_mode=True skips expensive embedding calculation."""
    if fast_mode:
        # Fast mode: assume coherent if grouped by subtag, estimate score from keyword overlap
        if len(cluster) <= 2:
            return (True, 0.85) if return_score else True
        texts = [i.get("text", "") for i in cluster]
        # Estimate coherence from keyword overlap
        token_sets = [_informative_tokens(t) for t in texts]
        if not all(token_sets):
            return (True, 0.75) if return_score else True
        overlaps = []
        for i in range(min(5, len(token_sets))):  # Sample first 5 for speed
            for j in range(i + 1, min(5, len(token_sets))):
                inter = token_sets[i] & token_sets[j]
                union = token_sets[i] | token_sets[j]
                if union:
                    overlaps.append(len(inter) / len(union))
        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.5
        score = 0.6 + (avg_overlap * 0.4)  # Scale to 0.6-1.0 range
        return (True, score) if return_score else True
    
    # Slow mode with embeddings (original behavior)
    if not model:
        return (False, 0.0) if return_score else False
    if len(cluster) <= 2:
        return (True, 1.0) if return_score else True
    texts = [i["text"] for i in cluster]
    embeddings = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    sim_matrix = util.cos_sim(embeddings, embeddings).cpu().numpy()
    upper_triangle = sim_matrix[np.triu_indices(len(texts), k=1)]
    avg_similarity = float(np.mean(upper_triangle))

    penalty = _word_overlap_penalty(texts)
    adj = max(0.0, avg_similarity - penalty)
    if return_score:
        return adj >= COHERENCE_THRESHOLD, adj
    return adj >= COHERENCE_THRESHOLD


def split_incoherent_cluster(cluster):
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


def _cluster_id(cluster):
    return hashlib.md5(
        "|".join(sorted(i.get("fingerprint", i.get("text", "")) for i in cluster)).encode()
    ).hexdigest()


def generate_cluster_metadata(cluster):
    """
    Uses GPT to summarize a cluster into Title / Theme / Problem.
    Fixed to use max_completion_tokens instead of max_tokens.
    """
    if client is None:
        return {
            "title": "Untitled Cluster",
            "theme": "General",
            "problem": "OpenAI client not configured.",
        }

    combined = "\n".join(i["text"] for i in cluster[:6])
    prompt = (
        "You are a senior product manager reviewing a cluster of user feedback. For the following grouped posts, "
        "generate:\n1. A concise title (max 10 words)\n2. A theme tag\n3. A clear problem statement that could go in a PRD\n"
        f"\nPosts:\n{combined}\n\nFormat your response as:\nTitle: ...\nTheme: ...\nProblem: ..."
    )
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_CLUSTER_META", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a senior product strategist."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_completion_tokens=250,
        )
        content = (response.choices[0].message.content or "").strip()
        lines = content.split("\n")

        def _extract(prefix, default):
            for line in lines:
                if line.lower().startswith(prefix.lower()):
                    return line.split(":", 1)[-1].strip() or default
            return default

        return {
            "title": _extract("Title", "Untitled Cluster"),
            "theme": _extract("Theme", "General"),
            "problem": _extract("Problem", "No problem statement provided."),
        }
    except Exception as e:
        return {
            "title": "(GPT Error)",
            "theme": "Unknown",
            "problem": str(e),
        }


def synthesize_cluster(cluster):
    meta = generate_cluster_metadata(cluster)
    brand = cluster[0].get("target_brand") or "Unknown"
    type_tag = cluster[0].get("type_tag") or "Insight"
    quotes = [f"- _{i.get('text', '')[:220]}_" for i in cluster[:3]]

    idea_counter = defaultdict(int)
    for i in cluster:
        for idea in i.get("ideas", []):
            if idea and len(idea.strip()) > 10 and not idea.lower().startswith("customer"):
                idea_counter[idea.strip()] += 1
    top_ideas = [k for k, _ in sorted(idea_counter.items(), key=lambda x: -x[1])[:5]]

    scores = [i.get("score", 0) for i in cluster]
    min_score = round(min(scores), 2)
    max_score = round(max(scores), 2)

    sentiments = list({i.get("brand_sentiment", "Neutral") for i in cluster})
    personas = list({i.get("persona", "Unknown") for i in cluster})
    efforts = list({i.get("effort", "Unknown") for i in cluster})
    topics = sorted({t for i in cluster for t in (i.get("topic_focus") or [])})
    competitors = sorted({c for i in cluster for c in (i.get("mentions_competitor") or [])})
    cid = _cluster_id(cluster)

    coherent, avg_sim = is_semantically_coherent(cluster, return_score=True, fast_mode=True)
    avg_cluster_ready = float(
        np.mean([i.get("cluster_ready_score", 0) for i in cluster])
    ) if cluster else 0.0

    return {
        "title": meta["title"],
        "theme": meta["theme"],
        "problem_statement": meta["problem"],
        "brand": brand,
        "type": type_tag,
        "personas": personas,
        "effort_levels": efforts,
        "sentiments": sentiments,
        "opportunity_tags": list({i.get("opportunity_tag", "General Insight") for i in cluster}),
        "quotes": quotes,
        "top_ideas": top_ideas,
        "score_range": f"{min_score}–{max_score}",
        "insight_count": len(cluster),
        "avg_cluster_ready": avg_cluster_ready,
        "topic_focus_tags": topics,
        "mentions_competitor": competitors,
        "cluster_id": cid,
        "avg_similarity": f"{avg_sim:.2f}",
        "coherent": coherent,
        "was_reclustered": False,
    }


def _get_signal_category(insight):
    """Determine the primary signal category for an insight based on flags."""
    # Check signal flags in priority order
    if insight.get("is_vault_signal"):
        return "Vault"
    if insight.get("is_psa_turnaround"):
        return "Grading"
    if insight.get("is_ag_signal"):
        return "Authentication"
    if insight.get("is_shipping_issue"):
        return "Shipping"
    if insight.get("_payment_issue"):
        return "Payments"
    if insight.get("is_refund_issue"):
        return "Refunds"
    if insight.get("is_fees_concern"):
        return "Fees"
    if insight.get("_upi_flag"):
        return "UPI"
    if insight.get("is_price_guide_signal"):
        return "Pricing"
    
    # Fall back to subtag or text-based detection
    subtag = insight.get("type_subtag") or insight.get("subtag") or ""
    if subtag and subtag != "General":
        return subtag
    
    # Text-based topic detection
    text = (insight.get("text", "") + " " + insight.get("title", "")).lower()
    if "vault" in text:
        return "Vault"
    if "grading" in text or "psa" in text or "turnaround" in text:
        return "Grading"
    if "shipping" in text or "delivery" in text or "tracking" in text:
        return "Shipping"
    if "payment" in text or "payout" in text or "paid" in text:
        return "Payments"
    if "refund" in text or "return" in text:
        return "Refunds"
    if "fee" in text or "commission" in text:
        return "Fees"
    if "authentication" in text or "authenticity" in text:
        return "Authentication"
    if "competitor" in text or "fanatics" in text or "alt" in text:
        return "Competitors"
    if "goldin" in text or "tcgplayer" in text:
        return "Subsidiaries"
    
    return "General Feedback"


def cluster_by_subtag_fast(insights, min_cluster_size=MIN_CLUSTER_SIZE):
    """Fast clustering by signal category - no embeddings, instant results."""
    grouped = defaultdict(list)
    for i in insights:
        category = _get_signal_category(i)
        grouped[category].append(i)

    all_clusters = []
    for category, group in grouped.items():
        if len(group) < min_cluster_size:
            continue
        # Group by signal category
        coherent, score = is_semantically_coherent(group, return_score=True, fast_mode=True)
        all_clusters.append((group, {"coherent": coherent, "was_reclustered": False, "avg_similarity": score, "category": category}))
    return all_clusters


def cluster_by_subtag_then_embed(insights, min_cluster_size=MIN_CLUSTER_SIZE, fast_mode=True):
    """Cluster insights. fast_mode=True uses keyword grouping only (instant), False uses embeddings (slow)."""
    if fast_mode:
        return cluster_by_subtag_fast(insights, min_cluster_size)
    
    # Original slow mode with embeddings
    if not model:
        return cluster_by_subtag_fast(insights, min_cluster_size)
    
    grouped = defaultdict(list)
    for i in insights:
        subtags = i.get("type_subtags") or [i.get("type_subtag", "General")]
        if isinstance(subtags, str):
            subtags = [subtags]
        for subtag in subtags:
            grouped[subtag].append(i)

    all_clusters = []
    for subtag, group in grouped.items():
        if len(group) < min_cluster_size:
            continue
        clusters = cluster_insights(group, min_cluster_size=min_cluster_size)
        for c in clusters:
            coherent, score = is_semantically_coherent(c, return_score=True, fast_mode=False)
            if coherent:
                all_clusters.append((c, {"coherent": True, "was_reclustered": False, "avg_similarity": score}))
            else:
                subs = split_incoherent_cluster(c)
                for sub in subs:
                    sub_coherent, sub_score = is_semantically_coherent(sub, return_score=True, fast_mode=False)
                    all_clusters.append((sub, {"coherent": sub_coherent, "was_reclustered": True, "avg_similarity": sub_score}))
    return all_clusters


def generate_synthesized_insights(insights):
    raw_cluster_tuples = cluster_by_subtag_then_embed(insights)
    summaries = []
    for cluster, meta in raw_cluster_tuples:
        card = synthesize_cluster(cluster)
        card["coherent"] = meta["coherent"]
        card["was_reclustered"] = meta["was_reclustered"]
        card["avg_similarity"] = f"{meta['avg_similarity']:.2f}"
        summaries.append(card)
    return summaries
