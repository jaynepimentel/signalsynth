# components/ai_suggester.py - env-driven GPT, cache-safe doc builders, VP critique loop

import os, json, hashlib, tempfile
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from slugify import slugify

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

MODEL_MAIN = os.getenv("OPENAI_MODEL_MAIN", "gpt-5.1")
MODEL_MINI = os.getenv("OPENAI_MODEL_SCREENER", "gpt-5.1-mini")
CACHE_PATH = "gpt_suggestion_cache.json"


def _load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception:
            return {}
    return {}


_sugg_cache = _load_cache()


def _save_cache():
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_sugg_cache, f, indent=2)


def cache_and_return(key, value):
    _sugg_cache[key] = value
    _save_cache()
    return value


def clean_gpt_input(text, max_words=1000):
    return " ".join((text or "").strip().split()[:max_words])


def should_fallback_to_signal_brief(text):
    t = (text or "").strip()
    return len(t) < 50 or len(t.split()) < 10


def safe_file_path(base_name, prefix="insight"):
    filename = slugify(f"{prefix}-{base_name}")[:64] + ".docx"
    return os.path.join(tempfile.gettempdir(), filename)


def write_docx(content, heading):
    doc = Document()
    doc.add_heading(heading, level=1)
    for line in (content or "").split("\n"):
        if line.strip().endswith(":"):
            doc.add_heading(line.strip(), level=2)
        else:
            doc.add_paragraph(line.strip())
    return doc


def build_metadata_block(brand, trend_context=None, competitor_context=None, meta_fields=None):
    ctx = [
        "Contextual Metadata:",
        f"- Brand: {brand}",
        "- Objective: Improve trust, conversion, or reduce friction.",
        "- Note: Use pragmatic product assumptions if data is missing.",
    ]
    if trend_context:
        ctx.append(f"Trend Signal: {trend_context}")
    if competitor_context:
        ctx.append(f"Competitor Mentioned: {competitor_context}")
    if meta_fields:
        for k, v in meta_fields.items():
            ctx.append(f"- {k}: {v}")
    return "\n".join(ctx)


def generate_exec_summary():
    return (
        "\n\n---\n\n**Executive TL;DR**\n"
        "- What: [summary]\n- Why it matters: [impact]\n- What decision is needed: [action]"
    )


# ------------------------------
# Core chat helper (safe when no API key)
# ------------------------------
def _chat(model, system, user, max_completion_tokens=2000, temperature=0.3):
    """
    Wrapper around chat.completions.create that uses max_completion_tokens
    so it works with newer models like gpt-5.1 and newer models.

    """
    if client is None:
        # Offline or no key: return a stub so the pipeline does not break
        return f"[LLM disabled] {system}\n\n{user[:800]}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def generate_gpt_doc(prompt, title):
    try:
        draft = _chat(
            MODEL_MAIN,
            title,
            clean_gpt_input(prompt),
            max_completion_tokens=2000,
            temperature=0.3,
        )
        # If running in fallback or offline, skip critique loop
        if draft.startswith("[LLM disabled]"):
            return draft

        critique = (
            "Critique like a VP of Product. Tighten structure, remove fluff, improve specificity, and rewrite:\n\n"
            f"{draft}"
        )
        return _chat(
            MODEL_MAIN,
            "You are a critical VP of Product.",
            clean_gpt_input(critique),
            max_completion_tokens=2000,
            temperature=0.3,
        )
    except Exception as e:
        return f"⚠️ GPT Error: {e}"


def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in _sugg_cache:
        return _sugg_cache[key]

    prompt = (
        "You are a senior PM at a marketplace like eBay.\n"
        "Generate 3 concise, concrete product suggestions to improve trust or conversion.\n\n"
        f"Feedback:\n{text}\n\nBrand: {brand}"
    )
    try:
        ideas = _chat(
            MODEL_MINI,
            "Generate actionable, concrete product improvement ideas.",
            prompt,
            max_completion_tokens=320,
            temperature=0.2,
        )
        # If offline stub, just return one idea with trimmed prompt context
        if ideas.startswith("[LLM disabled]"):
            return cache_and_return(key, [ideas[:240]])

        lines = [l.strip("-• ").strip() for l in ideas.split("\n") if l.strip()]
        return cache_and_return(key, (lines[:3] or [ideas]))
    except Exception as e:
        return [f"[GPT error: {e}]"]


# --- compat: simple batch wrapper so precompute_insights.py can import it ---
def generate_pm_ideas_batch(texts, brand="eBay"):
    """
    Batch-safe wrapper. Returns a list of idea lists (one list per input text).
    Falls back gracefully if any single suggestion fails.
    """
    results = []
    for t in (texts or []):
        try:
            results.append(generate_pm_ideas(text=t, brand=brand))
        except Exception as e:
            results.append([f"[GPT error: {e}]"])
    return results


def _maybe_brief(text, brand, base_filename):
    prompt = (
        "Turn this brief signal into a 1-page internal summary for product leadership.\n\n"
        f"{text}\n\nBrand: {brand}\n\nSections:\n"
        "- Observation\n- Hypothesis\n- Strategic Importance\n- Potential Impact\n- Suggested Next Steps\n- Open Questions"
    )
    content = generate_gpt_doc(prompt, "You summarize vague signals into a strategic brief.")
    doc = write_docx(content, "Strategic Signal Brief")
    path = safe_file_path(base_filename, prefix="brief")
    doc.save(path)
    return path


def generate_prd_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return _maybe_brief(text, brand, base_filename)
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
    path = safe_file_path(base_filename, prefix="prd")
    doc.save(path)
    return path


def generate_brd_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return _maybe_brief(text, brand, base_filename)
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
    path = safe_file_path(base_filename, prefix="brd")
    doc.save(path)
    return path


def generate_prfaq_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return _maybe_brief(text, brand, base_filename)
    meta = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""Write an Amazon-style PRFAQ based on this insight:

{text}

{meta}

Persona: choose a concrete persona (e.g., Luca, a power buyer in Italy dealing with customs).
Include objection handling and GTM readiness checklist."""
    content = generate_gpt_doc(prompt, "You are a product marketing lead writing a PRFAQ.")
    doc = write_docx(content, "Product PRFAQ Document")
    path = safe_file_path(base_filename, prefix="faq")
    doc.save(path)
    return path


def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = (
        "Draft a JIRA bug ticket for this complaint:\n\n"
        f"{text}\n\nFields: Title, Summary, Steps, Expected vs Actual, Severity."
    )
    return generate_gpt_doc(prompt, "You are a support lead drafting a JIRA bug ticket.")


def generate_multi_signal_prd(text_list, filename, brand="eBay"):
    combined = "\n\n".join(text_list)
    return generate_prd_docx(combined, brand, filename)


def _cluster_text_and_brand(cluster_or_card):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"])
        brand = cluster_or_card.get("brand", "eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8])
        brand = cluster_or_card[0].get("target_brand", "eBay")
    return text, brand


def generate_cluster_prd_docx(cluster_or_card, filename):
    text, brand = _cluster_text_and_brand(cluster_or_card)
    return generate_prd_docx(text, brand, filename)


def generate_cluster_brd_docx(cluster_or_card, filename):
    text, brand = _cluster_text_and_brand(cluster_or_card)
    return generate_brd_docx(text, brand, filename)


def generate_cluster_prfaq_docx(cluster_or_card, filename):
    text, brand = _cluster_text_and_brand(cluster_or_card)
    return generate_prfaq_docx(text, brand, filename)
