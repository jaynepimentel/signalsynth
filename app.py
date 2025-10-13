# app.py — SignalSynth (keeps Shipping/Auth + adds Payments/UPI/High-ASP, carriers, evidence KPIs)

import os, json, streamlit as st
from dotenv import load_dotenv
from datetime import datetime

from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.cluster_view import display_clustered_insight_cards
from components.emerging_trends import detect_emerging_topics, render_emerging_topics
from components.journey_heatmap import display_journey_heatmap
from components.insight_explorer import display_insight_explorer
from components.ai_suggester import (
    generate_pm_ideas, generate_prd_docx, generate_brd_docx,
    generate_prfaq_docx, generate_jira_bug_ticket, generate_gpt_doc,
    generate_multi_signal_prd
)
from components.strategic_tools import (
    display_signal_digest, display_journey_breakdown,
    display_brand_comparator, display_impact_heatmap,
    display_prd_bundler, display_spark_suggestions
)
from components.enhanced_insight_view import render_insight_cards
from components.floating_filters import render_floating_filters

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="SignalSynth", layout="wide")
load_dotenv()

@st.cache_resource(show_spinner="Loading embedding model...")
def get_model():
    try:
        from sentence_transformers import SentenceTransformer
        model_name=os.getenv("SS_APP_EMBED","intfloat/e5-base-v2")
        try:
            if os.path.isdir(f"models/{model_name.replace('/','_')}"):
                m=SentenceTransformer(f"models/{model_name.replace('/','_')}")
            else:
                m=SentenceTransformer(model_name)
        except Exception:
            if os.path.isdir("models/all-MiniLM-L6-v2"):
                m=SentenceTransformer("models/all-MiniLM-L6-v2")
            else:
                m=SentenceTransformer("all-MiniLM-L6-v2")
        try: m.max_seq_length=int(os.getenv("SS_MAX_SEQ_LEN","384"))
        except Exception: pass
        return m
    except Exception as e:
        st.warning(f"⚠️ Failed to load embedding model: {e}")
        return None

def coerce_bool(value):
    if isinstance(value,bool): return "Yes" if value else "No"
    s=str(value).lower()
    if s in {"true","yes","1"}: return "Yes"
    if s in {"false","no","0"}: return "No"
    return "Unknown"

def normalize_topic_focus(raw):
    if isinstance(raw,list): return sorted({t for t in raw if isinstance(t,str) and t})
    if isinstance(raw,str) and raw.strip(): return [raw.strip()]
    return []

def normalize_insight(i, cache):
    i["ideas"]=cache.get(i.get("text",""),[])
    i["persona"]=i.get("persona","Unknown")
    i["journey_stage"]=i.get("journey_stage","Unknown")
    i["type_tag"]=i.get("type_tag","Unclassified")
    i["brand_sentiment"]=i.get("brand_sentiment","Neutral")
    i["clarity"]=i.get("clarity","Unknown")
    i["effort"]=i.get("effort","Unknown")
    i["target_brand"]=i.get("target_brand","Unknown")
    i["action_type"]=i.get("action_type","Unclear")
    i["opportunity_tag"]=i.get("opportunity_tag","General Insight")
    i["topic_focus_list"]=normalize_topic_focus(i.get("topic_focus"))
    i["_payment_issue_str"]=coerce_bool(i.get("_payment_issue",False))
    i["_upi_flag_str"]=coerce_bool(i.get("_upi_flag",False))
    i["_high_end_flag_str"]=coerce_bool(i.get("_high_end_flag",False))
    i["carrier"]=(i.get("carrier") or "Unknown").upper() if isinstance(i.get("carrier"),str) else "Unknown"
    i["intl_program"]=(i.get("intl_program") or "Unknown").upper() if isinstance(i.get("intl_program"),str) else "Unknown"
    i["customs_flag_str"]=coerce_bool(i.get("customs_flag",False))
    i["evidence_count"]=i.get("evidence_count",1)
    i["last_seen"]=i.get("last_seen") or i.get("_logged_date") or i.get("post_date") or "Unknown"
    txt=(i.get("text") or "").lower()
    speed_words=any(w in txt for w in ["slow","delay","delayed","backlog","turnaround","weeks","months"])
    auth_focus="Authenticity Guarantee" in i["topic_focus_list"]
    grading_focus="Grading" in i["topic_focus_list"]
    shippingish=(i["journey_stage"] in {"Fulfillment","Post-Purchase"}) or ("shipping" in txt) or (i["carrier"]!="Unknown")
    i["speed_risk_str"]=coerce_bool(speed_words and (auth_focus or grading_focus or shippingish))
    return i

def get_field_values(insight, field):
    val=insight.get(field,None)
    if val is None: return ["Unknown"]
    if isinstance(val,list): return [str(x).strip() for x in val if str(x).strip()]
    s=str(val)
    if "," in s: return [v.strip() for v in s.split(",") if v.strip()]
    return [s.strip() or "Unknown"]

def match_multiselect_filters(insight, active_filters, filter_fields):
    for _, field in filter_fields.items():
        selected=active_filters.get(field,[])
        if not selected or "All" in selected: continue
        values=get_field_values(insight, field)
        if not any(v in selected for v in values): return False
    return True

st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")
st.markdown("""
    <style>
      [data-testid="collapsedControl"] { display: none }
      section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

if "show_intro" not in st.session_state: st.session_state.show_intro=True
if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth! What’s here now?", expanded=True):
        st.markdown("""
- Shipping & Authentication signals are preserved and highlighted.
- Added: Payments, UPI, High-ASP, Carrier, International Program, Customs Flag.
- Evidence collapse with `evidence_count` and `last_seen`.
- Decision Tiles in Clusters: Decision, Risk, Owner.
- Speed Risk toggle: isolate “slow shipping/grading/auth” chatter.
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

try:
    scraped_insights=json.load(open("precomputed_insights.json","r",encoding="utf-8"))
    try: cache=json.load(open("gpt_suggestion_cache.json","r",encoding="utf-8"))
    except Exception: cache={}
    normalized=[normalize_insight(i, cache) for i in scraped_insights]
    total=len(normalized)
    complaints=sum(1 for i in normalized if i.get("brand_sentiment")=="Complaint")
    payments=sum(1 for i in normalized if i.get("_payment_issue_str")=="Yes")
    upi=sum(1 for i in normalized if i.get("_upi_flag_str")=="Yes")
    high_asp=sum(1 for i in normalized if i.get("_high_end_flag_str")=="Yes")
    shipping_count=sum(1 for i in normalized if ("shipping" in (i.get("text","").lower())) or (i.get("journey_stage") in {"Fulfillment","Post-Purchase"}) or (i.get("carrier")!="Unknown"))
    auth_count=sum(1 for i in normalized if "Authenticity Guarantee" in (i.get("topic_focus_list") or []))
    st.success(f"✅ Loaded {total} insights")
except Exception as e:
    st.error(f"❌ Failed to load insights: {e}"); st.stop()

c1,c2,c3,c4,c5,c6,c7=st.columns(7)
c1.metric("All Insights", f"{total:,}")
c2.metric("Complaints", f"{complaints:,}")
c3.metric("Shipping-Related", f"{shipping_count:,}", "Fulfillment mentions or carrier tagged")
c4.metric("Auth/AG Mentions", f"{auth_count:,}", "Authenticity Guarantee topics")
c5.metric("Payments Signals", f"{payments:,}", "Payment declined & wire/ACH friction")
c6.metric("UPI Mentions", f"{upi:,}", "Unpaid-item complaints")
c7.metric("High-ASP Flags", f"{high_asp:,}", "Mentions of $1k+, 5k, 10k, etc.")

filter_fields={
    "Target Brand":"target_brand",
    "Persona":"persona",
    "Journey Stage":"journey_stage",
    "Insight Type":"type_tag",
    "Brand Sentiment":"brand_sentiment",
    "Clarity":"clarity",
    "Effort Estimate":"effort",
    "Action Type":"action_type",
    "Opportunity Tag":"opportunity_tag",
    "Topic Focus":"topic_focus_list",
    "Carrier":"carrier",
    "Intl Program":"intl_program",
    "Customs Flag":"customs_flag_str",
    "Payments Flag":"_payment_issue_str",
    "UPI Flag":"_upi_flag_str",
    "High-ASP Flag":"_high_end_flag_str",
    "Speed Risk":"speed_risk_str",
}

qt1,qt2,qt3,qt4=st.columns([1,1,1,1])
q_ship=qt1.toggle("📦 Shipping slice", value=False)
q_auth=qt2.toggle("✅ Auth/AG slice", value=False)
q_pay =qt3.toggle("💳 Payments only", value=False)
q_speed=qt4.toggle("⏱️ Speed Risk", value=False)

quick=normalized
if q_ship:
    quick=[i for i in quick if ("shipping" in (i.get("text","").lower())) or (i.get("journey_stage") in {"Fulfillment","Post-Purchase"}) or (i.get("carrier")!="Unknown")]
if q_auth:
    quick=[i for i in quick if "Authenticity Guarantee" in (i.get("topic_focus_list") or [])]
if q_pay:
    quick=[i for i in quick if i.get("_payment_issue_str")=="Yes"]
if q_speed:
    quick=[i for i in quick if i.get("speed_risk_str")=="Yes"]

tabs=st.tabs(["📌 Insights","🧱 Clusters","📈 Trends","📺 Journey Heatmap","🔎 Explorer","🔥 Emerging","🧠 Strategic Tools"])

with tabs[0]:
    st.header("📌 Individual Insights")
    try:
        filters=render_floating_filters(quick, filter_fields, key_prefix="insights")
        filtered=[i for i in quick if match_multiselect_filters(i, filters, filter_fields)]
        model=get_model()
        render_insight_cards(filtered, model, key_prefix="insights")
    except Exception as e:
        st.error(f"❌ Insights tab error: {e}")

with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    try:
        model=get_model()
        if model: display_clustered_insight_cards(quick)
        else: st.warning("⚠️ Embedding model not available. Skipping clustering.")
    except Exception as e:
        st.error(f"❌ Cluster view error: {e}")

with tabs[2]:
    st.header("📈 Trends + Brand Summary")
    try:
        display_insight_charts(quick)
        display_brand_dashboard(quick)
    except Exception as e:
        st.error(f"❌ Trends tab error: {e}")

with tabs[3]:
    st.header("📺 Journey Heatmap")
    try:
        display_journey_heatmap(quick)
    except Exception as e:
        st.error(f"❌ Journey Heatmap error: {e}")

with tabs[4]:
    st.header("🔎 Insight Explorer")
    try:
        explorer_filters=render_floating_filters(quick, filter_fields, key_prefix="explorer")
        explorer_filtered=[i for i in quick if match_multiselect_filters(i, explorer_filters, filter_fields)]
        results=display_insight_explorer(explorer_filtered)
        if results:
            model=get_model()
            render_insight_cards(results[:50], model, key_prefix="explorer")
    except Exception as e:
        st.error(f"❌ Explorer tab error: {e}")

with tabs[5]:
    st.header("🔥 Emerging Topics")
    try:
        render_emerging_topics(detect_emerging_topics(quick))
    except Exception as e:
        st.error(f"❌ Emerging tab error: {e}")

with tabs[6]:
    st.header("🧠 Strategic Tools")
    try:
        display_spark_suggestions(quick)
        display_signal_digest(quick)
        display_impact_heatmap(quick)
        display_journey_breakdown(quick)
        display_brand_comparator(quick)
        display_prd_bundler(quick)
    except Exception as e:
        st.error(f"❌ Strategic Tools tab error: {e}")
