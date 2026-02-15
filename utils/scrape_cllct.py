# scrape_cllct.py — Cllct.com news scraper for collectibles industry news
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Any

# Cllct.com category pages to scrape
CATEGORY_PAGES = [
    {"name": "Sports Cards", "url": "https://www.cllct.com/sports-collectibles/sports-cards"},
    {"name": "Auctions", "url": "https://www.cllct.com/sports-collectibles/auctions"},
    {"name": "Autographs", "url": "https://www.cllct.com/sports-collectibles/autographs"},
    {"name": "Ticket Stubs", "url": "https://www.cllct.com/sports-collectibles/ticket-stubs"},
    {"name": "Game Worn", "url": "https://www.cllct.com/sports-collectibles/game-worn-jersey"},
    {"name": "News / Memorabilia", "url": "https://www.cllct.com/sports-collectibles/memorabilia"},
]

SAVE_PATH = "data/scraped_cllct_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def scrape_category_page(category: Dict[str, str], max_pages: int = 3) -> List[Dict[str, Any]]:
    """Scrape article listings from a Cllct.com category page."""
    articles = []
    category_name = category["name"]
    base_url = category["url"]

    for page in range(1, max_pages + 1):
        url = f"{base_url}?page={page}" if page > 1 else base_url

        try:
            res = requests.get(url, headers=HEADERS, timeout=20)

            if res.status_code != 200:
                print(f"    ⚠️ Page {page}: HTTP {res.status_code}")
                break

            soup = BeautifulSoup(res.text, "html.parser")

            # Find article links — cllct uses <a> tags with article paths
            link_selectors = [
                "a[href*='/sports-collectibles/']",
                "article a",
                ".post-card a",
                ".article-card a",
                "h2 a",
                "h3 a",
            ]

            links = []
            for selector in link_selectors:
                links = soup.select(selector)
                if links:
                    break

            if not links:
                # Fallback: grab all internal links that look like articles
                links = soup.select("a[href]")
                links = [
                    a for a in links
                    if a.get("href", "").startswith("/sports-collectibles/")
                    and a.get("href", "").count("/") >= 3
                    and a.get_text(strip=True)
                ]

            seen_urls = set()
            for link in links:
                try:
                    href = link.get("href", "")
                    if not href:
                        continue

                    # Make URL absolute
                    if href.startswith("/"):
                        href = f"https://www.cllct.com{href}"
                    elif not href.startswith("http"):
                        continue

                    # Skip category index pages and non-article links
                    path = href.replace("https://www.cllct.com", "")
                    if path.count("/") < 3:
                        continue
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    title = link.get_text(strip=True)
                    if not title or len(title) < 15:
                        continue

                    # Skip navigation / generic links
                    skip_phrases = ["read more", "watch more", "see all", "view all", "subscribe"]
                    if any(phrase in title.lower() for phrase in skip_phrases):
                        continue

                    articles.append({
                        "title": title,
                        "url": href,
                        "category": category_name,
                    })

                except Exception:
                    continue

            if not links:
                break

            time.sleep(1)  # Rate limiting between pages

        except requests.exceptions.Timeout:
            print(f"    ⏱️ Page {page}: Timeout")
        except Exception as e:
            print(f"    ❌ Page {page}: {e}")

    return articles


def scrape_article(url: str, title: str, category: str) -> Dict[str, Any]:
    """Scrape the full text of a single Cllct.com article."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)

        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Extract article body text
        body_selectors = [
            "article",
            ".article-body",
            ".post-content",
            ".entry-content",
            "[class*='article']",
            "[class*='content']",
            "main",
        ]

        body_text = ""
        for selector in body_selectors:
            body = soup.select_one(selector)
            if body:
                # Remove script/style tags
                for tag in body.select("script, style, nav, footer, header"):
                    tag.decompose()
                body_text = body.get_text(separator="\n", strip=True)
                if len(body_text) > 100:
                    break

        if not body_text or len(body_text) < 50:
            body_text = title

        # Extract publish date
        post_date = datetime.now().strftime("%Y-%m-%d")
        date_selectors = [
            "time[datetime]",
            "meta[property='article:published_time']",
            "[class*='date']",
            "[class*='time']",
        ]

        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                datetime_attr = date_elem.get("datetime") or date_elem.get("content") or ""
                if datetime_attr:
                    try:
                        post_date = datetime_attr[:10]
                        break
                    except Exception:
                        pass
                date_text = date_elem.get_text(strip=True)
                if date_text:
                    # Try common date formats
                    for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"]:
                        try:
                            post_date = datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue

        # Extract author
        author = "cllct.com"
        author_selectors = [
            "[class*='author'] a",
            "[class*='author']",
            "meta[name='author']",
            "[rel='author']",
        ]
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = author_elem.get("content") or author_elem.get_text(strip=True)
                if author:
                    break

        # Extract meta description as summary
        summary = ""
        meta_desc = soup.select_one("meta[property='og:description']") or soup.select_one("meta[name='description']")
        if meta_desc:
            summary = meta_desc.get("content", "")

        # Combine title + summary + body for full text
        full_text = f"{title}\n\n{summary}\n\n{body_text}" if summary else f"{title}\n\n{body_text}"

        # Truncate very long articles to keep data manageable
        if len(full_text) > 3000:
            full_text = full_text[:3000] + "..."

        return {
            "text": full_text,
            "title": title,
            "source": "Cllct",
            "category": category,
            "username": author,
            "url": url,
            "post_date": post_date,
            "_logged_date": datetime.now().isoformat(),
            "summary": summary,
        }

    except Exception as e:
        return None


def run_cllct_scraper(max_articles_per_category: int = 15) -> List[Dict[str, Any]]:
    """Main entry point for Cllct.com scraping."""
    print("📰 Starting Cllct.com news scraper...")

    all_article_refs = []

    # Collect article links from each category
    for category in CATEGORY_PAGES:
        print(f"  📂 {category['name']}...")
        refs = scrape_category_page(category, max_pages=2)

        if refs:
            print(f"  📥 {category['name']}: {len(refs)} article links")
            all_article_refs.extend(refs)
        else:
            print(f"  ⚠️ {category['name']}: No articles found")

        time.sleep(1)

    if not all_article_refs:
        print("\n❌ No articles found on Cllct.com.")
        return []

    # Deduplicate by URL
    seen_urls = set()
    unique_refs = []
    for ref in all_article_refs:
        if ref["url"] not in seen_urls:
            seen_urls.add(ref["url"])
            unique_refs.append(ref)

    print(f"\n📄 Found {len(unique_refs)} unique articles, scraping content...")

    # Scrape each article (limit per category)
    category_counts = {}
    all_posts = []

    for ref in unique_refs:
        cat = ref["category"]
        category_counts.setdefault(cat, 0)

        if category_counts[cat] >= max_articles_per_category:
            continue

        article = scrape_article(ref["url"], ref["title"], ref["category"])
        if article:
            all_posts.append(article)
            category_counts[cat] += 1

        time.sleep(0.5)  # Rate limiting

    if not all_posts:
        print("\n❌ No article content scraped from Cllct.com.")
        return []

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Scraped {len(all_posts)} articles → {SAVE_PATH}")

    # Print category breakdown
    print("\n📊 Articles by category:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    return all_posts


if __name__ == "__main__":
    run_cllct_scraper()
