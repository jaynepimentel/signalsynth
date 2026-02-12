#!/usr/bin/env python3
"""Create strategic epic/initiative clusters from insights."""
import json
from datetime import datetime, timezone
from collections import defaultdict

INPUT = "precomputed_insights.json"
OUTPUT = "precomputed_clusters.json"

# Strategic Epics - ordered by priority (signal-based epics first, persona-based last)
STRATEGIC_EPICS = [
    ("Payment & Checkout", {
        "icon": "💳",
        "description": "Reduce friction in payment flow from checkout to payout, including unpaid items",
        "product_opportunity": "Seamless collectibles payment experience",
        "signals": ["_payment_issue", "_upi_flag"],
        "subtags": ["Payments"],
        "keywords": ["payment", "checkout", "funds", "payout", "transaction", "declined", "unpaid", "non-paying", "didn't pay", "won't pay", "blocked", "banned", "restricted", "suspended"],
    }),
    ("Trust & Safety", {
        "icon": "🛡️",
        "description": "Build buyer/seller confidence through authentication, fraud prevention, and transparent marketplace practices",
        "product_opportunity": "End-to-end trust ecosystem for collectibles",
        "signals": ["is_ag_signal", "is_trust_issue"],
        "subtags": ["Trust", "Authenticity Guarantee"],
        "keywords": ["counterfeit", "fake", "scam", "fraud", "authentic", "verification", "trust"],
    }),
    ("High-Value Collectibles", {
        "icon": "�",
        "description": "Premium experience for investment-grade cards, coins, and collectibles",
        "product_opportunity": "White-glove service for high-value transactions",
        "signals": ["_high_end_flag", "is_vault_signal"],
        "subtags": ["High-Value", "Vault"],
        "keywords": ["expensive", "investment", "psa 10", "gem mint", "valuable", "vault", "graded"],
    }),
    ("Buyer Experience", {
        "icon": "🛒",
        "description": "Streamline discovery, purchase, and post-purchase experience for collectors",
        "product_opportunity": "Collector-focused buying journey",
        "signals": ["is_shipping_issue", "is_refund_issue"],
        "subtags": ["Shipping", "Returns & Refunds"],
        "keywords": ["buyer", "purchase", "shipping", "delivery", "return", "refund"],
        "persona": "Buyer",
    }),
    ("Seller Success", {
        "icon": "�",
        "description": "Help sellers price, list, and sell collectibles efficiently with tools and protection",
        "product_opportunity": "Seller toolkit for collectibles specialists",
        "signals": ["is_price_guide_signal"],
        "subtags": [],
        "keywords": ["seller", "listing", "price", "sold", "fee"],
        "persona": "Seller",
    }),
]

def matches_epic(insight, epic_def):
    """Check if an insight matches an epic's criteria."""
    text = (insight.get("text", "") + " " + insight.get("title", "")).lower()
    subtag = insight.get("subtag", "")
    persona = insight.get("persona", "")
    
    # Match by signal flags
    for signal in epic_def.get("signals", []):
        if insight.get(signal):
            return True
    
    # Match by subtag
    if subtag in epic_def.get("subtags", []):
        return True
    
    # Match by persona
    if epic_def.get("persona") and persona == epic_def.get("persona"):
        return True
    
    # Match by keywords (require at least 2 keyword matches for stronger signal)
    keyword_matches = sum(1 for kw in epic_def.get("keywords", []) if kw in text)
    if keyword_matches >= 2:
        return True
    
    return False

def main():
    with open(INPUT, "r", encoding="utf-8") as f:
        insights = json.load(f)
    
    print(f"Loaded {len(insights)} insights")
    print(f"\n📊 Grouping into {len(STRATEGIC_EPICS)} strategic epics...\n")
    
    # Convert list to dict for lookup
    epic_dict = {name: epic_def for name, epic_def in STRATEGIC_EPICS}
    
    # Group insights by strategic epics (ordered iteration)
    epic_groups = defaultdict(list)
    
    for i in insights:
        for epic_name, epic_def in STRATEGIC_EPICS:  # Iterate list of tuples in order
            if matches_epic(i, epic_def):
                epic_groups[epic_name].append(i)
                break  # Assign to first matching epic only
    
    # Create clusters for each epic (maintain priority order)
    clusters = []
    for epic_name, epic_def in STRATEGIC_EPICS:
        items = epic_groups.get(epic_name, [])
        if len(items) < 1:
            continue
        icon = epic_def.get("icon", "📊")
        description = epic_def.get("description", "")
        product_opp = epic_def.get("product_opportunity", "")
        
        # Get sample texts (prioritize negative sentiment)
        sorted_items = sorted(items, key=lambda x: x.get("brand_sentiment") == "Negative", reverse=True)
        sample_texts = [i.get("text", "")[:200] for i in sorted_items[:5]]
        
        # Count sentiment
        negative = sum(1 for i in items if i.get("brand_sentiment") == "Negative")
        positive = sum(1 for i in items if i.get("brand_sentiment") == "Positive")
        complaints = sum(1 for i in items if i.get("type_tag") == "Complaint")
        feature_requests = sum(1 for i in items if i.get("type_tag") == "Feature Request")
        
        cluster = {
            "cluster_id": f"epic_{epic_name.lower().replace(' ', '_').replace('&', 'and')}",
            "subtag": epic_name,
            "label": f"{icon} {epic_name}",
            "title": epic_name,
            "size": len(items),
            "insights": items,
            "insight_ids": [i.get("url", str(idx)) for idx, i in enumerate(items)],
            "sample_texts": sample_texts,
            "description": description,
            "product_opportunity": product_opp,
            "signal_counts": {
                "negative": negative,
                "positive": positive,
                "complaints": complaints,
                "feature_requests": feature_requests,
                "total": len(items),
            },
            "summary": f"{product_opp} — {len(items)} signals ({complaints} complaints, {feature_requests} feature requests)",
            "coherence_score": 0.9,
        }
        clusters.append(cluster)
        print(f"  {icon} {epic_name}")
        print(f"     └─ {len(items)} insights | {complaints} complaints | {feature_requests} FRs")
        print(f"     └─ Opportunity: {product_opp}")
    
    # Build output
    output = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "counts": {
                "input_insights": len(insights),
                "cluster_count": len(clusters),
            },
        },
        "clusters": clusters,
    }
    
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Created {len(clusters)} clusters → {OUTPUT}")

if __name__ == "__main__":
    main()
