# enhanced_classifier.py — sentiment + brand + type subtag enhancer
import re
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from scipy.special import softmax
from components.brand_recognizer import recognize_brand

# Load sentiment model once
MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

# Subtags by keyword trigger
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

    # Brand detection (NER + fuzzy match)
    brand = recognize_brand(text)
    insight["target_brand"] = brand

    # Sentiment detection
    sentiment, sent_conf = classify_sentiment(text)
    insight["brand_sentiment"] = {
        "Positive": "Praise",
        "Negative": "Complaint",
        "Neutral": "Neutral"
    }.get(sentiment, "Neutral")
    insight["sentiment_confidence"] = sent_conf

    # Subtag
    insight["type_subtag"] = get_subtag(text)

    # Type tagging fallback (optional)
    if "type_tag" not in insight:
        insight["type_tag"] = "Discussion"
        insight["type_confidence"] = 70
        insight["type_reason"] = "No match — defaulted to Discussion"

    return insight
