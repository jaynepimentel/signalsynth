# scrape_competitors.py — Scrape competitor and eBay subsidiary discussions from Reddit/social
"""
Scrapes social discussions about:
- Competitors: Fanatics Collect, Fanatics Live, Heritage Auctions, Alt, Whatnot
- eBay Subsidiaries: Goldin, TCGPlayer (TCGP)
"""

import json
import os
import time
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
            "fanatics vs ebay cards", "selling on fanatics collect"
        ],
        "subreddits": ["baseballcards", "sportscards", "footballcards", "basketballcards"],
        "required_keywords": ["fanatics"],
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
            "heritage auctions coins", "ha.com auction"
        ],
        "subreddits": ["coins", "comicbookcollecting", "sportscards"],
        "required_keywords": ["heritage", "auction", "card", "coin", "comic", "collectible"],
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
            "whatnot app cards", "whatnot live shopping cards"
        ],
        "subreddits": ["sportscards", "baseballcards", "pokemontcg", "basketballcards", "footballcards"],
        "required_keywords": ["whatnot"],
    },
    "Goldin": {
        "type": "ebay_subsidiary",
        "search_terms": [
            "goldin auctions experience", "goldin auctions fees",
            "goldin vs ebay", "selling on goldin",
            "goldin buyer premium", "goldin consignment",
            "goldin auction complaint", "goldin auction review",
        ],
        "subreddits": ["sportscards", "baseballcards", "basketballcards", "footballcards", "pokemontcg"],
        "required_keywords": ["goldin"],
    },
    "TCGPlayer": {
        "type": "ebay_subsidiary",
        "search_terms": [
            "tcgplayer marketplace", "tcgplayer selling",
            "tcgplayer pokemon cards", "tcgplayer magic cards",
            "tcgplayer yugioh", "tcgplayer prices", "tcgplayer vs ebay"
        ],
        "subreddits": ["pokemontcg", "mtgfinance", "yugioh", "magicTCG"],
        "required_keywords": ["tcgplayer", "tcg player", "card", "pokemon", "magic", "yugioh", "marketplace", "price"],
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
        for term in comp_config["search_terms"][:5]:  # Limit to top 5 terms
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
                if p["post_id"] not in seen_ids:
                    seen_ids.add(p["post_id"])
                    comp_posts.append(p)
                    added += 1
            print(f"     └─ {added} relevant posts (of {len(posts)} found)")
            time.sleep(1.5)  # Rate limiting
        
        # Search in specific subreddits
        for subreddit in comp_config["subreddits"][:3]:  # Limit to top 3 subreddits
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
                if p["post_id"] not in seen_ids:
                    seen_ids.add(p["post_id"])
                    comp_posts.append(p)
                    added += 1
            print(f"     └─ {added} relevant posts")
            time.sleep(1.5)
        
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
