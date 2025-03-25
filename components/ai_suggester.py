# ai_suggester.py — OpenAI v1.0+ safe with caching and quota handling
import os
import json
import hashlib
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

system_prompt = """
You are a senior product manager at a major marketplace platform like eBay or Fanatics. 
Based on user feedback, identify the customer's concern and recommend specific, strategic 
product improvements or operational actions. Focus on things that would build trust, improve
conversion, or reduce friction. Use strong PM thinking.
"""

CACHE_PATH = "gpt_suggestion_cache.json"

# Load or initialize cache
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(text.strip().encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    if not os.getenv("OPENAI_API_KEY"):
        return ["[No API key set — using fallback suggestion]"]

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
        output = response.choices[0].message.content.strip().split("\n")
        suggestions = [line.strip("- ").strip() for line in output if line.strip()]
        suggestion_cache[key] = suggestions

        # Save to cache
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2)

        return suggestions

    except Exception as e:
        if "429" in str(e):
            return ["[⚠️ OpenAI rate limit hit — retry later or reduce load]"]
        elif "authentication" in str(e).lower():
            return ["[⚠️ Missing or invalid OpenAI API key]"]
        else:
            return [f"[Error calling OpenAI: {e}]"]