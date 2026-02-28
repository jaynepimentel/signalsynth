# evaluation_harness.py — Gold set labeling, precision/recall, cluster quality, citation faithfulness
#
# Usage:
#   python -m components.evaluation_harness create-gold --input precomputed_insights.json --size 200
#   python -m components.evaluation_harness evaluate --gold evaluation/gold_set.json --input precomputed_insights.json
#   python -m components.evaluation_harness cluster-quality --clusters precomputed_clusters.json

import json
import os
import random
import hashlib
import argparse
import re
from datetime import datetime
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
EVAL_DIR = "evaluation"
GOLD_SET_PATH = os.path.join(EVAL_DIR, "gold_set.json")
EVAL_RESULTS_PATH = os.path.join(EVAL_DIR, "eval_results.json")


# ---------------------------------------------------------------------------
# Gold Set Creation — stratified sampling for manual labeling
# ---------------------------------------------------------------------------

def create_gold_set(
    insights: List[Dict[str, Any]],
    size: int = 200,
    output_path: str = GOLD_SET_PATH,
) -> str:
    """
    Create a stratified sample for manual labeling.
    Stratifies by source, sentiment, and taxonomy type to ensure coverage.
    Outputs a JSON file with fields for human annotation.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Stratify by source × sentiment
    buckets: Dict[str, List[Dict]] = defaultdict(list)
    for i in insights:
        source = i.get("source", "Unknown")
        sentiment = i.get("brand_sentiment", "Neutral")
        key = f"{source}|{sentiment}"
        buckets[key].append(i)

    # Proportional sampling from each bucket
    sampled: List[Dict] = []
    total = len(insights)
    for key, items in buckets.items():
        proportion = len(items) / max(total, 1)
        n = max(1, round(proportion * size))
        chosen = random.sample(items, min(n, len(items)))
        sampled.extend(chosen)

    # Trim or pad to target size
    random.shuffle(sampled)
    sampled = sampled[:size]

    # Build gold set entries with annotation fields
    gold_entries = []
    for idx, item in enumerate(sampled):
        text = item.get("text", "")
        gold_entries.append({
            "gold_id": idx,
            "fingerprint": item.get("fingerprint", hashlib.md5(text.encode()).hexdigest()),
            "text": text[:500],
            "title": item.get("title", "")[:200],
            "source": item.get("source", "Unknown"),
            "url": item.get("url", ""),
            # Pipeline-assigned labels (to evaluate)
            "pipeline_sentiment": item.get("brand_sentiment", ""),
            "pipeline_taxonomy_type": (item.get("taxonomy", {}) or {}).get("type", item.get("type_tag", "")),
            "pipeline_taxonomy_topic": (item.get("taxonomy", {}) or {}).get("topic", item.get("subtag", "")),
            "pipeline_persona": item.get("persona", ""),
            "pipeline_relevant": True,  # passed the filter
            "pipeline_signal_strength": item.get("signal_strength", item.get("score", 0)),
            # Human annotation fields (to be filled manually)
            "human_relevant": None,           # True/False — is this a real collectibles signal?
            "human_sentiment": None,          # Positive/Negative/Neutral
            "human_taxonomy_type": None,      # Complaint/Feature Request/Praise/Question/Churn Signal/...
            "human_taxonomy_topic": None,     # Vault/Grading/Fees/Shipping/...
            "human_persona": None,            # Power Seller/Collector/New Seller/...
            "human_notes": "",                # Free-text notes
            "labeled": False,                 # Set to True once human labels are complete
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "created_at": datetime.utcnow().isoformat() + "Z",
                "total_pool": total,
                "sample_size": len(gold_entries),
                "sources_represented": len(set(e["source"] for e in gold_entries)),
                "instructions": (
                    "For each entry, fill in the human_* fields and set labeled=True. "
                    "human_relevant: is this a meaningful collectibles/marketplace signal? "
                    "human_sentiment: Positive/Negative/Neutral. "
                    "human_taxonomy_type: Complaint/Feature Request/Praise/Question/Churn Signal/Bug Report/General. "
                    "human_taxonomy_topic: the primary topic (Vault, Grading, Fees, Shipping, etc). "
                    "human_persona: Power Seller/Collector/Investor/New Seller/Casual Buyer/General."
                ),
            },
            "entries": gold_entries,
        }, f, ensure_ascii=False, indent=2)

    print(f"[EVAL] Created gold set with {len(gold_entries)} entries at {output_path}")
    print(f"  Sources: {len(set(e['source'] for e in gold_entries))} unique")
    print(f"  Sentiments: {Counter(e['pipeline_sentiment'] for e in gold_entries).most_common()}")
    return output_path


# ---------------------------------------------------------------------------
# Evaluation — compare pipeline labels against gold set
# ---------------------------------------------------------------------------

def _accuracy(predicted: List[str], actual: List[str]) -> float:
    if not actual:
        return 0.0
    correct = sum(1 for p, a in zip(predicted, actual) if p == a)
    return round(correct / len(actual), 4)


def _precision_recall_f1(
    predicted: List[bool], actual: List[bool]
) -> Dict[str, float]:
    tp = sum(1 for p, a in zip(predicted, actual) if p and a)
    fp = sum(1 for p, a in zip(predicted, actual) if p and not a)
    fn = sum(1 for p, a in zip(predicted, actual) if not p and a)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn,
    }


def evaluate_pipeline(
    gold_path: str = GOLD_SET_PATH,
    output_path: str = EVAL_RESULTS_PATH,
) -> Dict[str, Any]:
    """
    Compare pipeline-assigned labels against human-labeled gold set.
    Returns precision, recall, F1 for relevance filter and accuracy for taxonomy.
    """
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    entries = [e for e in gold_data["entries"] if e.get("labeled")]
    if not entries:
        print("[EVAL] No labeled entries found. Label entries first, then re-run.")
        return {}

    print(f"[EVAL] Evaluating against {len(entries)} labeled entries...")

    results: Dict[str, Any] = {
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "labeled_count": len(entries),
    }

    # 1. Relevance filter precision/recall
    if all(e.get("human_relevant") is not None for e in entries):
        pred_relevant = [bool(e["pipeline_relevant"]) for e in entries]
        actual_relevant = [bool(e["human_relevant"]) for e in entries]
        results["relevance"] = _precision_recall_f1(pred_relevant, actual_relevant)
        print(f"  Relevance: P={results['relevance']['precision']:.2%} R={results['relevance']['recall']:.2%} F1={results['relevance']['f1']:.2%}")

    # 2. Sentiment accuracy
    sentiment_entries = [e for e in entries if e.get("human_sentiment")]
    if sentiment_entries:
        pred_sent = [e["pipeline_sentiment"] for e in sentiment_entries]
        actual_sent = [e["human_sentiment"] for e in sentiment_entries]
        results["sentiment_accuracy"] = _accuracy(pred_sent, actual_sent)
        # Per-class breakdown
        classes = sorted(set(actual_sent))
        per_class = {}
        for cls in classes:
            cls_pred = [p == cls for p in pred_sent]
            cls_actual = [a == cls for a in actual_sent]
            per_class[cls] = _precision_recall_f1(cls_pred, cls_actual)
        results["sentiment_per_class"] = per_class
        print(f"  Sentiment accuracy: {results['sentiment_accuracy']:.2%}")

    # 3. Taxonomy type accuracy
    type_entries = [e for e in entries if e.get("human_taxonomy_type")]
    if type_entries:
        pred_type = [e["pipeline_taxonomy_type"] for e in type_entries]
        actual_type = [e["human_taxonomy_type"] for e in type_entries]
        results["taxonomy_type_accuracy"] = _accuracy(pred_type, actual_type)
        print(f"  Taxonomy type accuracy: {results['taxonomy_type_accuracy']:.2%}")

    # 4. Taxonomy topic accuracy
    topic_entries = [e for e in entries if e.get("human_taxonomy_topic")]
    if topic_entries:
        pred_topic = [e["pipeline_taxonomy_topic"] for e in topic_entries]
        actual_topic = [e["human_taxonomy_topic"] for e in topic_entries]
        results["taxonomy_topic_accuracy"] = _accuracy(pred_topic, actual_topic)
        print(f"  Taxonomy topic accuracy: {results['taxonomy_topic_accuracy']:.2%}")

    # 5. Persona accuracy
    persona_entries = [e for e in entries if e.get("human_persona")]
    if persona_entries:
        pred_persona = [e["pipeline_persona"] for e in persona_entries]
        actual_persona = [e["human_persona"] for e in persona_entries]
        results["persona_accuracy"] = _accuracy(pred_persona, actual_persona)
        print(f"  Persona accuracy: {results['persona_accuracy']:.2%}")

    # Save results
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[EVAL] Results saved to {output_path}")
    return results


# ---------------------------------------------------------------------------
# Cluster Quality Evaluation
# ---------------------------------------------------------------------------

def evaluate_cluster_quality(
    clusters_path: str = "precomputed_clusters.json",
) -> Dict[str, Any]:
    """
    Evaluate cluster quality using intrinsic metrics:
    - Intra-cluster coherence (avg pairwise text similarity via Jaccard on tokens)
    - Cluster size distribution
    - Topic purity (how homogeneous are taxonomy labels within clusters)
    """
    with open(clusters_path, "r", encoding="utf-8") as f:
        cdata = json.load(f)

    clusters = cdata.get("clusters", [])
    if not clusters:
        print("[EVAL] No clusters found.")
        return {}

    results = {
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "cluster_count": len(clusters),
    }

    sizes = []
    purities = []
    coherences = []

    for cl in clusters:
        items = cl.get("insights", [])
        sizes.append(len(items))

        # Topic purity: fraction of items sharing the most common topic
        topics = []
        for item in items:
            tax = item.get("taxonomy") if isinstance(item.get("taxonomy"), dict) else {}
            topic = tax.get("topic") or item.get("subtag") or "General"
            topics.append(topic)
        if topics:
            most_common_count = Counter(topics).most_common(1)[0][1]
            purity = most_common_count / len(topics)
            purities.append(purity)

        # Token-based coherence (Jaccard similarity of informative tokens)
        if len(items) >= 2:
            stopwords = {
                "the", "a", "an", "and", "or", "to", "for", "of", "in", "on",
                "with", "is", "are", "was", "were", "it", "that", "this", "i",
                "you", "my", "we", "they", "he", "she", "as", "at", "be", "by",
                "from", "if", "but", "so", "not", "no", "do", "did", "does",
                "ebay", "item", "seller", "buyer",
            }
            token_sets = []
            for item in items[:20]:  # sample for large clusters
                text = (item.get("text", "") + " " + item.get("title", "")).lower()
                tokens = set(re.findall(r"[a-z0-9]+", text)) - stopwords
                if tokens:
                    token_sets.append(tokens)

            if len(token_sets) >= 2:
                jaccards = []
                pairs = min(50, len(token_sets) * (len(token_sets) - 1) // 2)
                for idx_i in range(len(token_sets)):
                    for idx_j in range(idx_i + 1, len(token_sets)):
                        inter = token_sets[idx_i] & token_sets[idx_j]
                        union = token_sets[idx_i] | token_sets[idx_j]
                        if union:
                            jaccards.append(len(inter) / len(union))
                        if len(jaccards) >= pairs:
                            break
                    if len(jaccards) >= pairs:
                        break
                if jaccards:
                    coherences.append(float(np.mean(jaccards)))

    results["size_distribution"] = {
        "min": int(min(sizes)) if sizes else 0,
        "max": int(max(sizes)) if sizes else 0,
        "mean": round(float(np.mean(sizes)), 1) if sizes else 0,
        "median": round(float(np.median(sizes)), 1) if sizes else 0,
    }
    results["topic_purity"] = {
        "mean": round(float(np.mean(purities)), 4) if purities else 0,
        "min": round(float(min(purities)), 4) if purities else 0,
        "clusters_above_80pct": sum(1 for p in purities if p >= 0.8),
    }
    results["token_coherence"] = {
        "mean": round(float(np.mean(coherences)), 4) if coherences else 0,
        "min": round(float(min(coherences)), 4) if coherences else 0,
        "max": round(float(max(coherences)), 4) if coherences else 0,
    }

    print(f"[EVAL] Cluster quality for {len(clusters)} clusters:")
    print(f"  Sizes: min={results['size_distribution']['min']}, max={results['size_distribution']['max']}, mean={results['size_distribution']['mean']}")
    print(f"  Topic purity: mean={results['topic_purity']['mean']:.2%}, {results['topic_purity']['clusters_above_80pct']}/{len(clusters)} above 80%")
    print(f"  Token coherence: mean={results['token_coherence']['mean']:.4f}")

    return results


# ---------------------------------------------------------------------------
# Citation Faithfulness Scoring
# ---------------------------------------------------------------------------

def score_citation_faithfulness(
    response_text: str,
    source_texts: List[str],
) -> Dict[str, Any]:
    """
    Evaluate how well an Ask AI response is grounded in source signals.
    Checks:
    - How many claims have [S#] citations
    - How many cited sources actually exist in the provided context
    - Ratio of cited vs uncited substantive sentences
    """
    # Extract all [S#] citations from response
    citations = re.findall(r"\[S(\d+)\]", response_text)
    cited_indices = set(int(c) for c in citations)
    valid_citations = set(i for i in cited_indices if 1 <= i <= len(source_texts))
    invalid_citations = cited_indices - valid_citations

    # Count substantive sentences (non-header, non-empty, not just formatting)
    sentences = [
        s.strip() for s in re.split(r"[.!?]\s", response_text)
        if len(s.strip()) > 20
        and not s.strip().startswith("#")
        and not s.strip().startswith("|")
        and not s.strip().startswith("-")
    ]
    cited_sentences = [s for s in sentences if re.search(r"\[S\d+\]", s)]

    total_sentences = len(sentences)
    cited_count = len(cited_sentences)
    faithfulness_ratio = cited_count / max(total_sentences, 1)

    return {
        "total_citations": len(citations),
        "unique_sources_cited": len(valid_citations),
        "invalid_citations": len(invalid_citations),
        "total_substantive_sentences": total_sentences,
        "cited_sentences": cited_count,
        "faithfulness_ratio": round(faithfulness_ratio, 4),
        "source_coverage": round(len(valid_citations) / max(len(source_texts), 1), 4),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SignalSynth Evaluation Harness")
    sub = parser.add_subparsers(dest="command")

    # create-gold
    p_gold = sub.add_parser("create-gold", help="Create a gold set for manual labeling")
    p_gold.add_argument("--input", default="precomputed_insights.json", help="Input insights JSON")
    p_gold.add_argument("--size", type=int, default=200, help="Number of entries to sample")
    p_gold.add_argument("--output", default=GOLD_SET_PATH, help="Output path")

    # evaluate
    p_eval = sub.add_parser("evaluate", help="Evaluate pipeline against labeled gold set")
    p_eval.add_argument("--gold", default=GOLD_SET_PATH, help="Path to labeled gold set")
    p_eval.add_argument("--output", default=EVAL_RESULTS_PATH, help="Output path for results")

    # cluster-quality
    p_clust = sub.add_parser("cluster-quality", help="Evaluate cluster quality metrics")
    p_clust.add_argument("--clusters", default="precomputed_clusters.json", help="Clusters JSON")

    args = parser.parse_args()

    if args.command == "create-gold":
        with open(args.input, "r", encoding="utf-8") as f:
            insights = json.load(f)
        create_gold_set(insights, size=args.size, output_path=args.output)

    elif args.command == "evaluate":
        evaluate_pipeline(gold_path=args.gold, output_path=args.output)

    elif args.command == "cluster-quality":
        evaluate_cluster_quality(clusters_path=args.clusters)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
