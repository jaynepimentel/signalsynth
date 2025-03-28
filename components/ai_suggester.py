# ai_suggester.py — AI-powered PRD/BRD/PRFAQ/JIRA generation with caching and retries
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

def cache_and_return(key, value):
    suggestion_cache[key] = value
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(suggestion_cache, f, indent=2)
    return value

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
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": title},
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

def write_docx(content, heading):
    doc = Document()
    doc.add_heading(heading, level=1)
    for line in content.split("\n"):
        if line.strip().endswith(":"):
            doc.add_heading(line.strip(), level=2)
        else:
            doc.add_paragraph(line.strip())
    return doc

def generate_prd_docx(text, brand, base_filename):
    prompt = f"""
Write a professional Product Requirements Document (PRD) for a product team working on a major marketplace like eBay. Use the user insight below as the starting point.

---
User Insight:
{text}

---
Metadata:
- Brand: {brand}
- Goal: Improve user experience, trust, or conversion

---
Include the following PRD sections:
1. Overview
2. Customer Pain Point
3. Strategic Context
4. Personas Impacted
5. Proposed Solutions
6. Annotated User Journey
7. Effort Estimate (High/Med/Low)
8. Risks / Dependencies
9. Data or Success Metrics
10. Recommended Next Steps
11. Jobs to Be Done (JTBD)
12. Discovery-to-Delivery Phase (Double Diamond classification)
13. Testable Hypothesis and Suggested Experiment
"""
    content = generate_gpt_doc(prompt, "You are a product lead writing a strategic PRD.")
    doc = write_docx(content, "Product Requirements Document (PRD)")
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_brd_docx(text, brand, base_filename):
    prompt = f"""
Write a Business Requirements Document (BRD) based on this marketplace customer feedback:

---
User Insight:
{text}

---
Include:
- Executive Summary
- Problem Statement
- Market Opportunity
- Strategic Fit with {brand}
- Proposed Business Solution
- ROI Estimate
- Stakeholders
- Legal or Policy Constraints
- Next Steps
"""
    content = generate_gpt_doc(prompt, "You are a business strategist writing a BRD.")
    doc = write_docx(content, "Business Requirements Document (BRD)")
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_prfaq_docx(text, brand, base_filename):
    prompt = f"""
Write a PRFAQ document for a marketplace team launching a new feature based on the user insight below.

---
User Insight:
{text}

---
Include the following sections:
1. Press Release:
   - Headline
   - Subheadline
   - Opening Paragraph
   - Customer Quote
   - Internal Quote
2. FAQ:
   - Customer Questions and Answers
   - Internal Stakeholder Questions and Answers
3. Launch Readiness Checklist (bullets)
"""
    content = generate_gpt_doc(prompt, "You are a product marketing lead creating a launch-ready PRFAQ.")
    doc = write_docx(content, "Product PRFAQ Document")
    file_path = safe_file_path(base_filename)
    doc.save(file_path)
    return file_path

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"Turn this user complaint into a JIRA ticket:\n{text}\n\nInclude: Title, Summary, Steps to Reproduce, Expected vs. Actual Results, Severity."
    return generate_gpt_doc(prompt, "You are a support lead writing a bug report.")

def generate_cluster_prd_docx(cluster, filename):
    text = "\n\n".join(i["text"] for i in cluster[:8])
    return generate_prd_docx(text, cluster[0].get("target_brand", "eBay"), filename)

def generate_cluster_brd_docx(cluster, filename):
    text = "\n\n".join(i["text"] for i in cluster[:8])
    return generate_brd_docx(text, cluster[0].get("target_brand", "eBay"), filename)

def generate_cluster_prfaq_docx(cluster, filename):
    text = "\n\n".join(i["text"] for i in cluster[:8])
    return generate_prfaq_docx(text, cluster[0].get("target_brand", "eBay"), filename)
