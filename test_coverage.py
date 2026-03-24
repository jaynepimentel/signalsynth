#!/usr/bin/env python3
"""Test signal coverage for key recent topics."""
import json, os, sys
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

with open("precomputed_insights.json", "r", encoding="utf-8") as f:
    insights = json.load(f)

print(f"Total insights: {len(insights):,}")
print()

# ─── TEST 1: Whatnot class action lawsuit (March 2026) ───
print("=" * 60)
print("TEST 1: Whatnot Class Action Lawsuit (March 2026)")
print("=" * 60)

lawsuit_terms = ["whatnot lawsuit", "whatnot sued", "rico", "illegal gambling",
                 "unregulated casino", "class action", "whatnot in hot water",
                 "reckoning coming", "big trouble for breakers", "accuses whatnot",
                 "is whatnot gambling"]

lawsuit_signals = []
for i in insights:
    text = (i.get("text", "") + " " + i.get("title", "")).lower()
    if any(t in text for t in lawsuit_terms):
        lawsuit_signals.append(i)

print(f"Found: {len(lawsuit_signals)} signals")
for s in sorted(lawsuit_signals, key=lambda x: x.get("post_date", ""), reverse=True)[:8]:
    date = s.get("post_date", "?")
    source = s.get("source", "?")
    title = (s.get("title", "") or s.get("text", ""))[:100]
    print(f"  [{date}] [{source}] {title}")

# Check March 2026 specifically
march_signals = [s for s in lawsuit_signals if s.get("post_date", "").startswith("2026-03")]
print(f"\nMarch 2026 signals: {len(march_signals)}")
if not march_signals:
    print("  ❌ GAP: No March 2026 Whatnot lawsuit signals!")
else:
    print("  ✅ March 2026 coverage present")

# ─── TEST 2: eBay Vault integration issues ───
print()
print("=" * 60)
print("TEST 2: eBay Vault Integration Issues")
print("=" * 60)

vault_terms = ["ebay vault", "psa vault", "vault withdraw", "vault transfer",
               "vault checkout", "vault shipping", "vault authentication",
               "vault delay", "vault issue", "vault problem", "vault fee",
               "keep in vault", "vault option", "vault not showing"]

vault_signals = []
for i in insights:
    text = (i.get("text", "") + " " + i.get("title", "")).lower()
    if any(t in text for t in vault_terms):
        vault_signals.append(i)

print(f"Found: {len(vault_signals)} signals")

# Break down by subtopic
vault_subtopics = {}
for s in vault_signals:
    text = (s.get("text", "") + " " + s.get("title", "")).lower()
    if "withdraw" in text:
        vault_subtopics.setdefault("Withdrawal", []).append(s)
    elif "checkout" in text or "not showing" in text or "option" in text:
        vault_subtopics.setdefault("Checkout/UX", []).append(s)
    elif "authentication" in text or "authenticate" in text:
        vault_subtopics.setdefault("Authentication", []).append(s)
    elif "delay" in text or "wait" in text or "slow" in text:
        vault_subtopics.setdefault("Delays", []).append(s)
    elif "fee" in text or "cost" in text:
        vault_subtopics.setdefault("Fees", []).append(s)
    elif "ship" in text or "transfer" in text:
        vault_subtopics.setdefault("Shipping/Transfer", []).append(s)
    else:
        vault_subtopics.setdefault("General", []).append(s)

for topic, sigs in sorted(vault_subtopics.items(), key=lambda x: -len(x[1])):
    print(f"  {topic}: {len(sigs)} signals")

# Show recent vault signals
recent_vault = [s for s in vault_signals if s.get("post_date", "") >= "2026-03-01"]
print(f"\nMarch 2026 vault signals: {len(recent_vault)}")
for s in sorted(recent_vault, key=lambda x: x.get("post_date", ""), reverse=True)[:5]:
    date = s.get("post_date", "?")
    source = s.get("source", "?")
    title = (s.get("title", "") or s.get("text", ""))[:100]
    print(f"  [{date}] [{source}] {title}")

# ─── TEST 3: Payout issues ───
print()
print("=" * 60)
print("TEST 3: Payout Issues")
print("=" * 60)

payout_terms = ["payout", "funds held", "payment hold", "money held",
                "payout delay", "payment delay", "funds on hold",
                "can't get paid", "won't release", "payment pending",
                "managed payments", "payout issue", "payment problem"]

payout_signals = []
for i in insights:
    text = (i.get("text", "") + " " + i.get("title", "")).lower()
    if any(t in text for t in payout_terms):
        payout_signals.append(i)

print(f"Found: {len(payout_signals)} signals")

# Source distribution
from collections import Counter
payout_sources = Counter(s.get("source", "?") for s in payout_signals)
print("By source:")
for src, cnt in payout_sources.most_common(8):
    print(f"  {src}: {cnt}")

# Sentiment
payout_neg = sum(1 for s in payout_signals if s.get("brand_sentiment") == "Negative")
print(f"\nSentiment: {payout_neg} negative / {len(payout_signals)} total ({round(payout_neg/max(len(payout_signals),1)*100)}% negative)")

# Recent payout signals
recent_payout = [s for s in payout_signals if s.get("post_date", "") >= "2026-03-01"]
print(f"March 2026 payout signals: {len(recent_payout)}")
for s in sorted(recent_payout, key=lambda x: x.get("post_date", ""), reverse=True)[:5]:
    date = s.get("post_date", "?")
    source = s.get("source", "?")
    title = (s.get("title", "") or s.get("text", ""))[:100]
    sent = s.get("brand_sentiment", "?")
    print(f"  [{date}] [{source}] [{sent}] {title}")

# ─── TEST 4: Retrieval test ───
print()
print("=" * 60)
print("TEST 4: Retrieval Quality Check")
print("=" * 60)

try:
    from components.hybrid_retrieval import HybridRetriever
    retriever = HybridRetriever(insights)
    
    test_queries = [
        ("Whatnot class action lawsuit gambling RICO", "Whatnot Lawsuit"),
        ("eBay Vault issues problems authentication checkout", "Vault Issues"),
        ("payout delays funds held managed payments seller", "Payout Problems"),
    ]
    
    for query, label in test_queries:
        results = retriever.retrieve(query, top_k=10, candidate_pool=60, max_per_source=8)
        # Filter out promotional
        results = [r for r in results if not r.get("_is_promotional")][:10]
        
        print(f"\n🔍 {label}: '{query[:50]}...'")
        print(f"   Retrieved {len(results)} signals")
        for idx, r in enumerate(results[:5], 1):
            source = r.get("source", "?")
            date = r.get("post_date", "?")
            title = (r.get("title", "") or r.get("text", ""))[:80]
            print(f"   [{idx}] [{date}] [{source}] {title}")
except Exception as e:
    print(f"  ⚠️ Retriever error: {e}")

print()
print("=" * 60)
print("COVERAGE SUMMARY")
print("=" * 60)
print(f"Whatnot Lawsuit:  {len(lawsuit_signals)} signals ({len(march_signals)} in March 2026)")
print(f"Vault Issues:     {len(vault_signals)} signals ({len(recent_vault)} in March 2026)")
print(f"Payout Problems:  {len(payout_signals)} signals ({len(recent_payout)} in March 2026)")
