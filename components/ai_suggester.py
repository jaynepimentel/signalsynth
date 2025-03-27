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

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    system_prompt = "You are a senior product manager at eBay. Generate strategic PM ideas based on user feedback."

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User feedback:
{text}

Brand: {brand}"}
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

def generate_gpt_doc_content(prompt, role="You are a senior PM writing a PRD or BRD. Be specific, strategic, and structured."):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ GPT Error: {str(e)}"

def safe_file_path(base_name):
    filename = slugify(base_name)[:64] + ".docx"
    return os.path.join(tempfile.gettempdir(), filename)

def generate_prd_docx(text, brand, base_filename):
    prompt = f"""Write a clear, strategic Product Requirements Document (PRD) based on the following customer feedback.

Include:
- Overview
- Customer Problem
- Strategic Context
- Personas Affected
- Proposed Solution
- UX or Workflow Touchpoints
- Success Metrics
- Risks
- Suggested Next Steps
- Jira Ticket Name and Slack Channel

Feedback:
{text}

Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    doc = Document()
    doc.add_heading("Product Requirements Document (PRD)", level=1)
    for line in content.split("\n"):
        doc.add_paragraph(line)
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_brd_docx(text, brand, base_filename):
    prompt = f"""Write a well-framed Business Requirements Document (BRD) based on this customer feedback.

Include:
- Executive Summary
- Business Opportunity
- Customer Problem
- Market Context
- Proposed Solution
- Revenue or Cost Impact
- Key Stakeholders
- Open Questions
- Recommended Next Step

Feedback:
{text}

Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    doc = Document()
    doc.add_heading("Business Requirements Document (BRD)", level=1)
    for line in content.split("\n"):
        doc.add_paragraph(line)
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"""Write a JIRA bug report based on this customer complaint.

Include:
- Title
- Summary
- Steps to Reproduce
- Expected Result
- Actual Result
- Severity
- Brand

Complaint:
{text}

Brand: {brand}
"""
    return generate_gpt_doc_content(prompt, role="You are a senior QA lead writing a JIRA bug.")