# scrape_forums_blogs.py — Scrape collectibles forums, blogs, and marketplace signals
# Direct scraping for accessible sites, Google News RSS fallback for blocked ones.

import requests
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

SAVE_PATH = "data/scraped_forums_blogs_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── Google News RSS helper ──────────────────────────────────────

def _google_news_rss(query, source_label, max_results=100):
    """Fetch indexed content from Google News RSS for a given site: query."""
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
                "source": source_label,
                "url": link,
                "username": "",
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": 0,
                "post_id": f"gnews_{hash(link) % 10**8}",
            })
    except Exception as e:
        print(f"    [WARN] Google News RSS failed for '{query}': {e}")
    return posts


# ─── Bench Trading (direct scrape) ───────────────────────────────

def scrape_bench_trading():
    """Scrape The Bench Trading forum — direct HTML scraping."""
    print("  Bench Trading (direct)...")
    posts = []
    base_url = "https://thebenchtrading.com"

    try:
        r = requests.get(base_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"    [WARN] Bench Trading returned {r.status_code}, falling back to Google News")
            return _google_news_rss("site:thebenchtrading.com", "Bench Trading")

        soup = BeautifulSoup(r.text, "html.parser")

        # Find thread/topic links
        thread_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(x in href for x in ["/topic/", "/thread/", "/discussion/", "showthread"]):
                full_url = href if href.startswith("http") else f"{base_url}{href}"
                if full_url not in [t[1] for t in thread_links]:
                    thread_links.append((a.get_text(strip=True), full_url))

        print(f"    Found {len(thread_links)} threads")

        # Scrape up to 20 threads
        for title, url in thread_links[:20]:
            try:
                tr = requests.get(url, headers=HEADERS, timeout=10)
                if tr.status_code != 200:
                    continue

                tsoup = BeautifulSoup(tr.text, "html.parser")

                # Try to find post content
                post_elements = tsoup.find_all(["div", "article"], class_=re.compile(r"post|message|comment|content|body", re.I))
                if not post_elements:
                    post_elements = tsoup.find_all("p")

                for el in post_elements[:10]:
                    text = el.get_text(strip=True)
                    if len(text) < 30:
                        continue

                    posts.append({
                        "text": text[:2000],
                        "title": title,
                        "source": "Bench Trading",
                        "url": url,
                        "username": "",
                        "post_date": datetime.now().strftime("%Y-%m-%d"),
                        "_logged_date": datetime.now().isoformat(),
                        "search_term": "",
                        "score": 0,
                        "post_id": f"bench_{hash(text[:100]) % 10**8}",
                    })

                time.sleep(0.5)
            except Exception:
                continue

    except Exception as e:
        print(f"    [WARN] Bench Trading direct scrape failed: {e}")
        posts = _google_news_rss("site:thebenchtrading.com", "Bench Trading")

    # Supplement with Google News
    gn_posts = _google_news_rss("site:thebenchtrading.com", "Bench Trading")
    posts.extend(gn_posts)

    print(f"    Total: {len(posts)} posts")
    return posts


# ─── Alt.xyz Blog (direct scrape) ────────────────────────────────

def scrape_alt_blog():
    """Scrape Alt.xyz blog — direct HTML scraping."""
    print("  Alt.xyz Blog (direct)...")
    posts = []
    blog_url = "https://www.alt.xyz/blog"

    try:
        r = requests.get(blog_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"    [WARN] Alt.xyz returned {r.status_code}")
            return _google_news_rss("site:alt.xyz", "Alt.xyz Blog")

        soup = BeautifulSoup(r.text, "html.parser")

        # Find article links
        article_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/blog/" in href and href != "/blog/" and href != "/blog":
                full_url = href if href.startswith("http") else f"https://www.alt.xyz{href}"
                title = a.get_text(strip=True) or ""
                if full_url not in [al[1] for al in article_links] and len(title) > 5:
                    article_links.append((title, full_url))

        print(f"    Found {len(article_links)} articles")

        # Scrape up to 15 articles
        for title, url in article_links[:15]:
            try:
                ar = requests.get(url, headers=HEADERS, timeout=10)
                if ar.status_code != 200:
                    continue

                asoup = BeautifulSoup(ar.text, "html.parser")

                # Extract article body
                article_body = asoup.find("article") or asoup.find("main") or asoup.find("div", class_=re.compile(r"content|article|post|body", re.I))
                if article_body:
                    text = article_body.get_text(separator="\n", strip=True)
                else:
                    paragraphs = asoup.find_all("p")
                    text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)

                if len(text) < 50:
                    continue

                # Find date
                post_date = datetime.now().strftime("%Y-%m-%d")
                time_el = asoup.find("time")
                if time_el and time_el.get("datetime"):
                    try:
                        post_date = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                posts.append({
                    "text": text[:3000],
                    "title": title,
                    "source": "Alt.xyz Blog",
                    "url": url,
                    "username": "Alt.xyz",
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "search_term": "",
                    "score": 0,
                    "post_id": f"alt_{hash(url) % 10**8}",
                })

                time.sleep(0.5)
            except Exception:
                continue

    except Exception as e:
        print(f"    [WARN] Alt.xyz direct scrape failed: {e}")

    # Supplement with Google News
    gn_posts = _google_news_rss("site:alt.xyz", "Alt.xyz Blog")
    posts.extend(gn_posts)

    print(f"    Total: {len(posts)} posts")
    return posts


# ─── Google News RSS fallback sources ─────────────────────────────

def scrape_blowout_forums_gn():
    """Blowout Forums via Google News (direct scrape blocked by Incapsula)."""
    print("  Blowout Forums (Google News)...")
    posts = _google_news_rss("site:blowoutforums.com", "Blowout Forums")
    print(f"    {len(posts)} posts")
    return posts


def scrape_net54_gn():
    """Net54 Baseball via Google News (direct scrape returns 403)."""
    print("  Net54 Baseball (Google News)...")
    posts = _google_news_rss("site:net54baseball.com", "Net54 Baseball")
    print(f"    {len(posts)} posts")
    return posts


def scrape_comc_gn():
    """COMC via Google News (direct scrape returns 403). Filter out product catalog pages."""
    print("  COMC (Google News)...")
    posts = _google_news_rss("site:comc.com", "COMC")
    # Filter out product catalog pages (card listings, not user feedback)
    catalog_patterns = ["ungraded comc", "comc rcr", "comc ex to", "comc good to", "comc nm",
                        "baseball cards ungraded", "football cards ungraded", "basketball cards ungraded"]
    filtered = [p for p in posts if not any(cp in p.get("title", "").lower() for cp in catalog_patterns)]
    print(f"    {len(filtered)} posts ({len(posts) - len(filtered)} catalog pages filtered)")
    return filtered


def scrape_whatnot_gn():
    """Whatnot blog/news via Google News (direct scrape returns 403)."""
    print("  Whatnot (Google News)...")
    posts = _google_news_rss("site:whatnot.com", "Whatnot")
    print(f"    {len(posts)} posts")
    return posts


def scrape_fanatics_gn():
    """Fanatics Collect via Google News (domain doesn't resolve)."""
    print("  Fanatics Collect (Google News)...")
    # collect.fanatics.com doesn't resolve, search broader
    posts = _google_news_rss("fanatics collect trading cards", "Fanatics Collect")
    print(f"    {len(posts)} posts")
    return posts


def scrape_tcdb_gn():
    """Trading Card Database via Google News."""
    print("  TCDB (Google News)...")
    posts = _google_news_rss("site:tradingcarddb.com", "TCDB")
    print(f"    {len(posts)} posts")
    return posts


# ─── Main entry point ─────────────────────────────────────────────

def run_forums_blogs_scraper():
    """Main entry point for forums & blogs scraper."""
    print("\U0001f4ac Starting Forums & Blogs scraper...")

    all_posts = []

    # Direct scrape sources
    scrapers = [
        scrape_bench_trading,
        scrape_alt_blog,
        # Google News fallback sources
        scrape_blowout_forums_gn,
        scrape_net54_gn,
        scrape_comc_gn,
        scrape_whatnot_gn,
        scrape_fanatics_gn,
        scrape_tcdb_gn,
    ]

    for scraper_fn in scrapers:
        try:
            posts = scraper_fn()
            all_posts.extend(posts)
        except Exception as e:
            print(f"  \u274c {scraper_fn.__name__} failed: {e}")
        time.sleep(1.0)

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for post in all_posts:
        url = post.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique.append(post)

    # Sort by date
    unique.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    # Summary
    from collections import Counter
    source_counts = Counter(p.get("source", "?") for p in unique)
    print(f"\n  \u2705 Total: {len(unique)} unique posts")
    for src, cnt in source_counts.most_common():
        print(f"    {src}: {cnt}")
    print(f"  Saved to: {SAVE_PATH}")

    return unique


if __name__ == "__main__":
    run_forums_blogs_scraper()
