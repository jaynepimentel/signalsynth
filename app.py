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

    # Forums & blogs data (Bench Trading, Alt.xyz, Blowout, Net54, COMC, Whatnot, etc.)
    forums_blogs_raw = []
    try:
        with open("data/scraped_forums_blogs_posts.json", "r", encoding="utf-8") as f:
            forums_blogs_raw = json.load(f)
    except:
        pass

    # YouTube data
    youtube_raw = []
    try:
        with open("data/scraped_youtube_posts.json", "r", encoding="utf-8") as f:
            youtube_raw = json.load(f)
    except:
        pass

    # News RSS data
    news_rss_raw = []
    try:
        with open("data/scraped_news_rss_posts.json", "r", encoding="utf-8") as f:
            news_rss_raw = json.load(f)
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
# 6 Tabs
# ─────────────────────────────────────────────
tabs = st.tabs([
    "📊 Overview",
    "⚔️ Competitor Intel",
    "🎯 eBay Voice",
    "📰 Industry & Trends",
    "🔧 Broken Windows",
    "📋 Strategy",
])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1: OVERVIEW — Executive snapshot
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[0]:
    with st.expander("💡 New here? How to use SignalSynth", expanded=False):
        st.markdown("""
**SignalSynth** scrapes thousands of posts from Reddit, Twitter/X, YouTube, forums, and news — then uses AI to surface what matters most to an eBay Collectibles PM.

| Tab | What you'll find |
|-----|-----------------|
| **Competitor Intel** | What Fanatics, Whatnot, Heritage, PWCC are doing. What their customers complain about (conquest opportunities). What people like about them (threats). |
| **eBay Voice** | What eBay's own customers are saying — product feedback, pain points, feature requests, filtered by topic. |
| **Industry & Trends** | News, blog posts, YouTube commentary, forum discussions — the broader collectibles market. |
| **Broken Windows** | Bugs, UX confusion, fee complaints, shipping friction, return disputes — things that erode trust and need fixing. |
| **Strategy** | AI-clustered themes with signal counts. Generate PRDs, BRDs, PRFAQ docs, and Jira tickets. |
        """)

    # Sentiment overview
    neg = sum(1 for i in normalized if i.get("brand_sentiment") == "Negative")
    pos = sum(1 for i in normalized if i.get("brand_sentiment") == "Positive")
    neu = total - neg - pos

    dash_left, dash_right = st.columns([3, 2])

    with dash_left:
        st.subheader("Signal Trends")
        try:
            display_insight_charts(normalized)
        except Exception as e:
            st.error(f"Chart error: {e}")

    with dash_right:
        st.subheader("Pulse Check")
        st.markdown(f"**Sentiment:** 🟢 {pos} positive · ⚪ {neu} neutral · 🔴 {neg} negative")

        # Top pain points
        from collections import Counter
        subtag_neg = Counter(i.get("subtag", "General") for i in normalized if i.get("brand_sentiment") == "Negative")
        if subtag_neg:
            st.markdown("**Top Pain Points (by negative sentiment):**")
            for tag, cnt in subtag_neg.most_common(5):
                pct = round(cnt / max(neg, 1) * 100)
                st.markdown(f"- **{tag}**: {cnt} ({pct}%)")

        # Competitor volume
        if competitor_posts_raw:
            comp_counts = Counter(p.get("competitor", "?") for p in competitor_posts_raw if p.get("competitor_type") != "ebay_subsidiary")
            if comp_counts:
                st.markdown("---")
                st.markdown("**Competitor Chatter:**")
                for name, cnt in comp_counts.most_common(5):
                    st.markdown(f"- **{name}**: {cnt} posts")

    # Brand trend dashboard
    st.markdown("---")
    try:
        display_brand_dashboard(normalized)
    except Exception as e:
        st.error(f"Dashboard error: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2: COMPETITOR INTEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[1]:
    st.markdown("What competitors are doing, what their customers complain about, and where eBay can win.")

    if not competitor_posts_raw:
        st.info("No competitor data. Run `python utils/scrape_competitors.py` to collect competitor signals.")
    else:
        # Split into competitors vs subsidiaries
        comp_posts = defaultdict(list)
        sub_posts_map = defaultdict(list)
        for p in competitor_posts_raw:
            name = p.get("competitor", "Unknown")
            if p.get("competitor_type") == "ebay_subsidiary":
                sub_posts_map[name].append(p)
            else:
                comp_posts[name].append(p)

        # ── Competitor selector ──
        all_comps = sorted(comp_posts.keys())
        comp_view = st.radio("View", ["All Competitors", "Subsidiaries (Goldin, TCGPlayer)"], horizontal=True, key="comp_intel_view")

        if comp_view == "All Competitors":
            selected_comp = st.selectbox("Filter by competitor", ["All"] + all_comps, key="comp_select")
            show_comps = all_comps if selected_comp == "All" else [selected_comp]

            for comp_name in show_comps:
                posts = comp_posts.get(comp_name, [])
                if not posts:
                    continue

                # Classify posts: complaints, praise, policy/product changes
                complaints_list = []
                praise_list = []
                changes_list = []
                discussion_list = []
                for p in posts:
                    text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
                    # Policy/product changes — require specific phrases, not generic words
                    if any(w in text_lower for w in [
                        "announced", "just launched", "new feature", "policy change", "new policy",
                        "rolling out", "beta test", "now available", "just released", "price increase",
                        "fee change", "fee increase", "new partnership", "acquired", "shut down",
                    ]):
                        changes_list.append(p)
                    elif any(w in text_lower for w in [
                        "love", "amazing", "best platform", "better than ebay", "prefer",
                        "switched to", "moved to", "so much better", "way better",
                    ]):
                        praise_list.append(p)
                    elif any(w in text_lower for w in [
                        "problem", "issue", "broken", "terrible", "worst", "hate",
                        "frustrated", "scam", "complaint", "disappointed", "awful",
                        "can't believe", "ridiculous", "rip off", "waste",
                    ]):
                        complaints_list.append(p)
                    else:
                        discussion_list.append(p)

                with st.container(border=True):
                    st.subheader(f"⚔️ {comp_name}")
                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Total Posts", len(posts))
                    mc2.metric("Complaints", len(complaints_list), help="Posts with negative sentiment — potential conquest opportunities")
                    mc3.metric("Praise / Threats", len(praise_list), help="Posts praising this competitor — areas where eBay may be losing")

                    # Policy & product changes
                    if changes_list:
                        with st.expander(f"📢 Policy & Product Changes ({len(changes_list)})", expanded=False):
                            for idx, post in enumerate(sorted(changes_list, key=lambda x: x.get("post_date", ""), reverse=True)[:8], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                st.markdown(f"**{idx}.** {title}")
                                st.markdown(f"> {post.get('text', '')[:300]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

                    # Complaints = conquest opportunities
                    if complaints_list:
                        with st.expander(f"🎯 Conquest Opportunities — What Their Customers Complain About ({len(complaints_list)})", expanded=False):
                            sorted_complaints = sorted(complaints_list, key=lambda x: x.get("score", 0), reverse=True)
                            for idx, post in enumerate(sorted_complaints[:10], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                score = post.get("score", 0)
                                post_id = post.get("post_id", f"comp_{comp_name}_{idx}")
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | r/{post.get('subreddit', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                brief_key = f"brief_conquest_{post_id}"
                                if st.button("⚔️ AI Conquest Brief", key=f"btn_{brief_key}"):
                                    st.session_state[brief_key] = True
                                    st.rerun()
                                if st.session_state.get(brief_key):
                                    with st.spinner("Generating conquest analysis..."):
                                        result = generate_ai_brief("competitor", comp_name, post.get("text", ""), post.get("title", ""))
                                    st.info(result)
                                st.markdown("---")

                    # Praise = competitive threats
                    if praise_list:
                        with st.expander(f"⚠️ Competitive Threats — What People Like About {comp_name} ({len(praise_list)})", expanded=False):
                            for idx, post in enumerate(sorted(praise_list, key=lambda x: x.get("score", 0), reverse=True)[:10], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                st.markdown(f"**{idx}.** {title}")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

                    # General discussion
                    if discussion_list:
                        with st.expander(f"💬 General Discussion ({len(discussion_list)})", expanded=False):
                            for idx, post in enumerate(sorted(discussion_list, key=lambda x: x.get("score", 0), reverse=True)[:10], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                score = post.get("score", 0)
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

        else:
            # Subsidiaries view
            all_subs = sorted(sub_posts_map.keys())
            selected_sub = st.selectbox("Subsidiary", ["All"] + all_subs, key="sub_select")
            show_subs = all_subs if selected_sub == "All" else [selected_sub]

            for sub_name in show_subs:
                posts = sub_posts_map.get(sub_name, [])
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: EBAY VOICE — What eBay customers are saying
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[2]:
    st.markdown("What eBay customers are saying about products and experiences — filtered, enriched, and ready to act on.")

    # Filters
    filter_fields = {"Topic": "subtag", "Type": "type_tag", "Sentiment": "brand_sentiment"}
    filters = render_floating_filters(normalized, filter_fields, key_prefix="ebay_voice")
    filtered = [i for i in normalized if match_multiselect_filters(i, filters, filter_fields)]
    time_range = filters.get("_time_range", "All Time")
    filtered = filter_by_time(filtered, time_range)

    # Quick stats for filtered view
    f_neg = sum(1 for i in filtered if i.get("brand_sentiment") == "Negative")
    f_pos = sum(1 for i in filtered if i.get("brand_sentiment") == "Positive")
    f_complaints = sum(1 for i in filtered if i.get("type_tag") == "Complaint")
    f_requests = sum(1 for i in filtered if i.get("type_tag") == "Feature Request")

    vc1, vc2, vc3, vc4 = st.columns(4)
    vc1.metric("Showing", f"{len(filtered)}", help=f"of {total} total insights")
    vc2.metric("Negative", f_neg, help="Insights with negative sentiment")
    vc3.metric("Complaints", f_complaints)
    vc4.metric("Feature Requests", f_requests)

    # Partner signals section
    STRATEGIC_PARTNERS = {
        "PSA Vault": ["psa vault", "vault storage", "vault sell", "vault auction", "vault withdraw"],
        "PSA Grading": ["psa grading", "psa grade", "psa turnaround", "psa submission", "psa 10", "psa 9"],
        "PSA Consignment": ["psa consignment", "psa consign", "consignment psa"],
        "PSA Offers": ["psa offer", "psa buyback", "psa buy back", "psa instant"],
        "ComC": ["comc", "check out my cards", "comc consignment", "comc selling"],
    }
    partner_counts = {}
    for pname, kws in STRATEGIC_PARTNERS.items():
        cnt = sum(1 for i in filtered if any(kw in (i.get("text", "") + " " + i.get("title", "")).lower() for kw in kws))
        if cnt > 0:
            partner_counts[pname] = cnt

    if partner_counts:
        with st.expander(f"🤝 Partner Signals ({sum(partner_counts.values())} mentions in view)", expanded=False):
            for pname, cnt in sorted(partner_counts.items(), key=lambda x: -x[1]):
                st.markdown(f"- **{pname}**: {cnt} signals")

    # Insight cards
    model = get_model()
    render_insight_cards(filtered, model, key_prefix="ebay_voice")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4: INDUSTRY & TRENDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[3]:
    st.markdown("What the broader collectibles industry is saying — news, blogs, YouTube, and forum discussions.")

    # Combine all industry sources
    industry_posts = []

    # News RSS
    for p in news_rss_raw:
        p["_industry_source"] = "News"
        industry_posts.append(p)

    # YouTube — group comments by video, filter for quality comments only
    YT_QUALITY_KW = [
        "ebay", "fee", "shipping", "listing", "seller", "buyer", "auction",
        "promoted", "vault", "authenticity", "fanatics", "whatnot", "heritage",
        "tcgplayer", "goldin", "price", "value", "market", "invest", "flip",
        "profit", "trend", "crash", "overpriced", "grading", "psa", "bgs",
        "topps", "panini", "bowman", "prizm", "quality control", "shorted",
        "missing auto", "scam", "fake", "rip off", "robbery", "hobby",
        "industry", "future", "license", "monopoly",
    ]
    YT_SPAM = ["sign up for", "use this link", "use code", "subscribe", "check out my", "follow me", "giveaway"]

    def _yt_comment_quality(c):
        """Return True if comment is worth showing."""
        text = c.get("text", "")
        text_lower = text.lower()
        likes = c.get("like_count", 0) or 0
        if len(text) < 50:
            return False
        if any(sp in text_lower for sp in YT_SPAM):
            return False
        kw_hits = sum(1 for kw in YT_QUALITY_KW if kw in text_lower)
        if likes >= 5 and kw_hits >= 1:
            return True
        if kw_hits >= 2 and len(text) >= 80:
            return True
        if likes >= 15:
            return True
        return False

    yt_videos = {}  # url -> {video_post, comments: []}
    for p in youtube_raw:
        url = p.get("url", "")
        source = p.get("source", "")
        if source == "YouTube (comment)":
            if url not in yt_videos:
                yt_videos[url] = {"video": None, "comments": []}
            # Only keep quality comments
            if _yt_comment_quality(p):
                yt_videos[url]["comments"].append(p)
        else:
            if url not in yt_videos:
                yt_videos[url] = {"video": p, "comments": []}
            else:
                yt_videos[url]["video"] = p

    for url, group in yt_videos.items():
        video = group["video"]
        comments = group["comments"]
        if video:
            video["_industry_source"] = "YouTube"
            video["_yt_comments"] = comments
            industry_posts.append(video)
        elif comments:
            # No transcript/video post, create a summary entry from quality comments
            representative = comments[0].copy()
            representative["_industry_source"] = "YouTube"
            representative["source"] = "YouTube"
            representative["_yt_comments"] = comments
            representative["text"] = f"{len(comments)} quality comments on this video"
            industry_posts.append(representative)

    # Forums & Blogs
    for p in forums_blogs_raw:
        src = p.get("source", "Forum")
        p["_industry_source"] = src
        industry_posts.append(p)

    # Sort by date
    industry_posts.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    if not industry_posts:
        st.info("No industry data. Run scrapers to collect news, YouTube, and forum data.")
    else:
        # Source breakdown
        from collections import Counter
        source_counts = Counter(p.get("_industry_source", "?") for p in industry_posts)

        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Total Industry Posts", len(industry_posts))
        ic2.metric("Sources", len(source_counts))
        ic3.metric("Most Recent", industry_posts[0].get("post_date", "?") if industry_posts else "N/A")

        # Source filter
        all_sources = ["All"] + sorted(source_counts.keys())
        selected_source = st.selectbox("Filter by source", all_sources, key="industry_source")

        if selected_source != "All":
            industry_posts = [p for p in industry_posts if p.get("_industry_source") == selected_source]

        # Search
        search_term = st.text_input("Search industry posts", "", key="industry_search")
        if search_term:
            search_lower = search_term.lower()
            industry_posts = [p for p in industry_posts if search_lower in (p.get("text", "") + " " + p.get("title", "")).lower()]

        st.caption(f"Showing {len(industry_posts)} posts")

        # Paginate
        per_page = 15
        total_pages = max(1, (len(industry_posts) + per_page - 1) // per_page)
        if "industry_page" not in st.session_state:
            st.session_state["industry_page"] = 0
        st.session_state["industry_page"] = min(st.session_state["industry_page"], total_pages - 1)

        if total_pages > 1:
            nav1, nav2, nav3 = st.columns([1, 3, 1])
            with nav1:
                if st.button("◀ Prev", key="ind_prev", disabled=st.session_state["industry_page"] == 0):
                    st.session_state["industry_page"] -= 1
                    st.rerun()
            with nav2:
                st.markdown(f"**Page {st.session_state['industry_page'] + 1} of {total_pages}**")
            with nav3:
                if st.button("Next ▶", key="ind_next", disabled=st.session_state["industry_page"] >= total_pages - 1):
                    st.session_state["industry_page"] += 1
                    st.rerun()

        start = st.session_state["industry_page"] * per_page
        paged = industry_posts[start:start + per_page]

        for idx, post in enumerate(paged, start=start + 1):
            source_label = post.get("_industry_source", post.get("source", "?"))
            title = post.get("title", "")[:120] or post.get("text", "")[:120]
            date = post.get("post_date", "")
            url = post.get("url", "")

            source_icons = {
                "News": "📰", "YouTube": "🎬", "YouTube (transcript)": "🎬",
                "YouTube (comment)": "💬", "Alt.xyz Blog": "📝",
                "Blowout Forums": "🗣️", "Net54 Baseball": "⚾",
                "COMC": "🃏", "Whatnot": "📱", "Fanatics Collect": "🏈",
                "Bench Trading": "🔄", "TCDB": "🗂️",
            }
            icon = source_icons.get(source_label, "📄")

            yt_comments = post.get("_yt_comments", [])
            comment_label = f" · 💬 {len(yt_comments)} comments" if yt_comments else ""

            with st.expander(f"{icon} **{title}** — {source_label} · {date}{comment_label}"):
                text = post.get("text", "")
                if len(text) > 600:
                    st.markdown(f"> {text[:600]}...")
                elif text:
                    st.markdown(f"> {text}")
                meta_parts = [f"**Source:** {source_label}"]
                if date:
                    meta_parts.append(f"**Date:** {date}")
                if url:
                    meta_parts.append(f"[🔗 Original]({url})")
                st.caption(" · ".join(meta_parts))

                # Show YouTube comments nested under the video
                if yt_comments:
                    st.markdown("---")
                    st.markdown(f"**💬 Top Comments ({len(yt_comments)}):**")
                    sorted_comments = sorted(yt_comments, key=lambda c: c.get("like_count", 0) or 0, reverse=True)
                    for ci, comment in enumerate(sorted_comments[:8], 1):
                        c_text = comment.get("text", "")[:300]
                        c_user = comment.get("username", "")
                        c_likes = comment.get("like_count", 0) or 0
                        likes_str = f" · 👍 {c_likes}" if c_likes else ""
                        st.markdown(f"**{ci}.** {c_text}")
                        st.caption(f"u/{c_user}{likes_str}")
                    if len(yt_comments) > 8:
                        st.caption(f"... and {len(yt_comments) - 8} more comments")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 5: BROKEN WINDOWS — Bugs, UX confusion, fee friction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[4]:
    st.markdown("Things that are broken, confusing, or frustrating for eBay customers — bugs, UX friction, fee confusion, and product pain points that erode trust.")

    # Define broken-window categories with detection keywords
    BW_CATEGORIES = {
        "Bugs & Errors": {
            "keywords": ["bug", "glitch", "error", "crash", "broken", "not working", "doesn't work", "won't load", "can't access", "404", "white screen", "blank page", "stuck", "frozen", "loop", "down ", "outage"],
            "icon": "🐛",
            "description": "Technical bugs, errors, and things that are literally broken",
        },
        "UX Confusion": {
            "keywords": ["confus", "unclear", "don't understand", "can't find", "where is", "how do i", "how to", "makes no sense", "unintuitive", "hard to find", "hidden", "not obvious", "misleading", "why does ebay", "why can't i", "doesn't make sense"],
            "icon": "😕",
            "description": "Users who can't figure out how to do something — UX gaps",
        },
        "Fee Complaints": {
            "keywords": ["fee", "commission", "too expensive", "overcharged", "hidden fee", "extra charge", "final value", "insertion fee", "take rate", "13%", "12.9%", "tax ", "1099", "sales tax"],
            "icon": "💸",
            "description": "Complaints about eBay's fee structure, pricing, or unexpected charges",
        },
        "Promoted Listings & Ads": {
            "keywords": ["promoted listing", "promoted", "ad ", "ads ", "advertising", "pay to play", "boost", "sponsored", "promoted standard", "promoted advanced", "ad rate"],
            "icon": "📢",
            "description": "Promoted listings frustration — forced visibility tax, ad spend, pay-to-play concerns",
        },
        "Payment & Payout Holds": {
            "keywords": ["payment hold", "payout", "pending", "funds held", "managed payments", "hold my money", "can't get paid", "money held", "release my funds", "payment processing", "payment delay"],
            "icon": "💳",
            "description": "Payment holds, payout delays, managed payments friction",
        },
        "Shipping Friction": {
            "keywords": ["shipping label", "tracking not", "lost package", "damaged in transit", "shipping cost", "standard envelope", "can't print label", "wrong weight", "shipping estimate", "usps", "fedex", "shipping damage", "arrived damaged", "crushed"],
            "icon": "📦",
            "description": "Shipping-related pain points — labels, tracking, costs, damage",
        },
        "Returns & Disputes": {
            "keywords": ["inad", "item not as described", "forced return", "return abuse", "partial refund", "case opened", "dispute", "money back guarantee", "buyer scam", "empty box", "return request", "refund", "sent back", "sided with buyer", "unfair return"],
            "icon": "🔄",
            "description": "Return policy friction, INAD abuse, dispute resolution problems",
        },
        "Trust & Safety": {
            "keywords": ["scam", "fraud", "fake", "counterfeit", "stolen", "suspicious", "sketchy", "shill", "shill bid", "fake listing", "not authentic", "replica", "knock off"],
            "icon": "🛡️",
            "description": "Scams, fraud, counterfeits, and trust issues on the platform",
        },
        "Grading & Authentication": {
            "keywords": ["grade", "grading", "graded", "psa ", "bgs ", "cgc ", "sgc ", "misgrade", "wrong grade", "crack out", "crossover", "slab", "authentic", "authentication", "not real"],
            "icon": "🏅",
            "description": "Grading disputes, authentication problems, misgraded items",
        },
        "Account & Policy Issues": {
            "keywords": ["account suspended", "account restricted", "banned", "limited", "locked out", "verification", "policy violation", "vero", "removed listing", "taken down", "flagged", "delisted", "blocked"],
            "icon": "🔒",
            "description": "Account restrictions, policy enforcement confusion, VERO takedowns",
        },
        "Search & Discovery": {
            "keywords": ["search broken", "can't find my listing", "no views", "visibility", "algorithm", "cassini", "best match", "search ranking", "not showing up", "buried", "no impressions", "no traffic"],
            "icon": "🔍",
            "description": "Search/discovery issues — listings not showing, ranking problems",
        },
        "Seller Protection": {
            "keywords": ["no protection", "seller protection", "always side with buyer", "unfair", "ebay sided", "no recourse", "lost case", "ebay doesn't care", "hate selling", "done with ebay", "leaving ebay"],
            "icon": "🛑",
            "description": "Sellers feeling unprotected — eBay siding with buyers, no recourse, churn risk",
        },
        "Customer Service": {
            "keywords": ["customer service", "support", "called ebay", "chat with ebay", "ebay rep", "no response", "wait time", "hours on hold", "useless support", "no help", "terrible support"],
            "icon": "📞",
            "description": "Customer service quality — long waits, unhelpful reps, no resolution",
        },
        "Vault Issues": {
            "keywords": ["vault", "can't withdraw", "stuck in vault", "vault withdraw", "vault shipping", "vault delay"],
            "icon": "🏦",
            "description": "eBay Vault withdrawal, shipping, and access problems",
        },
    }

    # Classify insights into broken-window categories
    bw_buckets = {cat: [] for cat in BW_CATEGORIES}
    bw_uncategorized = []

    # Only look at complaints, confusion, and negative sentiment
    bw_candidates = [
        i for i in normalized
        if i.get("type_tag") in ("Complaint", "Confusion", "Question")
        or i.get("brand_sentiment") == "Negative"
    ]

    for insight in bw_candidates:
        text_lower = (insight.get("text", "") + " " + insight.get("title", "")).lower()
        matched = False
        for cat, config in BW_CATEGORIES.items():
            if any(kw in text_lower for kw in config["keywords"]):
                bw_buckets[cat].append(insight)
                matched = True
                break
        if not matched:
            bw_uncategorized.append(insight)

    # Summary metrics
    total_bw = sum(len(v) for v in bw_buckets.values())
    bw1, bw2, bw3 = st.columns(3)
    bw1.metric("Broken Window Signals", total_bw, help="Complaints, bugs, confusion, and friction points")
    bw2.metric("Categories", sum(1 for v in bw_buckets.values() if v))
    bw3.metric("Uncategorized", len(bw_uncategorized), help="Negative signals that don't fit a specific category")

    # Render each category
    for cat, config in BW_CATEGORIES.items():
        items = bw_buckets[cat]
        if not items:
            continue

        neg_count = sum(1 for i in items if i.get("brand_sentiment") == "Negative")
        severity = "🔴 High" if neg_count > len(items) * 0.6 else ("🟡 Medium" if neg_count > len(items) * 0.3 else "🟢 Low")

        with st.expander(f"{config['icon']} **{cat}** — {len(items)} signals ({severity} severity)", expanded=False):
            st.caption(config["description"])

            # Quick stats
            complaints = sum(1 for i in items if i.get("type_tag") == "Complaint")
            questions = sum(1 for i in items if i.get("type_tag") in ("Question", "Confusion"))
            st.markdown(f"**{complaints}** complaints · **{questions}** confused users · **{neg_count}** negative sentiment")
            st.markdown("---")

            # Show top items sorted by score
            sorted_items = sorted(items, key=lambda x: x.get("score", 0), reverse=True)
            for idx, insight in enumerate(sorted_items[:10], 1):
                text = insight.get("text", "")[:400]
                title = insight.get("title", "")[:100]
                score = insight.get("score", 0)
                sentiment = insight.get("brand_sentiment", "Neutral")
                sent_icon = {"Negative": "🔴", "Positive": "🟢"}.get(sentiment, "⚪")
                subtag = insight.get("subtag", "")
                url = insight.get("url", "")
                date = insight.get("post_date", "")

                st.markdown(f"**{idx}. {sent_icon}** {title or text[:80]}")
                st.markdown(f"> {text}")
                meta = []
                if subtag and subtag.lower() not in ("general", "unknown"):
                    meta.append(f"**Topic:** {subtag}")
                if date:
                    meta.append(f"**Date:** {date}")
                if score:
                    meta.append(f"⬆️ {score}")
                if url:
                    meta.append(f"[🔗 Source]({url})")
                if meta:
                    st.caption(" · ".join(meta))
                st.markdown("---")

    # Uncategorized negative signals
    if bw_uncategorized:
        with st.expander(f"❓ Other Negative Signals ({len(bw_uncategorized)})", expanded=False):
            st.caption("Negative feedback that doesn't fit a specific broken-window category — worth scanning for emerging patterns.")
            for idx, insight in enumerate(sorted(bw_uncategorized, key=lambda x: x.get("score", 0), reverse=True)[:15], 1):
                text = insight.get("text", "")[:300]
                subtag = insight.get("subtag", "")
                st.markdown(f"**{idx}.** {text}")
                if subtag and subtag.lower() not in ("general", "unknown"):
                    st.caption(f"Topic: {subtag}")
                st.markdown("---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 6: STRATEGY — Clusters + AI doc generation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[5]:
    st.markdown("AI-clustered themes from user signals. Generate PRDs, BRDs, PRFAQ docs, and Jira tickets.")
    try:
        display_clustered_insight_cards(normalized)
    except Exception as e:
        st.error(f"Cluster view error: {e}")
