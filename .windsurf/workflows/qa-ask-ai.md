---
description: QA test Ask AI with executive questions and analyze response quality
---

## QA Test Ask AI Responses

Test the Ask AI pipeline with diverse exec-level questions and grade each response.

### 1. Run 5 test questions through the pipeline
Ask Cascade to run these questions against the live data and assess each response:

**Test Questions:**
1. "Give me an executive briefing — what are the top 3 issues I should act on this week?"
2. "What are the signals around eBay Live — what's working, what's broken, and how does it compare to Whatnot?"
3. "What seller protection gaps are driving the most churn risk right now?"
4. "How is eBay's Price Guide perceived vs Card Ladder — are we the trusted standard?"
5. "What are the biggest authentication and grading pain points, and how do they affect buyer trust?"

### 2. Grade each response on 4 dimensions
- **Actionable**: Does it have specific recommendations with owners and timelines?
- **Useful**: Does it answer the question with enough depth for a VP?
- **Accurate**: Are citations real? Any hallucinated stats?
- **Strategic**: Does it connect to business impact (revenue, churn, competitive)?

### 3. Check source quality
Scan the source list for irrelevant posts:
- Gaming subs (r/Helldivers, r/Borderlands, etc.) → add to NOISE_SUBREDDITS in quick_process.py
- Relationship/meme subs → add to NOISE_SUBREDDITS
- "PSA:" meaning "public service announcement" → tighten PSA regex in quick_process.py
- Promotional content → add patterns to _PROMO_PATTERNS in app.py normalize_insight()

### 4. Common fixes
- **Low citations** → check retrieval scoring in app.py _relevance_score() or components/hybrid_retrieval.py
- **Wrong format** → check question-type detection (_q_briefing, _q_competitive, etc.) and format_guidance templates in app.py
- **Hallucinated stats** → strengthen anti-hallucination rules in system prompt (app.py ~line 1650)
- **Missing signals** → check _TERM_EXPANSIONS in app.py or query expansion in hybrid_retrieval.py
- **Irrelevant sources** → add subreddits to NOISE_SUBREDDITS, then rerun quick_process.py + precompute_clusters.py
