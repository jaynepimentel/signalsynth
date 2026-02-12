# utils/load_scraped_insights.py
# — JSON-first loader with legacy .txt fallback, GPT/heuristic filtering, null-safe normalization, and traceability

import os
import re
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────
# Config (env-overridable without code edits)
# ─────────────────────────────────────────────────────────────
DATA_DIR              = os.getenv("SS_DATA_DIR", "data")
PREFER_JSON           = os.getenv("SS_PREFER_JSON", "1") == "1"
USE_GPT_FILTER        = os.getenv("SS_USE_GPT_FILTER", "0") == "1"     # default off for cost/speed
MIN_LEN               = int(os.getenv("SS_MIN_TEXT_LEN", "40"))        # min characters after cleaning
DEBUG_REJECTIONS      = os.getenv("SS_DEBUG_REJECTIONS", "0") == "1"

# Lightweight signal gates (tweakable)
NOISE_PHRASES = set(
    (os.getenv("SS_NOISE_PHRASES",
     "mail day,for sale,look at this,showing off,pickup post,got this,check this out,look what i found,haul,pc update"))
    .lower().split(",")
)
REQUIRED_KEYWORDS = set(
    (os.getenv("SS_REQUIRED_KEYWORDS",
     "ebay,grading,vault,shipping,return,refund,authentication,delay,scam,psa,whatnot,fanatics,alt marketplace,"
     "bgs,cgc,sgc,hga,csg,payment,wire,transfer,funds,upi,unpaid,dispute,counterfeit,fake,fraud,fees,seller,"
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
<<<<<<< C:/Users/jayne/repo/signalsynth/utils/load_scraped_insights.py
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible,"
     "sneaker,comic,vintage,auction,card,pokemon,sports card,lego,coin,hot wheels,memorabilia,"
     "resell,flip,grail,rare,limited edition,price guide,authenticity,certified,slab,wax,hobby box"))
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
=======
     "buyer,support,customer service,damage,lost,tracking,marketplace,funko,trading card,collectible"))
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/utils/load_scraped_insights.py
    .lower().split(",")
)

# Optional GPT screener (kept lazy-imported to avoid import costs if disabled)
if USE_GPT_FILTER:
    try:
        from components.scoring_utils import gpt_estimate_sentiment_subtag
    except Exception:
        gpt_estimate_sentiment_subtag = None  # survives import errors gracefully


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _now_date() -> str:
    return datetime.today().date().isoformat()

def _hash(s: str) -> str:
    return hashlib.md5((s or "").strip().encode("utf-8")).hexdigest()

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _clean_text(text: str) -> str:
    t = text or ""
    # remove URLs
    t = re.sub(r"http[s]?://\S+", "", t)
    # strip emojis / non-ASCII
    t = re.sub(r"[^\x00-\x7F]+", " ", t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def _looks_noisy(t: str) -> bool:
    tl = t.lower()
    return any(phrase in tl for phrase in NOISE_PHRASES)

def _has_required_keyword(t: str) -> bool:
    tl = t.lower()
    return any(k in tl for k in REQUIRED_KEYWORDS)

def _is_high_signal(text: str) -> (bool, str):
    """Heuristic + optional GPT gate; returns (keep, reason)."""
    cleaned = _clean_text(text)
    if len(cleaned) < MIN_LEN:
        return False, "too_short"
    if _looks_noisy(cleaned):
        return False, "noise_phrase"
    if _has_required_keyword(cleaned):
        return True, "keyword_match"
    if USE_GPT_FILTER and gpt_estimate_sentiment_subtag:
        try:
            g = gpt_estimate_sentiment_subtag(cleaned)
            # keep if not Neutral OR has impact >=3 (you can tighten to >=4 if desired)
            if (g.get("sentiment") != "Neutral") or (int(g.get("impact", 1)) >= 3):
                return True, "gpt_pass"
            return False, "gpt_neutral"
        except Exception:
            # if GPT fails, don’t block the post purely on that
            return True, "gpt_error_passthrough"
    return False, "no_keyword"

def _infer_source_from_path(path: str) -> str:
    p = (path or "").lower()
    if "reddit" in p: return "Reddit"
    if "twitter" in p or "x" in p: return "Twitter/X"
    if "bluesky" in p or "bsky" in p: return "Bluesky"
    if "community" in p or "ebay" in p or "forum" in p: return "eBay Forums"
    if "all_scraped" in p: return "Multi-Source"
    return "Unknown"

def _best_date(item: Dict[str, Any]) -> str:
    return _norm(item.get("post_date")) or _norm(item.get("_logged_date")) or _now_date()


# ─────────────────────────────────────────────────────────────
# Readers (JSON first, then legacy txt)
# ─────────────────────────────────────────────────────────────
def _read_json_file(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[WARN] Bad JSON ({path}): {e}")
        return out

    # Accept list of dicts or envelope with items
    rows = data if isinstance(data, list) else data.get("items", [])
    for r in rows:
        if not isinstance(r, dict):
            continue
        text = _norm(r.get("text")) or _norm(r.get("raw_text"))
        if not text:
            continue
        cleaned = _clean_text(text)
        out.append({
            # core text
            "text": cleaned,
            # traceability
            "raw_text": text,
            "source": r.get("source") or _infer_source_from_path(path),
            "url": r.get("url"),
            "source_file": path,
            # dates
            "post_date": _norm(r.get("post_date")) or _now_date(),
            "_logged_date": _norm(r.get("_logged_date")) or _now_date(),
            # optional metadata passthroughs (harmless if absent)
            "topic_focus": r.get("topic_focus") or [],
            "mentions_competitor": r.get("mentions_competitor") or [],
            "mentions_ecosystem_partner": r.get("mentions_ecosystem_partner") or [],
            "char_count": len(cleaned),
            # ids
            "post_id": r.get("post_id") or _hash(text),
            "hash": r.get("hash") or _hash(text),
        })
    return out

def _read_txt_file(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                raw = _norm(line)
                if not raw:
                    continue
                cleaned = _clean_text(raw)
                out.append({
                    "text": cleaned,
                    "raw_text": raw,
                    "source": _infer_source_from_path(path),
                    "url": None,
                    "source_file": path,
                    "post_date": _now_date(),
                    "_logged_date": _now_date(),
                    "topic_focus": [],
                    "mentions_competitor": [],
                    "mentions_ecosystem_partner": [],
                    "char_count": len(cleaned),
                    "post_id": _hash(raw),
                    "hash": _hash(raw),
                })
    except Exception as e:
        print(f"[WARN] TXT read failed ({path}): {e}")
    return out

def _discover_files(ext: str) -> List[str]:
    """Find files of a given extension in DATA_DIR."""
    files: List[str] = []
    if not os.path.isdir(DATA_DIR):
        return files
    for fn in os.listdir(DATA_DIR):
        if fn.lower().endswith(ext.lower()):
            files.append(os.path.join(DATA_DIR, fn))
    return sorted(files)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def load_scraped_posts(debug: bool = False) -> List[Dict[str, Any]]:
    """
    Load posts from data/*.json (preferred) or *.txt (fallback), apply light filtering
    and return normalized dicts expected by precompute/scorer.
    """
    items: List[Dict[str, Any]] = []

    # Prefer JSON sources if present
    json_paths = _discover_files(".json") if PREFER_JSON else []
    txt_paths  = _discover_files(".txt")

    if json_paths:
        total = 0
        for p in json_paths:
            rows = _read_json_file(p)
            total += len(rows)
            items.extend(rows)
        print(f"🗂 Using JSON sources ({total} rows).")
    else:
        # Fallback to legacy txt
        total = 0
        for p in txt_paths:
            rows = _read_txt_file(p)
            total += len(rows)
            items.extend(rows)
        print(f"🗂 Using TXT fallback ({total} rows).")

    # Filter to high-signal posts
    kept: List[Dict[str, Any]] = []
    rejected = 0
    for r in items:
        keep, reason = _is_high_signal(r.get("raw_text") or r.get("text") or "")
        if keep:
            r.setdefault("gpt_screen_reason", reason)
            kept.append(r)
        else:
            rejected += 1
            if DEBUG_REJECTIONS:
                sample = (r.get("raw_text") or r.get("text") or "")[:120]
                print(f"❌ Rejected [{reason}]: {sample}…")

    print(f"✅ Kept {len(kept)} / {len(items)} posts ({0 if not items else round(100*len(kept)/len(items),1)}% high-signal)")

    return kept


def process_insights(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Minimal, null-safe post-processing. Do NOT call expensive enrichers here —
    the scorer/enricher will handle AI classification. This function guarantees
    the keys the pipeline expects exist.
    """
    out: List[Dict[str, Any]] = []
    for r in raw or []:
        txt = _norm(r.get("text"))
        if not txt:
            continue

        i = dict(r)  # shallow copy
        # Ensure required keys exist
        i["text"] = txt
        i["post_date"] = _norm(i.get("post_date")) or _now_date()
        i["_logged_date"] = _norm(i.get("_logged_date")) or i["post_date"]
        i["source"] = i.get("source") or "Unknown"
        i["topic_focus"] = i.get("topic_focus") or []
        i["mentions_competitor"] = i.get("mentions_competitor") or []
        i["mentions_ecosystem_partner"] = i.get("mentions_ecosystem_partner") or []
        i["char_count"] = i.get("char_count") or len(txt)
        i["post_id"] = i.get("post_id") or _hash(i.get("raw_text") or txt)
        i["hash"] = i.get("hash") or _hash(i.get("raw_text") or txt)

        out.append(i)
    return out
