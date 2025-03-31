# enhanced_classifier.py — hybrid GPT + keyword enrichment with severity unpack fix

import os
import re
from components.brand_recognizer import recognize_brand
from components.scoring_utils import estimate_severity, calculate_pm_priority, gpt_estimate_sentiment_subtag

# Use lightweight transformer model unless disabled
USE_LIGHT_MODEL = os.getenv("USE_LIGHT_CLASSIFIERS", "1") == "1"

if USE_LIGHT_MODEL:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from scipy.special import softmax

    MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
else:
    tokenizer = None
    model = None

def classify_sentiment(text):
    if tokenizer and model:
        encoded_input = tokenizer(text, return_tensors='pt', truncation=True, padding=True)
        with torch.no_grad():
            output = model(**encoded_input)
            scores = softmax(output.logits[0].numpy())
            labels = ["Negative", "Neutral", "Positive"]
            label = labels[scores.argmax()]
            confidence = round(float(scores.max()) * 100, 2)
        return {
            "sentiment": {"Positive": "Praise", "Negative": "Complaint", "Neutral": "Neutral"}.get(label, "Neutral"),
            "confidence": confidence
        }

    # fallback to GPT-based
    result = gpt_estimate_sentiment_subtag(text)
    return {
        "sentiment": result["sentiment"],
        "confidence": 70
    }

def detect_subtags(text):
    if not USE_LIGHT_MODEL:
        return gpt_estimate_sentiment_subtag(text)["subtags"]

    SUBTAG_MAP = {
        "delay": "Delays", "scam": "Fraud Concern", "slow": "Speed Issue",
        "authentication": "Trust Issue", "refund": "Refund Issue", "tracking": "Tracking Confusion",
        "fees": "Fee Frustration", "grading": "Grading Complaint", "shipping": "Shipping Concern",
        "vault": "Vault Friction", "fake": "Counterfeit Concern", "pop report": "Comps/Valuation",
        "turnaround": "Speed Issue", "verification": "Trust Issue"
    }
    found = set()
    for key, label in SUBTAG_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", text):
            found.add(label)
    return list(found) if found else ["General"]

def enhance_insight(insight):
    text = insight.get("text", "").lower()

    # Brand detection
    brand = recognize_brand(text)
    insight["target_brand"] = brand

    # Sentiment classification
    sentiment_result = classify_sentiment(text)
    insight["brand_sentiment"] = sentiment_result["sentiment"]
    insight["sentiment_confidence"] = sentiment_result["confidence"]

    # Subtags
    subtags = detect_subtags(text)
    insight["type_subtags"] = subtags
    insight["type_subtag"] = subtags[0]

    # Severity scoring
    severity, reason = estimate_severity(text)
    insight["severity_score"] = severity
    insight["severity_reason"] = reason
    insight["frustration_flag"] = severity >= 85

    # PM Priority
    insight["pm_priority_score"] = calculate_pm_priority(insight)

    # Fallbacks
    if "type_tag" not in insight:
        insight["type_tag"] = "Discussion"
        insight["type_confidence"] = 70
        insight["type_reason"] = "Defaulted to Discussion"

    return insight
