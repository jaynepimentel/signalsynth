# app.py — SignalSynth: Streamlined Collectibles Insight Engine

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import json
import re
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
load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)

def _has_valid_openai_key():
    def _is_placeholder(v):
        if not v:
            return True
        s = str(v).strip()
        if not s:
            return True
        bad_markers = [
            "YOUR_OPENAI_API_KEY",
            "YOUR_OPE",
            "YOUR_OPEN",
            "REPLACE_ME",
        ]
        return any(m in s.upper() for m in bad_markers)

    env_key = os.getenv("OPENAI_API_KEY")
    if not _is_placeholder(env_key):
        return True

    try:
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            sec_key = st.secrets["OPENAI_API_KEY"]
            if not _is_placeholder(sec_key):
                return True
    except Exception:
        pass
    return False

OPENAI_KEY_PRESENT = _has_valid_openai_key()

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


def _nested_get(obj, path, default=None):
    """Safe dotted-path getter, e.g. _nested_get(i, 'taxonomy.topic')."""
    cur = obj
    for part in str(path).split("."):
        if not isinstance(cur, dict):
            return default
        if part not in cur:
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def _taxonomy_type(insight):
    return _nested_get(insight, "taxonomy.type", insight.get("type_tag", "Unclassified"))


def _taxonomy_topic(insight):
    return _nested_get(insight, "taxonomy.topic", insight.get("subtag", "General"))


def _taxonomy_theme(insight):
    return _nested_get(insight, "taxonomy.theme", insight.get("theme") or _taxonomy_topic(insight))


PG_STRICT_EXACT_KW = [
    "ebay price guide", "ebay's price guide", "price guide on ebay",
    "card ladder", "cardladder", "card-ladder", "scan to price",
]
PG_STRICT_EBAY_CONTEXT_KW = ["ebay"]
PG_STRICT_PRODUCT_KW = ["price guide", "scan to price"]
PG_STRICT_EXCLUDE_KW = [
    "riftbound", "secret lair", "beanie", "logoman", "pikachu illustrator",
    "rookie debut patch", "record sale", "most expensive", "banger grail",
    "best app for value", "what's it worth", "worth anything", "price discrepancy",
    "need help pricing", "pricing you say",
]


def _is_true_price_guide_signal(item):
    txt = (str(item.get("title", "")) + " " + str(item.get("text", ""))).lower()
    if any(ex in txt for ex in PG_STRICT_EXCLUDE_KW):
        return False
    if any(k in txt for k in PG_STRICT_EXACT_KW):
        return True
    if any(ctx in txt for ctx in PG_STRICT_EBAY_CONTEXT_KW) and any(pk in txt for pk in PG_STRICT_PRODUCT_KW):
        return True
    return False

def normalize_insight(i, suggestion_cache):
    i["ideas"] = suggestion_cache.get(i.get("text",""), [])
    i["persona"] = i.get("persona", "Unknown")
    i["journey_stage"] = i.get("journey_stage", "Unknown")

    # Canonical taxonomy object (single source of truth), while preserving
    # legacy flat fields for backward compatibility.
    taxonomy = i.get("taxonomy") if isinstance(i.get("taxonomy"), dict) else {}
    canonical_type = (
        taxonomy.get("type")
        or i.get("type_tag")
        or i.get("insight_type")
        or "Unclassified"
    )
    canonical_topic = taxonomy.get("topic") or i.get("subtag")
    if not canonical_topic:
        tf = i.get("topic_focus_list") or i.get("topic_focus") or []
        if isinstance(tf, list) and tf:
            canonical_topic = tf[0]
        elif isinstance(tf, str) and tf.strip():
            canonical_topic = tf.strip()
        else:
            canonical_topic = "General"
    canonical_theme = taxonomy.get("theme") or i.get("theme") or canonical_topic

    i["taxonomy"] = {
        "type": canonical_type,
        "topic": canonical_topic,
        "theme": canonical_theme,
    }

    # Legacy compatibility fields (read from canonical taxonomy)
    i["type_tag"] = i["taxonomy"]["type"]
    i["subtag"] = i["taxonomy"]["topic"]
    i["theme"] = i["taxonomy"]["theme"]
    i["type_subtag"] = i.get("type_subtag") or i["taxonomy"]["topic"]

    if not i.get("type_subtags"):
        i["type_subtags"] = [i["taxonomy"]["topic"]] if i["taxonomy"]["topic"] else []

    i["brand_sentiment"] = i.get("brand_sentiment", "Neutral")
    i["clarity"] = i.get("clarity", "Unknown")
    i["effort"] = i.get("effort", "Unknown")
    i["target_brand"] = i.get("target_brand", "Unknown")
    i["action_type"] = i.get("action_type", "Unclear")
    i["opportunity_tag"] = i.get("opportunity_tag", "General Insight")
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
    val = _nested_get(insight, field, None)
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
3. Key drivers or contributing factors
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

    # Cllct news data
    cllct_raw = []
    try:
        with open("data/scraped_cllct_posts.json", "r", encoding="utf-8") as f:
            cllct_raw = json.load(f)
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
    complaints = sum(1 for i in normalized if _taxonomy_type(i) == "Complaint" or i.get("brand_sentiment") == "Negative")
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
# Ask AI (always visible above tabs)
# ─────────────────────────────────────────────
st.markdown("### 🤖 Ask AI About the Data")
st.caption("Ask any question about scraped insights and get a polished, data-grounded answer.")

if not OPENAI_KEY_PRESENT:
    st.warning("OpenAI API key not configured. Add your key to `.env` to enable AI Q&A.")
else:
    if "qa_messages" not in st.session_state:
        st.session_state["qa_messages"] = []
    if "qa_draft" not in st.session_state:
        st.session_state["qa_draft"] = "is there any signal about PSA vault issues?"

    c1, c2 = st.columns([5, 1])
    with c1:
        user_question = st.text_input(
            "Ask a question",
            key="qa_draft",
            placeholder="e.g., What are the top complaints about Whatnot vs eBay?",
        )
    with c2:
        st.write("")
        ask_clicked = st.button("Ask AI", key="qa_ask_btn", type="primary")

    st.caption("Try this prompt: **is there any signal about PSA vault issues?**")

    if ask_clicked and user_question.strip():
        question = user_question.strip()
        st.session_state["qa_messages"].append({"role": "user", "content": question})

        q_words = set(question.lower().split())

        def _relevance_score(insight):
            text = (insight.get("text", "") + " " + insight.get("title", "")).lower()
            subtag = (_taxonomy_topic(insight) or "").lower()
            source = (insight.get("source", "") or "").lower()
            score = 0
            for w in q_words:
                if len(w) > 3 and w in text:
                    score += 1
                if w in subtag:
                    score += 3
                if w in source:
                    score += 2
            return score

        scored = [(p, _relevance_score(p)) for p in normalized]
        scored.sort(key=lambda x: -x[1])
        relevant = [p for p, s in scored if s > 0][:30]

        context_lines = []
        for p in relevant[:20]:
            title = p.get("title", "")[:120]
            text = p.get("text", "")[:350].replace("\n", " ")
            source = p.get("source", "")
            sub = p.get("subreddit", "")
            subtag = _taxonomy_topic(p)
            sentiment = p.get("brand_sentiment", "")
            score = p.get("score", 0)
            type_tag = _taxonomy_type(p)
            sub_label = f"r/{sub}" if sub else source
            context_lines.append(
                f"- [{type_tag}] [{sentiment}] [{subtag}] (score:{score}, {sub_label}) {title}: {text}"
            )

        total_neg = sum(1 for i in normalized if i.get("brand_sentiment") == "Negative")
        total_pos = sum(1 for i in normalized if i.get("brand_sentiment") == "Positive")
        total_complaints = sum(1 for i in normalized if _taxonomy_type(i) == "Complaint")
        total_features = sum(1 for i in normalized if _taxonomy_type(i) == "Feature Request")
        subtag_counts = defaultdict(int)
        for i in normalized:
            st_val = _taxonomy_topic(i)
            if st_val and st_val != "General":
                subtag_counts[st_val] += 1
        top_subtags = sorted(subtag_counts.items(), key=lambda x: -x[1])[:10]

        stats_block = (
            f"Dataset: {len(normalized)} insights total\n"
            f"Sentiment: {total_neg} negative, {total_pos} positive\n"
            f"Types: {total_complaints} complaints, {total_features} feature requests\n"
            f"Top topics: {', '.join(f'{k} ({v})' for k, v in top_subtags)}"
        )
        context_block = "\n".join(context_lines) if context_lines else "(No directly matching posts found.)"

        system_prompt = f"""You are SignalSynth AI, an executive-grade analyst for eBay Collectibles PMs and leadership.
Your response must be boardroom-ready: concise, specific, and grounded only in provided data.
If evidence is weak, explicitly say so.

Format your answer exactly with these headings:
1) **Executive answer** (3-5 sentences, direct answer first)
2) **What the signals show** (3-6 bullets with concrete evidence — cite verbatim user quotes in "italics" to ground each claim)
3) **Implications for eBay** (2-4 bullets)
4) **Recommended actions (next 30 days)** (3-5 numbered actions with owner + expected impact)
5) **Confidence & gaps** (1-3 bullets)

Rules:
- Never invent facts not present in the provided signals.
- Always cite 2-3 verbatim user quotes from the signals to back up your key points.
- Prefer specific product/policy terms over generic language.
- Mention uncertainty clearly if evidence is limited.
- Keep total response under ~400 words unless explicitly asked for more.

DATASET SUMMARY:
{stats_block}

RELEVANT SIGNALS:
{context_block}"""

        try:
            from components.ai_suggester import _chat, MODEL_MAIN
            with st.spinner("Searching insights and generating answer..."):
                response = _chat(
                    MODEL_MAIN,
                    system_prompt,
                    question,
                    max_completion_tokens=1500,
                    temperature=0.3,
                )
            st.session_state["qa_messages"].append({"role": "assistant", "content": response})
        except Exception as e:
            st.session_state["qa_messages"].append({"role": "assistant", "content": f"⚠️ Error: {e}"})

    if st.session_state["qa_messages"]:
        with st.expander("AI Q&A responses", expanded=True):
            for msg in st.session_state["qa_messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            if st.button("🗑️ Clear chat", key="clear_qa"):
                st.session_state["qa_messages"] = []
                st.rerun()
# ─────────────────────────────────────────────
# 6 Tabs
# ─────────────────────────────────────────────
tabs = st.tabs([
    "📋 Strategy",
    "⚔️ Competitor Intel",
    "🎯 Customer Signals",
    "📰 Industry & Trends",
    "📦 Checklists & Sealed Launches",
    "📊 Charts",
])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 6: CHARTS — Executive snapshot
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[5]:
    # ── Executive Briefing ──
    from collections import Counter

    neg = sum(1 for i in normalized if i.get("brand_sentiment") == "Negative")
    pos = sum(1 for i in normalized if i.get("brand_sentiment") == "Positive")
    complaints = [i for i in normalized if _taxonomy_type(i) == "Complaint"]
    feature_reqs = [i for i in normalized if _taxonomy_type(i) == "Feature Request"]

    # Headline metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Negative Signals", neg, help="Posts with negative sentiment about eBay")
    m2.metric("Complaints", len(complaints), help="Explicit complaints from users")
    m3.metric("Feature Requests", len(feature_reqs), help="Users asking for something new or better")
    m4.metric("Positive Signals", pos, help="Posts with positive sentiment")

    # ── Section 1: Top Issues to Fix ──
    st.markdown("### 🔴 Top Issues to Fix")
    st.caption("Platform & product issues that eBay, Goldin, or TCGPlayer teams can act on — ranked by volume.")

    # Only count posts that describe something a product/engineering team can fix
    # Must mention a platform feature, tool, policy, or flow — not just be from a relevant subreddit
    PLATFORM_ACTION_KW = [
        # eBay platform
        "ebay", "e-bay", "listing", "seller hub", "promoted listing",
        "managed payments", "checkout", "search result", "best match",
        "authenticity guarantee", "standard envelope", "global shipping",
        # Vault / storage
        "vault", "psa vault", "vault sell", "vault inventory",
        # Payments & fees
        "fee", "final value", "payout", "payment hold", "held funds",
        "managed payment", "paypal",
        # Shipping & returns
        "shipping label", "tracking", "return request", "inad",
        "item not as described", "money back guarantee", "refund",
        "return abuse", "partial refund",
        # Account & policy
        "account suspended", "account restricted", "verification",
        "policy violation", "vero", "removed listing",
        # Grading & authentication
        "grading", "psa", "bgs", "cgc", "sgc", "authentication",
        "turnaround time", "grading fee",
        # Subsidiaries
        "goldin", "tcgplayer", "tcg player", "comc",
        # Product/UX
        "app", "website", "mobile app", "notification", "watchlist",
        "price guide", "scan", "barcode",
        # Bugs & UX
        "bug", "glitch", "error", "broken", "not working", "crash",
        "confusing", "can't find", "won't load",
    ]
    # Exclude personal stories and off-topic posts
    NOT_ACTIONABLE = [
        "stole my", "nephew", "my cards were stolen", "someone stole",
        "lost my collection", "house fire", "flooded",
        "fake money", "porch pick up", "counterfeit bill",
        "hands free controller", "nintendo", "ruined someone's kid",
        "dvd of an old film", "swirly shiny",
        # Non-eBay marketplace stories
        "sold a sealed japanese region 3ds", "mercari",
        "card show drama", "dallas card show",
        "am i dumb? 10k in cards", "10k in cards i got into slabs",
        # Generic collecting frustrations (not platform bugs)
        "i got into slabs during the peak",
        # Stock/investment conspiracy posts that mention eBay in passing
        "gameshire", "$100b endgame", "the whale, the trio",
        "bitcoin treasury", "warrants (gme", "roll-up",
        "diamond hands", "short squeeze", "moass", "tendies",
        "to the moon", "hedge fund", "warrants to blockchain",
        # Generic trade/sales threads (not platform issues)
        "official sales/trade/breaks", "leave a comment here in this thread with your sales",
        # False PSA/Vault matches from gaming/public-service posts
        "psa if you think you might want to play survival",
        "make a placeholder vault", "placeholder vault",
        "rewards in experimental", "play survival in the future",
        "survival vault", "public service announcement",
    ]
    # Subreddits that are never about eBay product issues
    NOT_ACTIONABLE_SUBS = [
        "superstonk", "gme_meltdown", "amcstock",
        "bitcoin", "stocks", "investing",
        "gamestop", "gmejungle", "fwfbthinktank", "gme",
    ]

    def _is_platform_issue(post):
        """Return True if this post describes something a product/eng team can fix."""
        text_lower = (post.get("text", "") + " " + post.get("title", "")).lower()
        # Exclude known off-topic subreddits
        if post.get("subreddit", "").lower() in NOT_ACTIONABLE_SUBS:
            return False
        # Exclude personal stories and off-topic content
        if any(na in text_lower for na in NOT_ACTIONABLE):
            return False
        # Must mention a platform feature/tool/policy
        return any(kw in text_lower for kw in PLATFORM_ACTION_KW)

    # Filter to only actionable issues, THEN count
    actionable_neg = [i for i in normalized if i.get("brand_sentiment") == "Negative" and _is_platform_issue(i)]
    subtag_neg = Counter(_taxonomy_topic(i) for i in actionable_neg)
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

Write an executive-ready issue brief in this EXACT format:

**What's happening:** (2-3 sentences. Be SPECIFIC about what users are experiencing. Name specific features, flows, or policies. Don't be vague.)

**Sub-issues identified:**
1. **[Specific sub-issue name]** — (1 sentence with concrete detail. e.g. "Vault inventory errors causing cancelled auctions after payment" not "users have issues with vault")
2. **[Specific sub-issue name]** — (1 sentence)
3. **[Specific sub-issue name]** — (1 sentence)

**Who's affected:** (Sellers? Buyers? High-value collectors? New users? Be specific.)

**Business impact:** (1-2 sentences. Revenue risk? Trust erosion? Churn to competitors? Quantify using the signal volume and engagement when possible.)

**Recommended next steps (30 days):**
1. **[Owner]** Specific action — not "investigate" but "audit vault inventory sync between PSA and eBay listing system"
2. **[Owner]** Specific action
3. **[Owner]** Specific action

**Confidence & data gaps:** (1-2 bullets. What are we confident about? What should be validated before committing roadmap?)

Cite 2-3 verbatim user quotes from the signals to ground your claims. Be extremely specific and concrete. Reference actual product features, flows, and policies. No generic advice. Avoid jargon and fluff."""

        try:
            return _chat(
                MODEL_MAIN,
                "You are an executive communications-grade product strategist. Write crisp, concrete briefs with quantified impact and clear ownership. Always cite specific user quotes.",
                prompt,
                max_completion_tokens=700,
                temperature=0.3
            )
        except Exception as e:
            return None

    if subtag_neg:
        top_issues = subtag_neg.most_common(5)
        for rank, (tag, cnt) in enumerate(top_issues, 1):
            pct = round(cnt / max(neg, 1) * 100)
            action_info = TOPIC_ACTION_MAP.get(tag, DEFAULT_ACTION)

            # Get only actionable posts for this topic (already filtered by _is_platform_issue)
            tag_posts = sorted(
                [i for i in actionable_neg if _taxonomy_topic(i) == tag],
                key=lambda x: x.get("score", 0), reverse=True
            )

            tag_complaints = sum(1 for p in tag_posts if _taxonomy_type(p) == "Complaint")
            tag_feature_reqs = sum(1 for p in tag_posts if _taxonomy_type(p) == "Feature Request")
            tag_bugs = sum(1 for p in tag_posts if _taxonomy_type(p) == "Bug Report")

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

                # Raw signals — toggle instead of nested expander
                if st.checkbox(f"📄 Show raw signals ({len(tag_posts)})", key=f"raw_{tag}", value=False):
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
                        st.info(f"🎯 **{len(tag_posts) - 8} more** — see **Customer Signals** tab filtered by *{tag}*.")
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
    subtag_counts = Counter(_taxonomy_topic(i) for i in normalized)
    subtag_counts.pop("General", None)
    if subtag_counts:
        top_tags = subtag_counts.most_common(8)
        for tag, cnt in top_tags:
            # Count unique posts that need attention (negative sentiment, complaint, or bug)
            tag_posts = [i for i in normalized if _taxonomy_topic(i) == tag]
            needs_attention = len([
                p for p in tag_posts
                if p.get("brand_sentiment") == "Negative"
                or _taxonomy_type(p) in ("Complaint", "Bug Report")
            ])
            ok_count = cnt - needs_attention
            attn_pct = round(needs_attention / max(cnt, 1) * 100)
            # Health: red if majority are problems, yellow if significant minority
            is_red = attn_pct > 40 or needs_attention >= 20
            is_yellow = attn_pct > 15 or needs_attention >= 10
            bar = "🔴" if is_red else ("🟡" if is_yellow else "🟢")
            st.markdown(f"{bar} **{tag}** — {needs_attention} of {cnt} signals need attention ({attn_pct}%)")

    st.markdown("---")
    st.markdown("### 🚦 Where to Go Next")
    nc1, nc2, nc3 = st.columns(3)
    with nc1:
        st.markdown("""
**🎯 Customer Signals**
Customer feedback + broken windows triage in one place.
""")
    with nc2:
        st.markdown("""
**📰 Industry & Trends**
Market context from news, YouTube, forums, and social.
""")
    with nc3:
        st.markdown("""
**📋 Strategy**
Strategic Themes from user signals: Theme → Opportunity Area → Supporting Signals → Top Topics.
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
        # Put Whatnot first, then sort the rest alphabetically
        _other_comps = sorted(k for k in comp_posts.keys() if k != "Whatnot")
        all_comps = (["Whatnot"] if "Whatnot" in comp_posts else []) + _other_comps
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
# TAB 3: CUSTOMER SIGNALS — eBay voice + broken windows
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[2]:
    st.markdown("Customer feedback and broken-windows triage in one place — fewer tabs, clearer action path.")

    # Filters
    filter_fields = {"Topic": "taxonomy.topic", "Type": "taxonomy.type", "Sentiment": "brand_sentiment"}
    filters = render_floating_filters(normalized, filter_fields, key_prefix="ebay_voice")
    filtered = [i for i in normalized if match_multiselect_filters(i, filters, filter_fields)]
    time_range = filters.get("_time_range", "All Time")
    filtered = filter_by_time(filtered, time_range)

    # When Topic filter includes Price Guide, enforce strict product relevance so
    # generic card-pricing chatter does not leak into Customer Signals Raw Feed.
    selected_topics = filters.get("taxonomy.topic", [])
    if selected_topics and "All" not in selected_topics and "Price Guide" in selected_topics:
        filtered = [i for i in filtered if _is_true_price_guide_signal(i)]

    cs_pulse_tab, cs_problems_tab, cs_requests_tab, cs_raw_tab = st.tabs([
        "📈 Pulse", "🔧 Problems", "💡 Requests", "📄 Raw Feed"
    ])

    with cs_pulse_tab:
        st.caption("Quick pulse on customer sentiment, issue load, and partner-related chatter for the current filter view.")

        # Quick stats for filtered view
        f_neg = sum(1 for i in filtered if i.get("brand_sentiment") == "Negative")
        f_pos = sum(1 for i in filtered if i.get("brand_sentiment") == "Positive")
        f_complaints = sum(1 for i in filtered if _taxonomy_type(i) == "Complaint")
        f_requests = sum(1 for i in filtered if _taxonomy_type(i) == "Feature Request")

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

        # Quick top-topic pulse
        topic_counts = defaultdict(int)
        for i in filtered:
            t = _taxonomy_topic(i)
            if t and t not in ("General", "Unknown"):
                topic_counts[t] += 1
        if topic_counts:
            st.markdown("**Top topics in current view:**")
            top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]
            st.caption(" · ".join([f"{k} ({v})" for k, v in top_topics]))

    with cs_requests_tab:
        st.caption("Feature asks and improvement opportunities from the currently filtered Customer Signals view.")

        REQUEST_HINTS = [
            "should", "wish", "need", "please add", "feature", "why can't", "allow", "option to", "improve",
        ]

        request_posts = [
            i for i in filtered
            if _taxonomy_type(i) == "Feature Request"
            or any(h in (i.get("text", "") + " " + i.get("title", "")).lower() for h in REQUEST_HINTS)
        ]

        st.metric("Request Signals", len(request_posts))
        if not request_posts:
            st.info("No request-like signals in this filtered view.")
        else:
            req_topic_counts = defaultdict(int)
            for i in request_posts:
                req_topic_counts[_taxonomy_topic(i)] += 1
            st.caption("Top request topics: " + " · ".join([f"{k} ({v})" for k, v in sorted(req_topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]]))

            for idx, post in enumerate(sorted(request_posts, key=lambda x: (x.get("score", 0), x.get("post_date", "")), reverse=True)[:20], 1):
                title = post.get("title", "")[:120] or post.get("text", "")[:120]
                ttype = _taxonomy_type(post)
                topic = _taxonomy_topic(post)
                score = post.get("score", 0)
                date = post.get("post_date", "")
                src = post.get("source", "")
                url = post.get("url", "")
                link = f" · [Source]({url})" if url else ""
                st.markdown(f"**{idx}.** {title}")
                st.caption(f"{ttype} · {topic} · ⬆️ {score} · {src} · {date}{link}")

    with cs_raw_tab:
        st.caption("Full customer signal explorer for the current filters.")
        model = get_model()
        render_insight_cards(filtered, model, key_prefix="ebay_voice")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4: INDUSTRY & TRENDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[3]:
    st.markdown("Top news, viral posts, YouTube commentary, podcasts, forum discussions, and product launches across the collectibles industry.")

    # ── Combine all industry sources ──
    industry_posts = []

    # News RSS
    for p in news_rss_raw:
        p["_industry_source"] = "News"
        industry_posts.append(p)

    # Cllct direct scrape (important collectibles industry source)
    for p in cllct_raw:
        p["_industry_source"] = "Cllct"
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

    # Viral / high-engagement Reddit posts — ONLY industry-relevant ones
    VIRAL_THRESHOLD = 100
    industry_urls = {p.get("url", "") for p in industry_posts if p.get("url")}

    # Industry-relevant keywords: platform business, market trends, policy, fees, competitor moves
    INDUSTRY_RELEVANT_KW = [
        # Platform & business
        "ebay fee", "ebay policy", "ebay change", "ebay update", "ebay announce",
        "whatnot fee", "whatnot policy", "fanatics", "heritage auction",
        "goldin", "tcgplayer", "tcg player", "alt marketplace",
        "platform", "marketplace", "seller fee", "buyer fee", "final value",
        "promoted listing", "managed payments", "payout",
        # Price guide / valuation (eBay cards)
        "price guide", "card ladder", "cardladder", "market comps", "comps",
        "ebay price guide", "scan card", "scanner", "raw or graded",
        # Market & industry trends
        "market crash", "market trend", "hobby crash", "hobby boom",
        "price drop", "price spike", "bubble", "overvalued", "undervalued",
        "license", "licensing deal", "exclusive deal", "monopoly",
        "panini", "topps", "upper deck", "bowman",
        # Grading & authentication industry
        "psa turnaround", "psa backlog", "bgs turnaround", "cgc turnaround",
        "grading fee", "grading change", "grading service",
        "psa vault", "vault update", "vault issue",
        # Trust & fraud (industry-level)
        "counterfeit", "fake card", "scam ring", "fraud ring",
        "authentication", "authenticity guarantee",
        # Business discussions
        "investing in cards", "card market", "hobby is dying", "hobby is dead",
        "future of collecting", "state of the hobby", "industry news",
        "new product", "product release", "checklist release",
        "quality control", "qc issue", "print run",
    ]
    # Exclude personal stories, memes, video games, off-topic
    INDUSTRY_EXCLUDE_KW = [
        "my nephew", "my daughter", "my son", "my kid", "my wife", "my husband",
        "look what i found", "look what i pulled", "just pulled",
        "mail day", "pickup", "lcs find", "card show find",
        "instant retirement", "can't believe", "holy grail",
        "rate my collection", "collection update", "added to the pc",
        "nfs/nft", "show off", "shove it up",
        "nintendo", "playstation", "xbox", "ps vita", "dev kit",
        "seed vault extract", "arc raiders", "stella montis",
        "hands free controller", "gold bar", "fake gold",
        "iron maiden", "secret lair",
        "superstonk", "gme", "gamestop", "diamond hands", "moass",
        "push start", "early access",
        "riftbound", "lgs need to be reeled in", "as a game",
    ]
    INDUSTRY_EXCLUDE_SUBS = [
        "gamecollecting", "superstonk", "gme", "gamestop", "amcstock",
        "gold", "silver", "coins", "arcraiders", "nostupidquestions",
        "ismypokemoncardfake", "riftboundtcg",
    ]

    viral_reddit = []
    for p in normalized:
        if p.get("source") not in ("Reddit", "Reddit (comment)"):
            continue
        if p.get("score", 0) < VIRAL_THRESHOLD:
            continue
        if p.get("url", "") in industry_urls:
            continue
        text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
        sub_lower = p.get("subreddit", "").lower()
        # Exclude off-topic subs and content
        if sub_lower in INDUSTRY_EXCLUDE_SUBS:
            continue
        if any(ex in text_lower for ex in INDUSTRY_EXCLUDE_KW):
            continue
        # Must contain at least one industry-relevant keyword
        if not any(kw in text_lower for kw in INDUSTRY_RELEVANT_KW):
            continue
        p_copy = dict(p)
        p_copy["_industry_source"] = "Reddit"
        viral_reddit.append(p_copy)
    # Deduplicate by URL
    seen_urls = set()
    for p in viral_reddit:
        u = p.get("url", "")
        if u and u not in seen_urls:
            seen_urls.add(u)
            industry_posts.append(p)

    # Twitter / Bluesky posts with engagement — also require industry relevance
    for p in normalized:
        src = p.get("source", "")
        if src not in ("Twitter", "Bluesky"):
            continue
        if p.get("score", 0) < 20:
            continue
        if p.get("url", "") in industry_urls:
            continue
        text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
        if any(ex in text_lower for ex in INDUSTRY_EXCLUDE_KW):
            continue
        if not any(kw in text_lower for kw in INDUSTRY_RELEVANT_KW):
            continue
        p_copy = dict(p)
        p_copy["_industry_source"] = src
        industry_posts.append(p_copy)

    def _is_industry_feed_spam(post):
        src = post.get("_industry_source", post.get("source", ""))
        title = (post.get("title", "") or "").strip()
        text = (post.get("text", "") or "").strip()
        combined = f"{title} {text}".lower()

        # YouTube livestream break spam (repetitive numbered titles)
        if src == "YouTube":
            if re.match(r"^!\d+\b", title.lower()):
                return True
            if "break w/" in combined and any(k in combined for k in ["1x ", "2x ", "tennis break", "ufc with"]):
                return True

        # Checklist-heavy news belongs in Checklists tab, not Full Industry Feed
        if src in ("News", "Cllct"):
            if "checklist" in combined and any(k in combined for k in ["team set list", "set lists", "checklist and details", "set list"]):
                return True

        return False

    industry_posts = [p for p in industry_posts if not _is_industry_feed_spam(p)]

    def _normalized_industry_title(post):
        raw = (post.get("title", "") or post.get("text", "")[:80]).strip().lower()
        # Normalize common stream counters so duplicates collapse
        raw = re.sub(r"^!\d+\s*", "", raw)
        raw = re.sub(r"^#\d+\s*", "", raw)
        raw = re.sub(r"^\d+x\s+", "", raw)
        raw = re.sub(r"\s+", " ", raw)
        return raw

    # Deduplicate by title+source — keep most recent when same title repeats (e.g. recurring livestreams)
    industry_posts.sort(key=lambda x: (x.get("post_date", ""), x.get("score", 0)), reverse=True)
    _seen_titles = set()
    _deduped = []
    for p in industry_posts:
        title = _normalized_industry_title(p)
        src = p.get("_industry_source", "")
        key = f"{src}::{title}"
        if key not in _seen_titles:
            _seen_titles.add(key)
            _deduped.append(p)
    industry_posts = _deduped

    if not industry_posts:
        st.info("No industry data. Run scrapers to collect news, YouTube, and forum data.")
    else:
        # ── Top metrics ──
        from collections import Counter
        source_counts = Counter(p.get("_industry_source", "?") for p in industry_posts)

        ic1, ic2, ic3, ic4 = st.columns(4)
        ic1.metric("Total Posts", len(industry_posts))
        ic2.metric("Sources", len(source_counts))
        viral_count = sum(1 for p in industry_posts if p.get("score", 0) >= VIRAL_THRESHOLD)
        ic3.metric("Viral (100+ pts)", viral_count)
        ic4.metric("Most Recent", industry_posts[0].get("post_date", "?") if industry_posts else "N/A")

        # ── 🔥 Top Industry News & Discussions ──
        st.markdown("### 🔥 Top Industry News & Discussions")
        st.caption("Recent-first ranking with engagement weighting — prioritizes fresh industry signals over stale high-score posts.")

        def _days_old(post):
            raw_date = str(post.get("post_date", "") or "")[:10]
            if not raw_date:
                return 9999
            try:
                d = datetime.fromisoformat(raw_date).date()
                return max(0, (datetime.now().date() - d).days)
            except Exception:
                return 9999

        def _time_weighted_score(post):
            # Decay older posts so recency matters: score / (1 + age_in_months)
            base_score = float(post.get("score", 0) or 0)
            src = str(post.get("_industry_source", post.get("source", "")) or "")
            title_text = (str(post.get("title", "")) + " " + str(post.get("text", ""))).lower()

            # Many news/forum items have no social score; give source-aware baseline so
            # major stories can still rank in Top Industry News.
            if base_score <= 0:
                if src.startswith("News") or src == "Cllct":
                    base_score = 120
                elif src in ("YouTube", "YouTube (transcript)"):
                    base_score = 90
                elif src in ("Blowout Forums", "Net54 Baseball", "Alt.xyz Blog"):
                    base_score = 70
                else:
                    base_score = 30

            # Strategic boosts for major market-moving stories
            boost = 0
            if any(k in title_text for k in ["record sale", "record-breaking", "record ", "$16.5 million", "million", "auction"]):
                boost += 35
            if any(k in title_text for k in ["logan paul", "pikachu illustrator", "goldin"]):
                boost += 30
            if any(k in title_text for k in ["policy change", "fee change", "partnership", "acquired", "licensing"]):
                boost += 20
            if any(k in title_text for k in ["price guide", "card ladder", "market comps", "scan", "scanner"]):
                boost += 25

            base_score += boost
            age_days = _days_old(post)
            return base_score / (1 + (age_days / 30.0))

        # Prefer recent windows; fall back if data is sparse
        recent_120 = [p for p in industry_posts if _days_old(p) <= 120]
        recent_365 = [p for p in industry_posts if _days_old(p) <= 365]
        top_pool = recent_120 if len(recent_120) >= 8 else (recent_365 if recent_365 else industry_posts)

        top_viral = sorted(
            top_pool,
            key=lambda x: (_time_weighted_score(x), float(x.get("score", 0) or 0)),
            reverse=True,
        )[:10]
        for rank, post in enumerate(top_viral, 1):
            source_label = post.get("_industry_source", post.get("source", "?"))
            title = post.get("title", "")[:120] or post.get("text", "")[:120]
            score = post.get("score", 0)
            date = post.get("post_date", "")
            url = post.get("url", "")
            sub = post.get("subreddit", "")
            source_icons = {
                "News": "📰", "YouTube": "🎬", "Reddit": "💬",
                "Twitter": "🐦", "Bluesky": "🦋",
                "Blowout Forums": "🗣️", "Net54 Baseball": "⚾",
                "Alt.xyz Blog": "📝", "COMC": "🃏", "Cllct": "🗞️",
            }
            icon = source_icons.get(source_label, "📄")
            sub_label = f"r/{sub} · " if sub else ""
            link = f" · [Link]({url})" if url else ""
            age_days = _days_old(post)
            age_label = f" · {age_days}d ago" if age_days < 9999 else ""
            st.markdown(f"**{rank}.** {icon} **{title}**")
            st.caption(f"⬆️ {score} pts · {sub_label}{source_label} · {date}{age_label}{link}")

        # ── eBay Price Guide Spotlight ──
        st.markdown("### 🧭 eBay Price Guide Signals")
        st.caption("What users like, where they are confused, and what they dislike about eBay's Price Guide (including Card Ladder coverage).")

        def _is_price_guide_signal(item):
            return _is_true_price_guide_signal(item)

        pg_signals = [p for p in normalized if _is_price_guide_signal(p)]
        pg_signals_sorted = sorted(pg_signals, key=lambda x: (x.get("post_date", ""), float(x.get("score", 0) or 0)), reverse=True)

        if not pg_signals_sorted:
            st.info("No eBay Price Guide signals found in current insights cache.")
        else:
            pg_neg = sum(1 for p in pg_signals_sorted if p.get("brand_sentiment") == "Negative")
            pg_pos = sum(1 for p in pg_signals_sorted if p.get("brand_sentiment") == "Positive")
            pg_neu = max(0, len(pg_signals_sorted) - pg_neg - pg_pos)

            confusion_kw = ["confus", "can't find", "how do i", "where is", "not showing", "missing", "doesn't work", "doesnt work"]
            dislike_kw = ["wrong", "inaccurate", "bad", "hate", "useless", "terrible", "off", "not accurate", "broken"]
            like_kw = ["helpful", "useful", "love", "great", "good", "accurate", "better", "nice"]

            pg_confused = sum(1 for p in pg_signals_sorted if any(k in (p.get("text", "") + " " + p.get("title", "")).lower() for k in confusion_kw))
            pg_dislike = sum(1 for p in pg_signals_sorted if any(k in (p.get("text", "") + " " + p.get("title", "")).lower() for k in dislike_kw))
            pg_like = sum(1 for p in pg_signals_sorted if any(k in (p.get("text", "") + " " + p.get("title", "")).lower() for k in like_kw))

            pg1, pg2, pg3, pg4 = st.columns(4)
            pg1.metric("Price Guide Signals", len(pg_signals_sorted))
            pg2.metric("👍 Positive", pg_pos)
            pg3.metric("❓ Confusion Cues", pg_confused)
            pg4.metric("👎 Negative", pg_neg)
            st.caption(f"Sentiment mix: 🔴 {pg_neg} negative · 🟢 {pg_pos} positive · ⚪ {pg_neu} neutral · 👍 keyword likes: {pg_like} · 👎 keyword dislikes: {pg_dislike}")

            for idx, post in enumerate(pg_signals_sorted[:8], 1):
                title = post.get("title", "")[:120] or post.get("text", "")[:120]
                sentiment = post.get("brand_sentiment", "Neutral")
                score = post.get("score", 0)
                src = post.get("source", "?")
                date = post.get("post_date", "")
                url = post.get("url", "")
                link = f" · [Link]({url})" if url else ""
                st.markdown(f"**{idx}.** {title}")
                st.caption(f"{sentiment} · ⬆️ {score} · {src} · {date}{link}")

        # Explicit industry coverage list (news/videos)
        pg_coverage = [p for p in industry_posts if _is_price_guide_signal(p)]
        pg_coverage = sorted(pg_coverage, key=lambda x: (_time_weighted_score(x), x.get("post_date", "")), reverse=True)
        if pg_coverage:
            st.caption("Industry coverage (news/videos) for Price Guide & Card Ladder:")
            for i, p in enumerate(pg_coverage[:6], 1):
                t = p.get("title", "")[:120] or p.get("text", "")[:120]
                src = p.get("_industry_source", p.get("source", "?"))
                d = p.get("post_date", "")
                u = p.get("url", "")
                l = f" · [Link]({u})" if u else ""
                st.markdown(f"- **{i}.** {t}")
                st.caption(f"{src} · {d}{l}")

        st.markdown("---")

        # ── Full feed with filters ──
        st.markdown("### 📡 Full Industry Feed")

        # Source filter
        all_sources = ["All"] + sorted(source_counts.keys())
        sf1, sf2 = st.columns([1, 2])
        with sf1:
            selected_source = st.selectbox("Filter by source", all_sources, key="industry_source")
        with sf2:
            search_term = st.text_input("Search", "", key="industry_search")

        display_posts = industry_posts
        if selected_source != "All":
            display_posts = [p for p in display_posts if p.get("_industry_source") == selected_source]
        if search_term:
            search_lower = search_term.lower()
            display_posts = [p for p in display_posts if search_lower in (p.get("text", "") + " " + p.get("title", "")).lower()]

        st.caption(f"Showing {len(display_posts)} posts")

        # Paginate
        per_page = 15
        total_pages = max(1, (len(display_posts) + per_page - 1) // per_page)
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
        paged = display_posts[start:start + per_page]

        for idx, post in enumerate(paged, start=start + 1):
            source_label = post.get("_industry_source", post.get("source", "?"))
            title = post.get("title", "")[:120] or post.get("text", "")[:120]
            date = post.get("post_date", "")
            url = post.get("url", "")
            score = post.get("score", 0)
            sub = post.get("subreddit", "")

            source_icons = {
                "News": "📰", "YouTube": "🎬", "YouTube (transcript)": "🎬",
                "YouTube (comment)": "💬", "Alt.xyz Blog": "📝",
                "Blowout Forums": "🗣️", "Net54 Baseball": "⚾",
                "COMC": "🃏", "Whatnot": "📱", "Fanatics Collect": "🏈",
                "Bench Trading": "🔄", "TCDB": "🗂️",
                "Reddit": "💬", "Twitter": "🐦", "Bluesky": "🦋",
            }
            icon = source_icons.get(source_label, "📄")

            yt_comments = post.get("_yt_comments", [])
            comment_label = f" · 💬 {len(yt_comments)} comments" if yt_comments else ""
            score_label = f" · ⬆️ {score}" if score else ""
            sub_label = f" · r/{sub}" if sub else ""

            with st.expander(f"{icon} **{title}** — {source_label} · {date}{sub_label}{score_label}{comment_label}"):
                text = post.get("text", "")
                if len(text) > 600:
                    st.markdown(f"> {text[:600]}...")
                elif text:
                    st.markdown(f"> {text}")
                meta_parts = [f"**Source:** {source_label}"]
                if sub:
                    meta_parts.append(f"**Subreddit:** r/{sub}")
                if date:
                    meta_parts.append(f"**Date:** {date}")
                if score:
                    meta_parts.append(f"**Score:** {score}")
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

        st.markdown("---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 5: CHECKLISTS & SEALED LAUNCHES — Checklists & Upcoming Sealed Product Launches
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[4]:
    st.markdown("Upcoming sealed product launches and checklists from Panini, Topps, Leaf, Upper Deck, Bowman, and more.")

    releases_data = []
    try:
        with open("data/upcoming_releases.json", "r", encoding="utf-8") as f:
            releases_data = json.load(f)
    except:
        pass

    if not releases_data:
        st.info("No data available. Run scrapers to collect upcoming sealed launches and checklists.")
    else:
        checklists = [r for r in releases_data if r.get("category") == "checklist"]
        releases = [r for r in releases_data if r.get("category") == "release"]

        # Metrics
        pr1, pr2, pr3 = st.columns(3)
        pr1.metric("Upcoming Releases", len(releases))
        pr2.metric("Checklists Available", len(checklists))
        all_brands = sorted(set(r.get("brand", "Other") for r in releases_data))
        pr3.metric("Brands Tracked", len(all_brands))

        rel_tab1, rel_tab2 = st.tabs(["️ Upcoming Releases", "📋 Checklists"])

        with rel_tab1:
            st.caption("Upcoming sealed product launches — filter by sport/category and brand.")
            rel_sports = sorted(set(r.get("sport", "Trading Cards") for r in releases))
            rel_brands = sorted(set(r.get("brand", "Other") for r in releases))
            fr1, fr2, fr3 = st.columns(3)
            with fr1:
                rel_sport_filter = st.selectbox("Sport/Category", ["All"] + rel_sports, key="rel_sport")
            with fr2:
                rel_brand_filter = st.selectbox("Brand", ["All"] + rel_brands, key="rel_brand")
            with fr3:
                rel_search = st.text_input("Search releases", "", key="rel_search")

            filtered_rel = releases
            if rel_sport_filter != "All":
                filtered_rel = [r for r in filtered_rel if r.get("sport") == rel_sport_filter]
            if rel_brand_filter != "All":
                filtered_rel = [r for r in filtered_rel if r.get("brand") == rel_brand_filter]
            if rel_search:
                rel_search_lower = rel_search.lower()
                filtered_rel = [r for r in filtered_rel if rel_search_lower in (r.get("title", "") + " " + r.get("sport", "")).lower()]

            # Sort by date (most recent first)
            filtered_rel.sort(key=lambda x: x.get("post_date", ""), reverse=True)

            st.caption(f"Showing {len(filtered_rel)} releases")

            if filtered_rel:
                for idx, rel in enumerate(filtered_rel[:50], 1):
                    title = rel.get("title", "")
                    url = rel.get("url", "")
                    date = rel.get("post_date", "")
                    sport = rel.get("sport", "")
                    brand = rel.get("brand", "")
                    link = f"[Details]({url})" if url else ""
                    st.markdown(f"**{idx}.** {title}")
                    st.caption(f"{brand} · {sport} · {date} · {link}")
                if len(filtered_rel) > 50:
                    st.caption(f"... and {len(filtered_rel) - 50} more releases.")
            else:
                st.info("No releases match your filters.")

        with rel_tab2:
            st.caption("Published checklists — click links to view full card lists. Filter by sport/category and brand.")
            cl_sports = sorted(set(c.get("sport", "Trading Cards") for c in checklists))
            cl_brands = sorted(set(c.get("brand", "Other") for c in checklists))
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                cl_sport_filter = st.selectbox("Sport/Category", ["All"] + cl_sports, key="cl_sport")
            with fc2:
                cl_brand_filter = st.selectbox("Brand", ["All"] + cl_brands, key="cl_brand")
            with fc3:
                cl_search = st.text_input("Search checklists", "", key="cl_search")

            filtered_cl = checklists
            if cl_sport_filter != "All":
                filtered_cl = [c for c in filtered_cl if c.get("sport") == cl_sport_filter]
            if cl_brand_filter != "All":
                filtered_cl = [c for c in filtered_cl if c.get("brand") == cl_brand_filter]
            if cl_search:
                cl_search_lower = cl_search.lower()
                filtered_cl = [c for c in filtered_cl if cl_search_lower in (c.get("title", "") + " " + c.get("sport", "")).lower()]

            # Sort by date (most recent first)
            filtered_cl.sort(key=lambda x: x.get("post_date", ""), reverse=True)

            st.caption(f"Showing {len(filtered_cl)} checklists")

            if filtered_cl:
                for idx, cl in enumerate(filtered_cl[:50], 1):
                    title = cl.get("title", "")
                    url = cl.get("url", "")
                    date = cl.get("post_date", "")
                    sport = cl.get("sport", "")
                    brand = cl.get("brand", "")
                    link = f"[Open Checklist]({url})" if url else ""
                    st.markdown(f"**{idx}.** {title}")
                    st.caption(f"{brand} · {sport} · {date} · {link}")
                if len(filtered_cl) > 50:
                    st.caption(f"... and {len(filtered_cl) - 50} more checklists.")
            else:
                st.info("No checklists match your filters.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3 (continued): BROKEN WINDOWS — Bugs, UX confusion, fee friction
with cs_problems_tab:
    st.markdown("### 🔧 Broken Windows")
    st.markdown("Platform bugs, UX friction, and product pain points that eBay, Goldin, or TCGPlayer engineering teams can fix.")

    # ── Broken window categories ──
    # Keywords must be specific enough to avoid matching generic hobby posts
    # Posts already passed _is_bw_actionable (confirmed eBay-related),
    # so category keywords just need to identify the TOPIC, not re-confirm eBay context.
    BW_CATEGORIES = {
        "Returns & INAD Abuse": {
            "keywords": ["inad", "item not as described", "forced return", "return abuse", "partial refund",
                         "case opened", "money back guarantee", "buyer scam", "empty box",
                         "return request", "refund", "sided with buyer", "unfair return",
                         "buyer opened a case", "sent back wrong", "returned wrong item",
                         "buyer claims", "not received", "not as described"],
            "icon": "🔄",
            "owner": "Returns PM",
        },
        "Trust & Fraud": {
            "keywords": ["scam", "fraud", "shill bid", "fake listing", "counterfeit",
                         "fake card", "says it's fake", "it's fake", "not authentic",
                         "stolen", "replica", "knock off", "suspicious seller",
                         "scammer", "ripped off", "got scammed"],
            "icon": "🛡️",
            "owner": "Trust & Safety PM",
        },
        "Authentication & Grading": {
            "keywords": ["authenticity guarantee", "authentication", "misgrade",
                         "wrong grade", "fake grade", "grading error",
                         "grading issue", "grading problem", "grading complaint",
                         "psa error", "bgs error", "cgc error",
                         "grade came back", "grading service", "grading turnaround"],
            "icon": "🏅",
            "owner": "Authentication PM",
        },
        "Vault Bugs": {
            "keywords": ["psa vault", "ebay vault", "vault sell", "vault inventory", "vault withdraw",
                         "vault shipping", "vault delay", "vault error", "vault listing",
                         "stuck in vault", "vault payout", "vault card"],
            "icon": "🏦",
            "owner": "Vault PM",
        },
        "Fee & Pricing Confusion": {
            "keywords": ["fee", "final value", "insertion fee", "take rate", "13.25%",
                         "13%", "12.9%", "ebay takes", "fee structure", "hidden fee",
                         "commission", "overcharged", "too expensive to sell"],
            "icon": "💸",
            "owner": "Monetization PM",
        },
        "Shipping & Label Issues": {
            "keywords": ["shipping label", "tracking", "lost in mail", "lost package",
                         "damaged in transit", "standard envelope", "can't print label",
                         "wrong weight", "shipping estimate", "shipping damage",
                         "arrived damaged", "crushed", "print label"],
            "icon": "📦",
            "owner": "Shipping PM",
        },
        "Payment & Payout Issues": {
            "keywords": ["payment hold", "payout", "funds held", "managed payments", "hold my money",
                         "can't get paid", "money held", "release my funds", "payment processing",
                         "payment delay", "stripe verification", "stopped payment"],
            "icon": "💳",
            "owner": "Payments PM",
        },
        "Seller Protection Gaps": {
            "keywords": ["seller protection", "always side with buyer", "sided with buyer",
                         "no recourse", "lost case", "hate selling", "done with ebay",
                         "leaving ebay", "doesn't care about sellers", "unfair to sellers",
                         "seller cancelled", "cancelled my order"],
            "icon": "🛑",
            "owner": "Seller Experience PM",
        },
        "App & UX Bugs": {
            "keywords": ["ebay app", "ebay website", "app glitch", "app bug", "app crash",
                         "ebay not working", "ebay won't load", "error message",
                         "seller hub bug", "seller hub glitch", "seller hub broken",
                         "white screen", "blank page", "ebay crash",
                         "ebay glitch", "ebay bug", "app won't", "app keeps",
                         "app freezes", "app update broke"],
            "icon": "🐛",
            "owner": "App/UX PM",
        },
        "Account & Policy Enforcement": {
            "keywords": ["account suspended", "account restricted", "banned",
                         "locked out", "policy violation", "vero",
                         "listing removed", "flagged", "delisted", "taken down"],
            "icon": "🔒",
            "owner": "Trust & Safety PM",
        },
        "Search & Listing Visibility": {
            "keywords": ["search broken", "can't find my listing", "no views",
                         "algorithm", "best match", "search ranking",
                         "not showing up", "buried", "no impressions", "no traffic", "cassini"],
            "icon": "🔍",
            "owner": "Search PM",
        },
        "Promoted Listings Friction": {
            "keywords": ["promoted listing", "promoted standard", "promoted advanced",
                         "pay to play", "ad rate", "forced to promote", "ad spend",
                         "promoted listings fee", "visibility tax"],
            "icon": "📢",
            "owner": "Ads PM",
        },
    }

    # ── Filter to platform-actionable issues only ──
    # Must mention eBay/Goldin/TCGPlayer by name OR be from an eBay-focused subreddit
    BW_PLATFORM_NAMES = ["ebay", "e-bay", "goldin", "tcgplayer", "tcg player", "comc"]
    BW_EBAY_SUBS = [
        "ebay", "flipping", "ebaysellers", "ebayselleradvice",
    ]
    # Specific platform features (only count if post also mentions a platform name or is from eBay sub)
    BW_FEATURE_KW = [
        "seller hub", "promoted listing", "vault", "authenticity guarantee",
        "standard envelope", "managed payments", "global shipping",
        "shipping label", "inad", "item not as described", "money back guarantee",
        "payment hold", "payout", "final value fee", "insertion fee",
        "promoted standard", "promoted advanced", "best match",
        "psa vault", "vault inventory",
    ]
    BW_EXCLUDE = [
        "stole my", "nephew", "my cards were stolen", "house fire",
        "fake money", "porch pick up", "hands free controller", "nintendo",
        "dvd of an old film", "mercari", "card show drama",
        "gameshire", "$100b endgame", "the whale, the trio",
        "bitcoin treasury", "diamond hands", "short squeeze", "moass",
        "to the moon", "hedge fund", "warrants to blockchain",
        "official sales/trade/breaks", "leave a comment here in this thread with your sales",
        # Generic hobby posts
        "iron maiden", "secret lair", "new to mtg", "new player",
        "dev kit", "ps vita", "playstation",
        # Collecting stories that mention eBay in passing
        "my daughter swears", "help! my daughter",
        "catalogued my grandmother", "my inheritance",
        "stopped ordering from amazon", "what website or app do you use instead",
        "help me sell my storage unit", "jet engine",
        "would you block this buyer? i already can smell",
        "i only brought 300",
        "seed vault extract", "arc raiders", "stella montis",
        # False PSA/Vault matches from gaming/public-service posts
        "psa if you think you might want to play survival",
        "make a placeholder vault", "placeholder vault",
        "rewards in experimental", "play survival in the future",
        "survival vault", "public service announcement",
        # Celebrations, jokes, memes, personal stories
        "instant retirement", "can't believe i pulled", "best email to receive",
        "second best email", "shove it up", "going up on ebay today",
        "look what i found", "look what i pulled", "just pulled this",
        "mail day", "pickup of the year", "grail acquired",
        "finally got one", "dream card", "holy grail",
        "lcs pickup", "card show pickup", "hit of the year",
        "rip results", "box break results", "case break results",
        "my collection", "collection update", "added to the pc",
        "rate my collection", "show off", "nfs/nft",
    ]
    BW_EXCLUDE_SUBS = [
        "superstonk", "gme_meltdown", "amcstock",
        "bitcoin", "stocks", "investing",
        "gamestop", "gmejungle", "fwfbthinktank", "gme",
        "kleinanzeigen_betrug",
        "arcraiders", "nostupidquestions",
    ]

    # Positive/celebratory signals — these are NOT broken windows even if tagged negative
    BW_POSITIVE_SIGNALS = [
        "best email", "second best email", "can't believe i pulled",
        "instant retirement", "just pulled", "look what i",
        "finally got", "dream card", "holy grail", "grail acquired",
        "love ebay", "ebay came through", "great experience",
        "shout out to ebay", "thank you ebay", "ebay is the best",
        "happy with", "so excited", "pumped", "let's go",
        "w pull", "huge pull", "insane pull", "fire pull",
    ]

    def _is_bw_actionable(post):
        text_lower = (post.get("text", "") + " " + post.get("title", "")).lower()
        sub_lower = post.get("subreddit", "").lower()
        if sub_lower in BW_EXCLUDE_SUBS:
            return False
        if any(ex in text_lower for ex in BW_EXCLUDE):
            return False
        # Skip celebratory / positive posts that aren't actual complaints
        if any(pos in text_lower for pos in BW_POSITIVE_SIGNALS):
            return False
        # Must mention a platform by name, OR be from an eBay sub, OR mention a specific eBay feature
        mentions_platform = any(name in text_lower for name in BW_PLATFORM_NAMES)
        from_ebay_sub = sub_lower in BW_EBAY_SUBS
        mentions_feature = any(kw in text_lower for kw in BW_FEATURE_KW)
        return mentions_platform or from_ebay_sub or mentions_feature

    bw_candidates = [
        i for i in normalized
        if (_taxonomy_type(i) in ("Complaint", "Bug Report") or i.get("brand_sentiment") == "Negative")
        and _is_bw_actionable(i)
    ]

    # Classify into categories
    bw_buckets = {cat: [] for cat in BW_CATEGORIES}
    for insight in bw_candidates:
        text_lower = (insight.get("text", "") + " " + insight.get("title", "")).lower()
        for cat, config in BW_CATEGORIES.items():
            if any(kw in text_lower for kw in config["keywords"]):
                bw_buckets[cat].append(insight)
                break

    # Sort categories by volume
    sorted_cats = sorted(BW_CATEGORIES.items(), key=lambda x: len(bw_buckets[x[0]]), reverse=True)
    active_cats = [(cat, config) for cat, config in sorted_cats if bw_buckets[cat]]

    # ── Executive summary metrics ──
    total_bw = sum(len(bw_buckets[cat]) for cat, _ in active_cats)
    bw1, bw2, bw3 = st.columns(3)
    bw1.metric("Actionable Issues", total_bw, help="Platform bugs, friction, and pain points that teams can fix")
    bw2.metric("Problem Areas", len(active_cats))
    top_cat_name = active_cats[0][0] if active_cats else "None"
    top_cat_count = len(bw_buckets[top_cat_name]) if active_cats else 0
    bw3.metric("Hottest Area", f"{top_cat_name}", delta=f"{top_cat_count} signals", delta_color="inverse")

    # ── AI Broken Windows Executive Brief ──
    def _generate_bw_brief(categories, buckets):
        try:
            from components.ai_suggester import _chat, MODEL_MAIN
        except ImportError:
            return None

        # Build digest of top issues per category
        digest = ""
        for cat, config in categories[:6]:
            items = buckets[cat]
            if not items:
                continue
            digest += f"\n## {cat} ({len(items)} signals, Owner: {config['owner']})\n"
            for p in sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:5]:
                text = p.get("text", "")[:150].replace("\n", " ")
                digest += f"- [{p.get('score',0)} pts] {text}\n"

        prompt = f"""You are a Senior Product Manager at eBay writing a Broken Windows executive brief for the engineering and product leadership team.

Below are the top platform issues grouped by category, sourced from Reddit, Twitter, YouTube, and forums.

{digest}

Write a crisp executive brief in this EXACT format:

### Top 3 Priorities to Fix Now

**1. [Specific issue name]** (Owner: [team])
- **What's broken:** (1-2 sentences, be VERY specific — name the exact flow, feature, or policy)
- **User impact:** (1 sentence — who is affected and how badly)
- **Suggested fix:** (1 concrete action)

**2. [Specific issue name]** (Owner: [team])
- **What's broken:** (1-2 sentences)
- **User impact:** (1 sentence)
- **Suggested fix:** (1 concrete action)

**3. [Specific issue name]** (Owner: [team])
- **What's broken:** (1-2 sentences)
- **User impact:** (1 sentence)
- **Suggested fix:** (1 concrete action)

### Emerging Risks
- (1-2 bullet points about patterns that could become bigger problems)

Be extremely specific. Name exact features, flows, and policies. No generic advice like "investigate" or "improve the experience"."""

        try:
            return _chat(
                MODEL_MAIN,
                "You write sharp, specific product briefs for engineering leadership. Every recommendation must be concrete and actionable.",
                prompt,
                max_completion_tokens=800,
                temperature=0.3
            )
        except Exception:
            return None

    bw_brief_key = "bw_executive_brief"
    if st.button("🧠 Generate AI Broken Windows Brief", key="btn_bw_brief"):
        st.session_state[bw_brief_key] = "__generating__"
        st.rerun()
    if st.session_state.get(bw_brief_key) == "__generating__":
        with st.spinner("Analyzing broken windows across all categories..."):
            result = _generate_bw_brief(active_cats, bw_buckets)
        st.session_state[bw_brief_key] = result or "AI analysis unavailable."
        st.rerun()
    if st.session_state.get(bw_brief_key) and st.session_state[bw_brief_key] != "__generating__":
        with st.container(border=True):
            st.markdown(st.session_state[bw_brief_key])

    st.markdown("---")

    # ── Per-category drill-downs ──
    for cat, config in active_cats:
        items = bw_buckets[cat]
        total_engagement = sum(i.get("score", 0) for i in items)
        severity = "🔴" if len(items) >= 15 else ("🟡" if len(items) >= 5 else "🟢")

        with st.expander(f"{config['icon']} **{cat}** — {len(items)} issues · ⬆️ {total_engagement} engagement · Owner: {config['owner']}", expanded=False):
            # Per-category AI brief
            cat_brief_key = f"bw_cat_brief_{cat}"
            if st.button(f"🧠 AI Summary", key=f"btn_{cat_brief_key}"):
                st.session_state[cat_brief_key] = "__generating__"
                st.rerun()
            if st.session_state.get(cat_brief_key) == "__generating__":
                digest_lines = []
                for p in sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:10]:
                    text = p.get("text", "")[:200].replace("\n", " ")
                    digest_lines.append(f"[{p.get('score',0)} pts] {text}")
                cat_prompt = f"""Analyze these {len(items)} user reports about "{cat}" on eBay. Write a 4-sentence summary:
1. What specific things are broken or frustrating (be concrete — name features/flows)
2. How many users are affected and how severely
3. The #1 thing to fix first and why
4. One specific Jira ticket title for the top fix

Reports:
""" + "\n".join(digest_lines)
                with st.spinner(f"Analyzing {cat}..."):
                    try:
                        from components.ai_suggester import _chat, MODEL_MAIN
                        result = _chat(MODEL_MAIN, "Write specific, actionable product analysis.", cat_prompt, max_completion_tokens=300, temperature=0.3)
                    except Exception:
                        result = None
                st.session_state[cat_brief_key] = result or "AI analysis unavailable."
                st.rerun()
            if st.session_state.get(cat_brief_key) and st.session_state[cat_brief_key] != "__generating__":
                with st.container(border=True):
                    st.markdown(st.session_state[cat_brief_key])

            # Top signals
            sorted_items = sorted(items, key=lambda x: x.get("score", 0), reverse=True)
            for idx, insight in enumerate(sorted_items[:6], 1):
                text = insight.get("text", "")[:300]
                score = insight.get("score", 0)
                url = insight.get("url", "")
                subtag = _taxonomy_topic(insight)
                st.markdown(f"**{idx}.** {text}{'...' if len(insight.get('text', '')) > 300 else ''}")
                meta = f"⬆️ {score}"
                if subtag and subtag.lower() not in ("general", "unknown"):
                    meta += f" · {subtag}"
                if url:
                    meta += f" · [Source]({url})"
                st.caption(meta)
            if len(items) > 6:
                st.caption(f"+ {len(items) - 6} more signals")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1: STRATEGY — Strategic themes + AI doc generation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[0]:
    with st.expander("💡 New here? How to use SignalSynth", expanded=True):
        st.markdown("""
**SignalSynth** turns noisy community chatter into product-ready direction for eBay Collectibles teams.

### Start here
- **📋 Strategy:** identify top themes, then generate PRD/BRD/PRFAQ/Jira drafts.
- **🎯 Customer Signals:** explore real user evidence and feedback.
- **⚔️ Competitor Intel + 📰 Industry & Trends:** pressure-test decisions with market context.
- **📦 Checklists & Sealed Launches:** track release/checklist timing.
- **📊 Charts:** review KPIs and prioritize actions.

**Tip:** Use Ask AI above the tabs for fast synthesis before diving in.
        """)

    st.markdown("Strategic Themes from user signals. Use the hierarchy Theme → Opportunity Area → Supporting Signals → Top Topics, then generate PRDs, BRDs, PRFAQ docs, and Jira tickets.")
    try:
        display_clustered_insight_cards(normalized)
    except Exception as e:
        st.error(f"Cluster view error: {e}")


