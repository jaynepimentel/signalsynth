#!/usr/bin/env python3
"""Quick process scraped data without heavy embedding - just basic enrichment."""
import json
import os
import re
import unicodedata
from datetime import datetime


def normalize_text(text):
    """Clean up weird formatting, vertical text, and unicode issues."""
    if not text:
        return ""
    
    # Normalize unicode (convert fancy chars to ASCII equivalents)
    text = unicodedata.normalize("NFKC", text)
    
    # Remove zero-width and invisible characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u00ad]', '', text)
    
    # Fix vertical text pattern: single characters on separate lines
    # Pattern matches sequences like "a\nb\nc\nd" (single chars separated by newlines)
    def fix_vertical(match):
        chars = match.group(0)
        # Remove all newlines and spaces between single chars
        return re.sub(r'\s+', '', chars)
    
    # Match sequences of: single char, newline(s), single char, newline(s)... repeated
    text = re.sub(r'(?:\b\w\s*\n\s*){3,}', fix_vertical, text)
    
    # Also fix the pattern where text alternates between normal and vertical
    # Like: "300\ni\nn\ns\nt\ne\na\nd\no\nf\n380\ninsteadof380"
    lines = text.split('\n')
    cleaned_lines = []
    buffer = []
    
    for line in lines:
        line = line.strip()
        if len(line) == 1 and line.isalnum():
            buffer.append(line)
        else:
            if buffer:
                cleaned_lines.append(''.join(buffer))
                buffer = []
            if line:
                cleaned_lines.append(line)
    
    if buffer:
        cleaned_lines.append(''.join(buffer))
    
    text = ' '.join(cleaned_lines)
    
    # Remove duplicate words that appear right next to each other (artifact of vertical text)
    # Like "insteadof380 insteadof380" -> "insteadof380"
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text)
    
    # Remove excessive whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text

# Payment FLOW detection (checkout, processing, transactions - NOT protection/scams)
RE_PAYMENT_FLOW = re.compile(r"\b(checkout|payment processing|managed payments|payment method|card declined|payment failed|payment error|payment stuck|can.?t pay|won.?t process|transaction failed|payment pending|funds held|funds on hold|payout|payout delay|payout pending|direct deposit|bank transfer|wire transfer|ach|instant transfer|payment option|apple pay|google pay|venmo|zelle)\b", re.I)

# High-value payment issues (expensive items)
RE_HIGH_VALUE_PAYMENT = re.compile(r"(\$[1-9]\d{3,}|\$\d+k|\d+\s*thousand|expensive|high value|high.?end|graded|psa 10|bgs 10|gem mint).{0,30}(payment|pay|checkout|transaction|purchase|buy)", re.I)

# Exclude protection/scam noise (not payment FLOW)
PAYMENT_NOISE = [
    "buyer protection", "seller protection", "money back guarantee",
    "scam", "scammer", "scammed", "fraud", "fraudulent", "fake",
    "police report", "file a report", "report to",
    "chargeback", "dispute", "case opened", "case closed",
    "refund request", "return request",
]

# UPI/Non-paying buyer and account restrictions (valid payment signal)
RE_UPI = re.compile(r"(unpaid item|upi|non.?paying buyer|didn.?t pay|never paid|won.?t pay|payment pending|buyer.{0,5}(hasn.?t|didn.?t|won.?t).{0,5}pay|account.{0,10}(blocked|banned|restricted|suspended|limited)|blocked.{0,10}unpaid|banned.{0,10}unpaid|unpaid.{0,10}(strike|warning|block|ban|restrict)|strike.{0,10}unpaid|too many unpaid)", re.I)
# High ASP: $500+, $1k+, expensive items, investment-grade collectibles
RE_HIGH_ASP = re.compile(r"(\$[5-9]\d{2}|\$[1-9],?\d{3,}|\$\d+k|\d+\s*thousand|expensive|high.?value|investment|rare\s+(card|coin|comic)|valuable|psa\s*10|bgs\s*(10|9\.5)|gem\s*mint|pristine|six.?figure|five.?figure)", re.I)
RE_PSA = re.compile(r"(psa|bgs|sgc|csg|cgc).{0,20}(turnaround|wait|days|weeks|months|delay|slow|fast|submit|submission|return|back)", re.I)
# Authenticity Guarantee (AG) - eBay's authentication service for collectibles
RE_AG = re.compile(r"(authenticity guarantee|ebay.{0,10}authenticat|authenticat.{0,10}ebay|\bAG\b.{0,10}ebay|ebay.{0,10}\bAG\b|authentication.{0,10}(card|sneaker|watch|collectible|handbag|jersey)|verified.{0,10}authentic|counterfeit.{0,10}ebay|ebay.{0,10}counterfeit|fake.{0,10}ebay|ebay.{0,10}fake|trust.{0,10}authenticity|authenticity.{0,10}(check|service|program|failed|passed|pending))", re.I)
# Price Guide - eBay's specific feature (tighter regex to avoid false positives)
RE_PRICE_GUIDE = re.compile(r"(ebay.{0,10}price guide|price guide.{0,10}ebay|scan.?to.?price|ebay.{0,10}suggested price|ebay.{0,10}market value|tcgplayer price|what.?s.?my.?card.?worth|card.?value.?ebay|ebay.{0,10}pricing tool)", re.I)
# Vault - eBay's Vault service AND PSA Vault (both are relevant for collectibles)
RE_VAULT = re.compile(r"(ebay.{0,10}vault|vault.{0,10}ebay|ebay vault|psa.{0,10}vault|vault.{0,10}psa|psa vault|vault storage|vault.{0,10}withdraw|withdraw.{0,10}vault|vault.{0,10}card|card.{0,10}vault|vault.{0,10}collectible|store.{0,10}vault|vault.{0,10}service|vault.{0,10}auction|auction.{0,10}vault|vault.{0,10}sell|sell.{0,10}vault|vault.{0,10}list|list.{0,10}vault|vault isn.?t|vault trust)", re.I)
RE_SHIPPING = re.compile(r"(shipping|ship|delivery|deliver|package|parcel|usps|ups|fedex).{0,15}(lost|damage|delay|late|missing|broken|never|issue|problem)", re.I)
RE_REFUND = re.compile(r"(refund|return|money back|chargeback|dispute|case).{0,15}(denied|reject|wait|pending|won|lost|issue|problem)", re.I)
RE_FEES = re.compile(r"(fee|commission|final value|fvf|cost|charge).{0,15}(high|increase|too much|expensive|ridiculous|outrageous)", re.I)
# Trust issues - counterfeits, scams, buyer/seller trust
RE_TRUST = re.compile(r"(trust|trustworthy|legit|legitimate|counterfeit|fake|scam|scammer|fraud|fraudulent|sketchy|shady|suspicious|rip.?off|ripped off|stolen|theft|con artist|bad seller|bad buyer|buyer from hell|seller from hell|never buy from|avoid this|warning|beware|be careful)", re.I)

# Relevance filter - must mention marketplace/platform or have actionable signal
RE_MARKETPLACE = re.compile(r"\b(ebay|mercari|whatnot|goldin|pwcc|comc|myslabs|alt\s*marketplace|fanatics|stockx|goat|tcgplayer|cardmarket)\b", re.I)
RE_SELLER_BUYER = re.compile(r"\b(seller|buyer|listing|sold|purchase|order|transaction|checkout|cart|bid|auction|buy\s*it\s*now|bin|offer|counterfeit|scam|fraud)\b", re.I)
RE_GRADING_SERVICE = re.compile(r"\b(psa|bgs|sgc|csg|cgc|beckett|gem\s*mint|population|pop\s*report|registry|crossover|crack|regrade|resubmit|raw|slab)\b", re.I)

# Noise phrases to exclude (collection flexes, personal stories)
NOISE_PHRASES = [
    "just pulled", "look what i found", "mail day", "new pickup", "got this today",
    "rate my collection", "how did i do", "first ever", "my grail", "finally got",
    "airport", "girlfriend", "boyfriend", "wife", "husband", "mom", "dad",
    "pope", "church", "signed by", "autograph", "met at", "lucky pull",
    "check out my", "showing off", "proud of", "excited about", "cheese",
    "arrived safely", "came back", "just arrived", "mail call", "haul",
    "uncut sheet", "acquired", "added to collection", "newest addition",
    "first submission", "first time", "beyond happy", "so happy", "love this",
    "beautiful card", "stunning", "gorgeous", "amazing pull", "fire pull",
    "hit of the day", "hit of the week", "biggest hit", "insane hit",
    "pc addition", "personal collection", "new pc", "grail acquired",
]

# Pain point indicators (must have at least one for actionable insight)
# Using regex patterns for word boundaries
RE_PAIN = re.compile(r"\b(problem|issue|broken|damaged|lost|missing|wrong|frustrated|annoying|terrible|horrible|worst|awful|can.?t|won.?t|doesn.?t work|not working|failed|error|help me|question|how do i|how can i|why is|why does|anyone else|is this normal|should i|what should|complaint|disappointed|upset|angry|ridiculous|waiting|still waiting|been waiting|no response|no update|overcharged|extra fee|hidden fee|too expensive|slow|delay|delayed|late|took forever|taking forever|scam|scammed|fake|counterfeit|not authentic|refund|return|money back|chargeback|dispute|unpaid|didn.?t pay|won.?t pay|non.?paying|case opened|charge me|want to charge|sent to vault|stuck|hassle|nightmare|don.?t think)\b", re.I)

# Collectibles-specific terms (REQUIRED - this is the eBay Collectibles product)
RE_COLLECTIBLES = re.compile(r"\b(trading card|sports card|baseball card|basketball card|football card|hockey card|pokemon|pokémon|tcg|psa|bgs|sgc|cgc|csg|beckett|graded|grading|slab|slabbed|raw card|gem mint|pop report|population|registry|crossover|regrade|vault|authentication|authenticity guarantee|ag |price guide|scan to price|comps|comp sales|wax|hobby box|blaster|case break|whatnot|goldin|pwcc|comc|alt marketplace|fanatics|topps|panini|upper deck|fleer|bowman|prizm|select|optic|mosaic|chrome|refractor|auto|autograph|patch|relic|rookie|rc |1st edition|charizard|pikachu|holo|holographic|insert|parallel|numbered|/99|/10|one of one|1/1|coin|bullion|silver|gold|numismatic|comic|cgc comic|funko|pop vinyl|collectible|memorabilia)\b", re.I)

# eBay Collectibles product features
RE_EBAY_COLLECTIBLES_FEATURES = re.compile(r"\b(vault|authenticity guarantee|ag |price guide|scan.?to.?price|managed payments|unpaid item|upi|buyer protection|seller protection|item not received|inr|item not as described|inad|final value fee|fvf|promoted listings)\b", re.I)

# Exclude non-collectibles categories
NON_COLLECTIBLES = [
    "electronics", "laptop", "computer", "phone", "iphone", "android", "ram", "cpu", "gpu",
    "shoes", "sneakers", "clothing", "clothes", "shirt", "pants", "dress", "jacket",
    "furniture", "appliance", "kitchen", "bathroom", "home decor",
    "car", "auto", "vehicle", "motorcycle", "bike",
    "thrift", "mystery box", "mystery shoes", "goodwill",
    "playstation", "xbox", "nintendo", "video game", "console",
]

SCRAPED_FILES = [
    "data/all_scraped_posts.json",  # Consolidated from all sources (Reddit, Bluesky, eBay Forums)
    "data/scraped_competitor_posts.json",  # Competitor & subsidiary data
    "data/scraped_reddit_posts.json",  # Fallback
    "data/scraped_bluesky_posts.json",  # Fallback
]


def is_relevant(text, subreddit=""):
    """
    Balanced filter: eBay marketplace issues relevant to collectibles PM.
    Excludes sales posts, non-collectibles, and noise.
    """
    text_lower = text.lower()
    subreddit_lower = subreddit.lower()
    
    # Exclude trading/sales posts (not user feedback)
    sales_patterns = [
        "[h]", "[w]", "[fs]", "[ft]", "[wts]", "[wtb]", "[wtt]",
        "for sale", "selling my", "looking to sell", "paypal only",
        "prices include shipping", "shipping included", "obo",
        "timestampe", "timestamps", "pm me", "dm me",
    ]
    if any(sp in text_lower for sp in sales_patterns):
        return False
    
    # Exclude non-collectibles categories (use word boundaries to avoid false positives like "car" in "card")
    non_collectibles = [
        "shoes", "sneakers", "louboutin", "jordan shoe", "nike shoe", "adidas", "yeezy",
        "clothing", "clothes", "shirt", "pants", " dress ", "jacket", "jeans",
        "thrift", "goodwill", "salvation army", "mystery box",
        "laptop", "computer", "phone", "iphone", "electronics", "ram stick", "cpu",
        "furniture", "appliance", " car ", "vehicle", "motorcycle",
        # Woodworking/tools (not collectibles)
        "woodworking", "hand tool", "power tool", "cabinet", "workbench", "dovetail",
        "plywood", "lumber", "sawdust", "chisel", "plane ", "jointer", "router",
        "lie-nielsen", "veritas", "stanley plane", "wood shop", "workshop",
    ]
    if any(nc in text_lower for nc in non_collectibles):
        return False
    
    # Exclude posts with vertical text formatting (corrupted Reddit markdown)
    lines = text.split('\n')
    single_char_lines = sum(1 for line in lines[:30] if len(line.strip()) == 1)
    if single_char_lines >= 5:
        return False
    
    # Exclude obvious noise phrases
    noise_count = sum(1 for phrase in NOISE_PHRASES if phrase in text_lower)
    if noise_count >= 2:
        return False
    
    # Must have pain indicator
    has_pain = bool(RE_PAIN.search(text))
    if not has_pain:
        return False
    
    # eBay subreddits - include if has pain point
    is_ebay_subreddit = subreddit_lower in ["ebay", "ebayselleradvice", "flipping"]
    if is_ebay_subreddit:
        return True
    
    # Non-eBay subreddits - need eBay mention OR PSA Vault (sells on eBay)
    has_ebay = "ebay" in text_lower
    has_psa_vault = "psa vault" in text_lower or ("vault" in text_lower and "psa" in text_lower)
    
    # PSA grading subreddit with vault mention is highly relevant
    is_psa_subreddit = subreddit_lower in ["psagrading", "psacard"]
    has_vault = "vault" in text_lower
    
    if has_ebay or has_psa_vault or (is_psa_subreddit and has_vault):
        return True
    
    return False


def classify_insight(text):
    """Classify insight type and sentiment for PM relevance."""
    text_lower = text.lower()
    
    # Complaint indicators - frustration, problems, negative experiences
    complaint_indicators = [
        "frustrated", "annoying", "terrible", "horrible", "worst", "awful", "ridiculous",
        "disappointed", "angry", "upset", "hate", "sucks", "garbage", "trash", "scam",
        "unacceptable", "pathetic", "useless", "broken", "ruined", "wasted", "lost money",
        "never again", "done with", "fed up", "sick of", "tired of", "can't believe",
        "absolutely", "completely", "totally", "so annoying", "so frustrating",
        "waste of time", "rip off", "ripoff", "stolen", "robbed", "screwed",
        "incompetent", "lazy", "unprofessional", "nightmare", "disaster", "mess",
        "problem", "issue", "failed", "failure", "doesn't work", "won't work",
        "ugh", "wtf", "smh", "ffs", "bs", "ridiculous", "insane", "crazy",
    ]
    
    # Feature request indicators - suggestions, wants, improvements
    feature_request_indicators = [
        "should", "would be nice", "wish", "they need to", "please add", "feature request",
        "why can't", "why don't", "why doesn't", "why isn't", "it would be great",
        "i want", "we need", "need to add", "should add", "should have", "should be",
        "would love", "would help", "suggestion", "suggest", "idea", "improve",
        "better if", "easier if", "option to", "ability to", "allow us to",
        "can we get", "can you add", "please make", "please let", "please allow",
        "missing feature", "lacking", "needs improvement", "could be better",
    ]
    
    # Bug indicators - technical issues
    bug_indicators = [
        "bug", "glitch", "crash", "error message", "error code", "not working", 
        "broken feature", "won't load", "can't access", "site down", "app crash",
        "technical issue", "system error", "500 error", "404", "timeout"
    ]
    
    # Count matches for each type
    complaint_matches = sum(1 for c in complaint_indicators if c in text_lower)
    feature_matches = sum(1 for f in feature_request_indicators if f in text_lower)
    
    if any(q in text_lower for q in ["how do i", "how can i", "how to", "anyone know", "help me", "need help"]) and "?" in text_lower:
        insight_type = "Question"
    elif complaint_matches >= 1:
        insight_type = "Complaint"
    elif feature_matches >= 1:
        insight_type = "Feature Request"
    elif any(b in text_lower for b in bug_indicators):
        insight_type = "Bug Report"
    else:
        insight_type = "Feedback"
    
    # Determine sentiment - expanded word lists
    negative_words = [
        "frustrated", "annoying", "terrible", "horrible", "worst", "awful", "ridiculous",
        "disappointed", "angry", "upset", "hate", "sucks", "garbage", "trash", "scam",
        "problem", "issue", "bad", "poor", "failed", "broken", "wrong", "unfair",
        "waste", "lost", "stolen", "fake", "fraud", "nightmare", "disaster",
    ]
    positive_words = [
        "great", "love", "amazing", "awesome", "excellent", "perfect", "best", "thank",
        "happy", "glad", "pleased", "satisfied", "helpful", "nice", "good", "wonderful",
        "fantastic", "brilliant", "superb", "outstanding", "impressed", "recommend",
    ]
    
    neg_count = sum(1 for w in negative_words if w in text_lower)
    pos_count = sum(1 for w in positive_words if w in text_lower)
    
    if neg_count > pos_count:
        sentiment = "Negative"
    elif pos_count > neg_count:
        sentiment = "Positive"
    else:
        sentiment = "Neutral"
    
    # Determine urgency
    urgent_words = ["urgent", "asap", "immediately", "now", "critical", "emergency", "stuck", "blocked"]
    is_urgent = any(u in text_lower for u in urgent_words)
    
    return insight_type, sentiment, is_urgent

def load_all():
    posts = []
    for path in SCRAPED_FILES:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"  {path}: {len(data)} posts")
                    posts.extend(data)
            except Exception as e:
                print(f"  {path}: error - {e}")
    return posts

def enrich(post):
    text = normalize_text(post.get("text", "") or "")
    title = normalize_text(post.get("title", "") or "")
    combined = f"{title} {text}".lower()
    
    # Store cleaned text back
    post["text"] = text
    post["title"] = title
    
    if len(combined) < 30:
        return None
    
    # Check for payment noise (protection/scam issues - not payment FLOW)
    has_payment_noise = any(noise in combined for noise in PAYMENT_NOISE)
    
    # Detect payment FLOW signals (exclude noise)
    has_payment_flow = bool(RE_PAYMENT_FLOW.search(combined)) and not has_payment_noise
    has_high_value_payment = bool(RE_HIGH_VALUE_PAYMENT.search(combined)) and not has_payment_noise
    has_payment = has_payment_flow or has_high_value_payment
    has_upi = bool(RE_UPI.search(combined))
    has_high_asp = bool(RE_HIGH_ASP.search(combined))
    has_psa = bool(RE_PSA.search(combined))
    has_ag = bool(RE_AG.search(combined))
    has_price_guide = bool(RE_PRICE_GUIDE.search(combined))
    has_vault = bool(RE_VAULT.search(combined))
    has_shipping = bool(RE_SHIPPING.search(combined))
    has_refund = bool(RE_REFUND.search(combined))
    has_fees = bool(RE_FEES.search(combined))
    has_trust = bool(RE_TRUST.search(combined))
    
    # Build topic focus
    topics = []
    if has_payment or has_upi: topics.append("Payments")
    if has_psa: topics.append("Grading Turnaround")
    if has_ag: topics.append("Authenticity Guarantee")
    if has_price_guide: topics.append("Price Guide")
    if has_vault: topics.append("Vault")
    if has_high_asp: topics.append("High-Value")
    if has_shipping: topics.append("Shipping")
    if has_refund: topics.append("Returns & Refunds")
    if has_fees: topics.append("Fees")
    if has_trust: topics.append("Trust")
    if not topics: topics.append("General")
    
    # Check if post mentions eBay collectibles features
    has_ebay_context = bool(RE_EBAY_COLLECTIBLES_FEATURES.search(combined)) or bool(RE_COLLECTIBLES.search(combined))
    
    # Assign primary subtag (most specific signal) - only if eBay-relevant
    subtag = "General"
    subreddit = post.get("subreddit", "").lower()
    
    # eBay subreddits get eBay Marketplace as default
    if subreddit in ["ebay", "ebayselleradvice", "flipping"]:
        subtag = "eBay Marketplace"
    
    # Override with specific signals if present AND eBay context exists
    # Trust is high priority - counterfeits, scams, fake items are important signals
    if has_trust and has_ebay_context: 
        subtag = "Trust"
    elif has_psa and has_ebay_context: 
        subtag = "Grading Turnaround"
    elif has_ag and has_ebay_context: 
        subtag = "Authenticity Guarantee"
    elif (has_payment or has_upi) and has_ebay_context: 
        subtag = "Payments"
    elif has_refund and has_ebay_context: 
        subtag = "Returns & Refunds"
    elif has_shipping and has_ebay_context: 
        subtag = "Shipping"
    elif has_fees and has_ebay_context: 
        subtag = "Fees"
    elif has_vault and has_ebay_context: 
        subtag = "Vault"
    elif has_price_guide and has_ebay_context: 
        subtag = "Price Guide"
    elif has_high_asp and has_ebay_context: 
        subtag = "High-Value"
    
    # For non-eBay subreddits, only assign if eBay mentioned in text
    if subtag == "General" and has_ebay_context:
        subtag = "eBay Marketplace"
    
    # Classify the insight
    insight_type, sentiment, is_urgent = classify_insight(combined)
    
    # Determine persona more accurately
    if "seller" in combined or "listing" in combined or "sold" in combined:
        persona = "Seller"
    elif "buyer" in combined or "bought" in combined or "purchase" in combined:
        persona = "Buyer"
    elif "collect" in combined:
        persona = "Collector"
    else:
        persona = "General"
    
    # Determine clarity based on text length and specificity
    if len(text) > 200 and any(x in combined for x in ["specific", "example", "when i", "after i"]):
        clarity = "High"
    elif len(text) > 100:
        clarity = "Medium"
    else:
        clarity = "Low"
    
    return {
        "text": text[:2000],
        "title": title,
        "source": post.get("source", "Reddit"),
        "url": post.get("url", ""),
        "subreddit": post.get("subreddit", ""),
        "post_date": post.get("post_date", datetime.now().strftime("%Y-%m-%d")),
        "_logged_date": datetime.now().isoformat(),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
        "_payment_issue": has_payment,
        "_upi_flag": has_upi,
        "_high_end_flag": has_high_asp,
        "is_price_guide_signal": has_price_guide,
        "is_psa_turnaround": has_psa,
        "is_ag_signal": has_ag,
        "is_vault_signal": has_vault,
        "is_shipping_issue": has_shipping,
        "is_refund_issue": has_refund,
        "is_fees_concern": has_fees,
        "is_urgent": is_urgent,
        "topic_focus": topics,
        "topic_focus_list": topics,
        "subtag": subtag,
        "target_brand": "eBay",
        "type_tag": insight_type,
        "brand_sentiment": sentiment,
        "clarity": clarity,
        "persona": persona,
    }

def main():
    print("🚀 Quick processing scraped data...")
    posts = load_all()
    print(f"📊 Loaded {len(posts)} total posts")
    
    # Filter for relevance first
    print("\n🔬 Filtering for eBay-specific actionable insights...")
    relevant_posts = []
    for post in posts:
        text = f"{post.get('title', '')} {post.get('text', '')}"
        subreddit = post.get("subreddit", "")
        if is_relevant(text, subreddit):
            relevant_posts.append(post)
    
    print(f"📊 Relevant posts: {len(relevant_posts)} / {len(posts)} ({100*len(relevant_posts)//len(posts)}%)")
    
    insights = []
    for post in relevant_posts:
        enriched = enrich(post)
        if enriched:
            insights.append(enriched)
    
    # Dedupe
    seen = set()
    unique = []
    for i in insights:
        key = i["text"][:100]
        if key not in seen:
            seen.add(key)
            unique.append(i)
    
    # Save
    with open("precomputed_insights.json", "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved {len(unique)} insights to precomputed_insights.json")
    
    # Stats
    payment = sum(1 for i in unique if i.get("_payment_issue"))
    upi = sum(1 for i in unique if i.get("_upi_flag"))
    psa = sum(1 for i in unique if i.get("is_psa_turnaround"))
    ag = sum(1 for i in unique if i.get("is_ag_signal"))
    pg = sum(1 for i in unique if i.get("is_price_guide_signal"))
    vault = sum(1 for i in unique if i.get("is_vault_signal"))
    shipping = sum(1 for i in unique if i.get("is_shipping_issue"))
    refund = sum(1 for i in unique if i.get("is_refund_issue"))
    fees = sum(1 for i in unique if i.get("is_fees_concern"))
    
    print(f"\n📊 Signals found:")
    print(f"  💳 Payment issues: {payment}")
    print(f"  ⚠️ UPI/Non-paying: {upi}")
    print(f"  ⏱️ PSA/Grading turnaround: {psa}")
    print(f"  🔐 Authentication/AG: {ag}")
    print(f"  📊 Price Guide: {pg}")
    print(f"  🏦 Vault: {vault}")
    print(f"  📦 Shipping issues: {shipping}")
    print(f"  🔄 Refund/Return issues: {refund}")
    print(f"  💰 Fee concerns: {fees}")

if __name__ == "__main__":
    main()
