# components/ai_suggester.py — env-driven GPT, cache-safe doc builders, VP critique loop

import os, json, hashlib, tempfile
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from slugify import slugify

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_MAIN = os.getenv("OPENAI_MODEL_MAIN", "gpt-4.1")         # upgradeable
MODEL_MINI = os.getenv("OPENAI_MODEL_SCREENER", "gpt-4.1-mini")# fast assistant
CACHE_PATH = "gpt_suggestion_cache.json"

def _load_cache():
    if os.path.exists(CACHE_PATH):
        try: return json.load(open(CACHE_PATH, "r", encoding="utf-8")) or {}
        except: return {}
    return {}
_sugg_cache = _load_cache()

def _save_cache():
    with open(CACHE_PATH, "w", encoding="utf-8") as f: json.dump(_sugg_cache, f, indent=2)

def cache_and_return(key, value):
    _sugg_cache[key] = value; _save_cache(); return value

def clean_gpt_input(text, max_words=1000):
    return " ".join((text or "").strip().split()[:max_words])

def should_fallback_to_signal_brief(text): return len((text or "").strip()) < 50 or len((text or "").split()) < 10

def safe_file_path(base_name, prefix="insight"):
    filename = slugify(f"{prefix}-{base_name}")[:64] + ".docx"
    return os.path.join(tempfile.gettempdir(), filename)

def write_docx(content, heading):
    doc = Document()
    doc.add_heading(heading, level=1)
    for line in (content or "").split("\n"):
        if line.strip().endswith(":"): doc.add_heading(line.strip(), level=2)
        else: doc.add_paragraph(line.strip())
    return doc

def build_metadata_block(brand, trend_context=None, competitor_context=None, meta_fields=None):
    ctx = [f"Contextual Metadata:", f"- Brand: {brand}", "- Objective: Improve trust, conversion, or reduce friction.", "- Note: Use pragmatic product assumptions if data is missing."]
    if trend_context: ctx.append(f"Trend Signal: {trend_context}")
    if competitor_context: ctx.append(f"Competitor Mentioned: {competitor_context}")
    if meta_fields:
        for k,v in meta_fields.items(): ctx.append(f"- {k}: {v}")
    return "\n".join(ctx)

def generate_exec_summary():
    return ("\n\n---\n\n**Executive TL;DR**\n- What: [summary]\n- Why it matters: [impact]\n- What decision is needed: [action]")

def _chat(model, system, user, max_tokens=2000, temperature=0.3):
    return client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=temperature, max_tokens=max_tokens
    ).choices[0].message.content.strip()

def generate_gpt_doc(prompt, title):
    try:
        draft = _chat(MODEL_MAIN, title, clean_gpt_input(prompt))
        critique = f"Critique this like a VP of Product. Tighten structure, remove fluff, improve specificity, and rewrite:\n\n{draft}"
        return _chat(MODEL_MAIN, "You are a critical VP of Product.", clean_gpt_input(critique))
    except Exception as e:
        return f"⚠️ GPT Error: {e}"

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in _sugg_cache: return _sugg_cache[key]
    prompt = f"You are a senior PM at a marketplace like eBay.\nGenerate 3 concise product suggestions to improve trust or conversion.\n\nFeedback:\n{text}\n\nBrand: {brand}"
    try:
        ideas = _chat(MODEL_MINI, "Generate actionable, concrete product improvement ideas.", prompt, max_tokens=320, temperature=0.2)
        lines = [l.strip("-• ").strip() for l in ideas.split("\n") if l.strip()]
        return cache_and_return(key, lines[:3] or [ideas])
    except Exception as e:
        return [f"[GPT error: {e}]"]

def _maybe_brief(text, brand, base_filename):
    prompt = f"Turn this brief signal into a 1-page internal summary for product leadership:\n\n{text}\n\nBrand: {brand}\n\nSections:\n- Observation\n- Hypothesis\n- Strategic Importance\n- Potential Impact\n- Suggested Next Steps\n- Open Questions"
    content = generate_gpt_doc(prompt, "You summarize vague signals into a strategic brief.")
    doc = write_docx(content, "Strategic Signal Brief")
    path = safe_file_path(base_filename, prefix="brief"); doc.save(path); return path

def generate_prd_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text): return _maybe_brief(text, brand, base_filename)
    meta = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""Write a GTM-ready PRD:

{text}

{meta}

Start with a 3-bullet Executive Summary (What, Why, What Now).

Sections:
1. Overview
2. Customer Pain Point
3. Strategic Context
4. Personas Impacted
5. Proposed Solutions
6. Annotated User Journey
7. Effort Estimate (High/Medium/Low)
8. Risks / Dependencies
9. Success Metrics
10. Next Steps
11. Jobs to Be Done (JTBD)
12. Discovery-to-Delivery Phase
13. Hypothesis + Suggested Experiment
14. Confidence Rating
{generate_exec_summary()}"""
    content = generate_gpt_doc(prompt, "You are a strategic product manager writing a PRD.")
    doc = write_docx(content, "Product Requirements Document (PRD)")
    path = safe_file_path(base_filename, prefix="prd"); doc.save(path); return path

def generate_brd_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text): return _maybe_brief(text, brand, base_filename)
    meta = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""Write a BRD for marketplace feedback:

{text}

{meta}

Start with a 3-bullet Executive Summary (What, Why, What Now).

Include:
- Problem Statement
- Impacted Business Metrics
- TAM or affected user group
- Macro trends
- Strategic Bet (risk × reward)
- Strategic Fit with {brand}
- Business Solution
- ROI Estimate
- Legal / Compliance / Policy
- Stakeholders
- Next Steps
- Confidence Rating
{generate_exec_summary()}"""
    content = generate_gpt_doc(prompt, "You are a strategic business leader writing a BRD.")
    doc = write_docx(content, "Business Requirements Document (BRD)")
    path = safe_file_path(base_filename, prefix="brd"); doc.save(path); return path

def generate_prfaq_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text): return _maybe_brief(text, brand, base_filename)
    meta = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""Write an Amazon-style PRFAQ based on this insight:

{text}

{meta}

Persona: choose a concrete persona (e.g., Luca, a power buyer in Italy dealing with customs).
Include objection handling and GTM readiness checklist."""
    content = generate_gpt_doc(prompt, "You are a product marketing lead writing a PRFAQ.")
    doc = write_docx(content, "Product PRFAQ Document")
    path = safe_file_path(base_filename, prefix="faq"); doc.save(path); return path

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"Draft a JIRA bug ticket for this complaint:\n\n{text}\n\nFields: Title, Summary, Steps, Expected vs Actual, Severity."
    return generate_gpt_doc(prompt, "You are a support lead drafting a JIRA bug ticket.")

def generate_multi_signal_prd(text_list, filename, brand="eBay"):
    combined = "\n\n".join(text_list)
    return generate_prd_docx(combined, brand, filename)

def generate_cluster_prd_docx(cluster_or_card, filename):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"]); brand = cluster_or_card.get("brand","eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8]); brand = cluster_or_card[0].get("target_brand","eBay")
    return generate_prd_docx(text, brand, filename)

def generate_cluster_brd_docx(cluster_or_card, filename):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"]); brand = cluster_or_card.get("brand","eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8]); brand = cluster_or_card[0].get("target_brand","eBay")
    return generate_brd_docx(text, brand, filename)

def generate_cluster_prfaq_docx(cluster_or_card, filename):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"]); brand = cluster_or_card.get("brand","eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8]); brand = cluster_or_card[0].get("target_brand","eBay")
    return generate_prfaq_docx(text, brand, filename)
