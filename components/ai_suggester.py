# ai_suggester.py — Enhanced GPT doc generation, insight utilities, and strategic modeling

import os
import json
import hashlib
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from slugify import slugify

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CACHE_PATH = "gpt_suggestion_cache.json"

# Load or initialize cache
if os.path.exists(CACHE_PATH):
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()
            suggestion_cache = json.loads(content) if content else {}
    except json.JSONDecodeError:
        suggestion_cache = {}
else:
    suggestion_cache = {}

# ─────────────────────────────────────
# 🔧 UTILS

def is_streamlit_mode():
    return os.getenv("RUNNING_IN_STREAMLIT") == "1"

def cache_and_return(key, value):
    suggestion_cache[key] = value
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(suggestion_cache, f, indent=2)
    return value

def clean_gpt_input(text, max_words=1000):
    return " ".join(text.strip().split()[:max_words])

def should_fallback_to_signal_brief(text):
    return len(text.strip()) < 50 or len(text.split()) < 10

def safe_file_path(base_name, prefix="insight"):
    filename = slugify(f"{prefix}-{base_name}")[:64] + ".docx"
    return os.path.join(tempfile.gettempdir(), filename)

def write_docx(content, heading):
    doc = Document()
    doc.add_heading(heading, level=1)
    for line in content.split("\n"):
        if line.strip().endswith(":"):
            doc.add_heading(line.strip(), level=2)
        else:
            doc.add_paragraph(line.strip())
    return doc

def build_metadata_block(brand, trend_context=None, competitor_context=None, meta_fields=None):
    context = f"""
Contextual Metadata:
- Brand: {brand}
- Objective: Improve trust, conversion, or reduce friction.
- Note: If any data is missing, make smart assumptions using product best practices.
"""
    if trend_context:
        context += f"\nTrend Signal: {trend_context}"
    if competitor_context:
        context += f"\nCompetitor Mentioned: {competitor_context}"
    if meta_fields:
        for k, v in meta_fields.items():
            context += f"\n- {k}: {v}"
    return context

def generate_exec_summary():
    return "\n\n---\n\n**Executive TL;DR**\n- What: [summary]\n- Why it matters: [impact]\n- What decision is needed: [action]"

# ─────────────────────────────────────
# ✨ GPT Utilities

def generate_gpt_doc(prompt, title):
    if is_streamlit_mode():
        return "⚠️ GPT doc generation is disabled in Streamlit mode."
    try:
        draft = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": title},
                {"role": "user", "content": clean_gpt_input(prompt)}
            ],
            temperature=0.3,
            max_tokens=2000
        ).choices[0].message.content.strip()

        critique_prompt = f"Critique this like a VP of Product. What’s weak, missing, or unclear? Rewrite and improve it.\n\n{draft}"
        improved = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a critical VP of Product."},
                {"role": "user", "content": clean_gpt_input(critique_prompt)}
            ],
            temperature=0.3,
            max_tokens=2000
        ).choices[0].message.content.strip()

        return improved
    except Exception as e:
        return f"⚠️ GPT Error: {str(e)}"

def clarify_insight(text):
    prompt = f"Rewrite this vague user feedback in a clearer, more specific way:\n\n{text}"
    return generate_gpt_doc(prompt, "You are rewriting vague customer input to help a PM understand it better.")

def suggest_tags(text):
    prompt = f"""Suggest 3–5 concise product tags or themes (in lowercase-hyphenated form) that describe this user feedback:\n\n{text}"""
    return generate_gpt_doc(prompt, "You are tagging product signals with thematic keywords.")

# ─────────────────────────────────────
# 🧠 Product Idea Suggestions

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    if is_streamlit_mode():
        return ["[GPT disabled in Streamlit mode — use precompute_insights.py]"]

    prompt = f"""You are a senior product manager at a marketplace like eBay. 
Based on the user feedback below, generate 3 concise product suggestions that would improve trust, conversion, or reduce friction.

Feedback:
{text}

Brand: {brand}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Generate actionable product improvement ideas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        ideas = [line.strip("-• ").strip() for line in response.choices[0].message.content.strip().split("\n") if line.strip()]
        return cache_and_return(key, ideas)
    except Exception as e:
        return [f"[GPT error: {str(e)}]"]

# ─────────────────────────────────────
# 📄 Strategic Document Generators

def generate_signal_brief_docx(text, brand, base_filename):
    prompt = f"""
Turn this brief user signal into a 1-page internal summary for product leadership.

User Input:
{text}

Brand: {brand}

Format:
- Observation
- Hypothesis
- Strategic Importance
- Potential Impact
- Suggested Next Steps
- Open Questions to Validate
"""
    content = generate_gpt_doc(prompt, "You are summarizing a vague signal into a strategic product brief.")
    doc = write_docx(content, "Strategic Signal Brief")
    file_path = safe_file_path(base_filename, prefix="brief")
    doc.save(file_path)
    return file_path

def generate_prd_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return generate_signal_brief_docx(text, brand, base_filename)

    metadata = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""
Write a GTM-ready Product Requirements Document (PRD) for the following user insight:

{text}

{metadata}

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
{generate_exec_summary()}
"""
    content = generate_gpt_doc(prompt, "You are a strategic product manager writing a PRD.")
    doc = write_docx(content, "Product Requirements Document (PRD)")
    file_path = safe_file_path(base_filename, prefix="prd")
    doc.save(file_path)
    return file_path

def generate_brd_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return generate_signal_brief_docx(text, brand, base_filename)

    metadata = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""
Write a Business Requirements Document (BRD) based on this marketplace user feedback:

{text}

{metadata}

Start with a 3-bullet Executive Summary (What, Why, What Now).

Include:
- Problem Statement
- Impacted Business Metrics (e.g., GMV, CSAT, conversion)
- Total Addressable Market (TAM) or affected user group
- Relevant market/macro trends influencing urgency
- Strategic Bet Framing (risk × reward)
- Strategic Fit with {brand}
- Business Solution Description
- ROI Estimate
- Legal / Compliance / Policy Constraints
- Stakeholders
- Next Steps
- Confidence Rating
{generate_exec_summary()}
"""
    content = generate_gpt_doc(prompt, "You are a strategic business leader writing a BRD.")
    doc = write_docx(content, "Business Requirements Document (BRD)")
    file_path = safe_file_path(base_filename, prefix="brd")
    doc.save(file_path)
    return file_path

def generate_prfaq_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return generate_signal_brief_docx(text, brand, base_filename)

    metadata = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""
Write an Amazon-style PRFAQ for a proposed product launch based on this insight.

{text}

{metadata}

Persona: Choose a specific user persona (e.g., Luca, a power buyer in Italy dealing with customs).
Anticipate objections and include GTM launch readiness context.

Sections:
1. Press Release:
   - Headline
   - Subheadline
   - Opening Paragraph
   - Customer Quote (persona)
   - Internal Quote (PM or VP)

2. FAQ:
   - Customer Q&A (at least 5)
   - Internal Q&A (timing, risks)
   - Objection Handling

3. GTM Launch Checklist (Legal, Ops, Comms)

4. Confidence Rating
{generate_exec_summary()}
"""
    content = generate_gpt_doc(prompt, "You are a product marketing lead writing a PRFAQ.")
    doc = write_docx(content, "Product PRFAQ Document")
    file_path = safe_file_path(base_filename, prefix="faq")
    doc.save(file_path)
    return file_path

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"""
Write a JIRA bug ticket based on this user complaint:

{text}

Include:
- Title
- Summary
- Steps to Reproduce
- Expected vs. Actual Result
- Severity Estimate
"""
    return generate_gpt_doc(prompt, "You are a support lead drafting a JIRA bug ticket.")

# ─────────────────────────────────────
# 🔗 Cluster + Bundle Support

def generate_multi_signal_prd(text_list, filename, brand="eBay"):
    combined = "\n\n".join(text_list)
    return generate_prd_docx(combined, brand, filename)

def generate_cluster_prd_docx(cluster_or_card, filename):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"])
        brand = cluster_or_card.get("brand", "eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8])
        brand = cluster_or_card[0].get("target_brand", "eBay")
    return generate_prd_docx(text, brand, filename)

def generate_cluster_brd_docx(cluster_or_card, filename):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"])
        brand = cluster_or_card.get("brand", "eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8])
        brand = cluster_or_card[0].get("target_brand", "eBay")
    return generate_brd_docx(text, brand, filename)

def generate_cluster_prfaq_docx(cluster_or_card, filename):
    if isinstance(cluster_or_card, dict) and "quotes" in cluster_or_card:
        text = "\n\n".join(q.strip("- _") for q in cluster_or_card["quotes"])
        brand = cluster_or_card.get("brand", "eBay")
    else:
        text = "\n\n".join(i["text"] for i in cluster_or_card[:8])
        brand = cluster_or_card[0].get("target_brand", "eBay")
    return generate_prfaq_docx(text, brand, filename)
