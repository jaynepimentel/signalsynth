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

### Quick commands you can run yourself
```powershell
# Set this once per terminal session:
$env:KMP_DUPLICATE_LIB_OK="TRUE"

# Scrape + enrich + cluster (full refresh, ~20 min):
python utils/scrape_all.py; python quick_process.py; python precompute_clusters.py

# GPT enrich (~60 min, uses YOUR OpenAI key):
python quick_process.py --gpt-enrich

# Push to GitHub:
git add precomputed_insights.json precomputed_clusters.json _pipeline_meta.json; git commit -m "refresh"; git push

# Reboot Streamlit: do from Streamlit Cloud dashboard
```
