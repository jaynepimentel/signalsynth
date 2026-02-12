# scrape_twitter.py - Twitter/X scraper (no login / no API key)
# Strategy priority:
#   1. Syndication API  (curated account timelines - proven working)
#   2. Guest-token v1.1 REST search
#   3. Guest-token adaptive search v2
#   4. Nitter / mirror-site HTML scraping
import requests
import json
import os
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup

SEARCH_TERMS = [
    "ebay price guide", "ebay price guide cards", "ebay card value",
    "ebay scan to price", "ebay vault", "ebay vault review",
    "ebay authentication", "ebay authenticity guarantee",
    "psa grading turnaround", "bgs grading", "cgc grading",
    "ebay trading cards", "ebay psa graded", "graded card ebay",
    "pokemon card value", "sports card value",
    "ebay managed payments", "ebay payout delay",
    "ebay shipping problem", "ebay refund",
    "funko pop ebay", "coin collecting ebay", "sneaker resell ebay",
]

CURATED_ACCOUNTS = [
    "eBay", "eBayNewsroom", "AskeBay", "eBayForBusiness",
    "PSAcard", "BGSgrading", "CGCComics", "SGCgrading",
    "GoldCardAuctions", "CardPurchaser", "PokemonTCG",
    "ToppsCards", "PaniniAmerica", "UpperDeckCards",
    "OriginalFunko", "Collectors", "HotWheelsOfficial",
    "Mercari", "Poshmark",
]

SAVE_PATH = "data/scraped_twitter_posts.json"

BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

NITTER_INSTANCES = [
    "https://xcancel.com",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.woodland.cafe",
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _parse_twitter_date(raw):
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _make_post(text, username, tweet_id, post_date, query, raw_tw=None):
    raw_tw = raw_tw or {}
    return {
        "text": text,
        "source": "Twitter/X",
        "search_term": query,
        "username": username,
        "url": "https://x.com/{}/status/{}".format(username, tweet_id) if tweet_id else "",
        "post_date": post_date,
        "_logged_date": datetime.now().isoformat(),
        "retweet_count": raw_tw.get("retweet_count", 0),
        "favorite_count": raw_tw.get("favorite_count", 0),
    }


# ===================================================================
# Strategy 1 - Twitter Syndication API (curated accounts)
# ===================================================================
class SyndicationScraper:
    TIMELINE_URL = (
        "https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml",
        })
        self._consecutive_429 = 0

    @property
    def is_rate_limited(self):
        return self._consecutive_429 >= 2

    def user_timeline(self, username, max_retries=2):
        if self.is_rate_limited:
            return []
        for attempt in range(max_retries):
            try:
                r = self.session.get(
                    self.TIMELINE_URL.format(username=username), timeout=15,
                )
                if r.status_code == 200:
                    self._consecutive_429 = 0
                    return self._parse(r.text, username)
                if r.status_code == 429:
                    self._consecutive_429 += 1
                    if self.is_rate_limited:
                        print("    [syndication] rate-limited, skipping remaining")
                        return []
                    wait = 15 * (attempt + 1)
                    print("    [syndication] @{} 429, waiting {}s".format(username, wait))
                    time.sleep(wait)
                    continue
                print("    [syndication] @{} HTTP {}".format(username, r.status_code))
                break
            except Exception as e:
                print("    [syndication] @{} error: {}".format(username, e))
                break
        return []

    def _parse(self, html, username):
        posts = []
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return posts
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            return posts
        entries = (
            data.get("props", {})
            .get("pageProps", {})
            .get("timeline", {})
            .get("entries", [])
        )
        for entry in entries:
            try:
                if entry.get("type") != "tweet":
                    continue
                tw = entry.get("content", {}).get("tweet", {})
                text = tw.get("full_text") or tw.get("text", "")
                if len(text) < 20:
                    continue
                user = tw.get("user", {})
                screen_name = user.get("screen_name", username)
                tweet_id = tw.get("id_str", str(tw.get("id", "")))
                post_date = _parse_twitter_date(tw.get("created_at", ""))
                posts.append(_make_post(
                    text, screen_name, tweet_id, post_date,
                    "@{}".format(username), tw,
                ))
            except Exception:
                continue
        return posts


# ===================================================================
# Strategy 2 & 3 - Guest-token Twitter API
# ===================================================================
class GuestTokenScraper:
    def __init__(self):
        self.session = requests.Session()
        self.guest_token = None
        self.session.headers.update({
            "Authorization": "Bearer " + BEARER_TOKEN,
            "User-Agent": _UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def _activate(self):
        try:
            r = self.session.post(
                "https://api.twitter.com/1.1/guest/activate.json", timeout=10
            )
            if r.status_code == 200:
                self.guest_token = r.json().get("guest_token")
                self.session.headers["x-guest-token"] = self.guest_token
                return True
        except Exception:
            pass
        return False

    def search_v1(self, query, count=20):
        if not self.guest_token and not self._activate():
            return []
        try:
            r = self.session.get(
                "https://api.twitter.com/1.1/search/tweets.json",
                params={"q": query, "result_type": "recent", "count": count, "tweet_mode": "extended"},
                timeout=15,
            )
            if r.status_code == 200:
                posts = []
                for tw in r.json().get("statuses", []):
                    text = tw.get("full_text") or tw.get("text", "")
                    if len(text) < 20:
                        continue
                    user = tw.get("user", {})
                    posts.append(_make_post(
                        text, user.get("screen_name", "unknown"),
                        tw.get("id_str", ""),
                        _parse_twitter_date(tw.get("created_at", "")),
                        query, tw,
                    ))
                return posts
        except Exception:
            pass
        return []

    def search_adaptive(self, query, count=20):
        if not self.guest_token and not self._activate():
            return []
        try:
            r = self.session.get(
                "https://api.twitter.com/2/search/adaptive.json",
                params={"q": query, "count": count, "query_source": "typed_query", "pc": "1"},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                tweets = data.get("globalObjects", {}).get("tweets", {})
                users = data.get("globalObjects", {}).get("users", {})
                posts = []
                for tid, tw in tweets.items():
                    text = tw.get("full_text") or tw.get("text", "")
                    if len(text) < 20:
                        continue
                    uid = tw.get("user_id_str", "")
                    user = users.get(uid, {})
                    posts.append(_make_post(
                        text, user.get("screen_name", "unknown"),
                        tid, _parse_twitter_date(tw.get("created_at", "")),
                        query, tw,
                    ))
                return posts
        except Exception:
            pass
        return []


# ===================================================================
# Strategy 4 - Nitter / mirror HTML scraping
# ===================================================================
class NitterScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA})
        self.base_url = None

    def _find_instance(self):
        for url in NITTER_INSTANCES:
            try:
                r = self.session.get(url, timeout=8, allow_redirects=True)
                if r.status_code == 200:
                    self.base_url = url.rstrip("/")
                    return True
            except Exception:
                continue
        return False

    def search(self, query):
        if not self.base_url and not self._find_instance():
            return []
        try:
            r = self.session.get(
                self.base_url + "/search",
                params={"f": "tweets", "q": query}, timeout=15,
            )
            if r.status_code == 200:
                return self._parse_html(r.text, query)
        except Exception:
            pass
        return []

    def user_timeline(self, username):
        if not self.base_url and not self._find_instance():
            return []
        try:
            r = self.session.get(self.base_url + "/" + username, timeout=15)
            if r.status_code == 200:
                return self._parse_html(r.text, username)
        except Exception:
            pass
        return []

    def _parse_html(self, html, query):
        posts = []
        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".timeline-item"):
            try:
                body = item.select_one(".tweet-content, .tweet-body")
                if not body:
                    continue
                text = body.get_text(separator=" ", strip=True)
                if len(text) < 20:
                    continue
                username = "unknown"
                link_el = item.select_one("a.username")
                if link_el:
                    username = link_el.get_text(strip=True).lstrip("@")
                tweet_link = item.select_one("a.tweet-link")
                tweet_url, tweet_id = "", ""
                if tweet_link:
                    href = tweet_link.get("href", "")
                    tweet_url = ("https://x.com" + href) if href.startswith("/") else href
                    m = re.search(r"/status/(\d+)", href)
                    if m:
                        tweet_id = m.group(1)
                posts.append({
                    "text": text,
                    "source": "Twitter/X",
                    "search_term": query,
                    "username": username,
                    "url": tweet_url,
                    "post_date": datetime.now().strftime("%Y-%m-%d"),
                    "_logged_date": datetime.now().isoformat(),
                    "retweet_count": 0,
                    "favorite_count": 0,
                })
            except Exception:
                continue
        return posts


# ===================================================================
# Orchestrator
# ===================================================================
def run_twitter_scraper():
    """Run all strategies in priority order and merge results."""
    print("Starting Twitter/X scraper (multi-strategy, no login)...")
    all_posts = []

    # Strategy 1: Syndication API (curated accounts)
    print("\n  [syndication] Fetching curated account timelines...")
    synd = SyndicationScraper()
    for acct in CURATED_ACCOUNTS:
        print("  @{} ...".format(acct))
        posts = synd.user_timeline(acct)
        if posts:
            print("    got {} tweets".format(len(posts)))
            all_posts.extend(posts)
        if synd.is_rate_limited:
            break
        time.sleep(4)

    # Strategy 2 & 3: Guest-token API search
    print("\n  [guest-token] Trying API search...")
    guest = GuestTokenScraper()
    for term in SEARCH_TERMS:
        posts = guest.search_v1(term, count=20)
        if not posts:
            posts = guest.search_adaptive(term, count=20)
        if posts:
            print("    '{}': {} tweets".format(term, len(posts)))
            all_posts.extend(posts)
        time.sleep(1.5)

    # Strategy 4: Nitter mirrors (last resort)
    if not all_posts:
        print("\n  [nitter] Trying Nitter mirrors...")
        nitter = NitterScraper()
        for term in SEARCH_TERMS:
            posts = nitter.search(term)
            if posts:
                all_posts.extend(posts)
            time.sleep(2)
        for acct in CURATED_ACCOUNTS:
            posts = nitter.user_timeline(acct)
            if posts:
                all_posts.extend(posts)
            time.sleep(1.5)

    # Merge with existing data (preserve previous successful runs)
    existing = []
    if os.path.exists(SAVE_PATH):
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            print("  Loaded {} existing tweets from cache".format(len(existing)))
        except Exception:
            existing = []

    merged = existing + all_posts
    if not merged:
        print("\nNo tweets obtained from any strategy (and no cached data).")
        return []

    # Deduplicate & save
    seen = set()
    unique_posts = []
    for post in merged:
        key = post["text"][:120].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_posts.append(post)

    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)

    new_count = len(unique_posts) - len(existing)
    print("\nSaved {} unique tweets ({} new) -> {}".format(
        len(unique_posts), max(new_count, 0), SAVE_PATH
    ))
    return unique_posts


if __name__ == "__main__":
    run_twitter_scraper()
