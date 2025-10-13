# precompute_clusters.py — generate cluster cache with filters & money-risk awareness

import os, json, argparse
from datetime import datetime
from typing import List, Dict, Any
from components.cluster_synthesizer import cluster_insights, generate_synthesized_insights
from components.scoring_utils import detect_payments_upi_highasp

PRECOMPUTED_INSIGHTS_PATH="precomputed_insights.json"
CLUSTER_OUTPUT_PATH="precomputed_clusters.json"

def _parse_date(d:str):
    try: return datetime.fromisoformat(d).date()
    except Exception: return None

def _ensure_lists(i:Dict[str,Any])->Dict[str,Any]:
    for k in ("topic_focus","type_subtags","mentions_competitor","mentions_ecosystem_partner"):
        v=i.get(k)
        if v is None: i[k]=[]
        elif isinstance(v,str): i[k]=[v] if v.strip() else []
        elif isinstance(v,list): pass
        else: i[k]=[str(v)]
    if "type_subtag" not in i:
        i["type_subtag"]=i["type_subtags"][0] if i["type_subtags"] else "General"
    return i

def _promote_money_risk(i:Dict[str,Any])->Dict[str,Any]:
    flags=detect_payments_upi_highasp(i.get("text",""))
    if i.get("_payment_issue") is None: i["_payment_issue"]=flags["_payment_issue"]
    if i.get("payment_issue_types") is None: i["payment_issue_types"]=flags["payment_issue_types"]
    if i.get("_upi_flag") is None: i["_upi_flag"]=flags["_upi_flag"]
    if i.get("_high_end_flag") is None: i["_high_end_flag"]=flags["_high_end_flag"]
    if i.get("topic_hint") is None and flags["topic_hint"]: i["topic_hint"]=flags["topic_hint"]
    tf=list(i.get("topic_focus",[]) or [])
    if i["_payment_issue"] and "Payments" not in tf: tf.append("Payments")
    if i["_upi_flag"] and "UPI" not in tf: tf.append("UPI")
    i["topic_focus"]=tf
    return i

def _passes_filters(i:Dict[str,Any], brand:str|None, persona:str|None, topic:str|None, since:str|None, min_score:float|None)->bool:
    if brand and str(i.get("target_brand","")).lower()!=brand.lower(): return False
    if persona and str(i.get("persona","")).lower()!=persona.lower(): return False
    if topic:
        tf=i.get("topic_focus",[])
        if isinstance(tf,str): tf=[tf]
        if topic not in tf: return False
    if since:
        cutoff=_parse_date(since)
        if cutoff:
            d=_parse_date(i.get("last_seen") or i.get("_logged_date") or i.get("post_date") or "")
            if not d or d<cutoff: return False
    if min_score is not None and float(i.get("score",0.0))<float(min_score): return False
    return True

def main():
    ap=argparse.ArgumentParser(description="Precompute cluster cache from precomputed_insights.json")
    ap.add_argument("--brand", type=str)
    ap.add_argument("--persona", type=str)
    ap.add_argument("--topic", type=str)
    ap.add_argument("--since", type=str)
    ap.add_argument("--min-score", type=float, default=None)
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument("--input", type=str, default=PRECOMPUTED_INSIGHTS_PATH)
    ap.add_argument("--output", type=str, default=CLUSTER_OUTPUT_PATH)
    args=ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] File not found: {args.input}"); return

    insights:List[Dict[str,Any]]=json.load(open(args.input,"r",encoding="utf-8"))
    print(f"[INFO] Loaded {len(insights)} insights from {args.input}")

    hydrated=[]
    for i in insights:
        i=_ensure_lists(i)
        i=_promote_money_risk(i)
        hydrated.append(i)

    filtered=[i for i in hydrated if _passes_filters(i,args.brand,args.persona,args.topic,args.since,args.min_score)]
    if args.max_items and len(filtered)>args.max_items: filtered=filtered[:args.max_items]

    print(f"[INFO] Filtered set: {len(filtered)} insights "
          f"(brand={args.brand or '*'}, persona={args.persona or '*'}, topic={args.topic or '*'}, "
          f"since={args.since or '*'}, min_score={args.min_score if args.min_score is not None else '*'})")

    if not filtered:
        print("[WARN] No insights after filters; aborting cluster generation."); return

    print("[INFO] Generating cluster groups…")
    clusters=cluster_insights(filtered)
    cards=generate_synthesized_insights(filtered)

    payments_n=sum(1 for i in filtered if i.get("_payment_issue"))
    upi_n=sum(1 for i in filtered if i.get("_upi_flag"))
    high_asp_n=sum(1 for i in filtered if i.get("_high_end_flag"))
    evidence_total=sum(int(i.get("evidence_count",1)) for i in filtered)

    print(f"[INFO] Diagnostics:")
    print(f"  • Clusters synthesized: {len(cards)}")
    print(f"  • Payments signals: {payments_n} | UPI: {upi_n} | High-ASP: {high_asp_n}")
    print(f"  • Evidence (post-dedupe) total: {evidence_total}")

    data={"clusters":clusters,"cards":cards}
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    json.dump(data, open(args.output,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[✅ DONE] Saved clusters to {args.output}")

if __name__=="__main__":
    main()
