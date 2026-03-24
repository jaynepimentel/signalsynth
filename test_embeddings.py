#!/usr/bin/env python3
"""Test real embeddings"""

import numpy as np
from components.cluster_synthesizer import semantic_search

print('🔍 Testing semantic search with real embeddings...')
results = semantic_search('payment problems', top_k=5)
print(f'✅ Found {len(results)} results for "payment problems"')
for idx, (insight, score) in enumerate(results[:3], 1):
    print(f'  {idx}. Score: {score:.3f} - {insight.get("title", "")[:50]}...')

print('\n🔍 Testing another query...')
results2 = semantic_search('vault storage', top_k=3)
print(f'✅ Found {len(results2)} results for "vault storage"')
for idx, (insight, score) in enumerate(results2[:3], 1):
    print(f'  {idx}. Score: {score:.3f} - {insight.get("title", "")[:50]}...')
