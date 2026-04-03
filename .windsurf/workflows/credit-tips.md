---
description: Tips to save Windsurf credits while using advanced LLMs
---

## Credit-Saving Tips for SignalSynth

### What costs Windsurf credits
- Every Cascade chat turn (my responses)
- Tool calls I make (file reads, command runs, searches)
- Longer responses = more output tokens = more credits

### What does NOT cost Windsurf credits
- Python scripts running on your machine (uses your OpenAI key)
- GPT enrichment pipeline ($3-4 on your OpenAI key, $0 Windsurf)
- Ask AI responses in the Streamlit app (your OpenAI key)
- Cluster GPT summaries (your OpenAI key)
- Git commands you run yourself

### Top credit savers

1. **Batch requests**: "scrape, enrich, cluster, and push" in one message
2. **Run long jobs yourself**: Copy the command, run in terminal, come back when done
3. **Use /refresh-data workflow**: Runs the full pipeline with turbo-tagged steps
4. **Skip monitoring**: "run X — don't show me progress, just tell me when done"
5. **Be specific**: "fix the cluster count bug in app.py line 440" vs "something's broken"
6. **Self-serve simple tasks**: git push, pip install, streamlit restart — do these yourself

### When to use Opus vs cheaper models
- **Opus/Claude 3.5**: New features, complex debugging, architecture changes, Ask AI prompt tuning
- **Sonnet/GPT-4o**: Data refreshes, simple fixes, adding search queries, updating keyword lists
- **Any model**: Reading the .windsurfrules gives full project context — no need for Opus just for context

### Quick commands you can run yourself
```powershell
# Scrape + enrich + cluster (full refresh, ~20 min):
python utils/scrape_all.py; python quick_process.py; python precompute_clusters.py

# Push to GitHub:
git add -A; git commit -m "data refresh"; git push

# Just reprocess (no scraping, ~1 min):
python quick_process.py; python precompute_clusters.py
```
