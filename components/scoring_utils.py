# scoring_utils.py — Enhanced scoring with GPT-powered enrichment, reasoning, caching, and normalization
import os
import json
import hashlib
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

CACHE_PATH = "gpt_sentiment_cache.json"

def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

sentiment_cache = load_cache()

def estimate_severity(text):
    lowered = text.lower()
    if any(word in lowered for word in ["scam", "never received", "fraud", "fake", "authentication error", "vault locked"]):
        return 90, "Contains fraud-related or high-risk terms"
    if any(word in lowered for word in ["issue", "problem", "broken", "confused", "error", "glitch"]):
        return 70, "Mentions confusion, bugs, or known issues"
    if any(word in lowered for word in ["could be better", "wish", "suggest", "slow", "should", "would be great if"]):
        return 50, "Mild complaint or enhancement request"
    return 30, "Low-intensity or neutral language"

def calculate_pm_priority(insight):
    base = insight.get("score", 0)
    severity = insight.get("severity_score", 0)
    confidence = insight.get("type_confidence", 50)
    sentiment_conf = insight.get("sentiment_confidence", 50)
    return round((base * 0.2) + (severity * 0.4) + (confidence * 0.2) + (sentiment_conf * 0.2), 2)

def normalize_priority_scores(insights):
    scores = [i.get("pm_priority_score", 0) for i in insights]
    if not scores:
        return insights
    min_score, max_score = min(scores), max(scores)
    for i in insights:
        raw = i.get("pm_priority_score", 0)
        i["pm_priority_percentile"] = round(100 * (raw - min_score) / (max_score - min_score + 1e-5), 2)
    return insights

def gpt_estimate_sentiment_subtag(text):
    if not client:
        return {"sentiment": "Neutral", "subtags": ["General"], "summary": "", "frustration": 1, "impact": 1}

    key = hashlib.md5(text.strip().encode()).hexdigest()
    if key in sentiment_cache:
        return sentiment_cache[key]

    try:
        prompt = f"""
Classify the following user feedback:
{text}

Return the following:
Sentiment: [Praise|Complaint|Neutral]
Subtags: [comma-separated themes like Refund, Trust Issue, Search]
Frustration: [1 (mild) to 5 (angry)]
Impact: [1 (low) to 5 (critical business impact)]
Summary: [One sentence summarizing the pain point]
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product analyst identifying themes and risk."},
                {"role": "user", "content": prompt.strip()}
            ],
            temperature=0,
            max_tokens=200
        )

        content = response.choices[0].message.content.strip().lower()

        sentiment = "Neutral"
        subtags = ["General"]
        frustration = 1
        impact = 1
        summary = ""

        for line in content.split("\n"):
            if "sentiment:" in line:
                if "praise" in line:
                    sentiment = "Praise"
                elif "complaint" in line:
                    sentiment = "Complaint"
            elif "subtags:" in line:
                subtags = [s.strip().title() for s in line.split(":", 1)[-1].strip("[] ").split(",") if s.strip()]
            elif "frustration:" in line:
                try:
                    frustration = int(line.split(":", 1)[-1].strip())
                except:
                    frustration = 1
            elif "impact:" in line:
                try:
                    impact = int(line.split(":", 1)[-1].strip())
                except:
                    impact = 1
            elif "summary:" in line:
                summary = line.split(":", 1)[-1].strip().capitalize()

        result = {
            "sentiment": sentiment.title(),
            "subtags": subtags or ["General"],
            "frustration": frustration,
            "impact": impact,
            "summary": summary
        }
        sentiment_cache[key] = result
        save_cache(sentiment_cache)
        return result

    except Exception as e:
        print("[GPT fallback error]", e)
        return {"sentiment": "Neutral", "subtags": ["General"], "summary": "", "frustration": 1, "impact": 1}
