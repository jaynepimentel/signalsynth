# app.py — SignalSynth: Streamlined Collectibles Insight Engine

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
from slugify import slugify

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="SignalSynth", layout="wide")

# ─────────────────────────────────────────────
# Component imports
# ─────────────────────────────────────────────
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.cluster_view_simple import display_clustered_insight_cards
from components.enhanced_insight_view import render_insight_cards
from components.floating_filters import render_floating_filters, filter_by_time

# ─────────────────────────────────────────────
# Env & model
# ─────────────────────────────────────────────
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

def get_model():
    """Lazy-load embedding model only when needed."""
    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("IS_STREAMLIT_CLOUD"):
        return None
    try:
        from sentence_transformers import SentenceTransformer
        try:
            return SentenceTransformer("models/all-MiniLM-L6-v2")
        except Exception:
            return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def coerce_bool(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if str(value).lower() in {"true", "yes", "1"}:
        return "Yes"
    if str(value).lower() in {"false", "no", "0"}:
        return "No"
    return "Unknown"

def normalize_insight(i, suggestion_cache):
    i["ideas"] = suggestion_cache.get(i.get("text",""), [])
    i["persona"] = i.get("persona", "Unknown")
    i["journey_stage"] = i.get("journey_stage", "Unknown")
    i["type_tag"] = i.get("type_tag", "Unclassified")
    i["brand_sentiment"] = i.get("brand_sentiment", "Neutral")
    i["clarity"] = i.get("clarity", "Unknown")
    i["effort"] = i.get("effort", "Unknown")
    i["target_brand"] = i.get("target_brand", "Unknown")
    i["action_type"] = i.get("action_type", "Unclear")
    i["opportunity_tag"] = i.get("opportunity_tag", "General Insight")
    if not i.get("subtag"):
        tf = i.get("topic_focus_list") or i.get("topic_focus") or []
        if isinstance(tf, list) and tf:
            i["subtag"] = tf[0]
        elif isinstance(tf, str) and tf.strip():
            i["subtag"] = tf.strip()
        else:
            i["subtag"] = "General"
    if isinstance(i.get("topic_focus"), list):
        i["topic_focus_list"] = sorted({t for t in i["topic_focus"] if isinstance(t, str) and t})
    elif isinstance(i.get("topic_focus"), str) and i["topic_focus"].strip():
        i["topic_focus_list"] = [i["topic_focus"].strip()]
    else:
        i["topic_focus_list"] = []
    i["_payment_issue_str"] = coerce_bool(i.get("_payment_issue", False))
    i["_upi_flag_str"] = coerce_bool(i.get("_upi_flag", False))
    i["_high_end_flag_str"] = coerce_bool(i.get("_high_end_flag", False))
    i["carrier"] = (i.get("carrier") or "Unknown").upper() if isinstance(i.get("carrier"), str) else "Unknown"
    i["intl_program"] = (i.get("intl_program") or "Unknown").upper() if isinstance(i.get("intl_program"), str) else "Unknown"
    i["customs_flag_str"] = coerce_bool(i.get("customs_flag", False))
    i["evidence_count"] = i.get("evidence_count", 1)
    i["last_seen"] = i.get("last_seen") or i.get("_logged_date") or i.get("post_date") or "Unknown"
    return i

def get_field_values(insight, field):
    val = insight.get(field, None)
    if val is None:
        return ["Unknown"]
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val)
    if "," in s:
        return [v.strip() for v in s.split(",") if v.strip()]
    return [s.strip() or "Unknown"]

def match_multiselect_filters(insight, active_filters, filter_fields):
    for label, field in filter_fields.items():
        selected = active_filters.get(field, [])
        if not selected or "All" in selected:
            continue
        values = get_field_values(insight, field)
        if not any(v in selected for v in values):
            return False
    return True

def generate_ai_brief(entity_type, entity_name, post_text, post_title):
    """Unified AI brief generator for competitors, subsidiaries, and partners."""
    try:
        from components.ai_suggester import _chat, MODEL_MAIN
    except ImportError:
        return "LLM not available. Please configure OpenAI API key."
    prompts = {
        "competitor": f"""You are a Senior Product Strategist at eBay. Analyze this competitive signal about {entity_name}.

Title: {post_title}
Content: {post_text}

Write a brief (5 sentences max):
1. Signal type (threat / advantage / pain point)
2. Threat level (Low/Med/High)
3. What users want
4. One eBay response action
5. Recommended play""",
        "subsidiary": f"""You are a PM at eBay responsible for {entity_name}. Analyze this user feedback.

Title: {post_title}
Content: {post_text}

Write a brief (5 sentences max):
1. Feedback type (bug / feature request / UX issue / praise)
2. Priority (P0-P3)
3. User pain point
4. Quick fix recommendation
5. Success metric""",
        "partner": f"""You are a Partnerships Manager at eBay analyzing {entity_name} feedback.

Title: {post_title}
Content: {post_text}

Write a brief (5 sentences max):
1. Signal type (service issue / integration gap / positive)
2. Impact on eBay users
3. Root cause hypothesis
4. Recommended action
5. Partnership health (Green/Yellow/Red)""",
    }
    try:
        return _chat(
            MODEL_MAIN,
            "You write crisp, actionable strategy briefs. Be direct.",
            prompts.get(entity_type, prompts["competitor"]),
            max_completion_tokens=400,
            temperature=0.4
        )
    except Exception as e:
        return f"Generation failed: {e}"

# ─────────────────────────────────────────────
# Global styles
# ─────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="collapsedControl"] { display: none }
  section[data-testid="stSidebar"] { width: 0px !important; display: none }
  @media (max-width: 768px) {
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.25rem !important; }
    [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    .stButton > button { min-height: 44px !important; }
    .stTabs [data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; }
    .stTabs [data-baseweb="tab"] { white-space: nowrap !important; padding: 8px 12px !important; }
  }
  .stButton > button { min-height: 40px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Header — clean, one-line
# ─────────────────────────────────────────────
st.title("📡 SignalSynth")
st.caption("AI-powered collectibles insight engine — community signals → actionable intelligence")

# ─────────────────────────────────────────────
# Data load
# ─────────────────────────────────────────────
try:
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    try:
        with open("gpt_suggestion_cache.json", "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}

    raw_posts_count = 0
    try:
        with open("data/all_scraped_posts.json", "r", encoding="utf-8") as f:
            raw_posts_count = len(json.load(f))
    except:
        pass

    competitor_posts_count = 0
    competitor_posts_raw = []
    try:
        with open("data/scraped_competitor_posts.json", "r", encoding="utf-8") as f:
            competitor_posts_raw = json.load(f)
            competitor_posts_count = len(competitor_posts_raw)
    except:
        pass

    clusters_count = 0
    try:
        with open("precomputed_clusters.json", "r", encoding="utf-8") as f:
            clusters_data = json.load(f)
            clusters_count = len(clusters_data.get("clusters", []))
    except:
        pass

    normalized = [normalize_insight(i, cache) for i in scraped_insights]

    total = len(normalized)
    complaints = sum(1 for i in normalized if i.get("type_tag") == "Complaint" or i.get("brand_sentiment") == "Negative")
    total_posts = raw_posts_count + competitor_posts_count
    hours_saved = round((total_posts * 2) / 60, 1)

    dates = [i.get("post_date", "") for i in scraped_insights if i.get("post_date")]
    date_range = ""
    if dates:
        valid_dates = sorted([d for d in dates if d and len(d) >= 10])
        if valid_dates:
            date_range = f"{valid_dates[0]} to {valid_dates[-1]}"

except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# ─────────────────────────────────────────────
# KPI banner with context
# ─────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Posts Scraped", f"{total_posts:,}",
              help="Total posts collected from Reddit, Twitter/X, YouTube, forums, and news sites")
with col2:
    st.metric("Actionable Insights", f"{total:,}",
              help=f"Posts filtered for relevance and enriched with topic/sentiment tags. {total} out of {total_posts:,} posts contained actionable signal.")
with col3:
    st.metric("Themes", clusters_count,
              help="AI-grouped clusters of related insights. Each theme represents a strategic area like 'Vault Trust' or 'Shipping Friction' — find them in the Strategy tab.")
with col4:
    st.metric("Est. Hours Saved", f"~{hours_saved}",
              help=f"Estimated time to manually read and categorize {total_posts:,} posts at ~2 min each")

filter_pct = round(total / max(total_posts, 1) * 100, 1)
pipeline_text = f"{total_posts:,} posts → {total:,} insights ({filter_pct}% signal) → {clusters_count} themes"
if date_range:
    st.caption(f"{pipeline_text} · Data: {date_range}")

# ─────────────────────────────────────────────
# 3 Tabs: Dashboard · Explore · Strategy
# ─────────────────────────────────────────────
tabs = st.tabs(["📊 Dashboard", "🔍 Explore", "🧱 Strategy"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1: DASHBOARD — Executive overview
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[0]:
    # Quick-start guide (collapsible, friendly for first-time users)
    with st.expander("💡 New here? Start here — How to use SignalSynth", expanded=False):
        st.markdown("""
### What is SignalSynth?

SignalSynth scrapes **thousands of posts** from Reddit, Twitter/X, YouTube, forums, and news sites — then uses AI to surface the insights that matter most to a collectibles PM.

Instead of reading 10,000+ posts, you get **actionable signals** organized by topic, sentiment, and urgency.

---

### Quick Start (2 minutes)

**1. Check the numbers above** — the KPI bar shows how many posts were scraped, how many became insights, and how many strategic clusters were formed.

**2. Scroll down on this Dashboard tab** — you'll see:
- **Signal Trends** — what topics are spiking (Trust issues? Vault complaints? Shipping problems?)
- **Entity Intelligence** — what competitors (Fanatics, Heritage), partners (PSA), and subsidiaries (Goldin, TCGPlayer) people are talking about
- **Strategic Intelligence** — sentiment breakdown by product area and trends over time

**3. Switch to the Explore tab** to dig into individual user quotes. Use the filters at the top to narrow by:
- **Topic** — Vault, Payments, Trust, Shipping, etc.
- **Type** — Complaints, Feature Requests, Questions
- **Sentiment** — Negative, Positive, Neutral
- Each card shows the **actual user quote**, and you can expand "🧠 AI Analysis" for a synthesized takeaway

**4. Switch to the Strategy tab** to see AI-generated **strategic epics** — clusters of related signals grouped into themes like "Vault Trust Issues" or "Payment Friction." Each epic includes:
- Signal counts and sentiment health
- Top themes and sample quotes
- Buttons to generate **PRDs, BRDs, PRFAQ docs, and Jira tickets**

---

### Tips
- **Filters persist** across the Explore tab — combine topic + sentiment + type to find exactly what you need
- **Deep Dive** (in Explore) calls GPT to generate a richer analysis of any individual insight
- **Document generation** (in Strategy) creates PM-ready artifacts you can paste into your workflow
        """)

    # Two-column layout: charts left, entity intel right
    dash_left, dash_right = st.columns([3, 2])

    with dash_left:
        st.subheader("Signal Trends")
        try:
            display_insight_charts(normalized)
        except Exception as e:
            st.error(f"Chart error: {e}")

    with dash_right:
        st.subheader("Entity Intelligence")
        try:
            # Quick entity breakdown from competitor data
            if competitor_posts_raw:
                comp_groups = defaultdict(int)
                sub_groups = defaultdict(int)
                for p in competitor_posts_raw:
                    name = p.get("competitor", "Unknown")
                    if p.get("competitor_type") == "ebay_subsidiary":
                        sub_groups[name] += 1
                    else:
                        comp_groups[name] += 1

                if comp_groups:
                    st.markdown("**🏢 Competitors**")
                    for name, count in sorted(comp_groups.items(), key=lambda x: -x[1])[:5]:
                        st.markdown(f"- **{name}**: {count} posts")

                if sub_groups:
                    st.markdown("**🏪 Subsidiaries**")
                    for name, count in sorted(sub_groups.items(), key=lambda x: -x[1]):
                        st.markdown(f"- **{name}**: {count} posts")

            # Partner signal counts
            PARTNER_KEYWORDS = {
                "PSA": ["psa vault", "psa grading", "psa grade", "psa turnaround", "psa submission", "psa consignment", "psa offer", "psa buyback", "psa 10", "psa 9"],
                "ComC": ["comc", "check out my cards"],
            }
            partner_counts = {k: 0 for k in PARTNER_KEYWORDS}
            for ins in normalized:
                text = (ins.get("title", "") + " " + ins.get("text", "")).lower()
                for partner, kws in PARTNER_KEYWORDS.items():
                    if any(kw in text for kw in kws):
                        partner_counts[partner] += 1

            if any(v > 0 for v in partner_counts.values()):
                st.markdown("**🤝 Partners**")
                for name, count in sorted(partner_counts.items(), key=lambda x: -x[1]):
                    if count > 0:
                        st.markdown(f"- **{name}**: {count} signals")

            # Sentiment summary
            st.markdown("---")
            neg = sum(1 for i in normalized if i.get("brand_sentiment") == "Negative")
            pos = sum(1 for i in normalized if i.get("brand_sentiment") == "Positive")
            neu = total - neg - pos
            st.markdown(f"**Sentiment:** 🟢 {pos} positive · ⚪ {neu} neutral · 🔴 {neg} negative")

        except Exception as e:
            st.caption(f"Entity data unavailable: {e}")

    # Strategic dashboard (brand trends)
    st.markdown("---")
    try:
        display_brand_dashboard(normalized)
    except Exception as e:
        st.error(f"Dashboard error: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2: EXPLORE — Unified filtered view
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[1]:
    # View selector: Insights vs Entities
    explore_view = st.radio(
        "View",
        ["All Insights", "Competitors", "Subsidiaries", "Partners"],
        horizontal=True,
        key="explore_view"
    )

    if explore_view == "All Insights":
        # Filters
        filter_fields = {"Topic": "subtag", "Type": "type_tag"}
        filters = render_floating_filters(normalized, filter_fields, key_prefix="explore")
        filtered = [i for i in normalized if match_multiselect_filters(i, filters, filter_fields)]
        time_range = filters.get("_time_range", "All Time")
        filtered = filter_by_time(filtered, time_range)
        st.caption(f"Showing {len(filtered)} of {total} insights")
        model = get_model()
        render_insight_cards(filtered, model, key_prefix="explore")

    elif explore_view == "Competitors":
        if not competitor_posts_raw:
            st.info("No competitor data. Run `python utils/scrape_competitors.py`.")
        else:
            comp_groups = defaultdict(list)
            for p in competitor_posts_raw:
                if p.get("competitor_type") != "ebay_subsidiary":
                    comp_groups[p.get("competitor", "Unknown")].append(p)

            all_comps = sorted(comp_groups.keys())
            selected = st.selectbox("Competitor", ["All"] + all_comps, key="explore_comp")

            for comp_name in (all_comps if selected == "All" else [selected]):
                posts = comp_groups.get(comp_name, [])
                if not posts:
                    continue
                with st.container(border=True):
                    st.subheader(f"🏢 {comp_name} ({len(posts)} posts)")
                    sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
                    for idx, post in enumerate(sorted_posts[:10], 1):
                        title = post.get("title", "")[:80] or post.get("text", "")[:80]
                        score = post.get("score", 0)
                        post_id = post.get("post_id", f"{comp_name}_{idx}")
                        with st.expander(f"{idx}. {title}... (⬆️ {score})"):
                            st.markdown(f"> {post.get('text', '')[:500]}")
                            st.caption(f"**Date:** {post.get('post_date', '')} | r/{post.get('subreddit', '')} | [Source]({post.get('url', '')})")
                            brief_key = f"brief_comp_{post_id}"
                            if st.button("⚔️ AI Brief", key=f"btn_{brief_key}"):
                                st.session_state[brief_key] = True
                                st.rerun()
                            if st.session_state.get(brief_key):
                                with st.spinner("Generating..."):
                                    result = generate_ai_brief("competitor", comp_name, post.get("text", ""), post.get("title", ""))
                                st.info(result)

    elif explore_view == "Subsidiaries":
        sub_posts = [p for p in competitor_posts_raw if p.get("competitor_type") == "ebay_subsidiary"]
        if not sub_posts:
            st.info("No subsidiary data found.")
        else:
            sub_groups = defaultdict(list)
            for p in sub_posts:
                sub_groups[p.get("competitor", "Unknown")].append(p)

            all_subs = sorted(sub_groups.keys())
            selected = st.selectbox("Subsidiary", ["All"] + all_subs, key="explore_sub")

            for sub_name in (all_subs if selected == "All" else [selected]):
                posts = sub_groups.get(sub_name, [])
                if not posts:
                    continue
                with st.container(border=True):
                    st.subheader(f"🏪 {sub_name} ({len(posts)} posts)")
                    sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
                    for idx, post in enumerate(sorted_posts[:10], 1):
                        title = post.get("title", "")[:80] or post.get("text", "")[:80]
                        score = post.get("score", 0)
                        post_id = post.get("post_id", f"{sub_name}_sub_{idx}")
                        with st.expander(f"{idx}. {title}... (⬆️ {score})"):
                            st.markdown(f"> {post.get('text', '')[:500]}")
                            st.caption(f"**Date:** {post.get('post_date', '')} | r/{post.get('subreddit', '')} | [Source]({post.get('url', '')})")
                            brief_key = f"brief_sub_{post_id}"
                            if st.button("🔧 AI Brief", key=f"btn_{brief_key}"):
                                st.session_state[brief_key] = True
                                st.rerun()
                            if st.session_state.get(brief_key):
                                with st.spinner("Generating..."):
                                    result = generate_ai_brief("subsidiary", sub_name, post.get("text", ""), post.get("title", ""))
                                st.success(result)

    elif explore_view == "Partners":
        STRATEGIC_PARTNERS = {
            "PSA Vault": ["psa vault", "vault storage", "vault sell", "vault auction", "vault withdraw"],
            "PSA Grading": ["psa grading", "psa grade", "psa turnaround", "psa submission", "psa 10", "psa 9"],
            "PSA Consignment": ["psa consignment", "psa consign", "consignment psa"],
            "PSA Offers": ["psa offer", "psa buyback", "psa buy back", "psa instant"],
            "ComC": ["comc", "check out my cards", "comc consignment", "comc selling"],
        }
        partner_posts = {name: [] for name in STRATEGIC_PARTNERS}
        for ins in normalized:
            text = (ins.get("title", "") + " " + ins.get("text", "")).lower()
            for pname, kws in STRATEGIC_PARTNERS.items():
                if any(kw in text for kw in kws):
                    partner_posts[pname].append(ins)

        all_partners = [p for p in STRATEGIC_PARTNERS if partner_posts[p]]
        if not all_partners:
            st.info("No partner signals found.")
        else:
            selected = st.selectbox("Partner", ["All"] + all_partners, key="explore_partner")

            for pname in (all_partners if selected == "All" else [selected]):
                posts = partner_posts.get(pname, [])
                if not posts:
                    continue
                with st.container(border=True):
                    st.subheader(f"🤝 {pname} ({len(posts)} signals)")
                    sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
                    for idx, post in enumerate(sorted_posts[:10], 1):
                        title = post.get("title", "")[:80] or post.get("text", "")[:80]
                        sentiment = post.get("brand_sentiment", "Neutral")
                        sent_icon = {"Negative": "🔴", "Positive": "🟢"}.get(sentiment, "⚪")
                        post_id = post.get("fingerprint", f"{pname}_{idx}")
                        with st.expander(f"{idx}. {sent_icon} {title}..."):
                            st.markdown(f"> {post.get('text', '')[:500]}")
                            url = post.get("url", "")
                            st.caption(f"**Date:** {post.get('post_date', '')} | [Source]({url})" if url else f"**Date:** {post.get('post_date', '')}")
                            brief_key = f"brief_partner_{post_id}"
                            if st.button("📋 AI Brief", key=f"btn_{brief_key}"):
                                st.session_state[brief_key] = True
                                st.rerun()
                            if st.session_state.get(brief_key):
                                with st.spinner("Generating..."):
                                    result = generate_ai_brief("partner", pname, post.get("text", ""), post.get("title", ""))
                                st.info(result)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: STRATEGY — Clusters + AI doc generation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[2]:
    st.markdown("Generate executive summaries, PRDs, BRDs, and Jira tickets from clustered user signals.")
    try:
        display_clustered_insight_cards(normalized)
    except Exception as e:
        st.error(f"Cluster view error: {e}")
