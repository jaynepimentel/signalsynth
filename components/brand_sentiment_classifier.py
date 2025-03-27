# brand_sentiment_classifier.py — Hybrid keyword + OpenAI classification for brand sentiment
import re
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Keyword and pattern rules
PRAISE_KEYWORDS = [
    "love", "quick", "easy", "reliable", "awesome", "best", "great", "smooth", "affordable",
    "impressed", "good deal", "recommend", "trustworthy", "shipped fast", "perfect"
]

COMPLAINT_KEYWORDS = [
    "slow", "broken", "problem", "issue", "delay", "scam", "waste", "frustrated", "glitch",
    "too expensive", "doesn't work", "never received", "unacceptable", "refused", "fees", "cancelled"
]

PRAISE_PATTERNS = [
    r"i (really )?(love|like|appreciate) .*?({brand})",
    r"({brand}) .*? (is|was)? (so )?(easy|great|fast|awesome|smooth)"
]

COMPLAINT_PATTERNS = [
    r"({brand}) .*? (is|was|has been)? .*?(terrible|scam|problem|issue|broken|late|refused)",
    r"(hate|avoid|can't stand) .*?({brand})"
]

def classify_brand_sentiment(text, brand):
    text_lower = text.lower()
    brand_lower = brand.lower()

    # Heuristic rules
    if any(word in text_lower for word in PRAISE_KEYWORDS) and brand_lower in text_lower:
        return "Praise"
    if any(word in text_lower for word in COMPLAINT_KEYWORDS) and brand_lower in text_lower:
        return "Complaint"

    for pattern in PRAISE_PATTERNS:
        if re.search(pattern.format(brand=re.escape(brand_lower)), text_lower):
            return "Praise"
    for pattern in COMPLAINT_PATTERNS:
        if re.search(pattern.format(brand=re.escape(brand_lower)), text_lower):
            return "Complaint"

    # Fallback to AI sentiment classification
    if client and len(text_lower) > 30:
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Classify this customer's sentiment toward a brand as Praise, Complaint, or Neutral. Only return one of those words."},
                    {"role": "user", "content": f"Customer text:\n{text}\n\nBrand: {brand}"}
                ],
                temperature=0.2,
                max_tokens=10
            )
            classification = response.choices[0].message.content.strip()
            if classification in ["Praise", "Complaint", "Neutral"]:
                return classification
        except Exception as e:
            print("[Sentiment Fallback Error]", e)

    return "Neutral"
