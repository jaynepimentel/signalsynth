---
description: Full data refresh - scrape, enrich, cluster, push
---

## Full Data Refresh Pipeline

Run these commands in order. You can run them yourself to save Windsurf credits, or ask Cascade to run them.

### 1. Scrape all sources (~15-20 min)
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python utils/scrape_all.py
```

### 2. Scrape new forums (~2 min)
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python utils/scrape_new_forums.py
```

### 3. Run enrichment pipeline (~30 sec)
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python quick_process.py
```

### 4. Optional: GPT enrichment (~45-60 min, costs ~$3-4 on your OpenAI key)
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python quick_process.py --gpt-enrich
```

### 5. Regenerate clusters (~25 sec)
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python precompute_clusters.py
```

### 6. Regenerate embeddings (~5 min, requires Anaconda env)
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; conda run -n base python -c "import json, sys; sys.path.insert(0, '.'); from components.hybrid_retrieval import precompute_embeddings; insights = json.load(open('precomputed_insights.json', 'r', encoding='utf-8')); precompute_embeddings(insights, model_name='all-MiniLM-L6-v2')"
```

### 7. Push to GitHub
// turbo
```powershell
git add precomputed_insights.json precomputed_clusters.json precomputed_embeddings.npy precomputed_embeddings_meta.json _pipeline_meta.json
git commit -m "Data refresh $(Get-Date -Format 'yyyy-MM-dd')"
git push origin main
```

### 8. Reboot Streamlit
Reboot from Streamlit Cloud dashboard.
