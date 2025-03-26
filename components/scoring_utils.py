# scoring_utils.py — with GPT-enhanced severity + sentiment/subtag fallback
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a sentiment/subtag classifier for customer complaints and feature ideas."},
                {"role": "user", "content": f"""Classify the following:

{text}

Return format:
Sentiment: [Praise|Complaint|Neutral]
Subtags: [tag1, tag2]"""}
            ],
            temperature=0,
            max_tokens=150
        )
        content = response.choices[0].message.content.lower()
        sentiment = "Neutral"
        subtags = ["General"]
        if "praise" in content:
            sentiment = "Praise"
        elif "complaint" in content:
            sentiment = "Complaint"
        if "subtags:" in content:
            line = content.split("subtags:")[-1]
            subtags = [s.strip().title() for s in line.strip("[]").split(",") if s.strip()]
        return {"sentiment": sentiment.title(), "subtags": subtags}
    except:
        return {"sentiment": "Neutral", "subtags": ["General"]}