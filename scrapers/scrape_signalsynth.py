# scrape_signalsynth.py — cleaner logic, filtered for relevant marketplace content
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
SAVE_PATH = "scraped_community_posts.txt"

COMMUNITY_FORUMS = {
    "Buying-Selling": "https://community.ebay.com/t5/Buying-Selling/ct-p/buying-selling-db",
    "Collectibles-Art": "https://community.ebay.com/t5/Collectibles-Art/bd-p/29"
}

REDDIT_SUBREDDITS = ["tradingcards", "pokemonTCG", "MagicTCG", "baseballcards", "ebay"]
REDDIT_TERMS = [
    "ebay vault", "fanatics live", "fanatics authentication", "alt marketplace",
    "whatnot shipping", "psa ebay", "grading", "authentication", "return", "delay", "scam"
]

# 🔍 Filters out generic or irrelevant posts
def is_relevant(text):
    keywords = [
        "ebay", "vault", "grading", "psa", "fanatics", "authentication", "return",
        "whatnot", "alt marketplace", "delay", "refund", "cut", "fees", "fake"
    ]
    text = text.lower()
    return any(k in text for k in keywords) and len(text) > 30

def scrape_ebay_forum(name, url):
    try:
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        posts = []
        for thread in soup.select(".lia-link-navigation"):
            title = thread.get_text(strip=True)
            if title and is_relevant(title):
                posts.append(f"[eBay - {name}] {title}")
        return posts
    except Exception as e:
        print(f"❌ eBay forum error: {name} | {e}")
        return []

def scrape_reddit_search(term, subreddit):
    url = f"https://old.reddit.com/r/{subreddit}/search?q={term.replace(' ', '+')}&restrict_sr=1&sort=new"
    try:
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        posts = []
        for post in soup.select(".search-title"):
            text = post.get_text(strip=True)
            if text and is_relevant(text):
                posts.append(f"[Reddit - {subreddit}] {term}: {text}")
        return posts
    except Exception as e:
        print(f"❌ Reddit search error for '{term}' in r/{subreddit} | {e}")
        return []

def run_signal_scraper():
    all_posts = []

    # ✅ Scrape eBay forums
    for name, url in COMMUNITY_FORUMS.items():
        all_posts.extend(scrape_ebay_forum(name, url))

    # ✅ Scrape Reddit with multiple terms
    for subreddit in REDDIT_SUBREDDITS:
        for term in REDDIT_TERMS:
            all_posts.extend(scrape_reddit_search(term, subreddit))

    # ✅ Save filtered posts
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        for post in all_posts:
            f.write(post + "\n")

    print(f"✅ Scraped {len(all_posts)} high-signal posts → {SAVE_PATH}")

if __name__ == "__main__":
    run_signal_scraper()
