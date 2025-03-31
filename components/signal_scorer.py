# signal_scorer.py — Final self-contained version with insight type classifiers, effort, and enrichment

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import (
    generate_pm_ideas,
    rate_clarity
)
from components.scoring_utils import gpt_estimate_sentiment_subtag
from sentence_transformers import SentenceTransformer, util
import numpy as np
import hashlib

model = SentenceTransformer("all-MiniLM-L6-v2")

HIGH_SIGNAL_EXAMPLES = [
    "Authentication guarantee failed and refund denied",
    "Vault is down and I can't access my items",
    "PSA integration broke and delayed my grading by 30 days",
    "Shipping label created but never scanned, refund blocked",
    "Case break was rigged on eBay Live and nobody moderated"
]
EXEMPLAR_EMBEDDINGS = model.encode(HIGH_SIGNAL_EXAMPLES, convert_to_tensor=True)

HEURISTIC_KEYWORDS = {
    "authenticity guarantee": 15,
    "authentication failed": 15,
    "grading psa": 12,
    "ebay psa": 10,
    "vault authentication": 10,
    "return after authentication": 8,
    "delay": 5,
    "scam": 5,
    "broken": 5,
    "never received": 5,
    "ebay live": 5,
    "fanatics live": 5,
    "case break": 4,
    "box break": 4
}

KNOWN_COMPETITORS = ["fanatics", "whatnot", "alt", "loupe", "tiktok"]
KNOWN_PARTNERS = ["psa", "comc", "goldin", "ebay live", "ebay vault"]

ACTION_TYPES = {
    "ui": ["filter", "search", "tooltip", "label", "navigation"],
    "feature": ["add", "introduce", "enable", "support", "integration"],
    "policy": ["refund", "suspend", "blocked", "authentication"],
    "marketplace": ["grading", "shipping", "vault", "case break", "pack"]
}

def classify_effort(ideas):
    text = " ".join(ideas).lower()
    if any(x in text for x in ["rename", "change label", "copy", "show tooltip", "highlight", "reorder", "color"]):
        return "Low"
    if any(x in text for x in ["add filter", "combine", "enhance", "link", "simplify", "group", "new tab"]):
        return "Medium"
    return "High"

def classify_insight_type(text):
    lowered = text.lower()
    if any(x in lowered for x in ["can't find", "search", "filter", "browse"]):
        return "Discovery Friction", 80, "Search-related terms"
    if any(x in lowered for x in ["refund", "problem", "issue", "support", "delay", "authentic"]):
        return "Trust Issue", 85, "Post-purchase or authentication problems"
    if any(x in lowered for x in ["want", "wish", "add feature", "missing", "would be better"]):
        return "Feature Request", 75, "Improvement language"
    if any(x in lowered for x in ["love", "great", "awesome", "easy"]):
        return "Praise", 90, "Positive sentiment"
    return "Marketplace Chatter", 50, "Unclassified"

def classify_insight_type_gpt(text):
    return "Marketplace Chatter", 45, "GPT fallback not implemented"

def score_insight_semantic(text):
    embedding = model.encode(text, convert_to_tensor=True)
    similarity = util.cos_sim(embedding, EXEMPLAR_EMBEDDINGS).max().item()
    return round(similarity * 100, 2)

def score_insight_heuristic(text):
    lowered = text.lower()
    score = 0
    for keyword, value in HEURISTIC_KEYWORDS.items():
        if keyword in lowered:
            score += value
    return score

def combined_score(semantic, heuristic):
    return round((0.6 * semantic) + (0.4 * heuristic), 2)

def classify_persona(text):
    text = text.lower()
    buyer_signals = ["bought", "paid", "picked up", "acquired", "pc", "investment"]
    seller_signals = ["sold", "selling", "consigning", "listing", "submitted", "vault", "liquidating", "offloading"]
    if any(word in text for word in buyer_signals):
        return "Buyer"
    elif any(word in text for word in seller_signals):
        return "Seller"
    return "General"

def tag_topic_focus(text):
    lowered = text.lower()
    tags = []
    if "authenticity guarantee" in lowered or "authentication" in lowered:
        tags.append("Authenticity Guarantee")
    if "grading" in lowered and "psa" in lowered:
        tags.append("eBay PSA Grading")
    if "vault" in lowered:
        tags.append("Vault")
    if "refund" in lowered and "graded" in lowered:
        tags.append("Graded Refund Issue")
    if "case break" in lowered or "box break" in lowered:
        tags.append("Case Break")
    return tags

def detect_competitor_and_partner_mentions(text):
    lowered = text.lower()
    competitors = [c for c in KNOWN_COMPETITORS if c in lowered]
    partners = [p for p in KNOWN_PARTNERS if p in lowered]
    return competitors, partners

def classify_action_type(text):
    lowered = text.lower()
    for category, terms in ACTION_TYPES.items():
        if any(term in lowered for term in terms):
            return category.capitalize()
    return "Unclear"

def generate_insight_title(text):
    return text.strip().capitalize()[:60] + "..." if len(text) > 60 else text.strip().capitalize()

def classify_journey_stage(text):
    text = text.lower()
    if any(x in text for x in ["search", "browse", "can't find", "filter", "looking for"]):
        return "Discovery"
    elif any(x in text for x in ["buy", "add to cart", "checkout", "purchase", "payment"]):
        return "Purchase"
    elif any(x in text for x in ["ship", "shipping", "tracking", "delivered", "delay", "package"]):
        return "Fulfillment"
    elif any(x in text for x in ["return", "refund", "problem", "issue", "feedback", "support", "bad experience"]):
        return "Post-Purchase"
    return "Unknown"

def classify_opportunity_type(text):
    lowered = text.lower()
    if any(x in lowered for x in ["policy", "terms", "blocked", "suspended"]):
        return "Policy Risk"
    if any(x in lowered for x in ["conversion", "checkout", "didn’t buy"]):
        return "Conversion Blocker"
    if any(x in lowered for x in ["leaving", "stop using", "quit"]):
        return "Retention Risk"
    if any(x in lowered for x in ["compared to", "fanatics", "whatnot", "alt"]):
        return "Competitor Signal"
    if any(x in lowered for x in ["trust", "scam", "fraud"]):
        return "Trust Erosion"
    if any(x in lowered for x in ["love", "amazing", "recommend"]):
        return "Referral Amplifier"
    return "General Insight"

def enrich_single_insight(i, min_score=3):
    text = i.get("text", "")
    if not text or len(text.strip()) < 10:
        return None

    semantic_score = score_insight_semantic(text)
    heuristic_score = score_insight_heuristic(text)
    i["semantic_score"] = semantic_score
    i["heuristic_score"] = heuristic_score
    i["score"] = combined_score(semantic_score, heuristic_score)

    type_tag, confidence, reason = classify_insight_type(text)
    if confidence < 75:
        type_tag, confidence, reason = classify_insight_type_gpt(text)
    i["type_tag"] = type_tag
    i["type_confidence"] = confidence
    i["type_reason"] = reason

    i = enhance_insight(i)

    gpt_tags = gpt_estimate_sentiment_subtag(text)
    i["gpt_sentiment"] = gpt_tags.get("sentiment")
    i["gpt_subtags"] = gpt_tags.get("subtags")
    i["frustration"] = gpt_tags.get("frustration")
    i["impact"] = gpt_tags.get("impact")
    i["pm_summary"] = gpt_tags.get("summary")

    i["persona"] = classify_persona(text)
    i["ideas"] = generate_pm_ideas(text=text, brand=i.get("target_brand"), sentiment=i.get("brand_sentiment"))
    i["effort"] = classify_effort(i["ideas"])
    i["shovel_ready"] = (
        i["effort"] in ["Low", "Medium"]
        and i["type_tag"] in ["Feature Request", "Complaint"]
        and i["frustration"] >= 3
    )

    competitors, partners = detect_competitor_and_partner_mentions(text)
    i["mentions_competitor"] = competitors
    i["mentions_ecosystem_partner"] = partners
    i["action_type"] = classify_action_type(text)

    i["topic_focus"] = tag_topic_focus(text)
    i["journey_stage"] = classify_journey_stage(text)
    i["clarity"] = rate_clarity(text)
    i["title"] = generate_insight_title(text)
    i["opportunity_tag"] = classify_opportunity_type(text)
    i["cluster_ready_score"] = round((i["score"] + (i["frustration"] or 0)*5 + (i["impact"] or 0)*5) / 3, 2)
    i["fingerprint"] = hashlib.md5(text.lower().encode()).hexdigest()

    if i["type_tag"] != "Marketplace Chatter" and (i["score"] >= min_score or i["type_tag"] in ["Complaint", "Feature Request"]):
        return i
    return None

def filter_relevant_insights(insights, min_score=3):
    enriched = []
    for i in insights:
        enriched_item = enrich_single_insight(i, min_score)
        if enriched_item:
            enriched.append(enriched_item)
        else:
            print(f"[SKIPPED] Score too low or irrelevant: {i.get('text')[:80]}...")
    print(f"[SUMMARY] Enriched {len(enriched)} / {len(insights)} total insights")
    return enriched
