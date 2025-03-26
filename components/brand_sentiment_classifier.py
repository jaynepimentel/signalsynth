# brand_sentiment_classifier.py — fallback GPT support for sentiment
import re
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PRAISE_KEYWORDS = ["love", "fast", "quick", "easy", "reliable", "awesome", "best", "great"]
COMPLAINT_KEYWORDS = ["slow", "broken", "bad", "issue", "problem", "delay", "scam", "waste"]

def classify_brand_sentiment(text, brand):
    text = text.lower()
    brand = brand.lower()

    if any(p in text for p in PRAISE_KEYWORDS) and brand in text:
        return "Praise"
    if any(c in text for c in COMPLAINT_KEYWORDS) and brand in text:
        return "Complaint"

    # GPT fallback
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a brand sentiment classifier."},
                {"role": "user", "content": f"What is the sentiment toward {brand} in this post?

{text}"}
            ],
            temperature=0,
            max_tokens=20
        )
        result = response.choices[0].message.content.lower()
        if "praise" in result or "positive" in result:
            return "Praise"
        if "complaint" in result or "negative" in result:
            return "Complaint"
    except:
        pass
    return "Neutral"