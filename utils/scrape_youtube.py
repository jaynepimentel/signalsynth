# scrape_youtube.py — YouTube scraper for collectibles video transcripts & comments
# Uses youtube-transcript-api (no API key) for transcripts and
# YouTube Data API v3 for search/comments (requires YOUTUBE_API_KEY in .env).
# Falls back to RSS feeds if no API key is set.

import requests
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SAVE_PATH = "data/scraped_youtube_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Collectibles YouTube channels (channel IDs)
CHANNELS = {
    "Jabs Family": "UCBUF4GX277yARAA5BypZiaQ",
    "Sports Card Investor": "UCk9zL0UlZ28uS7tlcguSLQg",
    "Stacking Slabs": "UCV1WAph8QQj0O5s3IQCjjBg",
    "CardShopLive": "UCoUHqtkCTJ60WdYZHJRQrng",
    "CardCollector2": "UCbUwX0sho_2c9AweeyA8DlA",
    "Gary Vee": "UCctXZhXmG-kf3tlIXgVZUlw",
    "Whatnot": "UCVdat_B93QEX801rp3vTfOg",
    "Goldin Auctions": "UC7Z5M_SnsFMk8NCi0slmXIA",
}

# Search queries for finding relevant videos
SEARCH_QUERIES = [
    "ebay trading cards",
    "ebay vault review",
    "ebay authenticity guarantee",
    "psa grading turnaround",
    "sports cards investing",
    "ebay vs fanatics cards",
    "card breaks live",
    "graded cards selling tips",
]


def _get_transcript(video_id):
    """Fetch transcript for a YouTube video using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        # Join all text snippets
        full_text = " ".join(snippet.text for snippet in transcript)
        return full_text.strip()
    except Exception:
        return None


def _get_video_comments_api(video_id, max_comments=20):
    """Fetch top comments using YouTube Data API v3."""
    if not YOUTUBE_API_KEY:
        return []

    comments = []
    url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_comments, 100),
        "order": "relevance",
        "textFormat": "plainText",
        "key": YOUTUBE_API_KEY,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": snippet.get("textDisplay", ""),
                "author": snippet.get("authorDisplayName", "unknown"),
                "likes": snippet.get("likeCount", 0),
                "published": snippet.get("publishedAt", ""),
            })
    except Exception:
        pass

    return comments


def _search_videos_api(query, max_results=10):
    """Search YouTube videos using Data API v3."""
    if not YOUTUBE_API_KEY:
        return []

    videos = []
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "date",
        "relevanceLanguage": "en",
        "key": YOUTUBE_API_KEY,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        for item in data.get("items", []):
            vid = item["id"].get("videoId")
            snippet = item.get("snippet", {})
            if vid:
                videos.append({
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "published": snippet.get("publishedAt", ""),
                    "description": snippet.get("description", ""),
                })
    except Exception:
        pass

    return videos


def _get_channel_videos_rss(channel_id, channel_name):
    """Fetch recent videos from a channel via YouTube RSS (no API key needed)."""
    videos = []
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    try:
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }
        root = ET.fromstring(r.content)

        for entry in root.findall("atom:entry", ns)[:10]:
            video_id = entry.find("yt:videoId", ns)
            title = entry.find("atom:title", ns)
            published = entry.find("atom:published", ns)
            media_group = entry.find("media:group", ns)
            description = ""
            if media_group is not None:
                desc_el = media_group.find("media:description", ns)
                if desc_el is not None and desc_el.text:
                    description = desc_el.text

            if video_id is not None and video_id.text:
                videos.append({
                    "video_id": video_id.text,
                    "title": title.text if title is not None else "",
                    "channel": channel_name,
                    "published": published.text if published is not None else "",
                    "description": description,
                })
    except Exception as e:
        print(f"    [WARN] RSS failed for {channel_name}: {e}")

    return videos


def scrape_channel_videos():
    """Scrape recent videos from known collectibles channels."""
    print("  Fetching videos from collectibles channels...")
    all_videos = []

    for name, channel_id in CHANNELS.items():
        videos = _get_channel_videos_rss(channel_id, name)
        all_videos.extend(videos)
        print(f"    {name}: {len(videos)} videos")
        time.sleep(0.5)

    return all_videos


def scrape_search_videos():
    """Search for collectibles-related videos."""
    if not YOUTUBE_API_KEY:
        print("  [SKIP] No YOUTUBE_API_KEY set, skipping search-based video discovery")
        return []

    print("  Searching for collectibles videos...")
    all_videos = []
    seen_ids = set()

    for query in SEARCH_QUERIES:
        videos = _search_videos_api(query, max_results=5)
        for v in videos:
            if v["video_id"] not in seen_ids:
                seen_ids.add(v["video_id"])
                all_videos.append(v)
        print(f"    '{query}': {len(videos)} videos")
        time.sleep(0.5)

    return all_videos


def process_videos(videos, max_videos=50):
    """Process videos: fetch transcripts and comments, build posts.
    
    Falls back to video title + description if transcripts are IP-blocked.
    """
    posts = []
    seen_ids = set()
    transcript_ok = 0
    transcript_fail = 0
    transcript_blocked = False

    # Deduplicate
    unique_videos = []
    for v in videos:
        vid = v["video_id"]
        if vid not in seen_ids:
            seen_ids.add(vid)
            unique_videos.append(v)

    # Limit to avoid excessive API calls
    unique_videos = unique_videos[:max_videos]
    print(f"  Processing {len(unique_videos)} unique videos...")

    for i, video in enumerate(unique_videos):
        vid = video["video_id"]
        title = video.get("title", "")
        channel = video.get("channel", "unknown")
        published = video.get("published", "")
        description = video.get("description", "")

        # Parse date
        post_date = datetime.now().strftime("%Y-%m-%d")
        if published:
            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                post_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        video_url = f"https://www.youtube.com/watch?v={vid}"

        # Try transcript (skip if already IP-blocked to avoid wasting time)
        transcript = None
        if not transcript_blocked:
            transcript = _get_transcript(vid)
            if transcript and len(transcript) > 50:
                transcript_ok += 1
            else:
                transcript_fail += 1
                # If first 3 all fail, assume IP-blocked
                if transcript_fail >= 3 and transcript_ok == 0:
                    transcript_blocked = True
                    print("    [INFO] Transcripts appear IP-blocked, using title+description fallback")

        # Build post from transcript or title+description
        if transcript and len(transcript) > 50:
            post_text = f"{title}\n\n{transcript[:3000]}"
            source_label = "YouTube (transcript)"
        else:
            # Fallback: title + description from RSS (always available)
            post_text = title
            if description and len(description) > 10:
                post_text = f"{title}\n\n{description[:2000]}"
            source_label = "YouTube"

        if len(post_text) >= 20:
            posts.append({
                "text": post_text,
                "title": title,
                "source": source_label,
                "url": video_url,
                "username": channel,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": "",
                "score": 0,
                "like_count": 0,
                "num_comments": 0,
                "post_id": f"yt_{vid}",
            })

        # Fetch comments (requires YOUTUBE_API_KEY)
        comments = _get_video_comments_api(vid, max_comments=15)
        for comment in comments:
            c_text = comment.get("text", "")
            if len(c_text) < 20:
                continue

            c_date = post_date
            if comment.get("published"):
                try:
                    dt = datetime.fromisoformat(comment["published"].replace("Z", "+00:00"))
                    c_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            posts.append({
                "text": c_text,
                "title": f"Comment on: {title}",
                "source": "YouTube (comment)",
                "url": video_url,
                "username": comment.get("author", "unknown"),
                "post_date": c_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": "",
                "score": comment.get("likes", 0),
                "like_count": comment.get("likes", 0),
                "num_comments": 0,
                "post_id": f"yt_comment_{vid}_{hash(c_text) % 10**8}",
            })

        if (i + 1) % 10 == 0:
            print(f"    Processed {i + 1}/{len(unique_videos)} videos...")

        time.sleep(0.3)

    print(f"    Transcripts: {transcript_ok} ok, {transcript_fail} failed, blocked={transcript_blocked}")
    return posts


def run_youtube_scraper():
    """Main entry point for YouTube scraper."""
    print("\n" + "=" * 50)
    print("\U0001f3ac YOUTUBE SCRAPER")
    print("  (transcripts + comments from collectibles channels)")
    print("=" * 50)

    all_videos = []

    # Channel RSS (always works, no API key needed)
    try:
        channel_videos = scrape_channel_videos()
        all_videos.extend(channel_videos)
    except Exception as e:
        print(f"  \u274c Channel scrape failed: {e}")

    # Search-based (requires API key)
    try:
        search_videos = scrape_search_videos()
        all_videos.extend(search_videos)
    except Exception as e:
        print(f"  \u274c Search scrape failed: {e}")

    # Process: transcripts + comments
    posts = process_videos(all_videos)

    # Deduplicate by post_id
    seen = set()
    unique = []
    for p in posts:
        pid = p.get("post_id", "")
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        unique.append(p)

    # Sort by date
    unique.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    transcript_count = sum(1 for p in unique if p["source"] == "YouTube (transcript)")
    comment_count = sum(1 for p in unique if p["source"] == "YouTube (comment)")
    print(f"\n  Transcripts: {transcript_count}")
    print(f"  Comments: {comment_count}")
    print(f"  Total: {len(unique)}")
    print(f"  Saved to: {SAVE_PATH}")

    return unique


if __name__ == "__main__":
    results = run_youtube_scraper()
    print(f"\nDone. {len(results)} posts collected.")
