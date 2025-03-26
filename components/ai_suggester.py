# ai_suggester.py — OpenAI v1.0+ safe with caching and quota handling
import os
import json
import hashlib
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
from docx import Document

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

system_prompt = """
You are a senior product manager at a major marketplace platform like eBay or Fanatics. 
Based on user feedback, identify the customer's concern and recommend specific, strategic 
product improvements or operational actions. Focus on things that would build trust, improve
conversion, or reduce friction. Use strong PM thinking.
"""

CACHE_PATH = "gpt_suggestion_cache.json"

# Load or initialize cache
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

def generate_pm_ideas(text, brand="eBay"):
    key = hashlib.md5(text.strip().encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    if not os.getenv("OPENAI_API_KEY"):
        return ["[No API key set — using fallback suggestion]"]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Feedback from user:\n{text}\n\nBrand mentioned: {brand}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        output = response.choices[0].message.content.strip().split("\n")
        suggestions = [line.strip("- ").strip() for line in output if line.strip()]
        suggestion_cache[key] = suggestions

        # Save to cache
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2)

        return suggestions

    except Exception as e:
        if "429" in str(e):
            return ["[⚠️ OpenAI rate limit hit — retry later or reduce load]"]
        elif "authentication" in str(e).lower():
            return ["[⚠️ Missing or invalid OpenAI API key]"]
        else:
            return [f"[Error calling OpenAI: {e}]"]

def write_docx(content, filename, title="Product Requirements Document"):
    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph(content)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer, f"{filename}.docx"

def generate_prd_docx(insight_text, brand, filename):
    prompt = f"""
    You are writing a Product Requirements Document (PRD) based on the following insight:
    ---
    {insight_text}
    ---
    The insight comes from a user mentioning the brand: {brand}.
    Please include:
    - Overview
    - Customer Pain Point
    - Strategic Context
    - Personas Impacted
    - Proposed Solutions
    - Data or Success Metrics
    - Risks / Dependencies
    - Testable Hypothesis
    - Jobs to Be Done (JTBD) statement
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product strategist generating detailed product documentation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        prd_content = response.choices[0].message.content.strip()
        return write_docx(prd_content, filename, "Product Requirements Document (PRD)")

    except Exception as e:
        fallback = f"PRD generation failed due to error: {str(e)}\n\nInsight: {insight_text}"
        return write_docx(fallback, filename, "Product Requirements Document (PRD)")
