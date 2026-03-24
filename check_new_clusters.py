#!/usr/bin/env python3
"""Check cluster structure after precompute_clusters.py"""

import json

with open('precomputed_clusters.json', 'r', encoding='utf-8') as f:
    clusters = json.load(f)

print(f'📊 Cluster structure: {type(clusters)}')
print(f'📊 Keys: {list(clusters.keys()) if isinstance(clusters, dict) else "Not a dict"}')

if isinstance(clusters, dict):
    print(f'📊 Clusters count: {len(clusters.get("clusters", []))}')
    print(f'📊 Cards count: {len(clusters.get("cards", []))}')
    
    # Check which structure exists
    if 'clusters' in clusters:
        print('✅ Using "clusters" structure')
        clusters_list = clusters['clusters']
    elif 'cards' in clusters:
        print('✅ Using "cards" structure')
        clusters_list = clusters['cards']
    else:
        print('❌ No clusters or cards found')
        clusters_list = []
    
    print(f'📈 Total insights in clusters: {sum(c.get("insight_count", 0) for c in clusters_list)}')
    
    # Show first few clusters
    for i, cluster in enumerate(clusters_list[:3], 1):
        theme = cluster.get('theme', cluster.get('title', 'Unknown'))
        insights = cluster.get('insight_count', 0)
        print(f'  {i}. {theme} ({insights} insights)')
