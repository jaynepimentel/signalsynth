---
description: QA test Ask AI with executive questions and analyze response quality
---

## QA Test Ask AI Responses

Run programmatic QA against the Ask AI pipeline to verify response quality.

### 1. Run QA test suite
// turbo
```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"; python qa_ask_ai.py
```

### 2. Analyze results
// turbo
```powershell
python qa_analyze.py
```

### 3. Review quality metrics
Check qa_results.json for:
- Citation count per response (target: 5+)
- Structure compliance (Bottom Line, Executive Answer, Signals, Actions)
- Response length (target: 1500-6000 chars)
- Source diversity

### 4. If issues found, fix in app.py
Common fixes:
- Low citations → adjust retrieval boost weights in components/hybrid_retrieval.py
- Wrong format → update format_guidance templates in app.py
- Hallucinated stats → strengthen anti-hallucination rules in system prompt
- Missing signals → check _TERM_EXPANSIONS and _expand_query() in hybrid_retrieval.py
