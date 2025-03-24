# scrape_signalsynth.py — Nitter with failover support
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
SAVE_PATH = "scraped_community_posts.txt"

COMMUNITY_FORUMS = {
    "Buying-Selling": "https://community.ebay.com/t5/Buying-Selling/ct-p/buying-selling-db",
    "Collectibles-Art": "https://community.ebay.com/t5/Collectibles-Art/bd-p/29"
}

REDDIT_SEARCHES = {
    "Fanatics": ["baseballcards", "tradingcards", "pokemonTCG", "magicTCG"],
    "Collectibles": ["ebay"]
}

NITTER_SEARCHES = [
    "ebay live", "fanatics collect", "whatnot app", "alt marketplace", "loupe app",
    "psa ebay partnership", "grading add-on ebay", "ebay vault to psa", "psa integration with ebay",
    "ebay psa cert", "psa x ebay", "ebay vault turnaround time", "psa grading delay ebay"
]

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us"
]


def scrape_ebay_forum(name, url):
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    posts = []
    for thread in soup.select(".lia-link-navigation"):
        title = thread.get_text(strip=True)
        if title and len(title) > 10:
            posts.append(f"[eBay - {name}] {title}")
    return posts

def scrape_reddit_search(term, subreddit):
    url = f"https://old.reddit.com/r/{subreddit}/search?q={term.replace(' ', '+')}&restrict_sr=1&sort=new"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    posts = []
    for post in soup.select(".search-title"):
        text = post.get_text(strip=True)
        if text:
            posts.append(f"[Reddit - {subreddit}] {term}: {text}")
    return posts

def scrape_nitter():
    all_nitter_posts = []
    for term in NITTER_SEARCHES:
        success = False
        for base in NITTER_INSTANCES:
            try:
                url = f"{base}/search?f=tweets&q={term.replace(' ', '+')}"
                res = requests.get(url, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
                for tweet in soup.select(".timeline-item .tweet-content"):
                    tweet_text = tweet.get_text(strip=True)
                    if tweet_text and len(tweet_text) > 20:
                        all_nitter_posts.append(f"[Twitter] {term}: {tweet_text}")
                success = True
                break  # exit instance loop if successful
            except Exception as e:
                print(f"Retrying Nitter search '{term}' on next instance...")
        if not success:
            print(f"❌ All Nitter instances failed for: {term}")
    return all_nitter_posts

def run_signal_scraper():
    all_posts = []

    for name, url in COMMUNITY_FORUMS.items():
        try:
            posts = scrape_ebay_forum(name, url)
            all_posts.extend(posts)
        except Exception as e:
            print(f"Error scraping eBay {name}: {e}")

    for sub in REDDIT_SEARCHES["Fanatics"]:
        try:
            fanatics_posts = scrape_reddit_search("fanatics", sub)
            all_posts.extend(fanatics_posts)
        except Exception as e:
            print(f"Error scraping Fanatics from r/{sub}: {e}")

    try:
        ebay_collectibles = scrape_reddit_search("collectibles OR trading cards", "ebay")
        all_posts.extend(ebay_collectibles)
    except Exception as e:
        print("Error scraping filtered eBay subreddit:", e)

    all_posts.extend(scrape_nitter())

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        for post in all_posts:
            f.write(post + "\n")

    print(f"✅ Scraped {len(all_posts)} total posts → {SAVE_PATH}")

if __name__ == "__main__":
    run_signal_scraper()
