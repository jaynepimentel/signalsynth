# cluster_synthesizer.py — GPT-tuned summarization of insight clusters
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import DBSCAN
from collections import defaultdict
import numpy as np
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

model = SentenceTransformer("all-MiniLM-L6-v2")

def cluster_insights(insights, min_cluster_size=3):
    texts = [i['text'] for i in insights]
    embeddings = model.encode(texts, convert_to_tensor=True)

    clustering = DBSCAN(eps=0.4, min_samples=min_cluster_size, metric="cosine").fit(embeddings.cpu().numpy())
    labels = clustering.labels_

    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)

    return list(clustered.values())

def summarize_cluster_with_gpt(cluster):
    combined_texts = "
".join(i["text"] for i in cluster[:5])
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Summarize the key theme of this group of user posts in 1 sentence."},
                {"role": "user", "content": combined_texts}
            ],
            temperature=0.3,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except:
        return cluster[0]["text"][:80] + "..."

def synthesize_cluster(cluster):
    summary = summarize_cluster_with_gpt(cluster)
    brand = cluster[0].get("target_brand", "Unknown")
    type_tag = cluster[0].get("type_tag", "Insight")
    subtype = cluster[0].get("type_subtag", "General")
    quotes = [f"- _{i['text'][:200]}_" for i in cluster[:3]]
    idea_counter = defaultdict(int)
    for i in cluster:
        for idea in i.get("ideas", []):
            idea_counter[idea] += 1
    top_ideas = sorted(idea_counter.items(), key=lambda x: -x[1])[:2]
    return {
        "title": f"{type_tag}: {subtype} issue ({len(cluster)} mentions)",
        "brand": brand,
        "summary": summary,
        "quotes": quotes,
        "top_ideas": [i[0] for i in top_ideas]
    }

def generate_synthesized_insights(insights):
    clusters = cluster_insights(insights)
    return [synthesize_cluster(c) for c in clusters]