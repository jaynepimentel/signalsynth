# ai_suggester.py — Enhanced with meta-tagging, fallback handling, multi-signal support, and cleaner GPT prep
import os
import hashlib
import json
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from slugify import slugify

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CACHE_PATH = "gpt_suggestion_cache.json"

if os.path.exists(CACHE_PATH):
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()
            suggestion_cache = json.loads(content) if content else {}
    except json.JSONDecodeError:
        suggestion_cache = {}
else:
    suggestion_cache = {}

def is_streamlit_mode():
    return os.getenv("RUNNING_IN_STREAMLIT") == "1"

def cache_and_return(key, value):
    suggestion_cache[key] = value
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(suggestion_cache, f, indent=2)
    return value

def clean_gpt_input(text, max_words=1000):
    return " ".join(text.strip().split()[:max_words])

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    if is_streamlit_mode():
        return ["[⚠️ GPT disabled in Streamlit mode — use precompute_insights.py]"]

    prompt = f"You are a senior product manager at a marketplace like eBay. Based on the user feedback below, generate 3 concise product suggestions that would improve trust, conversion, or reduce friction.\n\nFeedback:\n{text}\n\nBrand: {brand}"

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
        return [f"[⚠️ GPT error: {str(e)}]"]

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

        critique_prompt = f"Now critique this like a VP of Product. What's weak, missing, or unclear? Then rewrite and improve it.\n\n{draft}"
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

def should_fallback_to_signal_brief(text):
    return len(text.strip()) < 50 or len(text.split()) < 10

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

def generate_exec_summary():
    return "\n\n---\n\n**Executive TL;DR**\n- What: [summary]\n- Why it matters: [impact]\n- What decision is needed: [action]"

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
Write a Business Requirements Document (BRD) based on the marketplace user feedback below:

{text}

{metadata}

Start with a 3-bullet Executive Summary (What, Why, What Now).

Sections:
- Executive Summary
- Problem Statement
- Market Opportunity
- Strategic Fit with {brand}
- Business Solution
- ROI Estimate
- Stakeholders
- Legal/Policy Constraints
- Next Steps
- Confidence Rating
{generate_exec_summary()}
"""
    content = generate_gpt_doc(prompt, "You are a strategic business lead writing a BRD.")
    doc = write_docx(content, "Business Requirements Document (BRD)")
    file_path = safe_file_path(base_filename, prefix="brd")
    doc.save(file_path)
    return file_path

def generate_prfaq_docx(text, brand, base_filename, trend_context=None, competitor_context=None, meta_fields=None):
    if should_fallback_to_signal_brief(text):
        return generate_signal_brief_docx(text, brand, base_filename)

    metadata = build_metadata_block(brand, trend_context, competitor_context, meta_fields)
    prompt = f"""
Write an Amazon-style PRFAQ document for a new product launch based on this feedback:

{text}

{metadata}

Start with a 3-bullet Executive Summary (What, Why, What Now).

Sections:
1. Press Release:
   - Headline
   - Subheadline
   - Opening Paragraph
   - Customer Quote
   - Internal Quote
2. FAQ:
   - External Customer Q&A
   - Internal Team Q&A
3. Launch Checklist (bulleted)
4. Confidence Rating
{generate_exec_summary()}
"""
    content = generate_gpt_doc(prompt, "You are a product marketing lead writing a PRFAQ.")
    doc = write_docx(content, "Product PRFAQ Document")
    file_path = safe_file_path(base_filename, prefix="faq")
    doc.save(file_path)
    return file_path

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"Turn this customer complaint into a JIRA ticket:\n{text}\n\nInclude: Title, Summary, Steps to Reproduce, Expected vs. Actual Result, Severity."
    return generate_gpt_doc(prompt, "You are a support agent writing a bug report.")

def generate_multi_signal_prd(text_list, filename, brand="eBay"):
    text = "\n\n".join(text_list)
    return generate_prd_docx(text, brand, filename)

def generate_cluster_prd_docx(cluster, filename):
    text = "\n\n".join(i["text"] for i in cluster[:8])
    brand = cluster[0].get("target_brand", "eBay")
    return generate_prd_docx(text, brand, filename)

def generate_cluster_brd_docx(cluster, filename):
    text = "\n\n".join(i["text"] for i in cluster[:8])
    brand = cluster[0].get("target_brand", "eBay")
    return generate_brd_docx(text, brand, filename)

def generate_cluster_prfaq_docx(cluster, filename):
    text = "\n\n".join(i["text"] for i in cluster[:8])
    brand = cluster[0].get("target_brand", "eBay")
    return generate_prfaq_docx(text, brand, filename)
