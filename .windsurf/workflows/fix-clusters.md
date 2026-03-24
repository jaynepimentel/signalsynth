---
description: Regenerate strategic theme clusters after data changes
---

## Regenerate Strategic Theme Clusters

Run after any data refresh to update the 21 exec-actionable workstream clusters.

### 1. Regenerate clusters with GPT summaries (~25 sec)
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python precompute_clusters.py
```

### 2. Push updated clusters
// turbo
```powershell
git add precomputed_clusters.json; git commit -m "Regenerate clusters"; git push origin main
```

### 3. Reboot Streamlit from dashboard

### Troubleshooting
- "No strategic themes available" → clusters file structure mismatch, check cluster_view_simple.py _load_clusters()
- Wrong signal counts → check _get_signal_category() routing in components/cluster_synthesizer.py
- Promotional content in clusters → check _PROMO_PATTERNS filter in cluster_synthesizer.py
- Gaming content leaking in → check _exclude_keywords and _gaming_keywords filters
