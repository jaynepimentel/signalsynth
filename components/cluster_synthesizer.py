# cluster_synthesizer.py — Optimized clustering with caching, lazy GPT, and faster embeddings

import os
from collections import defaultdict, Counter
from sklearn.cluster import DBSCAN
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from itertools import combinations
import hashlib
from functools import lru_cache

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

model = None
if os.getenv("RUNNING_IN_STREAMLIT") != "1":
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("intfloat/e5-base-v2")
    except Exception as e:
        print("❌ Failed to load SentenceTransformer:", e)
else:
    print("⚠️ Skipping model load — running in Streamlit environment.")

COHERENCE_THRESHOLD = 0.68
RECLUSTER_EPS = 0.30

@lru_cache(maxsize=2048)
def get_embedding(text):
    return model.encode([text], convert_to_tensor=True)[0].cpu().numpy()

def cluster_by_subtag_then_embed(insights, min_cluster_size=3):
    if not model:
        print("⚠️ Embedding model unavailable. Skipping clustering.")
        return []

    grouped = defaultdict(list)
    for i in insights:
        for subtag in i.get("type_subtags", [i.get("type_subtag", "General")]):
            grouped[subtag].append(i)

    all_clusters = []
    for subtag, group in grouped.items():
        if len(group) < min_cluster_size:
            continue
        clusters = cluster_insights(group, min_cluster_size=min_cluster_size)
        for c in clusters:
            coherent, score = is_semantically_coherent(c, return_score=True)
            all_clusters.append((c, {
                "coherent": coherent,
                "was_reclustered": False,
                "avg_similarity": score
            }))
    return all_clusters

def cluster_insights(insights, min_cluster_size=3, eps=0.38):
    if not model:
        return []
    texts = [i.get("text", "")[:220] for i in insights]
    embeddings = np.array([get_embedding(t) for t in texts])
    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric="cosine").fit(embeddings)
    labels = clustering.labels_

    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)

    return list(clustered.values())

def is_semantically_coherent(cluster, return_score=False):
    if not model:
        return (False, 0.0) if return_score else False
    if len(cluster) <= 2:
        return (True, 1.0) if return_score else True
    texts = [i["text"] for i in cluster]
    embeddings = np.array([get_embedding(t) for t in texts])
    sim_matrix = np.inner(embeddings, embeddings)
    upper_triangle = sim_matrix[np.triu_indices(len(texts), k=1)]
    avg_similarity = upper_triangle.mean()
    return (avg_similarity >= COHERENCE_THRESHOLD, avg_similarity) if return_score else avg_similarity >= COHERENCE_THRESHOLD

def generate_cluster_metadata(cluster):
    if not client:
        return {
            "title": cluster[0]["text"][:80] + "...",
            "theme": "General",
            "problem": "Could not generate problem statement."
        }
    combined = "\n".join(i["text"] for i in cluster[:6])
    prompt = (
        "You are a senior product manager reviewing a cluster of user feedback. For the following grouped posts, "
        "generate:\n1. A concise title (max 10 words)\n2. A theme tag\n3. A clear problem statement that could go in a PRD\n"
        f"\nPosts:\n{combined}\n\nFormat your response as:\nTitle: ...\nTheme: ...\nProblem: ..."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a senior product strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        lines = response.choices[0].message.content.strip().split("\n")
        return {
            "title": lines[0].replace("Title:", "").strip() or "Untitled Cluster",
            "theme": lines[1].replace("Theme:", "").strip() or "General",
            "problem": lines[2].replace("Problem:", "").strip() or "No problem statement provided."
        }
    except Exception as e:
        return {
            "title": "(GPT Error)",
            "theme": "Unknown",
            "problem": str(e)
        }

def synthesize_cluster(cluster):
    metadata = {
        "title": cluster[0]["text"][:80] + "...",
        "theme": "General",
        "problem": "Click to generate with GPT"
    }

    brand = cluster[0].get("target_brand", "Unknown")
    type_tag = cluster[0].get("type_tag", "Insight")
    quotes = [f"- _{i.get('text', '')[:220]}_" for i in cluster[:3]]

    idea_counter = defaultdict(int)
    for i in cluster:
        for idea in i.get("ideas", []):
            if idea and len(idea.strip()) > 10 and not idea.lower().startswith("customer"):
                idea_counter[idea.strip()] += 1
    top_ideas = sorted(idea_counter.items(), key=lambda x: -x[1])[:5]

    scores = [i.get("score", 0) for i in cluster]
    min_score = round(min(scores), 2)
    max_score = round(max(scores), 2)

    personas = list({i.get("persona", "Unknown") for i in cluster})
    sentiments = list({i.get("brand_sentiment", "Neutral") for i in cluster})
    cluster_id = hashlib.md5("|".join(sorted(i.get("fingerprint", i.get("text", "")) for i in cluster)).encode()).hexdigest()

    return {
        "title": metadata["title"],
        "theme": metadata["theme"],
        "problem_statement": metadata["problem"],
        "brand": brand,
        "type": type_tag,
        "personas": personas,
        "effort_levels": list({i.get("effort", "Unknown") for i in cluster}),
        "sentiments": sentiments,
        "opportunity_tags": list({i.get("opportunity_tag", "General Insight") for i in cluster}),
        "quotes": quotes,
        "top_ideas": [i[0] for i in top_ideas],
        "score_range": f"{min_score}–{max_score}",
        "insight_count": len(cluster),
        "avg_cluster_ready": round(np.mean([i.get("cluster_ready_score", 0) for i in cluster]), 2),
        "cluster_id": cluster_id
    }

def generate_synthesized_insights(insights):
    raw_cluster_tuples = cluster_by_subtag_then_embed(insights)
    summaries = []
    for cluster, meta in raw_cluster_tuples:
        card = synthesize_cluster(cluster)
        card["coherent"] = meta["coherent"]
        card["was_reclustered"] = meta["was_reclustered"]
        card["avg_similarity"] = f"{meta['avg_similarity']:.2f}"
        summaries.append(card)
    return summaries