# scrape_signalsynth.py - Collectibles-first scraper with GPT 5.1 relevance
# and high-ASP payments / UPI detection, plus Scan-to-Price / Price Guide focus
# and additional Blowout Cards forum coverage.

import os, sys
import json
import time
import subprocess
import requests
import warnings
import re
from datetime import datetime, timezone
from dateutil.parser import isoparse
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
from openai import OpenAI

# Ensure imports work when running from scrapers/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Local project enrichers
from components.signal_scorer import enrich_single_insight
from components.scoring_utils import detect_competitor_and_partner_mentions

"""
Collectibles-first scraper focused on:
- Trading cards and collectibles conversations
- High value payments, UPI, wire or bank transfer issues
- eBay, competitors, and partner ecosystems
- eBay Scan-to-Price, Price Guide (PG 2.0), Smart Lens, and scan accuracy
- Blowout Cards forums and adjacent hobby chatter

Key behavior:
- Subreddit coverage broadened for sports cards, non-sports TCG, and EU-relevant markets
- Semantic relevance gate plus GPT 5.1 backup
- Collectibles-or-money-or-price-guide gate to keep only relevant signal
"""

load_dotenv()
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

HEADERS = {"User-Agent": os.getenv("SCRAPER_UA", "Mozilla/5.0")}
SAVE_PATH = "data/scraped_community_posts.json"
NOW = datetime.now(timezone.utc)

# Embedding for semantic relevance
MODEL_NAME = os.getenv("SS_SCRAPE_EMBED_MODEL", "all-MiniLM-L6-v2")
try:
    model = SentenceTransformer(MODEL_NAME, device="cpu")
except Exception:
    model = None

# OpenAI client for relevance fallback
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Screener model defaults and limits
SCRAPER_LLM_MODEL = os.getenv("OPENAI_MODEL_SCREENER", "gpt-5.1")
SCRAPER_LLM_MAX_TOKENS = int(os.getenv("OPENAI_SCRAPER_LLM_MAX_TOKENS", "16"))

start_date = os.getenv("SCRAPE_SINCE", "2025-01-01")
end_date = NOW.date().isoformat()
SIM_THRESHOLD = float(os.getenv("SS_SCRAPE_SIM_THRESHOLD", "0.14"))

# ------------------------------
# Sources and Queries
# ------------------------------

REDDIT_SUBREDDITS = [
    # Marketplace and general trading
    "eBay",
    "tradingcards",

    # Pokemon
    "pokemonTCG",
    "pkmntcg",

    # Core sports cards
    "baseballcards",
    "basketballcards",
    "footballcards",
    "hockeycards",
    "sportscards",
    "soccercard",

    # Live shopping or specific competitor ecosystems
    "WhatnotApp",
    "fanatics",

    # Other marketplaces and general commerce
    "AltMarketplace",
    "tiktokshopping",
    "CardMarket",

    # Coins and memorabilia
    "coins",
    "sportsmemorabilia",

    # Grading and slabs
    "gradedcards",
    "magicTCG",
    "yugioh",

    # Growing non-sports TCGs
    "OnePieceTCG",
    "DigimonCardGame2020",
]

# Price Guide and scan related hints we want to catch aggressively
PRICE_GUIDE_HINTS = {
    # Existing PG / Scan phrases
    "scan to price",
    "scan & price",
    "scan price",
    "scan or search",
    "scan to list",
    "scan feature",
    "image scan",
    "camera scan",
    "photo scan",
    "smart lens",
    "smartlens",
    "ebay price guide",
    "price guide",
    "pg2",
    "pg 2.0",
    "price guide 2.0",
    "card pricing tool",
    "pricing tool",
    "autopricing",
    "price guidance",
    "pricing guidance",
    "catalog pricing",
    "catalog based pricing",
    "90 day median",
    "median price",
    "guide accuracy",
    "scan accuracy",
    "scan did not match",
    "scan didnt match",
    "scan failed",
    "scan broken",
    "wrong pricing",
    "wrong price guide",
    "pricing bug",

    # Real-world chatter around PG/Scan/valuation
    "scan wrong",
    "scan is wrong",
    "scan off",
    "scan inaccurate",
    "scan glitch",
    "scan bug",
    "scan issue",
    "scan mispriced",
    "scan misidentifying",
    "scan not working",
    "scan doesnt work",
    "scan doesn't work",
    "scan incorrect",
    "scan problem",
    "scan wrong card",

    "pricing wrong",
    "pricing off",
    "pricing inaccurate",
    "wrong price",
    "wrong pricing",
    "mispriced",
    "value wrong",
    "value off",

    "pg wrong",
    "pg off",
    "pg broken",
    "pg messed up",

    "catalog wrong",
    "catalog off",
    "catalog inaccurate",
    "median wrong",
    "median off",
    "median inaccurate",
}

REDDIT_TERMS = [
    # Core eBay and live
    "ebay",
    "ebay collectibles",
    "ebay live",
    "ebay vault",

    # Price Guide / Scan / Smart Lens
    "scan to price",
    "scan & price",
    "scan price",
    "scan or search",
    "scan to list",
    "scan feature",
    "image scan",
    "camera scan",
    "photo scan",
    "smart lens",
    "smartlens",
    "ebay price guide",
    "price guide",
    "pg2",
    "pg 2.0",
    "price guide 2.0",
    "card pricing tool",
    "pricing tool",
    "autopricing",
    "price guidance",
    "pricing guidance",
    "catalog pricing",
    "catalog based pricing",
    "90 day median",
    "median price",
    "guide accuracy",
    "scan accuracy",
    "scan did not match",
    "scan didnt match",
    "scan failed",
    "wrong pricing",
    "wrong price guide",
    "pricing bug",

    # Grading and authentication
    "grading",
    "PSA",
    "BGS",
    "SGC",
    "authentication",
    "population report",

    # Marketplaces and competitors
    "fanatics live",
    "fanatics collect",
    "whatnot app",
    "alt marketplace",
    "loupe app",
    "goldin auctions",
    "heritage auction",
    "elite auction",
    "pwcc",

    # Consignment and auction houses
    "consignment",
    "auction house",

    # Selling high value cards
    "best place to sell cards",
    "best place to sell high value card",
    "higher value card",
    "high value cards",

    # Vault, live, breaks, repacks
    "vault to grading",
    "live stream",
    "buy it now",
    "packs",
    "breaks",
    "repack",
    "slabs",

    # Risk and problems
    "returns",
    "scam",
    "refund",
    "counterfeit",
    "case break",

    # Investing and flipping
    "trading card investing",
    "flipping cards",

    # Coins
    "coin collecting",
    "silver coins",
    "grading coins",

    # Funnel and payments
    "search",
    "filters",
    "conversion",
    "checkout",
    "payment",
    "payout",
    "hold",
]

TW_BASE = "(ebay OR #ebay OR 'Ebay' OR 'ebay live' OR #ebaylive)"
TW_PAYMENT = "(payment OR paid OR pay OR 'payment method' OR declined OR 'payment declined' OR 'card declined' OR 'credit card' OR 'debit card' OR 'charge failed' OR 'payment failed')"
TW_WIRE = "('wire transfer' OR wire OR 'bank transfer' OR ACH OR 'bank wire' OR 'bank instructions' OR 'bank details')"
TW_UPI = "('unpaid item' OR UPI OR 'did not pay' OR 'didn\\'t pay' OR 'non-paying' OR 'non paying' OR 'nonpaying bidder' OR 'buyer never paid' OR 'no payment received')"
TW_HIGHASP_HINT = "('$1,000' OR '$2,000' OR '$5,000' OR '$10,000' OR '5k' OR '10k' OR 'six figures' OR 'five figures' OR 'high value' OR 'high-end' OR 'high end' OR 'grail')"

TWITTER_TERMS = [
    # General eBay / collectibles
    TW_BASE,
    "(grading OR #grading OR psa OR #psa OR bgs OR sgc)",
    "(vault OR 'ebay vault' OR #ebayvault)",
    "(goldin OR #goldin OR 'goldin auctions')",
    "(fanatics OR #fanatics OR 'fanatics live')",
    "(authentication OR authentic OR #authentication)",
    "(case break OR casebreak OR #casebreaks OR 'box break' OR #boxbreak)",
    "(consignment OR 'auction house' OR pwcc OR heritage OR elite)",
    "('trading card investing' OR 'sports card flip' OR 'coin investing' OR 'silver coin')",

    # Price Guide / Scan to Price / Smart Lens
    "(ebay 'scan to price' OR 'scan & price' OR 'scan price')",
    "(ebay 'scan to list' OR 'scan or search' OR 'scan feature')",
    "(ebay 'smart lens' OR smartlens OR 'price guide' OR 'pg 2.0' OR pg2)",
    "(ebay 'card pricing tool' OR 'pricing tool' OR 'price guidance' OR 'catalog pricing')",

    # Payments / UPI / high ASP
    f"{TW_BASE} {TW_PAYMENT}",
    f"{TW_BASE} {TW_WIRE}",
    f"{TW_BASE} {TW_UPI}",
    f"{TW_BASE} {TW_PAYMENT} {TW_HIGHASP_HINT}",
    f"{TW_BASE} {TW_WIRE} {TW_HIGHASP_HINT}",
    f"{TW_BASE} {TW_UPI} {TW_HIGHASP_HINT}",
]

COMMUNITY_FORUMS = {
    "Buying-Selling": "https://community.ebay.com/t5/Buying-Selling/ct-p/buying-selling-db",
    "Collectibles-Art": "https://community.ebay.com/t5/Collectibles-Art/bd-p/29",
    "Shipping": "https://community.ebay.com/t5/Shipping/bd-p/215",
    "Returns-Cancellations": "https://community.ebay.com/t5/Returns-Cancellations/bd-p/210",
    "Selling": "https://community.ebay.com/t5/Selling/bd-p/Selling",
}

# Blowout Cards forums: representative entry points to active card sections.
BLOWOUT_FORUMS = {
    "Blowout-Baseball": "https://www.blowoutforums.com/forums/baseball.6/",
    "Blowout-Basketball": "https://www.blowoutforums.com/forums/basketball.7/",
    "Blowout-Football": "https://www.blowoutforums.com/forums/football.8/",
    "Blowout-Multisport": "https://www.blowoutforums.com/forums/multi-sport-talk.30/",
}

# ------------------------------
# Tag helpers
# ------------------------------

def is_case_break(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ["case break", "box break", "live break", "repack", "mystery pack"])


def is_live_shopping(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ["ebay live", "fanatics live", "livestream", "live shopping", "live stream"])


def is_dev_feedback(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ["ebay api", "developer.ebay", "graphql", "sdk", "rate limit", "oauth", "auth token"])


def is_coin_signal(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ["coin collecting", "silver coin", "graded coin", "pcgs", "ngc"])


def is_repack_signal(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ["repack", "mystery pack", "chase card", "guaranteed hit"])


def gpt_pg_signal(text: str) -> bool:
    """
    GPT-based semantic detector for PG/Scan/Smart Lens signals.
    Runs only if the text already looks scan/price/valuation-ish.
    """
    if client is None:
        return False

    t = (text or "").lower()
    if "scan" not in t and not any(w in t for w in ["price", "guide", "value", "median"]):
        return False

    prompt = (
        "Answer Yes or No. Is this post discussing any aspect of eBay's Scan-to-Price feature, "
        "Price Guide (including PG 2.0), Smart Lens, catalog-based card pricing, price accuracy, "
        "scan accuracy, or valuation (including praise, complaints, or neutral commentary)?\n\n"
        f"{text[:1000]}"
    )

    try:
        resp = client.chat.completions.create(
            model=SCRAPER_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You identify Price Guide / Scan-to-Price / Smart Lens signals."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_completion_tokens=8,
        )
        ans = (resp.choices[0].message.content or "").lower()
        return "yes" in ans
    except Exception:
        return False


def is_price_guide_signal(text: str) -> bool:
    """
    Hybrid PG/Scan detector:
    1) Keyword list (PRICE_GUIDE_HINTS)
    2) Heuristic: scan + pricing/value/guide context
    3) GPT: semantic classification for subtle/implicit mentions
    """
    t = (text or "").lower()

    # 1) direct keyword hit
    if any(h in t for h in PRICE_GUIDE_HINTS):
        return True

    # 2) heuristic: scan + pricing-ish terms
    if "scan" in t and any(w in t for w in ["price", "value", "guide", "median", "accurate", "inaccurate", "wrong", "right"]):
        return True

    # 3) GPT semantic check (only if scan/pricing language present)
    if gpt_pg_signal(text):
        return True

    return False

# ------------------------------
# Payment, UPI, high ASP detection
# ------------------------------

RE_HIGH_ASP_AMT = re.compile(r"\$\s?(\d{1,3}(?:[,\s]\d{3})+)|\b(\d{1,2})\s?k\b", re.I)
RE_PAYMENT_DECLINED = re.compile(
    r"(payment (?:was )?declined|card (?:was )?declined|payment failed|charge failed|"
    r"credit card (?:issue|problem|declined)|debit card (?:issue|problem|declined))",
    re.I,
)
RE_WIRE = re.compile(
    r"(wire transfer|bank transfer|ACH|bank wire|bank details|bank instructions|wire instructions)",
    re.I,
)
RE_UPI = re.compile(
    r"(unpaid item|UPI\b|did(?:\s*not|\s*n[’']?t)\s*pay|non[-\s]?paying bidder|buyer never paid|no payment received)",
    re.I,
)

PAYMENT_HINTS = [
    "payment", "paid", "pay", "declined", "failed", "charge", "card",
    "credit", "debit", "wire", "bank transfer", "ACH", "instructions",
    "routing", "swift", "iban",
]

def is_high_asp(text: str) -> bool:
    if RE_HIGH_ASP_AMT.search(text):
        return True
    t = text.lower()
    return any(term in t for term in ["high-end", "high end", "grail", "expensive", "six figures", "five figures"])

def detect_payment_issue_types(text: str):
    types = []
    if RE_PAYMENT_DECLINED.search(text): types.append("payment_declined")
    if RE_WIRE.search(text): types.append("wire_or_bank_transfer")
    if RE_UPI.search(text): types.append("unpaid_item_upi")
    return types

# ------------------------------
# Strict MTG filtering
# ------------------------------

MTG_NOISE_TERMS = {
    "edh", "commander", "standard", "modern", "pioneer", "legacy", "vintage",
    "draft", "sealed", "cube", "brew", "deck", "decklist", "sideboard",
    "spoiler", "leak", "art", "lore", "flavor", "judge", "ruling", "combo",
    "primer", "fnm", "arena", "mtgo", "banlist", "pro tour", "pt",
}

BUSINESS_ALLOWLIST = {
    "ebay", "ebay live", "vault", "authenticity", "authentication", "psa",
    "bgs", "sgc", "grading", "turnaround", "pop report", "population report",
    "fees", "final value fee", "seller fee", "buyer fee", "shipping", "label",
    "refund", "return", "scam", "counterfeit", "listing", "search", "filter",
    "conversion", "checkout", "payment", "hold", "payout", "consign",
    "consignment", "auction", "auction house", "goldin", "heritage", "pwcc",
    "whatnot", "fanatics", "loupe", "alt marketplace", "comc", "tiktok shopping",
}

def _has_any(text: str, vocab: set) -> bool:
    return any(w in text.lower() for w in vocab)

def _is_mtg_context(text: str) -> bool:
    t = text.lower()
    return ("magic: the gathering" in t) or (" mtg " in f" {t} ")

def is_mtg_irrelevant(text: str, subreddit_hint: str | None = None) -> bool:
    t = text.lower()
    in_mtg = (subreddit_hint or "").lower() in {"magictcg", "mtgfinance", "tcg"}
    if in_mtg or _is_mtg_context(t):
        ebay_hit = "ebay" in t
        biz_hit = _has_any(t, BUSINESS_ALLOWLIST)
        noise = _has_any(t, MTG_NOISE_TERMS)
        if not (ebay_hit or biz_hit):
            return True
        if noise and not (ebay_hit or biz_hit):
            return True
    return False

# ------------------------------
# Collectibles-first domain gate
# ------------------------------

COLLECTIBLES_HINTS = {
    "card",
    "trading card",
    "slab",
    "psa",
    "bgs",
    "sgc",
    "tcg",
    "pokemon",
    "comic",
    "graded",
    "pop report",
    "population report",
    "vault",
    "whatnot",
    "goldin",
    "heritage",
    "pwcc",
    "fanatics",
    "alt marketplace",
    "loupe",
}

def collectibles_or_money_signal(text: str) -> bool:
    """
    Domain gate: keep collectibles, money-risk AND all PG/Scan signals
    including praise, neutral commentary, and subtle scan/valuation talk.
    """
    t = (text or "").lower()
    hit_collectibles = any(k in t for k in COLLECTIBLES_HINTS)
    has_pay_flag = bool(detect_payment_issue_types(t))
    high_asp = is_high_asp(t)
    hit_price_guide = is_price_guide_signal(t)

    if hit_collectibles or has_pay_flag or high_asp or hit_price_guide:
        return True

    # Extra fallback: scan + pricing-ish language, even if PG detector didn't fire
    if "scan" in t and any(w in t for w in ["price", "value", "guide", "median", "pricing"]):
        return True

    return False

# ------------------------------
# Price Guide tagging helper
# ------------------------------

def apply_price_guide_flags(enriched: dict, text: str) -> dict:
    """
    If the text looks like a Scan/Price Guide / Smart Lens signal, mark:
    - is_price_guide_signal = True
    - append "Price Guide / Scan" to topic_focus
    """
    pg = is_price_guide_signal(text)
    enriched["is_price_guide_signal"] = bool(pg)

    if pg:
        tf = enriched.get("topic_focus") or []
        if isinstance(tf, str): tf = [tf]
        if "Price Guide / Scan" not in tf:
            tf.append("Price Guide / Scan")
        enriched["topic_focus"] = tf

    return enriched

# ------------------------------
# LLM relevance gate using GPT 5.1
# ------------------------------

def gpt_relevance_check(text: str) -> bool:
    if client is None:
        return False

    snippet = (text or "")[:1000]

    prompt = (
        "Answer Yes or No. Is this post relevant to eBay Collectibles product or business "
        "topics like fees, selling, listing, grading or logistics, authentication, "
        "Scan-to-Price or Scan-to-List, Price Guide, Smart Lens, "
        "consignment, or competitors (Fanatics, Whatnot, Goldin, Heritage, PWCC, COMC, Loupe), "
        "or does it discuss high-value payments (declines, wire or ACH), or unpaid items (UPI)?\n\n"
        f"{snippet}"
    )

    try:
        response = client.chat.completions.create(
            model=SCRAPER_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise classifier for eBay collectibles and price-guide relevance."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_completion_tokens=SCRAPER_LLM_MAX_TOKENS,
        )
        answer = (response.choices[0].message.content or "").strip().lower()
        return "yes" in answer
    except Exception:
        return False


def is_relevant(text: str) -> bool:
    """
    Hybrid relevance gate:
    1) Embedding similarity against a collectibles query
    2) GPT 5.1 Yes or No fallback
    """
    text = (text or "").strip()
    if len(text) < 5:
        return False

    if model is None:
        return gpt_relevance_check(text)

    try:
        query = (
            "eBay collectibles, grading, authentication, search, fees, consignment, "
            "goldin, fanatics, whatnot, psa, scan to price, price guide, smart lens"
        )
        emb_text = model.encode(text, convert_to_tensor=True)
        emb_query = model.encode(query, convert_to_tensor=True)
        score = util.cos_sim(emb_text, emb_query)[0].item()
        if score > SIM_THRESHOLD:
            return True
        return gpt_relevance_check(text)
    except Exception:
        return gpt_relevance_check(text)

# ------------------------------
# Twitter (pip-installed snscrape)
# ------------------------------

def run_snscrape_search(term: str, max_results: int | None = None):
    """
    Run snscrape for a given search term and return a list of tweet texts.
    Uses the pip version of snscrape via CLI:
        snscrape --jsonl --max-results N twitter-search "<query>"
    """
    max_results = max_results or int(os.getenv("SCRAPE_TW_MAX", "100"))
    query = f"{term} since:{start_date} until:{end_date}"

    command = (
        f'snscrape --jsonl --max-results {max_results} '
        f'twitter-search "{query}"'
    )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True,
            timeout=90,
        )

        tweets: list[str] = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                content = obj.get("content", "")
                if content:
                    tweets.append(content)
            except:
                continue

        if not tweets:
            print(f"[WARN] snscrape returned no tweets for: {term}")

        return tweets

    except Exception as e:
        print(f"[ERROR] Twitter scrape failed for '{term}': {e}")
        return []

# ------------------------------
# Reddit (old.reddit.com)
# ------------------------------

def scrape_reddit_post_detail(post_url: str, subreddit_hint: str | None = None):
    try:
        res = requests.get(post_url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")

        title_el = soup.select_one("a.title, .title")
        title = (title_el.get_text(strip=True) if title_el else "").strip()
        body_el = (
            soup.select_one(".expando .usertext-body .md")
            or soup.select_one(".usertext .md")
            or soup.select_one(".expando")
        )
        body = body_el.get_text(" ", strip=True) if body_el else ""

        full_text = f"{title}\n{body}".strip()
        if not full_text:
            return None

        # Filters
        if is_mtg_irrelevant(full_text, subreddit_hint):
            return None
        if not is_relevant(full_text):
            return None
        if not collectibles_or_money_signal(full_text):
            return None

        comments = [
            c.get_text(" ", strip=True)
            for c in soup.select(".comment .md")[:3]
            if len(c.get_text(strip=True)) > 10
        ]

        timestamp_el = soup.select_one("time")
        timestamp = timestamp_el["datetime"] if timestamp_el and "datetime" in timestamp_el.attrs else None
        try:
            post_date = isoparse(timestamp).date() if timestamp else NOW.date()
        except:
            post_date = NOW.date()

        enriched = enrich_single_insight(
            {
                "text": full_text,
                "url": post_url,
                "source": "Reddit",
                "post_date": post_date.isoformat(),
                "_logged_date": NOW.date().isoformat(),
                "post_age_days": (NOW.date() - post_date).days,
                "comment_count": len(comments),
                "top_comments": comments,
                "subreddit": subreddit_hint,
            }
        )

        if enriched:
            payment_types = detect_payment_issue_types(full_text)
            enriched["_high_end_flag"] = is_high_asp(full_text)
            enriched["_payment_issue"] = bool(payment_types)
            enriched["payment_issue_types"] = payment_types
            enriched["_upi_flag"] = "unpaid_item_upi" in payment_types
            if payment_types:
                enriched["topic_hint"] = "Payments"

            enriched["is_case_break"] = is_case_break(full_text)
            enriched["is_live_shopping"] = is_live_shopping(full_text)
            enriched["is_dev_feedback"] = is_dev_feedback(full_text)
            enriched["mentions"] = detect_competitor_and_partner_mentions(full_text)
            enriched = apply_price_guide_flags(enriched, full_text)

        return enriched

    except Exception:
        return None

def scrape_reddit_html(limit: int | None = None):
    limit = limit or int(os.getenv("SCRAPE_REDDIT_LIMIT", "100"))
    posts = []

    for sub in REDDIT_SUBREDDITS:
        for term in REDDIT_TERMS:

            url = f"https://old.reddit.com/r/{sub}/search?q={requests.utils.quote(term)}&restrict_sr=on&sort=new"

            try:
                res = requests.get(url, headers=HEADERS, timeout=20)
                soup = BeautifulSoup(res.text, "html.parser")

                anchors = soup.select("a.search-title")
                if not anchors:
                    anchors = [
                        a for a in soup.select("a[href*='/r/']")
                        if "/comments/" in (a.get("href") or "")
                    ]

                for link in anchors[:15]:
                    href = link.get("href")
                    if not href:
                        continue
                    if href.startswith("https://old.reddit.com/r/") and "/comments/" in href:
                        post = scrape_reddit_post_detail(href, subreddit_hint=sub)
                        if post:
                            posts.append(post)

                    if len(posts) >= limit:
                        return posts

            except Exception:
                pass

            time.sleep(1.1)

    return posts

def debug_single_reddit_url(url: str, subreddit_hint: str | None = None):
    post = scrape_reddit_post_detail(url, subreddit_hint=subreddit_hint)
    if not post:
        print(f"[DEBUG] Post filtered out: {url}")
    else:
        print(f"[DEBUG] Post kept:", post.get("score"), post.get("source"))
        print("    Topic focus:", post.get("topic_focus"))
        print("    Persona:", post.get("persona"), "Sentiment:", post.get("brand_sentiment"))

# ------------------------------
# eBay Forums (robust)
# ------------------------------

def scrape_forum_post_body(url: str):
    """
    Fetch an individual eBay community thread and extract the main body.
    Tries multiple CSS selectors for the body to be resilient to layout changes.
    """
    try:
        full = url if url.startswith("http") else f"https://community.ebay.com{url}"
        res = requests.get(full, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")

        body = (
            soup.select_one(".lia-message-body")
            or soup.select_one(".lia-message-body-content")
            or soup.select_one(".message-body")
            or soup.select_one(".lia-message-body-wrapper")
        )

        time_tag = soup.find("time")
        timestamp = (
            time_tag["datetime"]
            if time_tag and time_tag.has_attr("datetime")
            else None
        )
        try:
            post_date = (
                isoparse(timestamp).date().isoformat()
                if timestamp
                else NOW.date().isoformat()
            )
        except Exception:
            post_date = NOW.date().isoformat()

        return {
            "body": body.get_text(" ", strip=True) if body else "",
            "post_date": post_date,
            "url": full,
        }

    except Exception:
        return {"body": "", "post_date": NOW.date().isoformat(), "url": url}


def scrape_ebay_forum(category: str, base_url: str, max_pages: int = 2):
    """
    Scrape eBay community forums by category.
    """
    results = []

    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}?page={page}"
            res = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(res.text, "html.parser")

            threads = soup.select(".message-subject a, a.lia-message-subject, a.lia-link-navigation")
            if not threads:
                threads = [
                    a for a in soup.select("a[href*='/t5/']")
                    if "message-id" in (a.get("href") or "")
                ]

            for thread in threads:
                href = thread.get("href")
                if not href:
                    continue

                post = scrape_forum_post_body(href)
                if not post["body"]:
                    continue

                text = post["body"]

                # filters
                if not is_relevant(text):
                    continue
                if not collectibles_or_money_signal(text):
                    continue

                enriched = enrich_single_insight(
                    {
                        "text": text,
                        "url": post["url"],
                        "source": "eBay Forums",
                        "post_date": post["post_date"],
                        "_logged_date": NOW.date().isoformat(),
                        "forum_category": category,
                    }
                )

                if enriched:
                    payment_types = detect_payment_issue_types(text)
                    high_asp = is_high_asp(text)
                    upi_flag = "unpaid_item_upi" in payment_types
                    payment_flag = bool(payment_types)

                    enriched["_high_end_flag"] = high_asp
                    enriched["_payment_issue"] = payment_flag
                    enriched["payment_issue_types"] = payment_types
                    enriched["_upi_flag"] = upi_flag
                    if payment_flag:
                        enriched["topic_hint"] = "Payments"

                    enriched["is_case_break"] = is_case_break(text)
                    enriched["is_live_shopping"] = is_live_shopping(text)
                    enriched["is_dev_feedback"] = is_dev_feedback(text)
                    enriched["mentions"] = detect_competitor_and_partner_mentions(text)
                    enriched = apply_price_guide_flags(enriched, text)

                    results.append(enriched)

        except Exception as e:
            print(f"[ERROR] eBay forum scrape error in {category}: {e}")

    return results

# ------------------------------
# Blowout Cards Forums (session-based + XenForo-safe)
# ------------------------------

# Use Session for Blowout to mitigate Cloudflare-lite blocking
BLOWOUT_SESSION = requests.Session()
BLOWOUT_SESSION.headers.update(HEADERS)


def scrape_blowout_thread(thread_url: str, forum_label: str):
    """
    Scrape a single Blowout thread (XenForo 2, first post only).
    """
    try:
        res = BLOWOUT_SESSION.get(thread_url, timeout=20)
        if res.status_code != 200:
            print(f"[WARN] Blowout blocked or unavailable: {thread_url}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        title_el = soup.select_one("h1.p-title-value") or soup.select_one("h1")
        title = title_el.get_text(" ", strip=True) if title_el else ""

        body_el = (
            soup.select_one("article .bbWrapper")
            or soup.select_one("div.message-body .bbWrapper")
            or soup.select_one("div.message-content .bbWrapper")
        )
        body = body_el.get_text(" ", strip=True) if body_el else ""

        full_text = f"{title}\n{body}".strip()
        if not full_text:
            return None

        if not is_relevant(full_text):
            return None
        if not collectibles_or_money_signal(full_text):
            return None

        enriched = enrich_single_insight(
            {
                "text": full_text,
                "url": thread_url,
                "source": "Blowout Forums",
                "post_date": NOW.date().isoformat(),
                "_logged_date": NOW.date().isoformat(),
                "forum_category": forum_label,
            }
        )

        if not enriched:
            return None

        payment_types = detect_payment_issue_types(full_text)
        high_asp = is_high_asp(full_text)
        payment_flag = bool(payment_types)
        upi_flag = "unpaid_item_upi" in payment_types

        enriched["_high_end_flag"] = high_asp
        enriched["_payment_issue"] = payment_flag
        enriched["payment_issue_types"] = payment_types
        enriched["_upi_flag"] = upi_flag
        if payment_flag:
            enriched["topic_hint"] = "Payments"

        enriched["is_case_break"] = is_case_break(full_text)
        enriched["is_live_shopping"] = is_live_shopping(full_text)
        enriched["is_dev_feedback"] = False
        enriched["mentions"] = detect_competitor_and_partner_mentions(full_text)

        enriched = apply_price_guide_flags(enriched, full_text)

        return enriched

    except Exception as e:
        print(f"[ERROR] Blowout thread scrape failed: {thread_url} :: {e}")
        return None


def scrape_blowout_forum(label: str, base_url: str, max_pages: int = 2):
    """
    Scrape Blowout Cards forums across multiple pages with session + updated selectors.
    """
    results = []
    seen_threads = set()

    for page in range(1, max_pages + 1):
        try:
            url = base_url if page == 1 else f"{base_url}page-{page}"
            res = BLOWOUT_SESSION.get(url, timeout=20)
            if res.status_code != 200:
                print(f"[WARN] Blowout page blocked: {url}")
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            anchors = soup.select("h3.title a, a.thread-title, a[href*='/threads/']")
            for a in anchors:
                href = a.get("href")
                if not href:
                    continue

                if href.startswith("/"):
                    full = f"https://www.blowoutforums.com{href}"
                elif href.startswith("http"):
                    full = href
                else:
                    full = f"https://www.blowoutforums.com/{href.lstrip('/')}"

                if full in seen_threads:
                    continue
                seen_threads.add(full)

                enriched = scrape_blowout_thread(full, forum_label=label)
                if enriched:
                    results.append(enriched)

        except Exception as e:
            print(f"[ERROR] Blowout forum scrape error in '{label}': {e}")

        time.sleep(1.0)

    return results

# ------------------------------
# Main entrypoint
# ------------------------------

def run_signal_scraper():
    all_posts = []

    # eBay Community
    print("[INFO] Scraping eBay Forums...")
    for name, url in COMMUNITY_FORUMS.items():
        forum_results = scrape_ebay_forum(name, url)
        print(f"[INFO] eBay forum '{name}' produced {len(forum_results)} posts")
        all_posts.extend(forum_results)

    # Reddit
    print("[INFO] Scraping Reddit...")
    reddit = scrape_reddit_html()
    print(f"[INFO] Reddit posts kept: {len(reddit)}")
    all_posts.extend(reddit)

    # Blowout Forums
    print("[INFO] Scraping Blowout Cards Forums...")
    for label, url in BLOWOUT_FORUMS.items():
        blowout_results = scrape_blowout_forum(label, url)
        print(f"[INFO] Blowout forum '{label}' produced {len(blowout_results)} posts")
        all_posts.extend(blowout_results)

    # Twitter / X
    print("[INFO] Scraping Twitter...")
    for term in TWITTER_TERMS:
        tweets = run_snscrape_search(term)
        print(f"[INFO] {len(tweets)} tweets for '{term}'")

        for tweet in tweets:
            if not tweet:
                continue
            if is_mtg_irrelevant(tweet, subreddit_hint=None):
                continue

            keep = is_relevant(tweet)
            if not keep:
                tl = tweet.lower()
                keep = any(h in tl for h in PAYMENT_HINTS) or RE_UPI.search(tweet) is not None

            if keep:
                enriched = enrich_single_insight(
                    {
                        "text": tweet,
                        "source": "Twitter",
                        "url": "https://x.com/search?q=" + requests.utils.quote(tweet[:50]),
                        "post_date": NOW.date().isoformat(),
                        "_logged_date": NOW.date().isoformat(),
                    }
                )

                if enriched:
                    payment_types = detect_payment_issue_types(tweet)
                    high_asp = is_high_asp(tweet)
                    upi_flag = "unpaid_item_upi" in payment_types
                    payment_flag = bool(payment_types)

                    enriched["_high_end_flag"] = high_asp
                    enriched["_payment_issue"] = payment_flag
                    enriched["payment_issue_types"] = payment_types
                    enriched["_upi_flag"] = upi_flag
                    if payment_flag:
                        enriched["topic_hint"] = "Payments"

                    enriched["is_case_break"] = is_case_break(tweet)
                    enriched["is_live_shopping"] = is_live_shopping(tweet)
                    enriched["is_dev_feedback"] = is_dev_feedback(tweet)
                    enriched["mentions"] = detect_competitor_and_partner_mentions(tweet)

                    enriched = apply_price_guide_flags(enriched, tweet)

                    all_posts.append(enriched)

    # Save results
    os.makedirs(os.path.dirname(SAVE_PATH) or ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Saved {len(all_posts)} total posts to {SAVE_PATH}.")
    print(f"[INFO] Twitter: {len([p for p in all_posts if p.get('source') == 'Twitter'])}")
    print(f"[INFO] Reddit: {len([p for p in all_posts if p.get('source') == 'Reddit'])}")
    print(f"[INFO] Forums: {len([p for p in all_posts if p.get('source') == 'eBay Forums'])}")
    print(f"[INFO] Blowout: {len([p for p in all_posts if p.get('source') == 'Blowout Forums'])}")


if __name__ == "__main__":
    run_signal_scraper()
