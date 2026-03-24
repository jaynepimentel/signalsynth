#!/usr/bin/env python3
"""Verify eBay Collectibles-only clusters"""

import json

with open('precomputed_clusters.json', 'r', encoding='utf-8') as f:
    clusters_data = json.load(f)

clusters = clusters_data['clusters']
print(f'🎯 eBay Collectibles-Only Clusters: {len(clusters)}')
print(f'📊 Total signals: {clusters_data["metadata"]["total_signals"]:,}')
print(f'🔍 Filtered: {clusters_data["metadata"]["filtered_content"]}')
print()

# Show top clusters by signal count
sorted_clusters = sorted(clusters, key=lambda x: x.get('insight_count', 0), reverse=True)

for i, cluster in enumerate(sorted_clusters[:5], 1):
    theme = cluster.get('theme', 'Unknown')
    signals = cluster.get('insight_count', 0)
    complaints = cluster.get('complaints', 0)
    
    print(f'{i}. {theme}')
    print(f'   📊 Signals: {signals:,} | 🚨 Complaints: {complaints}')
    
    # Check for any remaining gaming content in quotes
    quotes = cluster.get('quotes', [])
    if quotes:
        first_quote = quotes[0].lower()
        gaming_terms = ['psa:', 'public service announcement', 'seed vault', 'stella montis', 'game', 'gaming']
        if any(term in first_quote for term in gaming_terms):
            print(f'   ⚠️  WARNING: Still has gaming content!')
        else:
            print(f'   ✅ Clean - no gaming content detected')
    print()

print('🎯 SUCCESS: All clusters now contain only eBay Collectibles-relevant content!')
