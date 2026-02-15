# scrape_news_rss.py — RSS feed scraper for collectibles industry news outlets
import requests
import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any
from xml.etree import ElementTree as ET
from html import unescape

# RSS feeds to scrape — high-signal collectibles/marketplace news sources
RSS_FEEDS = [
    {
        "name": "Beckett News",
        "url": "https://www.beckett.com/news/feed/",
        "focus": "Checklists, product releases, hobby news, pricing",
    },
    {
        "name": "Just Collect Blog",
        "url": "https://blog.justcollect.com/rss.xml",
        "focus": "Vintage cards, grading news, collecting tips, market insights",
    },
    {
        "name": "Cardlines",
        "url": "https://cardlines.com/feed/",
        "focus": "Grading trends, market analysis, breaks, investing",
    },
    {
        "name": "Cardboard Connection",
        "url": "https://www.cardboardconnection.com/feed",
        "focus": "Set reviews, product guides, checklists, releases",
    },
    {
        "name": "Dave and Adams",
        "url": "https://www.dacardworld.com/blog/feed/",
        "focus": "Product news, chase cards, market trends",
    },
]

SAVE_PATH = "data/scraped_news_rss_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# XML namespaces commonly used in RSS feeds
NAMESPACES = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}


def strip_html(html_text: str) -> str:
    """Remove HTML tags and decode entities from text."""
    if not html_text:
        return ""
    # Remove CDATA wrappers
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', html_text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode HTML entities
    text = unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_rss_date(date_str: str) -> str:
    """Parse an RSS date string into YYYY-MM-DD format."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    # Common RSS date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",      # RFC 822: Mon, 01 Jan 2026 12:00:00 +0000
        "%a, %d %b %Y %H:%M:%S %Z",      # Mon, 01 Jan 2026 12:00:00 GMT
        "%Y-%m-%dT%H:%M:%S%z",            # ISO 8601
        "%Y-%m-%dT%H:%M:%SZ",             # ISO 8601 UTC
        "%Y-%m-%d %H:%M:%S",              # Simple datetime
        "%Y-%m-%d",                        # Simple date
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return datetime.now().strftime("%Y-%m-%d")


def fetch_rss_feed(feed_config: Dict[str, str], max_items: int = 25) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS feed."""
    feed_name = feed_config["name"]
    feed_url = feed_config["url"]
    feed_focus = feed_config["focus"]
    posts = []

    try:
        res = requests.get(feed_url, headers=HEADERS, timeout=20)

        if res.status_code != 200:
            print(f"    ⚠️ HTTP {res.status_code}")
            return posts

        # Parse XML
        root = ET.fromstring(res.content)

        # Handle both RSS 2.0 and Atom feeds
        items = root.findall(".//item")
        if not items:
            # Try Atom format
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items[:max_items]:
            try:
                # Extract title
                title_elem = item.find("title")
                title = ""
                if title_elem is not None and title_elem.text:
                    title = strip_html(title_elem.text)

                if not title or len(title) < 10:
                    continue

                # Extract link
                link_elem = item.find("link")
                link = ""
                if link_elem is not None:
                    link = link_elem.text or link_elem.get("href", "")

                # Extract description / summary
                description = ""
                desc_elem = item.find("description")
                if desc_elem is not None and desc_elem.text:
                    description = strip_html(desc_elem.text)

                # Try content:encoded for full article text
                content_elem = item.find("content:encoded", NAMESPACES)
                content_text = ""
                if content_elem is not None and content_elem.text:
                    content_text = strip_html(content_elem.text)

                # Use the richest text available
                body = content_text or description or ""

                # Combine title + body
                full_text = f"{title}\n\n{body}" if body else title

                # Truncate very long articles
                if len(full_text) > 3000:
                    full_text = full_text[:3000] + "..."

                # Extract publish date
                pub_date_elem = item.find("pubDate")
                if pub_date_elem is None:
                    pub_date_elem = item.find("dc:date", NAMESPACES)
                if pub_date_elem is None:
                    pub_date_elem = item.find("{http://www.w3.org/2005/Atom}published")

                post_date = parse_rss_date(
                    pub_date_elem.text if pub_date_elem is not None else ""
                )

                # Extract author
                author = feed_name
                creator_elem = item.find("dc:creator", NAMESPACES)
                if creator_elem is not None and creator_elem.text:
                    author = strip_html(creator_elem.text)
                else:
                    author_elem = item.find("{http://www.w3.org/2005/Atom}author")
                    if author_elem is not None:
                        name_elem = author_elem.find("{http://www.w3.org/2005/Atom}name")
                        if name_elem is not None and name_elem.text:
                            author = name_elem.text

                # Extract categories
                categories = []
                for cat_elem in item.findall("category"):
                    if cat_elem.text:
                        categories.append(strip_html(cat_elem.text))

                posts.append({
                    "text": full_text,
                    "title": title,
                    "source": f"News:{feed_name}",
                    "feed_name": feed_name,
                    "feed_focus": feed_focus,
                    "username": author,
                    "url": link.strip() if link else "",
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "categories": categories,
                    "summary": description[:500] if description else "",
                })

            except Exception:
                continue

    except requests.exceptions.Timeout:
        print(f"    ⏱️ Timeout")
    except ET.ParseError as e:
        print(f"    ❌ XML parse error: {e}")
    except Exception as e:
        print(f"    ❌ Error: {e}")

    return posts


def run_news_rss_scraper(max_items_per_feed: int = 25) -> List[Dict[str, Any]]:
    """Main entry point for RSS news scraping."""
    print("📰 Starting RSS news feed scraper...")

    all_posts = []
    feed_counts = {}

    for feed_config in RSS_FEEDS:
        feed_name = feed_config["name"]
        print(f"  📡 {feed_name}...")

        posts = fetch_rss_feed(feed_config, max_items=max_items_per_feed)

        if posts:
            print(f"  📥 {feed_name}: {len(posts)} articles")
            all_posts.extend(posts)
            feed_counts[feed_name] = len(posts)
        else:
            print(f"  ⚠️ {feed_name}: No articles found")
            feed_counts[feed_name] = 0

        time.sleep(1)  # Rate limiting between feeds

    if not all_posts:
        print("\n❌ No articles scraped from RSS feeds.")
        return []

    # Deduplicate by URL
    seen_urls = set()
    unique_posts = []
    for post in all_posts:
        url = post.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique_posts.append(post)

    # Sort by date (newest first)
    unique_posts.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Scraped {len(unique_posts)} unique articles → {SAVE_PATH}")

    # Print feed breakdown
    print("\n📊 Articles by feed:")
    for feed, count in sorted(feed_counts.items(), key=lambda x: -x[1]):
        print(f"  {feed}: {count}")

    # Date range
    if unique_posts:
        dates = [p.get("post_date", "") for p in unique_posts if p.get("post_date")]
        if dates:
            print(f"\n📅 Date range: {min(dates)} to {max(dates)}")

    return unique_posts


if __name__ == "__main__":
    run_news_rss_scraper()
