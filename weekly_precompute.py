#!/usr/bin/env python3
"""
Weekly precompute job for SignalSynth.

Runs all scrapers, scores/enriches posts, and generates cached clusters.
Schedule this to run once a week so the app loads quickly with everything
except document generation already cached.

Usage:
    python weekly_precompute.py
    python weekly_precompute.py --skip-scrape    # only re-process + re-cluster existing data
    python weekly_precompute.py --no-twitter      # skip Twitter scraper
    python weekly_precompute.py --no-reddit       # skip Reddit scraper
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def run_step(description, cmd, cwd=None):
    """Run a subprocess step, stream output, return success bool."""
    log(f">> {description}")
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=False,
            text=True,
        )
        elapsed = round(time.time() - start, 1)
        if result.returncode == 0:
            log(f"   Done ({elapsed}s)")
            return True
        else:
            log(f"   FAILED (exit {result.returncode}, {elapsed}s)")
            return False
    except Exception as e:
        log(f"   ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="SignalSynth weekly precompute job")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping, only re-process existing data")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit scraper")
    parser.add_argument("--no-bluesky", action="store_true", help="Skip Bluesky scraper")
    parser.add_argument("--no-ebay", action="store_true", help="Skip eBay Forums scraper")
    parser.add_argument("--no-twitter", action="store_true", help="Skip Twitter/X scraper")
    parser.add_argument("--no-cllct", action="store_true", help="Skip Cllct.com scraper")
    parser.add_argument("--no-news-rss", action="store_true", help="Skip RSS news feeds scraper")
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)

    log("=" * 60)
    log("SIGNALSYNTH WEEKLY PRECOMPUTE JOB")
    log("=" * 60)

    py = sys.executable
    results = {}

    # ── Step 1: Scrape all sources ─────────────────────────────
    if not args.skip_scrape:
        scrape_cmd = [py, "-m", "utils.scrape_all"]
        if args.no_reddit:
            scrape_cmd.append("--no-reddit")
        if args.no_bluesky:
            scrape_cmd.append("--no-bluesky")
        if args.no_ebay:
            scrape_cmd.append("--no-ebay")
        if args.no_twitter:
            scrape_cmd.append("--no-twitter")
        if args.no_cllct:
            scrape_cmd.append("--no-cllct")
        if args.no_news_rss:
            scrape_cmd.append("--no-news-rss")

        results["scrape"] = run_step(
            "Step 1/3: Scraping all sources",
            scrape_cmd,
        )
    else:
        log(">> Step 1/3: SKIPPED (--skip-scrape)")
        results["scrape"] = True

    # ── Step 2: Score & enrich ─────────────────────────────────
    results["enrich"] = run_step(
        "Step 2/3: Scoring & enriching (quick_process.py)",
        [py, "quick_process.py"],
    )

    # ── Step 3: Cluster ────────────────────────────────────────
    if results["enrich"]:
        results["cluster"] = run_step(
            "Step 3/3: Generating clusters (precompute_clusters.py)",
            [py, "precompute_clusters.py"],
        )
    else:
        log(">> Step 3/3: SKIPPED (enrichment failed)")
        results["cluster"] = False

    # ── Summary ────────────────────────────────────────────────
    log("")
    log("=" * 60)
    log("JOB SUMMARY")
    log("=" * 60)
    for step, ok in results.items():
        status = "OK" if ok else "FAILED"
        log(f"  {step}: {status}")

    # Show cached file sizes
    cached_files = [
        "data/all_scraped_posts.json",
        "data/scraped_reddit_posts.json",
        "data/scraped_bluesky_posts.json",
        "data/scraped_competitor_posts.json",
        "data/scraped_twitter_posts.json",
        "data/scraped_cllct_posts.json",
        "data/scraped_news_rss_posts.json",
        "precomputed_insights.json",
        "precomputed_clusters.json",
    ]
    log("")
    log("Cached files:")
    for f in cached_files:
        fp = os.path.join(PROJECT_ROOT, f)
        if os.path.exists(fp):
            size_kb = round(os.path.getsize(fp) / 1024, 1)
            log(f"  {f}: {size_kb} KB")
        else:
            log(f"  {f}: (missing)")

    all_ok = all(results.values())
    log("")
    log("RESULT: " + ("ALL STEPS PASSED" if all_ok else "SOME STEPS FAILED"))
    log("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
