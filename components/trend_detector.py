# trend_detector.py — Statistical trend & anomaly detection per theme/topic
#
# Detects:
#   1. Volume anomalies: themes with this-period volume > mean + 2σ
#   2. Sentiment shifts: themes where negative ratio changed significantly
#   3. Emerging topics: new themes not seen in prior periods
#   4. Declining topics: themes that dropped significantly
#
# Usage:
#   from components.trend_detector import detect_trends
#   alerts = detect_trends(insights, window_days=7)

import re
from datetime import datetime, timedelta, date
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.fromisoformat(str(d).replace("Z", "+00:00")).date()
    except Exception:
        pass
    # Try common formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(d)[:20], fmt).date()
        except Exception:
            continue
    return None


def _get_insight_date(insight: Dict[str, Any]) -> Optional[date]:
    for field in ("post_date", "_logged_date", "last_seen", "date"):
        d = _parse_date(insight.get(field))
        if d:
            return d
    return None


def _get_topic(insight: Dict[str, Any]) -> str:
    tax = insight.get("taxonomy") if isinstance(insight.get("taxonomy"), dict) else {}
    return tax.get("topic") or insight.get("subtag") or insight.get("type_subtag") or "General"


def _get_type(insight: Dict[str, Any]) -> str:
    tax = insight.get("taxonomy") if isinstance(insight.get("taxonomy"), dict) else {}
    return tax.get("type") or insight.get("type_tag") or "Unclassified"


# ---------------------------------------------------------------------------
# Time-bucketing
# ---------------------------------------------------------------------------

def _bucket_by_period(
    insights: List[Dict[str, Any]],
    window_days: int = 7,
) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Bucket insights into time windows by topic.
    Returns: {period_label: {topic: [insights]}}
    """
    # Find date range
    dated = []
    for i in insights:
        d = _get_insight_date(i)
        if d:
            dated.append((d, i))

    if not dated:
        return {}

    dated.sort(key=lambda x: x[0])
    min_date = dated[0][0]
    max_date = dated[-1][0]

    # Create period boundaries
    periods: Dict[str, Dict[str, List[Dict]]] = {}
    current = min_date
    while current <= max_date:
        period_end = current + timedelta(days=window_days - 1)
        label = f"{current.isoformat()}_{period_end.isoformat()}"
        periods[label] = defaultdict(list)
        current = current + timedelta(days=window_days)

    # Assign insights to periods
    for d, insight in dated:
        days_from_start = (d - min_date).days
        period_idx = days_from_start // window_days
        period_keys = list(periods.keys())
        if period_idx < len(period_keys):
            topic = _get_topic(insight)
            periods[period_keys[period_idx]][topic].append(insight)

    return periods


# ---------------------------------------------------------------------------
# Trend Detection
# ---------------------------------------------------------------------------

class TrendAlert:
    """Represents a detected trend or anomaly."""

    def __init__(
        self,
        alert_type: str,
        topic: str,
        severity: str,
        message: str,
        current_value: float,
        baseline_value: float,
        confidence: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.alert_type = alert_type      # volume_spike, sentiment_shift, emerging, declining
        self.topic = topic
        self.severity = severity          # high, medium, low
        self.message = message
        self.current_value = current_value
        self.baseline_value = baseline_value
        self.confidence = confidence      # 0-1
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "topic": self.topic,
            "severity": self.severity,
            "message": self.message,
            "current_value": self.current_value,
            "baseline_value": round(self.baseline_value, 2),
            "confidence": round(self.confidence, 3),
            "details": self.details,
        }


def detect_trends(
    insights: List[Dict[str, Any]],
    window_days: int = 7,
    min_periods: int = 2,
    z_threshold: float = 2.0,
    sentiment_shift_threshold: float = 0.15,
) -> Dict[str, Any]:
    """
    Detect statistical trends and anomalies across topics.

    Args:
        insights: All enriched insights
        window_days: Size of each time window in days
        min_periods: Minimum number of historical periods needed for baseline
        z_threshold: Z-score threshold for volume anomaly (default 2.0 = ~95% confidence)
        sentiment_shift_threshold: Min change in negative ratio to flag (0.15 = 15pp)

    Returns:
        Dict with alerts list, topic summaries, and metadata
    """
    periods = _bucket_by_period(insights, window_days=window_days)
    period_keys = list(periods.keys())

    if len(period_keys) < min_periods + 1:
        return {
            "alerts": [],
            "topic_trends": {},
            "metadata": {
                "periods_available": len(period_keys),
                "min_periods_needed": min_periods + 1,
                "status": "insufficient_data",
            },
        }

    # Split into historical baseline and current period
    current_key = period_keys[-1]
    baseline_keys = period_keys[:-1]
    current_data = periods[current_key]

    # Build baseline statistics per topic
    all_topics = set()
    topic_history: Dict[str, List[int]] = defaultdict(list)           # volume per period
    topic_neg_history: Dict[str, List[float]] = defaultdict(list)     # negative ratio per period

    for bk in baseline_keys:
        period_data = periods[bk]
        period_topics = set(period_data.keys())
        all_topics |= period_topics

        for topic in all_topics:
            items = period_data.get(topic, [])
            topic_history[topic].append(len(items))
            if items:
                neg_count = sum(
                    1 for i in items
                    if i.get("brand_sentiment") in ("Negative", "Complaint")
                )
                topic_neg_history[topic].append(neg_count / len(items))
            else:
                topic_neg_history[topic].append(0.0)

    all_topics |= set(current_data.keys())

    # Detect alerts
    alerts: List[TrendAlert] = []
    topic_summaries: Dict[str, Dict[str, Any]] = {}

    for topic in sorted(all_topics):
        if topic in ("General", "Unknown", ""):
            continue

        history = topic_history.get(topic, [])
        current_count = len(current_data.get(topic, []))
        current_items = current_data.get(topic, [])

        # Topic summary
        summary: Dict[str, Any] = {
            "current_volume": current_count,
            "historical_volumes": history,
            "periods_seen": sum(1 for h in history if h > 0),
        }

        # --- Volume anomaly detection ---
        if len(history) >= min_periods:
            hist_array = np.array(history, dtype=float)
            mean_vol = float(np.mean(hist_array))
            std_vol = float(np.std(hist_array))

            if std_vol > 0:
                z_score = (current_count - mean_vol) / std_vol
            else:
                z_score = 0.0 if current_count == mean_vol else (5.0 if current_count > mean_vol else -5.0)

            summary["mean_volume"] = round(mean_vol, 1)
            summary["std_volume"] = round(std_vol, 2)
            summary["z_score"] = round(z_score, 2)

            if z_score >= z_threshold and current_count > 0:
                pct_change = ((current_count - mean_vol) / max(mean_vol, 1)) * 100
                severity = "high" if z_score >= 3.0 else "medium"
                confidence = min(1.0, 1 - (1 / (1 + abs(z_score))))

                alerts.append(TrendAlert(
                    alert_type="volume_spike",
                    topic=topic,
                    severity=severity,
                    message=f"{topic}: +{pct_change:.0f}% volume this period ({current_count} vs avg {mean_vol:.0f}, z={z_score:.1f})",
                    current_value=current_count,
                    baseline_value=mean_vol,
                    confidence=confidence,
                    details={"z_score": round(z_score, 2), "pct_change": round(pct_change, 1)},
                ))

            elif z_score <= -z_threshold and mean_vol > 2:
                pct_change = ((current_count - mean_vol) / max(mean_vol, 1)) * 100
                alerts.append(TrendAlert(
                    alert_type="declining",
                    topic=topic,
                    severity="medium",
                    message=f"{topic}: {pct_change:.0f}% volume drop ({current_count} vs avg {mean_vol:.0f})",
                    current_value=current_count,
                    baseline_value=mean_vol,
                    confidence=min(1.0, 1 - (1 / (1 + abs(z_score)))),
                    details={"z_score": round(z_score, 2), "pct_change": round(pct_change, 1)},
                ))

        # --- Sentiment shift detection ---
        neg_history = topic_neg_history.get(topic, [])
        if current_items and len(neg_history) >= min_periods:
            current_neg_count = sum(
                1 for i in current_items
                if i.get("brand_sentiment") in ("Negative", "Complaint")
            )
            current_neg_ratio = current_neg_count / max(len(current_items), 1)
            baseline_neg_ratio = float(np.mean(neg_history)) if neg_history else 0.0

            shift = current_neg_ratio - baseline_neg_ratio
            summary["current_neg_ratio"] = round(current_neg_ratio, 3)
            summary["baseline_neg_ratio"] = round(baseline_neg_ratio, 3)
            summary["sentiment_shift"] = round(shift, 3)

            if abs(shift) >= sentiment_shift_threshold and current_count >= 3:
                direction = "worsening" if shift > 0 else "improving"
                severity = "high" if abs(shift) >= 0.25 else "medium"
                alerts.append(TrendAlert(
                    alert_type="sentiment_shift",
                    topic=topic,
                    severity=severity,
                    message=f"{topic}: sentiment {direction} ({shift:+.0%} negative ratio shift, now {current_neg_ratio:.0%} vs baseline {baseline_neg_ratio:.0%})",
                    current_value=current_neg_ratio,
                    baseline_value=baseline_neg_ratio,
                    confidence=0.7 if current_count >= 5 else 0.5,
                    details={"direction": direction, "shift_pp": round(shift * 100, 1)},
                ))

        # --- Emerging topic detection ---
        if current_count >= 3 and all(h == 0 for h in history):
            alerts.append(TrendAlert(
                alert_type="emerging",
                topic=topic,
                severity="medium",
                message=f"{topic}: NEW topic detected ({current_count} signals, not seen in prior {len(history)} periods)",
                current_value=current_count,
                baseline_value=0,
                confidence=0.6 if current_count >= 5 else 0.4,
                details={"periods_absent": len(history)},
            ))

        topic_summaries[topic] = summary

    # Sort alerts by severity then confidence
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 9), -a.confidence))

    return {
        "alerts": [a.to_dict() for a in alerts],
        "topic_trends": topic_summaries,
        "metadata": {
            "periods_analyzed": len(period_keys),
            "window_days": window_days,
            "baseline_periods": len(baseline_keys),
            "current_period": current_key,
            "topics_tracked": len(topic_summaries),
            "alerts_generated": len(alerts),
            "z_threshold": z_threshold,
        },
    }


# ---------------------------------------------------------------------------
# Absence / Counterfactual Detection
# ---------------------------------------------------------------------------

def detect_absences(
    insights: List[Dict[str, Any]],
    window_days: int = 7,
    min_baseline_volume: int = 3,
) -> List[Dict[str, Any]]:
    """
    Detect topics that historically generated signals but have gone silent.
    This is the "what's NOT being said" analysis — silence can signal
    either resolution or user abandonment/churn.
    """
    periods = _bucket_by_period(insights, window_days=window_days)
    period_keys = list(periods.keys())

    if len(period_keys) < 3:
        return []

    current_key = period_keys[-1]
    baseline_keys = period_keys[:-1]
    current_data = periods[current_key]

    absences = []
    all_topics = set()
    for bk in baseline_keys:
        all_topics |= set(periods[bk].keys())

    for topic in sorted(all_topics):
        if topic in ("General", "Unknown", ""):
            continue

        history = [len(periods[bk].get(topic, [])) for bk in baseline_keys]
        avg_volume = float(np.mean(history)) if history else 0
        current_volume = len(current_data.get(topic, []))

        if avg_volume >= min_baseline_volume and current_volume == 0:
            absences.append({
                "topic": topic,
                "baseline_avg_volume": round(avg_volume, 1),
                "current_volume": 0,
                "periods_with_signal": sum(1 for h in history if h > 0),
                "total_baseline_periods": len(history),
                "message": f"{topic}: went silent (avg {avg_volume:.0f} signals/period → 0 this period)",
                "hypothesis": (
                    f"'{topic}' was consistently discussed (avg {avg_volume:.0f}/period) "
                    f"but has no signals this period. Possible causes: "
                    f"issue resolved, users churned, or topic moved to other channels."
                ),
            })

    return absences


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="SignalSynth Trend Detection")
    parser.add_argument("--input", default="precomputed_insights.json", help="Input insights JSON")
    parser.add_argument("--window", type=int, default=7, help="Window size in days")
    parser.add_argument("--output", default="trend_alerts.json", help="Output path")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        insights = json.load(f)

    print(f"[TRENDS] Analyzing {len(insights)} insights with {args.window}-day windows...")

    results = detect_trends(insights, window_days=args.window)
    absences = detect_absences(insights, window_days=args.window)
    results["absences"] = absences

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[TRENDS] {results['metadata']['alerts_generated']} alerts detected:")
    for alert in results["alerts"][:10]:
        icon = "🔴" if alert["severity"] == "high" else "🟡"
        print(f"  {icon} [{alert['alert_type']}] {alert['message']}")

    if absences:
        print(f"\n[ABSENCES] {len(absences)} topics went silent:")
        for a in absences[:5]:
            print(f"  🔇 {a['message']}")

    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
