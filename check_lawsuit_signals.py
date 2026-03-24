#!/usr/bin/env python3
"""Check why Whatnot lawsuit signals aren't being retrieved."""
import json, os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

with open("precomputed_insights.json", "r", encoding="utf-8") as f:
    insights = json.load(f)

lawsuit_terms = ["whatnot lawsuit", "whatnot in hot water", "is whatnot gambling",
                 "unregulated casino", "class action", "whatnot sued",
                 "reckoning coming", "big trouble for breakers",
                 "lawsuit could mean", "accuses whatnot"]

print("=== KEY WHATNOT LAWSUIT SIGNALS ===")
for i in insights:
    text = (i.get("text", "") + " " + i.get("title", "")).lower()
    if any(term in text for term in lawsuit_terms):
        title = i.get("title", "")[:150]
        source = i.get("source", "")
        date = i.get("post_date", "")
        score = i.get("score", 0)
        strength = i.get("signal_strength", 0)
        print(f"SOURCE: {source}")
        print(f"DATE: {date}")
        print(f"SCORE: {score} | STRENGTH: {strength}")
        print(f"TITLE: {title}")
        print(f"TEXT: {i.get('text', '')[:200]}")
        print()

# Now test retrieval for a Whatnot policy question
print("\n=== TESTING RETRIEVAL ===")
try:
    from components.hybrid_retrieval import HybridRetriever
    retriever = HybridRetriever(insights)
    
    query = "What policy or terms of service changes has Whatnot made recently around mystery repacks, unpaid items, or trust enforcement? How are collectors reacting?"
    results = retriever.retrieve(query, top_k=25, candidate_pool=60, max_per_source=15)
    
    print(f"Retrieved {len(results)} signals")
    lawsuit_in_results = 0
    for idx, r in enumerate(results, 1):
        title = r.get("title", "")[:100]
        source = r.get("source", "")
        text_lower = (r.get("text", "") + " " + r.get("title", "")).lower()
        is_lawsuit = any(t in text_lower for t in ["lawsuit", "class action", "gambling", "casino", "hot water", "reckoning"])
        if is_lawsuit:
            lawsuit_in_results += 1
        marker = " *** LAWSUIT ***" if is_lawsuit else ""
        print(f"  [{idx}] [{source}] {title}{marker}")
    
    print(f"\nLawsuit signals in top 25: {lawsuit_in_results}")
except Exception as e:
    print(f"Retriever error: {e}")
