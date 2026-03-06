# scrape_new_sources.py — New sources: Trustpilot, Goldin Blog, Heritage Blog,
# Card Ladder, PSA Forums, App Reviews, and expanded Twitter/Reddit coverage
"""
Fills coverage gaps identified in the scraping audit:
- Trustpilot reviews: Direct customer feedback for eBay, Goldin, TCGPlayer, Whatnot, Heritage
- Goldin.com blog: Subsidiary intel (eBay-owned)
- Heritage Auctions blog: Competitor intel
- Card Ladder blog: eBay's price guide partner
- PSA Collectors Universe forums: Grading community
- App Store reviews: eBay & TCGPlayer product feedback via Google News
"""

import requests
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Any

SAVE_PATH = "data/scraped_new_sources_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── Google News RSS helper ──────────────────────────────────────

def _google_news_rss(query, source_label, max_results=100):
    """Fetch indexed content from Google News RSS for a given query."""
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


# ─── HTML scraping helper ────────────────────────────────────────

def _scrape_html_articles(base_url, source_label, link_pattern, max_articles=15):
    """Generic blog/article scraper. Finds article links matching a pattern, then scrapes each."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print(f"    [WARN] BeautifulSoup not available, falling back to Google News for {source_label}")
        return []

    posts = []
    try:
        r = requests.get(base_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"    [WARN] {source_label} returned {r.status_code}")
            return posts

        soup = BeautifulSoup(r.text, "html.parser")

        # Find article links matching the pattern
        article_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(link_pattern, href) and href not in [al[1] for al in article_links]:
                full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}{href}"
                title = a.get_text(strip=True) or ""
                if len(title) > 5:
                    article_links.append((title, full_url))

        print(f"    Found {len(article_links)} articles")

        for title, url in article_links[:max_articles]:
            try:
                ar = requests.get(url, headers=HEADERS, timeout=10)
                if ar.status_code != 200:
                    continue

                asoup = BeautifulSoup(ar.text, "html.parser")

                # Extract article body
                article_body = (
                    asoup.find("article")
                    or asoup.find("main")
                    or asoup.find("div", class_=re.compile(r"content|article|post|body|entry", re.I))
                )
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
                        post_date = datetime.fromisoformat(
                            time_el["datetime"].replace("Z", "+00:00")
                        ).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                posts.append({
                    "text": text[:3000],
                    "title": title,
                    "source": source_label,
                    "url": url,
                    "username": "",
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "search_term": "",
                    "score": 0,
                    "post_id": f"{source_label.lower().replace(' ', '_')}_{hash(url) % 10**8}",
                })

                time.sleep(0.5)
            except Exception:
                continue

    except Exception as e:
        print(f"    [WARN] {source_label} direct scrape failed: {e}")

    return posts


# ═══════════════════════════════════════════════════════════════════
# 1. TRUSTPILOT REVIEWS — Pure customer feedback
# ═══════════════════════════════════════════════════════════════════

TRUSTPILOT_TARGETS = [
    {"company": "ebay.com", "source": "Trustpilot:eBay"},
    {"company": "goldin.com", "source": "Trustpilot:Goldin"},
    {"company": "tcgplayer.com", "source": "Trustpilot:TCGPlayer"},
    {"company": "whatnot.com", "source": "Trustpilot:Whatnot"},
    {"company": "ha.com", "source": "Trustpilot:Heritage"},
    {"company": "vinted.com", "source": "Trustpilot:Vinted"},
]


def scrape_trustpilot():
    """Scrape Trustpilot reviews via Google News RSS (direct scraping blocked)."""
    print("  📝 Trustpilot Reviews...")
    all_posts = []

    for target in TRUSTPILOT_TARGETS:
        company = target["company"]
        source = target["source"]
        print(f"    {source}...")

        # Google News picks up Trustpilot pages
        posts = _google_news_rss(
            f"site:trustpilot.com {company}",
            source
        )

        # Also search for review discussions about these platforms
        review_posts = _google_news_rss(
            f"{company.split('.')[0]} review customer experience collectibles",
            source
        )
        posts.extend(review_posts)

        print(f"      {len(posts)} posts")
        all_posts.extend(posts)
        time.sleep(1.0)

    print(f"    Total Trustpilot: {len(all_posts)} posts")
    return all_posts


# ═══════════════════════════════════════════════════════════════════
# 2. GOLDIN BLOG — Subsidiary intel (eBay-owned)
# ═══════════════════════════════════════════════════════════════════

def scrape_goldin_blog():
    """Scrape Goldin.com blog for subsidiary intel."""
    print("  🏪 Goldin Blog...")
    posts = []

    # Try direct scrape
    direct = _scrape_html_articles(
        "https://goldin.co/blog",
        "Goldin Blog",
        r"/blog/",
        max_articles=20
    )
    posts.extend(direct)

    # Supplement with Google News
    gn_posts = _google_news_rss("site:goldin.co blog", "Goldin Blog")
    posts.extend(gn_posts)

    # Also get Goldin auction highlights and news
    gn_auctions = _google_news_rss("goldin auctions results record sale", "Goldin Blog")
    posts.extend(gn_auctions)

    # Ken Goldin interviews and appearances
    gn_ken = _google_news_rss('"ken goldin" interview collectibles', "Goldin Blog")
    posts.extend(gn_ken)

    print(f"    Total Goldin Blog: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# 3. HERITAGE AUCTIONS BLOG — Competitor intel
# ═══════════════════════════════════════════════════════════════════

def scrape_heritage_blog():
    """Scrape Heritage Auctions blog and news for competitor intel."""
    print("  🏢 Heritage Auctions Blog...")
    posts = []

    # Try direct scrape
    direct = _scrape_html_articles(
        "https://www.ha.com/heritage-auctions-press-releases-and-news.s",
        "Heritage Blog",
        r"(press-release|news|blog|article)",
        max_articles=15
    )
    posts.extend(direct)

    # Google News for Heritage Auctions coverage
    gn_posts = _google_news_rss("site:ha.com", "Heritage Blog")
    posts.extend(gn_posts)

    # Heritage auction results and record sales
    gn_results = _google_news_rss(
        "heritage auctions record sale collectibles cards coins comics",
        "Heritage Blog"
    )
    posts.extend(gn_results)

    # Heritage buyer premium and fees discussion
    gn_fees = _google_news_rss(
        "heritage auctions buyer premium fees consignment review",
        "Heritage Blog"
    )
    posts.extend(gn_fees)

    print(f"    Total Heritage Blog: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# 4. CARD LADDER — eBay's price guide partner
# ═══════════════════════════════════════════════════════════════════

def scrape_card_ladder():
    """Scrape Card Ladder blog — eBay's price guide integration partner."""
    print("  📊 Card Ladder...")
    posts = []

    # Direct scrape attempt
    direct = _scrape_html_articles(
        "https://www.cardladder.com/blog",
        "Card Ladder",
        r"/blog/",
        max_articles=15
    )
    posts.extend(direct)

    # Google News
    gn_posts = _google_news_rss("site:cardladder.com", "Card Ladder")
    posts.extend(gn_posts)

    # Card Ladder + eBay integration discussions
    gn_ebay = _google_news_rss(
        "card ladder ebay price guide integration",
        "Card Ladder"
    )
    posts.extend(gn_ebay)

    print(f"    Total Card Ladder: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# 5. PSA COLLECTORS UNIVERSE FORUMS — Grading community
# ═══════════════════════════════════════════════════════════════════

def scrape_psa_forums():
    """Scrape PSA Collectors Universe forums via Google News (direct blocked)."""
    print("  🔐 PSA Collectors Universe Forums...")
    posts = []

    # Google News for PSA forum discussions
    queries = [
        "site:collectors.com forum",
        "site:collectors.com psa",
        "psa collectors universe forum grading",
        "psa collectors universe forum vault",
        "psa collectors universe forum ebay",
    ]

    for query in queries:
        gn_posts = _google_news_rss(query, "PSA Forums")
        posts.extend(gn_posts)
        time.sleep(0.5)

    print(f"    Total PSA Forums: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# 6. APP STORE REVIEWS — Product feedback
# ═══════════════════════════════════════════════════════════════════

def scrape_app_reviews():
    """Scrape app review discussions via Google News — eBay, TCGPlayer app feedback."""
    print("  📱 App Store Reviews...")
    posts = []

    queries = [
        # eBay app reviews
        "ebay app review 2025 collectibles",
        "ebay app crash bug issue",
        "ebay seller hub app problems",
        "ebay app update feedback",
        # TCGPlayer app reviews
        "tcgplayer app review",
        "tcgplayer app scanner",
        "tcgplayer app problems issues",
        # Whatnot app
        "whatnot app review live shopping",
        # General marketplace app comparisons
        "best app selling trading cards 2025",
        "best card scanning app",
    ]

    for query in queries:
        gn_posts = _google_news_rss(query, "App Reviews")
        posts.extend(gn_posts)
        time.sleep(0.5)

    print(f"    Total App Reviews: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# 7. INDUSTRY ANALYSIS & MARKET REPORTS — Strategic intel
# ═══════════════════════════════════════════════════════════════════

def scrape_industry_analysis():
    """Scrape industry analysis, market reports, and trade publication coverage."""
    print("  📈 Industry Analysis & Market Reports...")
    posts = []

    queries = [
        # Market analysis
        "sports card market 2025 analysis trends",
        "trading card market growth collectibles industry",
        "collectibles market report auction results 2025",
        # Platform comparisons
        "ebay vs whatnot vs goldin marketplace comparison",
        "best platform sell graded cards 2025",
        "where to sell sports cards online 2025",
        # Industry events
        "the national sports collectors convention 2025",
        "card show convention 2025 collectibles",
        # Licensing and business moves
        "fanatics topps panini license trading cards",
        "exclusive card license sports 2025",
        # Grading industry
        "psa bgs sgc cgc grading turnaround comparison 2025",
        "card grading backlog wait times 2025",
        # Authentication & trust
        "counterfeit cards collectibles detection 2025",
        "card authentication technology 2025",
    ]

    for query in queries:
        gn_posts = _google_news_rss(query, "Industry Analysis")
        posts.extend(gn_posts)
        time.sleep(0.5)

    print(f"    Total Industry Analysis: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# 8. MARKETPLACE SELLER COMMUNITIES — Seller experience feedback
# ═══════════════════════════════════════════════════════════════════

def scrape_seller_communities():
    """Scrape seller community discussions from sources we're not covering yet."""
    print("  🛒 Seller Community Discussions...")
    posts = []

    queries = [
        # eBay seller experience
        "site:community.ebay.com seller",
        "site:community.ebay.com authentication",
        "site:community.ebay.com vault",
        "site:community.ebay.com shipping",
        # TCGPlayer seller forums
        "site:seller.tcgplayer.com",
        "tcgplayer seller forum experience",
        # General seller communities
        "ebay seller community 2025 frustration",
        "ebay seller fees increase 2025",
        "ebay promoted listings cost worth it",
    ]

    for query in queries:
        gn_posts = _google_news_rss(query, "Seller Community")
        posts.extend(gn_posts)
        time.sleep(0.5)

    print(f"    Total Seller Community: {len(posts)} posts")
    return posts


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_new_sources_scraper():
    """Run all new source scrapers."""
    print("=" * 60)
    print("🆕 NEW SOURCES SCRAPER")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_posts = []

    scrapers = [
        ("Trustpilot Reviews", scrape_trustpilot),
        ("Goldin Blog", scrape_goldin_blog),
        ("Heritage Blog", scrape_heritage_blog),
        ("Card Ladder", scrape_card_ladder),
        ("PSA Forums", scrape_psa_forums),
        ("App Reviews", scrape_app_reviews),
        ("Industry Analysis", scrape_industry_analysis),
        ("Seller Communities", scrape_seller_communities),
    ]

    for name, scraper_fn in scrapers:
        print(f"\n{'─' * 40}")
        try:
            posts = scraper_fn()
            all_posts.extend(posts)
            print(f"  ✅ {name}: {len(posts)} posts")
        except Exception as e:
            print(f"  ❌ {name} failed: {e}")
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
    print(f"\n{'=' * 60}")
    print(f"📊 NEW SOURCES SUMMARY")
    print(f"{'=' * 60}")
    print(f"\n📦 Total unique posts: {len(unique)}")
    for src, cnt in source_counts.most_common():
        print(f"  {src}: {cnt}")
    print(f"💾 Saved to: {SAVE_PATH}")

    return unique


if __name__ == "__main__":
    run_new_sources_scraper()
