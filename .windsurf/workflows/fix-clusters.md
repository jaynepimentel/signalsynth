---
description: Regenerate strategic theme clusters after data changes
---

## Regenerate Strategic Theme Clusters

Run after data changes, quote relevance fixes, or workstream keyword updates.

### 1. Regenerate clusters with GPT summaries (~25 sec)
// turbo
```powershell
python precompute_clusters.py
```

### 2. Push and deploy
// turbo
```powershell
git add -A; git commit -m "recluster"; git push
```

### Troubleshooting
- **Irrelevant quotes** → tighten `_WORKSTREAM_KEYWORDS` in components/cluster_synthesizer.py. Require multi-word phrases for ambiguous terms (e.g., "whatnot app" not "whatnot"). Add marketplace context checks in `_is_topical_for_workstream()`.
- **Duplicate quotes** → check `seen_snippets` dedup in `synthesize_cluster()`. Increase text comparison window if needed.
- **Wrong signal counts** → check `_get_signal_category()` routing in components/cluster_synthesizer.py
- **"No strategic themes available"** → clusters file structure mismatch, check `_load_clusters()` in cluster_view_simple.py
