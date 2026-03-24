#!/usr/bin/env python3
"""Check clusters file structure"""

import json

with open('precomputed_clusters.json', 'r', encoding='utf-8') as f:
    clusters = json.load(f)

print(f'Clusters file type: {type(clusters)}')
print(f'Length: {len(clusters)}')

if isinstance(clusters, dict):
    print(f'Keys: {list(clusters.keys())}')
    for key, value in list(clusters.items())[:3]:
        print(f'Key: {key}, Value type: {type(value)}, Length: {len(value) if hasattr(value, "__len__") else "N/A"}')
elif isinstance(clusters, list):
    print(f'List with {len(clusters)} items')
    if clusters:
        first_item = clusters[0]
        print(f'First item type: {type(first_item)}')
        if isinstance(first_item, dict):
            print(f'First item keys: {list(first_item.keys())}')
        print(f'Sample first item: {first_item}')
