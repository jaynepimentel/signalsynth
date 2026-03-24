#!/usr/bin/env python3
"""
generate_pm_suggestions.py - Generate PM suggestions for all insights using OpenAI

Usage:
    1. Set your OPENAI_API_KEY environment variable or add it to .env
    2. Run: python generate_pm_suggestions.py
    
This will:
- Read insights from precomputed_insights.json
- Generate PM suggestions using GPT-4o-mini
- Save results to gpt_suggestion_cache.json
"""

import os
import json
import hashlib
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

load_dotenv()
load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)

# Config
INSIGHTS_PATH = "precomputed_insights.json"
CACHE_PATH = "gpt_suggestion_cache.json"
MODEL = os.getenv("OPENAI_MODEL_SCREENER", "gpt-4o-mini")  # Use a valid model
MAX_INSIGHTS = None  # Set to a number (e.g., 50) to limit for testing


def load_cache():
    """Load existing cache to avoid regenerating suggestions."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    """Save cache to disk."""
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def get_cache_key(text, brand="eBay"):
    """Generate cache key matching the existing format."""
    return hashlib.md5(f"{text}_{brand}".encode()).hexdigest()


def is_valid_suggestion(ideas):
    """Check if suggestions are valid (not empty or disabled)."""
    if not ideas:
        return False
    for idea in ideas:
        if isinstance(idea, str) and idea.strip() and not idea.startswith("[LLM disabled]"):
            return True
    return False


def generate_pm_ideas(client, text, brand="eBay"):
    """Generate PM suggestions using OpenAI."""
    prompt = (
        "You are a senior PM at a marketplace like eBay.\n"
        "Generate 3 concise, concrete product suggestions to improve trust or conversion.\n"
        "Format each as a numbered list with a bold title and brief description.\n\n"
        f"User Feedback:\n{text[:2000]}\n\nBrand: {brand}"
    )
    
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Generate actionable, concrete product improvement ideas."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        ideas = resp.choices[0].message.content or ""
        lines = [l.strip("-• ").strip() for l in ideas.split("\n") if l.strip()]
        return lines[:5] or [ideas]
    except Exception as e:
        print(f"  Error: {e}")
        return []


def main():
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not found!")
        print("\nTo set it:")
        print("  Option 1: Create a .env file with: OPENAI_API_KEY=sk-...")
        print("  Option 2: Set environment variable: $env:OPENAI_API_KEY='sk-...'")
        return
    
    print(f"[OK] OpenAI API key found")
    print(f"[INFO] Using model: {MODEL}")
    
    # Initialize client
    client = OpenAI(api_key=api_key)
    
    # Load insights
    if not os.path.exists(INSIGHTS_PATH):
        print(f"[ERROR] {INSIGHTS_PATH} not found!")
        return
    
    with open(INSIGHTS_PATH, "r", encoding="utf-8") as f:
        insights = json.load(f)
    
    print(f"[INFO] Loaded {len(insights)} insights")
    
    # Load existing cache
    cache = load_cache()
    print(f"[INFO] Existing cache has {len(cache)} entries")
    
    # Find insights that need suggestions
    to_generate = []
    for insight in insights:
        text = insight.get("text", "")
        brand = insight.get("target_brand", "eBay")
        key = get_cache_key(text, brand)
        
        # Skip if already has valid suggestions
        if key in cache and is_valid_suggestion(cache[key]):
            continue
        
        to_generate.append((key, text, brand))
    
    if MAX_INSIGHTS:
        to_generate = to_generate[:MAX_INSIGHTS]
    
    print(f"[INFO] Need to generate suggestions for {len(to_generate)} insights")
    
    if not to_generate:
        print("[OK] All insights already have valid suggestions!")
        return
    
    # Generate suggestions
    generated = 0
    failed = 0
    
    for key, text, brand in tqdm(to_generate, desc="Generating PM suggestions"):
        ideas = generate_pm_ideas(client, text, brand)
        
        if ideas and is_valid_suggestion(ideas):
            cache[key] = ideas
            generated += 1
        else:
            failed += 1
        
        # Save cache periodically
        if generated % 10 == 0:
            save_cache(cache)
    
    # Final save
    save_cache(cache)
    
    print(f"\n[DONE]")
    print(f"   Generated: {generated}")
    print(f"   Failed: {failed}")
    print(f"   Total in cache: {len(cache)}")


if __name__ == "__main__":
    main()
