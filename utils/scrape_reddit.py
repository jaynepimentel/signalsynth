# scrape_reddit.py — Comprehensive Reddit scraper using public JSON API (no auth required)
import requests
import json
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Any

# Subreddits to scrape (collectibles/marketplace related)
SUBREDDITS = [
    # Trading Cards
    "tradingcardcommunity",
    "sportscards",
    "baseballcards",
    "basketballcards",
    "footballcards",
    "hockeycards",
    "pokemontcg",
    "pkmntcgcollections",
    "mtgfinance",
    "yugioh",
    # Grading & Authentication
    "PSAcard",
    "psagrading",
    "gradedcoins",
    # Collectibles
    "funkopop",
    "Funko",
    "Collectibles",
    "comicbookcollecting",
    "VinylCollectors",
    "Antiques",
    # Marketplaces
    "Ebay",
    "eBaySellerAdvice", 
    "Flipping",
    "Mercari",
    "poshmark",
    # Specific Collectibles
    "coins",
    "coincollecting",
    "Silverbugs",
    "Gold",
    "stamps",
    "HotWheels",
    "legomarket",
    "VintageApple",
    "Sneakers",
    "SneakerMarket",
    # Investing / Finance
    "PokeInvesting",
    "mtgfinance",
    # Additional TCG
    "magicTCG",
    "DigimonCardGame2020",
    "OnePieceTCG",
    "lorcana",
]

# Search queries for cross-subreddit search
SEARCH_QUERIES = [
    # Price Guide (eBay's new feature - HIGH PRIORITY)
    "ebay price guide",
    "ebay price guide cards",
    "ebay price guide pokemon",
    "ebay price guide sports cards",
    "ebay card pricing",
    "ebay market value",
    "ebay scan to price",
    "ebay suggested price",
    "ebay card value",
    "ebay collectible pricing",
    "what's my card worth ebay",
    "card value ebay",
    "pokemon card value ebay",
    "sports card value ebay",
    # Vault (eBay Vault AND PSA Vault - both relevant)
    "ebay vault",
    "ebay vault review",
    "ebay vault withdraw",
    "ebay vault shipping",
    "psa vault",
    "psa vault ebay",
    "psa vault auction",
    "psa vault sell",
    "psa vault trust",
    # Authentication
    "ebay authentication",
    "ebay authenticity guarantee",
    "ebay ag failed",
    # Grading turnaround
    "psa grading turnaround",
    "psa turnaround time",
    "bgs grading wait",
    "cgc grading time",
    # Payment issues
    "ebay payment failed",
    "ebay checkout problem",
    "ebay managed payments",
    "ebay funds held",
    "ebay payout delay",
    # General collectibles + eBay
    "selling cards ebay",
    "buying cards ebay",
    "graded card ebay",
    # Beckett (acquisition, grading, pricing — competitive intel)
    "beckett grading",
    "beckett acquisition",
    "beckett fanatics",
    "beckett ebay",
    "beckett pricing cards",
    "beckett vs psa",
    "beckett card grading review",
]

SAVE_PATH = "data/scraped_reddit_posts.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignalSynth/1.0"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def get_subreddit_posts(subreddit: str, sort: str = "hot", limit: int = 50, time_filter: str = "week") -> List[Dict[str, Any]]:
    """
    Fetch posts from a subreddit using Reddit's public JSON API.
    sort: hot, new, top, rising
    time_filter: hour, day, week, month, year, all (only for top)
    """
    posts = []
    
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
    params = {
        "limit": limit,
        "raw_json": 1,
    }
    if sort == "top":
        params["t"] = time_filter
    
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            children = data.get("data", {}).get("children", [])
            
            for child in children:
                post = child.get("data", {})
                
                # Combine title and selftext
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                text = f"{title}\n\n{selftext}".strip() if selftext else title
                
                if not text or len(text) < 30:
                    continue
                
                # Skip removed/deleted posts
                if selftext in ["[removed]", "[deleted]"]:
                    continue
                
                created_utc = post.get("created_utc", 0)
                post_date = datetime.fromtimestamp(created_utc).strftime("%Y-%m-%d") if created_utc else datetime.now().strftime("%Y-%m-%d")
                
                # Extract image URL if present
                image_url = None
                if post.get("post_hint") == "image":
                    image_url = post.get("url")
                elif post.get("thumbnail") and post.get("thumbnail") not in ["self", "default", "nsfw", "spoiler", ""]:
                    image_url = post.get("thumbnail")
                elif post.get("preview", {}).get("images"):
                    try:
                        image_url = post["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")
                    except (KeyError, IndexError):
                        pass
                
                posts.append({
                    "text": text,
                    "title": title,
                    "source": "Reddit",
                    "subreddit": subreddit,
                    "username": post.get("author", "unknown"),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "post_id": post.get("id", ""),
                    "post_date": post_date,
                    "created_utc": created_utc,
                    "_logged_date": datetime.now().isoformat(),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                    "image_url": image_url,
                    "is_self": post.get("is_self", True),
                    "link_flair_text": post.get("link_flair_text", ""),
                })
                
        elif res.status_code == 429:
            print(f"  ⚠️ Rate limited on r/{subreddit}, waiting...")
            time.sleep(60)
        elif res.status_code == 403:
            print(f"  🔒 r/{subreddit}: Private or quarantined")
        elif res.status_code == 404:
            print(f"  ❓ r/{subreddit}: Not found")
        else:
            print(f"  ⚠️ r/{subreddit}: HTTP {res.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"  ⏱️ r/{subreddit}: Timeout")
    except Exception as e:
        print(f"  ❌ r/{subreddit}: {e}")
    
    return posts


def get_post_comments(post_url: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch comments from a specific Reddit post URL."""
    comments = []
    
    # Convert URL to JSON endpoint
    if not post_url.endswith('.json'):
        post_url = post_url.rstrip('/') + '.json'
    
    try:
        res = requests.get(post_url, params={"raw_json": 1, "limit": limit}, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            # Reddit returns [post, comments] array
            if len(data) > 1:
                comment_data = data[1].get("data", {}).get("children", [])
                
                def extract_comments(children, depth=0):
                    """Recursively extract comments including replies."""
                    extracted = []
                    for child in children:
                        if child.get("kind") != "t1":
                            continue
                        comment = child.get("data", {})
                        text = comment.get("body", "")
                        
                        if text and len(text) >= 30 and text not in ["[removed]", "[deleted]"]:
                            created_utc = comment.get("created_utc", 0)
                            post_date = datetime.fromtimestamp(created_utc).strftime("%Y-%m-%d") if created_utc else datetime.now().strftime("%Y-%m-%d")
                            
                            extracted.append({
                                "text": text,
                                "source": "Reddit",
                                "subreddit": comment.get("subreddit", "unknown"),
                                "username": comment.get("author", "unknown"),
                                "url": f"https://reddit.com{comment.get('permalink', '')}",
                                "post_id": comment.get("id", ""),
                                "post_date": post_date,
                                "_logged_date": datetime.now().isoformat(),
                                "score": comment.get("score", 0),
                                "is_comment": True,
                                "parent_id": comment.get("parent_id", ""),
                                "link_title": comment.get("link_title", ""),
                                "comment_depth": depth,
                            })
                        
                        # Get replies
                        replies = comment.get("replies")
                        if replies and isinstance(replies, dict):
                            reply_children = replies.get("data", {}).get("children", [])
                            extracted.extend(extract_comments(reply_children, depth + 1))
                    
                    return extracted
                
                comments = extract_comments(comment_data)
                
    except Exception as e:
        print(f"  ⚠️ Error fetching post comments: {e}")
    
    return comments


def get_subreddit_comments(subreddit: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent comments from a subreddit."""
    comments = []
    
    url = f"https://www.reddit.com/r/{subreddit}/comments.json"
    params = {"limit": limit, "raw_json": 1}
    
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            children = data.get("data", {}).get("children", [])
            
            for child in children:
                comment = child.get("data", {})
                text = comment.get("body", "")
                
                if not text or len(text) < 50 or text in ["[removed]", "[deleted]"]:
                    continue
                
                created_utc = comment.get("created_utc", 0)
                post_date = datetime.fromtimestamp(created_utc).strftime("%Y-%m-%d") if created_utc else datetime.now().strftime("%Y-%m-%d")
                
                comments.append({
                    "text": text,
                    "source": "Reddit",
                    "subreddit": subreddit,
                    "username": comment.get("author", "unknown"),
                    "url": f"https://reddit.com{comment.get('permalink', '')}",
                    "post_id": comment.get("id", ""),
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "score": comment.get("score", 0),
                    "is_comment": True,
                    "parent_id": comment.get("parent_id", ""),
                    "link_title": comment.get("link_title", ""),
                })
                
    except Exception as e:
        pass  # Silently fail for comments
    
    return comments


def search_reddit(query: str, limit: int = 50, sort: str = "relevance", time_filter: str = "month") -> List[Dict[str, Any]]:
    """
    Search Reddit across all subreddits.
    sort: relevance, hot, top, new, comments
    time_filter: hour, day, week, month, year, all
    """
    posts = []
    
    url = "https://www.reddit.com/search.json"
    params = {
        "q": query,
        "limit": limit,
        "sort": sort,
        "t": time_filter,
        "raw_json": 1,
    }
    
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            children = data.get("data", {}).get("children", [])
            
            for child in children:
                post = child.get("data", {})
                
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                text = f"{title}\n\n{selftext}".strip() if selftext else title
                
                if not text or len(text) < 30:
                    continue
                
                if selftext in ["[removed]", "[deleted]"]:
                    continue
                
                created_utc = post.get("created_utc", 0)
                post_date = datetime.fromtimestamp(created_utc).strftime("%Y-%m-%d") if created_utc else datetime.now().strftime("%Y-%m-%d")
                
                posts.append({
                    "text": text,
                    "title": title,
                    "source": "Reddit",
                    "subreddit": post.get("subreddit", "unknown"),
                    "search_term": query,
                    "username": post.get("author", "unknown"),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "post_id": post.get("id", ""),
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                })
                
        elif res.status_code == 429:
            print(f"  ⚠️ Rate limited on search, waiting...")
            time.sleep(60)
        else:
            print(f"  ⚠️ Search failed: HTTP {res.status_code}")
            
    except Exception as e:
        print(f"  ❌ Search error: {e}")
    
    return posts


def filter_high_signal_posts(posts: List[Dict[str, Any]], min_score: int = 2) -> List[Dict[str, Any]]:
    """Filter posts to keep only high-signal content."""
    
    # Keywords that indicate valuable feedback
    signal_keywords = [
        "problem", "issue", "broken", "scam", "fraud", "delay", "lost",
        "refund", "return", "dispute", "complaint", "terrible", "awful",
        "amazing", "love", "hate", "shipping", "damage", "authentic",
        "fake", "counterfeit", "grade", "grading", "vault", "fees",
        "customer service", "support", "help", "advice", "recommend",
        "experience", "review", "warning", "beware", "tip", "psa",
        "bgs", "cgc", "ebay", "whatnot", "fanatics", "marketplace",
        # Competitive signals
        "switched to", "moving to", "better than ebay", "leaving ebay",
        "heritage", "goldin", "tcgplayer", "alt.xyz", "mercari",
        # Product-specific
        "price guide", "card ladder", "scan to price", "authenticity guarantee",
        "promoted listing", "best offer", "buy it now",
        # Beckett
        "beckett", "bgs", "beckett grading", "beckett acquisition",
    ]
    
    high_signal = []
    for post in posts:
        text_lower = post.get("text", "").lower()
        
        # Skip low-engagement posts unless they have signal keywords
        score = post.get("score", 0)
        has_keyword = any(kw in text_lower for kw in signal_keywords)
        
        if score >= min_score or has_keyword:
            high_signal.append(post)
    
    return high_signal


def run_reddit_scraper(include_comments: bool = False, include_search: bool = True) -> List[Dict[str, Any]]:
    """Main entry point for Reddit scraping."""
    print("🤖 Starting Reddit scraper (public JSON API)...")
    
    all_posts = []
    
    # Scrape subreddits
    print(f"\n📍 Scraping {len(SUBREDDITS)} subreddits...")
    for subreddit in SUBREDDITS:
        print(f"  📂 r/{subreddit}...")
        
        # Get hot posts
        posts = get_subreddit_posts(subreddit, sort="hot", limit=50)
        
        # Get top posts from past year (covers 9 months)
        top_posts = get_subreddit_posts(subreddit, sort="top", limit=100, time_filter="year")
        posts.extend(top_posts)
        
        # Get new posts
        new_posts = get_subreddit_posts(subreddit, sort="new", limit=50)
        posts.extend(new_posts)
        
        if posts:
            print(f"  📥 r/{subreddit}: {len(posts)} posts")
            all_posts.extend(posts)
        
        # Optionally get comments
        if include_comments:
            comments = get_subreddit_comments(subreddit, limit=30)
            if comments:
                print(f"  💬 r/{subreddit}: {len(comments)} comments")
                all_posts.extend(comments)
        
        time.sleep(1)  # Rate limiting (Reddit allows ~60 req/min)
    
    # Scrape comments from high-value discussion posts
    high_value_posts = [
        "https://www.reddit.com/r/Flipping/comments/1pinfv7/what_is_your_method_to_price_items_on_ebay/",
        "https://www.reddit.com/r/Ebay/comments/1c8y4xn/ebay_vault_experience/",
        "https://www.reddit.com/r/Ebay/comments/1d2qk5h/authenticity_guarantee_experience/",
        "https://www.reddit.com/r/Flipping/comments/1b5k3xm/ebay_vs_mercari_for_collectibles/",
        "https://www.reddit.com/r/pokemontcg/comments/1c4r8wn/selling_on_ebay_tips/",
        "https://www.reddit.com/r/baseballcards/comments/1d7m2xk/ebay_selling_strategies/",
        # PSA Vault high-value discussions
        "https://www.reddit.com/r/psagrading/comments/1qm4iej/psa_vault_isnt_trust_worthy_anymore/",
        "https://www.reddit.com/r/psagrading/comments/1qtic9j/psa_vault_ebay_auction/",
        "https://www.reddit.com/r/sportscards/comments/1qvvudo/psa_vault_is_officially_broken/",
        "https://www.reddit.com/r/psagrading/comments/1qvpbsg/items_sent_to_vault_instead_of_to_me/",
    ]
    
    print(f"\n💬 Scraping comments from {len(high_value_posts)} high-value posts...")
    for post_url in high_value_posts:
        print(f"  📝 Fetching comments: {post_url[:60]}...")
        comments = get_post_comments(post_url, limit=100)
        if comments:
            print(f"  💬 Got {len(comments)} comments")
            all_posts.extend(comments)
        time.sleep(2)  # Rate limiting
    
    # Search for specific topics
    if include_search:
        print(f"\n🔍 Searching {len(SEARCH_QUERIES)} queries...")
        for query in SEARCH_QUERIES:
            print(f"  🔍 Searching: '{query}'...")
            posts = search_reddit(query, limit=50, time_filter="year")
            
            if posts:
                print(f"  📥 '{query}': {len(posts)} posts")
                all_posts.extend(posts)
            
            time.sleep(1)
    
    if not all_posts:
        print("\n❌ No posts scraped from Reddit.")
        return []
    
    # Filter to high-signal posts
    print(f"\n🔬 Filtering {len(all_posts)} posts for high-signal content...")
    high_signal = filter_high_signal_posts(all_posts, min_score=1)
    
    # Deduplicate by post_id and text
    seen_ids = set()
    seen_text = set()
    unique_posts = []
    for post in high_signal:
        post_id = post.get("post_id", "")
        text_hash = post.get("text", "")[:150]
        
        if post_id and post_id in seen_ids:
            continue
        if text_hash in seen_text:
            continue
        
        seen_ids.add(post_id)
        seen_text.add(text_hash)
        unique_posts.append(post)
    
    # Sort by score (highest first)
    unique_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Scraped {len(unique_posts)} unique high-signal posts → {SAVE_PATH}")
    
    # Print top subreddits by volume
    subreddit_counts = {}
    for post in unique_posts:
        sr = post.get("subreddit", "unknown")
        subreddit_counts[sr] = subreddit_counts.get(sr, 0) + 1
    
    print("\n📊 Top subreddits by volume:")
    for sr, count in sorted(subreddit_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  r/{sr}: {count}")
    
    return unique_posts


if __name__ == "__main__":
    run_reddit_scraper(include_comments=True, include_search=True)
