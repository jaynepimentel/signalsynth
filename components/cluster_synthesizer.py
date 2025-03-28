# ✅ cluster_synthesizer.py — Now with recursive mini-cluster repair for low coherence
import os
from collections import defaultdict, Counter
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from itertools import combinations

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

model = SentenceTransformer("all-MiniLM-L6-v2")

COHERENCE_THRESHOLD = 0.68
RECLUSTER_EPS = 0.30


def cluster_by_subtag_then_embed(insights, min_cluster_size=3):
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
            if is_semantically_coherent(c):
                all_clusters.append(c)
            else:
                all_clusters.extend(split_incoherent_cluster(c))
    return all_clusters


def cluster_insights(insights, min_cluster_size=3, eps=0.38):
    texts = [i.get("text", "") for i in insights]
    embeddings = model.encode(texts, convert_to_tensor=True)
    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric="cosine").fit(embeddings.cpu().numpy())
    labels = clustering.labels_

    clustered = defaultdict(list)
    for label, insight in zip(labels, insights):
        if label != -1:
            clustered[label].append(insight)

    return list(clustered.values())


def is_semantically_coherent(cluster):
    if len(cluster) <= 2:
        return True
    texts = [i["text"] for i in cluster]
    embeddings = model.encode(texts, convert_to_tensor=True)
    sim_matrix = np.inner(embeddings, embeddings)
    upper_triangle = sim_matrix[np.triu_indices(len(texts), k=1)]
    avg_similarity = upper_triangle.mean()
    return avg_similarity >= COHERENCE_THRESHOLD


def split_incoherent_cluster(cluster):
    if len(cluster) <= 3:
        return [cluster]
    subclusters = cluster_insights(cluster, min_cluster_size=2, eps=RECLUSTER_EPS)
    final = []
    for c in subclusters:
        if is_semantically_coherent(c):
            final.append(c)
        else:
            final.extend([[i] for i in c])  # break into singletons if still incoherent
    return final


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
            "title": lines[0].replace("Title:", "").strip(),
            "theme": lines[1].replace("Theme:", "").strip(),
            "problem": lines[2].replace("Problem:", "").strip(),
        }
    except Exception as e:
        return {
            "title": "(GPT Error)",
            "theme": "Unknown",
            "problem": str(e)
        }


def find_cross_tag_connections(insights, threshold=0.75):
    connections = defaultdict(list)
    text_map = {i["text"]: i for i in insights}
    texts = list(text_map.keys())
    embeddings = model.encode(texts, convert_to_tensor=True)
    sims = np.inner(embeddings, embeddings)

    for i, j in combinations(range(len(texts)), 2):
        if sims[i][j] > threshold:
            i_tag = text_map[texts[i]].get("type_subtag", "General")
            j_tag = text_map[texts[j]].get("type_subtag", "General")
            if i_tag != j_tag:
                key = f"{i_tag} ↔ {j_tag}"
                connections[key].append({
                    "a": texts[i],
                    "b": texts[j],
                    "similarity": round(float(sims[i][j]), 3)
                })
    return connections


def synthesize_cluster(cluster):
    metadata = generate_cluster_metadata(cluster)
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
    effort_levels = list({i.get("effort", "Unknown") for i in cluster})
    sentiments = list({i.get("brand_sentiment", "Neutral") for i in cluster})

    return {
        "title": metadata["title"],
        "theme": metadata["theme"],
        "problem_statement": metadata["problem"],
        "brand": brand,
        "type": type_tag,
        "personas": personas,
        "effort_levels": effort_levels,
        "sentiments": sentiments,
        "quotes": quotes,
        "top_ideas": [i[0] for i in top_ideas],
        "score_range": f"{min_score}–{max_score}",
        "insight_count": len(cluster)
    }


def generate_synthesized_insights(insights):
    clusters = cluster_by_subtag_then_embed(insights)
    cross_tag_patterns = find_cross_tag_connections(insights)
    summaries = [synthesize_cluster(c) for c in clusters]
    if cross_tag_patterns:
        summaries.append({
            "title": "🔗 Emerging Cross-Tag Patterns",
            "theme": "Cross-Topic Insight",
            "problem_statement": f"Identified {len(cross_tag_patterns)} weak-tie patterns across subtags",
            "connections": cross_tag_patterns,
            "insight_count": sum(len(v) for v in cross_tag_patterns.values())
        })
    return summaries
