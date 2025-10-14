# components/gpt_classifier.py — env-driven classifier + fixed scope bug

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
MODEL_TAGGER = os.getenv("OPENAI_MODEL_TAGGER", "gpt-4.1-mini")

SYSTEM_PROMPT = """You are a senior product strategist reviewing marketplace feedback.
Classify:
1) Type (Complaint, Praise, Confusion, Feature Request, Discussion)
2) Persona (Buyer, Seller, Collector, Grader, Support Agent, Unknown)
3) Journey (Discovery, Purchase, Fulfillment, Returns, Support, Unknown)
4) Opportunity (Search, UI, Trust, Speed, Fees, Policy, Vault, Grading, Discovery, Post-Purchase, None)
5) Impact Score (1-5)

Respond exactly:
Type: <type>
Persona: <persona>
Journey: <stage>
Opportunity: <tag>
Impact Score: <1-5>"""

def enrich_with_gpt_tags(insight: dict) -> dict:
    if not client: return insight
    text = (insight.get("text") or "").strip()
    if not text: return insight
    try:
        out = client.chat.completions.create(
            model=MODEL_TAGGER,
            messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":text[:1200]}],
            temperature=0.2, max_tokens=220
        ).choices[0].message.content.strip().splitlines()
        for line in out:
            if line.startswith("Type:"):        insight["type_tag"] = line.split(":",1)[1].strip()
            elif line.startswith("Persona:"):   insight["persona"] = line.split(":",1)[1].strip()
            elif line.startswith("Journey:"):   insight["journey_stage"] = line.split(":",1)[1].strip()
            elif line.startswith("Opportunity:"): insight["opportunity_tag"] = line.split(":",1)[1].strip()
            elif line.startswith("Impact Score:"):
                try: insight["impact"] = int(line.split(":",1)[1].strip())
                except: pass
    except Exception as e:
        insight["classification_error"] = str(e)
    return insight