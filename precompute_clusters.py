# precompute_clusters.py — saves .cache/clusters.json and cards.json from precomputed_insights.json

import json
import os
from components.cluster_synthesizer import cluster_insights, generate_synthesized_insights

INPUT_PATH = "precomputed_insights.json"
OUTPUT_DIR = ".cache"
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    insights = json.load(f)

print(f"🔍 Loaded {len(insights)} insights for clustering...")

clusters = cluster_insights(insights)
cards = generate_synthesized_insights(insights)

with open(os.path.join(OUTPUT_DIR, "clusters.json"), "w", encoding="utf-8") as f:
    json.dump(clusters, f, indent=2)

with open(os.path.join(OUTPUT_DIR, "cards.json"), "w", encoding="utf-8") as f:
    json.dump(cards, f, indent=2)

print(f"✅ Saved clusters and cards to {OUTPUT_DIR}/")