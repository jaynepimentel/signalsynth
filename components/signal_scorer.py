# signal_scorer.py — Enhanced AI scoring for SignalSynth v3 with strategic flags

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import (
    generate_pm_ideas,
    classify_persona,
    classify_effort,
    classify_insight_type,
    classify_insight_type_gpt,
    rate_clarity
)
from components.scoring_utils import gpt_estimate_sentiment_subtag
from sentence_transformers import SentenceTransformer, util
import openai
import hashlib

model = SentenceTransformer("all-MiniLM-L6-v2")

HIGH_SIGNAL_EXAMPLES = [
    "Authentication guarantee failed and refund denied",
    "Vault is down and I can't access my items",
    "PSA integration broke and delayed my grading by 30 days",
    "Shipping label created but never scanned, refund blocked"
]
EXEMPLAR_EMBEDDINGS = model.encode(HIGH_SIGNAL_EXAMPLES, convert_to_tensor=True)

def score_insight_semantic(text):
    embedding = model.encode(text, convert_to_tensor=True)
    similarity = util.cos_sim(embedding, EXEMPLAR_EMBEDDINGS).max().item()
    return round(similarity * 100, 2)

def score_insight_heuristic(text):
    lowered = text.lower()
    score = 0
    if "authenticity guarantee" in lowered or "authentication failed" in lowered:
        score += 15
    if "grading" in lowered and "psa" in lowered:
        score += 12
    if "ebay" in lowered and "psa" in lowered:
        score += 10
    if "vault" in lowered and "authentication" in lowered:
        score += 10
    if "return after authentication" in lowered:
        score += 8
    if any(term in lowered for term in ["delay", "scam", "broken", "never received"]):
        score += 5
    return score

def combined_score(semantic, heuristic):
    return round((0.6 * semantic) + (0.4 * heuristic), 2)

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
    return tags

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
    if any(x in text.lower() for x in ["policy", "terms", "blocked", "suspended"]):
        return "Policy Risk"
    if any(x in text.lower() for x in ["conversion", "checkout", "didn’t buy"]):
        return "Conversion Blocker"
    if any(x in text.lower() for x in ["leaving", "stop using", "quit"]):
        return "Retention Risk"
    if any(x in text.lower() for x in ["compared to", "fanatics", "whatnot", "alt"]):
        return "Competitor Signal"
    if any(x in text.lower() for x in ["trust", "scam", "fraud"]):
        return "Trust Erosion"
    if any(x in text.lower() for x in ["love", "amazing", "recommend"]):
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

    i["topic_focus"] = tag_topic_focus(text)
    i["journey_stage"] = classify_journey_stage(text)
    i["clarity"] = rate_clarity(text)
    i["title"] = generate_insight_title(text)

    # New strategic fields
    i["opportunity_tag"] = classify_opportunity_type(text)
    i["cluster_ready_score"] = round((i["score"] + (i["frustration"] or 0)*5 + (i["impact"] or 0)*5) / 3, 2)
    i["fingerprint"] = hashlib.md5(text.lower().encode()).hexdigest()

    if i["type_tag"] != "Marketplace Chatter" and i["score"] >= min_score:
        return i
    return None

def filter_relevant_insights(insights, min_score=3):
    enriched = [enrich_single_insight(i, min_score) for i in insights]
    return [i for i in enriched if i is not None]
