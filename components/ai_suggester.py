import os
import json
import hashlib
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from slugify import slugify

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise ValueError("Missing OPENAI_API_KEY in environment variables")

client = OpenAI(api_key=OPENAI_KEY)
CACHE_PATH = "gpt_suggestion_cache.json"

# Load or initialize cache
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

SYSTEM_PM_PROMPT = (
    "You are a senior product manager at a marketplace like eBay. "
    "Generate strategic, high-impact PM ideas based on user feedback. "
    "Focus on product or operational improvements that drive trust, reduce friction, or increase conversion."
)

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(f"{text}_{brand}".encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PM_PROMPT},
                {"role": "user", "content": f"User feedback:\n{text}\n\nBrand: {brand}"}
            ],
            temperature=0.3,
            max_tokens=400
        )
        raw = response.choices[0].message.content.strip().split("\n")
        ideas = [line.strip("-• ").strip() for line in raw if line.strip()]
        suggestion_cache[key] = ideas

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2)

        return ideas

    except Exception as e:
        if "429" in str(e):
            return ["[⚠️ OpenAI rate limit hit — retry later or reduce load]"]
        elif "authentication" in str(e).lower():
            return ["[⚠️ Missing or invalid OpenAI API key]"]
        return [f"[⚠️ GPT error: {str(e)}]"]

def generate_gpt_doc_content(prompt, role="You are a senior PM writing a PRD or BRD. Be specific, strategic, and structured."):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ GPT Error: {str(e)}"

def safe_file_path(base_name):
    filename = slugify(base_name)[:64] + ".docx"
    return os.path.join(tempfile.gettempdir(), filename)

def generate_prd_docx(text, brand, base_filename):
    prompt = f"""
You are a senior product manager at eBay. Write a strategic and well-structured Product Requirements Document (PRD) based on the user feedback below.

Include the following sections:
- Overview (why this matters now)
- Customer Problem (from the feedback)
- Strategic Context (alignment with trust, conversion, or OKRs)
- Personas Impacted (e.g., sellers, buyers, support)
- Proposed Solution (clear and feasible)
- UX/Workflow Touchpoints (which parts of eBay surface are impacted)
- User Journey (end-to-end path for the persona)
- Success Metrics (quantifiable KPIs)
- Risks & Mitigations
- Testable Hypothesis
- Suggested Experiment
- Next Steps
- Jira Ticket Name and Slack Channel

Feedback:
{text}

Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    return write_doc("Product Requirements Document (PRD)", content, base_filename)

def generate_brd_docx(text, brand, base_filename):
    prompt = f"""
You are a senior product manager at eBay. Write a crisp and strategic Business Requirements Document (BRD) based on the user feedback below.

Include:
- Executive Summary (1–2 sentence business case)
- Business Opportunity (market gap, trust risk, etc.)
- Customer Problem (from the feedback)
- Market Context (how others handle this)
- Proposed Solution (simple, clear)
- Revenue or Cost Impact (estimates or directional)
- Key Stakeholders (PM, engineering, CX, trust, etc.)
- Open Questions
- Recommended Next Step (e.g., discovery sprint, pilot)

Feedback:
{text}

Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    return write_doc("Business Requirements Document (BRD)", content, base_filename)

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"""
You are a senior QA lead writing a JIRA bug ticket based on this customer complaint.

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

def write_doc(title, content, base_filename):
    doc = Document()
    doc.add_heading(title, level=1)
    for line in content.split("\n"):
        doc.add_paragraph(line)
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path
    
def generate_cluster_prd_docx(cluster, base_filename):
    cluster_texts = "\n\n".join(i.get("text", "") for i in cluster[:10])
    brand = cluster[0].get("target_brand", "eBay")

    prompt = f"""
You are a senior product manager at eBay. Write a high-level Product Requirements Document (PRD) based on a recurring customer theme.

Base this PRD on the following grouped user feedback:

{cluster_texts}

Include:
- Overview
- Customer Problem
- Strategic Context
- Personas Affected
- Proposed Solution
- UX/Workflow Touchpoints
- User Journey
- Data or Success Metrics
- Risks & Mitigations
- Suggested Experiment
- Testable Hypothesis
- Jira Ticket Name and Slack Channel

Brand: {brand}
"""
    content = generate_gpt_doc_content(prompt)
    return write_doc("Cluster-Based PRD", content, base_filename)