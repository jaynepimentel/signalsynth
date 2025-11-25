# precompute_clusters.py — Cluster cache generator for SignalSynth
#
# - Reads from precomputed_insights.json
# - Re-promotes money-risk flags (Payments / UPI / High-ASP)
# - Collectibles-first gate
# - CLI filters: brand, persona, topic, since, min-score, max-items
# - Uses cluster_by_subtag_then_embed + synthesize_cluster from cluster_synthesizer
# - Saves clusters as dicts with stats and metadata, plus summary cards

import os
import json
import argparse
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from components.cluster_synthesizer import (
    cluster_by_subtag_then_embed,
    synthesize_cluster,
)
from components.scoring_utils import detect_payments_upi_highasp

# Default IO paths
PRECOMPUTED_INSIGHTS_PATH = "precomputed_insights.json"
CLUSTER_OUTPUT_PATH = "precomputed_clusters.json"


# -----------------------------
# Helpers
# -----------------------------

def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.fromisoformat(str(d)).date()
    except Exception:
        return None


def _ensure_lists(i: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize common list fields so downstream code can rely on them
    being lists instead of sometimes strings / None.
    """
    for k in ("topic_focus", "type_subtags", "mentions_competitor", "mentions_ecosystem_partner"):
        v = i.get(k)
        if v is None:
            i[k] = []
        elif isinstance(v, str):
            i[k] = [v] if v.strip() else []
        elif isinstance(v, list):
            # keep as-is
            pass
        else:
            i[k] = [str(v)]

    # Legacy compatibility: many components still expect a single "type_subtag"
    if "type_subtag" not in i:
        i["type_subtag"] = i["type_subtags"][0] if i["type_subtags"] else "General"

    return i


def _promote_money_risk(i: Dict[str, Any]) -> Dict[str, Any]:
    """
    Promote payment / UPI / high-ASP flags into normalized fields.
    If missing, derive from raw text via detect_payments_upi_highasp.
    """
    flags = detect_payments_upi_highasp(i.get("text", "") or "")

    if i.get("_payment_issue") is None:
        i["_payment_issue"] = flags.get("_payment_issue", False)
    if i.get("payment_issue_types") is None:
        i["payment_issue_types"] = flags.get("payment_issue_types", [])
    if i.get("_upi_flag") is None:
        i["_upi_flag"] = flags.get("_upi_flag", False)
    if i.get("_high_end_flag") is None:
        i["_high_end_flag"] = flags.get("_high_end_flag", False)

    if i.get("topic_hint") is None and flags.get("topic_hint"):
        i["topic_hint"] = flags["topic_hint"]

    # Ensure topic_focus carries money-risk tags for easier filtering
    tf = list(i.get("topic_focus", []) or [])
    if i["_payment_issue"] and "Payments" not in tf:
        tf.append("Payments")
    if i["_upi_flag"] and "UPI" not in tf:
        tf.append("UPI")
    i["topic_focus"] = tf

    return i


COLLECTIBLES_HINTS = (
    "card", "trading card", "slab", "psa", "bgs", "sgc", "tcg", "pokemon", "comic",
    "graded", "pop report", "population report", "vault", "whatnot", "goldin",
    "heritage", "pwcc", "fanatics", "alt marketplace", "loupe"
)


def _is_collectibles(i: Dict[str, Any]) -> bool:
    """
    Domain gate: keep only collectibles and high-value money-risk posts.
    """
    t = (i.get("text") or "").lower()
    money = bool(i.get("_payment_issue") or i.get("_upi_flag") or i.get("_high_end_flag"))
    return any(h in t for h in COLLECTIBLES_HINTS) or money


def _passes_filters(
    i: Dict[str, Any],
    brand: Optional[str],
    persona: Optional[str],
    topic: Optional[str],
    since: Optional[str],
    min_score: Optional[float],
) -> bool:
    """
    Apply optional CLI filters on top of the collectibles-first set.
    """
    if brand:
        if str(i.get("target_brand", "")).lower() != brand.lower():
            return False

    if persona:
        if str(i.get("persona", "")).lower() != persona.lower():
            return False

    if topic:
        tf = i.get("topic_focus", [])
        if isinstance(tf, str):
            tf = [tf]
        if topic not in tf:
            return False

    if since:
        cutoff = _parse_date(since)
        if cutoff:
            d = (
                _parse_date(i.get("last_seen"))
                or _parse_date(i.get("_logged_date"))
                or _parse_date(i.get("post_date"))
            )
            if not d or d < cutoff:
                return False

    if min_score is not None:
        try:
            if float(i.get("score", 0.0)) < float(min_score):
                return False
        except Exception:
            return False

    return True


def _cluster_stats(cluster_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute useful cluster-level metrics for downstream UI / prioritization.
    """
    n = len(cluster_items)
    if n == 0:
        return {
            "size": 0,
            "complaints": 0,
            "payments_flags": 0,
            "upi_flags": 0,
            "high_asp_flags": 0,
            "avg_score": 0.0,
        }

    complaints = sum(1 for x in cluster_items if x.get("brand_sentiment") == "Complaint")
    payments_flags = sum(1 for x in cluster_items if x.get("_payment_issue"))
    upi_flags = sum(1 for x in cluster_items if x.get("_upi_flag"))
    high_asp_flags = sum(1 for x in cluster_items if x.get("_high_end_flag"))
    avg_score = sum(float(x.get("score", 0.0) or 0.0) for x in cluster_items) / float(n)

    return {
        "size": n,
        "complaints": complaints,
        "payments_flags": payments_flags,
        "upi_flags": upi_flags,
        "high_asp_flags": high_asp_flags,
        "avg_score": round(avg_score, 2),
    }


# -----------------------------
# Main
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Precompute cluster cache from precomputed_insights.json"
    )
    parser.add_argument("--brand", type=str, help="Filter by target brand (exact match)")
    parser.add_argument("--persona", type=str, help="Filter by persona (exact match)")
    parser.add_argument("--topic", type=str, help="Require topic_focus to contain this tag (e.g. Payments)")
    parser.add_argument("--since", type=str, help="Only include insights on/after this date (YYYY-MM-DD)")
    parser.add_argument("--min-score", type=float, default=None, help="Minimum score filter")
    parser.add_argument("--max-items", type=int, default=None, help="Cap number of insights before clustering")
    parser.add_argument("--input", type=str, default=PRECOMPUTED_INSIGHTS_PATH, help="Path to precomputed insights JSON")
    parser.add_argument("--output", type=str, default=CLUSTER_OUTPUT_PATH, help="Where to save the cluster cache JSON")
    args = parser.parse_args()

    in_path = args.input
    out_path = args.output

    if not os.path.exists(in_path):
        print(f"[ERROR] File not found: {in_path}")
        return

    with open(in_path, "r", encoding="utf-8") as f:
        insights: List[Dict[str, Any]] = json.load(f)

    print(f"[INFO] Loaded {len(insights)} insights from {in_path}")

    # Hygiene + money-risk + domain filter
    hydrated: List[Dict[str, Any]] = []
    for i in insights:
        i = _ensure_lists(i)
        i = _promote_money_risk(i)
        if _is_collectibles(i):
            hydrated.append(i)

    # Non-destructive user filters
    filtered = [
        i
        for i in hydrated
        if _passes_filters(
            i,
            brand=args.brand,
            persona=args.persona,
            topic=args.topic,
            since=args.since,
            min_score=args.min_score,
        )
    ]

    if args.max_items and len(filtered) > args.max_items:
        filtered = filtered[: args.max_items]

    print(
        "[INFO] Filtered set: "
        f"{len(filtered)} insights "
        f"(brand={args.brand or '*'}, persona={args.persona or '*'}, "
        f"topic={args.topic or '*'}, since={args.since or '*'}, "
        f"min_score={args.min_score if args.min_score is not None else '*'})"
    )

    if not filtered:
        print("[WARN] No insights after filters; aborting cluster generation.")
        return

    # Cluster + synthesized cards using cluster_by_subtag_then_embed
    print("[INFO] Generating cluster groups…")
    raw_cluster_tuples = cluster_by_subtag_then_embed(filtered)
    if not raw_cluster_tuples:
        print("[WARN] cluster_by_subtag_then_embed returned no clusters.")
        data = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "filters": {
                    "brand": args.brand,
                    "persona": args.persona,
                    "topic": args.topic,
                    "since": args.since,
                    "min_score": args.min_score,
                    "max_items": args.max_items,
                    "input_path": in_path,
                },
                "counts": {
                    "input_insights": len(insights),
                    "hydrated_collectibles": len(hydrated),
                    "filtered_for_clustering": len(filtered),
                    "cluster_count": 0,
                },
            },
            "clusters": [],
            "cards": [],
        }
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[✅ DONE] Saved empty clusters to {out_path}")
        return

    clusters: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []

    for idx, (cluster_items, meta) in enumerate(raw_cluster_tuples):
        # cluster_items is a list of insight dicts
        stats = _cluster_stats(cluster_items)

        # synthesize summary card using existing logic
        card = synthesize_cluster(cluster_items)
        card["coherent"] = meta.get("coherent", True)
        card["was_reclustered"] = meta.get("was_reclustered", False)
        card["avg_similarity"] = f"{meta.get('avg_similarity', 0.0):.2f}"

        cid = card.get("cluster_id", idx)

        cluster_record = {
            "cluster_id": cid,
            "insights": cluster_items,
            "stats": stats,
            "coherent": card["coherent"],
            "was_reclustered": card["was_reclustered"],
            "avg_similarity": card["avg_similarity"],
        }
        clusters.append(cluster_record)
        cards.append(card)

    # Metadata block for traceability
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "filters": {
            "brand": args.brand,
            "persona": args.persona,
            "topic": args.topic,
            "since": args.since,
            "min_score": args.min_score,
            "max_items": args.max_items,
            "input_path": in_path,
        },
        "counts": {
            "input_insights": len(insights),
            "hydrated_collectibles": len(hydrated),
            "filtered_for_clustering": len(filtered),
            "cluster_count": len(clusters),
        },
    }

    data = {
        "metadata": metadata,
        "clusters": clusters,
        "cards": cards,
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[✅ DONE] Saved {len(clusters)} clusters to {out_path}")


if __name__ == "__main__":
    main()
