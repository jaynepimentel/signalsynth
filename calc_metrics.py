#!/usr/bin/env python3
"""Calculate correct metrics"""

import json

with open('precomputed_insights.json', 'r', encoding='utf-8') as f:
    insights = json.load(f)

def _taxonomy_type(insight):
    return insight.get('taxonomy', {}).get('type', insight.get('type_tag', 'Unclassified'))

total = len(insights)
complaints = sum(1 for i in insights if _taxonomy_type(i) == 'Complaint')
complaint_pct = round(complaints / max(total, 1) * 100, 1)
themes = len(set(i.get('taxonomy', {}).get('theme', 'Unknown') for i in insights))

print('CORRECT METRICS:')
print(f'Total insights: {total:,}')
print(f'Complaints: {complaints:,}')
print(f'Complaint %: {complaint_pct}%')
print(f'Themes: {themes}')

print('\nWHAT APP SHOULD SHOW:')
print(f'Signals: {total:,}')
print(f'Complaints: {complaints:,}')
print(f'{complaint_pct}% of signals')
print(f'Themes: {themes}')
