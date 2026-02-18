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

def generate_competitor_analysis(comp_name, complaints, praise, changes, comparisons, total_posts):
    """Generate an AI competitive intelligence summary for a competitor."""
    try:
        from components.ai_suggester import _chat, MODEL_MAIN
    except ImportError:
        return "LLM not available. Please configure OpenAI API key."

    # Build a digest of top posts across categories
    digest_parts = []
    if complaints:
        top_complaints = sorted(complaints, key=lambda x: x.get("score", 0), reverse=True)[:5]
        complaint_texts = "\n".join([f"- {p.get('title', '')[:80] or p.get('text', '')[:80]}" for p in top_complaints])
        digest_parts.append(f"COMPLAINTS ({len(complaints)} total):\n{complaint_texts}")
    if praise:
        top_praise = sorted(praise, key=lambda x: x.get("score", 0), reverse=True)[:5]
        praise_texts = "\n".join([f"- {p.get('title', '')[:80] or p.get('text', '')[:80]}" for p in top_praise])
        digest_parts.append(f"PRAISE ({len(praise)} total):\n{praise_texts}")
    if changes:
        change_texts = "\n".join([f"- {p.get('title', '')[:80] or p.get('text', '')[:80]}" for p in changes[:5]])
        digest_parts.append(f"PRODUCT/POLICY CHANGES ({len(changes)} total):\n{change_texts}")
    if comparisons:
        comp_texts = "\n".join([f"- {p.get('title', '')[:80] or p.get('text', '')[:80]}" for p in comparisons[:5]])
        digest_parts.append(f"COMPARISONS TO EBAY ({len(comparisons)} total):\n{comp_texts}")

    digest = "\n\n".join(digest_parts)

    prompt = f"""You are a Senior Competitive Intelligence Analyst at eBay Collectibles. Analyze these {total_posts} community signals about {comp_name}.

{digest}

Write a competitive intelligence brief in this exact format:

**🏢 {comp_name} — Competitive Summary**

**What they're doing:** (2-3 sentences on their strategy, recent moves, and market position. Reference any publicly known facts — funding, GMV, user base, fee structure, recent launches.)

**Where they're vulnerable:** (2-3 sentences on their biggest pain points based on the complaints. What are users most frustrated about? Be specific.)

**Where they're winning:** (1-2 sentences on what users praise them for. What does eBay need to match or beat?)

**eBay response playbook:**
1. (One specific conquest action — how to win their unhappy users)
2. (One defensive action — how to prevent eBay users from switching)
3. (One strategic move — longer-term competitive positioning)

**Threat level:** (🔴 High / 🟡 Medium / 🟢 Low) — with one sentence explaining why.

Be specific, data-driven, and actionable. Reference real product features and public market data where possible. No generic advice."""

    try:
        return _chat(
            MODEL_MAIN,
            "You are a sharp competitive intelligence analyst. Write crisp, specific, actionable briefs. Use real public data points when available.",
            prompt,
            max_completion_tokens=800,
            temperature=0.4
        )
    except Exception as e:
        return f"Analysis unavailable: {e}"


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
| **Competitor Intel** | What Fanatics, Whatnot, Heritage, Alt are doing. What their customers complain about (conquest opportunities). What people like about them (threats). |
| **eBay Voice** | What eBay's own customers are saying — product feedback, pain points, feature requests, filtered by topic. |
| **Industry & Trends** | News, blog posts, YouTube commentary, forum discussions — the broader collectibles market. |
| **Broken Windows** | Bugs, UX confusion, fee complaints, shipping friction, return disputes — things that erode trust and need fixing. |
| **Strategy** | AI-clustered themes with signal counts. Generate PRDs, BRDs, PRFAQ docs, and Jira tickets. |
        """)

    # ── Executive Briefing ──
    from collections import Counter

    neg = sum(1 for i in normalized if i.get("brand_sentiment") == "Negative")
    pos = sum(1 for i in normalized if i.get("brand_sentiment") == "Positive")
    complaints = [i for i in normalized if i.get("type_tag") == "Complaint"]
    feature_reqs = [i for i in normalized if i.get("type_tag") == "Feature Request"]

    # Headline metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Negative Signals", neg, help="Posts with negative sentiment about eBay")
    m2.metric("Complaints", len(complaints), help="Explicit complaints from users")
    m3.metric("Feature Requests", len(feature_reqs), help="Users asking for something new or better")
    m4.metric("Positive Signals", pos, help="Posts with positive sentiment")

    # ── Section 1: Top Issues to Fix ──
    st.markdown("### 🔴 Top Issues to Fix")
    st.caption("Highest-volume negative sentiment topics — expand each to see what's happening and what to do about it.")
    subtag_neg = Counter(i.get("subtag", "General") for i in normalized if i.get("brand_sentiment") == "Negative")
    subtag_neg.pop("General", None)

    # Classify what kind of action each topic area typically needs
    TOPIC_ACTION_MAP = {
        "Vault": {"action": "🐛 Bug Fix / UX Improvement", "owner": "Vault PM", "next": "Review top complaints → file bugs or UX tickets"},
        "Trust": {"action": "🛡️ Policy / Trust & Safety", "owner": "Trust PM", "next": "Assess if policy change or enforcement improvement needed"},
        "Payments": {"action": "🐛 Bug Fix / Policy Review", "owner": "Payments PM", "next": "Check if payment hold logic needs tuning or if it's a bug"},
        "Shipping": {"action": "🐛 Bug Fix / Partner Escalation", "owner": "Shipping PM", "next": "Review shipping label/tracking issues → escalate to carrier if needed"},
        "Grading Turnaround": {"action": "📊 Partner Monitoring", "owner": "Partnerships", "next": "Track PSA/BGS turnaround times → escalate if SLAs slipping"},
        "Grading": {"action": "📊 Partner Monitoring", "owner": "Partnerships", "next": "Track grading service issues → escalate to PSA/BGS if systemic"},
        "Authenticity Guarantee": {"action": "📝 PRD / Policy Update", "owner": "Authentication PM", "next": "Evaluate if AG coverage or process needs expansion"},
        "Returns & Refunds": {"action": "📝 Policy Review", "owner": "Returns PM", "next": "Analyze INAD patterns → consider policy tightening or seller tools"},
        "Fees": {"action": "📊 Pricing Analysis", "owner": "Monetization PM", "next": "Benchmark fees vs competitors → model impact of changes"},
        "High-Value": {"action": "📝 PRD / New Feature", "owner": "High-Value PM", "next": "Identify gaps in high-value seller/buyer experience → scope improvements"},
        "Seller Experience": {"action": "🐛 Fix / 📝 PRD", "owner": "Seller Experience PM", "next": "Triage: bugs → fix, gaps → PRD, confusion → UX improvement"},
        "Buyer Experience": {"action": "🐛 Fix / 📝 PRD", "owner": "Buyer Experience PM", "next": "Triage: bugs → fix, gaps → PRD, confusion → UX improvement"},
        "App & UX": {"action": "🐛 Bug Fix / UX Improvement", "owner": "Platform PM", "next": "File UX bugs or design improvements"},
        "Collecting": {"action": "🔍 Investigate", "owner": "Category PM", "next": "Understand collector pain points → identify product opportunities"},
        "Competitor Intel": {"action": "⚔️ Competitive Response", "owner": "Strategy", "next": "Assess competitive threat → build response plan"},
        "Listing Strategy": {"action": "📝 PRD / Education", "owner": "Seller Tools PM", "next": "Improve listing tools or create seller education content"},
        "Price Guide": {"action": "📝 PRD / Data Quality", "owner": "Price Guide PM", "next": "Review pricing data accuracy → scope improvements"},
        "Customer Service": {"action": "🔍 Ops Escalation", "owner": "CS Ops", "next": "Review CS quality metrics → escalate training gaps"},
        "Market & Investing": {"action": "📊 Market Intelligence", "owner": "Strategy", "next": "Monitor for market shifts that affect eBay collectibles GMV"},
        "Account Issues": {"action": "🐛 Bug Fix / Policy Review", "owner": "Trust PM", "next": "Review account restriction patterns → fix false positives"},
    }
    DEFAULT_ACTION = {"action": "🔍 Investigate", "owner": "PM Team", "next": "Review signals → determine if this is a bug, policy gap, or new opportunity"}

    def _generate_issue_brief(tag, posts, action_info):
        """Generate an AI-synthesized issue brief for a topic."""
        try:
            from components.ai_suggester import _chat, MODEL_MAIN
        except ImportError:
            return None

        # Build a digest of the top posts — include enough for AI to find patterns
        digest_lines = []
        for p in posts[:15]:
            text = p.get("text", "")[:200].replace("\n", " ")
            score = p.get("score", 0)
            type_tag = p.get("type_tag", "")
            source = p.get("source", "")
            digest_lines.append(f"[{type_tag}] [{source}] (⬆️{score}) {text}")

        digest = "\n".join(digest_lines)

        prompt = f"""You are a Senior Product Manager at eBay analyzing user feedback about "{tag}". Below are {len(posts)} negative signals from Reddit, Twitter, YouTube, and forums.

TOP SIGNALS:
{digest}

Write a concise issue brief in this EXACT format:

**What's happening:** (2-3 sentences. Be SPECIFIC about what users are experiencing. Name specific features, flows, or policies. Don't be vague.)

**Sub-issues identified:**
1. **[Specific sub-issue name]** — (1 sentence with concrete detail. e.g. "Vault inventory errors causing cancelled auctions after payment" not "users have issues with vault")
2. **[Specific sub-issue name]** — (1 sentence)
3. **[Specific sub-issue name]** — (1 sentence)

**Who's affected:** (Sellers? Buyers? High-value collectors? New users? Be specific.)

**Business impact:** (1-2 sentences. Revenue risk? Trust erosion? Churn to competitors? Quantify if possible from the signals.)

**Recommended next steps:**
1. (Specific action — not "investigate" but "audit vault inventory sync between PSA and eBay listing system")
2. (Specific action)

Be extremely specific and concrete. Reference actual product features, flows, and policies. No generic advice."""

        try:
            return _chat(
                MODEL_MAIN,
                "You are a sharp product analyst. Write specific, concrete briefs based on user signals. Never be vague.",
                prompt,
                max_completion_tokens=600,
                temperature=0.3
            )
        except Exception as e:
            return None

    if subtag_neg:
        top_issues = subtag_neg.most_common(5)
        for rank, (tag, cnt) in enumerate(top_issues, 1):
            pct = round(cnt / max(neg, 1) * 100)
            action_info = TOPIC_ACTION_MAP.get(tag, DEFAULT_ACTION)

            # Get the actual posts for this topic — filter out likely noise
            tag_posts = [i for i in normalized if i.get("subtag") == tag and i.get("brand_sentiment") == "Negative"]
            # Filter: must mention eBay or be from eBay-related subreddit to avoid video game posts etc.
            ebay_kw = ["ebay", "e-bay", "vault", "psa", "bgs", "grading", "listing", "seller", "buyer",
                       "auction", "shipping", "fee", "return", "refund", "payment", "authenticity"]
            ebay_subs = ["ebay", "flipping", "ebaySellers", "sportscards", "baseballcards",
                         "basketballcards", "pokemontcg", "coins", "PokeInvesting", "psagrading"]
            tag_posts_filtered = []
            for p in tag_posts:
                text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
                sub = p.get("subreddit", "")
                if any(kw in text_lower for kw in ebay_kw) or sub in ebay_subs:
                    tag_posts_filtered.append(p)
            tag_posts = sorted(tag_posts_filtered, key=lambda x: x.get("score", 0), reverse=True) if tag_posts_filtered else sorted(tag_posts, key=lambda x: x.get("score", 0), reverse=True)

            tag_complaints = sum(1 for p in tag_posts if p.get("type_tag") == "Complaint")
            tag_feature_reqs = sum(1 for p in tag_posts if p.get("type_tag") == "Feature Request")
            tag_bugs = sum(1 for p in tag_posts if p.get("type_tag") == "Bug Report")

            severity = "🔴 High" if cnt >= 20 else ("🟡 Medium" if cnt >= 8 else "🟢 Low")

            with st.expander(f"**{rank}. {tag}** — {cnt} signals ({pct}%) · {severity} · {action_info['action']}", expanded=False):
                st.markdown(f"**Owner:** {action_info['owner']} · **Severity:** {severity}")
                if tag_complaints or tag_feature_reqs or tag_bugs:
                    breakdown = []
                    if tag_complaints: breakdown.append(f"{tag_complaints} complaints")
                    if tag_feature_reqs: breakdown.append(f"{tag_feature_reqs} feature requests")
                    if tag_bugs: breakdown.append(f"{tag_bugs} bug reports")
                    st.caption(f"Signal mix: {' · '.join(breakdown)}")

                # AI synthesis — cached in session state
                brief_key = f"issue_brief_{tag}"
                if st.button(f"🧠 Generate AI Issue Brief", key=f"btn_{brief_key}"):
                    st.session_state[brief_key] = "__generating__"
                    st.rerun()
                if st.session_state.get(brief_key) == "__generating__":
                    with st.spinner(f"Analyzing {len(tag_posts)} signals for {tag}..."):
                        result = _generate_issue_brief(tag, tag_posts, action_info)
                    st.session_state[brief_key] = result or "AI analysis unavailable. See raw signals below."
                    st.rerun()
                if st.session_state.get(brief_key) and st.session_state[brief_key] != "__generating__":
                    with st.container(border=True):
                        st.markdown(st.session_state[brief_key])

                # Raw signals — collapsed, for reference
                with st.expander(f"📄 Raw signals ({len(tag_posts)})", expanded=False):
                    for idx, post in enumerate(tag_posts[:8], 1):
                        text = post.get("text", "")[:250]
                        score = post.get("score", 0)
                        type_tag = post.get("type_tag", "")
                        url = post.get("url", "")
                        source = post.get("source", "")
                        st.markdown(f"**{idx}.** {text}{'...' if len(post.get('text', '')) > 250 else ''}")
                        meta = f"⬆️ {score} · {type_tag} · {source}"
                        if url:
                            meta += f" · [Source]({url})"
                        st.caption(meta)
                    if len(tag_posts) > 8:
                        st.info(f"🎯 **{len(tag_posts) - 8} more** — see **eBay Voice** tab filtered by *{tag}*.")
    else:
        st.info("No negative signals found.")

    st.markdown("---")

    # ── Section 2: What Customers Want ──
    st.markdown("### 💡 What Customers Are Asking For")
    st.caption("Synthesized product opportunities from user feedback — grouped by theme.")

    # Synthesize feature requests into actionable themes instead of raw quotes
    # Require BOTH a product area keyword AND an intent keyword (actually requesting something)
    EBAY_PRODUCT_AREAS = [
        "listing", "search", "filter", "app", "website", "vault", "authenticity guarantee",
        "shipping label", "tracking", "fee structure", "payment", "payout", "return policy",
        "promoted listing", "price guide", "scan", "watchlist", "notification",
        "category", "photo", "description", "checkout", "dashboard", "analytics",
        "seller hub", "seller tool", "buyer experience", "authentication",
    ]
    EBAY_INTENT_KEYWORDS = [
        "should", "could", "would be nice", "wish", "need", "want", "please add",
        "why can't", "why doesn't", "feature", "improve", "better", "option to",
        "ability to", "allow", "enable", "support", "integrate", "add a",
        "missing", "lack", "no way to", "can't even", "should be able",
        "suggestion", "request", "idea", "proposal",
    ]
    # Posts that are just hobby questions, not platform feedback
    HOBBY_NOISE = [
        "best way to buy", "what's the best way", "where to buy",
        "how to start collecting", "for my binder", "my collection",
        "what should i collect", "is this card worth", "how much is",
        "just started collecting", "new to collecting",
        "when i started collecting", "i filled my case",
        "i enjoy selling it on", "i really enjoy selling",
        "heritage auctions this morning",
    ]

    def _is_actionable_feature_req(post):
        text = (post.get("text", "") + " " + post.get("title", "")).lower()
        # Exclude hobby noise
        if any(n in text for n in HOBBY_NOISE):
            return False
        # Must mention a product area OR "ebay" + intent
        has_product_area = any(kw in text for kw in EBAY_PRODUCT_AREAS)
        has_ebay = "ebay" in text
        has_intent = any(kw in text for kw in EBAY_INTENT_KEYWORDS)
        # Pass if: product area keyword, OR (ebay + intent keyword)
        return has_product_area or (has_ebay and has_intent)

    # Theme synthesis: group requests by subtag and generate actionable titles
    THEME_TITLES = {
        "Vault": "Better Vault Experience",
        "Trust": "Stronger Trust & Authenticity Signals",
        "Payments": "Smoother Payment & Payout Flow",
        "Shipping": "Shipping Tools & Cost Improvements",
        "Grading Turnaround": "Faster Grading Integration",
        "Grading": "Better Grading Service Integration",
        "Authenticity Guarantee": "Expanded Authentication Coverage",
        "Returns & Refunds": "Fairer Return & Dispute Process",
        "Fees": "More Transparent Fee Structure",
        "High-Value": "Better High-Value Item Experience",
        "Seller Experience": "Seller Tools & Workflow Improvements",
        "Buyer Experience": "Buyer Discovery & Purchase Flow",
        "App & UX": "App & UX Improvements",
        "Collecting": "Better Collector Discovery Tools",
        "Price Guide": "More Accurate Pricing Data",
        "Listing Strategy": "Smarter Listing & Pricing Tools",
        "Market & Investing": "Market Intelligence for Collectors",
        "Competitor Intel": "Competitive Feature Gaps to Close",
    }

    # Filter to actionable eBay product feature requests (not hobby questions)
    relevant_reqs = [r for r in feature_reqs if _is_actionable_feature_req(r)]

    if relevant_reqs:
        # Group by subtag
        req_by_theme = defaultdict(list)
        for r in relevant_reqs:
            subtag = r.get("subtag", "General")
            if subtag != "General":
                req_by_theme[subtag].append(r)

        # Sort themes by total engagement
        sorted_themes = sorted(req_by_theme.items(), key=lambda x: sum(r.get("score", 0) for r in x[1]), reverse=True)

        for rank, (subtag, reqs) in enumerate(sorted_themes[:5], 1):
            theme_title = THEME_TITLES.get(subtag, f"{subtag} Improvements")
            total_score = sum(r.get("score", 0) for r in reqs)
            top_req = sorted(reqs, key=lambda x: x.get("score", 0), reverse=True)[0]
            sample_text = top_req.get("text", "")[:200]

            with st.expander(f"**{rank}. {theme_title}** — {len(reqs)} requests · ⬆️ {total_score} total engagement", expanded=False):
                st.markdown(f"**Theme:** Users want improvements to **{subtag.lower()}** on eBay.")
                st.markdown("**Top requests:**")
                for idx, req in enumerate(sorted(reqs, key=lambda x: x.get("score", 0), reverse=True)[:4], 1):
                    text = req.get("text", "")[:250]
                    score = req.get("score", 0)
                    url = req.get("url", "")
                    st.markdown(f"**{idx}.** {text}{'...' if len(req.get('text', '')) > 250 else ''}")
                    meta = f"⬆️ {score}"
                    if url:
                        meta += f" · [Source]({url})"
                    st.caption(meta)
    else:
        st.info("No actionable feature requests found.")

    st.markdown("---")

    # ── Section 3: Competitor Watch ──
    st.markdown("### ⚔️ Competitor Watch")
    st.caption("Quick snapshot — click below to dive into full competitor analysis.")
    if competitor_posts_raw:
        comp_counts = Counter(p.get("competitor", "?") for p in competitor_posts_raw if p.get("competitor_type") != "ebay_subsidiary")
        if comp_counts:
            # For each top competitor, find the highest-engagement complaint
            for comp_name, cnt in comp_counts.most_common(4):
                comp_posts_list = [p for p in competitor_posts_raw if p.get("competitor") == comp_name]
                # Find a complaint or high-engagement post
                complaint_kw = ["problem", "issue", "hate", "terrible", "worst", "frustrated", "scam", "disappointed", "rip off", "overpriced"]
                comp_complaints = [p for p in comp_posts_list if any(kw in (p.get("text", "") + p.get("title", "")).lower() for kw in complaint_kw)]
                praise_kw = ["love", "amazing", "better than", "switched to", "prefer", "great"]
                comp_praise = [p for p in comp_posts_list if any(kw in (p.get("text", "") + p.get("title", "")).lower() for kw in praise_kw)]

                headline = f"**{comp_name}** — {cnt} posts"
                details = []
                if comp_complaints:
                    details.append(f"🎯 {len(comp_complaints)} complaints (conquest opps)")
                if comp_praise:
                    details.append(f"⚠️ {len(comp_praise)} praise (threats)")
                st.markdown(f"{headline} · {' · '.join(details)}" if details else headline)

            st.info("⚔️ **Want the full picture?** Switch to the **Competitor Intel** tab above for detailed complaints, praise, comparisons, and AI conquest briefs.")
    else:
        st.info("No competitor data. Run scrapers to collect.")

    st.markdown("---")

    # ── Section 4: Quick Pulse ──
    st.markdown("### 📊 Signal Breakdown")
    st.caption("Where signals are concentrated by topic — click a topic to see all signals.")
    subtag_counts = Counter(i.get("subtag", "General") for i in normalized)
    subtag_counts.pop("General", None)
    if subtag_counts:
        top_tags = subtag_counts.most_common(8)
        for tag, cnt in top_tags:
            neg_in_tag = sum(1 for i in normalized if i.get("subtag") == tag and i.get("brand_sentiment") == "Negative")
            neg_pct = round(neg_in_tag / max(cnt, 1) * 100)
            complaints_in_tag = sum(1 for i in normalized if i.get("subtag") == tag and i.get("type_tag") == "Complaint")
            # Health score: use BOTH percentage AND absolute volume
            # High absolute negative count = problem even if % is low
            is_red = neg_pct > 40 or neg_in_tag >= 15 or complaints_in_tag >= 20
            is_yellow = neg_pct > 15 or neg_in_tag >= 8 or complaints_in_tag >= 10
            bar = "🔴" if is_red else ("�" if is_yellow else "�🟢")
            st.markdown(f"{bar} **{tag}**: {cnt} signals · {neg_in_tag} negative ({neg_pct}%) · {complaints_in_tag} complaints")

    st.markdown("---")
    st.markdown("### 🚦 Where to Go Next")
    nc1, nc2, nc3 = st.columns(3)
    with nc1:
        st.markdown("""
**🔧 Broken Windows**
Bugs, UX confusion, fee friction — things to fix now.
""")
    with nc2:
        st.markdown("""
**🎯 eBay Voice**
Drill into customer feedback by topic, sentiment, and type.
""")
    with nc3:
        st.markdown("""
**📋 Strategy**
AI-clustered themes. Generate PRDs, BRDs, and Jira tickets.
""")


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

                # Classify posts: complaints, praise, policy/product changes, comparisons
                complaints_list = []
                praise_list = []
                changes_list = []
                comparison_list = []
                discussion_list = []
                for p in posts:
                    text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
                    # Policy/product changes
                    if any(w in text_lower for w in [
                        "announced", "just launched", "new feature", "policy change", "new policy",
                        "rolling out", "beta test", "now available", "just released", "price increase",
                        "fee change", "fee increase", "new partnership", "acquired", "shut down",
                        "exclusive", "partnership", "deal with",
                    ]):
                        changes_list.append(p)
                    # Complaints — broader keywords
                    elif any(w in text_lower for w in [
                        "problem", "issue", "broken", "terrible", "worst", "hate",
                        "frustrated", "scam", "complaint", "disappointed", "awful",
                        "can't believe", "ridiculous", "rip off", "waste", "shorted",
                        "missing", "wrong", "damaged", "overpriced", "robbery",
                        "bad experience", "never again", "don't buy", "warning",
                        "buyer beware", "stay away", "not worth", "regret",
                        "poor quality", "garbage", "trash", "junk",
                    ]):
                        complaints_list.append(p)
                    # Praise / competitive threats — broader
                    elif any(w in text_lower for w in [
                        "love", "amazing", "best platform", "better than ebay", "prefer",
                        "switched to", "moved to", "so much better", "way better",
                        "great experience", "highly recommend", "impressed",
                        "cheaper fees", "lower fees", "better fees",
                        "easier to use", "better ui", "better app",
                        "glad i switched", "never going back",
                    ]):
                        praise_list.append(p)
                    # Direct comparisons (vs eBay, vs other platforms)
                    elif any(w in text_lower for w in [
                        "vs ebay", "vs ", "compared to", "or ebay", "over ebay",
                        "instead of ebay", "better than", "worse than",
                        "pros and cons", "pros/cons", "which is better",
                    ]):
                        comparison_list.append(p)
                    else:
                        # Only keep discussion posts with some engagement
                        if (p.get("score", 0) or 0) >= 5:
                            discussion_list.append(p)

                actionable = len(changes_list) + len(complaints_list) + len(praise_list) + len(comparison_list)
                with st.container(border=True):
                    st.subheader(f"⚔️ {comp_name}")
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Actionable", actionable, help="Posts with clear signal: complaints, praise, changes, or comparisons")
                    mc2.metric("Complaints", len(complaints_list), help="Conquest opportunities — what their customers hate")
                    mc3.metric("Praise", len(praise_list), help="Competitive threats — what people like about them")
                    mc4.metric("Comparisons", len(comparison_list), help="Direct platform comparisons")

                    # AI Competitive Intelligence Summary
                    analysis_key = f"comp_analysis_{comp_name}"
                    if st.button(f"🧠 Generate AI Competitive Brief for {comp_name}", key=f"btn_{analysis_key}"):
                        st.session_state[analysis_key] = "__generating__"
                        st.rerun()
                    if st.session_state.get(analysis_key) == "__generating__":
                        with st.spinner(f"Analyzing {len(posts)} signals for {comp_name}..."):
                            result = generate_competitor_analysis(
                                comp_name, complaints_list, praise_list,
                                changes_list, comparison_list, len(posts)
                            )
                        st.session_state[analysis_key] = result
                        st.rerun()
                    if st.session_state.get(analysis_key) and st.session_state[analysis_key] != "__generating__":
                        with st.container(border=True):
                            st.markdown(st.session_state[analysis_key])

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

                    # Comparisons
                    if comparison_list:
                        with st.expander(f"⚖️ Platform Comparisons ({len(comparison_list)})", expanded=False):
                            for idx, post in enumerate(sorted(comparison_list, key=lambda x: x.get("score", 0), reverse=True)[:10], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                score = post.get("score", 0)
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

                    # General discussion — only high-engagement posts
                    if discussion_list:
                        with st.expander(f"💬 Other Discussion — {len(discussion_list)} high-engagement posts", expanded=False):
                            for idx, post in enumerate(sorted(discussion_list, key=lambda x: x.get("score", 0), reverse=True)[:8], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                score = post.get("score", 0)
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:300]}")
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

    # ── Upcoming Releases & Checklists ──
    releases_data = []
    try:
        with open("data/upcoming_releases.json", "r", encoding="utf-8") as f:
            releases_data = json.load(f)
    except:
        pass

    if releases_data:
        checklists = [r for r in releases_data if r.get("category") == "checklist"]
        releases = [r for r in releases_data if r.get("category") == "release"]

        st.markdown("### 📦 Upcoming Product Releases & Checklists")
        st.caption(f"{len(releases)} upcoming releases · {len(checklists)} checklists available — data team: click checklist links to pull card lists.")

        rel_tab1, rel_tab2 = st.tabs(["📋 Checklists", "🗓️ Upcoming Releases"])

        with rel_tab1:
            # Filter controls
            cl_sports = sorted(set(c.get("sport", "Trading Cards") for c in checklists))
            cl_brands = sorted(set(c.get("brand", "Other") for c in checklists))
            fc1, fc2 = st.columns(2)
            with fc1:
                cl_sport_filter = st.selectbox("Sport/Category", ["All"] + cl_sports, key="cl_sport")
            with fc2:
                cl_brand_filter = st.selectbox("Brand", ["All"] + cl_brands, key="cl_brand")

            filtered_cl = checklists
            if cl_sport_filter != "All":
                filtered_cl = [c for c in filtered_cl if c.get("sport") == cl_sport_filter]
            if cl_brand_filter != "All":
                filtered_cl = [c for c in filtered_cl if c.get("brand") == cl_brand_filter]

            # Display as a clean table
            if filtered_cl:
                for idx, cl in enumerate(filtered_cl[:30], 1):
                    title = cl.get("title", "")
                    url = cl.get("url", "")
                    date = cl.get("post_date", "")
                    sport = cl.get("sport", "")
                    brand = cl.get("brand", "")
                    link = f"[Open Checklist]({url})" if url else ""
                    st.markdown(f"**{idx}.** {title}")
                    st.caption(f"{brand} · {sport} · {date} · {link}")
                if len(filtered_cl) > 30:
                    st.caption(f"... and {len(filtered_cl) - 30} more checklists.")
            else:
                st.info("No checklists match your filters.")

        with rel_tab2:
            # Filter controls
            rel_sports = sorted(set(r.get("sport", "Trading Cards") for r in releases))
            rel_brands = sorted(set(r.get("brand", "Other") for r in releases))
            fr1, fr2 = st.columns(2)
            with fr1:
                rel_sport_filter = st.selectbox("Sport/Category", ["All"] + rel_sports, key="rel_sport")
            with fr2:
                rel_brand_filter = st.selectbox("Brand", ["All"] + rel_brands, key="rel_brand")

            filtered_rel = releases
            if rel_sport_filter != "All":
                filtered_rel = [r for r in filtered_rel if r.get("sport") == rel_sport_filter]
            if rel_brand_filter != "All":
                filtered_rel = [r for r in filtered_rel if r.get("brand") == rel_brand_filter]

            if filtered_rel:
                for idx, rel in enumerate(filtered_rel[:30], 1):
                    title = rel.get("title", "")
                    url = rel.get("url", "")
                    date = rel.get("post_date", "")
                    sport = rel.get("sport", "")
                    brand = rel.get("brand", "")
                    link = f"[Details]({url})" if url else ""
                    st.markdown(f"**{idx}.** {title}")
                    st.caption(f"{brand} · {sport} · {date} · {link}")
                if len(filtered_rel) > 30:
                    st.caption(f"... and {len(filtered_rel) - 30} more releases.")
            else:
                st.info("No releases match your filters.")

        st.markdown("---")

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
