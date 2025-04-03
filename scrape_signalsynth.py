# scrape_signalsynth.py — full rewritten version with eBay Dev Ecosystem tracking, Reddit, Twitter, and eBay Forums

import os
import requests
import warnings
import json
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from sentence_transformers import SentenceTransformer, util
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

SAVE_PATH = "data/scraped_community_posts.json"
NOW = datetime.now(timezone.utc)

REDDIT_SUBREDDITS = [
    "ebay", "tradingcards", "baseballcards", "pokemonTCG", "WhatnotApp",
    "sportscards", "fanatics", "tiktokshopping", "magicTCG", "sportsmemorabilia",
    "footballcards", "basketballcards", "hobbytalk", "boxbreaks",
    "api", "learnprogramming", "programming", "webdev", "developers"
]

REDDIT_TERMS = [
    # Core + Collectibles + Dev
    "ebay", "grading", "authentication", "vault", "live stream", "ebay live",
    "case break", "box break", "fanatics live", "whatnot", "scan to list",
    "goldin auctions", "goldin", "heritage auction", "elite auction", "pwcc",
    "slabs", "population report", "ebay price guide", "grading add-on",
    "psa partnership", "ebay psa grading", "psa grading services",
    "grading powered by psa", "vault to grading", "grading integration",
    "authenticity guarantee",
    # Developer Ecosystem
    "ebay api", "ebay developer program", "ebay sdk", "ebay graphql",
    "ebay sell feed", "ebay auth token", "ebay api down", "ebay dev bug",
    "ebay partner integration", "ebay api rate limit", "ebay api docs"
]

COMMUNITY_FORUMS = {
    "Buying-Selling": "https://community.ebay.com/t5/Buying-Selling/ct-p/buying-selling-db",
    "Collectibles-Art": "https://community.ebay.com/t5/Collectibles-Art/bd-p/29",
    "Shipping": "https://community.ebay.com/t5/Shipping/bd-p/215",
    "Returns-Cancellations": "https://community.ebay.com/t5/Returns-Cancellations/bd-p/210",
    "Selling": "https://community.ebay.com/t5/Selling/bd-p/Selling"
}

TWITTER_TERMS = [
    # Core + Dev
    "(ebay OR #ebay OR 'ebay live' OR #ebaylive)",
    "(grading OR #grading OR psa OR #psa)",
    "(vault OR 'ebay vault' OR #ebayvault)",
    "(goldin OR #goldin OR 'goldin auctions')",
    "(fanatics OR #fanatics OR 'fanatics live')",
    "(authentication OR authentic OR #authentication)",
    "(consignment OR 'auction house' OR pwcc OR heritage OR elite)",
    "(case break OR casebreak OR #casebreaks)",
    "(ebay api OR 'ebay developer' OR 'ebay sdk' OR 'ebay graphql')",
    "(ebay rate limit OR 'api key' OR 'developer issue')"
]

model = SentenceTransformer('all-MiniLM-L6-v2')
query_embedding = model.encode("grading issues, ebay live problems, goldin vs ebay, vault authentication, psa, consignment problems, comc, collectible refund, platform migration, case break, live shopping, ebay api issues, developer bugs, sdk integration")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def is_case_break(text):
    return any(kw in text.lower() for kw in ["case break", "live break", "box break"])

def is_live_shopping(text):
    return any(kw in text.lower() for kw in ["ebay live", "fanatics live", "livestream", "live shopping"])

def is_dev_feedback(text):
    return any(kw in text.lower() for kw in ["ebay api", "developer.ebay", "api.ebay", "dev.ebay", "ebay sdk", "rate limit", "auth token", "graphql", "sell feed", "integration issue"])

def is_semantically_relevant(text):
    embedding = model.encode(text, convert_to_tensor=True)
    score = util.cos_sim(query_embedding, embedding)[0].item()
    return score > 0.3

def is_gpt_relevant(text):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Is this post relevant to eBay Collectibles, eBay Live, PSA, COMC, Goldin, or competitors like Whatnot, Fanatics, Loupe, Heritage, or TikTok Shopping — OR to eBay developer APIs, SDKs, integration issues, auth tokens, rate limits, or ecosystem tools? Yes or No:\n{text}"}],
            temperature=0,
            max_tokens=5
        )
        return "yes" in response.choices[0].message.content.lower()
    except:
        return False

def classify_persona(text):
    text = text.lower()
    if is_dev_feedback(text):
        return "Developer"
    if any(w in text for w in ["bought", "paid", "acquired", "investment"]):
        return "Buyer"
    if any(w in text for w in ["sold", "selling", "listed", "consigned"]):
        return "Seller"
    return "General"

def run_snscrape_search(query, max_results=50):
    import subprocess
    query_with_date = f"{query} since:{(datetime.now() - timedelta(days=300)).date()} until:{datetime.now().date()}"
    command = f'python -m snscrape --max-results {max_results} twitter-search "{query_with_date}"'
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True, timeout=30)
        lines = result.stdout.strip().split("\n")
        return [line.strip() for line in lines if line.strip()]
    except Exception as e:
        print(f"[ERROR] Twitter scrape failed for '{query}': {e}")
        return []

def scrape_reddit_post_detail(post_url):
    try:
        res = requests.get(post_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.select_one(".title").text.strip() if soup.select_one(".title") else ""
        body_el = soup.select_one(".expando")
        body = body_el.get_text(strip=True) if body_el else ""
        author_el = soup.select_one(".author")
        author = author_el.text.strip() if author_el else "[deleted]"
        timestamp_el = soup.select_one("time")
        timestamp = timestamp_el['datetime'] if timestamp_el and 'datetime' in timestamp_el.attrs else None
        post_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).date() if timestamp else NOW.date()
        age_days = (NOW.date() - post_date).days
        comments = [c.get_text(strip=True) for c in soup.select(".comment .md")[:3] if len(c.get_text(strip=True)) > 10]
        text = title + "\n" + body
        return {
            "text": text,
            "url": post_url,
            "source": "Reddit",
            "post_date": post_date.isoformat(),
            "_logged_date": NOW.date().isoformat(),
            "post_age_days": age_days,
            "author": author,
            "author_karma": None,
            "comment_count": len(comments),
            "top_comments": comments,
            "is_case_break": is_case_break(text),
            "is_live_shopping": is_live_shopping(text),
            "is_dev_feedback": is_dev_feedback(text),
            "persona": classify_persona(text)
        }
    except Exception as e:
        print(f"[Error parsing {post_url}] {e}")
        return None

def scrape_reddit_html(limit=100):
    posts = []
    for sub in REDDIT_SUBREDDITS:
        for term in REDDIT_TERMS:
            url = f"https://old.reddit.com/r/{sub}/search?q={term}&restrict_sr=on&sort=new"
            try:
                res = requests.get(url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(res.text, "html.parser")
                for link in soup.select(".search-result a[data-click-id='body']")[:5]:
                    href = link.get("href")
                    if href and href.startswith("https://old.reddit.com/r/"):
                        post = scrape_reddit_post_detail(href)
                        if post:
                            posts.append(post)
                    if len(posts) >= limit:
                        return posts
            except Exception as e:
                print(f"[Reddit HTML error] {e}")
            time.sleep(1.5)
    return posts

def extract_post_date(timestamp):
    try:
        return datetime.fromisoformat(timestamp).date().isoformat() if timestamp else None
    except:
        return None

def scrape_forum_post_body(url):
    try:
        res = requests.get(f"https://community.ebay.com{url}", headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")
        body = soup.select_one(".lia-message-body")
        time_tag = soup.find("time")
        timestamp = time_tag["datetime"] if time_tag and time_tag.has_attr("datetime") else None
        post_date = extract_post_date(timestamp)
        return {
            "body": body.get_text(strip=True) if body else "",
            "timestamp": timestamp,
            "post_date": post_date
        }
    except:
        return {
            "body": "",
            "timestamp": None,
            "post_date": None
        }

def scrape_ebay_forum(category, base_url, max_pages=2):
    results = []
    try:
        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}"
            res = requests.get(url, headers=HEADERS)
            soup = BeautifulSoup(res.text, "html.parser")
            threads = soup.select(".message-subject a")
            for thread in threads:
                href = thread.get("href")
                if href:
                    post = scrape_forum_post_body(href)
                    if post["body"]:
                        results.append({
                            "text": post["body"],
                            "url": f"https://community.ebay.com{href}",
                            "source": "eBay Forums",
                            "_logged_at": NOW.isoformat(),
                            "_logged_date": NOW.date().isoformat(),
                            "post_date": post["post_date"],
                            "persona": classify_persona(post["body"]),
                            "is_dev_feedback": is_dev_feedback(post["body"]),
                            "_high_end_flag": is_high_end_signal(post["body"])
                        })
    except Exception as e:
        print(f"[ERROR] Failed to scrape eBay forum '{category}': {e}")
    return results

def run_signal_scraper():
    all_posts = []

    print("[INFO] Scraping eBay Community Forums...")
    for name, url in COMMUNITY_FORUMS.items():
        all_posts.extend(scrape_ebay_forum(name, url))

    print("[INFO] Scraping Reddit via HTML search...")
    all_posts.extend(scrape_reddit_html(limit=100))

    print("[INFO] Scraping Twitter via snscrape...")
    for term in TWITTER_TERMS:
        tweets = run_snscrape_search(term)
        print(f"[INFO] Found {len(tweets)} tweets for '{term}'")
        for tweet in tweets:
            if is_semantically_relevant(tweet) or is_gpt_relevant(tweet):
                all_posts.append({
                    "text": tweet,
                    "source": "Twitter",
                    "url": "https://x.com/search?q=" + requests.utils.quote(tweet[:50]),
                    "_logged_at": NOW.isoformat(),
                    "_logged_date": NOW.date().isoformat(),
                    "post_date": NOW.date().isoformat(),
                    "_high_end_flag": is_high_end_signal(tweet),
                    "is_dev_feedback": is_dev_feedback(tweet),
                    "persona": classify_persona(tweet)
                })

    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Saved {len(all_posts)} total high-signal posts.")
    print(f"[INFO] Twitter posts in final output: {len([p for p in all_posts if p['source'] == 'Twitter'])}")

if __name__ == "__main__":
    run_signal_scraper()
