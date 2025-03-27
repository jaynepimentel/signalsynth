# trend_logger.py — intelligent trend logging + volume spike tagging
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter

LOG_PATH = "trend_log.jsonl"
MAX_LOG_ENTRIES = 50000  # Optional: cap log size


def log_insights_over_time(insights):
    """
    Appends each insight with a timestamp to a local log file (JSON Lines).
    Also detects keyword bursts and adds metadata for downstream trend analysis.
    """
    now = datetime.utcnow().isoformat()
    trends_today = defaultdict(int)
    trend_keywords = ["grading", "vault", "refund", "search", "delay", "psa", "auth"]

    for i in insights:
        text = i.get("text", "").lower()
        keywords_hit = [kw for kw in trend_keywords if kw in text]
        i["_trend_keywords"] = keywords_hit
        i["_trend_score"] = len(keywords_hit)
        i["_logged_at"] = now

        for kw in keywords_hit:
            trends_today[kw] += 1

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for i in insights:
            f.write(json.dumps(i) + "\n")

    _maybe_compact_log()

    if trends_today:
        print("[TrendLogger] 🔥 Keywords detected:", dict(trends_today))


def _maybe_compact_log():
    """Optional cleanup to keep the trend log lean."""
    if not os.path.exists(LOG_PATH):
        return

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) <= MAX_LOG_ENTRIES:
        return

    # Keep only most recent N entries
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines[-MAX_LOG_ENTRIES:])
