# ai_suggester.py — GPT-powered suggestions, type classification, and clarity scoring

import os
import json
import hashlib
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# GPT suggestion cache
CACHE_PATH = "gpt_suggestion_cache.json"
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

def save_cache():
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(suggestion_cache, f, indent=2)

# ---- PM IDEAS ----
def generate_pm_ideas(text, brand="eBay", sentiment="Neutral"):
    key = hashlib.md5((text + brand + sentiment).encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    if not os.getenv("OPENAI_API_KEY"):
        return ["[⚠️ No API key set — skipping GPT suggestion generation]"]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a senior product manager. Based on this user feedback, identify the customer concern and provide specific, high-impact product suggestions."},
                {"role": "user", "content": f"Feedback: {text}\n\nBrand: {brand}\nSentiment: {sentiment}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        suggestions = [
            line.strip("- ").strip()
            for line in response.choices[0].message.content.strip().split("\n")
            if line.strip()
        ]
        suggestion_cache[key] = suggestions
        save_cache()
        return suggestions

    except Exception as e:
        return [f"[⚠️ GPT error: {str(e)}]"]

# ---- INSIGHT TYPE (HEURISTIC) ----
def classify_insight_type(text):
    t = text.lower()
    if any(p in t for p in ["issue", "bug", "broken", "not working", "problem"]):
        return "Complaint", 90, "Detected complaint phrasing"
    if any(p in t for p in ["should add", "wish", "feature request", "need to add"]):
        return "Feature Request", 88, "Detected feature request phrasing"
    if any(p in t for p in ["how do", "i don’t understand", "what is", "can someone explain"]):
        return "Confusion", 85, "Detected confusion/how-to phrasing"
    return "Discussion", 70, "Defaulted to general discussion"

# ---- INSIGHT TYPE (GPT FALLBACK) ----
def classify_insight_type_gpt(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product classification assistant. Classify the user feedback as one of the following types:\n- Complaint\n- Feature Request\n- Confusion\n- Discussion\n\nRespond in this exact format:\nType: [type]\nConfidence: [0–100]\nReason: [brief reason]"},
                {"role": "user", "content": text.strip()}
            ],
            temperature=0,
            max_tokens=100
        )
        result = response.choices[0].message.content.strip()

        type_tag = "Discussion"
        confidence = 70
        reason = "Defaulted"

        for line in result.splitlines():
            if line.lower().startswith("type:"):
                type_tag = line.split(":", 1)[1].strip()
            if line.lower().startswith("confidence:"):
                confidence = int(line.split(":", 1)[1].strip())
            if line.lower().startswith("reason:"):
                reason = line.split(":", 1)[1].strip()

        return type_tag, confidence, reason
    except Exception as e:
        return "Discussion", 70, f"GPT fallback failed: {e}"

# ---- PERSONA CLASSIFIER ----
def classify_persona(text):
    t = text.lower()
    if any(x in t for x in ["sell", "seller", "my buyer", "listing"]):
        return "Seller"
    if any(x in t for x in ["buy", "bought", "purchased", "my order"]):
        return "Buyer"
    if any(x in t for x in ["grading", "slab", "submission", "vault"]):
        return "Collector"
    return "Unknown"

# ---- EFFORT ESTIMATOR ----
def classify_effort(ideas):
    joined = " ".join(ideas).lower()
    if any(x in joined for x in ["tooltip", "label", "copy change", "nudge"]):
        return "Low"
    if any(x in joined for x in ["chart", "breakdown", "comps", "filters"]):
        return "Medium"
    if any(x in joined for x in ["integration", "workflow", "automation", "sync", "refactor"]):
        return "High"
    return "Medium"

# ---- CLARITY RATING ----
def rate_clarity(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Rate how clear and actionable this user insight is. Return either:\n- Clarity: Clear\n- Clarity: Needs Clarification"},
                {"role": "user", "content": text.strip()}
            ],
            temperature=0,
            max_tokens=20
        )
        content = response.choices[0].message.content.strip().lower()
        if "needs clarification" in content:
            return "Needs Clarification"
        return "Clear"
    except:
        return "Clear"
