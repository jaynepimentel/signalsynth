# ai_suggester.py — OpenAI-safe with Streamlit compatibility and improved error handling

import os
import json
import hashlib
from dotenv import load_dotenv

# Load env vars (safe in Streamlit too)
load_dotenv()

# Try importing OpenAI client
try:
    from openai import OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception as e:
    client = None
    OPENAI_API_KEY = None

# System prompt for product strategy insight generation
system_prompt = """
You are a senior product manager at a major marketplace platform like eBay or Fanatics. 
Based on user feedback, identify the customer's concern and recommend specific, strategic 
product improvements or operational actions. Focus on things that would build trust, improve
conversion, or reduce friction. Use strong PM thinking.
"""

CACHE_PATH = "gpt_suggestion_cache.json"

# Load existing cache
try:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            suggestion_cache = json.load(f)
    else:
        suggestion_cache = {}
except Exception:
    suggestion_cache = {}  # fallback to empty if cache is corrupt


def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(text.strip().encode()).hexdigest()

    # Serve from cache
    if key in suggestion_cache:
        return suggestion_cache[key]

    # No key set
    if not OPENAI_API_KEY or not client:
        return ["[⚠️ No OpenAI API key set — using fallback suggestion]"]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Feedback from user:\n{text}\n\nBrand mentioned: {brand}"}
            ],
            temperature=0.3,
            max_tokens=300
        )

        raw_output = response.choices[0].message.content.strip()
        lines = raw_output.split("\n")
        suggestions = [line.strip("-• ").strip() for line in lines if line.strip()]
        suggestion_cache[key] = suggestions

        # Write to cache safely
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(suggestion_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            suggestions.append(f"[⚠️ Could not save to cache: {e}]")

        return suggestions

    except Exception as e:
        # Friendly error messaging
        msg = str(e).lower()
        if "429" in msg or "rate limit" in msg:
            return ["[⚠️ OpenAI rate limit hit — retry later or reduce load]"]
        elif "authentication" in msg or "key" in msg:
            return ["[⚠️ Invalid or missing OpenAI API key]"]
        else:
            return [f"[❌ GPT error: {str(e)}]"]
