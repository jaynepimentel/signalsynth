# adhoc_scrape.py — Comprehensive on-demand topic scraper for Ask AI follow-up
# Scrapes 6 sources in parallel-style: Google News, Reddit, YouTube, Bluesky,
# Twitter/X (via Google), and Bing News. Enriches with sentiment, persona,
# signal strength, journey stage, and relevance ranking.
import requests
import json
import os
import re
import time
import math
from datetime import datetime
from typing import List, Dict, Any, Tuple
from urllib.parse import quote
from xml.etree import ElementTree as ET
from collections import Counter

ADHOC_PATH = "data/adhoc_scraped_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Domain-aware query expansion ──────────────────────────────────────
# Maps common collectibles concepts to related search terms
_DOMAIN_EXPANSIONS: Dict[str, List[str]] = {
    "vault": ["ebay vault", "psa vault", "card vault storage"],
    "authentication": ["authenticity guarantee", "ebay authentication", "AG program"],
    "grading": ["psa grading", "bgs grading", "cgc grading", "beckett grading"],
    "shipping": ["ebay shipping", "shipping damage cards", "global shipping program"],
    "returns": ["ebay returns", "inad returns", "return abuse"],
    "fees": ["ebay fees", "final value fee", "seller fees"],
    "whatnot": ["whatnot live breaks", "whatnot vs ebay", "whatnot marketplace"],
    "fanatics": ["fanatics collect", "fanatics marketplace", "fanatics ebay"],
    "price guide": ["ebay price guide", "card ladder", "scan to price"],
    "live": ["live breaks", "live shopping", "live auctions cards"],
    "beckett": ["beckett grading", "beckett acquisition", "beckett marketplace"],
    "psa": ["psa grading", "psa turnaround", "psa population report"],
    "heritage": ["heritage auctions", "heritage sports cards"],
    "comc": ["comc marketplace", "check out my cards"],
    "alt": ["alt marketplace", "alt trading cards"],
    "topps": ["topps baseball", "topps chrome", "topps releases"],
    "panini": ["panini basketball", "panini football", "panini prizm"],
    "bowman": ["bowman draft", "bowman chrome", "bowman prospects"],
    "breaks": ["card breaks", "live breaks", "box breaks"],
    "investing": ["sports card investing", "card market", "card values"],
    "pokemon": ["pokemon tcg", "pokemon cards ebay", "pokemon market"],
}


def _expand_queries(topic: str) -> List[str]:
    """Generate diverse search queries from a topic using domain knowledge."""
    queries = [topic]
    words = topic.lower().split()
    topic_lower = topic.lower()

    # Exact phrase variant
    if len(words) >= 2:
        queries.append(f'"{topic}"')

    # Domain-aware expansion: add related terms
    for trigger, expansions in _DOMAIN_EXPANSIONS.items():
        if trigger in topic_lower:
            for exp in expansions:
                if exp.lower() != topic_lower:
                    queries.append(exp)
            break  # One domain expansion per scrape to stay focused

    # Add "eBay" or "collectibles" context if not already present
    ebay_words = {"ebay", "e-bay"}
    collectible_words = {"card", "cards", "collectible", "collectibles", "trading", "grading", "hobby"}
    has_ebay = any(w in topic_lower for w in ebay_words)
    has_collectible = any(w in topic_lower for w in collectible_words)
    if not has_ebay and not has_collectible:
        queries.append(f"{topic} trading cards")
        queries.append(f"{topic} ebay collectibles")
    elif not has_ebay:
        queries.append(f"{topic} ebay")

    # Dedupe while preserving order
    seen = set()
    unique = []
    for q in queries:
        ql = q.lower().strip()
        if ql not in seen:
            seen.add(ql)
            unique.append(q)
    return unique[:6]  # Cap at 6 query variants


# ── RSS date parser ───────────────────────────────────────────────────
def _parse_rss_date(date_str: str) -> str:
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


# ── Source scrapers ───────────────────────────────────────────────────

def _scrape_google_news(query: str, max_results: int = 30) -> List[Dict[str, Any]]:
    """Scrape Google News RSS for a topic."""
    posts = []
    try:
        encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return posts
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()

            post_date = _parse_rss_date(pub_date)
            text = title
            if description and description != title:
                text = f"{title}\n{description}"
            if len(text) < 15:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": "Google News (adhoc)",
                "url": link,
                "username": "",
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": 0,
                "post_id": f"adhoc_gn_{hash(link) % 10**8}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] Google News failed for '{query}': {e}")
    return posts


def _scrape_bing_news(query: str, max_results: int = 25) -> List[Dict[str, Any]]:
    """Scrape Bing News RSS for a topic — complementary to Google News."""
    posts = []
    try:
        encoded = quote(query)
        rss_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return posts
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()

            post_date = _parse_rss_date(pub_date)
            text = title
            if description and description != title:
                text = f"{title}\n{description}"
            if len(text) < 15:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": "Bing News (adhoc)",
                "url": link,
                "username": "",
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": 0,
                "post_id": f"adhoc_bn_{hash(link) % 10**8}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] Bing News failed for '{query}': {e}")
    return posts


def _scrape_reddit_search(query: str, max_results: int = 30) -> List[Dict[str, Any]]:
    """Search Reddit for a topic via the public JSON API."""
    posts = []
    try:
        encoded = quote(query)
        url = f"https://www.reddit.com/search.json?q={encoded}&sort=relevance&limit={max_results}"
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
        if r.status_code != 200:
            return posts
        data = r.json()
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            text = f"{title}\n{selftext}" if selftext else title
            if len(text) < 15:
                continue

            created = p.get("created_utc", 0)
            post_date = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else datetime.now().strftime("%Y-%m-%d")

            posts.append({
                "text": text[:3000],
                "title": title,
                "source": "Reddit (adhoc)",
                "subreddit": p.get("subreddit", ""),
                "url": f"https://www.reddit.com{p.get('permalink', '')}",
                "username": p.get("author", ""),
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "post_id": f"adhoc_rd_{p.get('id', hash(title) % 10**8)}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] Reddit search failed for '{query}': {e}")
    return posts


def _scrape_twitter_via_google(query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """Scrape indexed tweets via Google News RSS (site:x.com query)."""
    posts = []
    try:
        gn_query = f"site:x.com OR site:twitter.com {query}"
        encoded = quote(gn_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return posts
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()

            post_date = _parse_rss_date(pub_date)
            text = title
            if description and description != title:
                text = f"{title}\n{description}"
            if len(text) < 15:
                continue

            # Extract username from URL
            username = ""
            url_match = re.search(r"(?:x\.com|twitter\.com)/(\w+)", link)
            if url_match:
                username = f"@{url_match.group(1)}"

            posts.append({
                "text": text,
                "title": title,
                "source": "Twitter/X (adhoc)",
                "url": link,
                "username": username,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": 0,
                "post_id": f"adhoc_tw_{hash(link) % 10**8}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] Twitter/X search failed for '{query}': {e}")
    return posts


def _scrape_youtube_rss(query: str, max_results: int = 15) -> List[Dict[str, Any]]:
    """Search YouTube via Google News RSS (site:youtube.com) — no API key needed."""
    posts = []
    try:
        gn_query = f"site:youtube.com {query}"
        encoded = quote(gn_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return posts
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()

            post_date = _parse_rss_date(pub_date)
            text = title
            if description and description != title:
                text = f"{title}\n{description}"
            if len(text) < 15:
                continue

            # Extract channel from title pattern "Title - Channel Name"
            channel = ""
            if " - " in title:
                channel = title.rsplit(" - ", 1)[-1].strip()

            posts.append({
                "text": text,
                "title": title,
                "source": "YouTube (adhoc)",
                "url": link,
                "username": channel,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": 0,
                "post_id": f"adhoc_yt_{hash(link) % 10**8}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] YouTube RSS failed for '{query}': {e}")
    return posts


def _scrape_bluesky(query: str, max_results: int = 25) -> List[Dict[str, Any]]:
    """Search Bluesky public API — no auth required."""
    posts = []
    try:
        bsky_api = "https://public.api.bsky.app"
        url = f"{bsky_api}/xrpc/app.bsky.feed.searchPosts"
        params = {"q": query, "limit": min(max_results, 25), "sort": "latest"}
        bsky_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/json",
        }
        r = requests.get(url, params=params, headers=bsky_headers, timeout=15)
        if r.status_code != 200:
            return posts

        data = r.json()
        for post in data.get("posts", []):
            try:
                record = post.get("record", {})
                text = record.get("text", "")
                if not text or len(text) < 20:
                    continue

                author = post.get("author", {})
                handle = author.get("handle", "unknown")
                display_name = author.get("displayName", handle)

                uri = post.get("uri", "")
                post_id = uri.split("/")[-1] if uri else ""
                web_url = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else ""

                created_at = record.get("createdAt", "")
                post_date = datetime.now().strftime("%Y-%m-%d")
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        post_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                posts.append({
                    "text": text,
                    "title": text[:120],
                    "source": "Bluesky (adhoc)",
                    "url": web_url,
                    "username": f"@{handle}",
                    "display_name": display_name,
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "search_term": query,
                    "score": post.get("likeCount", 0),
                    "like_count": post.get("likeCount", 0),
                    "repost_count": post.get("repostCount", 0),
                    "reply_count": post.get("replyCount", 0),
                    "post_id": f"adhoc_bs_{hash(web_url) % 10**8}",
                    "_adhoc": True,
                    "_adhoc_query": query,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  [WARN] Bluesky search failed for '{query}': {e}")
    return posts


# ── Enrichment ────────────────────────────────────────────────────────

_NEG_KEYWORDS = [
    "complaint", "issue", "problem", "frustrated", "broken", "scam", "terrible",
    "awful", "hate", "worst", "disappointed", "angry", "ridiculous", "unacceptable",
    "poor", "horrible", "garbage", "pathetic", "disgusted", "furious", "unusable",
    "rip off", "ripoff", "waste", "misleading", "deceptive", "fraud", "sketchy",
]
_POS_KEYWORDS = [
    "love", "great", "amazing", "excellent", "impressed", "best", "happy",
    "fantastic", "awesome", "perfect", "brilliant", "wonderful", "smooth",
    "reliable", "trustworthy", "convenient", "delighted", "outstanding",
    "seamless", "intuitive", "recommend", "kudos", "praise", "grateful",
]
_CHURN_KEYWORDS = [
    "leaving", "switching", "cancel", "done with", "moving to", "left ebay",
    "quit", "never again", "goodbye", "going to whatnot", "going to fanatics",
    "better on", "prefer", "stopped using",
]
_FEATURE_KEYWORDS = [
    "should", "wish", "need", "please add", "feature request", "would be nice",
    "it would help", "suggestion", "idea", "they should", "want to see",
    "hoping for", "can we get", "why can't",
]
_BUG_KEYWORDS = [
    "bug", "crash", "error", "glitch", "not working", "broken", "fails",
    "stuck", "unresponsive", "page won't load",
]

_TOPIC_MAP = {
    "Vault": ["vault", "psa vault", "ebay vault", "card vault"],
    "Authentication": ["authentication", "authenticity guarantee", "ag program", "verified authentic"],
    "Grading": ["grading", "psa", "bgs", "cgc", "beckett grading", "grade", "slab"],
    "Price Guide": ["price guide", "card ladder", "scan to price", "card value", "comp prices"],
    "Shipping": ["shipping", "tracking", "label", "damaged in transit", "global shipping"],
    "Payments": ["payment", "payout", "funds held", "managed payments", "payment processing"],
    "Returns": ["return", "inad", "refund", "money back", "return abuse"],
    "Fees": ["fee", "final value", "commission", "seller fees", "listing fee"],
    "Promoted Listings": ["promoted listing", "promoted standard", "promoted advanced", "ad rate"],
    "Search & Discovery": ["search", "best match", "visibility", "seo", "search ranking"],
    "Live Shopping": ["live break", "whatnot", "live shopping", "live auction", "live stream"],
    "Acquisition": ["acquisition", "acquired", "merger", "bought", "purchase deal"],
    "Trust & Safety": ["scam", "counterfeit", "fake", "fraud", "seller protection", "buyer abuse"],
    "Catalog & Listings": ["catalog", "listing", "item specifics", "product ID", "category"],
    "Mobile App": ["app", "mobile", "mobile app", "ios", "android"],
    "Market Trends": ["market", "prices", "investing", "value", "bubble", "crash"],
    "Releases & Products": ["release", "product", "chrome", "prizm", "bowman", "topps", "panini"],
    "Competitors": ["whatnot", "fanatics", "heritage", "comc", "alt", "goldin", "pwcc"],
}

_PERSONA_SIGNALS = {
    "Power Seller": ["my store", "my listings", "my sales", "as a seller", "top rated", "volume seller"],
    "Casual Seller": ["sold my", "trying to sell", "listed a", "selling some"],
    "Collector": ["my collection", "collecting", "pc ", "personal collection", "i collect"],
    "Investor": ["investing", "investment", "roi", "portfolio", "flip", "profit"],
    "Breaker": ["break", "ripping", "case break", "box break", "live break"],
    "Buyer": ["just bought", "purchased", "bid on", "won auction", "shopping for"],
    "Industry Observer": ["industry", "market", "trend", "analysis", "report", "data"],
}

_JOURNEY_SIGNALS = {
    "Awareness": ["heard about", "just found", "what is", "anyone know", "new to"],
    "Consideration": ["thinking about", "comparing", "vs ", "which is better", "should i"],
    "Active Use": ["i use", "i'm using", "been using", "my experience", "every day"],
    "Frustration": ["frustrated", "angry", "issue", "problem", "broken", "can't believe"],
    "Churn Risk": _CHURN_KEYWORDS,
    "Advocacy": ["recommend", "love it", "best platform", "everyone should", "switched to ebay"],
}


def _enrich(post: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Apply comprehensive enrichment to adhoc posts."""
    text_lower = (post.get("text", "") + " " + post.get("title", "")).lower()
    text_len = len(text_lower)

    # ── Sentiment (weighted) ──
    neg_score = sum(1 for k in _NEG_KEYWORDS if k in text_lower)
    pos_score = sum(1 for k in _POS_KEYWORDS if k in text_lower)
    churn_score = sum(1 for k in _CHURN_KEYWORDS if k in text_lower)
    neg_score += churn_score  # churn amplifies negativity

    if neg_score > pos_score + 1:
        post["brand_sentiment"] = "Negative"
    elif pos_score > neg_score + 1:
        post["brand_sentiment"] = "Positive"
    elif neg_score > pos_score:
        post["brand_sentiment"] = "Mixed-Negative"
    elif pos_score > neg_score:
        post["brand_sentiment"] = "Mixed-Positive"
    else:
        post["brand_sentiment"] = "Neutral"

    # ── Type classification ──
    feat_score = sum(1 for k in _FEATURE_KEYWORDS if k in text_lower)
    bug_score = sum(1 for k in _BUG_KEYWORDS if k in text_lower)
    if feat_score >= 2 or (feat_score == 1 and neg_score == 0):
        post["type_tag"] = "Feature Request"
    elif bug_score >= 2:
        post["type_tag"] = "Bug Report"
    elif churn_score >= 1:
        post["type_tag"] = "Churn Signal"
    elif neg_score >= 2:
        post["type_tag"] = "Complaint"
    elif pos_score >= 2:
        post["type_tag"] = "Praise"
    elif any(k in text_lower for k in ["news", "announce", "launch", "release", "report"]):
        post["type_tag"] = "Industry News"
    elif "?" in post.get("text", "") and text_len < 300:
        post["type_tag"] = "Question"
    else:
        post["type_tag"] = "Discussion"

    # ── Topic detection (multi-label, take best) ──
    topic_scores = {}
    for topic, keywords in _TOPIC_MAP.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            topic_scores[topic] = score
    if topic_scores:
        best_topic = max(topic_scores, key=topic_scores.get)
        post["subtag"] = best_topic
        # secondary topics
        secondary = [t for t, s in sorted(topic_scores.items(), key=lambda x: -x[1]) if t != best_topic][:2]
        post["secondary_topics"] = secondary
    else:
        post["subtag"] = "General"
        post["secondary_topics"] = []

    # ── Persona detection ──
    persona = "Unknown"
    best_persona_score = 0
    for p_name, p_keywords in _PERSONA_SIGNALS.items():
        p_score = sum(1 for k in p_keywords if k in text_lower)
        if p_score > best_persona_score:
            best_persona_score = p_score
            persona = p_name
    post["persona"] = persona

    # ── Journey stage ──
    journey = "Unknown"
    best_journey_score = 0
    for j_name, j_keywords in _JOURNEY_SIGNALS.items():
        j_score = sum(1 for k in j_keywords if k in text_lower)
        if j_score > best_journey_score:
            best_journey_score = j_score
            journey = j_name
    post["journey_stage"] = journey

    # ── Signal strength (0–100 composite) ──
    engagement = float(post.get("score", 0) or 0)
    comments = float(post.get("num_comments", 0) or 0)
    likes = float(post.get("like_count", 0) or 0)
    engagement_total = engagement + comments + likes

    # Engagement component (0–30)
    engagement_component = min(30, math.log2(engagement_total + 1) * 5)

    # Specificity component (0–25) — how many specific names/features mentioned
    specificity_terms = [
        "ebay", "psa", "bgs", "cgc", "whatnot", "fanatics", "heritage",
        "vault", "authentication", "price guide", "card ladder", "promoted",
        "goldin", "comc", "alt", "topps", "panini", "bowman",
    ]
    specificity = sum(1 for t in specificity_terms if t in text_lower)
    specificity_component = min(25, specificity * 5)

    # Pain/impact component (0–25)
    pain = neg_score + churn_score + bug_score
    pain_component = min(25, pain * 6)

    # Content depth component (0–20) — longer, more substantive posts score higher
    depth_component = min(20, (text_len / 200) * 4)

    signal_strength = round(engagement_component + specificity_component + pain_component + depth_component)
    post["signal_strength"] = max(10, min(100, signal_strength))

    # ── Relevance to query (0–100) ──
    query_words = set(query.lower().split())
    title_lower = post.get("title", "").lower()
    # Exact phrase match bonus
    exact_match = 40 if query.lower() in text_lower else 0
    # Word overlap
    word_overlap = sum(1 for w in query_words if w in text_lower and len(w) > 2)
    word_component = min(30, word_overlap * 10)
    # Title match bonus
    title_match = sum(1 for w in query_words if w in title_lower and len(w) > 2)
    title_component = min(20, title_match * 8)
    # Recency bonus (recent posts more relevant)
    try:
        days_old = (datetime.now() - datetime.strptime(post.get("post_date", "2020-01-01"), "%Y-%m-%d")).days
    except Exception:
        days_old = 365
    recency_component = max(0, 10 - days_old / 30)

    post["_relevance_score"] = round(exact_match + word_component + title_component + recency_component)

    # ── Taxonomy ──
    post["taxonomy"] = {
        "type": post.get("type_tag", "Discussion"),
        "topic": post.get("subtag", "General"),
        "theme": post.get("subtag", "General"),
    }
    post["clarity"] = "High" if text_len > 200 else ("Medium" if text_len > 80 else "Low")
    post["ideas"] = []

    return post


# ── Persistence ───────────────────────────────────────────────────────

def _load_existing() -> List[Dict[str, Any]]:
    """Load existing adhoc posts."""
    if os.path.exists(ADHOC_PATH):
        try:
            with open(ADHOC_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save(posts: List[Dict[str, Any]]):
    """Save adhoc posts."""
    os.makedirs(os.path.dirname(ADHOC_PATH) if os.path.dirname(ADHOC_PATH) else ".", exist_ok=True)
    with open(ADHOC_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


# ── Main entry point ─────────────────────────────────────────────────

def run_adhoc_scrape(topic: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Run a comprehensive ad-hoc scrape across 6 sources for a specific topic.

    Sources: Google News, Bing News, Reddit, Twitter/X, YouTube, Bluesky.
    Each post is enriched with sentiment, persona, journey stage, signal
    strength, and relevance ranking.

    Returns:
        (new_posts, summary_message)
    """
    print(f"🔍 Ad-hoc scrape: '{topic}'")

    queries = _expand_queries(topic)
    print(f"  📝 Query variants: {queries}")

    all_posts = []
    source_log = []

    # 1. Google News — primary news source
    for q in queries[:3]:
        print(f"  📰 Google News: {q}")
        posts = _scrape_google_news(q)
        all_posts.extend(posts)
        if posts:
            source_log.append(f"Google News({len(posts)})")
        time.sleep(0.3)

    # 2. Bing News — complementary news coverage
    for q in queries[:2]:
        print(f"  🔎 Bing News: {q}")
        posts = _scrape_bing_news(q)
        all_posts.extend(posts)
        if posts:
            source_log.append(f"Bing News({len(posts)})")
        time.sleep(0.3)

    # 3. Reddit — community discussions
    for q in queries[:2]:
        print(f"  💬 Reddit: {q}")
        posts = _scrape_reddit_search(q)
        all_posts.extend(posts)
        if posts:
            source_log.append(f"Reddit({len(posts)})")
        time.sleep(0.3)

    # 4. Twitter/X — social pulse via Google indexing
    print(f"  🐦 Twitter/X: {topic}")
    tw_posts = _scrape_twitter_via_google(topic)
    all_posts.extend(tw_posts)
    if tw_posts:
        source_log.append(f"Twitter/X({len(tw_posts)})")
    time.sleep(0.3)

    # 5. YouTube — video commentary
    print(f"  🎥 YouTube: {topic}")
    yt_posts = _scrape_youtube_rss(topic)
    all_posts.extend(yt_posts)
    if yt_posts:
        source_log.append(f"YouTube({len(yt_posts)})")
    time.sleep(0.3)

    # 6. Bluesky — emerging social signals
    for q in queries[:2]:
        print(f"  🦋 Bluesky: {q}")
        posts = _scrape_bluesky(q)
        all_posts.extend(posts)
        if posts:
            source_log.append(f"Bluesky({len(posts)})")
        time.sleep(0.3)

    # ── Deduplicate by URL or title ──
    seen = set()
    unique = []
    for p in all_posts:
        key = p.get("url", "") or p.get("title", "")[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    # ── Enrich all posts ──
    enriched = [_enrich(p, topic) for p in unique]

    # ── Rank by relevance + signal strength ──
    enriched.sort(key=lambda x: (x.get("_relevance_score", 0) + x.get("signal_strength", 0)), reverse=True)

    # ── Merge with existing adhoc data ──
    existing = _load_existing()
    existing_urls = {p.get("url", "") for p in existing if p.get("url")}
    existing_titles = {p.get("title", "")[:80] for p in existing if p.get("title")}
    new_posts = [
        p for p in enriched
        if (p.get("url", "") not in existing_urls)
        and (p.get("title", "")[:80] not in existing_titles)
    ]
    merged = existing + new_posts
    _save(merged)

    # ── Summary ──
    source_counts = Counter(p.get("source", "?") for p in new_posts)
    summary_parts = [f"**{cnt}** from {src}" for src, cnt in source_counts.most_common()]
    sources_hit = len(source_counts)
    sentiment_counts = Counter(p.get("brand_sentiment", "?") for p in new_posts)
    sentiment_parts = [f"{cnt} {s}" for s, cnt in sentiment_counts.most_common(3)]

    summary = (
        f"Scraped **{len(new_posts)} new posts** across **{sources_hit} sources** "
        f"for \"{topic}\".\n\n"
        f"**By source:** {', '.join(summary_parts) if summary_parts else 'no new posts found'}.\n\n"
        f"**Sentiment mix:** {', '.join(sentiment_parts) if sentiment_parts else 'n/a'}.\n\n"
        f"Total adhoc dataset: **{len(merged)} posts**."
    )

    print(f"  ✅ {len(new_posts)} new posts added from {sources_hit} sources (total adhoc: {len(merged)})")
    return new_posts, summary


if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Beckett acquisition PSA Collectors Universe"
    posts, summary = run_adhoc_scrape(topic)
    print(summary)
