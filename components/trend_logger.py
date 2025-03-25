# trend_logger.py — append insights to log with timestamp for trend tracking
import json
import os
from datetime import datetime

LOG_PATH = "trend_log.jsonl"

def log_insights_over_time(insights):
    """
    Appends each insight with a timestamp to a local log file (JSON Lines).
    """
    now = datetime.utcnow().isoformat()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for i in insights:
            i["_logged_at"] = now
            f.write(json.dumps(i) + "\n")
