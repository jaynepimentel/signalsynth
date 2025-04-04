# signal_scorer.py — Final version with full enrichment for Collectibles PMs

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import generate_pm_ideas
from components.gpt_classifier import enrich_with_gpt_tags
from components.scoring_utils import gpt_estimate_sentiment_subtag
from sentence_transformers import SentenceTransformer, util
import numpy as np
import hashlib
import datetime

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
    "authenticity guarantee": 15, "authentication failed": 15, "grading psa": 12,
    "ebay psa": 10, "vault authentication": 10, "return after authentication": 8,
    "delay": 5, "scam": 5, "broken": 5, "never received": 5, "ebay live": 5,
    "fanatics live": 5, "case break": 4, "box break": 4
}

KNOWN_COMPETITORS = ["fanatics", "whatnot", "alt", "loupe", "tiktok"]
KNOWN_PARTNERS = ["psa", "comc", "goldin", "ebay live", "ebay vault"]
KNOWN_FEATURES = ["vault", "grading", "psa", "scan to list", "price guide", "live"]
LIVE_EVENT_DATES = ["2024-10-03", "2024-11-15", "2024-12-10"]

ACTION_TYPES = {
    "ui": ["filter", "search", "tooltip", "label", "navigation"],
    "feature": ["add", "introduce", "enable", "support", "integration"],
    "policy": ["refund", "suspend", "blocked", "authentication"],
    "marketplace": ["grading", "shipping", "vault", "case break", "pack"]
}


def score_insight_semantic(text):
    embedding = model.encode(text, convert_to_tensor=True)
    similarity = util.cos_sim(embedding, EXEMPLAR_EMBEDDINGS).max().item()
    return round(similarity * 100, 2)

def score_insight_heuristic(text):
    lowered = text.lower()
    return sum(v for k, v in HEURISTIC_KEYWORDS.items() if k in lowered)

def combined_score(semantic, heuristic):
    return round((0.6 * semantic) + (0.4 * heuristic), 2)

def classify_effort(ideas):
    text = " ".join(ideas).lower()
    if any(x in text for x in ["rename", "change label", "tooltip"]): return "Low"
    if any(x in text for x in ["add filter", "enhance", "combine"]): return "Medium"
    return "High"

def classify_insight_type(text):
    lowered = text.lower()
    if any(x in lowered for x in ["scam", "trying to scam", "fraud"]): return "Complaint", 90, "Scam related"
    if any(x in lowered for x in ["can't find", "search"]): return "Discovery Friction", 80, "Search"
    if any(x in lowered for x in ["refund", "problem", "delay"]): return "Trust Issue", 85, "Post-purchase"
    if any(x in lowered for x in ["want", "wish", "add feature"]): return "Feature Request", 75, "Feature gap"
    if any(x in lowered for x in ["love", "great", "awesome"]): return "Praise", 90, "Positive"
    return "Marketplace Chatter", 50, "Fallback"

def classify_persona(text):
    text = text.lower()
    if any(w in text for w in ["bought", "paid", "acquired"]): return "Buyer"
    if any(w in text for w in ["sold", "selling", "consigned"]): return "Seller"
    if any(w in text for w in ["collecting", "collector"]): return "Collector"
    return "General"

def classify_journey_stage(text):
    text = text.lower()
    if any(x in text for x in ["search", "browse", "filter"]): return "Discovery"
    if any(x in text for x in ["buy", "checkout"]): return "Purchase"
    if any(x in text for x in ["ship", "tracking"]): return "Fulfillment"
    if any(x in text for x in ["return", "issue", "refund"]): return "Post-Purchase"
    return "Unknown"

def tag_topic_focus(text):
    lowered = text.lower()
    tags = []
    if "authenticity guarantee" in lowered: tags.append("Authenticity Guarantee")
    if "grading" in lowered and "psa" in lowered: tags.append("eBay PSA Grading")
    if "vault" in lowered: tags.append("Vault")
    if "case break" in lowered: tags.append("Case Break")
    return tags

def classify_action_type(text):
    lowered = text.lower()
    for category, terms in ACTION_TYPES.items():
        if any(term in lowered for term in terms): return category.capitalize()
    return "Unclear"

def classify_opportunity_type(text):
    lowered = text.lower()
    if "policy" in lowered or "blocked" in lowered: return "Policy Risk"
    if "conversion" in lowered or "checkout" in lowered: return "Conversion Blocker"
    if "leaving" in lowered or "quit" in lowered: return "Retention Risk"
    if any(c in lowered for c in KNOWN_COMPETITORS): return "Competitor Signal"
    if "trust" in lowered or "fraud" in lowered: return "Trust Erosion"
    if "love" in lowered: return "Referral Amplifier"
    return "General Insight"

def infer_clarity(text):
    text = text.lower()
    if len(text) < 40 or "???" in text or "idk" in text: return "Needs Clarification"
    return "Clear"

def detect_feature_area(text):
    lowered = text.lower()
    return [f for f in KNOWN_FEATURES if f in lowered]

def infer_signal_intent(text):
    lowered = text.lower()
    if any(k in lowered for k in ["sold", "listing"]): return "Seller"
    if any(k in lowered for k in ["bought", "paid"]): return "Buyer"
    if any(k in lowered for k in ["collector", "collecting"]): return "Collector"
    return "General"

def is_post_event_feedback(post_date_str):
    try:
        post_date = datetime.datetime.fromisoformat(post_date_str).date()
        return any(abs((post_date - datetime.date.fromisoformat(e)).days) <= 1 for e in LIVE_EVENT_DATES)
    except:
        return False

def detect_comparison_sentiment(text):
    lowered = text.lower()
    if any(x in lowered for x in ["better than", "prefer", "vs", "compared to"]):
        if any(c in lowered for c in KNOWN_COMPETITORS):
            return {"competitor_comparison_score": 2, "comparison_context": "User Comparison"}
    if any(x in lowered for x in ["worse than"]):
        return {"competitor_comparison_score": -2, "comparison_context": "Negative Comparison"}
    return {"competitor_comparison_score": 0, "comparison_context": "None"}

def infer_region(text):
    lowered = text.lower()
    if "canada" in lowered: return "Canada"
    if "japan" in lowered: return "Japan"
    if "germany" in lowered or "eu" in lowered: return "Europe"
    return "Unknown"

def detect_strategic_cohort(text):
    lowered = text.lower()
    if any(x in lowered for x in ["$10k", "goldin", "auction house"]): return "High-End Buyer"
    if any(x in lowered for x in ["bulk selling", "top-rated"]): return "Bulk Seller"
    if "collector" in lowered or "collecting" in lowered: return "Power Collector"
    return "General"

def enrich_single_insight(i, min_score=3):
    text = i.get("text", "")
    if not text or len(text.strip()) < 10: return None

    i["semantic_score"] = score_insight_semantic(text)
    i["heuristic_score"] = score_insight_heuristic(text)
    i["score"] = combined_score(i["semantic_score"], i["heuristic_score"])

    tag, conf, reason = classify_insight_type(text)
    i.update({"type_tag": tag, "type_confidence": conf, "type_reason": reason})

    i = enhance_insight(i)
    i = enrich_with_gpt_tags(i)
    gpt = gpt_estimate_sentiment_subtag(text)
    i.update({
        "gpt_sentiment": gpt.get("sentiment"),
        "gpt_subtags": gpt.get("subtags"),
        "frustration": gpt.get("frustration"),
        "impact": gpt.get("impact"),
        "pm_summary": gpt.get("summary")
    })

    i["persona"] = i.get("persona") or classify_persona(text)
    i["ideas"] = generate_pm_ideas(text=text, brand=i.get("target_brand"))
    i["effort"] = classify_effort(i["ideas"])
    i["shovel_ready"] = (i["effort"] in ["Low", "Medium"] and i["type_tag"] in ["Feature Request", "Complaint"] and i["frustration"] >= 3)

    i["mentions_competitor"], i["mentions_ecosystem_partner"] = detect_competitor_and_partner_mentions(text)
    i["action_type"] = classify_action_type(text)
    i["topic_focus"] = tag_topic_focus(text)
    i["journey_stage"] = i.get("journey_stage") or classify_journey_stage(text)
    i["clarity"] = infer_clarity(text)
    i["title"] = generate_insight_title(text)
    i["opportunity_tag"] = i.get("opportunity_tag") or classify_opportunity_type(text)
    i["cluster_ready_score"] = round((i["score"] + (i["frustration"] or 0)*5 + (i["impact"] or 0)*5) / 3, 2)
    i["fingerprint"] = hashlib.md5(text.lower().encode()).hexdigest()

    # 🧠 Advanced
    i["signal_intent"] = infer_signal_intent(text)
    i["feature_area"] = detect_feature_area(text)
    i["is_post_event_feedback"] = is_post_event_feedback(i.get("post_date", datetime.date.today().isoformat()))
    i["region"] = infer_region(text)
    i["cohort"] = detect_strategic_cohort(text)
    i.update(detect_comparison_sentiment(text))

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
