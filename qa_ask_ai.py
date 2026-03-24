#!/usr/bin/env python3
"""QA test for Ask AI — runs executive questions through the full pipeline."""

import json, os, sys, re
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)

from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# Load data
with open("precomputed_insights.json", "r", encoding="utf-8") as f:
    insights = json.load(f)

# Normalize
def _taxonomy_type(i):
    return (i.get("taxonomy") or {}).get("type", i.get("type_tag", "Unclassified"))

def _taxonomy_topic(i):
    return (i.get("taxonomy") or {}).get("topic", i.get("subtag", "General"))

# Force BM25-only retrieval (embeddings removed from deployment)
retriever = None
print("⚠️ Using BM25-only retrieval (embeddings not deployed)")

# Questions to test
QUESTIONS = [
    "What are the top complaints about eBay's Authenticity Guarantee program?",
    "Which platform is winning sports card sellers — eBay, Whatnot, or Fanatics? Show evidence.",
    "What are the biggest pain points with eBay Vault right now?",
    "Build a weekly exec briefing: top 5 signals I need to act on this week.",
    "What checkout and payment failures are costing eBay transactions right now?",
]

def retrieve_signals(question, all_insights):
    """Retrieve relevant signals for a question."""
    if retriever:
        return retriever.retrieve(question, top_k=25, candidate_pool=60, max_per_source=15)
    
    # Fallback: simple keyword scoring
    q_lower = question.lower()
    q_words = set(q_lower.split())
    
    scored = []
    for p in all_insights:
        text = (p.get("text", "") + " " + p.get("title", "")).lower()
        score = sum(2 for w in q_words if len(w) > 3 and w in text)
        score += p.get("signal_strength", 0) / 20
        scored.append((p, score))
    
    scored.sort(key=lambda x: -x[1])
    return [p for p, s in scored[:25] if s > 0]

def build_context(question, relevant):
    """Build the context block for the AI."""
    context_lines = []
    source_refs = []
    recent_cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    
    for idx, p in enumerate(relevant[:25], 1):
        title = p.get("title", "")[:140]
        text = p.get("text", "")[:500].replace("\n", " ")
        source = p.get("source", "")
        sub = p.get("subreddit", "")
        subtag = _taxonomy_topic(p)
        sentiment = p.get("brand_sentiment", "")
        score = p.get("score", 0)
        type_tag = _taxonomy_type(p)
        persona = p.get("persona", "")
        sig_str = p.get("signal_strength", 0)
        date = p.get("post_date", "")
        url = p.get("url", "")
        sub_label = f"r/{sub}" if sub else source
        ref_label = f"S{idx}"
        freshness = "RECENT" if date >= recent_cutoff else "older"
        context_lines.append(
            f"- [{ref_label}] [{freshness}] [{type_tag}] [{sentiment}] [{subtag}] "
            f"(engagement:{score}, strength:{sig_str}, persona:{persona}, date:{date}, {sub_label}) {title}: {text}"
        )
        if url:
            source_refs.append((ref_label, title or text[:80], url, sub_label))
    
    return "\n".join(context_lines), source_refs

def run_question(question, all_insights):
    """Run a single question through the Ask AI pipeline."""
    print(f"\n{'='*60}")
    print(f"❓ QUESTION: {question}")
    print(f"{'='*60}")
    
    # Retrieve
    relevant = retrieve_signals(question, all_insights)
    print(f"📊 Retrieved {len(relevant)} relevant signals")
    
    # Show source distribution
    src_counts = defaultdict(int)
    for p in relevant:
        src_counts[p.get("source", "Unknown")] += 1
    print(f"📡 Sources: {dict(src_counts)}")
    
    # Build context
    context_block, source_refs = build_context(question, relevant)
    
    # Build system prompt (simplified for testing)
    system_prompt = f"""You are SignalSynth AI — a senior strategy analyst embedded in the eBay Collectibles & Trading Cards business unit.

DOMAIN EXPERTISE:
- eBay SUBSIDIARIES (owned by eBay, NOT competitors): Goldin (premium auctions), TCGPlayer (TCG marketplace)
- TRUE COMPETITORS: Whatnot (live breaks), Fanatics Collect, Heritage Auctions, Alt, COMC, Beckett, Vinted
- eBay products: Authenticity Guarantee, Price Guide, Vault, Promoted Listings, Seller Hub

RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: Answer the question directly.)

### Executive Answer
(4-6 sentences with data backing — cite signal counts, sentiment ratios, key patterns)

### What the Signals Show
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] references)

### Implications for eBay Collectibles
- **Revenue impact**: [How does this affect GMV/take rate?]
- **User impact**: [Which personas? How many affected?]
- **Competitive impact**: [Does this help/hurt vs. competitors?]

### Recommended Actions
1. **[Action Name]** — Owner: [Team]. Timeline: [When]. Expected Impact: [Quantified]
2-4. [Continue with prioritized actions]

### Confidence & Gaps
- Evidence strength: [Strong/Moderate/Weak]
- What's missing: [gaps]

CRITICAL RULES:
- ONLY use information from the RELEVANT SIGNALS below. Never invent data.
- Every claim must have [S#] citations.
- Use VERBATIM quotes in "italics" from signals.
- Write for a VP who has 2 minutes.

RELEVANT SIGNALS:
{context_block}"""

    # Call API
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_completion_tokens=4000,
            temperature=0.4,
        )
        response = (completion.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return None
    
    # Analyze response quality
    print(f"\n📝 RESPONSE ({len(response)} chars):")
    print(response[:2000])
    if len(response) > 2000:
        print(f"\n... [{len(response) - 2000} more chars]")
    
    # Quality metrics
    citation_count = len(re.findall(r'\[S\d+\]', response))
    has_bottom_line = "Bottom Line" in response
    has_exec_answer = "Executive Answer" in response or "Executive" in response
    has_signals = "Signals Show" in response or "Signal Evidence" in response or "User Evidence" in response
    has_actions = "Recommended" in response or "Action" in response
    has_confidence = "Confidence" in response or "Gaps" in response
    quote_count = response.count('"') // 2  # Rough count of quoted text
    
    print(f"\n📊 QUALITY METRICS:")
    print(f"  Citations: {citation_count} {'✅' if citation_count >= 5 else '⚠️' if citation_count >= 3 else '❌'}")
    print(f"  Bottom Line: {'✅' if has_bottom_line else '❌'}")
    print(f"  Executive Answer: {'✅' if has_exec_answer else '❌'}")
    print(f"  Signals section: {'✅' if has_signals else '❌'}")
    print(f"  Actions: {'✅' if has_actions else '❌'}")
    print(f"  Confidence: {'✅' if has_confidence else '❌'}")
    print(f"  Approx quotes: {quote_count}")
    print(f"  Response length: {len(response)} chars {'✅' if 1500 < len(response) < 6000 else '⚠️'}")
    
    return {
        "question": question,
        "response": response,
        "signals_used": len(relevant),
        "citations": citation_count,
        "has_structure": all([has_bottom_line, has_exec_answer, has_signals, has_actions]),
        "length": len(response),
    }

if __name__ == "__main__":
    results = []
    for q in QUESTIONS:
        result = run_question(q, insights)
        if result:
            results.append(result)
    
    # Summary
    print(f"\n\n{'='*60}")
    print("📋 QA SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "✅" if r["has_structure"] and r["citations"] >= 5 else "⚠️"
        print(f"{status} Q: {r['question'][:60]}...")
        print(f"   Citations: {r['citations']} | Signals: {r['signals_used']} | Length: {r['length']}")
    
    # Save results
    with open("qa_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Results saved to qa_results.json")
