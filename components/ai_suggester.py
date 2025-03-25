# components/ai_suggester.py
import os
from dotenv import load_dotenv
import openai

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

system_prompt = """
You are a senior product manager at a major marketplace platform like eBay or Fanatics. 
Based on user feedback, identify the customer's concern and recommend specific, strategic 
product improvements or operational actions. Focus on things that would build trust, improve
conversion, or reduce friction. Use strong PM thinking.
"""

def generate_pm_ideas(text, brand="eBay"):
    if not openai.api_key:
        return ["[No API key set. Using fallback ideas]"]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Feedback from user:\n{text}\n\nBrand mentioned: {brand}"}
            ],
            temperature=0.4,
            max_tokens=300
        )
        output = response.choices[0].message.content.strip().split("\n")
        return [line.strip("- ").strip() for line in output if line.strip()]
    except Exception as e:
        return [f"[Error calling OpenAI: {e}]"]
