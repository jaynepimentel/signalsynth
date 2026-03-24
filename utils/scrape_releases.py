# scrape_releases.py — Scrape upcoming trading card product releases and checklists
# Sources: Google News RSS for Cardboard Connection, Beckett, and general release calendars

import requests
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

SAVE_PATH = "data/upcoming_releases.json"

MANUAL_CHECKLIST_URLS = [
    "https://www.checklistcenter.com/young-guns-card-checklist/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _google_news_rss(query, max_results=50):
    """Fetch from Google News RSS."""
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

            posts.append({
                "title": title,
                "text": text,
                "url": link,
                "post_date": post_date,
                "source": query.split("site:")[-1].split()[0] if "site:" in query else "Google News",
            })
    except Exception as e:
        print(f"  [WARN] RSS failed for '{query}': {e}")
    return posts


def _classify_release(title, text):
    """Classify a post as release, checklist, or other."""
    combined = (title + " " + text).lower()

    # Checklist indicators
    checklist_kw = ["checklist", "check list", "card list", "set details",
                    "base set", "insert set", "autograph checklist",
                    "parallel", "variation", "short print", "sp list"]
    if any(kw in combined for kw in checklist_kw):
        return "checklist"

    # Release date / upcoming product indicators
    release_kw = ["release date", "releases", "releasing", "coming soon",
                  "launch date", "available now", "pre-order", "preorder",
                  "hobby box", "retail box", "blaster", "mega box",
                  "first look", "preview", "product info", "product details",
                  "set to release", "hits shelves", "drops on", "arrives"]
    if any(kw in combined for kw in release_kw):
        return "release"

    # Product name patterns (2025/2026 Topps, Panini, etc.)
    if re.search(r"202[5-7]\s+(topps|panini|bowman|upper deck|leaf|sage)", combined):
        return "release"

    return "other"


def _extract_brand(title):
    """Extract the card brand/manufacturer from the title."""
    title_lower = title.lower()
    brands = {
        "Topps": ["topps", "bowman"],
        "Panini": ["panini", "prizm", "donruss", "select", "mosaic", "optic", "contenders", "national treasures", "flawless"],
        "Upper Deck": ["upper deck"],
        "Leaf": ["leaf"],
        "Sage": ["sage"],
    }
    for brand, keywords in brands.items():
        if any(kw in title_lower for kw in keywords):
            return brand
    return "Other"


def _extract_sport(title):
    """Extract sport/category from the title."""
    title_lower = title.lower()
    sports = {
        "Baseball": ["baseball", "bowman", "topps series", "topps chrome", "topps heritage"],
        "Football": ["football", "nfl", "draft picks"],
        "Basketball": ["basketball", "nba"],
        "Soccer": ["soccer", "premier league", "champions league", "match attax"],
        "Hockey": ["hockey", "nhl"],
        "Pokemon": ["pokemon", "pokémon"],
        "Magic: The Gathering": ["magic the gathering", "mtg", "magic:"],
        "Yu-Gi-Oh": ["yu-gi-oh", "yugioh"],
        "UFC/MMA": ["ufc", "mma"],
        "Wrestling": ["wwe", "wrestling", "aew"],
        "F1": ["formula 1", "f1 "],
        "Multi-Sport": ["multi-sport"],
    }
    for sport, keywords in sports.items():
        if any(kw in title_lower for kw in keywords):
            return sport
    return "Trading Cards"


def _scrape_direct_checklist(url):
    """Fetch direct checklist URLs (e.g., ChecklistCenter) and normalize into post shape."""
    fallback_title = url.rstrip("/").split("/")[-1].replace("-", " ").title() or "Checklist"
    title = fallback_title

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            title_el = soup.find("h1") or soup.find("title")
            if title_el and title_el.get_text(strip=True):
                title = title_el.get_text(" ", strip=True)
    except Exception:
        pass

    title = re.sub(r"\s*\|\s*ChecklistCenter\s*$", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"\s+", " ", title).strip()

    return {
        "title": title,
        "text": title,
        "url": url,
        "post_date": datetime.now().strftime("%Y-%m-%d"),
        "source": "checklistcenter.com",
        "category": "checklist",
        "brand": _extract_brand(title),
        "sport": _extract_sport(title),
    }


def scrape_upcoming_releases():
    """Scrape upcoming trading card releases and checklists."""
    print("📦 Scraping upcoming trading card releases and checklists...")

    all_posts = []

    # Cardboard Connection — best source for checklists and release info
    queries = [
        "site:cardboardconnection.com checklist 2025",
        "site:cardboardconnection.com checklist 2026",
        "site:cardboardconnection.com release date 2025",
        "site:cardboardconnection.com release date 2026",
        "site:cardboardconnection.com preview",
        # Beckett — release calendars
        "site:beckett.com release date trading cards 2025",
        "site:beckett.com release date trading cards 2026",
        "site:beckett.com release calendar",
        # General release news
        "trading cards release date 2025 2026 topps panini",
        "new trading card product release 2025",
        "upcoming sports card releases 2025 2026",
        "pokemon tcg new set release 2025 2026",
        # Checklists
        "trading card checklist 2025 topps",
        "trading card checklist 2025 panini",
    ]

    for query in queries:
        print(f"  Searching: {query}")
        posts = _google_news_rss(query)
        all_posts.extend(posts)
        time.sleep(1.0)

    # Direct checklist pages we always want represented
    for url in MANUAL_CHECKLIST_URLS:
        print(f"  Seeding direct checklist: {url}")
        all_posts.append(_scrape_direct_checklist(url))

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for p in all_posts:
        url = p.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Classify and enrich
        title = p.get("title", "")
        text = p.get("text", "")
        category = _classify_release(title, text)

        # Only keep release and checklist posts
        if category == "other":
            continue

        p["category"] = category
        p["brand"] = _extract_brand(title)
        p["sport"] = _extract_sport(title)
        unique.append(p)

    # Sort: checklists first, then by date
    unique.sort(key=lambda x: (0 if x["category"] == "checklist" else 1, x.get("post_date", "")), reverse=False)
    unique.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    # Summary
    releases = [p for p in unique if p["category"] == "release"]
    checklists = [p for p in unique if p["category"] == "checklist"]
    print(f"\n  ✅ Total: {len(unique)} posts ({len(releases)} releases, {len(checklists)} checklists)")
    print(f"  Saved to: {SAVE_PATH}")

    return unique


if __name__ == "__main__":
    scrape_upcoming_releases()
