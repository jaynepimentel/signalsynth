# cluster_synthesizer.py — GPT summarization + cleaned top idea extraction

import os
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

model = SentenceTransformer("all-MiniLM-L6-v2")

def cluster_insights(insights, min_cluster_size=3):
    texts = [i.get("text", "") for i in insights]
    embeddings = model.encode(texts, convert_to_tensor=True)
    clustering = DBSCAN(eps=0.4, min_samples=min_cluster_size, metric="cosine").fit(embeddings.cpu().numpy())
    labels = clustering.labels_

    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)

    return list(clustered.values())

def summarize_cluster_with_gpt(cluster):
    if not client:
        return cluster[0]["text"][:80] + "..."

    combined = "\n".join(i["text"] for i in cluster[:5])
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Summarize the key theme of this group of user posts in one sentence."},
                {"role": "user", "content": combined}
            ],
            temperature=0.3,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(GPT summary failed: {e})"

def synthesize_cluster(cluster):
    summary = summarize_cluster_with_gpt(cluster)
    brand = cluster[0].get("target_brand", "Unknown")
    type_tag = cluster[0].get("type_tag", "Insight")
    subtype = cluster[0].get("type_subtag", "General")

    quotes = [f"- _{i.get('text', '')[:200]}_" for i in cluster[:3]]

    # Clean PM ideas
    idea_counter = defaultdict(int)
    for i in cluster:
        for idea in i.get("ideas", []):
            if idea and len(idea.strip()) > 10 and not idea.lower().startswith("customer"):
                idea_counter[idea.strip()] += 1

    top_ideas = sorted(idea_counter.items(), key=lambda x: -x[1])[:3]

    scores = [i.get("score", 0) for i in cluster]
    min_score = round(min(scores), 2)
    max_score = round(max(scores), 2)

    return {
        "title": f"{type_tag}: {subtype} issue ({len(cluster)} mentions)",
        "brand": brand,
        "summary": summary,
        "quotes": quotes,
        "top_ideas": [i[0] for i in top_ideas],
        "score_range": f"{min_score}–{max_score}"
    }

def generate_synthesized_insights(insights):
    clusters = cluster_insights(insights)
    return [synthesize_cluster(c) for c in clusters]