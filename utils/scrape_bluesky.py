# scrape_bluesky.py — Bluesky scraper using public API (no auth required)
import requests
import json
import os
import time
from datetime import datetime
from urllib.parse import quote

# Search terms for collectibles/marketplace topics
SEARCH_TERMS = [
    "ebay trading cards",
    "ebay psa",
    "ebay vault",
    "ebay authentication",
    "ebay shipping",
    "ebay refund",
    "ebay seller",
    "funko vault",
    "graded cards",
    "psa graded",
    "trading card collection",
    "sports cards",
    "pokemon cards ebay",
    "collectibles marketplace",
]

# Hashtags/terms to search in post text (since search API requires auth)
COLLECTIBLES_KEYWORDS = [
    "ebay", "trading cards", "psa", "bgs", "graded", "slab",
    "sports cards", "pokemon tcg", "funko", "collectibles",
    "whatnot", "goldin", "auction", "grading", "vault",
]

# Active Bluesky accounts - verified or likely to exist
# Note: Many collectibles accounts use custom domains, not .bsky.social
PUBLIC_ACCOUNTS = [
    # Use DIDs for accounts that definitely exist (more reliable)
    # These are discovered dynamically below
]

# Feeds to try (curated feeds for collectibles topics)
COLLECTIBLES_FEEDS = [
    # Popular/trending feeds that may contain collectibles content
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot",
]

SAVE_PATH = "data/scraped_bluesky_posts.json"
BLUESKY_API = "https://public.api.bsky.app"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def search_posts(query, limit=25):
    """Search for posts on Bluesky using the public API."""
    posts = []
    
    try:
        url = f"{BLUESKY_API}/xrpc/app.bsky.feed.searchPosts"
        params = {
            "q": query,
            "limit": limit,
            "sort": "latest",
        }
        
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            
            for post in data.get("posts", []):
                try:
                    record = post.get("record", {})
                    text = record.get("text", "")
                    
                    if not text or len(text) < 20:
                        continue
                    
                    author = post.get("author", {})
                    handle = author.get("handle", "unknown")
                    display_name = author.get("displayName", handle)
                    
                    uri = post.get("uri", "")
                    # Convert AT URI to web URL
                    # at://did:plc:xxx/app.bsky.feed.post/yyy -> https://bsky.app/profile/handle/post/yyy
                    post_id = uri.split("/")[-1] if uri else ""
                    web_url = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else ""
                    
                    created_at = record.get("createdAt", "")
                    post_date = datetime.now().strftime("%Y-%m-%d")
                    if created_at:
                        try:
                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            post_date = dt.strftime("%Y-%m-%d")
                        except:
                            pass
                    
                    posts.append({
                        "text": text,
                        "source": "Bluesky",
                        "search_term": query,
                        "username": handle,
                        "display_name": display_name,
                        "url": web_url,
                        "post_date": post_date,
                        "_logged_date": datetime.now().isoformat(),
                        "like_count": post.get("likeCount", 0),
                        "repost_count": post.get("repostCount", 0),
                        "reply_count": post.get("replyCount", 0),
                    })
                    
                except Exception:
                    continue
                    
        elif res.status_code == 429:
            print(f"  ⚠️ Rate limited for '{query}', waiting...")
            time.sleep(30)
        else:
            print(f"  ⚠️ Search failed for '{query}': HTTP {res.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"  ⏱️ Timeout for '{query}'")
    except Exception as e:
        print(f"  ❌ Error searching '{query}': {e}")
    
    return posts


def get_author_feed(handle, limit=20):
    """Get posts from a specific Bluesky account."""
    posts = []
    
    try:
        # First resolve the handle to a DID
        resolve_url = f"{BLUESKY_API}/xrpc/com.atproto.identity.resolveHandle"
        res = requests.get(resolve_url, params={"handle": handle}, headers=HEADERS, timeout=10)
        
        if res.status_code != 200:
            print(f"  ⚠️ Could not resolve @{handle}")
            return posts
        
        did = res.json().get("did", "")
        if not did:
            return posts
        
        # Get the author's feed
        feed_url = f"{BLUESKY_API}/xrpc/app.bsky.feed.getAuthorFeed"
        params = {
            "actor": did,
            "limit": limit,
            "filter": "posts_no_replies",
        }
        
        res = requests.get(feed_url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            
            for item in data.get("feed", []):
                try:
                    post = item.get("post", {})
                    record = post.get("record", {})
                    text = record.get("text", "")
                    
                    if not text or len(text) < 20:
                        continue
                    
                    author = post.get("author", {})
                    author_handle = author.get("handle", handle)
                    display_name = author.get("displayName", author_handle)
                    
                    uri = post.get("uri", "")
                    post_id = uri.split("/")[-1] if uri else ""
                    web_url = f"https://bsky.app/profile/{author_handle}/post/{post_id}" if post_id else ""
                    
                    created_at = record.get("createdAt", "")
                    post_date = datetime.now().strftime("%Y-%m-%d")
                    if created_at:
                        try:
                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            post_date = dt.strftime("%Y-%m-%d")
                        except:
                            pass
                    
                    posts.append({
                        "text": text,
                        "source": "Bluesky",
                        "username": author_handle,
                        "display_name": display_name,
                        "url": web_url,
                        "post_date": post_date,
                        "_logged_date": datetime.now().isoformat(),
                        "like_count": post.get("likeCount", 0),
                        "repost_count": post.get("repostCount", 0),
                        "reply_count": post.get("replyCount", 0),
                    })
                    
                except Exception:
                    continue
                    
        else:
            print(f"  ⚠️ Feed failed for @{handle}: HTTP {res.status_code}")
            
    except Exception as e:
        print(f"  ❌ Error fetching @{handle}: {e}")
    
    return posts


def search_accounts(query, limit=25):
    """Search for Bluesky accounts matching a query."""
    accounts = []
    
    try:
        url = f"{BLUESKY_API}/xrpc/app.bsky.actor.searchActors"
        params = {"q": query, "limit": limit}
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            for actor in data.get("actors", []):
                handle = actor.get("handle", "")
                if handle:
                    accounts.append({
                        "handle": handle,
                        "display_name": actor.get("displayName", handle),
                        "description": actor.get("description", ""),
                    })
        else:
            print(f"  ⚠️ Actor search failed: HTTP {res.status_code}")
            
    except Exception as e:
        print(f"  ⚠️ Actor search error: {e}")
    
    return accounts


# Search terms to find collectibles accounts
ACCOUNT_SEARCH_TERMS = [
    "trading cards",
    "sports cards",
    "pokemon tcg",
    "graded cards",
    "psa grading",
    "card collector",
    "funko pop",
    "collectibles",
    "ebay seller",
    "card breaks",
    "baseball cards",
    "basketball cards",
]


def get_feed_posts(feed_uri, limit=30):
    """Get posts from a specific feed generator."""
    posts = []
    
    try:
        url = f"{BLUESKY_API}/xrpc/app.bsky.feed.getFeed"
        params = {"feed": feed_uri, "limit": limit}
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            
            for item in data.get("feed", []):
                post = item.get("post", {})
                record = post.get("record", {})
                text = record.get("text", "")
                
                # Filter for collectibles keywords
                text_lower = text.lower()
                if not any(kw in text_lower for kw in COLLECTIBLES_KEYWORDS):
                    continue
                
                if not text or len(text) < 20:
                    continue
                
                author = post.get("author", {})
                handle = author.get("handle", "unknown")
                display_name = author.get("displayName", handle)
                
                uri = post.get("uri", "")
                post_id = uri.split("/")[-1] if uri else ""
                web_url = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else ""
                
                created_at = record.get("createdAt", "")
                post_date = datetime.now().strftime("%Y-%m-%d")
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        post_date = dt.strftime("%Y-%m-%d")
                    except:
                        pass
                
                posts.append({
                    "text": text,
                    "source": "Bluesky",
                    "username": handle,
                    "display_name": display_name,
                    "url": web_url,
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "like_count": post.get("likeCount", 0),
                    "repost_count": post.get("repostCount", 0),
                })
                
    except Exception as e:
        print(f"  ⚠️ Feed fetch error: {e}")
    
    return posts


def discover_accounts_from_posts(posts):
    """Extract unique account handles from collected posts."""
    handles = set()
    for post in posts:
        handle = post.get("username", "")
        if handle and handle != "unknown":
            handles.add(handle)
    return list(handles)


def run_bluesky_scraper():
    """Main entry point."""
    print("🦋 Starting Bluesky scraper (public API)...")
    
    all_posts = []
    all_handles = set()
    
    # Search for collectibles-related accounts
    print("\n🔍 Searching for collectibles accounts...")
    for term in ACCOUNT_SEARCH_TERMS:
        print(f"  🔍 Searching: '{term}'...")
        accounts = search_accounts(term, limit=15)
        for acc in accounts:
            all_handles.add(acc["handle"])
        time.sleep(0.5)
    
    print(f"\n👤 Found {len(all_handles)} unique accounts, fetching feeds...")
    
    # Get posts from discovered accounts
    for handle in list(all_handles)[:50]:  # Limit to 50 accounts
        posts = get_author_feed(handle, limit=15)
        if posts:
            # Filter for collectibles keywords
            filtered = []
            for post in posts:
                text_lower = post.get("text", "").lower()
                if any(kw in text_lower for kw in COLLECTIBLES_KEYWORDS):
                    filtered.append(post)
            
            if filtered:
                print(f"  📥 @{handle}: {len(filtered)} relevant posts")
                all_posts.extend(filtered)
        
        time.sleep(0.3)
    
    if not all_posts:
        print("\n❌ No posts scraped from Bluesky.")
        return []
    
    # Deduplicate by text
    seen = set()
    unique_posts = []
    for post in all_posts:
        text_hash = post["text"][:100]
        if text_hash not in seen:
            seen.add(text_hash)
            unique_posts.append(post)
    
    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Scraped {len(unique_posts)} unique posts → {SAVE_PATH}")
    return unique_posts


if __name__ == "__main__":
    run_bluesky_scraper()
