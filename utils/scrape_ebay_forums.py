# scrape_ebay_forums.py — eBay Community Forums scraper
# Primary strategy: Lithium REST API v2 (LiQL) — bypasses Akamai WAF.
# Secondary strategy: Google News RSS with site:community.ebay.com queries.
# Direct HTML scraping is blocked by Akamai (HTTP 202 JS challenge).
import requests
import json
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

SAVE_PATH = "data/scraped_ebay_forums.json"

LITHIUM_API = "https://community.ebay.com/api/2.0/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

HTML_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Collectibles-relevant keyword searches for targeted LiQL queries
KEYWORD_SEARCHES = [
    "trading cards",
    "sports cards",
    "collectibles",
    "grading",
    "psa",
    "vault",
    "authenticity guarantee",
    "authentication",
    "shipping damage",
    "seller fees",
    "returns",
    "promoted listings",
    "price guide",
    "live breaks",
    "whatnot",
    "fanatics",
    "heritage auctions",
    "pokemon cards",
    "baseball cards",
    "football cards",
    "basketball cards",
    "funko",
    "coins",
    "seller defect",
    "payment hold",
    "final value fee",
    "standard envelope",
    "ebay international shipping",
    "managed payments",
    "item not as described",
]

# Google News RSS queries for supplementary indexed content
GN_QUERIES = [
    "site:community.ebay.com",
    "site:community.ebay.com seller",
    "site:community.ebay.com trading cards",
    "site:community.ebay.com collectibles",
    "site:community.ebay.com vault",
    "site:community.ebay.com shipping returns",
    "site:community.ebay.com payments",
    "site:community.ebay.com authenticity guarantee",
    "site:community.ebay.com grading",
    "site:community.ebay.com fees",
    '"ebay community" seller complaint',
    '"ebay community" trading cards',
    '"ebay community" collectibles',
    '"ebay forum" seller problem',
]


# ── Lithium REST API v2 (LiQL) ────────────────────────────────────────

def _strip_html(html_text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not html_text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_lithium_date(date_str: str) -> str:
    """Parse Lithium ISO timestamp to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return date_str[:10]
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _liql_query(query: str) -> List[Dict[str, Any]]:
    """Execute a LiQL query against the Lithium REST API v2."""
    try:
        r = requests.get(LITHIUM_API, params={"q": query}, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("status") != "success":
            return []
        return data.get("data", {}).get("items", [])
    except Exception as e:
        print(f"    [WARN] LiQL query failed: {e}")
        return []


def _parse_lithium_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Lithium API message item to our standard post format."""
    subject = item.get("subject", "").strip()
    body_html = item.get("body", "") or ""
    body_text = _strip_html(body_html)
    author = item.get("author", {}).get("login", "unknown")
    post_time = item.get("post_time", "")
    board_id = item.get("board", {}).get("id", "unknown")
    view_href = item.get("view_href", "")
    views = 0
    metrics = item.get("metrics", {})
    if metrics:
        views = metrics.get("views", 0)
    depth = item.get("depth", 0)

    # Build full URL
    url = view_href if view_href.startswith("http") else f"https://community.ebay.com{view_href}" if view_href else ""

    # Combine subject + body
    text = f"{subject}\n\n{body_text}" if body_text and body_text != subject else subject
    if len(text) < 20:
        return None

    # Truncate very long posts
    if len(text) > 3000:
        text = text[:3000] + "..."

    post_date = _parse_lithium_date(post_time)

    return {
        "text": text,
        "title": subject,
        "source": "eBay Forums",
        "forum_section": board_id,
        "username": author,
        "url": url,
        "post_date": post_date,
        "_logged_date": datetime.now().isoformat(),
        "is_original_post": depth == 0,
        "depth": depth,
        "views": views,
        "score": views,
        "post_id": f"ebay_li_{hash(url or subject) % 10**8}",
    }


def _scrape_recent_posts(limit: int = 100) -> List[Dict[str, Any]]:
    """Scrape the most recent original posts via LiQL."""
    print(f"  📥 Fetching {limit} most recent forum posts...")
    query = (
        f"SELECT subject,body,post_time,author.login,board.id,view_href,metrics.views,depth "
        f"FROM messages WHERE depth=0 ORDER BY post_time DESC LIMIT {limit}"
    )
    items = _liql_query(query)
    posts = []
    for item in items:
        post = _parse_lithium_item(item)
        if post:
            posts.append(post)
    print(f"    Got {len(posts)} recent posts")
    return posts


def _scrape_recent_replies(limit: int = 50) -> List[Dict[str, Any]]:
    """Scrape recent high-value replies (depth > 0) for richer thread context."""
    print(f"  💬 Fetching {limit} recent replies...")
    query = (
        f"SELECT subject,body,post_time,author.login,board.id,view_href,depth "
        f"FROM messages WHERE depth>0 ORDER BY post_time DESC LIMIT {limit}"
    )
    items = _liql_query(query)
    posts = []
    for item in items:
        post = _parse_lithium_item(item)
        if post and len(post.get("text", "")) > 50:
            posts.append(post)
    print(f"    Got {len(posts)} replies")
    return posts


def _scrape_keyword(keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search for posts matching a keyword via LiQL MATCHES clause."""
    query = (
        f"SELECT subject,body,post_time,author.login,board.id,view_href,metrics.views,depth "
        f"FROM messages WHERE body MATCHES '{keyword}' AND depth=0 "
        f"ORDER BY post_time DESC LIMIT {limit}"
    )
    items = _liql_query(query)
    posts = []
    for item in items:
        post = _parse_lithium_item(item)
        if post:
            post["search_term"] = keyword
            posts.append(post)
    return posts


def _scrape_keywords(keywords: List[str], limit_per: int = 50) -> List[Dict[str, Any]]:
    """Run keyword searches across collectibles-relevant terms."""
    print(f"  🔍 Searching {len(keywords)} keywords (limit {limit_per} each)...")
    all_posts = []
    for kw in keywords:
        posts = _scrape_keyword(kw, limit=limit_per)
        if posts:
            print(f"    '{kw}' => {len(posts)} posts")
        all_posts.extend(posts)
        time.sleep(0.3)
    print(f"    Total keyword posts: {len(all_posts)}")
    return all_posts


# ── Google News RSS (secondary) ────────────────────────────────────────

def _google_news_rss(query: str, max_results: int = 100) -> List[Dict[str, Any]]:
    """Fetch indexed eBay community content from Google News RSS."""
    posts = []
    try:
        encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(rss_url, headers=HTML_HEADERS, timeout=15)
        if r.status_code != 200:
            return posts
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()

            post_date = datetime.now().strftime("%Y-%m-%d")
            if pub_date:
                try:
                    from email.utils import parsedate_to_datetime
                    post_date = parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
                except Exception:
                    pass

            text = title
            if description and description != title:
                text = f"{title}\n{description}"
            if len(text) < 20:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": "eBay Forums",
                "url": link,
                "username": "",
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "forum_section": "Google News",
                "search_term": query,
                "score": 0,
                "post_id": f"ebay_gn_{hash(link) % 10**8}",
            })
    except Exception as e:
        print(f"    [WARN] Google News RSS failed for '{query}': {e}")
    return posts


def _scrape_google_news_supplement() -> List[Dict[str, Any]]:
    """Run Google News RSS queries for supplementary indexed content."""
    print(f"  � Running {len(GN_QUERIES)} Google News RSS queries...")
    all_posts = []
    for q in GN_QUERIES:
        posts = _google_news_rss(q)
        if posts:
            print(f"    '{q[:50]}' => {len(posts)} items")
        all_posts.extend(posts)
        time.sleep(0.5)
    print(f"    Total Google News posts: {len(all_posts)}")
    return all_posts


# ── Main entry point ─────────────────────────────────────────────────

def run_ebay_forums_scraper() -> List[Dict[str, Any]]:
    """Main entry point for eBay Forums scraping.

    Strategy:
    1. Lithium REST API v2 (LiQL) — recent posts + keyword searches
    2. Google News RSS — supplementary indexed content

    Returns list of post dicts.
    """
    print("� Starting eBay Community Forums scraper...")
    print("  Strategy: Lithium API v2 (LiQL) + Google News RSS")

    all_posts = []

    # ── Primary: Lithium API v2 ──
    print("\n── Phase 1: Lithium REST API v2 ──")

    # 1a. Recent original posts (broad, latest activity)
    recent = _scrape_recent_posts(limit=100)
    all_posts.extend(recent)

    # 1b. Recent replies (thread depth for richer context)
    replies = _scrape_recent_replies(limit=50)
    all_posts.extend(replies)

    # 1c. Keyword searches (collectibles-focused)
    keyword_posts = _scrape_keywords(KEYWORD_SEARCHES, limit_per=50)
    all_posts.extend(keyword_posts)

    lithium_count = len(all_posts)
    print(f"\n  Lithium API total (pre-dedup): {lithium_count}")

    # ── Secondary: Google News RSS ──
    print("\n── Phase 2: Google News RSS (supplementary) ──")
    gn_posts = _scrape_google_news_supplement()
    all_posts.extend(gn_posts)

    print(f"\n  Combined total (pre-dedup): {len(all_posts)}")

    if not all_posts:
        print("\n❌ No posts scraped from eBay Forums.")
        return []

    # ── Deduplicate ──
    seen_urls = set()
    seen_titles = set()
    unique_posts = []
    for post in all_posts:
        url = post.get("url", "")
        title_key = post.get("title", "")[:80].lower().strip()

        # Dedup by URL first, then by title similarity
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        unique_posts.append(post)

    # ── Save ──
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Scraped {len(unique_posts)} unique posts → {SAVE_PATH}")
    print(f"   (Lithium API: ~{lithium_count} raw, Google News: ~{len(gn_posts)} raw)")

    # Print section breakdown
    section_counts = {}
    for post in unique_posts:
        sec = post.get("forum_section", "unknown")
        section_counts[sec] = section_counts.get(sec, 0) + 1

    print("\n📊 Posts by section/board:")
    for sec, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        print(f"  {sec}: {count}")

    return unique_posts


if __name__ == "__main__":
    run_ebay_forums_scraper()
