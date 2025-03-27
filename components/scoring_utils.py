# scoring_utils.py — GPT-enhanced scoring, with hybrid severity + subtag fallback
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

def estimate_severity(text):
    lowered = text.lower()
    if any(word in lowered for word in ["scam", "never received", "fraud", "fake", "authentication error", "vault locked"]):
        return 90
    if any(word in lowered for word in ["issue", "problem", "broken", "confused", "error", "glitch"]):
        return 70
    if any(word in lowered for word in ["could be better", "wish", "suggest", "slow", "should", "would be great if"]):
        return 50
    return 30

def calculate_pm_priority(insight):
    base = insight.get("score", 0)
    severity = insight.get("severity_score", 0)
    confidence = insight.get("type_confidence", 50)
    sentiment_conf = insight.get("sentiment_confidence", 50)
    return round((base * 0.2) + (severity * 0.4) + (confidence * 0.2) + (sentiment_conf * 0.2), 2)

def gpt_estimate_sentiment_subtag(text):
    """
    Use GPT to jointly classify sentiment and extract topic tags.
    Returns: { sentiment: str, subtags: list[str] }
    """
    if not client:
        return {"sentiment": "Neutral", "subtags": ["General"]}

    try:
        prompt = f"""Classify the following user feedback:
{text}

Return this format:
Sentiment: [Praise|Complaint|Neutral]
Subtags: [comma-separated themes like Refund, Trust Issue, Search]
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product analyst identifying themes and sentiment."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=150
        )
        content = response.choices[0].message.content.strip().lower()

        sentiment = "Neutral"
        subtags = ["General"]
        if "praise" in content:
            sentiment = "Praise"
        elif "complaint" in content:
            sentiment = "Complaint"

        if "subtags:" in content:
            line = content.split("subtags:")[-1]
            subtags = [s.strip().title() for s in line.strip("[] ").split(",") if s.strip()]

        return {"sentiment": sentiment.title(), "subtags": subtags or ["General"]}
    except Exception as e:
        print("[GPT fallback error]", e)
        return {"sentiment": "Neutral", "subtags": ["General"]}
