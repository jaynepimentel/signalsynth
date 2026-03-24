# hybrid_retrieval.py — BM25 + precomputed embeddings + RRF merge for Ask AI
#
# Replaces the handrolled substring-matching _relevance_score in app.py with:
#   1. BM25 keyword retrieval (exact match + term frequency)
#   2. Dense embedding retrieval (cosine similarity on precomputed vectors)
#   3. Reciprocal Rank Fusion (RRF) to merge both ranked lists
#   4. Source diversity cap to prevent single-source dominance
#
# Usage:
#   retriever = HybridRetriever(insights, embeddings_path="precomputed_embeddings.npy")
#   results = retriever.retrieve(query, top_k=25)

import os
import json
import re
import math
import hashlib
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

# Optional: rank_bm25 for proper BM25 scoring
try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

# Optional: sentence-transformers for query encoding at runtime
try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False


# ---------------------------------------------------------------------------
# Tokenizer for BM25
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with",
    "is", "are", "was", "were", "it", "that", "this", "i", "you", "my",
    "we", "they", "them", "he", "she", "as", "at", "be", "by", "from",
    "if", "but", "so", "not", "no", "do", "did", "does", "just", "been",
    "have", "has", "had", "would", "could", "should", "will", "can",
    "very", "really", "much", "also", "about", "all", "any", "some",
    "more", "than", "then", "there", "here", "when", "what", "which",
    "who", "how", "why", "where", "each", "every", "both", "few",
    "many", "most", "other", "these", "those", "such",
}


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer with stopword removal."""
    tokens = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", (text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# Lightweight BM25 fallback (no external dependency)
# ---------------------------------------------------------------------------

class SimpleBM25:
    """Minimal BM25 implementation for when rank_bm25 is not installed."""

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.N = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / max(self.N, 1)

        # Document frequency
        self.df: Dict[str, int] = defaultdict(int)
        for doc in corpus:
            for term in set(doc):
                self.df[term] += 1

        # Term frequency per document
        self.tf: List[Dict[str, int]] = []
        self.doc_lens: List[int] = []
        for doc in corpus:
            tf = defaultdict(int)
            for term in doc:
                tf[term] += 1
            self.tf.append(dict(tf))
            self.doc_lens.append(len(doc))

    def get_scores(self, query: List[str]) -> np.ndarray:
        scores = np.zeros(self.N)
        for term in query:
            if term not in self.df:
                continue
            idf = math.log((self.N - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1)
            for idx in range(self.N):
                tf = self.tf[idx].get(term, 0)
                dl = self.doc_lens[idx]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1))
                scores[idx] += idf * (tf * (self.k1 + 1)) / max(denom, 1e-9)
        return scores


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    *ranked_lists: List[int],
    k: int = 60,
) -> List[Tuple[int, float]]:
    """
    Merge multiple ranked lists using RRF.
    Each ranked_list is a list of document indices ordered by relevance.
    Returns list of (doc_index, rrf_score) sorted by descending score.
    """
    scores: Dict[int, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, doc_idx in enumerate(ranked):
            scores[doc_idx] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


# ---------------------------------------------------------------------------
# Precomputed Embeddings Manager
# ---------------------------------------------------------------------------

EMBEDDINGS_PATH = "precomputed_embeddings.npy"
EMBEDDINGS_META_PATH = "precomputed_embeddings_meta.json"


def precompute_embeddings(
    insights: List[Dict[str, Any]],
    model_name: str = "intfloat/e5-base-v2",
    output_path: str = EMBEDDINGS_PATH,
    meta_path: str = EMBEDDINGS_META_PATH,
    batch_size: int = 64,
) -> str:
    """
    Precompute and save embeddings for all insights.
    Run this during the pipeline step so the app doesn't need sentence-transformers at runtime.
    """
    if not HAS_ST:
        raise RuntimeError("sentence-transformers required for precomputing embeddings. pip install sentence-transformers")

    model = SentenceTransformer(model_name)

    texts = []
    fingerprints = []
    for i in insights:
        text = i.get("text", "")
        title = i.get("title", "")
        source = i.get("source", "")
        subtag = (i.get("taxonomy", {}) or {}).get("topic", i.get("subtag", ""))
        # Rich text representation for embedding
        combined = f"{title} {text} | {source} | {subtag}"
        texts.append(combined)
        fp = i.get("fingerprint", hashlib.md5(text.encode()).hexdigest())
        fingerprints.append(fp)

    print(f"[EMBED] Encoding {len(texts)} insights with {model_name}...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    np.save(output_path, embeddings)

    meta = {
        "model": model_name,
        "count": len(texts),
        "dim": embeddings.shape[1],
        "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "fingerprints": fingerprints,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"[EMBED] Saved {embeddings.shape} embeddings to {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Hybrid Retriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """
    Hybrid BM25 + dense retrieval with RRF fusion.
    Loads precomputed embeddings at startup (no sentence-transformers needed at runtime).
    Falls back gracefully to BM25-only if embeddings are unavailable.
    """

    def __init__(
        self,
        insights: List[Dict[str, Any]],
        embeddings_path: str = EMBEDDINGS_PATH,
        embeddings_meta_path: str = EMBEDDINGS_META_PATH,
    ):
        self.insights = insights
        self.n = len(insights)

        # Build BM25 index
        self._build_bm25_index()

        # Load precomputed embeddings if available
        self.embeddings: Optional[np.ndarray] = None
        self._embed_model = None
        self._load_embeddings(embeddings_path, embeddings_meta_path)

    def _build_bm25_index(self):
        """Build BM25 index over insight text + metadata fields."""
        corpus = []
        for i in self.insights:
            text = i.get("text", "")
            title = i.get("title", "")
            source = i.get("source", "")
            subtag = (i.get("taxonomy", {}) or {}).get("topic", i.get("subtag", ""))
            persona = i.get("persona", "")
            competitor = " ".join(i.get("mentions_competitor", []) or [])
            combined = f"{title} {text} {source} {subtag} {persona} {competitor}"
            corpus.append(_tokenize(combined))

        if HAS_BM25:
            self.bm25 = BM25Okapi(corpus)
        else:
            self.bm25 = SimpleBM25(corpus)

    def _load_embeddings(self, path: str, meta_path: str):
        """Load precomputed embeddings, aligning by fingerprint."""
        if not os.path.exists(path):
            # Only warn once (not on every Streamlit rerun)
            if not getattr(self.__class__, '_embed_warned', False):
                print(f"[RETRIEVAL] No precomputed embeddings at {path} — using BM25 only")
                self.__class__._embed_warned = True
            return

        try:
            self.embeddings = np.load(path)
            # Verify alignment
            if self.embeddings.shape[0] != self.n:
                # Try to align by fingerprint
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    embed_fps = meta.get("fingerprints", [])
                    insight_fps = [
                        i.get("fingerprint", hashlib.md5(i.get("text", "").encode()).hexdigest())
                        for i in self.insights
                    ]
                    # Build lookup from fingerprint → embedding row
                    fp_to_row = {fp: idx for idx, fp in enumerate(embed_fps)}
                    aligned = np.zeros((self.n, self.embeddings.shape[1]), dtype=np.float32)
                    matched = 0
                    for i, fp in enumerate(insight_fps):
                        if fp in fp_to_row:
                            aligned[i] = self.embeddings[fp_to_row[fp]]
                            matched += 1
                    self.embeddings = aligned
                    print(f"[RETRIEVAL] Aligned embeddings: {matched}/{self.n} matched by fingerprint")
                else:
                    print(f"[RETRIEVAL] Embedding count mismatch ({self.embeddings.shape[0]} vs {self.n}), using BM25 only")
                    self.embeddings = None
        except Exception as e:
            print(f"[RETRIEVAL] Failed to load embeddings: {e}")
            self.embeddings = None

    def _bm25_retrieve(self, query: str, top_k: int = 50) -> List[int]:
        """Get top-k document indices by BM25 score."""
        tokens = _tokenize(query)
        if not tokens:
            return []

        if HAS_BM25:
            scores = self.bm25.get_scores(tokens)
        else:
            scores = self.bm25.get_scores(tokens)

        top_indices = np.argsort(scores)[::-1][:top_k]
        # Filter out zero-score results
        return [int(i) for i in top_indices if scores[i] > 0]

    def _dense_retrieve(self, query: str, top_k: int = 50) -> List[int]:
        """Get top-k document indices by cosine similarity with query embedding."""
        if self.embeddings is None:
            return []

        query_embedding = self._encode_query(query)
        if query_embedding is None:
            return []

        # Cosine similarity (embeddings are pre-normalized)
        sims = self.embeddings @ query_embedding
        top_indices = np.argsort(sims)[::-1][:top_k]
        # Filter out very low similarity
        return [int(i) for i in top_indices if sims[i] > 0.1]

    def _encode_query(self, query: str) -> Optional[np.ndarray]:
        """Encode query using sentence-transformers if available, else skip."""
        if self._embed_model is not None:
            return self._embed_model.encode(query, normalize_embeddings=True)

        if HAS_ST:
            try:
                model_name = os.getenv("SS_EMBED_MODEL", "intfloat/e5-base-v2")
                self._embed_model = SentenceTransformer(model_name)
                return self._embed_model.encode(query, normalize_embeddings=True)
            except Exception:
                pass

        # If no sentence-transformers, try to approximate with precomputed
        # by finding the closest BM25 hit and using its embedding as a proxy
        if self.embeddings is not None:
            bm25_top = self._bm25_retrieve(query, top_k=5)
            if bm25_top:
                proxy = np.mean(self.embeddings[bm25_top], axis=0)
                norm = np.linalg.norm(proxy)
                if norm > 0:
                    return proxy / norm
        return None

    def _apply_signal_boosts(
        self,
        scored: List[Tuple[int, float]],
        query: str,
    ) -> List[Tuple[int, float]]:
        """Apply domain-specific boosts: signal strength, engagement, source relevance."""
        q_lower = query.lower()

        # Detect query context for targeted boosts
        is_review_q = any(t in q_lower for t in ["trustpilot", "review", "rating", "app review"])
        is_persona_q = any(t in q_lower for t in ["seller", "buyer", "collector", "investor"])
        is_competitive_q = any(t in q_lower for t in ["whatnot", "fanatics", "heritage", "competitor", "vs "])

        # Date thresholds for recency boosting
        from datetime import datetime, timedelta
        _now = datetime.now().strftime("%Y-%m-%d")
        _30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        _90d = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        _1y = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        boosted = []
        for idx, score in scored:
            insight = self.insights[idx]
            boost = 0.0

            # Signal strength boost
            sig = insight.get("signal_strength", insight.get("score", 0))
            if sig > 60:
                boost += 0.02
            elif sig > 30:
                boost += 0.01

            # Engagement boost
            eng = insight.get("score", 0)
            if eng >= 50:
                boost += 0.015
            elif eng >= 10:
                boost += 0.005

            # Date recency boost — recent signals are more actionable
            date = insight.get("post_date", "") or ""
            if date >= _30d:
                boost += 0.03   # Last 30 days: strong boost
            elif date >= _90d:
                boost += 0.015  # Last 90 days: moderate boost
            elif date >= _1y:
                boost += 0.0    # Last year: neutral
            else:
                boost -= 0.02   # Older than 1 year: penalty

            # Context-aware source boost
            source = (insight.get("source", "") or "").lower()
            text_lower = (insight.get("text", "") + " " + insight.get("title", "")).lower()
            if is_review_q and "trustpilot" in source:
                boost += 0.03
            if is_persona_q and source in ("seller community", "app reviews"):
                boost += 0.02
            if is_competitive_q:
                competitors = insight.get("mentions_competitor", [])
                if competitors:
                    boost += 0.025
                # Boost news/industry sources for competitive questions —
                # these often have score:0 but contain breaking intelligence
                _NEWS_SOURCES = {"news:", "cllct", "podcast", "industry analysis",
                                 "mantel", "whatnot", "heritage", "goldin blog",
                                 "heritage blog", "card ladder", "sports card investor"}
                if any(ns in source for ns in _NEWS_SOURCES):
                    boost += 0.035
                # If source IS the competitor being asked about, strong boost
                _COMP_NAMES = ["whatnot", "fanatics", "heritage", "goldin", "tcgplayer", "comc", "beckett", "vinted"]
                for cn in _COMP_NAMES:
                    if cn in q_lower and cn in source:
                        boost += 0.04  # Source directly from the competitor platform
                # Extra boost for breaking news signals (lawsuits, policy changes, major events)
                _BREAKING_TERMS = ["lawsuit", "class action", "sued", "gambling",
                                   "rico", "legal", "regulation", "policy change",
                                   "hot water", "reckoning", "investigation",
                                   "settlement", "fine", "penalty", "banned",
                                   "regulate", "compliance", "enforcement"]
                if any(bt in text_lower for bt in _BREAKING_TERMS):
                    boost += 0.06  # Strong boost for breaking/legal news

            boosted.append((idx, score + boost))

        return sorted(boosted, key=lambda x: -x[1])

    def _expand_query(self, query: str) -> List[str]:
        """Generate query variations for multi-query retrieval.
        
        Uses lightweight keyword expansion (no LLM call) to catch
        signals that use different vocabulary for the same concept.
        """
        q_lower = query.lower()
        expansions = [query]  # Always include original
        
        # Synonym/concept expansion map
        _EXPANSIONS = {
            "vault": "PSA vault eBay vault storage withdrawal vaulted cards",
            "authentication": "authenticity guarantee AG fake counterfeit verified",
            "grading": "PSA BGS SGC CGC slab graded submission turnaround",
            "fees": "final value fee FVF commission take rate seller fees cost to sell",
            "shipping": "tracking delivery USPS FedEx damaged in transit lost package standard envelope",
            "payment": "payout funds held managed payments checkout payment hold",
            "returns": "refund INAD item not as described money back return dispute",
            "whatnot": "Whatnot live breaks live selling card breaks gambling RICO lawsuit",
            "fanatics": "Fanatics Collect Fanatics Live Topps Panini licensing",
            "lawsuit": "class action RICO sued gambling illegal regulation legal reckoning",
            "churn": "leaving eBay switching platform done with eBay moved to quit selling",
            "price guide": "card value market comps Card Ladder scan to price pricing data",
            "trust": "scam fraud fake counterfeit stolen phishing",
            "customer service": "support agent help desk chat bot can't reach human AI bot",
        }
        
        for trigger, expansion in _EXPANSIONS.items():
            if trigger in q_lower:
                expansions.append(f"{query} {expansion}")
                break  # One expansion is usually enough
        
        return expansions[:2]  # Max 2 queries (original + 1 expansion)

    def retrieve(
        self,
        query: str,
        top_k: int = 25,
        candidate_pool: int = 50,
        max_per_source: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Main retrieval method. Returns top_k insights ranked by hybrid relevance.

        Steps:
        1. Multi-query expansion (lightweight keyword expansion)
        2. BM25 + dense retrieval for each query variation
        3. RRF merge across all results
        4. Signal quality boosts
        5. Source diversity cap
        """
        # Step 1: Multi-query expansion
        queries = self._expand_query(query)
        
        # Step 2: Retrieve for each query variation and merge
        all_bm25 = []
        all_dense = []
        for q in queries:
            all_bm25.extend(self._bm25_retrieve(q, top_k=candidate_pool))
            dense = self._dense_retrieve(q, top_k=candidate_pool)
            if dense:
                all_dense.extend(dense)
        
        # Deduplicate indices while preserving best rank
        bm25_ranked = list(dict.fromkeys(all_bm25))[:candidate_pool * 2]
        dense_ranked = list(dict.fromkeys(all_dense))[:candidate_pool * 2] if all_dense else []

        # Step 3: RRF merge
        if dense_ranked:
            fused = reciprocal_rank_fusion(bm25_ranked, dense_ranked)
        else:
            # Dense unavailable — use BM25 only with synthetic scores
            fused = [(idx, 1.0 / (60 + rank + 1)) for rank, idx in enumerate(bm25_ranked)]

        # Step 4: Apply domain boosts
        boosted = self._apply_signal_boosts(fused, query)

        # Step 5: Source diversity cap
        results = []
        source_counts: Dict[str, int] = defaultdict(int)
        for idx, score in boosted:
            if idx >= self.n:
                continue
            insight = self.insights[idx]
            src = insight.get("source", "Unknown")
            if source_counts[src] >= max_per_source:
                continue
            result = dict(insight)
            result["_retrieval_score"] = round(score, 6)
            result["_retrieval_rank"] = len(results) + 1
            results.append(result)
            source_counts[src] += 1
            if len(results) >= top_k:
                break

        return results


# ---------------------------------------------------------------------------
# CLI — precompute embeddings
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hybrid Retrieval — precompute embeddings")
    parser.add_argument("--input", default="precomputed_insights.json", help="Input insights JSON")
    parser.add_argument("--output", default=EMBEDDINGS_PATH, help="Output embeddings .npy path")
    parser.add_argument("--model", default="intfloat/e5-base-v2", help="Embedding model name")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        insights = json.load(f)

    precompute_embeddings(insights, model_name=args.model, output_path=args.output)


if __name__ == "__main__":
    main()
