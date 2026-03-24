---
description: Add a new data source (forum, review site, API) to the scraping pipeline
---

## Add a New Data Source

### 1. Create scraper
Add a new scraper function in `utils/scrape_new_forums.py` or create a new file in `utils/`.

For RSS feeds, add to the `RSS_FEEDS` dict in `utils/scrape_new_forums.py`:
```python
"Source Name": ["https://example.com/feed/"],
```

For HTML scraping, create a new function following the `scrape_forum_via_google()` pattern.

### 2. Register in pipeline
Add the output file path to `SCRAPED_FILES` in `quick_process.py`:
```python
"data/scraped_new_source.json",
```

Add the source name to `CURATED_SOURCES` in `quick_process.py` if the scraper already filters for collectibles relevance.

### 3. Test
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python utils/scrape_new_forums.py
```

### 4. Run full pipeline
```powershell
python quick_process.py
python precompute_clusters.py
```

### 5. Push
// turbo
```powershell
git add -A; git commit -m "Add new source: [name]"; git push origin main
```
