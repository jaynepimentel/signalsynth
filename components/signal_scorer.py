# signal_scorer.py — enriches insights + elevates Payments/UPI/high-ASP into visible tags/opportunities/persona

import os, hashlib
from sentence_transformers import SentenceTransformer, util

from components.enhanced_classifier import enhance_insight
from components.ai_suggester import generate_pm_ideas
from components.gpt_classifier import enrich_with_gpt_tags
from components.scoring_utils import (
    gpt_estimate_sentiment_subtag,
    detect_competitor_and_partner_mentions,
    infer_clarity, generate_insight_title, tag_topic_focus,
    classify_opportunity_type, classify_action_type, calculate_cluster_ready_score,
    detect_payments_upi_highasp,
    detect_liquidity_signals,
)

def _load_embed():
    name=os.getenv("SS_EMBED_MODEL","intfloat/e5-base-v2")
    try:
        if os.path.isdir(f"models/{name.replace('/','_')}"):
            m=SentenceTransformer(f"models/{name.replace('/','_')}")
        else:
            m=SentenceTransformer(name)
    except Exception:
        try:
            m=SentenceTransformer("models/all-MiniLM-L6-v2")
        except Exception:
            m=SentenceTransformer("all-MiniLM-L6-v2")
    # Derive the true position-embedding limit from the underlying model config.
    try:
        pos_limit = m[0].auto_model.config.max_position_embeddings
    except Exception:
        pos_limit = 256
    # Set max_seq_length on ALL levels to ensure tokenizer truncation works.
    # Leave room for [CLS] + [SEP] special tokens (subtract 2).
    safe_limit = pos_limit - 2
    m.max_seq_length = safe_limit
    if hasattr(m, 'tokenizer'):
        m.tokenizer.model_max_length = safe_limit
    try:
        m[0].max_seq_length = safe_limit
    except Exception:
        pass
    return m

model=_load_embed()
# Cache the token limit for use in _truncate_to_token_limit
_MODEL_TOKEN_LIMIT = model.max_seq_length

HIGH_SIGNAL_EXAMPLES=[
    "authentication guarantee failed",
    "bid cancelled just before auction ended",
    "seller disappeared",
    "high bid pulled",
    "trust issue in auction flow",
    "counterfeit card detected in authenticity",
    "search relevancy broken on trading cards",
]
EXEMPLAR_EMBEDDINGS=model.encode(HIGH_SIGNAL_EXAMPLES, convert_to_tensor=True, normalize_embeddings=True)

HEURISTIC_KEYWORDS={
    "scam":8,"fraud":8,"trust issue":10,"bid cancel":10,"auction integrity":12,"cancelled bid":8,
    "high bid pulled":10,"counterfeit":10,"authentication error":10,"return fraud":10,
}

def _truncate_to_token_limit(text:str, max_tokens:int=0)->str:
    """Truncate text so it tokenizes to at most max_tokens.
    Uses the model's own tokenizer to count and truncate accurately."""
    if max_tokens <= 0:
        max_tokens = _MODEL_TOKEN_LIMIT - 2  # room for special tokens
    t = (text or "").strip()
    if not t:
        return t
    try:
        tok = model.tokenizer
        ids = tok.encode(t, add_special_tokens=False, truncation=False)
        if len(ids) <= max_tokens:
            return t
        # Decode only the first max_tokens token IDs back to text
        truncated = tok.decode(ids[:max_tokens], skip_special_tokens=True)
        return truncated
    except Exception:
        # Fallback: aggressive char-level truncation (~2 chars per token)
        return t[:max_tokens * 2]

def _safe_encode(text:str):
    """Encode text with guaranteed truncation to prevent tensor mismatch."""
    truncated = _truncate_to_token_limit(text)
    return model.encode(truncated, convert_to_tensor=True, normalize_embeddings=True)

def score_insight_semantic(text:str)->float:
    try:
        sim=util.cos_sim(_safe_encode(text), EXEMPLAR_EMBEDDINGS).max().item()
        return round(sim*100,2)
    except Exception:
        return 0.0

def score_insight_heuristic(text:str)->int:
    lowered=text.lower()
    return sum(v for k,v in HEURISTIC_KEYWORDS.items() if k in lowered)

def combined_score(semantic:float, heuristic:float, frustration:int, impact:int)->float:
    return round((0.5*semantic)+(0.3*heuristic)+(0.1*frustration*10)+(0.1*impact*10),2)

def classify_effort(ideas)->str:
    t=" ".join(ideas or []).lower()
    if any(x in t for x in ["tooltip","rename","label"]): return "Low"
    if any(x in t for x in ["simplify","filter","combine","sort","default"]): return "Medium"
    return "High"

def _apply_payment_flags(i:dict)->dict:
    topic=list(i.get("topic_focus") or [])
    sub=list(i.get("type_subtags") or [])

    flags=detect_payments_upi_highasp(i.get("text",""))
    for k,v in flags.items():
        if i.get(k) is None: i[k]=v

    if i.get("_payment_issue") and "Payments" not in topic: topic.append("Payments")
    if i.get("_upi_flag") and "UPI" not in topic: topic.append("UPI")

    pit=set(i.get("payment_issue_types") or [])
    if "payment_declined" in pit and "Payment Declined" not in sub: sub.append("Payment Declined")
    if "insufficient_funds" in pit and "Insufficient Funds" not in sub: sub.append("Insufficient Funds")
    if "wire_or_bank_transfer" in pit and "Wire/Bank Transfer" not in sub: sub.append("Wire/Bank Transfer")
    if "payment_hold" in pit and "Payment Hold" not in sub: sub.append("Payment Hold")
    if i.get("_upi_flag") and "UPI" not in sub: sub.append("UPI")

    if {"payment_declined","wire_or_bank_transfer","insufficient_funds","payment_hold"} & pit and not i.get("opportunity_tag"):
        i["opportunity_tag"]="Conversion Blocker"
    if i.get("_upi_flag") and (not i.get("opportunity_tag") or i["opportunity_tag"]=="General Insight"):
        i["opportunity_tag"]="Policy Risk"

    if (i.get("_payment_issue") or i.get("_upi_flag")) and i.get("brand_sentiment") in (None,"Neutral"):
        i["brand_sentiment"]="Complaint"

    if i.get("_high_end_flag") and (not i.get("persona") or i["persona"]=="General"):
        i["persona"]="High-End User"

    i["topic_focus"]=topic
    i["type_subtags"]=sub or ["General"]
    i["type_subtag"]=i["type_subtags"][0]
    return i

def _apply_liquidity_flags(i:dict)->dict:
    text=i.get("text","")
    flags=detect_liquidity_signals(text)
    for k,v in flags.items():
        if i.get(k) is None: i[k]=v
    topic=list(i.get("topic_focus") or [])
    sub=list(i.get("type_subtags") or [])
    if flags.get("_liquidity_signal"):
        if "Instant Offers / Liquidity" not in topic: topic.append("Instant Offers / Liquidity")
        sig_types=flags.get("liquidity_signal_types",[])
        if "instant_offer" in sig_types and "Instant Offers" not in sub: sub.append("Instant Offers")
        if "liquidity_behavior" in sig_types and "Liquidity" not in sub: sub.append("Liquidity")
        if "liquidity_platform" in sig_types and "Liquidity Platform" not in sub: sub.append("Liquidity Platform")
        if not i.get("opportunity_tag") or i["opportunity_tag"]=="General Insight":
            i["opportunity_tag"]="Liquidity Signal"
    i["topic_focus"]=topic
    i["type_subtags"]=sub or ["General"]
    i["type_subtag"]=i["type_subtags"][0]
    return i

def enrich_single_insight(i:dict, min_score:float=3):
    text=i.get("text","") or ""
    if len(text.strip())<10: return None

    semantic=score_insight_semantic(text)
    heuristic=score_insight_heuristic(text)
    gpt=gpt_estimate_sentiment_subtag(text)

    i=enhance_insight(i)      # sentiment, subtags, severity, pm_priority, brand, etc.
    i=enrich_with_gpt_tags(i)

    i["semantic_score"]=semantic
    i["heuristic_score"]=heuristic
    i["frustration"]=gpt.get("frustration",1)
    i["impact"]=gpt.get("impact",1)
    i["score"]=combined_score(semantic,heuristic,i["frustration"],i["impact"])

    i["gpt_sentiment"]=gpt.get("sentiment")
    i["gpt_subtags"]=gpt.get("subtags")
    i["pm_summary"]=gpt.get("summary")

    i["persona"]=i.get("persona") or "General"
    try:
        i["ideas"]=generate_pm_ideas(text=_truncate_to_token_limit(text, 200), brand=i.get("target_brand"))
    except (Exception, KeyboardInterrupt) as _pm_err:
        i["ideas"]=[]
    i["effort"]=classify_effort(i["ideas"])
    i["shovel_ready"]=(i["frustration"]>=4) and (i["impact"]>=3)

    mentions=detect_competitor_and_partner_mentions(text)
    if isinstance(mentions,dict):
        i["mentions"]=mentions
        i["mentions_competitor"]=mentions.get("competitors",[])
        i["mentions_ecosystem_partner"]=mentions.get("partners",[])
    else:
        comp,partner=mentions if isinstance(mentions,(list,tuple)) and len(mentions)==2 else ([],[])
        i["mentions"]={"competitors":list(comp),"partners":list(partner),"market_terms":[]}
        i["mentions_competitor"]=list(comp)
        i["mentions_ecosystem_partner"]=list(partner)

    i["action_type"]=classify_action_type(text)
    i["topic_focus"]=tag_topic_focus(text)
    i["journey_stage"]=i.get("journey_stage") or "Discovery"
    i["clarity"]=infer_clarity(text)
    i["title"]=generate_insight_title(text)
    i["opportunity_tag"]=i.get("opportunity_tag") or classify_opportunity_type(text)

    i=_apply_payment_flags(i)
    i=_apply_liquidity_flags(i)

    i["cluster_ready_score"]=calculate_cluster_ready_score(i["score"], i["frustration"], i["impact"])
    i["fingerprint"]=hashlib.md5(text.lower().encode()).hexdigest()
    return i if i["score"]>=min_score else None

def filter_relevant_insights(insights, min_score:float=3):
    enriched=[]
    for it in insights or []:
        x=enrich_single_insight(it, min_score)
        if x: enriched.append(x)
    return enriched
