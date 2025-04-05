# signal_scorer.py — Updated with Streamer persona, TikTok Shopping, and expanded Live Commerce tagging

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import generate_pm_ideas
from components.gpt_classifier import enrich_with_gpt_tags
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
    "marketplace": ["grading", "shipping", "vault", "case break", "pack", "stream"]
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

def score_insight_semantic(text):
    embedding = model.encode(text, convert_to_tensor=True)
    similarity = util.cos_sim(embedding, EXEMPLAR_EMBEDDINGS).max().item()
    return round(similarity * 100, 2)

def score_insight_heuristic(text):
    lowered = text.lower()
    return sum(v for k, v in HEURISTIC_KEYWORDS.items() if k in lowered)

def combined_score(semantic, heuristic):
    return round((0.6 * semantic) + (0.4 * heuristic), 2)

def classify_persona(text):
    text = text.lower()
    if any(w in text for w in ["streamed", "on my stream", "ran a break", "sold live", "claim sale", "shop live", "hosted"]):
        return "Streamer"
    if any(w in text for w in ["sold", "listing", "consigning", "auctioned", "live seller", "posted", "stream sale"]):
        return "Seller"
    if any(w in text for w in ["bought", "won", "received", "joined", "claimed", "live buy", "purchase", "paid", "got it"]):
        return "Buyer"
    if "grading" in text or "slabbed" in text:
        return "Grader"
    if "collection" in text or "collector" in text:
        return "Collector"
    return "Unknown"

def tag_topic_focus(text):
    lowered = text.lower()
    tags = []
    if any(term in lowered for term in [
        "ebay live", "fanatics live", "live stream", "live auction", "live sale",
        "stream sale", "claim sale", "live claim", "shop live", "on stream", "whatnot live"
    ]):
        tags.append("Live Shopping")
    if any(term in lowered for term in [
        "case break", "box break", "group break", "live break", "joined break", "ran a break", "rip", "ripping"
    ]):
        tags.append("Case Break")
    if "tiktok" in lowered and ("shop" in lowered or "live" in lowered or "stream" in lowered):
        tags.append("TikTok Shopping")
    if "grading" in lowered and "psa" in lowered:
        tags.append("eBay PSA Grading")
    if "vault" in lowered:
        tags.append("Vault")
    if "authenticity guarantee" in lowered or "authentication" in lowered:
        tags.append("Authenticity Guarantee")
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
    return text.strip().capitalize()[:60] + "." if len(text) > 60 else text.strip().capitalize()

def classify_journey_stage(text):
    text = text.lower()
    if any(x in text for x in ["search", "browse", "can't find", "filter", "scrolling", "looking for", "scouting", "watching stream", "joined live", "streamed break"]):
        return "Discovery"
    if any(x in text for x in ["buy", "add to cart", "checkout", "purchase", "payment", "paid", "claimed", "won in break", "live purchase", "live claim"]):
        return "Purchase"
    if any(x in text for x in ["ship", "shipping", "tracking", "delivered", "delay", "package", "arrived", "got my cards", "received break cards"]):
        return "Fulfillment"
    if any(x in text for x in ["return", "refund", "problem", "issue", "feedback", "support", "missing card", "scammed", "no shipment"]):
        return "Post-Purchase"
    return "Unknown"

def classify_opportunity_type(text):
    lowered = text.lower()
    if any(x in lowered for x in ["policy", "terms", "blocked", "suspended"]):
        return "Policy Risk"
    if any(x in lowered for x in ["conversion", "checkout", "didn’t buy", "couldn't buy"]):
        return "Conversion Blocker"
    if any(x in lowered for x in ["leaving", "stop using", "quit"]):
        return "Retention Risk"
    if any(x in lowered for x in ["compared to", "fanatics", "whatnot", "alt", "tiktok"]):
        return "Competitor Signal"
    if any(x in lowered for x in ["trust", "scam", "fraud"]):
        return "Trust Erosion"
    if any(x in lowered for x in ["love", "amazing", "recommend"]):
        return "Referral Amplifier"
    return "General Insight"

def infer_clarity(text):
    text = text.strip().lower()
    if len(text) < 40 or "???" in text or "idk" in text or "confused" in text:
        return "Needs Clarification"
    return "Clear"

# ─────────────────────────────────────
# 🚀 Enrichment Pipeline

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
        type_tag, confidence, reason = "Marketplace Chatter", 50, "Fallback tag"
    i["type_tag"] = type_tag
    i["type_confidence"] = confidence
    i["type_reason"] = reason

    i = enhance_insight(i)
    i = enrich_with_gpt_tags(i)

    gpt_tags = gpt_estimate_sentiment_subtag(text)
    i["gpt_sentiment"] = gpt_tags.get("sentiment")
    i["gpt_subtags"] = gpt_tags.get("subtags")
    i["frustration"] = gpt_tags.get("frustration")
    i["impact"] = gpt_tags.get("impact")
    i["pm_summary"] = gpt_tags.get("summary")

    i["persona"] = i.get("persona") or classify_persona(text)
    i["ideas"] = generate_pm_ideas(text=text, brand=i.get("target_brand"))
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
    i["journey_stage"] = i.get("journey_stage") or classify_journey_stage(text)
    i["clarity"] = infer_clarity(text)
    i["title"] = generate_insight_title(text)
    i["opportunity_tag"] = i.get("opportunity_tag") or classify_opportunity_type(text)
    i["cluster_ready_score"] = round((i["score"] + (i["frustration"] or 0) * 5 + (i["impact"] or 0) * 5) / 3, 2)
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
            print(f"[SKIPPED] Score too low or irrelevant: {i.get('text')[:80]}.")
    print(f"[SUMMARY] Enriched {len(enriched)} / {len(insights)} total insights")
    return enriched
