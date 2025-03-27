# ai_suggester.py — Upgraded PRD generator with strategic depth and formatting
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
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

def is_streamlit_mode():
    return os.getenv("RUNNING_IN_STREAMLIT") == "1"

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    if is_streamlit_mode():
        return ["[⚠️ GPT disabled in Streamlit mode — use precompute_insights.py]"]

    system_prompt = (
        "You are a senior product manager at a major marketplace like eBay. "
        "Given a piece of customer feedback, identify the pain point, map it to personas, "
        "and generate detailed product suggestions with measurable impact. Prioritize ideas that build trust, improve conversion, or reduce operational friction."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Customer feedback:\n{text}\n\nBrand: {brand}"}
            ],
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip().split("\n")
        ideas = [line.strip("-• ").strip() for line in raw if line.strip()]
        suggestion_cache[key] = ideas

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2)

        return ideas
    except Exception as e:
        return [f"[⚠️ GPT error: {str(e)}]"]

def generate_gpt_doc_content(prompt):
    if is_streamlit_mode():
        return "[⚠️ GPT document generation is disabled in Streamlit mode]"
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product leader writing robust, GTM-ready Product Requirements Documents (PRDs). Use executive-level structure, real-world complexity, and clear formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ GPT Error: {str(e)}"

def safe_file_path(base_name):
    filename = slugify(base_name)[:64] + ".docx"
    return os.path.join(tempfile.gettempdir(), filename)

def generate_prd_docx(text, brand, base_filename):
    prompt = f"""
Write a detailed, GTM-level Product Requirements Document (PRD) for the following user insight.
Make it clear, structured, and useful for cross-functional teams. Include:

- Overview
- Customer Problem (with user quotes if available)
- Strategic Context (why now, what’s at stake)
- Personas Impacted
- Proposed Solution (technical or process)
- Key UX Touchpoints (flows, screens, events)
- User Journey (step by step)
- Effort Estimate (preliminary)
- Data / Success Metrics (target metrics, telemetry)
- Risks & Mitigations
- Open Questions or Unknowns
- Suggested Experiment (if confidence is low)
- Testable Hypothesis
- Next Steps
- Jira-style Appendix or Slack channel (if applicable)

Text:
{text}

Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    doc = Document()
    doc.add_heading("Product Requirements Document (PRD)", level=1)
    for line in content.split("\n"):
        if line.strip().endswith(":"):
            doc.add_heading(line.strip(), level=2)
        else:
            doc.add_paragraph(line.strip())
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_brd_docx(text, brand, base_filename):
    prompt = f"""
Write a Business Requirements Document (BRD) for the following customer insight. Use a strategic product lens.

- Executive Summary
- Business Opportunity
- Customer Problem
- Strategic Context
- Personas
- Proposed Solution
- Revenue & Cost Impact
- Dependencies
- Legal/Privacy Considerations
- Key Stakeholders
- Risks
- Next Steps

Insight:
{text}
Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    doc = Document()
    doc.add_heading("Business Requirements Document (BRD)", level=1)
    for line in content.split("\n"):
        if line.strip().endswith(":"):
            doc.add_heading(line.strip(), level=2)
        else:
            doc.add_paragraph(line.strip())
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"""
Write a detailed JIRA bug ticket based on this customer complaint:

- Title
- Summary
- Steps to Reproduce
- Expected Result
- Actual Result
- Severity Level
- Component / Brand

Complaint:
{text}

Brand: {brand}
"""
    return generate_gpt_doc_content(prompt)
