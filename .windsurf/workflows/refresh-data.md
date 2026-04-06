---
description: Full data refresh - scrape, enrich, cluster, push
---

## Full Data Refresh Pipeline

Run these steps in order. Each step marked `// turbo` can auto-run.

### 1. Scrape all sources (~15-20 min, hits rate limits)
// turbo
```powershell
python utils/scrape_all.py
```
Wait for completion. Monitor for rate limit messages — these are normal and resolve automatically.

### 2. Run enrichment pipeline (~30 sec)
// turbo
```powershell
python quick_process.py
```
This also runs delta detection. Check output for "DELTA DETECTION" section to see what changed.

### 3. Regenerate clusters (~25 sec)
// turbo
```powershell
python precompute_clusters.py
```

### 4. Push everything and deploy
// turbo
```powershell
git add -A; git commit -m "data refresh: $(Get-Date -Format 'yyyy-MM-dd')"; git push
```
Streamlit Cloud auto-deploys from main in ~2 minutes.

### Notes
- Delta detection compares current run vs `_pipeline_snapshot.json` from previous run
- If insights count changes significantly, check NOISE_SUBREDDITS in quick_process.py
- If cluster quotes look irrelevant, check `_WORKSTREAM_KEYWORDS` in components/cluster_synthesizer.py

### Deployment guardrails
- Streamlit Cloud auto-deploys from main. Cold boot installs all packages in `requirements.txt`.
- **NEVER add pipeline-only packages** (scikit-learn, pandas, matplotlib, seaborn, networkx, beautifulsoup4, fuzzywuzzy, sentence-transformers) to `requirements.txt`. These go in `requirements-pipeline.txt` only.
- If the app takes >60s to load after a push, check `requirements.txt` for heavy packages that snuck in.
- The `data/` directory is gitignored — only `precomputed_insights.json`, `precomputed_clusters.json`, and `_pipeline_meta.json` are deployed.
