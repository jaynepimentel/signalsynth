# scrape_twitter.py — Twitter/X scraper using guest token API
import requests
import json
import os
import time
import re
from datetime import datetime
from urllib.parse import quote

# Search terms for collectibles/marketplace topics
SEARCH_TERMS = [
    "ebay trading cards",
    "ebay psa graded", 
    "ebay vault",
    "ebay authentication",
    "ebay shipping problem",
    "ebay refund",
    "funko vault",
    "graded cards",
]

SAVE_PATH = "data/scraped_twitter_posts.json"

# Twitter's internal API endpoints
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


class TwitterGuestScraper:
    """Scrape Twitter using guest token (no login required)."""
    
    def __init__(self):
        self.session = requests.Session()
        self.guest_token = None
        self.session.headers.update({
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
        })
    
    def get_guest_token(self):
        """Get a guest token from Twitter."""
        try:
            res = self.session.post(
                "https://api.twitter.com/1.1/guest/activate.json",
                timeout=10
            )
            if res.status_code == 200:
                self.guest_token = res.json().get("guest_token")
                self.session.headers["x-guest-token"] = self.guest_token
                print(f"  🔑 Got guest token: {self.guest_token[:10]}...")
                return True
        except Exception as e:
            print(f"  ❌ Failed to get guest token: {e}")
        return False
    
    def search_tweets(self, query, count=20):
        """Search for tweets using Twitter's internal API."""
        posts = []
        
        if not self.guest_token:
            if not self.get_guest_token():
                return posts
        
        # Twitter's GraphQL search endpoint
        variables = {
            "rawQuery": query,
            "count": count,
            "querySource": "typed_query",
            "product": "Latest"
        }
        
        features = {
            "rweb_lists_timeline_redesign_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_media_download_video_enabled": False,
            "responsive_web_enhance_cards_enabled": False
        }
        
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features),
        }
        
        try:
            res = self.session.get(
                "https://twitter.com/i/api/graphql/gkjsKepM6gl_HmFWoWKfgg/SearchTimeline",
                params=params,
                timeout=15
            )
            
            if res.status_code == 200:
                data = res.json()
                posts = self._parse_search_results(data, query)
            elif res.status_code == 429:
                print(f"  ⚠️ Rate limited, waiting...")
                time.sleep(60)
            else:
                print(f"  ⚠️ Search failed: HTTP {res.status_code}")
                
        except Exception as e:
            print(f"  ❌ Search error: {e}")
        
        return posts
    
    def _parse_search_results(self, data, query):
        """Parse tweet data from Twitter's GraphQL response."""
        posts = []
        
        try:
            # Navigate the nested response structure
            instructions = (
                data.get("data", {})
                .get("search_by_raw_query", {})
                .get("search_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )
            
            for instruction in instructions:
                entries = instruction.get("entries", [])
                for entry in entries:
                    try:
                        # Get tweet content
                        content = entry.get("content", {})
                        item_content = content.get("itemContent", {})
                        tweet_results = item_content.get("tweet_results", {})
                        result = tweet_results.get("result", {})
                        
                        # Handle different result types
                        if result.get("__typename") == "TweetWithVisibilityResults":
                            result = result.get("tweet", {})
                        
                        legacy = result.get("legacy", {})
                        
                        text = legacy.get("full_text", "")
                        if not text or len(text) < 20:
                            continue
                        
                        # Get user info
                        user = result.get("core", {}).get("user_results", {}).get("result", {})
                        user_legacy = user.get("legacy", {})
                        username = user_legacy.get("screen_name", "unknown")
                        
                        # Get tweet ID and date
                        tweet_id = legacy.get("id_str", "")
                        created_at = legacy.get("created_at", "")
                        
                        post_date = datetime.now().strftime("%Y-%m-%d")
                        if created_at:
                            try:
                                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                                post_date = dt.strftime("%Y-%m-%d")
                            except:
                                pass
                        
                        posts.append({
                            "text": text,
                            "source": "Twitter/X",
                            "search_term": query,
                            "username": username,
                            "url": f"https://twitter.com/{username}/status/{tweet_id}" if tweet_id else "",
                            "post_date": post_date,
                            "_logged_date": datetime.now().isoformat(),
                            "retweet_count": legacy.get("retweet_count", 0),
                            "favorite_count": legacy.get("favorite_count", 0),
                        })
                        
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"  ⚠️ Parse error: {e}")
        
        return posts


def run_twitter_scraper():
    """Main entry point."""
    print("🚀 Starting Twitter/X scraper (guest token API)...")
    
    scraper = TwitterGuestScraper()
    all_posts = []
    
    for term in SEARCH_TERMS:
        print(f"  🔍 Searching: '{term}'...")
        posts = scraper.search_tweets(term, count=20)
        
        if posts:
            print(f"  � '{term}': {len(posts)} tweets")
            all_posts.extend(posts)
        else:
            print(f"  ⚠️ '{term}': No tweets found")
        
        time.sleep(2)  # Rate limiting
    
    if not all_posts:
        print("\n❌ No tweets scraped. Twitter may have blocked guest access.")
        print("\nAlternative options:")
        print("  1. Use Twitter API v2 with bearer token (developer.twitter.com)")
        print("  2. Set TWITTER_USERNAME/PASSWORD for authenticated access")
        return []
    
    # Deduplicate
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
    
    print(f"\n✅ Scraped {len(unique_posts)} unique tweets → {SAVE_PATH}")
    return unique_posts


if __name__ == "__main__":
    run_twitter_scraper()
