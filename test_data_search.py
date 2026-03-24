#!/usr/bin/env python3
"""
Direct test of the search functionality and data.
"""

import json
import numpy as np
from collections import Counter

def test_data_and_search():
    """Test the underlying data and simple search."""
    
    print("🔍 TESTING DATA AVAILABILITY AND SEARCH")
    print("=" * 60)
    
    # Load insights
    with open('precomputed_insights.json', 'r', encoding='utf-8') as f:
        insights = json.load(f)
    
    print(f"✅ Loaded {len(insights)} insights")
    
    # Analyze data coverage
    sources = Counter()
    sentiments = Counter()
    themes = Counter()
    
    for insight in insights[:1000]:  # Sample for speed
        sources[insight.get('source', 'Unknown')] += 1
        sentiments[insight.get('sentiment', 'Unknown')] += 1
        themes[insight.get('theme', 'Unknown')] += 1
    
    print(f"\n📊 TOP SOURCES (sample):")
    for source, count in sources.most_common(5):
        print(f"  {source}: {count}")
    
    print(f"\n📊 SENTIMENT BREAKDOWN:")
    for sentiment, count in sentiments.most_common():
        print(f"  {sentiment}: {count}")
    
    print(f"\n📊 TOP THEMES:")
    for theme, count in themes.most_common(5):
        print(f"  {theme}: {count}")
    
    # Test keyword search for executive topics
    executive_queries = {
        "seller pain points": ["seller", "fees", "payments", "shipping", "frustration"],
        "authentication": ["authenticity", "guarantee", "graded", "psa", "fake"],
        "competition": ["whatnot", "fanatics", "heritage", "tcgplayer", "competitor"],
        "market share": ["leaving", "switching", "moving to", "alternative", "better than"],
        "vault": ["vault", "storage", "graded", "slab", "secure"]
    }
    
    print(f"\n🔍 EXECUTIVE QUERY ANALYSIS:")
    for topic, keywords in executive_queries.items():
        matches = []
        for insight in insights:
            text = (insight.get('text', '') + ' ' + insight.get('title', '')).lower()
            if any(keyword in text for keyword in keywords):
                matches.append(insight)
        
        print(f"\n📈 {topic.upper()}: {len(matches)} signals found")
        if matches:
            for i, match in enumerate(matches[:3], 1):
                title = match.get('title', '')[:60]
                source = match.get('source', '')
                sentiment = match.get('sentiment', '')
                print(f"  {i}. [{source}] {sentiment} - {title}")
    
    print(f"\n✅ Data analysis complete!")

if __name__ == "__main__":
    test_data_and_search()
