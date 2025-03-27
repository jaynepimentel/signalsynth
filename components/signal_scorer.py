# signal_scorer.py — AI-enhanced signal classification for SignalSynth

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import (
    generate_pm_ideas,
    classify_insight_type,
    classify_persona,
    classify_effort
)
from sentence_transformers import SentenceTransformer, util

# Load semantic similarity model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Exemplars of high-value signals for semantic scoring
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
    return round(similarity * 100, 2)  # 0–100 scale

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

def enrich_single_insight(i, min_score=3):
    text = i.get("text", "")
    if not text or len(text.strip()) < 10:
        return None

    # Scoring
    semantic_score = score_insight_semantic(text)
    heuristic_score = score_insight_heuristic(text)
    i["semantic_score"] = semantic_score
    i["heuristic_score"] = heuristic_score
    i["score"] = combined_score(semantic_score, heuristic_score)

    # Type
    i["type_tag"], i["type_confidence"], i["type_reason"] = classify_insight_type(text)

    # Brand, sentiment, subtag, severity
    i = enhance_insight(i)

    # Persona
    i["persona"] = classify_persona(text)

    # AI suggestions
    i["ideas"] = generate_pm_ideas(
        text=text,
        brand=i.get("target_brand"),
        sentiment=i.get("brand_sentiment")
    )

    # Effort + Shovel Readiness
    i["effort"] = classify_effort(i["ideas"])
    i["shovel_ready"] = i["effort"] in ["Low", "Medium"] and i["type_tag"] in ["Feature Request", "Complaint"]

    # Topic focus
    i["topic_focus"] = tag_topic_focus(text)

    # Discovery confidence
    if i["type_tag"] in ["Complaint", "Feature Request"] and i["score"] > 80:
        i["discovery_confidence"] = "High"
    elif i["score"] > 60:
        i["discovery_confidence"] = "Medium"
    else:
        i["discovery_confidence"] = "Low"

    # Final filter
    if i["type_tag"] != "Marketplace Chatter" and i["score"] >= min_score:
        return i
    return None

def filter_relevant_insights(insights, min_score=3):
    return [x for x in (enrich_single_insight(i, min_score) for i in insights) if x]