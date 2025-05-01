# components/gpt_classifier.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

system_prompt = """
You are a senior product strategist reviewing marketplace feedback.
Given the text, classify:
1. type_tag (Complaint, Praise, Confusion, Feature Request, Discussion)
2. persona (Buyer, Seller, Collector, Grader, Support Agent, Unknown)
3. journey_stage (Discovery, Purchase, Fulfillment, Returns, Support, Unknown)
4. opportunity_tag (Search, UI, Trust, Speed, Fees, Policy, Vault, Grading, Discovery, Post-Purchase, None)
5. impact_score (1-5 based on GMV/conversion/trust impact)

Respond in this format:
Type: <type>
Persona: <persona>
Journey: <stage>
Opportunity: <tag>
"""

def enrich_with_gpt_tags(insight):
    if not client:
        return insight  # fallback — keep as-is

    text = insight.get("text", "")
    if not text.strip():
        return insight

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text.strip()[:1000]}
            ],
            temperature=0.3,
            max_tokens=200
        )
        output = response.choices[0].message.content.strip().split("\n")
        for line in output:
            if line.startswith("Type:"):
                insight["type_tag"] = line.split(":", 1)[1].strip()
            elif line.startswith("Persona:"):
                insight["persona"] = line.split(":", 1)[1].strip()
            elif line.startswith("Journey:"):
                insight["journey_stage"] = line.split(":", 1)[1].strip()
            elif line.startswith("Opportunity:"):
                insight["opportunity_tag"] = line.split(":", 1)[1].strip()
    except Exception as e:
        insight["classification_error"] = str(e)

if line.startswith("Impact Score:"):
    insight["impact_score"] = int(line.split(":")[1].strip())
    
    return insight
