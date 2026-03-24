#!/usr/bin/env python3
"""Check cluster structure and content"""

import json

with open('precomputed_clusters.json', 'r', encoding='utf-8') as f:
    clusters_data = json.load(f)

print('Cluster data structure:')
print(f'Top-level keys: {list(clusters_data.keys())}')
print(f'Clusters type: {type(clusters_data["clusters"])}')

if clusters_data["clusters"]:
    first_cluster = clusters_data["clusters"][0]
    print(f'First cluster keys: {list(first_cluster.keys())}')
    print(f'First cluster sample: {first_cluster}')
else:
    print('No clusters found')

# Check if we need to restore the old cluster format
print('\nChecking if there are signal counts in the clusters...')
for i, cluster in enumerate(clusters_data["clusters"][:3]):
    signals = cluster.get('signals', 0)
    print(f'Cluster {i+1}: {signals} signals')
