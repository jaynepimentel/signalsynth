#!/usr/bin/env python3
"""
GPT-based signal enrichment — replaces regex tagging with LLM-powered classification.

Uses GPT-4o-mini in batch mode for cost-effective, accurate enrichment:
- Signal type (Complaint, Feature Request, Question, Praise, Churn Signal, Discussion)
- Sentiment (Negative, Positive, Neutral, Mixed) — sarcasm-aware
- Topic classification (mapped to eBay Collectibles workstreams)
- Entity extraction (products, competitors, personas mentioned)
- Signal strength scoring (0-100)
- One-line executive summary

Cost: ~$0.30-0.50 per 1,000 signals with gpt-4o-mini
"""

import json
import os
import time
import hashlib
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv()
load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)

from openai import OpenAI

# ── Config ──
MODEL = "gpt-4o-mini"
BATCH_SIZE = 10  # Signals per API call (balance cost vs accuracy)
MAX_WORKERS = 4  # Parallel API calls
CACHE_PATH = "data/gpt_enrichment_cache.json"

# ── Prompt ──
SYSTEM_PROMPT = """You are a signal classifier for eBay's Collectibles & Trading Cards business unit.

For each community signal, output a JSON object with these fields:
- "type": one of ["Complaint", "Feature Request", "Question", "Praise", "Churn Signal", "Bug Report", "Discussion"]
- "sentiment": one of ["Negative", "Positive", "Neutral", "Mixed"]
- "topic": the most specific topic from this list: ["Vault", "Authentication & Grading", "Payments & Checkout", "Shipping & Fulfillment", "Seller Fees & Economics", "Returns & Refunds", "Search & Discovery", "Listing Quality", "Customer Service", "Trust & Safety", "Competitive Intelligence", "Collector Community", "Market & Pricing", "App & Technical", "Live Commerce", "Instant Liquidity", "Account & Policy", "Price Guide", "General"]
- "entities": object with:
  - "products": list of eBay products mentioned (e.g., "Vault", "Authenticity Guarantee", "Promoted Listings", "Price Guide", "Seller Hub", "eBay Live")
  - "competitors": list of competitors mentioned (e.g., "Whatnot", "Fanatics", "Heritage", "Goldin", "TCGPlayer", "COMC", "Beckett", "Vinted")
  - "grading_services": list of grading companies mentioned (e.g., "PSA", "BGS", "SGC", "CGC")
- "persona": one of ["Seller", "Buyer", "Collector", "Investor", "New Seller", "Power Seller", "General"]
- "urgency": one of ["Critical", "High", "Medium", "Low"]
- "executive_summary": one sentence (max 25 words) summarizing the signal for a VP

CRITICAL RULES:
- "Complaint" = user expressing frustration, reporting a problem, or sharing a negative experience
- "Feature Request" = user suggesting an improvement or wanting a new capability
- "Churn Signal" = user explicitly saying they're leaving eBay or switching platforms
- "Mixed" sentiment = post contains both positive and negative elements
- Be SARCASM-AWARE: "I love how eBay screws sellers" is Negative, not Positive
- If a post says "PSA" in the context of "Public Service Announcement" (not grading), don't tag PSA as a grading service
- Goldin and TCGPlayer are eBay SUBSIDIARIES, not competitors"""


def _get_client() -> OpenAI:
    """Get OpenAI client with API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or "YOUR_" in api_key.upper():
        raise ValueError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key)


def _load_cache() -> Dict[str, Any]:
    """Load enrichment cache."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict[str, Any]):
    """Save enrichment cache."""
    os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def _signal_fingerprint(signal: Dict[str, Any]) -> str:
    """Generate a cache key for a signal."""
    text = signal.get("text", "")[:500]
    return hashlib.md5(text.encode()).hexdigest()


def _enrich_batch(client: OpenAI, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich a batch of signals with GPT."""
    # Build the batch prompt
    signal_texts = []
    for idx, sig in enumerate(signals):
        title = (sig.get("title", "") or "")[:150]
        text = (sig.get("text", "") or "")[:400]
        source = sig.get("source", "")
        signal_texts.append(f"[{idx+1}] Source: {source}\nTitle: {title}\nText: {text}")

    user_prompt = f"""Classify these {len(signals)} signals. Return a JSON array with one object per signal, in order.

{chr(10).join(signal_texts)}"""

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=2000,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        response_text = completion.choices[0].message.content or ""

        # Parse JSON response
        parsed = json.loads(response_text)
        # Handle both {"results": [...]} and direct array
        if isinstance(parsed, dict):
            results = parsed.get("results", parsed.get("signals", parsed.get("classifications", [])))
            if not results and len(parsed) == len(signals):
                results = list(parsed.values())
        elif isinstance(parsed, list):
            results = parsed
        else:
            results = []

        return results

    except Exception as e:
        print(f"    ⚠️ Batch enrichment failed: {e}")
        return []


def enrich_signals_with_gpt(
    signals: List[Dict[str, Any]],
    batch_size: int = BATCH_SIZE,
    max_workers: int = MAX_WORKERS,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Enrich signals using GPT-4o-mini for accurate classification.
    
    Returns signals with updated taxonomy, sentiment, entities, and executive summaries.
    Uses caching to avoid re-processing already-enriched signals.
    """
    client = _get_client()
    cache = _load_cache() if use_cache else {}
    
    # Split into cached and uncached
    to_process = []
    cached_results = {}
    for sig in signals:
        fp = _signal_fingerprint(sig)
        if fp in cache:
            cached_results[fp] = cache[fp]
        else:
            to_process.append(sig)
    
    print(f"  GPT enrichment: {len(signals)} signals ({len(cached_results)} cached, {len(to_process)} to process)")
    
    if not to_process:
        # Apply cached enrichments
        for sig in signals:
            fp = _signal_fingerprint(sig)
            if fp in cached_results:
                _apply_enrichment(sig, cached_results[fp])
        return signals
    
    # Process in batches
    batches = [to_process[i:i+batch_size] for i in range(0, len(to_process), batch_size)]
    new_enrichments = {}
    processed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for batch_idx, batch in enumerate(batches):
            future = executor.submit(_enrich_batch, client, batch)
            futures[future] = (batch_idx, batch)
        
        for future in as_completed(futures):
            batch_idx, batch = futures[future]
            try:
                results = future.result()
                for sig, enrichment in zip(batch, results):
                    fp = _signal_fingerprint(sig)
                    new_enrichments[fp] = enrichment
                    cache[fp] = enrichment
                processed += len(batch)
                if processed % 100 == 0 or processed == len(to_process):
                    print(f"    Processed {processed}/{len(to_process)} signals...")
                # Save cache incrementally every 500 signals
                if use_cache and processed % 500 == 0:
                    _save_cache(cache)
            except Exception as e:
                print(f"    ⚠️ Batch {batch_idx} failed: {e}")
                # Save cache on error too
                if use_cache:
                    _save_cache(cache)
    
    # Save updated cache
    if use_cache:
        _save_cache(cache)
    
    # Apply all enrichments (cached + new)
    all_enrichments = {**cached_results, **new_enrichments}
    enriched_count = 0
    for sig in signals:
        fp = _signal_fingerprint(sig)
        if fp in all_enrichments:
            _apply_enrichment(sig, all_enrichments[fp])
            enriched_count += 1
    
    print(f"  ✅ GPT-enriched {enriched_count}/{len(signals)} signals")
    return signals


def _apply_enrichment(signal: Dict[str, Any], enrichment: Dict[str, Any]):
    """Apply GPT enrichment results to a signal."""
    if not enrichment or not isinstance(enrichment, dict):
        return
    
    # Update taxonomy
    gpt_type = enrichment.get("type", "")
    gpt_topic = enrichment.get("topic", "")
    gpt_sentiment = enrichment.get("sentiment", "")
    
    if gpt_type:
        signal["taxonomy"] = signal.get("taxonomy", {})
        signal["taxonomy"]["type"] = gpt_type
        signal["type_tag"] = gpt_type
    
    if gpt_topic:
        signal["taxonomy"] = signal.get("taxonomy", {})
        signal["taxonomy"]["topic"] = gpt_topic
        signal["taxonomy"]["theme"] = gpt_topic
        signal["subtag"] = gpt_topic
    
    if gpt_sentiment:
        signal["brand_sentiment"] = gpt_sentiment
    
    # Entity extraction
    entities = enrichment.get("entities", {})
    if entities:
        signal["_gpt_products"] = entities.get("products", [])
        signal["_gpt_competitors"] = entities.get("competitors", [])
        signal["_gpt_grading_services"] = entities.get("grading_services", [])
        # Merge with existing competitor mentions
        existing_comps = signal.get("mentions_competitor", [])
        new_comps = entities.get("competitors", [])
        signal["mentions_competitor"] = list(set(existing_comps + new_comps))
    
    # Persona
    gpt_persona = enrichment.get("persona", "")
    if gpt_persona:
        signal["persona"] = gpt_persona
    
    # Executive summary
    exec_summary = enrichment.get("executive_summary", "")
    if exec_summary:
        signal["_executive_summary"] = exec_summary
    
    # Urgency
    urgency = enrichment.get("urgency", "")
    if urgency:
        signal["_urgency"] = urgency
    
    # Flag as GPT-enriched
    signal["_gpt_enriched"] = True


if __name__ == "__main__":
    # Test with a small batch
    import sys
    
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        insights = json.load(f)
    
    # Test with first 20 signals
    test_batch = insights[:20]
    print(f"Testing GPT enrichment on {len(test_batch)} signals...")
    
    enriched = enrich_signals_with_gpt(test_batch, batch_size=10, use_cache=False)
    
    for sig in enriched[:5]:
        print(f"\n{'='*60}")
        print(f"Title: {sig.get('title', '')[:80]}")
        print(f"Type: {sig.get('type_tag')}")
        print(f"Sentiment: {sig.get('brand_sentiment')}")
        print(f"Topic: {sig.get('subtag')}")
        print(f"Persona: {sig.get('persona')}")
        print(f"Products: {sig.get('_gpt_products', [])}")
        print(f"Competitors: {sig.get('mentions_competitor', [])}")
        print(f"Summary: {sig.get('_executive_summary', '')}")
