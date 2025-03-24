# components/enhanced_classifier.py

from transformers import pipeline
import re

# Load sentiment model
sentiment_model = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")

SUBTYPE_RULES = {
    "Complaint": [
        ("shipping|delay|late|slow", "Shipping Delay"),
        ("fees|cut|too expensive", "High Fees"),
        ("authentication|auth issue", "Authentication"),
        ("support|no response|customer service", "Customer Support")
    ],
    "Feature Request": [
        ("add|introduce|wish|should|enable|nudge", "Feature Idea"),
        ("grading options|add sgc|multi grading", "Grading Options"),
        ("ux|listing|upload", "Listing UX"),
        ("international|foreign buyers", "International Support")
    ],
    "Confusion": [
        ("how do i|why does|can someone explain", "Process Confusion"),
        ("grading flow|labeling", "Grading Flow"),
        ("vault integration|psa", "Vault/PSA Integration")
    ]
}

def classify_sentiment(text):
    result = sentiment_model(text)[0]
    label = result['label'].capitalize()
    confidence = round(result['score'] * 100)

    if label == "Positive":
        return ("Praise", confidence)
    elif label == "Negative":
        return ("Complaint", confidence)
    return ("Neutral", confidence)

def classify_subtype(text, main_type):
    text = text.lower()
    if main_type in SUBTYPE_RULES:
        for pattern, subtype in SUBTYPE_RULES[main_type]:
            if re.search(pattern, text):
                return subtype
    return "General"

def enhance_insight(insight):
    text = insight.get("text", "")
    sentiment, confidence = classify_sentiment(text)
    insight["brand_sentiment"] = sentiment
    insight["sentiment_confidence"] = confidence

    insight_type = insight.get("type_tag", "Discussion")
    subtype = classify_subtype(text, insight_type)
    insight["type_subtag"] = subtype

    return insight
