# scoring_utils.py — expanded competitor tagging, payments/UPI/high-ASP detection, topic focus, and sentiment hardening

import os, re, json, hashlib
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)
OPENAI_KEY=os.getenv("OPENAI_API_KEY")
client=OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

CACHE_PATH="gpt_sentiment_cache.json"

def load_cache():
    if os.path.exists(CACHE_PATH):
        try: return json.load(open(CACHE_PATH,"r",encoding="utf-8"))
        except: return {}
    return {}

def save_cache(cache): json.dump(cache, open(CACHE_PATH,"w",encoding="utf-8"), indent=2)
def clear_sentiment_cache():
    global sentiment_cache; sentiment_cache={}
    if os.path.exists(CACHE_PATH):
        try: os.remove(CACHE_PATH)
        except: pass

sentiment_cache=load_cache()

def gpt_estimate_sentiment_subtag(text):
    if not client:
        return {"sentiment":"Neutral","subtags":["General"],"summary":"","frustration":1,"impact":1,"gpt_confidence":0}
    key=hashlib.md5((text or "").strip().encode()).hexdigest()
    if key in sentiment_cache: return sentiment_cache[key]
    try:
        prompt=f"""Classify the feedback and return exactly these fields, one per line:

Sentiment: [Praise|Complaint|Neutral]
Subtags: [comma-separated themes like Refund, Trust Issue, Search]
Frustration: [1-5]
Impact: [1-5]
Summary: [One concise sentence summarizing the issue or praise]

---
{text}
"""
        mdl=os.getenv("OPENAI_MODEL_SCREENER","gpt-4o-mini")
        rsp=client.chat.completions.create(
            model=mdl,
            messages=[{"role":"system","content":"You are a product analyst identifying themes and risk. Output must follow requested fields exactly."},
                      {"role":"user","content":prompt.strip()}],
            temperature=0,max_completion_tokens=220)
        raw=(rsp.choices[0].message.content or "").strip()
        sentiment,subtags,frustration,impact,summary=("Neutral",["General"],1,1,"")
        for line in raw.splitlines():
            h,_,v=line.partition(":"); h=h.strip().lower(); v=v.strip()
            if h=="sentiment": sentiment="Praise" if "praise" in v.lower() else "Complaint" if "complaint" in v.lower() else "Neutral"
            elif h=="subtags": subtags=[s.strip().title() for s in v.strip("[] ").split(",") if s.strip()] or ["General"]
            elif h=="frustration":
                try: frustration=int(re.sub(r"[^0-9]","",v) or "1"); frustration=max(1,min(5,frustration))
                except: pass
            elif h=="impact":
                try: impact=int(re.sub(r"[^0-9]","",v) or "1"); impact=max(1,min(5,impact))
                except: pass
            elif h=="summary": summary=v.strip().capitalize()
        out={"sentiment":sentiment,"subtags":subtags,"frustration":frustration,"impact":impact,"summary":summary,"gpt_confidence":100.0}
        sentiment_cache[key]=out; save_cache(sentiment_cache); return out
    except Exception as e:
        print("[GPT fallback error]", e)
        return {"sentiment":"Neutral","subtags":["General"],"summary":"","frustration":1,"impact":1,"gpt_confidence":0}

# Payments/UPI/High-ASP
RE_HIGH_ASP_AMT=re.compile(r"\$\s?(\d{1,3}(?:[,\s]\d{3})+)|\b(\d{1,2})\s?k\b", re.I)
RE_PAYMENT_DECLINED=re.compile(r"(payment (?:was )?declined|card (?:was )?declined|payment failed|charge failed|credit card (?:issue|problem|declined)|debit card (?:issue|problem|declined)|transaction (?:failed|declined)|couldn['']?t (?:process|complete) payment)", re.I)
RE_INSUFFICIENT_FUNDS=re.compile(r"(insufficient funds|not enough funds|funds not available|balance too low|card limit|over (?:my |the )?limit|maxed out|declined for funds)", re.I)
RE_WIRE=re.compile(r"(wire transfer|bank transfer|ACH|bank wire|bank details|bank instructions|wire instructions|wiring money|wired payment|wire didn['']?t|wire never)", re.I)
RE_UPI=re.compile(r"(unpaid item|UPI\b|did(?:\s*not|\s*n['']?t)\s*pay|non[-\s]?paying bidder|buyer never paid|no payment received|buyer didn['']?t pay|still waiting for payment|payment never came|ghosted after winning|won but (?:didn['']?t|never) paid|case opened.*unpaid|unpaid item strike|file unpaid)", re.I)
RE_PAYMENT_HOLD=re.compile(r"(payment (?:on )?hold|funds? (?:on )?hold|hold on (?:my )?funds|pending (?:for|over) \d+ days|money stuck|payout delayed|can['']?t access (?:my )?funds)", re.I)

def detect_payments_upi_highasp(text:str):
    t=text or ""; types=[]
    if RE_PAYMENT_DECLINED.search(t): types.append("payment_declined")
    if RE_INSUFFICIENT_FUNDS.search(t): types.append("insufficient_funds")
    if RE_WIRE.search(t): types.append("wire_or_bank_transfer")
    if RE_UPI.search(t): types.append("unpaid_item_upi")
    if RE_PAYMENT_HOLD.search(t): types.append("payment_hold")
    high_asp=bool(RE_HIGH_ASP_AMT.search(t) or any(k in (t.lower()) for k in ["high-end","high end","grail","expensive","six figures","five figures"]))
    return {"_payment_issue":bool(types),"payment_issue_types":types,"_upi_flag":"unpaid_item_upi" in types,"_high_end_flag":high_asp,"topic_hint":"Payments" if types else None}

def estimate_severity(text):
    lo=(text or "").lower()
    if any(w in lo for w in ["scam","never received","fraud","fake","authentication error","vault locked","chargeback"]):
        return 90,"Contains fraud-related or high-risk terms"
    if any(w in lo for w in ["issue","problem","broken","confused","error","glitch"]):
        return 70,"Mentions confusion, bugs, or known issues"
    if any(w in lo for w in ["could be better","wish","suggest","slow","should","would be great if"]):
        return 50,"Mild complaint or enhancement request"
    return 30,"Low-intensity or neutral language"

def calculate_pm_priority(insight):
    base=insight.get("score",0); sev=insight.get("severity_score",0)
    conf=insight.get("type_confidence",50); senti=insight.get("sentiment_confidence",50)
    return round((base*0.2)+(sev*0.4)+(conf*0.2)+(senti*0.2),2)

def normalize_priority_scores(insights):
    scores=[i.get("pm_priority_score",0) for i in insights]
    if not scores: return insights
    mn,mx=min(scores),max(scores)
    for i in insights:
        raw=i.get("pm_priority_score",0)
        i["pm_priority_percentile"]=round(100*(raw-mn)/(mx-mn+1e-5),2)
    return insights

def infer_clarity(text):
    t=(text or "").strip().lower()
    return "Needs Clarification" if (len(t)<40 or "???" in t or "idk" in t or "confused" in t) else "Clear"

def detect_competitor_and_partner_mentions(text):
    lo=(text or "").lower()
    competitors=["fanatics","fanatics live","whatnot","whatnot app","alt","alt marketplace","loupe","tiktok","tiktok shopping","heritage","pwcc","elite auction","goldin"]  # pwcc kept as alias — rebranded to Fanatics Collect
    partners=["psa","comc","ebay live","ebay vault","sgc","bgs","pcgs","ngc"]
    market_terms=["consignment","auction house","authentication","population report","vault","grading","case break","repack","live shopping","stream","search","filters","relevancy","refund","return","payout","payment hold"]
    return {
        "competitors":sorted({c for c in competitors if c in lo}),
        "partners":sorted({p for p in partners if p in lo}),
        "market_terms":sorted({m for m in market_terms if m in lo}),
    }

def generate_insight_title(text):
    t=(text or "").strip()
    return t[:60].capitalize()+"..." if len(t)>60 else t.capitalize()

def classify_opportunity_type(text):
    lo=(text or "").lower()
    if any(x in lo for x in ["payment","payment declined","card declined","wire transfer","bank transfer","ach","charge failed"]): return "Conversion Blocker"
    if "upi" in lo or "unpaid item" in lo or "buyer never paid" in lo: return "Policy Risk"
    if any(x in lo for x in ["policy","terms","blocked","suspended"]): return "Policy Risk"
    if any(x in lo for x in ["conversion","checkout","didn’t buy","abandon","hesitated"]): return "Conversion Blocker"
    if any(x in lo for x in ["leaving","quit","stop using","moved to","switched to"]): return "Retention Risk"
    if any(x in lo for x in ["compared to","fanatics","whatnot","alt","loupe","tiktok"]): return "Competitor Signal"
    if any(x in lo for x in ["trust","scam","fraud"]): return "Trust Erosion"
    if any(x in lo for x in ["love","recommend","amazing","best"]): return "Referral Amplifier"
    return "General Insight"

def tag_topic_focus(text):
    lo=(text or "").lower(); tags=[]
    # Price Guide / Valuation - check BEFORE Fees/Pricing to avoid mislabeling
    valuation_phrases = ["what is it worth","what's it worth","what are they worth","what's this worth",
        "price check","value check","how much is","how much are","worth anything","is this worth",
        "good deal","got fleeced","overpaid","underpaid","fair price","market value","comp check",
        "price guide","what should i price","what to price","pricing advice","valuation",
        "what would you price","what do you think it's worth","did i overpay","worth grading"]
    if any(p in lo for p in valuation_phrases): tags.append("Price Guide")
    if any(t in lo for t in ["ebay live","fanatics live","live shopping","stream sale","claim sale","livestream","live stream"]): tags.append("Live Shopping")
    if "vault" in lo: tags.append("Vault")
    if "grading" in lo and any(x in lo for x in ["psa","bgs","sgc","pcgs","ngc"]): tags.append("Grading")
    if any(x in lo for x in ["case break","box break","repack","mystery pack"]): tags.append("Case Break / Repack")
    if "authentication" in lo or "authenticity guarantee" in lo: tags.append("Authenticity Guarantee")
    if "population report" in lo or "pop report" in lo: tags.append("Pop Report")
    if any(x in lo for x in ["search","filter","filters","relevancy"]): tags.append("Search/Relevancy")
    # Only tag Fees/Pricing if NOT already a Price Guide question
    if "Price Guide" not in tags and any(x in lo for x in ["fee","fees","final value fee","seller fee","buyer fee"]): tags.append("Fees/Pricing")
    if any(x in lo for x in ["payout","payouts","payment hold","holds"]): tags.append("Payouts/Holds")
    if any(x in lo for x in ["refund","return","returns","cancel","cancellation"]): tags.append("Returns/Policy")
    if any(x in lo for x in ["consignment","auction house","goldin","heritage","pwcc","elite auction"]): tags.append("Consignment/Auctions")
    if any(x in lo for x in ["bid cancel","bid retracted","cancelled bid","auction pulled","bidder flaked","pulled bid","shill"]): tags.append("Auction Integrity")
    if "auction" in lo and "cancel" in lo: tags.append("Trust")
    # Payment Friction
    if any(x in lo for x in ["payment","payment declined","card declined","wire transfer","bank transfer","ach","charge failed","insufficient funds","not enough funds","funds not available","transaction failed","couldn't process","payment hold","funds on hold","payout delayed"]): tags.append("Payments")
    if any(x in lo for x in ["upi","unpaid item","buyer never paid","no payment received","didn't pay","non-paying bidder","ghosted after winning","still waiting for payment","payment never came","file unpaid","unpaid item strike"]): tags.append("UPI")
    return sorted(list(dict.fromkeys(tags)))

def classify_action_type(text):
    lo=(text or "").lower()
    categories={
        "UI":["filter","search","tooltip","label","navigation"],
        "Feature":["add","introduce","enable","support","integration","combine"],
        "Policy":["refund","suspend","blocked","authentication","return policy","upi","unpaid item"],
        "Marketplace":["grading","shipping","vault","case break","stream","bid","auction","payment","wire transfer","bank transfer"],
    }
    for cat, terms in categories.items():
        if any(t in lo for t in terms): return cat
    return "Unclear"

def calculate_cluster_ready_score(score, frustration, impact):
    return round((score + frustration*5 + impact*5) / 3, 2)
