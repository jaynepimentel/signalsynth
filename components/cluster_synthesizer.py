# cluster_synthesizer.py — semantic clustering + AI insight cards
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import DBSCAN
from collections import defaultdict
import numpy as np

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


def synthesize_cluster(cluster):
    summary = cluster[0]['text'][:100] + "..."
    brand = cluster[0].get("target_brand", "Unknown")
    type_tag = cluster[0].get("type_tag", "Insight")
    subtype = cluster[0].get("type_subtag", "General")

    quotes = [f"- _{i['text'][:200]}_" for i in cluster[:3]]

    ideas = []
    for i in cluster:
        ideas.extend(i.get("ideas", []))
    idea_counter = defaultdict(int)
    for idea in ideas:
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
    cards = [synthesize_cluster(c) for c in clusters]
    return cards
