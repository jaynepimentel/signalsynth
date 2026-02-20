# scrape_podcasts.py — Podcast RSS scraper for collectibles industry podcasts
import requests
import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any
from xml.etree import ElementTree as ET
from html import unescape

SAVE_PATH = "data/scraped_podcast_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Podcast RSS feeds — collectibles industry voices
# All URLs verified via iTunes Search API + direct HTTP check
PODCAST_FEEDS = [
    {
        "name": "Sports Cards Nonsense",
        "url": "https://feeds.megaphone.fm/sports-cards-nonsense",
        "focus": "Sports cards market analysis, hobby news, industry interviews (The Ringer)",
    },
    {
        "name": "Sports Card Investor",
        "url": "https://feeds.captivate.fm/sports-card-investor/",
        "focus": "Card investing strategy, market analysis, buying/selling advice",
    },
    {
        "name": "Stacking Slabs",
        "url": "https://feeds.transistor.fm/stacking-slabs",
        "focus": "Graded cards, PSA/BGS/SGC, slab investing, pop reports",
    },
    {
        "name": "Hobby News Daily",
        "url": "https://anchor.fm/s/db5bb554/podcast/rss",
        "focus": "Daily hobby news, product releases, market trends",
    },
    {
        "name": "The Pull-Tab Podcast",
        "url": "https://anchor.fm/s/1e7e9b04/podcast/rss",
        "focus": "Sports cards investing, market analysis, box breaks",
    },
    {
        "name": "Collector Nation",
        "url": "https://rss2.flightcast.com/s0b568vp78icj45z9f87fhg4.xml",
        "focus": "Trading cards & collectibles, hobby culture, industry interviews",
    },
]

# XML namespaces commonly used in podcast RSS
NAMESPACES = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(date_str: str) -> str:
    """Parse RSS date formats into YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        pass
    # Try ISO format
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-%d")


def scrape_podcast_feed(feed: Dict[str, str], max_episodes: int = 20) -> List[Dict[str, Any]]:
    """Scrape episodes from a single podcast RSS feed."""
    name = feed["name"]
    url = feed["url"]
    focus = feed.get("focus", "")
    posts = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"    [WARN] {name}: HTTP {r.status_code}")
            return posts

        root = ET.fromstring(r.content)

        # Get channel-level info
        channel = root.find("channel") or root
        show_title = (channel.findtext("title") or name).strip()

        # Parse episodes
        items = channel.findall("item") or root.findall(".//item")
        for item in items[:max_episodes]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue

            # Episode description
            description = ""
            # Try content:encoded first (usually has full show notes)
            content_encoded = item.find("content:encoded", NAMESPACES)
            if content_encoded is not None and content_encoded.text:
                description = _strip_html(content_encoded.text)
            if not description:
                description = _strip_html(item.findtext("description") or "")

            # iTunes summary as fallback
            if not description:
                itunes_summary = item.find("itunes:summary", NAMESPACES)
                if itunes_summary is not None and itunes_summary.text:
                    description = _strip_html(itunes_summary.text)

            # Episode link
            link = (item.findtext("link") or "").strip()
            # Try enclosure URL (actual audio file — useful for reference)
            enclosure = item.find("enclosure")
            audio_url = ""
            if enclosure is not None:
                audio_url = enclosure.get("url", "")

            # Date
            pub_date = item.findtext("pubDate") or ""
            post_date = _parse_date(pub_date)

            # Duration
            duration = ""
            itunes_duration = item.find("itunes:duration", NAMESPACES)
            if itunes_duration is not None and itunes_duration.text:
                duration = itunes_duration.text.strip()

            # Build text: title + description (truncated)
            text = title
            if description:
                desc_trimmed = description[:2000]
                text = f"{title}\n\n{desc_trimmed}"

            if len(text) < 20:
                continue

            posts.append({
                "text": text,
                "title": f"🎙️ {show_title}: {title}",
                "source": "Podcast",
                "podcast_name": show_title,
                "url": link or audio_url,
                "audio_url": audio_url,
                "username": show_title,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": "",
                "score": 0,
                "duration": duration,
                "post_id": f"podcast_{hash(f'{name}_{title}') % 10**8}",
            })

    except ET.ParseError as e:
        print(f"    [WARN] {name}: XML parse error — {e}")
    except Exception as e:
        print(f"    [WARN] {name}: {e}")

    return posts


def run_podcast_scraper() -> List[Dict[str, Any]]:
    """Main entry point for podcast scraping."""
    print("🎙️ Starting Podcast scraper...")

    all_posts = []

    for feed in PODCAST_FEEDS:
        print(f"  📻 {feed['name']}...")
        posts = scrape_podcast_feed(feed)
        if posts:
            print(f"    {len(posts)} episodes")
            all_posts.extend(posts)
        else:
            print(f"    No episodes found (feed may be unavailable)")
        time.sleep(1.0)

    # Deduplicate by title
    seen_titles = set()
    unique = []
    for p in all_posts:
        title_key = p.get("title", "").lower().strip()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        unique.append(p)

    # Sort by date
    unique.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    # Summary
    from collections import Counter
    show_counts = Counter(p.get("podcast_name", "?") for p in unique)
    print(f"\n  ✅ Total: {len(unique)} podcast episodes")
    for show, cnt in show_counts.most_common():
        print(f"    {show}: {cnt}")
    print(f"  Saved to: {SAVE_PATH}")

    return unique


if __name__ == "__main__":
    run_podcast_scraper()
