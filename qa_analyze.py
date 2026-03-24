#!/usr/bin/env python3
"""Analyze QA results for improvement opportunities."""
import json

with open("qa_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

for r in results:
    print(f"Q: {r['question'][:70]}")
    print(f"  Citations: {r['citations']} | Signals: {r['signals_used']} | Len: {r['length']}")
    resp = r["response"]
    issues = []
    if r["citations"] < 8:
        issues.append("LOW_CITATIONS")
    if "I don" in resp or "no data" in resp.lower():
        issues.append("HEDGING")
    if resp.count("**") < 6:
        issues.append("LOW_FORMATTING")
    # Check for owner/timeline in actions
    has_owner = "Owner:" in resp or "owner:" in resp
    has_timeline = "Timeline:" in resp or "timeline:" in resp
    if not has_owner:
        issues.append("MISSING_OWNERS")
    if not has_timeline:
        issues.append("MISSING_TIMELINES")
    # Check source refs are linked back
    source_links = resp.count("[S")
    if source_links < 5:
        issues.append("FEW_SOURCE_LINKS")
    # Check for tables
    has_table = "|" in resp and "---" in resp
    if not has_table:
        issues.append("NO_TABLES")
    # Check for verbatim quotes
    italic_quotes = resp.count("*\"") + resp.count("*'")
    if italic_quotes < 2:
        issues.append("FEW_VERBATIM_QUOTES")
    print(f"  Issues: {issues if issues else 'None'}")
    print()

# Print full responses for manual review
print("\n" + "=" * 60)
print("FULL RESPONSES FOR MANUAL REVIEW")
print("=" * 60)
for i, r in enumerate(results, 1):
    print(f"\n{'='*60}")
    print(f"Q{i}: {r['question']}")
    print(f"{'='*60}")
    print(r["response"])
    print()
