#!/usr/bin/env python3
"""Check taxonomy structure in insights"""

import json

with open('precomputed_insights.json', 'r', encoding='utf-8') as f:
    insights = json.load(f)

print("Checking taxonomy structure...")
for i in insights[:5]:
    tax = i.get('taxonomy', {})
    type_tag = i.get('type_tag', '')
    brand_sent = i.get('brand_sentiment', '')
    
    print(f'Taxonomy: {tax}')
    print(f'Type tag: {type_tag}')
    print(f'Taxonomy type: {tax.get("type", "NO_TYPE")}')
    print(f'Brand sentiment: {brand_sent}')
    print('---')

# Count different taxonomy types
type_counts = {}
sentiment_counts = {}
for i in insights:
    tax_type = i.get('taxonomy', {}).get('type', 'NO_TYPE')
    type_counts[tax_type] = type_counts.get(tax_type, 0) + 1
    
    brand_sent = i.get('brand_sentiment', 'NO_SENTIMENT')
    sentiment_counts[brand_sent] = sentiment_counts.get(brand_sent, 0) + 1

print(f"\nTaxonomy type distribution:")
for ttype, count in sorted(type_counts.items()):
    print(f"  {ttype}: {count}")

print(f"\nBrand sentiment distribution:")
for sent, count in sorted(sentiment_counts.items()):
    print(f"  {sent}: {count}")
