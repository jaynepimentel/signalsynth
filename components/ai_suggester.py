# ai_suggester.py — GPT-enhanced strategic document generator
import os
import json
import hashlib
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
from docx import Document

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CACHE_PATH = "gpt_suggestion_cache.json"

if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(text.strip().encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a senior product manager offering concise but strategic PM suggestions."},
                {"role": "user", "content": f"Customer insight:\n{text}\n\nBrand mentioned: {brand}\n\nReturn 3–5 bullet point product suggestions."}
            ],
            temperature=0.3,
            max_tokens=300
        )
        output = response.choices[0].message.content.strip().split("\n")
        suggestions = [line.strip("- ").strip() for line in output if line.strip()]
        suggestion_cache[key] = suggestions

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2)

        return suggestions
    except Exception as e:
        return [f"[❌ GPT error: {str(e)}]"]

def write_docx(content, filename, title="Product Document"):
    doc = Document()
    doc.add_heading(title, level=1)
    for line in content.strip().split("\n"):
        doc.add_paragraph(line.strip())
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer, f"{filename}.docx"

def generate_prd_docx(insight_text, brand, filename):
    prompt = f"""
You are a senior product manager at a company like eBay. Based on the following customer insight, write a robust, strategic Product Requirements Document (PRD).

Customer Insight:
"""
    prompt += f"""
---
{insight_text}
---

Sections:
1. **Overview**
2. **Customer Problem**
3. **Strategic Context**
4. **Personas Affected**
5. **Proposed Product Improvements** (3–5)
6. **User Flow Sketch (Text)**
7. **Data & Success Metrics**
8. **Risks & Mitigations**
9. **Implementation Dependencies**
10. **Testable Hypothesis**
11. **JTBD Statement**
12. **Milestone Plan** (Optional)

Write in professional product tone. Format clearly.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You write detailed, enterprise-level product requirement docs."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1200
        )
        content = response.choices[0].message.content.strip()
        return write_docx(content, filename, "Product Requirements Document (PRD)")
    except Exception as e:
        return write_docx(f"PRD generation failed: {str(e)}\n\n{insight_text}", filename, "PRD Error")

def generate_brd_docx(insight_text, brand, filename):
    prompt = f"""
You are a business product strategist. Write a strategic Business Requirements Document (BRD) based on this insight.

Insight:
---
{insight_text}
---

Include:
1. **Executive Summary**
2. **Business Objective**
3. **Customer Problem**
4. **Proposed Initiatives**
5. **Key Stakeholders**
6. **ROI / Business Impact**
7. **Assumptions / Constraints**
8. **Timeline Considerations**
9. **Next Steps**

Use clear, structured business writing.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You write high-quality BRDs for business teams."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1000
        )
        content = response.choices[0].message.content.strip()
        return write_docx(content, filename, "Business Requirements Document (BRD)")
    except Exception as e:
        return write_docx(f"BRD generation failed: {str(e)}\n\n{insight_text}", filename, "BRD Error")

def generate_jira_bug_ticket(insight_text, brand):
    prompt = f"""
You are a technical product manager. Write a JIRA-style bug ticket based on this customer complaint:

---
{insight_text}
---

Return a markdown-formatted bug with:
- Title
- Description
- Steps to Reproduce (if possible)
- Expected vs. Actual Behavior
- Suggested Fix
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You generate JIRA markdown tickets from customer complaints."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"### JIRA Bug Error\nCould not generate JIRA bug ticket: {str(e)}"
