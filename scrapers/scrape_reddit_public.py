# scrape_reddit_public.py
import requests
from bs4 import BeautifulSoup
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

SUBREDDITS = [
    "baseballcards", "pokemonTCG", "MagicTCG", "FunkoPop", "coins", "tradingcards"
]
KEYWORDS = ["ebay", "vault", "graded", "PSA"]
SAVE_PATH = "scraped_reddit_posts.txt"


def scrape_reddit(subreddit, keyword):
    url = f"https://old.reddit.com/r/{subreddit}/search?q={keyword}&restrict_sr=1&sort=new"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    posts = []

    for post in soup.select(".search-result"):  # standard result container
        title = post.select_one("a.search-title")
        if title:
            text = title.get_text(strip=True)
            link = title['href']
            posts.append(f"[{subreddit}] {text} → {link}")

    return posts


def run_reddit_scraper():
    all_posts = []
    for sub in SUBREDDITS:
        for kw in KEYWORDS:
            try:
                posts = scrape_reddit(sub, kw)
                all_posts.extend(posts)
                time.sleep(1)  # Be nice to Reddit
            except Exception as e:
                print(f"Error scraping {sub} | {kw}: {e}")

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        for post in all_posts:
            f.write(post + "\n")

    print(f"✅ Scraped {len(all_posts)} Reddit posts to {SAVE_PATH}")


if __name__ == "__main__":
    run_reddit_scraper()
