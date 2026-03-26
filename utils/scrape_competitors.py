# scrape_competitors.py — Scrape competitor and eBay subsidiary discussions from Reddit/social
"""
Scrapes social discussions about:
- Competitors: Fanatics Collect, Fanatics Live, Heritage Auctions, Alt, Whatnot
- eBay Subsidiaries: Goldin, TCGPlayer (TCGP)
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from typing import List, Dict, Any

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

OUTPUT_PATH = "data/scraped_competitor_posts.json"

# Collectibles context keywords - posts must contain at least one of these
COLLECTIBLES_CONTEXT = [
    "card", "cards", "trading card", "sports card", "pokemon", "magic", "yugioh",
    "collectible", "collectibles", "graded", "psa", "bgs", "cgc",
    "slab", "raw card", "mint condition", "gem mint", "vintage card", "rookie", "autograph",
    "collection", "collector", "hobby", "wax", "box break", "case break", "card break",
    "ebay", "card show", "card shop", "lcs ", "memorabilia", "sports memorabilia",
    "topps", "panini", "upper deck", "bowman", "prizm", "select", "optic",
]

# Exclude posts that match these patterns (clearly not collectibles)
EXCLUDE_PATTERNS = [
    "stabbed", "murder", "killed", "death", "died", "shooting", "shot ",
    "arrested", "charged with", "sentenced", "prison", "jail",
    "facebook marketplace", "craigslist", "offerup",
    "car ", "truck", "vehicle", "motorcycle", "boat",
    "real estate", "house", "apartment", "rent ",
    "crypto", "bitcoin", "nft ", "stock market",
    "recipe", "cooking", "restaurant",
    "pixel", "google pixel", "iphone", "android", "samsung", "smartphone",
    "laptop", "computer", "gpu", "cpu", "ram ",
    "election", "democrat", "republican", "trump", "biden", "congress",
    "extremist", "terrorism", "terrorist",
    # Fanatical (game bundle site, NOT Fanatics Collect)
    "[fanatical]", "build your own", "platinum collection",
    "resident evil", "devil may cry", "steamworld", "frostpunk",
    "tomb raider", "skyrim", "lego bricktales", "ace attorney",
    # Trade/sale posts (not platform feedback)
    "[us,ww]", "[us,us]", "[us,fl]", "[us,ny]", "[us,co]", "[us,tx]",
    "[us-ny]", "[us-co]", "[us-tx]", "[us-fl]",
    "binder for sale", "85% tcg", "90% tcg", "75% tcg",
    "lowest verified", "market price",
]

# Competitor/subsidiary definitions
COMPETITORS = {
    "Fanatics Collect": {
        "type": "competitor",
        "search_terms": [
            "fanatics collect cards", "fanatics collectibles marketplace",
            "fanatics trading cards", "fanatics cards marketplace",
            "fanatics vs ebay cards", "selling on fanatics collect",
            "fanatics policy change", "fanatics collect update",
        ],
        "subreddits": ["baseballcards", "sportscards", "footballcards", "basketballcards"],
        "required_keywords": ["fanatics"],
        "google_news_queries": [
            'fanatics collect marketplace news announcement',
            'fanatics collectibles policy update',
        ],
    },
    "Fanatics Live": {
        "type": "competitor",
        "search_terms": [
            "fanatics live breaks cards", "fanatics live card breaks",
            "fanatics live sports cards", "fanatics live box break"
        ],
        "subreddits": ["baseballcards", "sportscards", "footballcards"],
        "required_keywords": ["fanatics live"],
    },
    "Heritage Auctions": {
        "type": "competitor",
        "search_terms": [
            "heritage auctions cards", "heritage auction sports",
            "heritage auctions collectibles", "heritage auctions comics",
            "heritage auctions coins", "ha.com auction",
            "heritage auctions experience", "heritage auctions fees",
            "heritage auctions buyer premium", "heritage auctions review",
            "heritage auctions vs ebay", "heritage auctions complaint",
            "selling through heritage auctions", "heritage auctions consignment",
            "heritage auctions policy", "heritage auctions terms",
        ],
        "subreddits": ["coins", "comicbookcollecting", "sportscards", "baseballcards", "basketballcards", "footballcards", "hockeycards", "PSAcard", "vintagecards"],
        "required_keywords": ["heritage", "auction", "card", "coin", "comic", "collectible", "ha.com"],
        "google_news_queries": [
            'heritage auctions policy change news',
            'heritage auctions update announcement collectibles',
        ],
    },
    "Alt": {
        "type": "competitor",
        "search_terms": [
            "alt.xyz cards", "alt marketplace sports cards",
            "alt vault cards", "alt.xyz vault", "alt collectibles app"
        ],
        "subreddits": ["sportscards", "baseballcards"],
        "required_keywords": ["alt.xyz", "alt marketplace", "alt vault", "alt app"],
    },
    "Whatnot": {
        "type": "competitor",
        "search_terms": [
            "whatnot live breaks", "whatnot card breaks",
            "whatnot sports cards", "whatnot pokemon cards",
            "whatnot vs ebay", "selling on whatnot",
            "whatnot app cards", "whatnot live shopping cards",
            "whatnot policy change", "whatnot terms of service",
            "whatnot mystery repack", "whatnot banned repack",
            "whatnot unpaid items", "whatnot collections policy",
            "whatnot trust safety", "whatnot seller rules",
            "whatnot prohibited items", "whatnot enforcement",
            # Seller switching (user interest)
            "switching to whatnot from ebay", "whatnot better than ebay",
            "why sellers leaving ebay whatnot",
            # Whatnot customer support
            "whatnot customer support", "whatnot dispute resolution",
        ],
        "subreddits": ["sportscards", "baseballcards", "pokemontcg", "basketballcards", "footballcards"],
        "required_keywords": ["whatnot"],
        "google_news_queries": [
            'whatnot policy change mystery repack',
            'whatnot terms of service update collectibles',
            'whatnot unpaid collections policy',
            'whatnot trust safety enforcement sellers',
            'whatnot prohibited items banned cards',
            'whatnot marketplace update 2025 2026',
            'whatnot live shopping news announcement',
        ],
    },
    "Vinted": {
        "type": "competitor",
        "search_terms": [
            "vinted selling experience", "vinted vs ebay",
            "vinted fees sellers", "vinted collectibles",
            "vinted trading cards", "vinted sports cards",
            "vinted seller review", "vinted shipping issues",
            "vinted buyer protection", "selling on vinted cards",
            "vinted app review", "vinted scam",
        ],
        "subreddits": ["Flipping", "Ebay", "eBaySellerAdvice", "Mercari", "sportscards", "pokemontcg"],
        "required_keywords": ["vinted"],
    },
    "Goldin": {
        "type": "ebay_subsidiary",
        "search_terms": [
            "goldin auctions experience", "goldin auctions fees",
            "goldin vs ebay", "selling on goldin",
            "goldin buyer premium", "goldin consignment",
            "goldin auction complaint", "goldin auction review",
            "goldin netflix", "king of collectibles goldin",
            "goldin 100 auction", "ken goldin",
            "goldin marketplace cards", "goldin elite",
            # Instant liquidity (user interest)
            "goldin instant offer", "goldin instant sale",
            "goldin buy now", "goldin ebay integration",
        ],
        "subreddits": ["sportscards", "baseballcards", "basketballcards", "footballcards", "pokemontcg", "hockeycards", "PSAcard", "PokeInvesting"],
        "required_keywords": ["goldin"],
    },
    "TCGPlayer": {
        "type": "ebay_subsidiary",
        "search_terms": [
            "tcgplayer marketplace", "tcgplayer selling",
            "tcgplayer pokemon cards", "tcgplayer magic cards",
            "tcgplayer yugioh", "tcgplayer prices", "tcgplayer vs ebay",
            "tcgplayer fees", "tcgplayer seller experience",
            "tcgplayer scam", "tcgplayer review",
            "tcgplayer shipping", "tcgplayer complaint",
            "tcgplayer condition", "tcgplayer refund",
            # Trust & integration (user interest)
            "tcgplayer trust issues", "tcgplayer ebay integration",
            "tcgplayer refund abuse", "tcgplayer buyer scam",
            "tcgplayer customer support",
        ],
        "subreddits": ["pokemontcg", "mtgfinance", "yugioh", "magicTCG", "PokemonTCG", "DigimonCardGame2020", "Lorcana"],
        "required_keywords": ["tcgplayer", "tcg player", "card", "pokemon", "magic", "yugioh", "marketplace", "price"],
    },
    "Beckett": {
        "type": "competitor",
        "search_terms": [
            "beckett grading cards", "beckett grading review",
            "beckett acquisition", "beckett fanatics acquisition",
            "beckett vs psa grading", "beckett pricing tool",
            "beckett marketplace", "beckett ebay",
            "beckett raw card review", "BGS beckett grading",
        ],
        "subreddits": ["sportscards", "baseballcards", "basketballcards", "footballcards", "hockeycards", "pokemontcg", "PSAcard"],
        "required_keywords": ["beckett", "bgs"],
    },
    "PSA Consignment": {
        "type": "ebay_subsidiary",
        "search_terms": [
            "PSA consignment eBay", "PSA sell on eBay",
            "PSA vault sell", "PSA vault eBay store",
            "PSA consignment experience", "PSA consignment fees",
            "sell through PSA eBay", "PSA vault consignment",
        ],
        "subreddits": ["psagrading", "sportscards", "baseballcards", "basketballcards", "pokemontcg", "PokeInvesting"],
        "required_keywords": ["psa"],
    },
}


def search_reddit(query: str, limit: int = 50, time_filter: str = "year") -> List[Dict]:
    """Search Reddit for a query."""
    url = f"https://www.reddit.com/search.json"
    params = {
        "q": query,
        "limit": limit,
        "sort": "relevance",
        "t": time_filter,
        "raw_json": 1,
    }
    
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code == 429:
            print(f"    ⚠️ Rate limited, waiting...")
            time.sleep(10)
            return []
        if res.status_code != 200:
            return []
        
        data = res.json()
        posts = []
        
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            text = post.get("selftext", "") or post.get("title", "")
            if len(text) < 30:
                continue
            
            posts.append({
                "text": text,
                "title": post.get("title", ""),
                "source": "Reddit",
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "subreddit": post.get("subreddit", ""),
                "username": post.get("author", "unknown"),
                "post_date": datetime.fromtimestamp(post.get("created_utc", 0)).strftime("%Y-%m-%d"),
                "_logged_date": datetime.now().isoformat(),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "post_id": post.get("id", ""),
                "search_term": query,
            })
        
        return posts
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return []


def scrape_subreddit_for_competitor(subreddit: str, competitor: str, limit: int = 50) -> List[Dict]:
    """Search a specific subreddit for competitor mentions."""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": competitor,
        "limit": limit,
        "sort": "relevance",
        "t": "year",
        "restrict_sr": "on",
        "raw_json": 1,
    }
    
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code == 429:
            time.sleep(10)
            return []
        if res.status_code != 200:
            return []
        
        data = res.json()
        posts = []
        
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            text = post.get("selftext", "") or post.get("title", "")
            if len(text) < 30:
                continue
            
            posts.append({
                "text": text,
                "title": post.get("title", ""),
                "source": "Reddit",
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "subreddit": post.get("subreddit", ""),
                "username": post.get("author", "unknown"),
                "post_date": datetime.fromtimestamp(post.get("created_utc", 0)).strftime("%Y-%m-%d"),
                "_logged_date": datetime.now().isoformat(),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "post_id": post.get("id", ""),
                "competitor": competitor,
            })
        
        return posts
    except Exception:
        return []


def _google_news_competitor(query: str, comp_name: str, comp_type: str) -> List[Dict]:
    """Fetch competitor news from Google News RSS."""
    encoded_q = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
    posts = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return posts
        root = ET.fromstring(res.content)
        for item in root.findall(".//item")[:20]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            desc = item.findtext("description", "").strip()
            # Clean HTML from description
            desc_clean = re.sub(r"<[^>]+>", "", desc)[:500]
            # Parse date
            post_date = datetime.now().strftime("%Y-%m-%d")
            if pub_date:
                for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"]:
                    try:
                        post_date = datetime.strptime(pub_date.strip(), fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            posts.append({
                "title": title,
                "text": f"{title}\n\n{desc_clean}",
                "url": link,
                "source": comp_name,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "competitor": comp_name,
                "competitor_type": comp_type,
                "post_id": f"gn_{comp_name}_{hash(link) % 10**8}",
                "score": 0,
            })
    except Exception as e:
        print(f"    ❌ Google News error: {e}")
    return posts


def run_competitor_scraper() -> List[Dict[str, Any]]:
    """Run the competitor scraper for all defined competitors and subsidiaries."""
    
    print("=" * 60)
    print("🏢 COMPETITOR & SUBSIDIARY SCRAPER")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_posts = []
    seen_ids = set()
    
    for comp_name, comp_config in COMPETITORS.items():
        comp_type = comp_config["type"]
        icon = "🏢" if comp_type == "competitor" else "🏪"
        
        print(f"\n{icon} {comp_name} ({comp_type})")
        print("-" * 40)
        
        comp_posts = []
        required_keywords = comp_config.get("required_keywords", [])
        
        # Search by terms
        for term in comp_config["search_terms"][:16]:  # Limit to top 16 terms
            print(f"  🔍 Searching: '{term}'...")
            posts = search_reddit(term, limit=30)
            added = 0
            for p in posts:
                text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
                
                # Must have collectibles context
                has_collectibles_context = any(kw in text_lower for kw in COLLECTIBLES_CONTEXT)
                if not has_collectibles_context:
                    continue
                
                # Exclude clearly irrelevant posts (crime, vehicles, etc.)
                if any(ep in text_lower for ep in EXCLUDE_PATTERNS):
                    continue
                
                # Filter by required keywords if specified
                if required_keywords:
                    if not any(kw.lower() in text_lower for kw in required_keywords):
                        continue  # Skip posts without required keywords
                
                p["competitor"] = comp_name
                p["competitor_type"] = comp_type
                p["source"] = comp_name  # Tag with competitor name for curated source recognition
                if p["post_id"] not in seen_ids:
                    seen_ids.add(p["post_id"])
                    comp_posts.append(p)
                    added += 1
            print(f"     └─ {added} relevant posts (of {len(posts)} found)")
            time.sleep(1.5)  # Rate limiting
        
        # Search in specific subreddits
        for subreddit in comp_config["subreddits"][:5]:  # Limit to top 5 subreddits
            print(f"  📂 r/{subreddit}...")
            posts = scrape_subreddit_for_competitor(subreddit, comp_name.split()[0], limit=20)
            added = 0
            for p in posts:
                text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
                
                # Must have collectibles context
                has_collectibles_context = any(kw in text_lower for kw in COLLECTIBLES_CONTEXT)
                if not has_collectibles_context:
                    continue
                
                # Exclude clearly irrelevant posts
                if any(ep in text_lower for ep in EXCLUDE_PATTERNS):
                    continue
                
                # Filter by required keywords if specified
                if required_keywords:
                    if not any(kw.lower() in text_lower for kw in required_keywords):
                        continue
                
                p["competitor"] = comp_name
                p["competitor_type"] = comp_type
                p["source"] = comp_name  # Tag with competitor name
                if p["post_id"] not in seen_ids:
                    seen_ids.add(p["post_id"])
                    comp_posts.append(p)
                    added += 1
            print(f"     └─ {added} relevant posts")
            time.sleep(1.5)
        
        # Google News for policy/product announcements
        gn_queries = comp_config.get("google_news_queries", [])
        for gn_q in gn_queries:
            print(f"  📰 Google News: '{gn_q}'...")
            gn_posts = _google_news_competitor(gn_q, comp_name, comp_type)
            added = 0
            for p in gn_posts:
                pid = p.get("post_id", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    comp_posts.append(p)
                    added += 1
            print(f"     └─ {added} articles")
            time.sleep(1)

        all_posts.extend(comp_posts)
        print(f"  ✅ Total for {comp_name}: {len(comp_posts)} posts")
    
    # Deduplicate by title + competitor (same post found via different search terms)
    seen_keys = set()
    deduped = []
    for p in all_posts:
        title = (p.get("title", "") or p.get("text", ""))[:80].strip().lower()
        comp = p.get("competitor", "")
        key = f"{comp}|{title}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(p)
    if len(all_posts) != len(deduped):
        print(f"  🧹 Deduped: {len(all_posts)} → {len(deduped)} ({len(all_posts) - len(deduped)} duplicates removed)")
    all_posts = deduped

    # Sort by date
    all_posts.sort(key=lambda x: x.get("post_date", ""), reverse=True)
    
    # Save to file
    os.makedirs(os.path.dirname(OUTPUT_PATH) if os.path.dirname(OUTPUT_PATH) else ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 COMPETITOR SCRAPING SUMMARY")
    print("=" * 60)
    
    # Count by competitor
    comp_counts = {}
    for p in all_posts:
        comp = p.get("competitor", "Unknown")
        comp_counts[comp] = comp_counts.get(comp, 0) + 1
    
    print("\n📊 Posts by competitor/subsidiary:")
    for comp, count in sorted(comp_counts.items(), key=lambda x: -x[1]):
        comp_type = COMPETITORS.get(comp, {}).get("type", "unknown")
        icon = "🏢" if comp_type == "competitor" else "🏪"
        print(f"  {icon} {comp}: {count}")
    
    print(f"\n📦 Total posts: {len(all_posts)}")
    print(f"💾 Saved to: {OUTPUT_PATH}")
    
    if all_posts:
        dates = [p.get("post_date", "") for p in all_posts if p.get("post_date")]
        if dates:
            print(f"📅 Date range: {min(dates)} to {max(dates)}")
    
    print("\n" + "=" * 60)
    print("✅ COMPETITOR SCRAPING COMPLETE")
    print("=" * 60)
    
    return all_posts


if __name__ == "__main__":
    run_competitor_scraper()
