# orchestrator.py — Real pipeline orchestration with sequential steps and checkpoints
#
# Replaces the passthrough run_pipeline.py with a proper DAG:
#   1. Load raw scraped data
#   2. Deduplicate (SimHash + exact prefix)
#   3. Enrich (signal scorer, GPT tags, etc.)
#   4. Precompute embeddings (for hybrid retrieval)
#   5. Cluster (subtag → DBSCAN)
#   6. Detect trends & anomalies
#   7. Save all outputs + checkpoint metadata
#
# Usage:
#   python -m pipeline.orchestrator --input data/all_scraped_posts.json
#   python -m pipeline.orchestrator --input data/all_scraped_posts.json --skip-embeddings

import os
import sys
import json
import argparse
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Step definitions
# ---------------------------------------------------------------------------

class PipelineStep:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "pending"  # pending, running, done, skipped, failed
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.stats: Dict[str, Any] = {}
        self.error: Optional[str] = None

    def start(self):
        self.status = "running"
        self.start_time = time.time()
        print(f"\n{'='*60}")
        print(f"  STEP: {self.name}")
        print(f"  {self.description}")
        print(f"{'='*60}")

    def done(self, stats: Optional[Dict] = None):
        self.status = "done"
        self.end_time = time.time()
        self.stats = stats or {}
        elapsed = self.end_time - (self.start_time or self.end_time)
        print(f"  ✅ {self.name} completed in {elapsed:.1f}s")
        if stats:
            for k, v in stats.items():
                print(f"     {k}: {v}")

    def skip(self, reason: str = ""):
        self.status = "skipped"
        print(f"  ⏭️ {self.name} skipped{': ' + reason if reason else ''}")

    def fail(self, error: str):
        self.status = "failed"
        self.end_time = time.time()
        self.error = error
        print(f"  ❌ {self.name} FAILED: {error}")

    def to_dict(self) -> Dict[str, Any]:
        elapsed = None
        if self.start_time and self.end_time:
            elapsed = round(self.end_time - self.start_time, 2)
        return {
            "name": self.name,
            "status": self.status,
            "elapsed_seconds": elapsed,
            "stats": self.stats,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    input_path: str = "data/all_scraped_posts.json",
    output_dir: str = ".",
    skip_embeddings: bool = False,
    skip_trends: bool = False,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run the full SignalSynth pipeline with checkpoints.

    Steps:
    1. Load → 2. Deduplicate → 3. Enrich → 4. Embed → 5. Cluster → 6. Trends → 7. Save
    """
    pipeline_start = time.time()
    steps: List[PipelineStep] = []

    # ── Step 1: Load raw data ──
    step1 = PipelineStep("load", "Load raw scraped posts from JSON files")
    steps.append(step1)
    step1.start()

    try:
        raw_posts = _load_scraped_data(input_path)
        if max_items and len(raw_posts) > max_items:
            raw_posts = raw_posts[:max_items]
        step1.done({"total_posts": len(raw_posts)})
    except Exception as e:
        step1.fail(str(e))
        return _make_checkpoint(steps, pipeline_start)

    # ── Step 2: Deduplicate ──
    step2 = PipelineStep("deduplicate", "Remove exact and near-duplicate posts (SimHash)")
    steps.append(step2)
    step2.start()

    try:
        from components.deduplicator import deduplicate_insights
        unique_posts, dedup_stats = deduplicate_insights(raw_posts, similarity_threshold=5)
        step2.done(dedup_stats)
    except Exception as e:
        step2.fail(str(e))
        # Fall back to raw posts
        unique_posts = raw_posts
        print(f"  ⚠️ Falling back to raw posts without dedup")

    # ── Step 3: Enrich ──
    step3 = PipelineStep("enrich", "Score, classify, and tag each insight")
    steps.append(step3)
    step3.start()

    try:
        enriched = _enrich_posts(unique_posts)
        insights_path = os.path.join(output_dir, "precomputed_insights.json")
        with open(insights_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        step3.done({
            "enriched": len(enriched),
            "output": insights_path,
        })
    except Exception as e:
        step3.fail(str(e))
        return _make_checkpoint(steps, pipeline_start)

    # ── Step 4: Precompute embeddings ──
    step4 = PipelineStep("embed", "Precompute dense embeddings for hybrid retrieval")
    steps.append(step4)

    if skip_embeddings:
        step4.skip("--skip-embeddings flag set")
    else:
        step4.start()
        try:
            from components.hybrid_retrieval import precompute_embeddings
            embed_path = precompute_embeddings(
                enriched,
                output_path=os.path.join(output_dir, "precomputed_embeddings.npy"),
                meta_path=os.path.join(output_dir, "precomputed_embeddings_meta.json"),
            )
            step4.done({"embeddings_path": embed_path, "count": len(enriched)})
        except Exception as e:
            step4.fail(str(e))
            print(f"  ⚠️ Embeddings failed — hybrid retrieval will use BM25 only")

    # ── Step 5: Cluster ──
    step5 = PipelineStep("cluster", "Generate strategic theme clusters")
    steps.append(step5)
    step5.start()

    try:
        clusters_path = os.path.join(output_dir, "precomputed_clusters.json")
        _run_clustering(enriched, clusters_path)
        step5.done({"output": clusters_path})
    except Exception as e:
        step5.fail(str(e))

    # ── Step 6: Trend detection ──
    step6 = PipelineStep("trends", "Detect volume anomalies, sentiment shifts, emerging topics")
    steps.append(step6)

    if skip_trends:
        step6.skip("--skip-trends flag set")
    else:
        step6.start()
        try:
            from components.trend_detector import detect_trends, detect_absences
            trend_results = detect_trends(enriched, window_days=7)
            absences = detect_absences(enriched, window_days=7)
            trend_results["absences"] = absences

            trends_path = os.path.join(output_dir, "trend_alerts.json")
            with open(trends_path, "w", encoding="utf-8") as f:
                json.dump(trend_results, f, ensure_ascii=False, indent=2)
            step6.done({
                "alerts": trend_results["metadata"]["alerts_generated"],
                "absences": len(absences),
                "topics_tracked": trend_results["metadata"]["topics_tracked"],
                "output": trends_path,
            })
        except Exception as e:
            step6.fail(str(e))

    # ── Step 7: Save checkpoint ──
    checkpoint = _make_checkpoint(steps, pipeline_start)
    meta_path = os.path.join(output_dir, "_pipeline_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Total time: {checkpoint['total_seconds']:.1f}s")
    print(f"  Steps: {sum(1 for s in steps if s.status == 'done')}/{len(steps)} succeeded")
    print(f"{'='*60}")

    return checkpoint


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _load_scraped_data(input_path: str) -> List[Dict[str, Any]]:
    """Load posts from one file or multiple known scraper outputs."""
    all_posts = []

    if os.path.exists(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_posts.extend(data)
            print(f"  📂 {input_path}: {len(data)} posts")

    # Also check standard scraper output paths
    standard_paths = [
        "data/scraped_reddit_posts.json",
        "data/scraped_bluesky_posts.json",
        "data/scraped_ebay_forums.json",
        "data/scraped_community_posts.json",
    ]
    for path in standard_paths:
        if path != input_path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"  📂 {path}: {len(data)} posts")
                    all_posts.extend(data)
            except Exception as e:
                print(f"  ⚠️ {path}: {e}")

    if not all_posts:
        raise FileNotFoundError(f"No scraped data found at {input_path} or standard paths")

    return all_posts


def _enrich_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich posts through the signal scorer pipeline."""
    from components.signal_scorer import enrich_single_insight
    from components.scoring_utils import detect_payments_upi_highasp, detect_competitor_and_partner_mentions, detect_liquidity_signals

    enriched = []
    for idx, post in enumerate(posts):
        text = post.get("text", "")
        if not text or len(text) < 30:
            continue

        insight = {
            "text": text,
            "title": post.get("title", ""),
            "source": post.get("source", "Unknown"),
            "url": post.get("url", ""),
            "post_date": post.get("post_date", datetime.now().strftime("%Y-%m-%d")),
            "_logged_date": post.get("_logged_date", datetime.now().isoformat()),
            "subreddit": post.get("subreddit", ""),
            "forum_section": post.get("forum_section", ""),
            "username": post.get("username", ""),
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
        }

        try:
            result = enrich_single_insight(insight)
            if result:
                # Add extra flags
                flags = detect_payments_upi_highasp(text)
                result["_payment_issue"] = flags.get("_payment_issue", False)
                result["_upi_flag"] = flags.get("_upi_flag", False)
                result["_high_end_flag"] = flags.get("_high_end_flag", False)
                result["payment_issue_types"] = flags.get("payment_issue_types", [])

                mentions = detect_competitor_and_partner_mentions(text)
                result["mentions_competitor"] = mentions.get("competitors", [])
                result["mentions_ecosystem_partner"] = mentions.get("partners", [])

                liq = detect_liquidity_signals(text)
                result["_liquidity_signal"] = liq.get("_liquidity_signal", False)
                result["liquidity_signal_types"] = liq.get("liquidity_signal_types", [])
                result["liquidity_platforms"] = liq.get("liquidity_platforms", [])

                enriched.append(result)
        except Exception as e:
            if (idx + 1) % 100 == 0:
                print(f"  ⚠️ Enrichment error at {idx}: {e}")

        if (idx + 1) % 500 == 0:
            print(f"  Processed {idx + 1}/{len(posts)} ({len(enriched)} enriched)...")

    return enriched


def _run_clustering(insights: List[Dict[str, Any]], output_path: str):
    """Run clustering and save results."""
    from components.cluster_synthesizer import cluster_by_subtag_then_embed, synthesize_cluster
    from components.scoring_utils import detect_payments_upi_highasp

    # Domain filter
    COLLECTIBLES_HINTS = (
        "card", "trading card", "slab", "psa", "bgs", "sgc", "tcg", "pokemon", "comic",
        "graded", "pop report", "vault", "whatnot", "goldin", "heritage", "pwcc", "fanatics",
    )
    filtered = [
        i for i in insights
        if any(h in (i.get("text", "") or "").lower() for h in COLLECTIBLES_HINTS)
        or i.get("_payment_issue") or i.get("_upi_flag") or i.get("_high_end_flag")
    ]

    print(f"  Clustering {len(filtered)} collectibles insights...")
    raw_clusters = cluster_by_subtag_then_embed(filtered)

    clusters = []
    cards = []
    for idx, (cluster_items, meta) in enumerate(raw_clusters):
        card = synthesize_cluster(cluster_items)
        card["coherent"] = meta.get("coherent", True)
        card["was_reclustered"] = meta.get("was_reclustered", False)
        card["avg_similarity"] = f"{meta.get('avg_similarity', 0.0):.2f}"

        cid = card.get("cluster_id", idx)
        cluster_record = {
            "cluster_id": cid,
            "insights": cluster_items,
            "stats": _cluster_stats(cluster_items),
            "coherent": card["coherent"],
            "was_reclustered": card["was_reclustered"],
            "avg_similarity": card["avg_similarity"],
        }
        clusters.append(cluster_record)
        cards.append(card)

    data = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "counts": {
                "input_insights": len(insights),
                "filtered_for_clustering": len(filtered),
                "cluster_count": len(clusters),
            },
        },
        "clusters": clusters,
        "cards": cards,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(clusters)} clusters to {output_path}")


def _cluster_stats(items: List[Dict]) -> Dict[str, Any]:
    n = len(items)
    if n == 0:
        return {"size": 0}
    from collections import Counter
    tax_type = lambda x: (x.get("taxonomy", {}) or {}).get("type", x.get("type_tag", ""))
    return {
        "size": n,
        "complaints": sum(1 for x in items if x.get("brand_sentiment") in ("Complaint", "Negative")),
        "feature_requests": sum(1 for x in items if tax_type(x) == "Feature Request"),
        "negative": sum(1 for x in items if x.get("brand_sentiment") in ("Complaint", "Negative")),
        "positive": sum(1 for x in items if x.get("brand_sentiment") in ("Praise", "Positive")),
        "avg_score": round(sum(float(x.get("score", 0) or 0) for x in items) / n, 2),
    }


def _make_checkpoint(steps: List[PipelineStep], start_time: float) -> Dict[str, Any]:
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_seconds": round(time.time() - start_time, 2),
        "steps": [s.to_dict() for s in steps],
        "status": "failed" if any(s.status == "failed" for s in steps) else "complete",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SignalSynth Pipeline Orchestrator")
    parser.add_argument("--input", default="data/all_scraped_posts.json", help="Input scraped posts JSON")
    parser.add_argument("--output-dir", default=".", help="Output directory for all artifacts")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding precomputation")
    parser.add_argument("--skip-trends", action="store_true", help="Skip trend detection")
    parser.add_argument("--max-items", type=int, default=None, help="Cap input size for testing")
    args = parser.parse_args()

    run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        skip_embeddings=args.skip_embeddings,
        skip_trends=args.skip_trends,
        max_items=args.max_items,
    )


if __name__ == "__main__":
    main()
