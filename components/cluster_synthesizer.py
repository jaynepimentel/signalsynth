# cluster_synthesizer.py — robust clustering with GPT error handling + logging

import os
from collections import defaultdict
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import DBSCAN
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

model = SentenceTransformer("all-MiniLM-L6-v2")


def cluster_insights(insights, min_cluster_size=2, eps=0.4):
    enriched_texts = [
        f"{i['text']} {i.get('type_subtag', '')} {i.get('target_brand', '')} {' '.join(i.get('ideas', []))}"
        for i in insights
    ]
    embeddings = model.encode(enriched_texts, convert_to_tensor=True)
    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric="cosine").fit(embeddings.cpu().numpy())
    labels = clustering.labels_

    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)

    print(f"✅ Clustered {len(insights)} insights into {len(clustered)} groups")
    return list(clustered.values())


def gpt_label_and_summary(cluster):
    if not cluster or not client:
        return "General", "(Cluster empty or GPT client missing)"

    combined = "\n".join(i["text"] for i in cluster[:5])
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a strategic product analyst. Based on the grouped customer feedback below, provide:\n1. A clear 1-3 word thematic label (e.g. Returns, Feedback, Authentication).\n2. A 1-sentence cluster summary."},
                {"role": "user", "content": combined}
            ],
            temperature=0.3,
            max_tokens=100
        )
        content = response.choices[0].message.content.strip()
        lines = content.split("\n")

        label, summary = "General", "(No summary)"
        for line in lines:
            if "Label:" in line:
                label = line.replace("Label:", "").strip()
            elif "Summary:" in line:
                summary = line.replace("Summary:", "").strip()

        return label, summary
    except Exception as e:
        print(f"❌ GPT cluster summary error: {e}")
        return "General", f"(GPT summary failed: {e})"


def synthesize_cluster(cluster):
    label, summary = gpt_label_and_summary(cluster)
    brand = cluster[0].get("target_brand", "Unknown")
    quotes = [f"- _{i['text'][:200]}_" for i in cluster[:3]]

    idea_counter = defaultdict(int)
    for i in cluster:
        for idea in i.get("ideas", []):
            idea_counter[idea] += 1
    top_ideas = sorted(idea_counter.items(), key=lambda x: -x[1])[:3]

    scores = [i.get("score", 0) for i in cluster]
    min_score = round(min(scores), 2)
    max_score = round(max(scores), 2)

    return {
        "title": f"{label}: {summary} ({len(cluster)} mentions)",
        "theme": label,
        "brand": brand,
        "summary": summary,
        "quotes": quotes,
        "top_ideas": [i[0] for i in top_ideas],
        "score_range": f"{min_score}–{max_score}"
    }


def generate_synthesized_insights(insights):
    clusters = cluster_insights(insights)
    return [synthesize_cluster(c) for c in clusters]
