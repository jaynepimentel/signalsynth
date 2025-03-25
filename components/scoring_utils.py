# scoring_utils.py — severity, risk, and priority scoring

def estimate_severity(text):
    """
    Scores how severe the user’s language is, based on known risk terms.
    Range: 0–100
    """
    text = text.lower()

    if any(word in text for word in ["scam", "never received", "fraud", "fake", "delay", "authentication error"]):
        return 90
    if any(word in text for word in ["issue", "problem", "confused", "why", "broken", "tracking error"]):
        return 70
    if any(word in text for word in ["could be better", "wish", "suggest", "should", "would be great if"]):
        return 50
    return 30  # Mild or neutral feedback

def calculate_pm_priority(insight):
    """
    Composite score using insight strength, severity, classifier confidence, and sentiment.
    Output is a single priority score (0–100+).
    """
    base = insight.get("score", 0)
    severity = insight.get("severity_score", 0)
    confidence = insight.get("type_confidence", 50)
    sentiment_conf = insight.get("sentiment_confidence", 50)

    return round((base * 0.2) + (severity * 0.4) + (confidence * 0.2) + (sentiment_conf * 0.2), 2)
