#!/usr/bin/env python3
"""Check current data files"""

import json
import os
import datetime

print('🔍 CHECKING CURRENT DATA FILES:')

# Check insights file
with open('precomputed_insights.json', 'r', encoding='utf-8') as f:
    insights = json.load(f)
print(f'✅ Insights file: {len(insights):,} insights')

# Check clusters file  
with open('precomputed_clusters.json', 'r', encoding='utf-8') as f:
    clusters = json.load(f)
print(f'✅ Clusters file: {len(clusters["clusters"])} clusters')
print(f'✅ Cluster signals: {clusters["metadata"]["total_signals"]:,}')

# Check pipeline metadata
with open('_pipeline_meta.json', 'r', encoding='utf-8') as f:
    meta = json.load(f)
print(f'✅ Pipeline meta: {meta.get("total_insights", "Unknown")} insights')
print(f'✅ Generated: {meta.get("generated_at", "Unknown")}')

# Check file timestamps
insights_mtime = os.path.getmtime('precomputed_insights.json')
clusters_mtime = os.path.getmtime('precomputed_clusters.json')
meta_mtime = os.path.getmtime('_pipeline_meta.json')

print(f'📅 Insights modified: {datetime.datetime.fromtimestamp(insights_mtime)}')
print(f'📅 Clusters modified: {datetime.datetime.fromtimestamp(clusters_mtime)}')
print(f'📅 Meta modified: {datetime.datetime.fromtimestamp(meta_mtime)}')

# Calculate actual metrics
total = len(insights)
complaints = sum(1 for i in insights if i.get('taxonomy', {}).get('type') == 'Complaint')
complaint_pct = round(complaints / max(total, 1) * 100, 1)

print(f'🎯 ACTUAL METRICS:')
print(f'   Total: {total:,}')
print(f'   Complaints: {complaints:,}')
print(f'   Percentage: {complaint_pct}%')
print(f'   Themes: {len(clusters["clusters"])}')
