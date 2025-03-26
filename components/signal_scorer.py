# signal_scorer.py — AI-enhanced signal classification for SignalSynth

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import generate_pm_ideas, classify_insight_type, classify_persona, classify_effort
from sentence_transformers import SentenceTransformer, util

# Load semantic model once
model = SentenceTransformer("all-MiniLM-L6-v2")

# Exemplars (high-signal references)
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
    return round(similarity * 100, 2)  # Scale to 0–100


def filter_relevant_insights(insights, min_score=3):
    enriched = []
    for i in insights:
        text = i.get("text", "")

        # --- Semantic Signal Strength
        i["score"] = score_insight_semantic(text)

        # --- GPT: Insight Type (Complaint, Confusion, Feature, etc.)
        i["type_tag"], i["type_confidence"], i["type_reason"] = classify_insight_type(text)

        # --- Classify & Enrich
        i = enhance_insight(i)

        # --- GPT: Persona Detection
        i["persona"] = classify_persona(text)

        # --- GPT: Idea Suggestions (competitive-aware)
        i["ideas"] = generate_pm_ideas(text, i.get("target_brand"), i.get("brand_sentiment"))

        # --- GPT: Effort Classification
        i["effort"] = classify_effort(i["ideas"])

        if i["type_tag"] != "Marketplace Chatter" and i["score"] >= min_score:
            enriched.append(i)

    return enriched
