#!/usr/bin/env python3
"""
Improved clustering using existing infrastructure
Focus on better topic separation and semantic coherence
"""

import json
from collections import defaultdict, Counter
from components.cluster_synthesizer import _get_signal_category, synthesize_cluster

def create_better_clusters():
    """Create better clusters using improved topic separation"""
    
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
    
    # Create more granular topic-based grouping
    topic_groups = defaultdict(list)
    
    for insight in filtered_insights:
        # Use more specific topic classification
        taxonomy = insight.get('taxonomy', {})
        topic = taxonomy.get('topic', 'General')
        subtag = insight.get('subtag', 'General')
        type_tag = taxonomy.get('type', 'Discussion')
        
        # Create more specific groupings
        if topic == 'Grading':
            # Split grading into subtopics
            text = (insight.get('text', '') + ' ' + insight.get('title', '')).lower()
            if any(term in text for term in ['turnaround', 'wait time', 'processing', 'delay']):
                specific_topic = 'Grading Turnaround Times'
            elif any(term in text for term in ['psa', 'bgs', 'sgc', 'cgc', 'slab']):
                specific_topic = 'Grading Service Quality'
            elif any(term in text for term in ['fake', 'counterfeit', 'authentic']):
                specific_topic = 'Authentication Issues'
            else:
                specific_topic = 'General Grading'
        elif topic == 'Payments':
            # Split payments into subtopics
            text = (insight.get('text', '') + ' ' + insight.get('title', '')).lower()
            if any(term in text for term in ['checkout', 'payment method', 'can\'t pay']):
                specific_topic = 'Checkout & Payment Methods'
            elif any(term in text for term in ['payout', 'funds held', 'payment delay']):
                specific_topic = 'Seller Payouts & Holds'
            else:
                specific_topic = 'General Payment Issues'
        elif topic == 'Seller Experience':
            # Split seller experience into subtopics
            text = (insight.get('text', '') + ' ' + insight.get('title', '')).lower()
            if any(term in text for term in ['fees', 'commission', 'take rate']):
                specific_topic = 'Seller Fees & Economics'
            elif any(term in text for term in ['listing', 'tool', 'app', 'seller hub']):
                specific_topic = 'Seller Tools & Interface'
            else:
                specific_topic = 'General Seller Experience'
        elif topic == 'Trust':
            # Split trust into subtopics
            text = (insight.get('text', '') + ' ' + insight.get('title', '')).lower()
            if any(term in text for term in ['fraud', 'scam', 'stolen']):
                specific_topic = 'Fraud & Security'
            elif any(term in text for term in ['refund', 'return', 'dispute']):
                specific_topic = 'Returns & Disputes'
            else:
                specific_topic = 'General Trust Issues'
        elif topic == 'Shipping':
            specific_topic = 'Shipping & Delivery'
        elif topic == 'Competitor Intel':
            specific_topic = 'Competitive Intelligence'
        elif topic == 'Vault':
            specific_topic = 'Vault & Storage Services'
        elif topic == 'Customer Service':
            specific_topic = 'Customer Support'
        elif topic == 'Price Guide':
            specific_topic = 'Pricing & Valuation'
        else:
            specific_topic = topic if topic != 'General' else f'General_{type_tag}'
        
        topic_groups[specific_topic].append(insight)
    
    print(f"📋 Created {len(topic_groups)} topic groups")
    
    # Create clusters from topic groups
    improved_clusters = []
    
    for topic_name, group_insights in topic_groups.items():
        if len(group_insights) < 5:  # Skip very small groups
            continue
            
        # Further split large groups if needed
        if len(group_insights) > 800:
            print(f"🔄 Splitting large group: {topic_name} ({len(group_insights)} signals)")
            sub_clusters = split_large_group(group_insights, topic_name)
            improved_clusters.extend(sub_clusters)
        else:
            # Create cluster for this topic
            cluster = create_cluster_from_insights(topic_name, group_insights)
            improved_clusters.append(cluster)
    
    # Sort by size
    improved_clusters.sort(key=lambda x: x['stats']['size'], reverse=True)
    
    print(f"✅ Created {len(improved_clusters)} improved clusters")
    
    # Display cluster summary
    for i, cluster in enumerate(improved_clusters[:10], 1):
        print(f"{i}. {cluster['theme']}: {cluster['stats']['size']} signals")
    
    # Save improved clusters
    output = {
        'clusters': improved_clusters,
        'metadata': {
            'method': 'improved_topic_clustering',
            'total_signals': sum(c['stats']['size'] for c in improved_clusters),
            'generated': '2026-03-20',
            'strategy': 'granular_topic_separation'
        }
    }
    
    with open('precomputed_clusters.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Saved improved clusters")
    return improved_clusters

def split_large_group(insights, base_topic):
    """Split a large group into smaller, more coherent subgroups"""
    
    # Use sentiment and signal strength to create subgroups
    subgroups = defaultdict(list)
    
    for insight in insights:
        # Group by sentiment and signal strength
        sentiment = insight.get('brand_sentiment', 'Neutral')
        strength = insight.get('signal_strength', 0)
        
        if strength > 70:
            quality = 'high'
        elif strength > 40:
            quality = 'medium'
        else:
            quality = 'low'
        
        subgroup_key = f"{sentiment}_{quality}"
        subgroups[subgroup_key].append(insight)
    
    # Create clusters from subgroups
    sub_clusters = []
    for subgroup_key, subgroup_insights in subgroups.items():
        if len(subgroup_insights) < 10:  # Skip very small subgroups
            continue
            
        sentiment, quality = subgroup_key.split('_')
        theme_name = f"{base_topic} - {sentiment.title()} {quality.title()} Priority"
        
        cluster = create_cluster_from_insights(theme_name, subgroup_insights)
        sub_clusters.append(cluster)
    
    return sub_clusters

def create_cluster_from_insights(theme_name, insights):
    """Create a cluster object from insights"""
    
    # Calculate stats
    stats = {
        'size': len(insights),
        'complaints': sum(1 for i in insights if i.get('taxonomy', {}).get('type') == 'Complaint'),
        'feature_requests': sum(1 for i in insights if i.get('taxonomy', {}).get('type') == 'Feature Request'),
        'negative': sum(1 for i in insights if i.get('brand_sentiment') == 'Negative'),
        'positive': sum(1 for i in insights if i.get('brand_sentiment') == 'Positive'),
        'neutral': sum(1 for i in insights if i.get('brand_sentiment') == 'Neutral'),
    }
    
    # Get representative quotes
    quotes = []
    sorted_insights = sorted(insights, key=lambda x: x.get('signal_strength', 0), reverse=True)
    
    for insight in sorted_insights[:3]:
        text = insight.get('text', '')
        title = insight.get('title', '')
        quote = title if title else (text[:150] + '...' if len(text) > 150 else text)
        quotes.append(quote)
    
    # Analyze themes
    topics = Counter(i.get('taxonomy', {}).get('topic', 'General') for i in insights)
    top_topics = topics.most_common(3)
    
    return {
        'cluster_id': theme_name.lower().replace(' ', '_').replace('&', 'and'),
        'theme': theme_name,
        'insights': insights,
        'stats': stats,
        'quotes': quotes,
        'top_topics': top_topics,
        'sentiment_breakdown': {
            'negative': stats['negative'],
            'positive': stats['positive'], 
            'neutral': stats['neutral']
        }
    }

if __name__ == "__main__":
    create_better_clusters()
