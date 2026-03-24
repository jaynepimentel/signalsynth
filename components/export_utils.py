# export_utils.py — Export filtered insights, clusters, and summaries
import os
import json
import csv
import pandas as pd
from datetime import datetime

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

def get_timestamped_name(prefix, ext="csv"):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return os.path.join(EXPORT_DIR, f"{prefix}_{ts}.{ext}")

# ─────────────────────────────────────────────
# 🧠 INSIGHT EXPORTS

def export_insights_to_csv(insights, filename=None):
    if not filename:
        filename = get_timestamped_name("insights", "csv")
    df = pd.DataFrame(insights)
    df.to_csv(filename, index=False)
    return filename

def export_insights_to_json(insights, filename=None):
    if not filename:
        filename = get_timestamped_name("insights", "json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    return filename

def export_insights_to_md(insights, filename=None):
    if not filename:
        filename = get_timestamped_name("insights", "md")
    with open(filename, "w", encoding="utf-8") as f:
        for i in insights:
            f.write(f"## 🧠 {i.get('title') or i.get('text')[:80]}\n")
            f.write(f"- **Type:** {i.get('type_tag')} > {i.get('type_subtag')}\n")
            f.write(f"- **Sentiment:** {i.get('brand_sentiment')}\n")
            f.write(f"- **Persona:** {i.get('persona')}\n")
            f.write(f"- **Journey Stage:** {i.get('journey_stage')}\n")
            f.write(f"> {i.get('text')}\n\n")
    return filename

# ─────────────────────────────────────────────
# 📦 CLUSTER EXPORTS

def export_clusters_to_md(cluster_cards, filename=None):
    if not filename:
        filename = get_timestamped_name("clusters", "md")
    with open(filename, "w", encoding="utf-8") as f:
        for idx, card in enumerate(cluster_cards):
            f.write(f"# 📌 Cluster {idx + 1}: {card.get('title')}\n")
            f.write(f"- Brand: {card.get('brand', 'Unknown')}\n")
            f.write(f"- Tags: {', '.join(card.get('topic_focus_tags', []))}\n")
            f.write(f"### Summary:\n{card.get('summary', '')}\n\n")
            if card.get("quotes"):
                f.write("### Quotes:\n")
                for quote in card["quotes"]:
                    f.write(f"> {quote.strip('- _')}\n")
            if card.get("top_ideas"):
                f.write("### Top Suggestions:\n")
                for idea in card["top_ideas"]:
                    f.write(f"- {idea}\n")
            f.write("\n---\n\n")
    return filename
