import os
import re
import json
import hashlib
from collections import defaultdict, Counter

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Heavy imports (sklearn, sentence_transformers, torch) are lazy-loaded
# to keep fast-mode clustering instant (<2s vs 60+s).
# They are only imported inside _ensure_embedding_model() when slow mode is used.
DBSCAN = None
SentenceTransformer = None
util = None

load_dotenv()
load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)

def _is_placeholder(v):
    if not v:
        return True
    s = str(v).strip()
    if not s:
        return True
    bad_markers = [
        "YOUR_OPENAI_API_KEY",
        "YOUR_OPE",
        "YOUR_OPEN",
        "REPLACE_ME",
    ]
    return any(m in s.upper() for m in bad_markers)


def _get_openai_key():
    # Prefer env for local scripts if valid
    env_key = os.getenv("OPENAI_API_KEY")
    if not _is_placeholder(env_key):
        return env_key

    # Fall back to Streamlit secrets for remote/runtime contexts
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            sec_key = st.secrets["OPENAI_API_KEY"]
            if not _is_placeholder(sec_key):
                return sec_key
    except Exception:
        pass
    return None


def _get_model_setting(key, default):
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            v = str(st.secrets[key]).strip()
            if v:
                return v
    except Exception:
        pass
    v = os.getenv(key)
    return v.strip() if isinstance(v, str) and v.strip() else default


OPENAI_KEY = _get_openai_key()
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

# Embedding model is loaded lazily so fast-mode clustering starts instantly.
model = None
_MAX_SEQ = 510  # safe default (512 position embeddings - 2 special tokens)


def _ensure_embedding_model():
    """Lazy-load the sentence-transformers model and sklearn only when needed."""
    global model, _MAX_SEQ, SentenceTransformer, util, DBSCAN
    if model is not None:
        return model
    if str(os.getenv("SS_CLUSTER_FAST_ONLY", "")).lower() in ("1", "true", "yes"):
        return None
    # Lazy-import heavy libraries (torch, transformers, sklearn)
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as ST, util as st_util
            SentenceTransformer = ST
            util = st_util
        except ImportError:
            return None
    if DBSCAN is None:
        try:
            from sklearn.cluster import DBSCAN as _DBSCAN
            DBSCAN = _DBSCAN
        except ImportError:
            pass
    try:
        model = SentenceTransformer(EMBED_MODEL)
        # Derive actual position-embedding limit and enforce it everywhere
        try:
            _MAX_SEQ = model[0].auto_model.config.max_position_embeddings - 2
        except Exception:
            _MAX_SEQ = 510
        model.max_seq_length = _MAX_SEQ
        if hasattr(model, "tokenizer"):
            model.tokenizer.model_max_length = _MAX_SEQ
        try:
            model[0].max_seq_length = _MAX_SEQ
        except Exception:
            pass
    except Exception:
        model = None
    return model


def _truncate_texts(texts: list, max_tokens: int = 0) -> list:
    """Truncate a list of texts so each fits within the model's token limit."""
    _ensure_embedding_model()
    if not model or not texts:
        return texts
    limit = max_tokens if max_tokens > 0 else _MAX_SEQ - 2
    try:
        tok = model.tokenizer
        result = []
        for t in texts:
            ids = tok.encode(t or "", add_special_tokens=False, truncation=False)
            if len(ids) <= limit:
                result.append(t)
            else:
                result.append(tok.decode(ids[:limit], skip_special_tokens=True))
        return result
    except Exception:
        # Fallback: char-level truncation
        return [t[:limit * 3] if len(t) > limit * 3 else t for t in texts]


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
    if not insights:
        return []
    _ensure_embedding_model()
    if not model:
        return []
    texts = [
        f"{i.get('text')} | Tags: {i.get('type_tag')}, {i.get('journey_stage')}, {i.get('persona')}"
        for i in insights
    ]
    texts = _truncate_texts(texts)
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
    _ensure_embedding_model()
    if not model:
        return (False, 0.0) if return_score else False
    if len(cluster) <= 2:
        return (True, 1.0) if return_score else True
    texts = _truncate_texts([i["text"] for i in cluster])
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


def _best_samples(cluster, n=8, workstream_name=""):
    """Pick the most representative, highest-engagement posts for GPT summarization.
    Prioritizes topical complaints and feature requests with high engagement scores."""
    def _is_topical(item):
        return _is_topical_for_workstream(item, workstream_name)
    
    # Separate topical complaints/feature requests from rest
    topical_actionable = [i for i in cluster if _is_topical(i) and (
        i.get("brand_sentiment") in ("Complaint", "Negative") or
        (i.get("taxonomy", {}) or {}).get("type") == "Feature Request")]
    topical_rest = [i for i in cluster if _is_topical(i) and i not in topical_actionable]
    all_actionable = [i for i in cluster if i.get("brand_sentiment") in ("Complaint", "Negative")]
    
    # Sort each by engagement
    topical_actionable.sort(key=lambda x: x.get("score", 0), reverse=True)
    topical_rest.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_actionable.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Priority: topical actionable > topical any > all actionable
    samples = topical_actionable[:min(n - 2, len(topical_actionable))]
    samples += topical_rest[:max(0, n - len(samples) - 1)]
    if len(samples) < n:
        # Fill with any actionable as fallback
        seen = set(id(s) for s in samples)
        for i in all_actionable:
            if id(i) not in seen:
                samples.append(i)
                seen.add(id(i))
            if len(samples) >= n:
                break
    return samples[:n]


def generate_cluster_metadata(cluster, workstream_name=""):
    """
    Uses GPT to summarize a cluster into Title / Theme / Problem.
    Samples highest-engagement actionable posts, not first 6.
    """
    if client is None:
        return {
            "title": "Untitled Cluster",
            "theme": "General",
            "problem": "OpenAI client not configured.",
        }

    samples = _best_samples(cluster, n=8, workstream_name=workstream_name)
    combined = "\n---\n".join(i.get("text", "")[:300] for i in samples)
    
    workstream_ctx = ""
    if workstream_name:
        ws_kws = _WORKSTREAM_KEYWORDS.get(workstream_name, [])
        kw_examples = ", ".join(ws_kws[:6]) if ws_kws else workstream_name
        workstream_ctx = (
            f"\nWORKSTREAM CATEGORY: {workstream_name}\n"
            f"The problem statement MUST specifically address {workstream_name}.\n"
            f"Use domain-specific terms like: {kw_examples}.\n"
            f"Do NOT write generic complaints. Focus on the specific {workstream_name} pain points.\n"
        )
    
    prompt = (
        f"You are a senior product manager at eBay Collectibles reviewing user feedback grouped under a strategic workstream.\n"
        f"{workstream_ctx}"
        f"For the following grouped posts, generate:\n"
        f"1. A concise title (max 10 words) describing the core problem\n"
        f"2. A theme tag\n"
        f"3. A clear, specific problem statement (2-3 sentences) that could go in a PRD. "
        f"The problem statement MUST use terminology specific to {workstream_name or 'the workstream'}. Focus on user pain points, not emotional stories.\n"
        f"\nPosts:\n{combined}\n\nFormat your response as:\nTitle: ...\nTheme: ...\nProblem: ..."
    )
    try:
        response = client.chat.completions.create(
            model=_get_model_setting("OPENAI_MODEL_CLUSTER_META", _get_model_setting("OPENAI_MODEL_SCREENER", "gpt-4o-mini")),
            messages=[
                {"role": "system", "content": "You are a senior product strategist."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_completion_tokens=250,
            timeout=30,
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


_WORKSTREAM_KEYWORDS = {
    "Vault & Storage Trust": ["vault", "vaulted", "withdraw", "vaulting", "storage", "in-gate", "psa vault"],
    "Authentication & Grading Confidence": ["grading", "graded", "authentication", "authenticity", "counterfeit", "fake", "psa", "bgs", "sgc", "cgc", "misgrade"],
    "Competitive Positioning": ["whatnot", "fanatics", "heritage", "vinted", "beckett", "competitor", "switched to", "leaving ebay"],
    "Seller Economics & Fees": ["fee", "fees", "final value", "fvf", "take rate", "commission", "seller fee", "insertion fee", "promoted listing cost"],
    "Payment & Checkout Friction": ["checkout", "payment method", "payment failed", "wire transfer", "managed payments", "payout", "payouts", "funds held", "payment hold", "can't pay", "unpaid item", "payment processing"],
    "Customer Service & Support": ["customer service", "customer support", "support team", "chat bot", "ai bot", "can't reach", "call center", "live agent", "support ticket", "ebay support"],
    "Shipping & Fulfillment": ["shipping", "delivery", "tracking", "lost package", "damaged", "return", "returns", "refund", "inad", "standard envelope", "usps", "ups", "fedex"],
    "Pricing & Valuation Tools": ["price guide", "card ladder", "scan to price", "market value", "worth", "value", "comps"],
    "Live Commerce & Breaks": ["live break", "case break", "box break", "live stream", "ebay live", "whatnot live"],
    "Instant Liquidity & Buyback": ["instant offer", "buyback", "buy back", "cash out", "sell now", "psa offers", "courtyard", "arena club"],
    "Subsidiary Ecosystem": ["goldin", "tcgplayer", "tcg player", "tcg"],
    "Trust & Safety": ["scam", "fraud", "stolen", "chargeback", "buyer abuse", "seller protection"],
    "Search & Discovery": ["search", "best match", "visibility", "promoted listing", "no views", "not showing up", "filter", "recommend"],
    "Seller Tools & App Experience": ["seller hub", "app crash", "app bug", "listing tool", "bulk listing", "mobile app"],
    "Collector Community & Hobby": ["collection", "pulled", "pull", "mail day", "haul", "hobby", "lcs", "card show"],
}

_WORKSTREAM_TOPIC_TAGS = {
    "Vault & Storage Trust": ["vault", "vault friction"],
    "Authentication & Grading Confidence": ["trust issue", "counterfeit concern", "grading complaint"],
    "Competitive Positioning": ["competitive churn"],
    "Seller Economics & Fees": ["fees/pricing", "fee frustration", "upi"],
    "Payment & Checkout Friction": ["payments", "payouts/holds"],
    "Shipping & Fulfillment": ["shipping concern", "tracking confusion", "returns/policy"],
    "Pricing & Valuation Tools": ["price guide"],
    "Live Commerce & Breaks": ["live shopping", "case break / repack"],
    "Instant Liquidity & Buyback": ["instant offers / liquidity", "instant offers"],
    "Search & Discovery": ["search/relevancy"],
    "Trust & Safety": ["fraud concern"],
    "Subsidiary Ecosystem": ["consignment/auctions"],
}

_WORKSTREAM_FLAG_FIELDS = {
    "Vault & Storage Trust": ["is_vault_signal"],
    "Authentication & Grading Confidence": ["is_ag_signal", "is_psa_turnaround"],
    "Seller Economics & Fees": ["is_fees_concern", "_upi_flag"],
    "Payment & Checkout Friction": ["_payment_issue"],
    "Shipping & Fulfillment": ["is_shipping_issue", "is_refund_issue"],
    "Pricing & Valuation Tools": ["is_price_guide_signal"],
    "Instant Liquidity & Buyback": ["_liquidity_signal"],
}


def _keyword_in_text(text, keyword):
    """Match keywords as whole words where possible to avoid false positives (e.g., 'fee' in 'feedback')."""
    if not keyword:
        return False
    if any(ch in keyword for ch in ["/", "-"]):
        return keyword in text
    if " " in keyword:
        return re.search(r"\b" + re.escape(keyword) + r"\b", text) is not None
    return re.search(r"\b" + re.escape(keyword) + r"\b", text) is not None


def _is_topical_for_workstream(item, workstream_name):
    ws_keywords = _WORKSTREAM_KEYWORDS.get(workstream_name, [])
    ws_topics = _WORKSTREAM_TOPIC_TAGS.get(workstream_name, [])
    ws_flags = _WORKSTREAM_FLAG_FIELDS.get(workstream_name, [])

    text = (item.get("text", "") + " " + item.get("title", "")).lower()
    if ws_keywords and any(_keyword_in_text(text, kw) for kw in ws_keywords):
        if workstream_name == "Vault & Storage Trust":
            if not any(ctx in text for ctx in ["psa", "ebay", "card", "graded", "grading", "storage", "consignment"]):
                return False
        return True

    if ws_topics:
        item_topics = [t.lower() for t in (item.get("topic_focus") or item.get("topic_focus_list") or [])]
        if any(t in item_topics for t in ws_topics):
            return True

    if ws_flags and any(item.get(flag) for flag in ws_flags):
        return True

    if workstream_name == "Competitive Positioning" and item.get("mentions_competitor"):
        return True

    if workstream_name == "Subsidiary Ecosystem":
        comps = [c.lower() for c in (item.get("mentions_competitor") or [])]
        if any(c in ("tcgplayer", "goldin") for c in comps):
            return True
        source = (item.get("source", "") or "").lower()
        if "tcgplayer" in source or "goldin" in source:
            return True

    if not (ws_keywords or ws_topics or ws_flags):
        return True

    return False


def synthesize_cluster(cluster, workstream_name=""):
    meta = generate_cluster_metadata(cluster, workstream_name=workstream_name)
    brand = cluster[0].get("target_brand") or "Unknown"
    type_tag = cluster[0].get("type_tag") or "Insight"
    
    # Pick representative quotes that are RELEVANT to the workstream topic
    ws_keywords = _WORKSTREAM_KEYWORDS.get(workstream_name, [])

    def _is_keyword_topical(item):
        if not ws_keywords:
            return True
        text = (item.get("text", "") + " " + item.get("title", "")).lower()
        return any(_keyword_in_text(text, kw) for kw in ws_keywords)

    def _extract_snippet(item, max_len=220):
        """Extract a preview snippet centered on the first workstream keyword.
        Falls back to the start of the text if no keyword is present.
        """
        title = (item.get("title", "") or "").strip()
        body = (item.get("text", "") or "").strip()
        text = (title + ". " + body).strip(". ") if title else body
        if not text:
            return ""
        if not ws_keywords:
            return text[:max_len]

        text_lower = text.lower()
        for kw in ws_keywords:
            idx = text_lower.find(kw)
            if idx != -1:
                start = max(0, idx - 90)
                end = min(len(text), idx + 130)
                snippet = text[start:end].strip()
                if start > 0:
                    snippet = "…" + snippet
                if end < len(text):
                    snippet = snippet + "…"
                return snippet[:max_len]
        return text[:max_len]

    def _is_topical(item):
        return _is_topical_for_workstream(item, workstream_name)
    
    # First: keyword-topical complaints sorted by engagement
    topical_complaints = sorted(
        [i for i in cluster if i.get("brand_sentiment") in ("Complaint", "Negative") and _is_keyword_topical(i)],
        key=lambda x: x.get("score", 0), reverse=True
    )
    # Second: keyword-topical posts of any sentiment
    topical_any = sorted(
        [i for i in cluster if _is_keyword_topical(i)],
        key=lambda x: x.get("score", 0), reverse=True
    )
    # Third fallback: highest engagement regardless
    all_by_engagement = sorted(cluster, key=lambda x: x.get("score", 0), reverse=True)
    
    # Merge in priority order, deduplicate (only fall back to non-topical if none exist)
    candidates = topical_complaints + topical_any
    if not candidates:
        # Fallback to broader topicality (tags/flags/competitor) before non-topical
        broader = sorted(
            [i for i in cluster if _is_topical(i)],
            key=lambda x: x.get("score", 0), reverse=True
        )
        candidates = broader or all_by_engagement
    seen_fps = set()
    unique_quotes = []
    for i in candidates:
        fp = i.get("fingerprint", i.get("text", "")[:50])
        if fp not in seen_fps:
            seen_fps.add(fp)
            unique_quotes.append(i)
        if len(unique_quotes) >= 3:
            break
    quotes = [f"- _{_extract_snippet(i)}_" for i in unique_quotes[:3]]

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
    """Map each insight to an exec-actionable workstream.
    
    These are designed as workstreams an eBay Collectibles VP would assign
    to a PM or team lead — each one is a deliverable initiative, not a
    generic topic bucket.
    """
    text = (insight.get("text", "") + " " + insight.get("title", "")).lower()
    subtag = (insight.get("type_subtag") or insight.get("subtag") or "").lower()
    topics = [t.lower() for t in (insight.get("topic_focus") or insight.get("topic_focus_list") or [])]
    competitors = [c.lower() for c in (insight.get("mentions_competitor") or [])]
    partners = [p.lower() for p in (insight.get("mentions_ecosystem_partner") or [])]

    # ── 1. Vault & Storage Trust ──
    # Owner: Vault PM. Covers: PSA Vault, eBay Vault, withdrawal, transfer, vaulting UX
    if (insight.get("is_vault_signal") or "vault" in text or
        any(t in topics for t in ["vault", "vault friction"])):
        return "Vault & Storage Trust"

    # ── 2. Authentication & Grading Confidence ──
    # Owner: AG PM. Covers: Authenticity Guarantee, grading disputes, PSA/BGS turnaround, counterfeit
    if (insight.get("is_ag_signal") or insight.get("is_psa_turnaround") or
        "authenticity guarantee" in text or "authentication" in text or
        ("grading" in text and any(g in text for g in ["psa", "bgs", "sgc", "cgc"])) or
        "counterfeit" in text or "fake card" in text or
        any(t in topics for t in ["trust issue", "counterfeit concern", "grading complaint"])):
        return "Authentication & Grading Confidence"

    # ── 3. Competitive Positioning ──
    # Owner: Strategy. Covers: Whatnot, Fanatics, Heritage, Vinted, Beckett, competitive churn
    if (competitors or
        any(c in text for c in ["whatnot", "fanatics", "heritage auction", "vinted", "beckett", "stockx"]) or
        any(t in topics for t in ["competitive churn"]) or
        "switched to" in text or "leaving ebay" in text or "moving to" in text):
        return "Competitive Positioning"

    # ── 4. Seller Economics & Fees ──
    # Owner: Seller Experience PM. Covers: fees, take rate, promoted listings cost, commission structures
    _fee_keywords = ["fee", "fees", "final value", "fvf", "take rate", "commission",
                     "promoted listing cost", "seller fee", "insertion fee"]
    if (insight.get("is_fees_concern") or insight.get("_upi_flag") or
        any(t in topics for t in ["fees/pricing", "fee frustration", "upi"]) or
        any(w in text for w in _fee_keywords)):
        return "Seller Economics & Fees"

    # ── 4b. Payment & Checkout Friction ──
    # Owner: Payments PM. Covers: checkout errors, payment method issues, wire transfer,
    # managed payments setup, payout delays, funds held, buyer can't pay, seller can't get paid
    _payment_friction_keywords = ["checkout", "payment method", "payment failed", "failed payment",
                                   "can't pay", "won't accept", "wire transfer", "managed payments",
                                   "payout", "payouts", "payout delay", "funds held", "payment hold",
                                   "payment not going", "checkout error", "payment issue",
                                   "unpaid item", "buyer didn't pay", "didn't pay",
                                   "payment processing", "payment problem"]
    _fraud_scam_keywords = ["scam", "fraud", "fake", "counterfeit", "stolen", "chargeback"]
    _has_payment_text = any(w in text for w in _payment_friction_keywords)
    _has_fraud_text = any(w in text for w in _fraud_scam_keywords)
    
    if _has_payment_text and not _has_fraud_text:
        return "Payment & Checkout Friction"
    if (insight.get("_payment_issue") or any(t in topics for t in ["payments", "payouts/holds"])):
        if _has_fraud_text:
            pass  # Let fall through to Trust & Safety
        else:
            return "Payment & Checkout Friction"

    # ── 5. Shipping & Fulfillment ──
    # Owner: Shipping PM. Covers: shipping damage, tracking, standard envelope, international shipping, returns logistics
    if (insight.get("is_shipping_issue") or insight.get("is_refund_issue") or
        any(t in topics for t in ["shipping concern", "tracking confusion", "returns/policy"]) or
        any(w in text for w in ["shipping", "tracking", "lost package", "damaged in transit",
                                 "standard envelope", "return", "refund", "inad"])):
        return "Shipping & Fulfillment"

    # ── 6. Pricing & Valuation Tools ──
    # Owner: Price Guide PM. Covers: Price Guide, Card Ladder, scan to price, comps, market value
    if (insight.get("is_price_guide_signal") or
        any(t in topics for t in ["price guide"]) or
        any(w in text for w in ["price guide", "card ladder", "scan to price", "market value",
                                 "what is it worth", "comps", "card value"])):
        return "Pricing & Valuation Tools"

    # ── 7. Live Commerce & Breaks ──
    # Owner: eBay Live PM. Covers: live breaks, case breaks, streaming, eBay Live
    if (any(t in topics for t in ["live shopping", "case break / repack"]) or
        any(w in text for w in ["live break", "case break", "box break", "live shopping",
                                 "ebay live", "live stream", "card break"])):
        return "Live Commerce & Breaks"

    # ── 8. Instant Liquidity & Buyback ──
    # Owner: Marketplace Innovation PM. Covers: instant offers, buyback, PSA Offers, Courtyard, cash out
    if (insight.get("_liquidity_signal") or
        any(t in topics for t in ["instant offers / liquidity", "instant offers"]) or
        any(w in text for w in ["instant offer", "buyback", "cash out", "sell now",
                                 "psa offers", "courtyard", "arena club"])):
        return "Instant Liquidity & Buyback"

    # ── 9. Subsidiary Ecosystem (Goldin & TCGPlayer) ──
    # Owner: Subsidiary Integration PM. Covers: Goldin, TCGPlayer, cross-platform synergy
    if (any(w in text for w in ["goldin", "tcgplayer", "tcg player"]) or
        any(t in topics for t in ["consignment/auctions"]) and any(w in text for w in ["goldin", "heritage"])):
        return "Subsidiary Ecosystem"

    # ── 10. Trust & Safety ──
    # Owner: Trust & Safety. Covers: scams, fraud, seller protection, buyer abuse, INAD abuse
    if (any(t in topics for t in ["fraud concern"]) or
        any(w in text for w in ["scam", "fraud", "buyer abuse", "seller protection",
                                 "chargeback", "fake buyer", "stolen"])):
        return "Trust & Safety"

    # ── 11. Customer Service & Support ──
    # Owner: CX PM. Covers: AI bot complaints, can't reach human, chat support, phone support
    if any(w in text for w in ["customer service", "customer support", "support team",
                                "chat bot", "ai bot", "can't reach", "no response",
                                "call center", "help desk", "live agent", "talk to a human",
                                "automated response", "support ticket", "ebay support"]):
        return "Customer Service & Support"

    # ── 12. Search & Discovery ──
    # Owner: Search PM. Covers: search relevancy, Best Match, visibility, promoted listings effectiveness
    if (any(t in topics for t in ["search/relevancy"]) or
        any(w in text for w in ["search", "best match", "cassini", "no views", "visibility",
                                 "not showing up", "promoted listing"])):
        return "Search & Discovery"

    # ── 13. Seller Tools & App Experience ──
    # Owner: Seller Hub PM. Covers: Seller Hub, app bugs, listing tools, mobile experience
    if (any(w in text for w in ["seller hub", "app crash", "app bug", "listing tool",
                                 "mobile app", "app update", "app glitch"])):
        return "Seller Tools & App Experience"

    # ── Route remaining subtag-tagged posts to appropriate workstreams ──
    if subtag in ("grading complaint", "speed issue", "trust issue", "counterfeit concern"):
        return "Authentication & Grading Confidence"
    if subtag in ("delays", "tracking confusion", "refund issue", "shipping concern"):
        return "Shipping & Fulfillment"
    if subtag in ("fee frustration",):
        return "Seller Economics & Fees"
    if subtag in ("fraud concern",):
        return "Trust & Safety"
    if subtag in ("payments",) and any(w in text for w in ["scam", "fraud", "fake", "stolen"]):
        return "Trust & Safety"

    # ── 14. Collector Community & Hobby ──
    # NOT a workstream to "fix" — this is organic community content (pulls, collections, trades).
    # Kept separate from General so execs can see community health and engagement.
    community_terms = ["pull", "pulled", "just got", "collection", "my collection", "lcs",
                       "card show", "hobby", "mail day", "haul", "rip", "opening",
                       "what do you think", "worth grading", "first time",
                       "inheritance", "inherited", "found these", "my dad",
                       "my grandfather", "my grandma", "started collecting"]
    if any(ct in text for ct in community_terms):
        return "Collector Community & Hobby"

    return "General Platform Feedback"


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
