#!/usr/bin/env python3
"""Analyze the General Platform Feedback bucket to find natural sub-groupings."""

import json, os, sys
from collections import Counter, defaultdict

# Need to import the signal category function
sys.path.insert(0, os.path.dirname(__file__))
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from components.cluster_synthesizer import _get_signal_category

with open("precomputed_insights.json", "r", encoding="utf-8") as f:
    insights = json.load(f)

# Find all insights that fall into General Platform Feedback
general_bucket = []
for i in insights:
    cat = _get_signal_category(i)
    if cat == "General Platform Feedback":
        general_bucket.append(i)

print(f"General Platform Feedback: {len(general_bucket)} signals")
print()

# Analyze by taxonomy topic
topic_counts = Counter()
for i in general_bucket:
    topic = (i.get("taxonomy") or {}).get("topic", i.get("subtag", "General"))
    topic_counts[topic] += 1

print("BY TAXONOMY TOPIC:")
for topic, count in topic_counts.most_common(30):
    print(f"  {topic}: {count}")

# Analyze by type_tag
type_counts = Counter()
for i in general_bucket:
    tt = (i.get("taxonomy") or {}).get("type", i.get("type_tag", "Unknown"))
    type_counts[tt] += 1

print(f"\nBY TYPE:")
for tt, count in type_counts.most_common():
    print(f"  {tt}: {count}")

# Analyze by source
source_counts = Counter()
for i in general_bucket:
    source_counts[i.get("source", "Unknown")] += 1

print(f"\nBY SOURCE:")
for src, count in source_counts.most_common(15):
    print(f"  {src}: {count}")

# Analyze by brand_sentiment
sent_counts = Counter()
for i in general_bucket:
    sent_counts[i.get("brand_sentiment", "Unknown")] += 1

print(f"\nBY SENTIMENT:")
for sent, count in sent_counts.most_common():
    print(f"  {sent}: {count}")

# Look at keyword patterns in the text to find natural groupings
keyword_groups = {
    "Returns & Refunds": ["return", "refund", "inad", "item not as described", "money back"],
    "Buyer Experience": ["buyer", "purchased", "buying", "won auction", "best offer", "shopping"],
    "Account Issues": ["suspended", "restricted", "banned", "account", "locked out"],
    "Listing Quality": ["listing", "description", "photo", "title", "category", "condition"],
    "Pricing & Market": ["price", "pricing", "overpriced", "underpriced", "market value", "comp"],
    "Collecting Community": ["collection", "collecting", "collector", "hobby", "mail day", "pickup", "pull"],
    "Authentication & Grading": ["grade", "grading", "psa", "bgs", "sgc", "cgc", "slab", "authentic"],
    "Platform Policy": ["policy", "terms of service", "rule", "restriction", "banned"],
    "Scam / Fraud": ["scam", "fraud", "fake", "counterfeit", "stolen"],
    "App & Technical": ["app", "bug", "glitch", "crash", "error", "broken", "update"],
}

print(f"\nKEYWORD GROUP ANALYSIS:")
assigned = set()
group_counts = {}
for group_name, keywords in keyword_groups.items():
    matches = []
    for idx, i in enumerate(general_bucket):
        if idx in assigned:
            continue
        text = (i.get("text", "") + " " + i.get("title", "")).lower()
        if any(kw in text for kw in keywords):
            matches.append(idx)
    group_counts[group_name] = len(matches)
    # Only assign to first matching group (priority order)
    for idx in matches:
        if idx not in assigned:
            assigned.add(idx)

for group_name, count in sorted(group_counts.items(), key=lambda x: -x[1]):
    print(f"  {group_name}: {count}")

unassigned = len(general_bucket) - len(assigned)
print(f"  Remaining unassigned: {unassigned}")

# Show sample texts from top unassigned
print(f"\nSAMPLE UNASSIGNED SIGNALS:")
for idx, i in enumerate(general_bucket):
    if idx not in assigned:
        text = (i.get("title", "") or i.get("text", ""))[:100]
        topic = (i.get("taxonomy") or {}).get("topic", "?")
        print(f"  [{topic}] {text}")
        if idx > 20:
            break
