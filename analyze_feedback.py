#!/usr/bin/env python3
"""
Analyze AI training feedback to identify patterns and improvement opportunities.
"""

import json
from datetime import datetime
from collections import Counter, defaultdict

def analyze_feedback():
    """Analyze the training feedback file and generate insights."""
    
    try:
        with open('ai_training_feedback.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ No training feedback file found.")
        return
    
    positive = [e for e in data if e.get('feedback') == 'positive']
    negative = [e for e in data if e.get('feedback') == 'negative']
    
    print(f"📊 FEEDBACK ANALYSIS")
    print(f"=" * 50)
    print(f"Total responses: {len(data)}")
    print(f"Positive (👍): {len(positive)}")
    print(f"Negative (👎): {len(negative)}")
    print()
    
    # Analyze positive patterns
    if positive:
        print("✅ POSITIVE RESPONSES PATTERNS:")
        print("-" * 30)
        
        # Length analysis
        lengths = [len(e.get('response', '')) for e in positive]
        print(f"Avg response length: {sum(lengths)/len(lengths):.0f} chars")
        print(f"Min/Max length: {min(lengths)} / {max(lengths)} chars")
        
        # Citation density
        citations = [e.get('response', '').count('[S') for e in positive]
        print(f"Avg citations per response: {sum(citations)/len(citations):.1f}")
        
        # Structure analysis
        structure_counts = {
            'Bottom Line': sum(1 for e in positive if '🎯 Bottom Line' in e.get('response', '')),
            'Executive Answer': sum(1 for e in positive if 'Executive Answer' in e.get('response', '')),
            'What the Signals Show': sum(1 for e in positive if 'What the Signals Show' in e.get('response', '')),
            'Implications': sum(1 for e in positive if 'Implications' in e.get('response', '')),
            'Recommended Actions': sum(1 for e in positive if 'Recommended Actions' in e.get('response', ''))
        }
        print("Structure frequency:")
        for struct, count in structure_counts.items():
            print(f"  {struct}: {count}/{len(positive)} ({count/len(positive)*100:.0f}%)")
        
        # Question types that get positive feedback
        question_starts = Counter()
        for e in positive:
            q = e.get('question', '').lower().strip()
            if q.startswith('what'):
                question_starts['What questions'] += 1
            elif q.startswith('how'):
                question_starts['How questions'] += 1
            elif q.startswith('why'):
                question_starts['Why questions'] += 1
            elif 'compare' in q or 'vs' in q:
                question_starts['Comparisons'] += 1
            else:
                question_starts['Other'] += 1
        
        print("\nQuestion types (positive):")
        for qtype, count in question_starts.most_common():
            print(f"  {qtype}: {count}")
        print()
    
    # Analyze negative patterns
    if negative:
        print("❌ NEGATIVE RESPONSES PATTERNS:")
        print("-" * 30)
        
        # Length analysis
        lengths = [len(e.get('response', '')) for e in negative]
        print(f"Avg response length: {sum(lengths)/len(lengths):.0f} chars")
        
        # Citation density
        citations = [e.get('response', '').count('[S') for e in negative]
        print(f"Avg citations per response: {sum(citations)/len(citations):.1f}")
        
        # Common issues
        short_responses = sum(1 for e in negative if len(e.get('response', '')) < 200)
        few_citations = sum(1 for e in negative if e.get('response', '').count('[S') < 3)
        no_structure = sum(1 for e in negative if not any(phrase in e.get('response', '') 
                        for phrase in ['Bottom Line', 'Executive', 'Signals']))
        thin_evidence = sum(1 for e in negative if e.get('was_thin', False))
        no_data_phrases = sum(1 for e in negative if 'don\'t have' in e.get('response', '').lower() 
                             or 'no data' in e.get('response', '').lower())
        
        print("Common issues in negative responses:")
        print(f"  Too short (<200 chars): {short_responses}/{len(negative)}")
        print(f"  Few citations (<3): {few_citations}/{len(negative)}")
        print(f"  No structured format: {no_structure}/{len(negative)}")
        print(f"  Thin evidence: {thin_evidence}/{len(negative)}")
        print(f"  'No data' responses: {no_data_phrases}/{len(negative)}")
        print()
    
    # Generate improvement recommendations
    print("💡 IMPROVEMENT RECOMMENDATIONS:")
    print("-" * 30)
    
    if positive and negative:
        pos_avg_len = sum(len(e.get('response', '')) for e in positive) / len(positive)
        neg_avg_len = sum(len(e.get('response', '')) for e in negative) / len(negative)
        
        if neg_avg_len < pos_avg_len * 0.7:
            print("• Negative responses tend to be shorter - aim for more comprehensive answers")
        
        pos_citations = sum(e.get('response', '').count('[S') for e in positive) / len(positive)
        neg_citations = sum(e.get('response', '').count('[S') for e in negative) / len(negative)
        
        if neg_citations < pos_citations * 0.7:
            print("• Negative responses have fewer citations - include more source references")
        
        if no_structure > len(negative) * 0.5:
            print("• Many negative responses lack structure - always use Bottom Line/Executive/Signals format")
    
    print("• Always start with ### 🎯 Bottom Line")
    print("• Include VERBATIM quotes with [S#] citations and persona context")
    print("• Provide actionable recommendations with owners and timelines")
    print("• When evidence is thin, acknowledge it but still provide related insights")
    print("• Never say 'I don't have data' - provide the best analysis possible")

if __name__ == "__main__":
    analyze_feedback()
