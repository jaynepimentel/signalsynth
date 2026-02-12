# scrape_ebay_forums.py — eBay Community Forums scraper
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Any

# eBay Community Forums to scrape
FORUM_SECTIONS = [
    # Seller forums
    {"name": "Seller Central", "url": "https://community.ebay.com/t5/Seller-Central/bd-p/seller-central"},
    {"name": "Payments", "url": "https://community.ebay.com/t5/Payments/bd-p/payments"},
    {"name": "Shipping & Returns", "url": "https://community.ebay.com/t5/Shipping-Returns/bd-p/shipping-returns"},
    {"name": "Selling", "url": "https://community.ebay.com/t5/Selling/bd-p/selling"},
    # Buyer forums
    {"name": "Buying", "url": "https://community.ebay.com/t5/Buying/bd-p/buying"},
    {"name": "Member To Member Support", "url": "https://community.ebay.com/t5/Member-To-Member-Support/bd-p/member-support"},
    # Category-specific
    {"name": "Coins & Paper Money", "url": "https://community.ebay.com/t5/Coins-Paper-Money/bd-p/coins"},
    {"name": "Sports Trading Cards", "url": "https://community.ebay.com/t5/Sports-Trading-Cards/bd-p/tradingcards"},
    {"name": "Toys & Hobbies", "url": "https://community.ebay.com/t5/Toys-Hobbies/bd-p/toys"},
    {"name": "Collectibles", "url": "https://community.ebay.com/t5/Collectibles/bd-p/collectibles"},
]

SAVE_PATH = "data/scraped_ebay_forums.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def scrape_forum_section(section: Dict[str, str], max_pages: int = 3) -> List[Dict[str, Any]]:
    """Scrape posts from an eBay Community forum section."""
    posts = []
    section_name = section["name"]
    base_url = section["url"]
    
    for page in range(1, max_pages + 1):
        url = f"{base_url}/page/{page}" if page > 1 else base_url
        
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            
            if res.status_code != 200:
                print(f"    ⚠️ Page {page}: HTTP {res.status_code}")
                break
            
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Find discussion threads
            thread_selectors = [
                ".MessageList .message-subject a",
                ".lia-list-row .page-link",
                "h2.message-subject a",
                ".lia-message-subject a",
                "a.page-link[href*='/m-p/']",
            ]
            
            threads = []
            for selector in thread_selectors:
                threads = soup.select(selector)
                if threads:
                    break
            
            if not threads:
                # Try alternative: look for topic list items
                topic_items = soup.select(".lia-list-row, .message-row, .topic-item")
                for item in topic_items:
                    link = item.select_one("a[href*='/m-p/'], a[href*='/td-p/']")
                    if link:
                        threads.append(link)
            
            for thread in threads[:15]:  # Limit per page
                try:
                    thread_url = thread.get("href", "")
                    if not thread_url:
                        continue
                    
                    # Make URL absolute
                    if thread_url.startswith("/"):
                        thread_url = f"https://community.ebay.com{thread_url}"
                    elif not thread_url.startswith("http"):
                        continue
                    
                    thread_title = thread.get_text(strip=True)
                    if not thread_title or len(thread_title) < 10:
                        continue
                    
                    # Fetch thread content
                    thread_posts = scrape_thread(thread_url, thread_title, section_name)
                    posts.extend(thread_posts)
                    
                    time.sleep(0.5)  # Rate limiting
                    
                except Exception as e:
                    continue
            
            time.sleep(1)  # Rate limiting between pages
            
        except requests.exceptions.Timeout:
            print(f"    ⏱️ Page {page}: Timeout")
        except Exception as e:
            print(f"    ❌ Page {page}: {e}")
    
    return posts


def scrape_thread(url: str, title: str, section: str) -> List[Dict[str, Any]]:
    """Scrape all posts from a single thread."""
    posts = []
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        
        if res.status_code != 200:
            return posts
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Find all message bodies
        message_selectors = [
            ".lia-message-body-content",
            ".message-body",
            ".lia-message-body",
            ".post-content",
        ]
        
        messages = []
        for selector in message_selectors:
            messages = soup.select(selector)
            if messages:
                break
        
        # Get the original post (first message)
        if messages:
            first_msg = messages[0]
            text = first_msg.get_text(strip=True)
            
            if text and len(text) > 30:
                # Try to get author
                author = ""
                author_elem = soup.select_one(".lia-user-name-link, .author-name, .username")
                if author_elem:
                    author = author_elem.get_text(strip=True)
                
                # Try to get date
                post_date = datetime.now().strftime("%Y-%m-%d")
                date_elem = soup.select_one(".lia-message-posted-on time, .post-date, time[datetime]")
                if date_elem:
                    datetime_attr = date_elem.get("datetime", "")
                    if datetime_attr:
                        try:
                            post_date = datetime_attr[:10]
                        except:
                            pass
                
                posts.append({
                    "text": f"{title}\n\n{text}",
                    "title": title,
                    "source": "eBay Forums",
                    "forum_section": section,
                    "username": author or "unknown",
                    "url": url,
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "is_original_post": True,
                })
        
        # Get replies (if substantial)
        for msg in messages[1:5]:  # Limit to first few replies
            text = msg.get_text(strip=True)
            
            if text and len(text) > 50:
                posts.append({
                    "text": text,
                    "title": f"Re: {title}",
                    "source": "eBay Forums",
                    "forum_section": section,
                    "username": "unknown",
                    "url": url,
                    "post_date": datetime.now().strftime("%Y-%m-%d"),
                    "_logged_date": datetime.now().isoformat(),
                    "is_original_post": False,
                })
                
    except Exception as e:
        pass
    
    return posts


def run_ebay_forums_scraper() -> List[Dict[str, Any]]:
    """Main entry point for eBay Forums scraping."""
    print("🛒 Starting eBay Community Forums scraper...")
    
    all_posts = []
    
    for section in FORUM_SECTIONS:
        print(f"  📂 {section['name']}...")
        posts = scrape_forum_section(section, max_pages=2)
        
        if posts:
            print(f"  📥 {section['name']}: {len(posts)} posts")
            all_posts.extend(posts)
        else:
            print(f"  ⚠️ {section['name']}: No posts found")
        
        time.sleep(1)
    
    if not all_posts:
        print("\n❌ No posts scraped from eBay Forums.")
        return []
    
    # Deduplicate by URL
    seen = set()
    unique_posts = []
    for post in all_posts:
        url = post.get("url", "")
        text_hash = post.get("text", "")[:100]
        key = url or text_hash
        
        if key not in seen:
            seen.add(key)
            unique_posts.append(post)
    
    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Scraped {len(unique_posts)} unique posts → {SAVE_PATH}")
    
    # Print section breakdown
    section_counts = {}
    for post in unique_posts:
        sec = post.get("forum_section", "unknown")
        section_counts[sec] = section_counts.get(sec, 0) + 1
    
    print("\n📊 Posts by section:")
    for sec, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        print(f"  {sec}: {count}")
    
    return unique_posts


if __name__ == "__main__":
    run_ebay_forums_scraper()
