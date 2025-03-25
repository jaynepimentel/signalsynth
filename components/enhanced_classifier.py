# enhanced_classifier.py — Cloud-safe: avoids model load in Streamlit Cloud
import os
import re
from components.brand_recognizer import recognize_brand
from components.scoring_utils import estimate_severity, calculate_pm_priority

# Use these only during precompute
if os.getenv("RUNNING_IN_STREAMLIT") != "1":
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from scipy.special import softmax

    MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
else:
    tokenizer = None
    model = None

SUBTAG_MAP = {
    "delay": "Delays",
    "scam": "Fraud Concern",
    "slow": "Speed Issue",
    "authentication": "Trust Issue",
    "refund": "Refund Issue",
    "tracking": "Tracking Confusion",
    "fees": "Fee Frustration",
    "grading": "Grading Complaint",
    "shipping": "Shipping Concern",
    "vault": "Vault Friction",
    "fake": "Counterfeit Concern",
    "pop report": "Comps/Valuation"
}

def classify_sentiment(text):
    if not tokenizer or not model:
        return "Neutral", 0

    encoded_input = tokenizer(text, return_tensors='pt', truncation=True, padding=True)
    with torch.no_grad():
        output = model(**encoded_input)
        scores = softmax(output.logits[0].numpy())
        labels = ["Negative", "Neutral", "Positive"]
        label = labels[scores.argmax()]
        confidence = round(float(scores.max()) * 100, 2)
    return label, confidence

def get_subtag(text):
    text = text.lower()
    for key, subtag in SUBTAG_MAP.items():
        if key in text:
            return subtag
    return "General"

def enhance_insight(insight):
    text = insight.get("text", "")

    # Brand detection
    brand = recognize_brand(text)
    insight["target_brand"] = brand

    # Sentiment
    sentiment, sent_conf = classify_sentiment(text)
    insight["brand_sentiment"] = {
        "Positive": "Praise",
        "Negative": "Complaint",
        "Neutral": "Neutral"
    }.get(sentiment, "Neutral")
    insight["sentiment_confidence"] = sent_conf

    # Subtag
    insight["type_subtag"] = get_subtag(text)

    # Severity + PM priority
    insight["severity_score"] = estimate_severity(text)
    insight["pm_priority_score"] = calculate_pm_priority(insight)

    # Default fallback
    if "type_tag" not in insight:
        insight["type_tag"] = "Discussion"
        insight["type_confidence"] = 70
        insight["type_reason"] = "Defaulted to Discussion"

    return insight
