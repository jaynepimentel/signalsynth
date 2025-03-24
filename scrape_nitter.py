# scrape_nitter.py (Twitter/X search via Nitter frontend)
import requests
from bs4 import BeautifulSoup
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
NITTER_BASE = "https://nitter.privacydev.net"
SEARCH_TERMS = ["ebay trading cards", "funko vault", "ebay psa", "graded cards ebay"]
SAVE_PATH = "scraped_nitter_posts.txt"


def scrape_nitter(term):
    url = f"{NITTER_BASE}/search?f=tweets&q={term.replace(' ', '+')}"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    posts = []

    for tweet in soup.select(".timeline-item .tweet-content"):
        tweet_text = tweet.get_text(strip=True)
        if tweet_text and len(tweet_text) > 20:
            posts.append(f"[{term}] {tweet_text}")

    return posts


def run_nitter_scraper():
    all_posts = []
    for term in SEARCH_TERMS:
        try:
            posts = scrape_nitter(term)
            all_posts.extend(posts)
            time.sleep(1)
        except Exception as e:
            print(f"Error scraping '{term}': {e}")

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        for post in all_posts:
            f.write(post + "\n")

    print(f"✅ Scraped {len(all_posts)} Nitter/X posts → {SAVE_PATH}")


if __name__ == "__main__":
    run_nitter_scraper()
