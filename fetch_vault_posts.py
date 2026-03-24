#!/usr/bin/env python3
"""Fetch specific PSA Vault posts and add to scraped data."""
import json
import requests
import time

posts_to_add = []
urls = [
    'https://www.reddit.com/r/psagrading/comments/1qm4iej/psa_vault_isnt_trust_worthy_anymore.json',
    'https://www.reddit.com/r/psagrading/comments/1qtic9j/psa_vault_ebay_auction.json',
    'https://www.reddit.com/r/sportscards/comments/1qvvudo/psa_vault_is_officially_broken.json',
    'https://www.reddit.com/r/psagrading/comments/1qvpbsg/items_sent_to_vault_instead_of_to_me.json',
]

for url in urls:
    try:
        r = requests.get(url, headers={'User-Agent': 'SignalSynth/1.0'}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            post = data[0]['data']['children'][0]['data']
            posts_to_add.append({
                'title': post.get('title', ''),
                'text': post.get('title', '') + ' ' + post.get('selftext', ''),
                'subreddit': post.get('subreddit', ''),
                'url': 'https://reddit.com' + post.get('permalink', ''),
                'source': 'Reddit',
                'created_utc': post.get('created_utc', 0),
            })
            print(f"Got: {post.get('title', '')[:50]}")
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")

# Load existing and merge
existing = json.load(open('data/scraped_reddit_posts.json', 'r', encoding='utf-8'))
existing_urls = {p.get('url', '') for p in existing}
new_posts = [p for p in posts_to_add if p.get('url') not in existing_urls]
print(f"Adding {len(new_posts)} new posts")
existing.extend(new_posts)
json.dump(existing, open('data/scraped_reddit_posts.json', 'w', encoding='utf-8'), indent=2)
print("Done")
