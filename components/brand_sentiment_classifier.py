# brand_sentiment_classifier.py — Enhanced with OpenAI fallback for nuanced sentiment
import re
import os
from dotenv import load_dotenv
from openai import OpenAI

PRAISE_KEYWORDS = [
    "love", "fast", "quick", "easy", "reliable", "awesome", "best", "great", "smooth", "affordable",
    "impressed", "good deal", "got it fast", "recommend", "trustworthy"
]

COMPLAINT_KEYWORDS = [
    "slow", "broken", "bad", "issue", "problem", "delay", "scam", "waste", "frustrated", "glitch",
    "too expensive", "fees", "doesn't work", "never received", "unacceptable", "refund"
]

PRAISE_PATTERNS = [
    r"i (really )?(love|like|appreciate) .*?\b({brand})\b",
    r"({brand}) .*? is (so )?(easy|smooth|great|fast|awesome)"
]

COMPLAINT_PATTERNS = [
    r"({brand}) .*? (is|was|has been)? .*? (terrible|scam|problem|issue|slow|broken)",
    r"(hate|can't stand|avoid) .*?({brand})"
]

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

def classify_brand_sentiment(text, brand):
    text = text.lower()
    brand = brand.lower()

    if any(p in text for p in PRAISE_KEYWORDS) and brand in text:
        return "Praise"
    if any(c in text for c in COMPLAINT_KEYWORDS) and brand in text:
        return "Complaint"

    for pat in PRAISE_PATTERNS:
        if re.search(pat.format(brand=brand), text):
            return "Praise"
    for pat in COMPLAINT_PATTERNS:
        if re.search(pat.format(brand=brand), text):
            return "Complaint"

    if client and len(text) > 50:
        try:
            prompt = f"Classify the sentiment of this text toward '{brand}':\n{text}\n\nLabel it only as Praise, Complaint, or Neutral."
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a sentiment classifier focused on customer feedback."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10
            )
            output = response.choices[0].message.content.strip()
            if output in ["Praise", "Complaint", "Neutral"]:
                return output
        except:
            pass

    return "Neutral"
