#!/usr/bin/env python3
"""
Improved clustering strategy for SignalSynth
Focus on semantic similarity rather than keyword-based grouping
"""

import json
import numpy as np
from sklearn.cluster import DBSCAN
from sentence_transformers import SentenceTransformer
from components.cluster_synthesizer import _get_signal_category

def create_improved_clusters():
    """Create clusters based on semantic similarity of actual content"""
    
    print("🔄 Loading insights...")
    with open('precomputed_insights.json', 'r', encoding='utf-8') as f:
        insights = json.load(f)
    
    # Filter out non-collectibles content
    filtered_insights = []
    for insight in insights:
        category = _get_signal_category(insight)
        if category != "EXCLUDE_NON_COLLECTIBLES":
            filtered_insights.append(insight)
    
    print(f"📊 Working with {len(filtered_insights)} collectibles-relevant insights")
    
    # Create text representations for clustering
    texts = []
    for insight in filtered_insights:
        # Combine title and text for better semantic representation
        title = insight.get('title', '')[:200]
        text = insight.get('text', '')[:300]
        topic = insight.get('taxonomy', {}).get('topic', '')
        
        # Create a rich text representation
        combined_text = f"{title} {text} {topic}".strip()
        texts.append(combined_text)
    
    print("🤖 Loading semantic model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("📈 Generating embeddings...")
    embeddings = model.encode(texts, show_progress_bar=True)
    
    print("🎯 Performing semantic clustering...")
    # Use DBSCAN for density-based clustering (better for finding natural groups)
    clustering = DBSCAN(eps=0.3, min_samples=5, metric='cosine').fit(embeddings)
    
    # Group insights by cluster
    clusters = {}
    for i, label in enumerate(clustering.labels_):
        if label == -1:  # Noise points - skip for now
            continue
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(filtered_insights[i])
    
    print(f"✅ Found {len(clusters)} semantic clusters")
    
    # Analyze and name clusters based on content
    improved_clusters = []
    for cluster_id, cluster_insights in clusters.items():
        if len(cluster_insights) < 10:  # Skip very small clusters
            continue
            
        # Analyze cluster themes
        themes = analyze_cluster_themes(cluster_insights)
        cluster_name = generate_cluster_name(themes, cluster_insights)
        
        # Create cluster object
        cluster = {
            'cluster_id': f'semantic_{cluster_id}',
            'theme': cluster_name,
            'insights': cluster_insights,
            'stats': {
                'size': len(cluster_insights),
                'complaints': sum(1 for i in cluster_insights if i.get('taxonomy', {}).get('type') == 'Complaint'),
                'feature_requests': sum(1 for i in cluster_insights if i.get('taxonomy', {}).get('type') == 'Feature Request'),
            },
            'themes': themes,
            'sample_quotes': get_representative_quotes(cluster_insights, 3)
        }
        
        improved_clusters.append(cluster)
        print(f"📋 Cluster '{cluster_name}': {len(cluster_insights)} signals")
    
    # Sort by size
    improved_clusters.sort(key=lambda x: x['stats']['size'], reverse=True)
    
    # Save improved clusters
    output = {
        'clusters': improved_clusters,
        'metadata': {
            'method': 'semantic_clustering',
            'total_signals': sum(c['stats']['size'] for c in improved_clusters),
            'generated': '2026-03-20',
            'model': 'all-MiniLM-L6-v2',
            'clustering_algorithm': 'DBSCAN'
        }
    }
    
    with open('precomputed_clusters.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Saved {len(improved_clusters)} improved clusters")
    return improved_clusters

def analyze_cluster_themes(insights):
    """Analyze common themes in a cluster"""
    topics = {}
    sentiment_counts = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
    
    for insight in insights:
        # Count topics
        topic = insight.get('taxonomy', {}).get('topic', 'General')
        topics[topic] = topics.get(topic, 0) + 1
        
        # Count sentiment
        sentiment = insight.get('brand_sentiment', 'Neutral')
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
    
    # Sort topics by frequency
    sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
    
    return {
        'top_topics': sorted_topics[:5],
        'sentiment_distribution': sentiment_counts,
        'dominant_topic': sorted_topics[0][0] if sorted_topics else 'General'
    }

def generate_cluster_name(themes, insights):
    """Generate a descriptive name for the cluster"""
    dominant_topic = themes['dominant_topic']
    top_topics = [topic for topic, count in themes['top_topics'][:3]]
    
    # Get some keywords from the content
    all_text = ' '.join([
        insight.get('title', '') + ' ' + insight.get('text', '') 
        for insight in insights[:10]
    ]).lower()
    
    # Topic-based naming
    topic_names = {
        'Payments': 'Payment Processing & Checkout Issues',
        'Grading': 'Card Grading & Authentication Services', 
        'Seller Experience': 'Seller Tools & Platform Experience',
        'Trust': 'Trust & Safety Concerns',
        'Shipping': 'Shipping & Delivery Problems',
        'Returns & Refunds': 'Return Policy & Refund Issues',
        'Competitor Intel': 'Competitor Platform Analysis',
        'Vault': 'Vault & Storage Services',
        'Customer Service': 'Customer Support Experience',
        'Price Guide': 'Pricing & Valuation Tools',
        'High-Value': 'High-Value Transaction Issues'
    }
    
    base_name = topic_names.get(dominant_topic, f'{dominant_topic} Related Issues')
    
    # Add specificity if multiple major topics
    if len(top_topics) >= 2 and themes['top_topics'][0][1] / len(insights) < 0.6:
        second_topic = top_topics[1]
        if second_topic in topic_names:
            base_name += f' & {second_topic}'
    
    return base_name

def get_representative_quotes(insights, max_quotes=3):
    """Get representative quotes from the cluster"""
    quotes = []
    
    # Sort by signal strength to get high-quality examples
    sorted_insights = sorted(insights, key=lambda x: x.get('signal_strength', 0), reverse=True)
    
    for insight in sorted_insights[:max_quotes]:
        text = insight.get('text', '')
        title = insight.get('title', '')
        
        # Use title if available, otherwise first part of text
        quote = title if title else text[:150] + '...' if len(text) > 150 else text
        quotes.append(quote)
    
    return quotes

if __name__ == "__main__":
    create_improved_clusters()
