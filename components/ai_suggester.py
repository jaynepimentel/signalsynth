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


def generate_pm_ideas(text, brand="eBay", sentiment="Neutral"):
    key = hashlib.md5(f"{text}_{brand}_{sentiment}".strip().encode()).hexdigest()

    if key in suggestion_cache:
        print(f"✅ Loaded from cache: {text[:80]}")
        return suggestion_cache[key]

    if not OPENAI_API_KEY or not client:
        print("❌ GPT skipped: missing key or client.")
        return ["[⚠️ No OpenAI API key set — using fallback suggestion]"]

    # Choose prompt dynamically
    brand_lower = brand.lower()
    sentiment_lower = sentiment.lower()

    competitors = ["whatnot", "fanatics", "alt", "loupe", "psa", "goldin"]

    if brand_lower in [c.lower() for c in competitors] and sentiment_lower == "complaint":
        dynamic_prompt = f"""
You are a senior product strategist at eBay.

A user is complaining about a competing platform: {brand}.
Your job is to identify their pain point and recommend bold, customer-centric product improvements
that would allow eBay to differentiate and win over users from {brand}.

Make sure your ideas reflect smart strategy, competitive positioning, and a deep understanding of trust, conversion, or retention.
"""
    else:
        dynamic_prompt = """
You are a senior product manager at a major marketplace platform like eBay or Fanatics. 
Based on user feedback, identify the customer's concern and recommend specific, strategic 
product improvements or operational actions. Focus on things that would build trust, improve
conversion, or reduce friction. Use strong PM thinking.
"""

    try:
        print(f"💬 Calling GPT for: {text[:80]}")

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": dynamic_prompt},
                {"role": "user", "content": f"Feedback from user:\n{text}\n\nBrand mentioned: {brand}"}
            ],
            temperature=0.3,
            max_tokens=400
        )

        raw_output = response.choices[0].message.content.strip()
        lines = raw_output.split("\n")
        suggestions = [line.strip("-• ").strip() for line in lines if line.strip()]
        suggestion_cache[key] = suggestions

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2, ensure_ascii=False)

        return suggestions

    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "rate limit" in msg:
            return ["[⚠️ OpenAI rate limit hit — retry later or reduce load]"]
        elif "authentication" in msg or "key" in msg:
            return ["[⚠️ Invalid or missing OpenAI API key]"]
        else:
            return [f"[❌ GPT error: {str(e)}]"]
def classify_insight_type(text):
    prompt = """
Classify this user insight into one of the following types:
- Complaint
- Confusion
- Feature Request
- Marketplace Chatter
- Discussion

Respond only with the type and a 1-line reason.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.2,
            max_tokens=100
        )
        reply = response.choices[0].message.content.strip().lower()

        for tag in ["complaint", "confusion", "feature request", "marketplace chatter", "discussion"]:
            if tag in reply:
                return tag.title(), 90, reply
        return "Discussion", 70, "Defaulted to Discussion"

    except Exception as e:
        return "Discussion", 60, f"GPT error: {str(e)}"


def classify_persona(text):
    prompt = """
Determine whether this user is acting as a:
- Buyer
- Seller
- Both (Buyer & Seller)
- Unknown

Respond with only one of those four labels.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.2,
            max_tokens=50
        )
        label = response.choices[0].message.content.strip()
        return label if label in ["Buyer", "Seller", "Buyer & Seller", "Unknown"] else "Unknown"
    except:
        return "Unknown"


def classify_effort(ideas):
    idea_text = " ".join(ideas).strip()
    if not idea_text:
        return "Medium"

    prompt = """
Classify the overall technical effort of implementing the following ideas into Low, Medium, or High.

Respond only with one of: Low, Medium, or High.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": idea_text}
            ],
            temperature=0.2,
            max_tokens=20
        )
        label = response.choices[0].message.content.strip()
        return label if label in ["Low", "Medium", "High"] else "Medium"
    except:
        return "Medium"
