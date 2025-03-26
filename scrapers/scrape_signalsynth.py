# scrape_signalsynth.py — generous signal scraper for eBay + competitors

import requests
from bs4 import BeautifulSoup
from scrape_twitter_cli import scrape_twitter_cli

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

SAVE_PATH = "scraped_community_posts.txt"
TWITTER_PATH = "scraped_twitter_posts.txt"

COMMUNITY_FORUMS = {
    "Buying-Selling": "https://community.ebay.com/t5/Buying-Selling/ct-p/buying-selling-db",
    "Collectibles-Art": "https://community.ebay.com/t5/Collectibles-Art/bd-p/29"
}

REDDIT_SUBREDDITS = ["ebay", "tradingcards", "baseballcards", "pokemonTCG"]

REDDIT_TERMS = [
    "ebay", "psa", "grading", "vault", "authentication", "authenticity guarantee",
    "fanatics", "whatnot", "alt", "goldin"
]

TWITTER_TERMS = [
    "ebay psa", "authenticity guarantee", "grading from ebay", "vault authentication",
    "psa submission", "grading delay", "return psa", "authentication ebay", "vault issues"
]


def is_relevant(text):
    text = text.lower()

    # Minimum text length to avoid junk
    if len(text) < 20:
        return False

    # Exclude obvious junk or listing posts
    noise_phrases = [
        "mail day", "just got this", "nfs", "not for sale", "bump", "buy/sell/trade", "price check"
    ]
    if any(phrase in text for phrase in noise_phrases):
        return False

    # If it mentions eBay, PSA, grading, or competitors — let it through
    keywords = [
        "ebay", "psa", "vault", "authenticity", "authentication", "grading", "fanatics", "whatnot", "alt", "goldin"
    ]
    return any(k in text for k in keywords)


def scrape_ebay_forum(name, url):
    try:
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")
        posts = []
        for thread in soup.select(".lia-link-navigation"):
            title = thread.get_text(strip=True)
            if title and is_relevant(title):
                posts.append(f"[eBay Forum - {name}] {title}")
        return posts
    except Exception as e:
        print(f"❌ Forum scrape error ({name}): {e}")
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
        print(f"❌ Reddit scrape error ({subreddit}/{term}): {e}")
        return []


def run_signal_scraper():
    all_posts = []
    twitter_posts = []

    print("🔍 Scraping eBay Community Forums...")
    for name, url in COMMUNITY_FORUMS.items():
        all_posts.extend(scrape_ebay_forum(name, url))

    print("🔍 Scraping Reddit...")
    for subreddit in REDDIT_SUBREDDITS:
        for term in REDDIT_TERMS:
            all_posts.extend(scrape_reddit_search(term, subreddit))

    print("🐦 Scraping Twitter via CLI...")
    for term in TWITTER_TERMS:
        tweets = scrape_twitter_cli(term)
        tweets = [t for t in tweets if is_relevant(t)]
        twitter_posts.extend(tweets)
        all_posts.extend(tweets)

    # Save results
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        for post in all_posts:
            f.write(post + "\n")

    with open(TWITTER_PATH, "w", encoding="utf-8") as f:
        for post in twitter_posts:
            f.write(post + "\n")

    print(f"\n✅ Saved {len(all_posts)} total high-signal posts.")
    print(f"🐦 Twitter-only: {len(twitter_posts)} posts saved to {TWITTER_PATH}")


if __name__ == "__main__":
    run_signal_scraper()
