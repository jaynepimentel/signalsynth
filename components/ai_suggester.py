import os
import hashlib
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CACHE_PATH = "gpt_suggestion_cache.json"

if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        suggestion_cache = json.load(f)
else:
    suggestion_cache = {}

def generate_pm_ideas(text, brand="eBay", sentiment="Neutral"):
    key = hashlib.md5(f"{text}_{brand}_{sentiment}".encode()).hexdigest()
    if key in suggestion_cache:
        return suggestion_cache[key]

    system_prompt = """
You are a senior product manager at eBay or a major marketplace. Analyze the user's feedback and generate strategic PM ideas to address it.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Customer feedback:\n{text}\n\nBrand: {brand}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        raw = response.choices[0].message.content.strip().split("\n")
        ideas = [line.strip("-• ").strip() for line in raw if line.strip()]
        suggestion_cache[key] = ideas

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(suggestion_cache, f, indent=2)
        return ideas

    except Exception as e:
        return [f"[⚠️ GPT error: {str(e)}]"]

def generate_prd(text, brand="eBay"):
    prompt = f"""
You are a senior product manager. Write a Product Requirements Document (PRD) for the following customer insight. Use this format:

Overview:
Customer Pain Point:
Strategic Context:
Personas Affected:
Proposed Solution:
User Journey:
Effort Estimate:
Success Metrics:
Risks:
Next Steps:

Customer insight:
{text}
Brand mentioned: {brand}
"""
    return call_gpt(prompt)

def generate_brd(text, brand="eBay"):
    prompt = f"""
You are a business strategy leader. Write a Business Requirements Document (BRD) based on this customer insight. Include:

Executive Summary:
Business Opportunity:
Customer Problem:
Market Context:
Proposed Solution:
Revenue or Cost Impact:
Key Stakeholders:
Open Questions:

Customer insight:
{text}
Brand mentioned: {brand}
"""
    return call_gpt(prompt)

def generate_jira_bug_ticket(text, brand="eBay"):
    prompt = f"""
You are a technical support lead. Write a JIRA bug report using this customer complaint. Include:

Title:
Summary:
Steps to Reproduce:
Expected Result:
Actual Result:
Severity:
Related Brand: {brand}

Customer complaint:
{text}
"""
    return call_gpt(prompt)

def call_gpt(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an experienced product manager."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=700
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[❌ GPT error: {str(e)}]"