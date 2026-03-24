# deduplicator.py — Near-duplicate detection using SimHash + exact prefix matching
#
# Replaces the naive first-150-chars dedup in process_scraped_data.py with:
#   1. Exact prefix matching (fast, catches identical posts)
#   2. SimHash fingerprinting (catches near-duplicates and cross-platform reposts)
#
# Usage:
#   from components.deduplicator import deduplicate_insights
#   unique = deduplicate_insights(insights, similarity_threshold=3)

import re
import hashlib
from collections import defaultdict
from typing import List, Dict, Any, Tuple

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with",
    "is", "are", "was", "were", "it", "that", "this", "i", "you", "my",
    "we", "they", "them", "he", "she", "as", "at", "be", "by", "from",
    "if", "but", "so", "not", "no", "do", "did", "does", "just", "been",
    "have", "has", "had", "would", "could", "should", "will", "can",
}


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


# ---------------------------------------------------------------------------
# SimHash — 64-bit fingerprint for near-duplicate detection
# ---------------------------------------------------------------------------

def _simhash(tokens: List[str], hashbits: int = 64) -> int:
    """
    Compute a SimHash fingerprint for a list of tokens.
    Two documents with similar content will have similar SimHash values
    (small Hamming distance).
    """
    if not tokens:
        return 0

    v = [0] * hashbits
    for token in tokens:
        # Use MD5 hash of each token as a consistent hash function
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(hashbits):
            bitmask = 1 << i
            if h & bitmask:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def _hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two integers."""
    x = a ^ b
    count = 0
    while x:
        count += 1
        x &= x - 1
    return count


# ---------------------------------------------------------------------------
# N-gram shingling for better near-duplicate detection
# ---------------------------------------------------------------------------

def _shingles(tokens: List[str], n: int = 3) -> List[str]:
    """Create character n-gram shingles from token list."""
    text = " ".join(tokens)
    if len(text) < n:
        return [text]
    return [text[i:i+n] for i in range(len(text) - n + 1)]


def _simhash_shingles(text: str, n: int = 3, hashbits: int = 64) -> int:
    """SimHash using character n-gram shingles (more robust than word tokens)."""
    tokens = _tokenize(text)
    shings = _shingles(tokens, n=n)
    return _simhash(shings, hashbits=hashbits)


# ---------------------------------------------------------------------------
# Deduplication Engine
# ---------------------------------------------------------------------------

def deduplicate_insights(
    insights: List[Dict[str, Any]],
    similarity_threshold: int = 5,
    prefix_chars: int = 150,
    prefer_higher_score: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Deduplicate insights using a two-pass approach:
    1. Exact prefix match (fast, catches identical posts)
    2. SimHash near-duplicate detection (catches paraphrased/cross-posted content)

    Args:
        insights: List of insight dicts
        similarity_threshold: Max Hamming distance to consider as duplicate (0-64).
                             Lower = stricter. 3-5 is typical for near-dupes.
        prefix_chars: Number of leading characters for exact match (pass 1)
        prefer_higher_score: When deduplicating, keep the higher-scored version

    Returns:
        (unique_insights, dedup_stats)
    """
    if not insights:
        return [], {"total": 0, "unique": 0, "exact_dupes": 0, "near_dupes": 0}

    # Pass 1: Exact prefix match (same as before but more robust)
    seen_prefixes = {}
    pass1_survivors = []
    exact_dupes = 0

    for i in insights:
        text = (i.get("text", "") or "").strip()
        if not text:
            continue
        prefix = text[:prefix_chars].lower().strip()
        if prefix in seen_prefixes:
            exact_dupes += 1
            # Keep the one with higher score
            if prefer_higher_score:
                existing_idx = seen_prefixes[prefix]
                existing_score = pass1_survivors[existing_idx].get("score", 0)
                new_score = i.get("score", 0)
                if new_score > existing_score:
                    pass1_survivors[existing_idx] = i
        else:
            seen_prefixes[prefix] = len(pass1_survivors)
            pass1_survivors.append(i)

    # Pass 2: SimHash near-duplicate detection
    # Compute SimHash for all survivors
    hashes = []
    for i in pass1_survivors:
        text = i.get("text", "")
        h = _simhash_shingles(text)
        hashes.append(h)

    # Use bucket-based approach for efficiency:
    # Split hash into bands and only compare within same band
    near_dupes = 0
    is_duplicate = [False] * len(pass1_survivors)
    band_size = 16  # Split 64-bit hash into 4 bands of 16 bits

    for band_start in range(0, 64, band_size):
        band_mask = ((1 << band_size) - 1) << band_start
        buckets = defaultdict(list)

        for idx, h in enumerate(hashes):
            if is_duplicate[idx]:
                continue
            band_value = (h & band_mask) >> band_start
            buckets[band_value].append(idx)

        # Only compare within same bucket (candidate pairs)
        for bucket_indices in buckets.values():
            if len(bucket_indices) < 2:
                continue
            for ii in range(len(bucket_indices)):
                if is_duplicate[bucket_indices[ii]]:
                    continue
                for jj in range(ii + 1, len(bucket_indices)):
                    idx_a = bucket_indices[ii]
                    idx_b = bucket_indices[jj]
                    if is_duplicate[idx_b]:
                        continue

                    dist = _hamming_distance(hashes[idx_a], hashes[idx_b])
                    if dist <= similarity_threshold:
                        # Mark the lower-scored one as duplicate
                        score_a = pass1_survivors[idx_a].get("score", 0)
                        score_b = pass1_survivors[idx_b].get("score", 0)
                        if prefer_higher_score and score_b > score_a:
                            is_duplicate[idx_a] = True
                        else:
                            is_duplicate[idx_b] = True
                        near_dupes += 1

    unique = [ins for ins, dup in zip(pass1_survivors, is_duplicate) if not dup]

    stats = {
        "total": len(insights),
        "after_exact_dedup": len(pass1_survivors),
        "exact_dupes": exact_dupes,
        "near_dupes": near_dupes,
        "unique": len(unique),
        "dedup_rate": round(1 - len(unique) / max(len(insights), 1), 4),
    }

    return unique, stats
