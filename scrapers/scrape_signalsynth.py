# scrape_signalsynth.py — smart search expansion + unified scraping
import requests
from bs4 import BeautifulSoup
from time import sleep
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SAVE_PATH = "data/scraped_community_posts.txt"

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net"
]

# 💡 Dynamically expand search terms
base_terms = [
    "grading", "vault", "authentication", "shipping", "return", "fees",
    "psa", "whatnot", "fanatics", "ebay", "alt"
]

modifiers = [
    "", "delay", "issue", "problem", "complaint", "refund", "slow", "confused", "not received", "too high"
]

NITTER_SEARCHES = sorted(set(f"{term} {mod}".strip() for term in base_terms for mod in modifiers if term != mod))

REDDIT_SEARCHES = {
    "Fanatics": ["baseballcards", "tradingcards", "pokemonTCG", "MagicTCG"],
    "Collectibles": ["ebay"]
}

COMMUNITY_FORUMS = {
    "Buying-Selling": "https://community.ebay.com/t5/Buying-Selling/ct-p/buying-selling-db",
    "Collectibles-Art": "https://community.ebay.com/t5/Collectibles-Art/bd-p/29"
}


def scrape_nitter(term):
    posts = []
    for base in NITTER_INSTANCES:
        try:
            url = f"{base}/search?f=tweets&q={term.replace(' ', '+')}"
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            for tweet in soup.select(".timeline-item .tweet-content"):
                text = tweet.get_text(strip=True)
                if text and len(text.split()) > 6:
                    posts.append(f"[Twitter] {term}: {text}")
            break  # use first success
        except:
            continue
    return posts


def scrape_reddit_search(term, subreddit):
    url = f"https://old.reddit.com/r/{subreddit}/search?q={term.replace(' ', '+')}&restrict_sr=1&sort=new"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    posts = []
    for post in soup.select(".search-title"):
        text = post.get_text(strip=True)
        if text and len(text.split()) > 6:
            posts.append(f"[Reddit - {subreddit}] {term}: {text}")
    return posts


def scrape_ebay_forum(name, url):
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    posts = []
    for thread in soup.select(".lia-link-navigation"):
        title = thread.get_text(strip=True)
        if title and len(title) > 10:
            posts.append(f"[eBay Forum - {name}] {title}")
    return posts


def run_signal_scraper():
    all_posts = set()

    # eBay Forums
    for name, url in COMMUNITY_FORUMS.items():
        try:
            all_posts.update(scrape_ebay_forum(name, url))
        except Exception as e:
            print(f"Forum error: {name} — {e}")

    # Reddit
    for term in NITTER_SEARCHES:
        for category, subs in REDDIT_SEARCHES.items():
            for sub in subs:
                try:
                    posts = scrape_reddit_search(term, sub)
                    all_posts.update(posts)
                    sleep(0.5)
                except Exception as e:
                    print(f"Reddit error: {sub} — {e}")

    # Nitter
    for term in NITTER_SEARCHES:
        posts = scrape_nitter(term)
        all_posts.update(posts)
        sleep(0.5)

    os.makedirs("data", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        for post in sorted(all_posts):
            f.write(post + "\n")

    print(f"✅ Scraped {len(all_posts)} total posts → {SAVE_PATH}")


if __name__ == "__main__":
    run_signal_scraper()
