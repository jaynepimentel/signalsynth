# enhanced_classifier.py — upgraded with multi-subtag, regex, severity boost
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
    "pop report": "Comps/Valuation",
    "turnaround": "Speed Issue",
    "verification": "Trust Issue"
}

STRONG_COMBOS = [
    ("vault", "delay", "Vault Friction"),
    ("shipping", "fanatics", "Shipping Concern"),
    ("grading", "psa", "Grading Complaint")
]

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

def detect_subtags(text):
    found = set()
    for key, label in SUBTAG_MAP.items():
        if re.search(rf"\\b{re.escape(key)}\\b", text):
            found.add(label)
    return list(found) if found else ["General"]

def match_combos(text):
    for a, b, label in STRONG_COMBOS:
        if a in text and b in text:
            return label
    return None

def enhance_insight(insight):
    text = insight.get("text", "").lower()

    # Brand detection
    brand = recognize_brand(text)
    insight["target_brand"] = brand

    # Sentiment classification
    sentiment, sent_conf = classify_sentiment(text)
    insight["brand_sentiment"] = {
        "Positive": "Praise",
        "Negative": "Complaint",
        "Neutral": "Neutral"
    }.get(sentiment, "Neutral")
    insight["sentiment_confidence"] = sent_conf

    # Subtags (plural)
    subtags = detect_subtags(text)
    combo_override = match_combos(text)
    if combo_override:
        subtags.insert(0, combo_override)  # prioritize

    insight["type_subtags"] = list(dict.fromkeys(subtags))  # deduped list
    insight["type_subtag"] = subtags[0]  # legacy primary subtag

    # Severity scoring
    severity = estimate_severity(text)
    insight["severity_score"] = severity
    insight["frustration_flag"] = severity >= 85

    # Priority scoring
    insight["pm_priority_score"] = calculate_pm_priority(insight)

    # Default fallback (if needed)
    if "type_tag" not in insight:
        insight["type_tag"] = "Discussion"
        insight["type_confidence"] = 70
        insight["type_reason"] = "Defaulted to Discussion"

    return insight
