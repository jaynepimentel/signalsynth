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

    # Podcast episodes
    podcast_raw = []
    try:
        with open("data/scraped_podcast_posts.json", "r", encoding="utf-8") as f:
            podcast_raw = json.load(f)
    except:
        pass

    # New sources (Trustpilot, blogs, PSA Forums, app reviews, industry analysis, seller communities)
    new_sources_raw = []
    try:
        with open("data/scraped_new_sources_posts.json", "r", encoding="utf-8") as f:
            new_sources_raw = json.load(f)
    except:
        pass

    clusters_count = 0
    try:
        with open("precomputed_clusters.json", "r", encoding="utf-8") as f:
            clusters_data = json.load(f)
            clusters_count = len(clusters_data.get("clusters", []))
    except:
        pass

    # Adhoc scraped data (persisted from previous ad-hoc scrape requests)
    adhoc_raw = []
    try:
        with open("data/adhoc_scraped_posts.json", "r", encoding="utf-8") as f:
            adhoc_raw = json.load(f)
    except:
        pass

    normalized = [normalize_insight(i, cache) for i in scraped_insights]

    # Initialize hybrid retriever for Ask AI (graceful fallback to legacy scoring)
    _hybrid_retriever = None
    try:
        from components.hybrid_retrieval import HybridRetriever
        # Cache key: insight count + first fingerprint (changes when data refreshes)
        _retriever_key = f"{len(normalized)}_{normalized[0].get('fingerprint','') if normalized else ''}"
        if "_hybrid_retriever_cache" not in st.session_state or st.session_state.get("_retriever_key") != _retriever_key:
            st.session_state["_hybrid_retriever_cache"] = HybridRetriever(normalized)
            st.session_state["_retriever_key"] = _retriever_key
        _hybrid_retriever = st.session_state["_hybrid_retriever_cache"]
    except Exception as _retriever_err:
        pass  # Fall back to legacy retrieval

    # Load trend alerts if available
    _trend_alerts = {}
    try:
        with open("trend_alerts.json", "r", encoding="utf-8") as f:
            _trend_alerts = json.load(f)
    except Exception:
        pass

    # Merge adhoc posts into normalized (lightweight — they have basic enrichment already)
    for p in adhoc_raw:
        p.setdefault("ideas", [])
        p.setdefault("persona", "Unknown")
        p.setdefault("journey_stage", "Unknown")
        p.setdefault("brand_sentiment", p.get("brand_sentiment", "Neutral"))
        p.setdefault("taxonomy", {"type": p.get("type_tag", "Discussion"), "topic": p.get("subtag", "General"), "theme": p.get("subtag", "General")})
        p.setdefault("type_tag", (p.get("taxonomy") or {}).get("type", "Discussion"))
        p.setdefault("subtag", (p.get("taxonomy") or {}).get("topic", "General"))
        p.setdefault("theme", (p.get("taxonomy") or {}).get("theme", "General"))
        p.setdefault("clarity", "Unknown")
        p.setdefault("effort", "Unknown")
        p.setdefault("target_brand", "Unknown")
        p.setdefault("action_type", "Unclear")
        p.setdefault("opportunity_tag", "General Insight")
        p.setdefault("topic_focus_list", [])
        p.setdefault("signal_strength", 30)
        normalized.append(p)

    total = len(normalized)
    complaints = sum(1 for i in normalized if _taxonomy_type(i) == "Complaint" or i.get("brand_sentiment") == "Negative")

    # Read accurate pipeline stats (written by quick_process.py)
    _pipeline_meta = {}
    try:
        with open("_pipeline_meta.json", "r", encoding="utf-8") as f:
            _pipeline_meta = json.load(f)
    except Exception:
        pass
    total_posts = _pipeline_meta.get("total_posts_loaded", raw_posts_count + competitor_posts_count)
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
              help="Total posts collected from 42 sources: Reddit, Twitter/X, YouTube, eBay Forums, Trustpilot, blogs, PSA Forums, app reviews, seller communities, news RSS, and podcasts")
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
pipeline_text = f"{total_posts:,} posts from 42 sources → {total:,} insights ({filter_pct}% signal) → {clusters_count} themes"
if date_range:
    st.caption(f"{pipeline_text} · Data: {date_range}")

# ─────────────────────────────────────────────
# Ask AI (always visible above tabs)
# ─────────────────────────────────────────────
st.markdown("### 🤖 Ask AI About the Data")
st.caption("Ask any question about scraped insights and get a polished, data-grounded answer.")

if not OPENAI_KEY_PRESENT:
    st.warning("OpenAI API key not configured. Contact your admin to enable AI Q&A.")
else:
    if "qa_messages" not in st.session_state:
        st.session_state["qa_messages"] = []
    if "qa_draft" not in st.session_state:
        st.session_state["qa_draft"] = ""
    
    # Auto-clean bad responses from history on every page load (no user action needed)
    _cleaned_messages = []
    for m in st.session_state["qa_messages"]:
        if m.get("role") == "user":
            _cleaned_messages.append(m)
        elif m.get("content") and len(m.get("content", "").strip()) >= 50 and not m.get("content", "").startswith("⚠️"):
            _cleaned_messages.append(m)
        # Skip bad responses silently
    st.session_state["qa_messages"] = _cleaned_messages

    # Use a form so Enter key submits the question
    with st.form(key="ask_ai_form", clear_on_submit=False):
        c1, c2 = st.columns([5, 1])
        with c1:
            user_question = st.text_input(
                "Ask a question",
                key="qa_draft",
                placeholder="e.g., What are the top complaints about Whatnot vs eBay?",
            )
        with c2:
            st.write("")
            ask_clicked = st.form_submit_button("Ask AI", type="primary")

    # ── Example prompt selector ──
    _rp_options = [
        "",
        # ── Strategy & Executive ──
        "Give me a weekly executive briefing — top 3 issues to act on, with signal counts and risk-of-inaction.",
        "Which workstreams have the most negative sentiment momentum in the last 14 days?",
        # ── Payment & Checkout Friction ──
        "What are the top checkout and payment friction issues preventing buyers from completing purchases?",
        "What are sellers saying about payout delays, funds held, and managed payments problems?",
        # ── Competitive Positioning ──
        "How does Whatnot threaten eBay in live breaks and card sales — what are sellers switching for?",
        "What are Vinted sellers saying vs eBay sellers about fees, shipping, and buyer protection?",
        # ── Authentication & Grading ──
        "What are the top grading complaints about PSA, BGS, and SGC — and how do they affect eBay trust?",
        # ── Vault & Services ──
        "What are the biggest pain points with PSA Vault and eBay Vault — withdrawals, trust, and UX?",
        # ── Customer Service ──
        "What are customers saying about eBay's customer support — AI bots, response times, and resolution quality?",
        # ── Subsidiary Ecosystem ──
        "How is TCGPlayer performing and what are the top seller complaints about the platform?",
        # ── Trust & Safety ──
        "What scam and fraud patterns are emerging in collectibles and how are they affecting buyer confidence?",
        # ── Seller Economics ──
        "Are eBay fee increases driving sellers to competitors? Show me the evidence with quotes.",
    ]
    def _on_prompt_select():
        val = st.session_state.get("_rp_select", "")
        if val:
            # Populate the text field instead of auto-submitting
            st.session_state["qa_draft"] = val
            st.session_state["_rp_select"] = ""

    st.selectbox(
        "💡 Or try an example prompt",
        _rp_options,
        format_func=lambda x: "Select an example prompt..." if x == "" else x,
        key="_rp_select",
        on_change=_on_prompt_select,
    )

    # Also trigger on ad-hoc re-ask after scrape
    _auto_reask = st.session_state.pop("_adhoc_auto_ask", None)
    if (ask_clicked or _auto_reask) and (user_question.strip() or _auto_reask):
        question = (_auto_reask or user_question).strip()
        st.session_state["qa_messages"].append({"role": "user", "content": question})

        q_lower = question.lower()
        q_words = set(q_lower.split())

        # ── Hybrid Retrieval (BM25 + embeddings + RRF) ──
        # Falls back to legacy keyword scoring if hybrid retriever unavailable
        if _hybrid_retriever is not None:
            relevant = _hybrid_retriever.retrieve(question, top_k=25, candidate_pool=60, max_per_source=15)
        else:
            # Legacy fallback: keyword-based retrieval
            _TERM_EXPANSIONS = {
                "vault": ["vault", "storage", "withdraw", "stuck in vault", "vault sell", "vault payout", "vault card"],
                "shipping": ["shipping", "tracking", "lost package", "damaged in transit", "standard envelope", "label", "carrier"],
                "payment": ["payment", "payout", "funds held", "managed payments", "hold my money", "payment hold"],
                "returns": ["return", "inad", "refund", "item not as described", "money back", "buyer scam"],
                "fees": ["fee", "final value", "insertion fee", "take rate", "commission", "overcharged"],
                "authentication": ["authentication", "authenticity guarantee", "ag", "misgrade", "grading"],
                "grading": ["grading", "psa", "bgs", "cgc", "turnaround", "grade", "slab"],
                "whatnot": ["whatnot", "live breaks", "live shopping"],
                "vinted": ["vinted", "vinted app", "vinted seller", "vinted fees", "vinted vs ebay"],
                "fanatics": ["fanatics", "fanatics collect", "fanatics live"],
                "goldin": ["goldin", "goldin auctions", "goldin elite", "ken goldin", "king of collectibles", "goldin buyer premium", "goldin consignment", "goldin 100"],
                "tcgplayer": ["tcgplayer", "tcg player", "tcgplayer fees", "tcgplayer seller", "tcgplayer scam", "tcgplayer condition", "tcgplayer refund", "tcgplayer shipping"],
                "heritage": ["heritage auctions", "heritage auction", "ha.com", "heritage buyer premium", "heritage consignment", "heritage fees"],
                "churn": ["churn", "leaving ebay", "switching", "done with ebay", "switched to"],
                "price guide": ["price guide", "card ladder", "cardladder", "scan to price", "card value", "market comps", "price tool", "ebay comps", "sales data", "transaction data", "pricing data"],
                "search": ["search", "best match", "cassini", "no views", "not showing up", "visibility"],
                "promoted": ["promoted listing", "promoted standard", "promoted advanced", "pay to play", "ad spend"],
                "app": ["app", "seller hub", "app crash", "app bug", "app glitch"],
                "instant offer": ["instant offer", "immediate offer", "buyback", "buy back", "sell now", "cash out", "instant liquidity", "quick flip", "psa offers", "courtyard", "arena club", "starstock", "dibbs", "otia"],
                "liquidity": ["liquidity", "liquidat", "cash out", "free up funds", "free up capital", "sell fast", "quick sell", "fire sale", "need cash", "fund a break", "reinvest", "wallet funds", "wallet balance", "instant offer", "buyback", "psa offers"],
                "courtyard": ["courtyard", "buyback", "wallet funds", "wallet balance", "instant offer"],
                "arena club": ["arena club", "arenaclub", "instant offer", "buyback"],
                "psa offers": ["psa offers", "psa offer", "instant offer", "buyback"],
                "beckett": ["beckett", "bgs", "beckett grading", "beckett pricing", "beckett acquisition", "beckett fanatics", "beckett marketplace"],
                "trustpilot": ["trustpilot", "trustpilot review", "review", "rating", "customer review", "app review", "star rating"],
                "card ladder": ["card ladder", "cardladder", "card ladder index", "cardladder.com", "card ladder data", "ebay transaction data", "scan to price", "card value tool"],
                "psa forums": ["psa forums", "collectors universe", "psa community", "psa discussion"],
                "seller community": ["seller community", "seller forum", "seller experience", "seller complaint", "seller feedback"],
            }
            expanded_terms = set()
            for w in q_words:
                if len(w) > 2:
                    expanded_terms.add(w)
            for trigger, expansions in _TERM_EXPANSIONS.items():
                if trigger in q_lower:
                    expanded_terms.update(expansions)
            _EXACT_MATCH_TERMS = {"tcgplayer", "tcg player", "goldin", "whatnot", "comc", "alt.xyz", "heritage", "beckett", "fanatics", "card ladder", "cardladder"}
            _q_review = any(t in q_lower for t in ["trustpilot", "review", "app review", "rating", "star rating", "app store", "play store", "customer review"])
            _q_persona = any(t in q_lower for t in ["sellers saying", "buyers saying", "seller perspective", "buyer perspective", "seller experience", "buyer experience", "what do sellers", "what do buyers", "seller sentiment", "buyer sentiment", "seller feedback", "buyer feedback", "power seller", "new seller", "casual buyer"])
            _q_fees = any(t in q_lower for t in ["fee", "fees", "pricing", "take rate", "commission", "final value", "insertion fee", "cost to sell", "seller fee", "buyer premium", "how much does"])
            def _relevance_score(insight):
                text = (insight.get("text", "") + " " + insight.get("title", "")).lower()
                subtag = (_taxonomy_topic(insight) or "").lower()
                source = (insight.get("source", "") or "").lower()
                competitor = (insight.get("competitor", "") or "").lower()
                entity_name = (insight.get("entity_name", "") or "").lower()
                score = 0
                for term in expanded_terms:
                    if len(term) <= 2:
                        continue
                    if term in _EXACT_MATCH_TERMS:
                        import re as _re_inner
                        pattern = r'\b' + _re_inner.escape(term) + r'\b'
                        if _re_inner.search(pattern, text):
                            score += 6
                        if term in competitor:
                            score += 8
                        if term in entity_name:
                            score += 8
                    else:
                        if term in text:
                            score += 2
                        if term in subtag:
                            score += 4
                        if term in source:
                            score += 2
                sig_strength = insight.get("signal_strength", 0)
                if sig_strength > 60:
                    score += 3
                elif sig_strength > 30:
                    score += 1
                eng = insight.get("score", 0)
                if eng >= 50:
                    score += 2
                elif eng >= 10:
                    score += 1
                if _q_review and "trustpilot" in source:
                    score += 5
                if _q_review and source in ("app reviews", "seller community"):
                    score += 3
                if _q_persona and source in ("seller community", "app reviews"):
                    score += 3
                if _q_fees and any(w in text for w in ["fee", "commission", "take rate", "final value", "buyer premium"]):
                    score += 3
                return score
            scored = [(p, _relevance_score(p)) for p in normalized]
            scored.sort(key=lambda x: -x[1])
            _all_relevant = [p for p, s in scored if s > 0]
            relevant = []
            _src_counts = defaultdict(int)
            _max_per_source = 24
            for p in _all_relevant:
                src = p.get("source", "Unknown")
                if _src_counts[src] < _max_per_source:
                    relevant.append(p)
                    _src_counts[src] += 1
                if len(relevant) >= 25:
                    break

        # Build numbered source references for the AI to cite
        context_lines = []
        source_refs = []  # [(label, title, url, source_platform)]
        _recent_cutoff = (datetime.now() - __import__('datetime').timedelta(days=14)).strftime("%Y-%m-%d")
        for idx, p in enumerate(relevant[:25], 1):
            title = p.get("title", "")[:140]
            text = p.get("text", "")[:500].replace("\n", " ")
            source = p.get("source", "")
            sub = p.get("subreddit", "")
            subtag = _taxonomy_topic(p)
            sentiment = p.get("brand_sentiment", "")
            score = p.get("score", 0)
            type_tag = _taxonomy_type(p)
            persona = p.get("persona", "")
            sig_str = p.get("signal_strength", 0)
            date = p.get("post_date", "")
            url = p.get("url", "")
            sub_label = f"r/{sub}" if sub else source
            ref_label = f"S{idx}"
            freshness = "RECENT" if date >= _recent_cutoff else "older"
            context_lines.append(
                f"- [{ref_label}] [{freshness}] [{type_tag}] [{sentiment}] [{subtag}] (engagement:{score}, strength:{sig_str}, persona:{persona}, date:{date}, {sub_label}) {title}: {text}"
            )
            if url:
                source_refs.append((ref_label, title or text[:80], url, sub_label))

        # ── Source coverage + cross-source triangulation ──
        _context_sources = defaultdict(int)
        _context_topics = defaultdict(lambda: defaultdict(int))  # topic → source → count
        for p in relevant[:25]:
            src = p.get("source", "Unknown")
            _context_sources[src] += 1
            topic = _taxonomy_topic(p)
            if topic and topic != "General":
                _context_topics[topic][src] += 1
        _source_coverage = ", ".join(f"{src} ({cnt})" for src, cnt in sorted(_context_sources.items(), key=lambda x: -x[1]))

        # Detect cross-source corroboration (same topic from 2+ independent sources)
        _triangulated = []
        for topic, src_map in _context_topics.items():
            if len(src_map) >= 2:
                sources_list = ", ".join(src_map.keys())
                total = sum(src_map.values())
                _triangulated.append(f"- {topic}: corroborated across {len(src_map)} sources ({sources_list}) — {total} signals")
        _triangulation_block = ""
        if _triangulated:
            _triangulation_block = "\n\nCROSS-SOURCE CORROBORATION (high confidence — multiple independent sources agree):\n" + "\n".join(_triangulated[:8])

        # ── Aggregate intelligence context ──
        total_neg = sum(1 for i in normalized if i.get("brand_sentiment") == "Negative")
        total_pos = sum(1 for i in normalized if i.get("brand_sentiment") == "Positive")
        total_complaints = sum(1 for i in normalized if _taxonomy_type(i) == "Complaint")
        total_features = sum(1 for i in normalized if _taxonomy_type(i) == "Feature Request")
        total_churn = sum(1 for i in normalized if i.get("type_tag") == "Churn Signal")
        total_praise = sum(1 for i in normalized if i.get("type_tag") == "Praise")
        subtag_counts = defaultdict(int)
        type_counts = defaultdict(int)
        for i in normalized:
            st_val = _taxonomy_topic(i)
            if st_val and st_val != "General":
                subtag_counts[st_val] += 1
            tt = _taxonomy_type(i)
            if tt:
                type_counts[tt] += 1
        top_subtags = sorted(subtag_counts.items(), key=lambda x: -x[1])[:12]

        stats_block = (
            f"Dataset: {len(normalized)} insights from 42 sources (Reddit, Twitter, YouTube, eBay Forums, Trustpilot, blogs, PSA Forums, app reviews, seller communities, industry news, podcasts)\n"
            f"Sentiment: {total_neg} negative, {total_pos} positive, {total_churn} churn signals, {total_praise} praise\n"
            f"Types: {', '.join(f'{k} ({v})' for k, v in sorted(type_counts.items(), key=lambda x: -x[1])[:8])}\n"
            f"Top topics: {', '.join(f'{k} ({v})' for k, v in top_subtags)}"
        )

        # ── Cluster themes (strategic layer — richer context) ──
        cluster_context = ""
        try:
            with open("precomputed_clusters.json", "r", encoding="utf-8") as _cf:
                _cdata = json.load(_cf)
            cluster_themes = []
            for card in _cdata.get("cards", [])[:10]:
                theme = card.get("theme", card.get("title", ""))
                problem = card.get("problem_statement", "")[:150]
                count = card.get("insight_count", 0)
                sentiments = card.get("sentiments", [])
                top_opp = (card.get("opportunity_tags", []) or ["General"])[0]
                competitors = ", ".join(card.get("mentions_competitor", [])[:3]) or "none"
                cluster_themes.append(
                    f"- {theme} ({count} signals, sentiment: {'/'.join(sentiments)}, opportunity: {top_opp}, competitors: {competitors}): {problem}"
                )
            if cluster_themes:
                cluster_context = "\n\nSTRATEGIC THEMES (AI-clustered from {0} signals):\n".format(
                    sum(c.get("insight_count", 0) for c in _cdata.get("cards", []))
                ) + "\n".join(cluster_themes)
        except Exception:
            pass

        # ── Trend alerts context (velocity / anomaly intelligence) ──
        trend_context = ""
        try:
            if _trend_alerts and _trend_alerts.get("alerts"):
                # Split into query-relevant vs general high-severity alerts
                # Filter out inflated first-load z-scores (z > 50 = data loaded all at once, not real trend)
                _query_alerts = []
                _high_alerts = []
                for a in _trend_alerts["alerts"]:
                    # Skip first-load artifacts: need meaningful baseline (avg > 2 signals/period)
                    if a.get("baseline_value", 0) < 2:
                        continue
                    topic = a.get("topic", "").lower()
                    is_relevant = any(w in topic for w in q_words if len(w) > 3)
                    if is_relevant:
                        _query_alerts.append(a)
                    elif a.get("severity") == "high":
                        _high_alerts.append(a)
                # Prioritize query-relevant, then top high-severity
                _final_alerts = _query_alerts[:3] + _high_alerts[:max(0, 4 - len(_query_alerts[:3]))]
                if _final_alerts:
                    alert_lines = []
                    for a in _final_alerts:
                        alert_lines.append(
                            f"- [{a['severity'].upper()}] {a['alert_type']}: {a['message']} (confidence: {a['confidence']:.0%})"
                        )
                    trend_context = "\n\nTREND VELOCITY ALERTS (statistical anomalies detected this period):\n" + "\n".join(alert_lines)
                # Add absences (only if relevant to query)
                _absences = _trend_alerts.get("absences", [])
                _relevant_absences = [a for a in _absences if any(w in a.get("topic", "").lower() for w in q_words if len(w) > 3)]
                if _relevant_absences:
                    absence_lines = [f"- SILENCE: {a['message']}" for a in _relevant_absences[:2]]
                    trend_context += "\n\nTOPICS GONE SILENT (possible resolution or user churn):\n" + "\n".join(absence_lines)
        except Exception:
            pass

        # ── Competitor landscape ──
        competitor_context = ""
        try:
            comp_counts = defaultdict(int)
            for p in competitor_posts_raw:
                comp_counts[p.get("competitor_name", p.get("source", "Unknown"))] += 1
            if comp_counts:
                comp_lines = [f"- {name}: {cnt} signals" for name, cnt in sorted(comp_counts.items(), key=lambda x: -x[1])[:8]]
                competitor_context = f"\n\nCOMPETITOR LANDSCAPE ({competitor_posts_count} total signals):\n" + "\n".join(comp_lines)
        except Exception:
            pass

        # ── Industry news headlines ──
        industry_context = ""
        try:
            news_headlines = []
            for src_list, src_name in [(cllct_raw, "Cllct"), (news_rss_raw, "News"), (podcast_raw, "Podcast"), (new_sources_raw, "New Sources")]:
                for p in sorted(src_list, key=lambda x: x.get("post_date", ""), reverse=True)[:3]:
                    hl = (p.get("title", "") or p.get("text", ""))[:120]
                    if hl:
                        news_headlines.append(f"- [{src_name}] {hl}")
            if news_headlines:
                industry_context = "\n\nRECENT INDUSTRY NEWS:\n" + "\n".join(news_headlines[:8])
        except Exception:
            pass

        # ── Question-type detection for adaptive prompting ──
        # Note: Goldin and TCGPlayer are eBay SUBSIDIARIES, not competitors
        _q_subsidiary = any(t in q_lower for t in ["goldin", "tcgplayer", "tcg player"])
        _q_liquidity = any(t in q_lower for t in ["instant offer", "liquidity", "liquidat", "buyback", "buy back", "cash out", "sell now", "quick flip", "psa offers", "courtyard", "arena club", "sell fast", "free up funds", "reinvest"])
        _q_competitive = any(t in q_lower for t in ["competitor", "whatnot", "fanatics", "heritage", "versus", " vs ", "compete", "market share", "threat", "comc", "alt.xyz", "beckett", "vinted"])
        _q_strategic = any(t in q_lower for t in ["strategy", "strategic", "roadmap", "prioritize", "invest", "opportunity", "moat", "differentiate", "retention"])
        _q_product = any(t in q_lower for t in ["vault", "price guide", "authentication", "ag ", "promoted", "shipping", "search", "seller hub", "app"])
        _q_trend = any(t in q_lower for t in ["trend", "growing", "declining", "increasing", "changing", "over time", "momentum"])
        _q_review = any(t in q_lower for t in ["trustpilot", "review", "app review", "rating", "star rating", "app store", "play store", "customer review"])
        _q_persona = any(t in q_lower for t in ["sellers saying", "buyers saying", "seller perspective", "buyer perspective", "seller experience", "buyer experience", "what do sellers", "what do buyers", "seller sentiment", "buyer sentiment", "seller feedback", "buyer feedback", "power seller", "new seller", "casual buyer"])
        _q_comparison = any(t in q_lower for t in [" vs ", "versus", "compared to", "compare", "difference between", "better than", "worse than", "pros and cons", "which is better", "how does .* compare"])
        _q_fees = any(t in q_lower for t in ["fee", "fees", "pricing", "take rate", "commission", "final value", "insertion fee", "cost to sell", "seller fee", "buyer premium", "how much does"])
        _q_briefing = any(t in q_lower for t in ["briefing", "brief me", "summary", "summarize", "highlights", "this week", "what should i know", "executive summary", "digest", "top findings", "key takeaway", "overview", "what's new", "what happened"])

        # Adaptive format instructions
        if _q_review and not _q_subsidiary and not _q_competitive:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: What's the overall review sentiment? What's the #1 theme across reviews?)

### Review Sentiment Breakdown
| Platform | Positive Themes | Negative Themes | Key Quote |
|----------|----------------|----------------|-----------|
(Fill with rows for each platform mentioned in signals — eBay, Goldin, TCGPlayer, Whatnot, Heritage as applicable)

### What Reviewers Love
(3-5 bullets with VERBATIM reviewer quotes in "italics" with [S#] citations — what's working well)

### What Reviewers Hate
(3-5 bullets with VERBATIM reviewer quotes in "italics" with [S#] citations — pain points and complaints)

### Competitive Review Comparison
(2-3 sentences: How does eBay's review sentiment compare to competitors? Which platform has the happiest/angriest users?)

### Recommended Actions
1. **[Action Name]** — Owner: [Team/PM]. Timeline: [When]. Impact: [How this addresses reviewer complaints]
2-4. [Continue with prioritized actions]

### Confidence & Gaps
- Evidence strength: [Strong/Moderate/Weak] based on [X] review signals
- What's missing: [specific gaps in review coverage]"""
        elif _q_liquidity:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

CONTEXT: The collectibles market is experiencing a surge in "instant liquidity" features — platforms offering instant offers, buybacks, and wallet-based payouts to let users quickly convert holdings to cash or reinvest. Key players include:
- PSA Offers (instant buyback on graded cards)
- Courtyard (wallet-based buyback with instant funds)
- Arena Club (instant offers on vault cards)
- eBay (traditional marketplace — slower but larger audience)

Analyze how these instant liquidity trends affect eBay's ecosystem, seller/buyer behavior, and competitive positioning.

### 🎯 Bottom Line
(2-3 sentences: What's the liquidity signal? How does this trend impact eBay's collectibles business?)

### Liquidity Landscape
(4-6 sentences analyzing the instant offer/liquidity trend — who's offering it, why users want it, volume/sentiment from signals)

### User Signals
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] citations showing liquidity-related behavior or sentiment)

### Impact Assessment
| Factor | Current State | eBay Opportunity | Risk if Ignored |
|--------|--------------|-----------------|-----------------|
(Fill with 3-4 rows: e.g., Seller retention, Buyer reinvestment velocity, Wallet/funds ecosystem, Cross-platform leakage)

### Recommended Actions for eBay
(4-6 NUMBERED actions:
1. **[Action Name]** — Owner: [Team/PM]. Timeline: [When]. Impact: [How this captures liquidity demand])

### Confidence & Gaps
- Evidence strength: [Strong/Moderate/Weak] based on [X] signals
- What's missing: [specific data gaps]"""
        elif _q_subsidiary:
            # Goldin and TCGPlayer are eBay SUBSIDIARIES - analyze as ecosystem, not competitors
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

IMPORTANT CONTEXT: Goldin and TCGPlayer are eBay SUBSIDIARIES (eBay-owned companies), NOT competitors. 
Analyze them as part of the eBay Collectibles ecosystem, focusing on:
- How they complement or extend eBay's marketplace
- User experience and sentiment with these eBay-owned platforms
- Integration opportunities or friction points with core eBay
- How they strengthen eBay's overall collectibles position

### 🎯 Bottom Line
(2-3 sentences: What's the key insight about this eBay subsidiary? How is it performing within the eBay ecosystem?)

### Ecosystem Assessment
(4-6 sentences analyzing how this subsidiary fits within eBay Collectibles — user sentiment, market positioning, integration with core eBay)

### User Feedback
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] citations showing user experience with this eBay subsidiary)

### Ecosystem Synergies & Friction
| Area | Synergy with eBay | Friction/Gap | Opportunity |
|------|------------------|--------------|-------------|
(Fill with 3-4 rows: e.g., Seller overlap, Buyer cross-shopping, Authentication, Inventory flow)

### Recommended Actions
(4-6 NUMBERED actions to improve this subsidiary's integration or performance within the eBay ecosystem:
1. **[Action Name]** — Owner: [Team/PM]. Timeline: [When]. Impact: [Expected ecosystem benefit])

### Confidence & Gaps
- Evidence strength: [Strong/Moderate/Weak] based on [X] signals
- What's missing: [specific data gaps]"""
        elif _q_competitive:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: What's the ONE key takeaway an exec needs to know? Be direct and specific.)

### Executive Answer
(4-6 sentences framing the competitive dynamics — who's winning, who's losing, why it matters for eBay)

### Competitive Evidence
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] citations showing how users compare platforms. Example: "I switched to Whatnot because eBay fees are insane" [S3])

### Threat Assessment
| Factor | eBay Position | Competitor Advantage | Risk Level |
|--------|--------------|---------------------|------------|
(Fill this table with 3-4 rows analyzing specific competitive dynamics)

### Strategic Response
(4-6 NUMBERED actions with this structure:
1. **[Action Name]** — Owner: [Team/PM]. Timeline: [When]. Impact: [Expected outcome]. Evidence: [S#])

### Confidence & Gaps
- Evidence strength: [Strong/Moderate/Weak] based on [X] signals
- What's missing: [specific data gaps]"""
        elif _q_strategic:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: What strategic decision should leadership make based on this evidence?)

### Strategic Assessment
(5-8 sentences framing the opportunity/challenge — quantify the scale: how many signals, what % negative, which personas affected)

### Signal Evidence
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] citations, organized by theme)

### Market Context
- **Industry trend**: [How does this connect to broader collectibles market shifts?]
- **Competitive pressure**: [Are competitors doing better/worse here?]
- **Timing urgency**: [Is this getting worse? Stable? Improving?]

### Recommended Strategy
**Immediate (This Week)**:
1. [Action] — Owner: [Team]. Impact: [Expected outcome]

**30-Day Horizon**:
2-3. [Actions with owners and impacts]

**90-Day Horizon**:
4-5. [Strategic investments with expected ROI]

### Risks & Dependencies
- [Risk 1]: Mitigation: [approach]
- [Risk 2]: Mitigation: [approach]"""
        elif _q_trend:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: What's the trend? Is it accelerating, stable, or declining? What should leadership do about it?)

### Trend Analysis
| Timeframe | Signal Volume | Sentiment | Key Drivers |
|-----------|--------------|-----------|-------------|
| Recent (7d) | [X signals] | [% neg/pos] | [Main themes] |
| Last 30d | [X signals] | [% neg/pos] | [Main themes] |

### What's Driving This Trend
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] citations showing the evolution)

### Trajectory Assessment
- **Direction**: [Improving / Stable / Worsening]
- **Velocity**: [Accelerating / Steady / Slowing]
- **Leading indicators**: [What signals predict where this is heading?]

### Implications
- **If trend continues**: [What happens in 30/60/90 days?]
- **Competitive context**: [Are competitors seeing the same?]
- **Business impact**: [GMV/retention/NPS implications]

### Recommended Response
1. **[Action]** — Owner: [Team]. Timeline: [When]. Expected Impact: [Outcome]
2. [Continue with 2-4 more prioritized actions]

### Confidence & Gaps
- Trend confidence: [High/Medium/Low] based on [X] signals over [Y] timeframe
- What would help: [Additional data to confirm/refute]"""
        elif _q_product:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: Is this product working? What's the #1 thing that needs to change?)

### Product Health Summary
| Metric | Status | Evidence |
|--------|--------|----------|
| User Sentiment | 🟢/🟡/🔴 | X% negative, Y signals |
| Functional Issues | 🟢/🟡/🔴 | [Key bugs/friction] |
| Competitive Position | 🟢/🟡/🔴 | [vs. alternatives] |

### User Evidence
**What's Working** (with [S#] citations):
- "[verbatim positive quote]" [S#]

**What's Broken** (with [S#] citations):
- "[verbatim negative quote]" [S#] — Impact: [who's affected, how severely]

### Impact Analysis
- **Revenue risk**: [$ or GMV impact if estimable]
- **Retention risk**: [Which persona is most likely to churn?]
- **Brand risk**: [Reputation/trust implications]

### Recommended Fixes
| Priority | Fix | Owner | User Impact | Effort |
|----------|-----|-------|-------------|--------|
| P0 | [Critical fix] | [Team] | [Impact] | [S/M/L] |
| P1 | [Important fix] | [Team] | [Impact] | [S/M/L] |

### Confidence & Gaps
- Evidence: [X] signals, [Strong/Moderate/Weak] coverage
- Missing: [What would strengthen this analysis?]"""
        elif _q_briefing:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 📋 Executive Signal Digest

### 🔴 Top 3 Issues Demanding Attention
1. **[Issue Name]** — [1-2 sentence summary]. Source: [S#]. Severity: 🔴/🟡
2. **[Issue Name]** — [1-2 sentence summary]. Source: [S#]. Severity: 🔴/🟡
3. **[Issue Name]** — [1-2 sentence summary]. Source: [S#]. Severity: 🔴/🟡

### 📊 Signal Landscape
| Category | Volume | Sentiment | Trend |
|----------|--------|-----------|-------|
| [e.g., Vault] | X signals | 🔴 Mostly negative | ↗️ Growing |
| [e.g., Shipping] | X signals | 🟡 Mixed | → Stable |
(Fill with 4-6 top categories from the data)

### 🏢 Competitor & Subsidiary Watch
(3-4 bullets on notable competitor moves or subsidiary signals, with [S#] citations)

### 💬 Voices from the Community
(3-5 VERBATIM user quotes in "italics" with [S#] that best capture the current mood — pick the most vivid, specific, or concerning ones)

### ⚡ Emerging Signals
(2-3 bullets on patterns that are new or growing — things that weren't prominent before but are gaining traction)

### 🎯 Recommended Focus This Week
1. **[Action]** — Owner: [Team]. Why now: [urgency]
2. **[Action]** — Owner: [Team]. Why now: [urgency]
3. **[Action]** — Owner: [Team]. Why now: [urgency]"""
        elif _q_fees and not _q_competitive:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: What's the overall fee sentiment? Is it a churn driver or manageable friction?)

### Fee Landscape Comparison
| Platform | Fee Structure | User Sentiment | Key Complaint |
|----------|--------------|----------------|---------------|
| eBay | [Final value fee %, insertion fees, promoted listings] | 🟢/🟡/🔴 | [Top complaint] |
| Whatnot | [Fee structure if known] | 🟢/🟡/🔴 | [Top complaint] |
| TCGPlayer | [Fee structure if known] | 🟢/🟡/🔴 | [Top complaint] |
| Heritage | [Buyer premium, consignment %] | 🟢/🟡/🔴 | [Top complaint] |
| Goldin | [Buyer premium, consignment %] | 🟢/🟡/🔴 | [Top complaint] |
(Fill based on available signals — leave blank if no data)

### What Users Are Saying About Fees
(5-8 bullets with VERBATIM quotes in "italics" with [S#] citations, organized by theme: hidden fees, fee increases, fee comparisons, value-for-money)

### Fee Impact on Behavior
- **Churn risk**: [Are users leaving over fees? Which persona?]
- **Listing behavior**: [Are sellers listing fewer items, raising prices, or switching to other platforms?]
- **Platform comparison shopping**: [Are sellers actively comparing fee structures?]

### Recommended Fee Strategy
1. **[Action]** — Owner: [Team]. Impact: [Expected outcome]
2-3. [Continue with prioritized actions]

### Confidence & Gaps
- Evidence: [X] fee-related signals from [Y] sources
- What's missing: [fee data gaps]"""
        elif _q_persona:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: What's the key insight? Which persona is most affected?)

### 🏪 Seller Perspective
**Sentiment**: 🟢/🟡/🔴
**Top Concerns** (with [S#] citations):
1. "[verbatim seller quote]" [S#] — [context: Power Seller / New Seller / etc.]
2. "[verbatim seller quote]" [S#]
3. "[verbatim seller quote]" [S#]

**What Sellers Want**: (2-3 bullets summarizing seller asks)

### 🛒 Buyer/Collector Perspective
**Sentiment**: 🟢/🟡/🔴
**Top Concerns** (with [S#] citations):
1. "[verbatim buyer quote]" [S#] — [context: Collector / Investor / Casual Buyer]
2. "[verbatim buyer quote]" [S#]
3. "[verbatim buyer quote]" [S#]

**What Buyers Want**: (2-3 bullets summarizing buyer asks)

### Persona Friction Map
| Persona | Pain Point | Severity | eBay Feature Affected |
|---------|-----------|----------|----------------------|
| Power Seller | [specific pain] | 🔴/🟡 | [feature] |
| Collector | [specific pain] | 🔴/🟡 | [feature] |
| New Seller | [specific pain] | 🔴/🟡 | [feature] |
| Investor | [specific pain] | 🔴/🟡 | [feature] |
(Fill based on available signals)

### Recommended Actions by Persona
1. **For Sellers**: [Action] — Owner: [Team]. Impact: [outcome]
2. **For Buyers**: [Action] — Owner: [Team]. Impact: [outcome]
3. **Cross-persona**: [Action] — Owner: [Team]. Impact: [outcome]

### Confidence & Gaps
- Evidence: [X] signals. Seller-heavy / Buyer-heavy / Balanced?
- Missing perspectives: [which persona is underrepresented?]"""
        elif _q_comparison and not _q_competitive:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: Which option comes out ahead based on user signals? What's the deciding factor?)

### Side-by-Side Comparison
| Factor | [Option A] | [Option B] | Winner |
|--------|-----------|-----------|--------|
| User Sentiment | [summary] | [summary] | [A/B/Tie] |
| Fees/Pricing | [if relevant] | [if relevant] | [A/B/Tie] |
| Trust & Safety | [summary] | [summary] | [A/B/Tie] |
| Ease of Use | [summary] | [summary] | [A/B/Tie] |
| Selection/Inventory | [summary] | [summary] | [A/B/Tie] |
(Customize factors based on what's being compared. Fill from signals only.)

### What Users Say About [Option A]
(3-4 bullets with VERBATIM quotes in "italics" with [S#] citations)

### What Users Say About [Option B]
(3-4 bullets with VERBATIM quotes in "italics" with [S#] citations)

### Users Who've Tried Both
(2-3 bullets from users who directly compare, with [S#] citations — these are the most valuable signals)

### Implications for eBay
- **If [A] is eBay**: [What to defend / improve]
- **If [B] is eBay**: [What to defend / improve]
- **Ecosystem opportunity**: [How can eBay win regardless?]

### Confidence & Gaps
- Comparison evidence: [Strong/Moderate/Weak] — [X] signals directly compare these options
- Caveat: [Any selection bias or missing perspectives?]"""
        else:
            format_guidance = """RESPOND IN THIS EXACT FORMAT:

### 🎯 Bottom Line
(2-3 sentences: Answer the question directly. What does leadership need to know RIGHT NOW?)

### Executive Answer
(4-6 sentences expanding on the bottom line with data backing — cite signal counts, sentiment ratios, key patterns)

### What the Signals Show
(5-8 bullets with VERBATIM user quotes in "italics" with [S#] references. Example:
- "I've been on eBay for 15 years but the new fee structure is pushing me to Whatnot" [S3] — Power Seller, 89 engagement score)

### Implications for eBay Collectibles
- **Revenue impact**: [How does this affect GMV/take rate?]
- **User impact**: [Which personas? How many affected?]
- **Competitive impact**: [Does this help/hurt vs. competitors?]
- **Timeline urgency**: [Is this acute or chronic? Getting worse?]

### Recommended Actions
1. **[Action Name]** — Owner: [Specific team/PM]. Timeline: [When]. Expected Impact: [Quantified if possible]
2. [Continue with 3-5 more prioritized actions]

### Confidence & Gaps
- Evidence strength: [Strong/Moderate/Weak] — based on [X] signals from [Y] sources
- Bias check: [Are signals one-sided? Missing perspectives?]
- What would help: [Additional data that would strengthen conclusions]"""

        context_block = "\n".join(context_lines) if context_lines else "(No directly matching posts found.)"

        system_prompt = f"""You are SignalSynth AI — a senior strategy analyst embedded in the eBay Collectibles & Trading Cards business unit.

DOMAIN EXPERTISE:
- eBay SUBSIDIARIES (owned by eBay, NOT competitors): Goldin (premium auctions), TCGPlayer (TCG marketplace)
- eBay PARTNERSHIPS: PSA (vault, consignment, grading), Card Ladder (receives eBay transaction data to power indexes)
- PRICE GUIDE STRATEGY: eBay's goal is to be THE premier, most trusted price guide in the collectibles market. eBay provides its transaction/sales data to partners like Card Ladder and PSA to help them build their indexes — but eBay's own Price Guide (powered by eBay sales comps) is the primary product. Card Ladder and PSA are data recipients, not data providers to eBay. When analyzing Price Guide signals, frame eBay as the owner of the most comprehensive transaction dataset in collectibles.
- TRUE COMPETITORS (external threats): Whatnot (live breaks), Fanatics Collect (marketplace + Topps/Panini licenses), Heritage Auctions (high-end), Alt (fractional), COMC (consignment), Beckett (grading + pricing, acquired by Fanatics), Vinted (resale marketplace, growing in collectibles/cards)
- INSTANT LIQUIDITY LANDSCAPE: PSA Offers (instant buyback on graded cards), Courtyard (wallet-based buyback + instant funds), Arena Club (instant offers on vault cards), StarStock, Dibbs, Otia — these platforms offer instant liquidity features that let users convert holdings to cash or reinvest immediately. This is an emerging competitive dynamic for eBay.
- eBay products: Authenticity Guarantee, Price Guide, Vault, Promoted Listings, Seller Hub
- User personas: Power Sellers, Collectors, Investors, New Sellers, Casual Buyers
- Key metrics: GMV, take rate, seller NPS, buyer conversion, authentication volume
- DATA SOURCES: This dataset includes Trustpilot reviews (eBay, Goldin, TCGPlayer, Whatnot, Heritage), app store review discussions, PSA Collectors Universe forums, Goldin Blog, Heritage Blog, Card Ladder blog, seller community forums, and industry analysis reports — in addition to Reddit, Twitter/X, YouTube, eBay Forums, news RSS, and podcasts.

CRITICAL: When discussing Goldin or TCGPlayer, remember they are PART OF THE EBAY ECOSYSTEM. Analyze them as subsidiaries that extend eBay's reach, not as competitive threats.

YOUR AUDIENCE: VP/GM-level leaders who make investment and prioritization decisions. They need strategic clarity, not just data summaries. Connect evidence to business impact.

{format_guidance}

CRITICAL RULES — FOLLOW EXACTLY:

⚠️ ANTI-HALLUCINATION RULES (MOST IMPORTANT):
- You have NO external data. You ONLY know what's in the RELEVANT SIGNALS section below.
- NEVER invent statistics like "10% improvement" or "7-9% increase" — you have NO survey data, NO metrics, NO percentages unless explicitly stated in a signal.
- NEVER claim "recent data shows" or "surveys indicate" — you only have community posts and forum discussions.
- Every number you cite MUST come from the signals: "X of Y signals mention...", "engagement score of Z from [S#]"
- If you don't have data to answer, say "The signals don't contain direct evidence on this, but based on related discussions..."

PER-CLAIM CITATION ENFORCEMENT:
- For each factual claim you make, you MUST link it to one or more [S#] source references.
- If a claim cannot be supported by any signal, explicitly label it as "[Inference]" or remove it.
- When quoting users, copy their EXACT words in "italics" and tag with [S#]. Do NOT paraphrase and pretend it's a quote.
- TABLE ROWS must include [S#] citations in the cells (e.g., "| Vault | 5 signals | Complaint [S2][S7] | Rising |").
- RECOMMENDATIONS must cite the signal(s) that justify them (e.g., "based on [S3] and [S8]").
- EMERGING SIGNALS bullets must each cite at least one [S#].
- Aim for 80%+ faithfulness (4 of every 5 substantive sentences should have [S#] citations).

RESPONSE RULES:
1. **ALWAYS produce a substantive response** — never return empty or minimal text. If evidence is thin, say so but still provide analysis.
2. **Lead with the answer** — executives skim. Put the most important insight in the first 2-3 sentences.
3. **Ground EVERY claim in [S#] citations** — if you can't cite a signal, don't make the claim.
4. **Use VERBATIM quotes** — copy exact user language in "italics" with [S#] tags AND persona/engagement context: *"quote here"* [S3] — Power Seller, 228 engagement. This lets readers gauge signal weight.
5. **Map to eBay product areas** — Always connect signals to specific eBay products: Vault, Authenticity Guarantee (AG), Price Guide, Promoted Listings, Seller Hub, Search/Best Match, Managed Payments, Standard Envelope, eBay International Shipping, eBay Live. Never say "improve the experience" — say "fix Vault withdrawal flow" or "improve AG turnaround communication."
6. **Only quantify what you can count** — "8 of 25 signals mention shipping issues", NOT invented percentages.
7. **Connect patterns** — synthesize what signals mean together.
8. **Actionable recommendations** — every recommendation needs: Owner (team/PM), Timeline (when), Expected Impact (what changes).
9. **Be honest about gaps** — if evidence is thin or one-sided, flag it explicitly. Say "I don't have enough data" when true.
10. **Write for a VP** — they have 2 minutes. Make every sentence count.
11. **Source triangulation** — when multiple independent sources agree, call it out: "Corroborated across Reddit, Trustpilot, and eBay Forums." Use the CROSS-SOURCE CORROBORATION section.
12. **Trend velocity** — if TREND VELOCITY ALERTS show a topic spiking or shifting, say so: "Vault signals up +47% this period (z=3.2), escalating." This is proactive intelligence, not just a summary.
13. **Freshness** — signals tagged [RECENT] are from the last 14 days. Weight them more heavily for "what's happening now" questions. Flag when evidence is mostly older.
14. **Competitive migration** — when signals show users moving between platforms, call it out explicitly: "Sellers are actively moving high-value card sales to eBay due to TCGPlayer's limitations [S8]." Name the source platform, destination platform, and the reason.
15. **Risk-of-inaction** — frame consequences: "If not addressed, this risks seller churn and cross-platform leakage to Whatnot." Executives need to know what happens if they do nothing.
16. **Describe user behaviors, not just sentiment** — don't just say "users are frustrated." Describe what they're doing: "Buyers intentionally wait to bundle purchases for shipping savings, but the new 1-hour payment policy blocks this workflow [S1]." Behavior context makes signals actionable.

DATASET SUMMARY:
{stats_block}
{cluster_context}
{trend_context}
{competitor_context}
{industry_context}
{_triangulation_block}

SOURCE COVERAGE FOR THIS QUERY: {_source_coverage}
(Note: signals come from {len(_context_sources)} different source types. When multiple source types agree, confidence is higher.)
(Signals marked [RECENT] are from the last 14 days — weight these more heavily for "what's happening now" questions.)

RELEVANT SIGNALS (sorted by relevance to the question):
{context_block}"""

        try:
            from openai import OpenAI
            import os
            from dotenv import load_dotenv
            
            # Load API key fresh each time
            load_dotenv()
            load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key or "YOUR_" in api_key.upper():
                # Try Streamlit secrets
                try:
                    api_key = st.secrets.get("OPENAI_API_KEY")
                except:
                    pass
            
            if not api_key or "YOUR_" in str(api_key).upper():
                response = "⚠️ OpenAI API key not configured. Check your .env file or Streamlit secrets."
            else:
                # Create fresh client for each request
                _client = OpenAI(api_key=api_key)
                _ask_ai_model = "gpt-4.1"
                
                _signals_used = min(len(relevant), 25)
                with st.spinner(f"Analyzing {_signals_used} relevant signals (model: {_ask_ai_model}, from {len(normalized):,} total)..."):
                    # Make direct API call
                    try:
                        completion = _client.chat.completions.create(
                            model=_ask_ai_model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": question}
                            ],
                            max_completion_tokens=4000,
                            temperature=0.4,
                        )
                        response = (completion.choices[0].message.content or "").strip()
                    except Exception as api_err:
                        st.error(f"API call failed: {type(api_err).__name__}: {api_err}")
                        response = f"⚠️ API Error: {api_err}"
                
                # Handle empty responses - try fallback
                if not response or len(response.strip()) < 50:
                    st.warning(f"Primary model returned {len(response) if response else 0} chars. Trying gpt-4o...")
                    try:
                        completion = _client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": question}
                            ],
                            max_completion_tokens=4000,
                            temperature=0.4,
                        )
                        response = (completion.choices[0].message.content or "").strip()
                    except Exception as fallback_err:
                        st.error(f"Fallback API call failed: {fallback_err}")
                        response = f"⚠️ Fallback API Error: {fallback_err}"
                
                # Still empty?
                if not response or len(response.strip()) < 50:
                    response = f"⚠️ AI returned empty response.\n\n**Debug:**\n- Model: {_ask_ai_model}\n- Signals: {len(relevant)}\n- Prompt length: {len(system_prompt)} chars"
            # Detect thin results — offer ad-hoc scrape
            _is_thin = len(relevant) < 5
            
            # Only store if we got a valid response (not empty/error)
            if response and len(response.strip()) >= 50 and not response.startswith("⚠️"):
                st.session_state["qa_messages"].append({
                    "role": "assistant",
                    "content": response,
                    "sources": source_refs,
                    "_thin": _is_thin,
                    "_question": question,
                    "_relevant_count": len(relevant),
                })
            else:
                # Don't persist bad responses - show inline error instead
                st.error(f"AI response failed. {response if response else 'Empty response.'}\n\nTry asking again.")
                # Remove the user question we just added so it doesn't clutter history
                if st.session_state["qa_messages"] and st.session_state["qa_messages"][-1].get("role") == "user":
                    st.session_state["qa_messages"].pop()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # Show error inline but don't persist to history
            st.error(f"⚠️ Error: {e}")
            st.code(tb, language="python")
            # Remove the user question we just added
            if st.session_state["qa_messages"] and st.session_state["qa_messages"][-1].get("role") == "user":
                st.session_state["qa_messages"].pop()

    # ── Handle ad-hoc scrape requests ──
    if st.session_state.get("_adhoc_scrape_pending"):
        adhoc_topic = st.session_state.pop("_adhoc_scrape_pending")
        adhoc_question = st.session_state.pop("_adhoc_reask_question", adhoc_topic)
        with st.spinner(f"🔍 Live-scraping 6 sources (Google News, Bing News, Reddit, Twitter/X, YouTube, Bluesky) for \"{adhoc_topic}\"..."):
            try:
                from utils.adhoc_scrape import run_adhoc_scrape
                new_posts, summary = run_adhoc_scrape(adhoc_topic)
                st.session_state["qa_messages"].append({
                    "role": "assistant",
                    "content": f"📡 **Ad-hoc scrape complete.** {summary}\n\nRe-analyzing with new data...",
                })
                # Merge new posts into normalized for immediate re-query
                for p in new_posts:
                    p.setdefault("ideas", [])
                    p.setdefault("persona", p.get("persona", "Unknown"))
                    p.setdefault("journey_stage", "Unknown")
                    p.setdefault("brand_sentiment", p.get("brand_sentiment", "Neutral"))
                    p.setdefault("taxonomy", {"type": p.get("type_tag", "Discussion"), "topic": p.get("subtag", "General"), "theme": p.get("subtag", "General")})
                    p.setdefault("type_tag", p["taxonomy"]["type"])
                    p.setdefault("subtag", p["taxonomy"]["topic"])
                    normalized.append(p)
                # Trigger re-ask by setting state
                st.session_state["_adhoc_reask"] = adhoc_question
            except Exception as e:
                st.session_state["qa_messages"].append({
                    "role": "assistant",
                    "content": f"⚠️ Ad-hoc scrape failed: {e}",
                })
        st.rerun()

    # ── Handle re-ask after ad-hoc scrape ──
    if st.session_state.get("_adhoc_reask"):
        reask_q = st.session_state.pop("_adhoc_reask")
        st.session_state["qa_draft"] = reask_q
        st.session_state["_adhoc_auto_ask"] = reask_q
        st.rerun()

    if st.session_state["qa_messages"]:
        import streamlit.components.v1 as _stc_qa
        with st.expander("AI Q&A responses", expanded=True):
            _qa_reversed = list(reversed(list(enumerate(st.session_state["qa_messages"]))))
            for msg_idx, msg in _qa_reversed:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

                    if msg["role"] == "assistant" and not msg["content"].startswith("⚠️"):
                        # Feedback and copy buttons
                        fb_col1, fb_col2, fb_col3, fb_col4 = st.columns([1, 1, 1, 4])
                        with fb_col1:
                            if st.button("👍", key=f"thumbs_up_{msg_idx}", help="Good response - save for training"):
                                # Save to training file
                                import json
                                from datetime import datetime
                                training_entry = {
                                    "timestamp": datetime.now().isoformat(),
                                    "question": msg.get("_question", ""),
                                    "response": msg["content"],
                                    "sources_count": len(msg.get("sources", [])),
                                    "feedback": "positive"
                                }
                                training_file = "ai_training_feedback.json"
                                try:
                                    with open(training_file, "r", encoding="utf-8") as f:
                                        training_data = json.load(f)
                                except:
                                    training_data = []
                                training_data.append(training_entry)
                                with open(training_file, "w", encoding="utf-8") as f:
                                    json.dump(training_data, f, indent=2, ensure_ascii=False)
                                st.toast(f"✅ Saved to {training_file} for future training!")
                        with fb_col2:
                            if st.button("👎", key=f"thumbs_down_{msg_idx}", help="Bad response - remove from history"):
                                # Remove this Q&A pair from history
                                # Find and remove both the question and this response
                                if msg_idx > 0:
                                    st.session_state["qa_messages"].pop(msg_idx)  # Remove response
                                    if msg_idx - 1 >= 0 and st.session_state["qa_messages"][msg_idx - 1].get("role") == "user":
                                        st.session_state["qa_messages"].pop(msg_idx - 1)  # Remove question
                                else:
                                    st.session_state["qa_messages"].pop(msg_idx)
                                st.toast("🗑️ Removed bad response from history")
                                st.rerun()
                        with fb_col3:
                            if st.button("📋", key=f"copy_btn_{msg_idx}", help="Copy response"):
                                st.session_state[f"_copy_content_{msg_idx}"] = msg["content"]
                                st.toast("📋 Use Ctrl+C to copy from the text area below")
                        
                        # Show copy area if requested
                        if st.session_state.get(f"_copy_content_{msg_idx}"):
                            st.text_area("Copy this:", value=st.session_state[f"_copy_content_{msg_idx}"], height=100, key=f"copy_area_{msg_idx}")
                            if st.button("Done", key=f"copy_done_{msg_idx}"):
                                st.session_state.pop(f"_copy_content_{msg_idx}", None)
                                st.rerun()

                    # Render source links below assistant responses
                    sources = msg.get("sources")
                    if sources:
                        st.markdown("---")
                        st.markdown("**📎 Sources** — click to view the original post")
                        src_lines = []
                        for ref_label, title, url, platform in sources:
                            short_title = (title[:90] + "…") if len(title) > 90 else title
                            src_lines.append(f"**[{ref_label}]** [{short_title}]({url}) · {platform}")
                        st.markdown("\n\n".join(src_lines))

                    # Offer ad-hoc scrape when results are thin
                    if msg.get("_thin") and msg.get("_question"):
                        rel_count = msg.get("_relevant_count", 0)
                        st.markdown("---")
                        st.warning(
                            f"⚠️ Only **{rel_count} matching signals** found in the current dataset. "
                            f"Want me to **live-search the web** for more data on this topic?"
                        )
                        scrape_col1, scrape_col2 = st.columns([2, 3])
                        with scrape_col1:
                            if st.button("🔍 Scrape & Re-Analyze", key=f"adhoc_btn_{msg_idx}"):
                                st.session_state["_adhoc_scrape_pending"] = msg["_question"]
                                st.session_state["_adhoc_reask_question"] = msg["_question"]
                                st.rerun()
                        with scrape_col2:
                            custom_topic = st.text_input(
                                "Or refine the search topic:",
                                value=msg["_question"],
                                key=f"adhoc_topic_{msg_idx}",
                            )
                            if st.button("🔍 Scrape Custom Topic", key=f"adhoc_custom_btn_{msg_idx}"):
                                st.session_state["_adhoc_scrape_pending"] = custom_topic
                                st.session_state["_adhoc_reask_question"] = msg["_question"]
                                st.rerun()

            if st.button("🗑️ Clear chat", key="clear_qa"):
                st.session_state["qa_messages"] = []
                st.rerun()
# ─────────────────────────────────────────────
# 5 Tabs
# ─────────────────────────────────────────────
tabs = st.tabs([
    "📋 Strategy & Overview",
    "⚔️ Competitor Intel",
    "🎯 Customer Signals",
    "📰 Industry & Trends",
    "📦 Releases & Checklists",
])

# (Charts tab removed — content merged into Strategy & Overview)
# CHARTS_BLOCK_DELETED
# TAB 2: COMPETITOR INTEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[1]:
    st.markdown("What competitors are doing, what their customers complain about, and where eBay can win.")

    if not competitor_posts_raw:
        st.info("No competitor data available yet. Check back after the next data refresh.")
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
            # Subsidiaries view — structured like Competitor view
            all_subs = sorted(sub_posts_map.keys())
            selected_sub = st.selectbox("Subsidiary", ["All"] + all_subs, key="sub_select")
            show_subs = all_subs if selected_sub == "All" else [selected_sub]

            for sub_name in show_subs:
                posts = sub_posts_map.get(sub_name, [])
                if not posts:
                    continue

                # Classify posts same as competitors
                sub_complaints = []
                sub_praise = []
                sub_integration = []  # integration/ecosystem signals
                sub_discussion = []
                for p in posts:
                    text_lower = (p.get("text", "") + " " + p.get("title", "")).lower()
                    if any(w in text_lower for w in [
                        "problem", "issue", "broken", "terrible", "frustrated", "scam",
                        "complaint", "disappointed", "awful", "rip off", "warning",
                        "bad experience", "never again", "poor quality", "hate",
                    ]):
                        sub_complaints.append(p)
                    elif any(w in text_lower for w in [
                        "love", "amazing", "best", "great experience", "impressed",
                        "recommend", "better than", "so much better", "glad",
                    ]):
                        sub_praise.append(p)
                    elif any(w in text_lower for w in [
                        "ebay", "integration", "cross-list", "synergy", "ecosystem",
                        "combined", "partnership", "linked", "connected",
                    ]):
                        sub_integration.append(p)
                    elif (p.get("score", 0) or 0) >= 5:
                        sub_discussion.append(p)

                with st.container(border=True):
                    st.subheader(f"🏪 {sub_name}")
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    sc1.metric("Total Signals", len(posts))
                    sc2.metric("Complaints", len(sub_complaints), help="Pain points users have with this subsidiary")
                    sc3.metric("Praise", len(sub_praise), help="What users love — strengths to amplify")
                    sc4.metric("eBay Mentions", len(sub_integration), help="Posts that mention eBay alongside this subsidiary")

                    # AI Subsidiary Brief
                    sub_analysis_key = f"sub_analysis_{sub_name}"
                    if st.button(f"🧠 Generate AI Ecosystem Brief for {sub_name}", key=f"btn_{sub_analysis_key}"):
                        st.session_state[sub_analysis_key] = "__generating__"
                        st.rerun()
                    if st.session_state.get(sub_analysis_key) == "__generating__":
                        with st.spinner(f"Analyzing {len(posts)} signals for {sub_name}..."):
                            result = generate_competitor_analysis(
                                sub_name, sub_complaints, sub_praise,
                                sub_integration, sub_discussion, len(posts)
                            )
                        st.session_state[sub_analysis_key] = result
                        st.rerun()
                    if st.session_state.get(sub_analysis_key) and st.session_state[sub_analysis_key] != "__generating__":
                        with st.container(border=True):
                            st.markdown(st.session_state[sub_analysis_key])

                    # Complaints
                    if sub_complaints:
                        with st.expander(f"🚨 Pain Points ({len(sub_complaints)})", expanded=False):
                            for idx, post in enumerate(sorted(sub_complaints, key=lambda x: x.get("score", 0), reverse=True)[:8], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                score = post.get("score", 0)
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | r/{post.get('subreddit', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

                    # Praise
                    if sub_praise:
                        with st.expander(f"🟢 What Users Love ({len(sub_praise)})", expanded=False):
                            for idx, post in enumerate(sorted(sub_praise, key=lambda x: x.get("score", 0), reverse=True)[:8], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                st.markdown(f"**{idx}.** {title}")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

                    # eBay ecosystem mentions
                    if sub_integration:
                        with st.expander(f"🔗 eBay Ecosystem Mentions ({len(sub_integration)})", expanded=False):
                            for idx, post in enumerate(sorted(sub_integration, key=lambda x: x.get("score", 0), reverse=True)[:8], 1):
                                title = post.get("title", "")[:100] or post.get("text", "")[:100]
                                score = post.get("score", 0)
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:400]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")

                    # General discussion
                    if sub_discussion:
                        with st.expander(f"💬 Other Discussion ({len(sub_discussion)})", expanded=False):
                            for idx, post in enumerate(sorted(sub_discussion, key=lambda x: x.get("score", 0), reverse=True)[:6], 1):
                                title = post.get("title", "")[:80] or post.get("text", "")[:80]
                                score = post.get("score", 0)
                                st.markdown(f"**{idx}.** {title} (⬆️ {score})")
                                st.markdown(f"> {post.get('text', '')[:300]}")
                                url = post.get("url", "")
                                st.caption(f"{post.get('post_date', '')} | [Source]({url})" if url else post.get("post_date", ""))
                                st.markdown("---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: CUSTOMER SIGNALS — executive briefing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[2]:
    st.markdown("One-page executive view — scroll top-to-bottom for health, top issues, customer asks, and deep-dive explorer.")

    # ── Filters ──
    filter_fields = {"Topic": "taxonomy.topic", "Type": "taxonomy.type", "Sentiment": "brand_sentiment"}
    filters = render_floating_filters(normalized, filter_fields, key_prefix="ebay_voice")
    filtered = [i for i in normalized if match_multiselect_filters(i, filters, filter_fields)]
    time_range = filters.get("_time_range", "All Time")
    filtered = filter_by_time(filtered, time_range)

    selected_topics = filters.get("taxonomy.topic", [])
    if selected_topics and "All" not in selected_topics and "Price Guide" in selected_topics:
        filtered = [i for i in filtered if _is_true_price_guide_signal(i)]


    # ── Customer Signals Sub-tabs ──
    cs_tabs = st.tabs(["🔥 Issues & Health", "💡 Asks & Churn", "🤝 Partners & Explorer"])

    with cs_tabs[0]:
        # ═══════════════════════════════════════════════
        # HEALTH SNAPSHOT
        # ═══════════════════════════════════════════════
        f_neg = sum(1 for i in filtered if i.get("brand_sentiment") == "Negative")
        f_pos = sum(1 for i in filtered if i.get("brand_sentiment") == "Positive")
        f_complaints = sum(1 for i in filtered if _taxonomy_type(i) == "Complaint")
        f_requests = sum(1 for i in filtered if _taxonomy_type(i) == "Feature Request")
        f_churn = sum(1 for i in filtered if i.get("type_tag") == "Churn Signal")
        strengths = [i.get("signal_strength", 0) for i in filtered if i.get("signal_strength")]
        avg_strength = round(sum(strengths) / max(len(strengths), 1), 1) if strengths else 0

        h1, h2, h3, h4, h5, h6 = st.columns(6)
        h1.metric("Signals", len(filtered), help=f"of {total} total")
        neg_pct = round(f_neg / max(len(filtered), 1) * 100)
        h2.metric("Negative", f_neg, delta=f"{neg_pct}%", delta_color="inverse")
        h3.metric("Complaints", f_complaints)
        h4.metric("Churn Risks", f_churn, delta_color="inverse" if f_churn else "off")
        h5.metric("Feature Asks", f_requests)
        h6.metric("Avg Strength", f"{avg_strength}/100")

        topic_counts = defaultdict(int)
        for i in filtered:
            t = _taxonomy_topic(i)
            if t and t not in ("General", "Unknown"):
                topic_counts[t] += 1
        if topic_counts:
            top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            st.caption("**Top topics:** " + " · ".join([f"{k} ({v})" for k, v in top_topics]))

        st.markdown("---")

        # ═══════════════════════════════════════════════
        # 🔥 TOP ISSUES TO FIX
        # ═══════════════════════════════════════════════
        st.markdown("### 🔥 Top Issues to Fix")
        st.caption("Highest-impact platform problems from user reports — sorted by engagement × severity.")

        # ── Broken-windows classification (inlined) ──
        _BW_CATEGORIES = {
            "Returns & INAD Abuse": {
                "keywords": ["inad", "item not as described", "forced return", "return abuse", "partial refund",
                             "case opened", "money back guarantee", "buyer scam", "empty box",
                             "return request", "refund", "sided with buyer", "unfair return",
                             "buyer opened a case", "sent back wrong", "returned wrong item",
                             "buyer claims", "not received", "not as described"],
                "icon": "🔄", "owner": "Returns PM",
            },
            "Trust & Fraud": {
                "keywords": ["scam", "fraud", "shill bid", "fake listing", "counterfeit",
                             "fake card", "says it's fake", "it's fake", "not authentic",
                             "stolen", "replica", "knock off", "suspicious seller",
                             "scammer", "ripped off", "got scammed"],
                "icon": "🛡️", "owner": "Trust & Safety PM",
            },
            "Authentication & Grading": {
                "keywords": ["authenticity guarantee", "authentication", "misgrade",
                             "wrong grade", "fake grade", "grading error",
                             "grading issue", "grading problem", "grading complaint",
                             "psa error", "bgs error", "cgc error",
                             "grade came back", "grading service", "grading turnaround"],
                "icon": "🏅", "owner": "Authentication PM",
            },
            "Vault Bugs": {
                "keywords": ["psa vault", "ebay vault", "vault sell", "vault inventory", "vault withdraw",
                             "vault shipping", "vault delay", "vault error", "vault listing",
                             "stuck in vault", "vault payout", "vault card"],
                "icon": "🏦", "owner": "Vault PM",
            },
            "Fee & Pricing Confusion": {
                "keywords": ["fee", "final value", "insertion fee", "take rate", "13.25%",
                             "13%", "12.9%", "ebay takes", "fee structure", "hidden fee",
                             "commission", "overcharged", "too expensive to sell"],
                "icon": "💸", "owner": "Monetization PM",
            },
            "Shipping & Label Issues": {
                "keywords": ["shipping label", "tracking", "lost in mail", "lost package",
                             "damaged in transit", "standard envelope", "can't print label",
                             "wrong weight", "shipping estimate", "shipping damage",
                             "arrived damaged", "crushed", "print label"],
                "icon": "📦", "owner": "Shipping PM",
            },
            "Payment & Payout Issues": {
                "keywords": ["payment hold", "payout", "funds held", "managed payments", "hold my money",
                             "can't get paid", "money held", "release my funds", "payment processing",
                             "payment delay", "stripe verification", "stopped payment"],
                "icon": "💳", "owner": "Payments PM",
            },
            "Seller Protection Gaps": {
                "keywords": ["seller protection", "always side with buyer", "sided with buyer",
                             "no recourse", "lost case", "hate selling", "done with ebay",
                             "leaving ebay", "doesn't care about sellers", "unfair to sellers",
                             "seller cancelled", "cancelled my order"],
                "icon": "🛑", "owner": "Seller Experience PM",
            },
            "App & UX Bugs": {
                "keywords": ["ebay app", "ebay website", "app glitch", "app bug", "app crash",
                             "ebay not working", "ebay won't load", "error message",
                             "seller hub bug", "seller hub glitch", "seller hub broken",
                             "white screen", "blank page", "ebay crash",
                             "ebay glitch", "ebay bug", "app won't", "app keeps",
                             "app freezes", "app update broke"],
                "icon": "🐛", "owner": "App/UX PM",
            },
            "Account & Policy Enforcement": {
                "keywords": ["account suspended", "account restricted", "banned",
                             "locked out", "policy violation", "vero",
                             "listing removed", "flagged", "delisted", "taken down"],
                "icon": "🔒", "owner": "Trust & Safety PM",
            },
            "Search & Listing Visibility": {
                "keywords": ["search broken", "can't find my listing", "no views",
                             "algorithm", "best match", "search ranking",
                             "not showing up", "buried", "no impressions", "no traffic", "cassini"],
                "icon": "🔍", "owner": "Search PM",
            },
            "Promoted Listings Friction": {
                "keywords": ["promoted listing", "promoted standard", "promoted advanced",
                             "pay to play", "ad rate", "forced to promote", "ad spend",
                             "promoted listings fee", "visibility tax"],
                "icon": "📢", "owner": "Ads PM",
            },
        }

        _BW_PLATFORM_NAMES = ["ebay", "e-bay", "goldin", "tcgplayer", "tcg player", "comc"]
        _BW_EBAY_SUBS = ["ebay", "flipping", "ebaysellers", "ebayselleradvice"]
        _BW_FEATURE_KW = [
            "seller hub", "promoted listing", "vault", "authenticity guarantee",
            "standard envelope", "managed payments", "global shipping",
            "shipping label", "inad", "item not as described", "money back guarantee",
            "payment hold", "payout", "final value fee", "insertion fee",
            "promoted standard", "promoted advanced", "best match",
            "psa vault", "vault inventory",
        ]
        _BW_EXCLUDE = [
            "stole my", "nephew", "my cards were stolen", "house fire",
            "fake money", "porch pick up", "hands free controller", "nintendo",
            "dvd of an old film", "mercari", "card show drama",
            "gameshire", "$100b endgame", "the whale, the trio",
            "bitcoin treasury", "diamond hands", "short squeeze", "moass",
            "to the moon", "hedge fund", "warrants to blockchain",
            "official sales/trade/breaks", "leave a comment here in this thread with your sales",
            "iron maiden", "secret lair", "new to mtg", "new player",
            "dev kit", "ps vita", "playstation",
            "my daughter swears", "help! my daughter",
            "catalogued my grandmother", "my inheritance",
            "stopped ordering from amazon", "what website or app do you use instead",
            "help me sell my storage unit", "jet engine",
            "would you block this buyer? i already can smell",
            "i only brought 300",
            "seed vault extract", "arc raiders", "stella montis",
            "psa if you think you might want to play survival",
            "make a placeholder vault", "placeholder vault",
            "rewards in experimental", "play survival in the future",
            "survival vault", "public service announcement",
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
        _BW_EXCLUDE_SUBS = [
            "superstonk", "gme_meltdown", "amcstock",
            "bitcoin", "stocks", "investing",
            "gamestop", "gmejungle", "fwfbthinktank", "gme",
            "kleinanzeigen_betrug", "arcraiders", "nostupidquestions",
        ]
        _BW_POSITIVE = [
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
            if sub_lower in _BW_EXCLUDE_SUBS:
                return False
            if any(ex in text_lower for ex in _BW_EXCLUDE):
                return False
            if any(pos in text_lower for pos in _BW_POSITIVE):
                return False
            return (any(n in text_lower for n in _BW_PLATFORM_NAMES)
                    or sub_lower in _BW_EBAY_SUBS
                    or any(kw in text_lower for kw in _BW_FEATURE_KW))

        bw_candidates = [
            i for i in filtered
            if (_taxonomy_type(i) in ("Complaint", "Bug Report") or i.get("brand_sentiment") == "Negative")
            and _is_bw_actionable(i)
        ]
        bw_buckets = {cat: [] for cat in _BW_CATEGORIES}
        for insight in bw_candidates:
            text_lower = (insight.get("text", "") + " " + insight.get("title", "")).lower()
            for cat, config in _BW_CATEGORIES.items():
                if any(kw in text_lower for kw in config["keywords"]):
                    bw_buckets[cat].append(insight)
                    break
        sorted_cats = sorted(_BW_CATEGORIES.items(), key=lambda x: len(bw_buckets[x[0]]), reverse=True)
        active_cats = [(cat, config) for cat, config in sorted_cats if bw_buckets[cat]]
        total_bw = sum(len(bw_buckets[cat]) for cat, _ in active_cats)

        # Flatten top issues across all categories, sorted by score
        all_bw = []
        for cat in bw_buckets:
            for item in bw_buckets[cat]:
                item_copy = dict(item)
                item_copy["_bw_cat"] = cat
                item_copy["_bw_icon"] = _BW_CATEGORIES[cat]["icon"]
                item_copy["_bw_owner"] = _BW_CATEGORIES[cat]["owner"]
                all_bw.append(item_copy)
        all_bw.sort(key=lambda x: (x.get("signal_strength", 0), x.get("score", 0)), reverse=True)

        if not all_bw:
            st.info("No actionable platform issues in the current view. Try adjusting your filters.")
        else:
            bw_m1, bw_m2, bw_m3 = st.columns(3)
            bw_m1.metric("Actionable Issues", total_bw)
            bw_m2.metric("Problem Areas", len(active_cats))
            top_cat_name = active_cats[0][0] if active_cats else "None"
            bw_m3.metric("Hottest Area", top_cat_name, delta=f"{len(bw_buckets.get(top_cat_name, []))} signals", delta_color="inverse")

            for idx, item in enumerate(all_bw[:8], 1):
                score = item.get("score", 0)
                sev = "🔴" if score >= 50 else ("🟡" if score >= 10 else "⚪")
                text = item.get("text", "")[:250]
                url = item.get("url", "")
                link = f" · [Source]({url})" if url else ""
                st.markdown(f"**{idx}.** {sev} {item['_bw_icon']} {text}{'...' if len(item.get('text', '')) > 250 else ''}")
                src_label = item.get('source', '')
                src_part = f" · {src_label}" if src_label else ""
                st.caption(f"⬆️ {score} · {item['_bw_cat']} · Owner: {item['_bw_owner']}{src_part} · {item.get('post_date', '')}{link}")

            # AI Broken Windows Executive Brief
            def _generate_bw_brief_inline(categories, buckets):
                try:
                    from components.ai_suggester import _chat, MODEL_MAIN
                except ImportError:
                    return None
                digest = ""
                for cat, config in categories[:6]:
                    items = buckets[cat]
                    if not items:
                        continue
                    digest += f"\n## {cat} ({len(items)} signals, Owner: {config['owner']})\n"
                    for p in sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:5]:
                        text = p.get("text", "")[:150].replace("\n", " ")
                        digest += f"- [{p.get('score',0)} pts] {text}\n"
                prompt = f"""You are a Senior Product Manager at eBay writing a Broken Windows executive brief.

    {digest}

    Write a crisp brief:

    ### Top 3 Priorities to Fix Now

    **1. [Issue]** (Owner: [team])
    - **What's broken:** (1-2 sentences, name exact flow/feature/policy)
    - **User impact:** (1 sentence)
    - **Suggested fix:** (1 concrete action)

    **2. [Issue]** (Owner: [team])
    - **What's broken:** / **User impact:** / **Suggested fix:**

    **3. [Issue]** (Owner: [team])
    - **What's broken:** / **User impact:** / **Suggested fix:**

    ### Emerging Risks
    - (1-2 bullets about patterns that could become bigger)

    Be extremely specific. Name exact features and flows."""
                try:
                    return _chat(MODEL_MAIN, "Write sharp, specific product briefs.", prompt, max_completion_tokens=800, temperature=0.3)
                except Exception:
                    return None

            bw_brief_key = "bw_executive_brief"
            if st.button("🧠 Generate AI Executive Brief", key="btn_bw_brief"):
                st.session_state[bw_brief_key] = "__generating__"
                st.rerun()
            if st.session_state.get(bw_brief_key) == "__generating__":
                with st.spinner("Analyzing top issues across all categories..."):
                    result = _generate_bw_brief_inline(active_cats, bw_buckets)
                st.session_state[bw_brief_key] = result or "AI analysis unavailable."
                st.rerun()
            if st.session_state.get(bw_brief_key) and st.session_state[bw_brief_key] != "__generating__":
                with st.container(border=True):
                    st.markdown(st.session_state[bw_brief_key])

        st.markdown("---")

        # ═══════════════════════════════════════════════
        # 📊 PROBLEM BREAKDOWN
        # ═══════════════════════════════════════════════
        if active_cats:
            st.markdown("### 📊 Problem Breakdown by Area")
            st.caption("Expand any category for details and per-area AI analysis.")

            for cat, config in active_cats:
                items = bw_buckets[cat]
                total_eng = sum(i.get("score", 0) for i in items)
                sev = "🔴" if len(items) >= 15 else ("🟡" if len(items) >= 5 else "🟢")

                with st.expander(f"{sev} {config['icon']} **{cat}** — {len(items)} issues · ⬆️ {total_eng} · Owner: {config['owner']}"):
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
    1. What specific things are broken or frustrating
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

            st.markdown("---")


    with cs_tabs[1]:
        # ═══════════════════════════════════════════════
        # 🚨 CHURN & RETENTION RISKS
        # ═══════════════════════════════════════════════
        churn_signals = [i for i in filtered if i.get("type_tag") == "Churn Signal"]
        if churn_signals:
            st.markdown("### 🚨 Churn & Retention Risks")

            # Destination extraction — where are they going?
            _CHURN_DESTINATIONS = {
                "Whatnot": ["whatnot", "moved to whatnot", "switching to whatnot"],
                "Heritage": ["heritage", "heritage auctions"],
                "Fanatics": ["fanatics", "fanatics collect"],
                "TCGPlayer": ["tcgplayer", "tcg player"],
                "Mercari": ["mercari"],
                "Facebook": ["facebook marketplace", "facebook groups", "fb marketplace"],
                "COMC": ["comc"],
                "Alt": ["alt.xyz", "alt marketplace"],
                "Courtyard": ["courtyard"],
                "Arena Club": ["arena club"],
            }
            _dest_counts = defaultdict(int)
            for cs in churn_signals:
                _cs_text = (cs.get("text", "") + " " + cs.get("title", "")).lower()
                for _dest, _kws in _CHURN_DESTINATIONS.items():
                    if any(kw in _cs_text for kw in _kws):
                        _dest_counts[_dest] += 1
            _dest_summary = ""
            if _dest_counts:
                _sorted_dests = sorted(_dest_counts.items(), key=lambda x: -x[1])[:5]
                _dest_summary = " · Where they're going: " + ", ".join(f"**{d}** ({c})" for d, c in _sorted_dests)

            st.caption(f"{len(churn_signals)} signals where users mention leaving eBay or switching.{_dest_summary}")
            for idx, post in enumerate(sorted(churn_signals, key=lambda x: x.get("score", 0), reverse=True)[:8], 1):
                text = post.get("text", "")[:220]
                score = post.get("score", 0)
                url = post.get("url", "")
                link = f" · [Source]({url})" if url else ""
                st.markdown(f"**{idx}.** 🚨 {text}{'...' if len(post.get('text', '')) > 220 else ''}")
                st.caption(f"⬆️ {score} · {post.get('source', '')} · {post.get('post_date', '')}{link}")
            st.markdown("---")

        # ═══════════════════════════════════════════════
        # 💡 WHAT CUSTOMERS ARE ASKING FOR
        # ═══════════════════════════════════════════════
        st.markdown("### 💡 What Customers Are Asking For")
        st.caption("Grouped by product area — each section shows the problem users face and what they want eBay to build or fix.")

        _REQUEST_HINTS = [
            "should", "wish", "need", "please add", "feature", "why can't", "allow", "option to", "improve",
        ]
        request_posts = [
            i for i in filtered
            if _taxonomy_type(i) == "Feature Request"
            or any(h in (i.get("text", "") + " " + i.get("title", "")).lower() for h in _REQUEST_HINTS)
        ]

        if not request_posts:
            st.info("No feature requests in current filter view.")
        else:
            # Group by topic
            _req_by_topic = defaultdict(list)
            for i in request_posts:
                _t = _taxonomy_topic(i)
                if _t and _t not in ("General", "Unknown"):
                    _req_by_topic[_t].append(i)
            # Sort topics by total engagement
            _sorted_topics = sorted(
                _req_by_topic.items(),
                key=lambda x: sum(p.get("score", 0) for p in x[1]),
                reverse=True,
            )

            _rq1, _rq2 = st.columns([1, 3])
            _rq1.metric("Request Signals", len(request_posts))
            with _rq2:
                st.caption(f"Across **{len(_sorted_topics)} product areas** — expand any area to see what users want")

            for _rank, (_topic, _reqs) in enumerate(_sorted_topics[:8], 1):
                _total_eng = sum(r.get("score", 0) for r in _reqs)
                _top_reqs = sorted(_reqs, key=lambda x: x.get("score", 0), reverse=True)

                with st.expander(f"**{_rank}. {_topic}** — {len(_reqs)} requests · ⬆️ {_total_eng} engagement"):
                    # AI synthesis button
                    _synth_key = f"req_synth_{_topic}"
                    if st.button("🧠 AI: Synthesize Problem → Solution", key=f"btn_{_synth_key}"):
                        st.session_state[_synth_key] = "__generating__"
                        st.rerun()
                    if st.session_state.get(_synth_key) == "__generating__":
                        _digest = "\n".join(
                            f"- [{r.get('source', '')}] (⬆️{r.get('score', 0)}) {r.get('text', '')[:200]}"
                            for r in _top_reqs[:10]
                        )
                        _synth_prompt = f"""Analyze these {len(_reqs)} user requests about "{_topic}" on eBay. Write a structured brief:

**🔴 The Problem:** (2-3 sentences. What specific pain point or gap are users experiencing? Be concrete — name features, flows, or policies.)

**💡 What They Want:** (2-3 bullet points. Each bullet = one specific product change or new feature users are asking for. Start each with a verb: "Add...", "Fix...", "Allow...", "Show...".)

**📊 Evidence:** (2-3 verbatim user quotes that best illustrate the ask)

**🎯 Suggested Jira Epic:** (One-line epic title a PM could use, e.g. "Improve vault withdrawal flow for high-value cards")

Signals:
{_digest}"""
                        with st.spinner(f"Synthesizing {_topic} requests..."):
                            try:
                                from components.ai_suggester import _chat, MODEL_MAIN
                                _result = _chat(MODEL_MAIN, "Write specific, actionable product briefs. Always cite user quotes.", _synth_prompt, max_completion_tokens=500, temperature=0.3)
                            except Exception:
                                _result = None
                        st.session_state[_synth_key] = _result or "AI synthesis unavailable."
                        st.rerun()
                    if st.session_state.get(_synth_key) and st.session_state[_synth_key] != "__generating__":
                        with st.container(border=True):
                            st.markdown(st.session_state[_synth_key])

                    # Top requests as evidence
                    st.markdown("**Top requests:**")
                    for _qi, _req in enumerate(_top_reqs[:4], 1):
                        _txt = (_req.get("text", "") or _req.get("title", ""))[:220]
                        _sc = _req.get("score", 0)
                        _url = _req.get("url", "")
                        _lnk = f" · [Source]({_url})" if _url else ""
                        st.markdown(f"**{_qi}.** {_txt}{'...' if len(_req.get('text', '') or '') > 220 else ''}")
                        st.caption(f"⬆️ {_sc} · {_req.get('source', '')} · {_req.get('post_date', '')}{_lnk}")

        st.markdown("---")


    with cs_tabs[2]:
        # ═══════════════════════════════════════════════
        # 🤝 PARTNER HEALTH
        # ═══════════════════════════════════════════════
        STRATEGIC_PARTNERS = {
            "PSA Vault": ["psa vault", "vault storage", "vault sell", "vault auction", "vault withdraw"],
            "PSA Grading": ["psa grading", "psa grade", "psa turnaround", "psa submission", "psa 10", "psa 9"],
            "PSA Consignment": ["psa consignment", "psa consign", "consignment psa"],
            "PSA Offers": ["psa offer", "psa buyback", "psa buy back", "psa instant"],
            "Card Ladder": ["card ladder", "cardladder", "scan to price", "card value tool", "cardladder.com"],
            "ComC": ["comc", "check out my cards", "comc consignment", "comc selling"],
        }
        partner_counts = {}
        partner_sentiment = {}
        for pname, kws in STRATEGIC_PARTNERS.items():
            matching = [i for i in filtered if any(kw in (i.get("text", "") + " " + i.get("title", "")).lower() for kw in kws)]
            cnt = len(matching)
            if cnt > 0:
                partner_counts[pname] = cnt
                neg = sum(1 for i in matching if i.get("brand_sentiment") == "Negative")
                neg_pct = round(neg / max(cnt, 1) * 100)
                partner_sentiment[pname] = "🔴" if neg_pct > 40 else ("🟡" if neg_pct > 15 else "🟢")
        if partner_counts:
            st.markdown("### 🤝 Partner Health")
            st.caption("Signal volume and sentiment for strategic partners. 🟢 = mostly positive, 🟡 = mixed, 🔴 = mostly negative.")
            pcols = st.columns(min(len(partner_counts), 5))
            for idx, (pname, cnt) in enumerate(sorted(partner_counts.items(), key=lambda x: -x[1])):
                health = partner_sentiment.get(pname, "⚪")
                pcols[idx % len(pcols)].metric(f"{health} {pname}", cnt)
            st.markdown("---")

        # ═══════════════════════════════════════════════
        # 📋 DEEP DIVE EXPLORER
        # ═══════════════════════════════════════════════
        st.markdown("### 📋 Deep Dive Explorer")
        st.caption(f"Browse all **{len(filtered)} signals** with full AI analysis, suggested actions, and document generation.")
        if st.toggle(f"Open Signal Explorer ({len(filtered)} signals)", value=False, key="cs_explorer_toggle"):
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

    # Podcasts (Sports Card Nonsense, Hobby Wire, Card Shop Life, etc.)
    for p in podcast_raw:
        p["_industry_source"] = "Podcast"
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

    # New sources — only industry-level content (blogs, analysis, PSA Forums)
    # Trustpilot, App Reviews, and Seller Community are customer-level signals
    _INDUSTRY_LEVEL_SOURCES = {"Goldin Blog", "Heritage Blog", "Card Ladder", "Industry Analysis", "PSA Forums"}
    _CUSTOMER_REVIEW_SOURCES = {"Trustpilot:eBay", "Trustpilot:Goldin", "Trustpilot:TCGPlayer",
                                 "Trustpilot:Whatnot", "Trustpilot:Heritage", "App Reviews", "Seller Community"}
    _customer_review_posts = []
    for p in new_sources_raw:
        src = p.get("source", "New Source")
        if src in _INDUSTRY_LEVEL_SOURCES:
            p["_industry_source"] = src
            industry_posts.append(p)
        elif src in _CUSTOMER_REVIEW_SOURCES:
            p["_industry_source"] = src
            _customer_review_posts.append(p)

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
        st.info("No industry data available yet. Check back after the next data refresh.")
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
                elif src == "Podcast":
                    base_score = 110
                elif src in ("YouTube", "YouTube (transcript)"):
                    base_score = 90
                elif src in ("Blowout Forums", "Net54 Baseball", "Alt.xyz Blog"):
                    base_score = 70
                elif src in ("Goldin Blog", "Heritage Blog", "Card Ladder", "Industry Analysis"):
                    base_score = 100
                elif src in ("PSA Forums", "Seller Community"):
                    base_score = 60
                elif src.startswith("Trustpilot"):
                    base_score = 50
                elif src == "App Reviews":
                    base_score = 40
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
                "Podcast": "🎙️",
                "Trustpilot:eBay": "⭐", "Trustpilot:Goldin": "⭐",
                "Trustpilot:TCGPlayer": "⭐", "Trustpilot:Whatnot": "⭐",
                "Trustpilot:Heritage": "⭐",
                "Goldin Blog": "📝", "Heritage Blog": "📝",
                "Card Ladder": "📊", "PSA Forums": "🔐",
                "App Reviews": "📱", "Industry Analysis": "📈",
                "Seller Community": "🛒",
            }
            icon = source_icons.get(source_label, "📄")
            sub_label = f"r/{sub} · " if sub else ""
            link = f" · [Link]({url})" if url else ""
            age_days = _days_old(post)
            age_label = f" · {age_days}d ago" if age_days < 9999 else ""
            st.markdown(f"**{rank}.** {icon} **{title}**")
            st.caption(f"⬆️ {score} pts · {sub_label}{source_label} · {date}{age_label}{link}")

        # ── Industry News & Podcasts ──
        st.markdown("### 📰 Industry News & Podcasts")
        st.caption("Latest from Cllct, Beckett, Cardlines, Sports Card Nonsense, and other industry sources — curated for your strategy team.")

        # Gather news + podcast posts, sorted by date
        _news_sources = {"News", "Cllct", "Podcast", "Alt.xyz Blog", "Blowout Forums", "Net54 Baseball",
                         "Goldin Blog", "Heritage Blog", "Card Ladder", "Industry Analysis"}
        news_podcast_feed = sorted(
            [p for p in industry_posts if p.get("_industry_source") in _news_sources],
            key=lambda x: x.get("post_date", ""),
            reverse=True,
        )

        if not news_podcast_feed:
            st.info("No industry news or podcast data available yet.")
        else:
            _np_icons = {"News": "📰", "Cllct": "🗞️", "Podcast": "🎙️", "Alt.xyz Blog": "📝", "Blowout Forums": "🗣️", "Net54 Baseball": "⚾",
                         "Goldin Blog": "📝", "Heritage Blog": "📝", "Card Ladder": "📊", "Industry Analysis": "📈"}
            for idx, np_post in enumerate(news_podcast_feed[:15], 1):
                np_src = np_post.get("_industry_source", "")
                np_icon = _np_icons.get(np_src, "📄")
                np_title = np_post.get("title", "")[:130] or np_post.get("text", "")[:130]
                np_date = np_post.get("post_date", "")
                np_url = np_post.get("url", "")
                np_podcast = np_post.get("podcast_name", "")
                np_link = f" · [Read / Listen ↗]({np_url})" if np_url else ""
                np_show = f" · {np_podcast}" if np_podcast and np_podcast not in np_title else ""
                st.markdown(f"**{idx}.** {np_icon} {np_title}")
                st.caption(f"{np_src}{np_show} · {np_date}{np_link}")

        st.markdown("---")

        # ── eBay Price Guide Spotlight ──
        st.markdown("### 🧭 eBay Price Guide Signals")
        st.caption("User sentiment on eBay's Price Guide — the market's most comprehensive pricing tool, powered by eBay's transaction data. Card Ladder and PSA receive this data to build their indexes.")

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

        # ── Customer Reviews Spotlight ──
        if _customer_review_posts:
            st.markdown("### ⭐ Customer Reviews Spotlight")
            st.caption("Trustpilot reviews, app store feedback, and seller community signals across eBay and competitors.")

            # Group by source and show sentiment
            from collections import Counter as _CRCounter
            _cr_by_src = defaultdict(list)
            for p in _customer_review_posts:
                _cr_by_src[p.get("source", "Unknown")].append(p)
            _cr_sorted = sorted(_cr_by_src.items(), key=lambda x: -len(x[1]))

            _cr_cols = st.columns(min(len(_cr_sorted), 4))
            for ci, (cr_src, cr_posts) in enumerate(_cr_sorted):
                cr_neg = sum(1 for p in cr_posts if p.get("brand_sentiment") == "Negative")
                cr_neg_pct = round(cr_neg / max(len(cr_posts), 1) * 100)
                cr_health = "🔴" if cr_neg_pct > 40 else ("🟡" if cr_neg_pct > 15 else "🟢")
                _cr_cols[ci % len(_cr_cols)].metric(f"{cr_health} {cr_src}", f"{len(cr_posts)} signals")

            # Show top reviews sorted by engagement
            _cr_all = sorted(_customer_review_posts, key=lambda x: (x.get("score", 0), x.get("post_date", "")), reverse=True)
            for ci, cr_post in enumerate(_cr_all[:8], 1):
                cr_title = cr_post.get("title", "")[:120] or cr_post.get("text", "")[:120]
                cr_src = cr_post.get("source", "")
                cr_sent = cr_post.get("brand_sentiment", "Neutral")
                cr_score = cr_post.get("score", 0)
                cr_date = cr_post.get("post_date", "")
                cr_url = cr_post.get("url", "")
                cr_link = f" · [Link]({cr_url})" if cr_url else ""
                _sent_icon = "🔴" if cr_sent == "Negative" else ("🟢" if cr_sent == "Positive" else "⚪")
                st.markdown(f"**{ci}.** {_sent_icon} {cr_title}")
                st.caption(f"{cr_src} · {cr_sent} · ⬆️ {cr_score} · {cr_date}{cr_link}")

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
                "Cllct": "🗞️", "Podcast": "🎙️",
                "Trustpilot:eBay": "⭐", "Trustpilot:Goldin": "⭐",
                "Trustpilot:TCGPlayer": "⭐", "Trustpilot:Whatnot": "⭐",
                "Trustpilot:Heritage": "⭐",
                "Goldin Blog": "📝", "Heritage Blog": "📝",
                "Card Ladder": "📊", "PSA Forums": "🔐",
                "App Reviews": "📱", "Industry Analysis": "📈",
                "Seller Community": "🛒",
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
        st.info("No release or checklist data available yet. Check back after the next data refresh.")
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
# TAB 1: STRATEGY & OVERVIEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[0]:
    # ── Onboarding (collapsed by default for returning users) ──
    with st.expander("💡 New here? How to use SignalSynth", expanded=False):
        st.markdown("""
**SignalSynth** is an AI-powered intelligence engine built for eBay Collectibles & Trading Cards leadership. It continuously scrapes, enriches, and synthesizes community signals into executive-ready insights — so you don't have to manually read thousands of posts to know what's happening.

---

#### 🤖 Start with Ask AI (above the tabs)
The fastest way to get answers. Type any question and get a strategic, source-cited response grounded in real data. Examples:
- *"What are the top complaints about the PSA Vault?"*
- *"How does Whatnot threaten eBay in live breaks?"*
- *"What do sellers want most from eBay right now?"*

If your question has thin results, SignalSynth will offer to **live-search the web** for that topic, pull in fresh signals, and re-analyze — so the system learns your interests over time.

---

#### 📡 Where the data comes from
SignalSynth pulls from **42 sources** across the collectibles ecosystem:

| Source | What it captures |
|--------|------------------|
| **Reddit** | r/baseballcards, r/sportscards, r/eBay, r/pokemontcg, r/footballcards, r/funkopop, r/coins + 35 more subs |
| **Twitter / X** | Hobby influencers, eBay mentions, competitor chatter |
| **YouTube** | Jabs Family, Sports Card Investor, Stacking Slabs, CardShopLive, Gary Vee, Goldin |
| **eBay Forums** | Seller & buyer discussions from eBay Community (real-time) |
| **Bluesky** | Emerging hobby community signals |
| **Trustpilot** | Customer reviews for eBay, Goldin, TCGPlayer, Whatnot, Heritage Auctions |
| **Cllct** | Industry news from Cllct.com (Sports Cards, Auctions, Autographs, Memorabilia) |
| **News RSS** | Beckett, Cardlines, Cardboard Connection, Dave and Adams, Sports Collectors Daily, PSA Blog, Blowout Buzz, Just Collect Blog |
| **Podcasts** | Sports Cards Nonsense, Sports Card Investor, Stacking Slabs, Hobby News Daily, The Pull-Tab Podcast, Collector Nation |
| **Forums & Blogs** | Blowout Forums, Net54, Bench Trading, Alt.xyz, COMC, Whatnot, Fanatics Collect, TCDB |
| **Goldin Blog & Heritage Blog** | Official blog posts from eBay subsidiaries and key competitors |
| **Card Ladder** | Price guide partner blog and market analysis |
| **PSA Forums** | Collectors Universe forums — grading, vault, consignment discussions |
| **App Reviews** | App store review discussions about eBay and competitor mobile experiences |
| **Industry Analysis** | Analyst reports and market commentary on the collectibles industry |
| **Seller Communities** | Seller forums and community discussions about platform experiences |
| **Competitors** | Whatnot, Fanatics Collect, Fanatics Live, Heritage Auctions, Alt, Goldin, TCGPlayer, Beckett, PSA Consignment |

Every post is enriched with **sentiment, topic, persona, churn risk, and signal strength** scoring.

---

#### 🗂️ Tab guide
- **📋 Strategy & Overview** (you're here) — Executive pulse, signal health, and AI-clustered strategic themes. Drill into any theme, then generate **PRDs, BRDs, PRFAQs, or Jira tickets** with one click.
- **⚔️ Competitor Intel** — What Whatnot, Fanatics, Heritage, and others are doing. Complaints (conquest opportunities), praise (competitive threats), policy changes, and platform comparisons.
- **🎯 Customer Signals** — Deep-dive: health snapshot → top issues → problem breakdown → churn risks → customer asks → partner health → signal explorer.
- **📰 Industry & Trends** — Top industry news, podcast episodes, viral posts, YouTube commentary, Price Guide signals, and a full filterable feed.
- **📦 Releases & Checklists** — Upcoming product releases and published checklists from Topps, Panini, Bowman, Upper Deck, and more.

---

#### 💡 Tips
- **Filters matter** — use topic, sentiment, and time filters on the Customer Signals tab to focus on what you care about.
- **AI buttons everywhere** — look for 🧠 buttons to generate executive briefs, competitive analyses, and per-category summaries.
- **Source links** — every insight links back to the original post so you can verify context.
        """)

    # ── Executive Pulse ──
    st.markdown("### 📊 Executive Pulse")
    # Freshness timestamp
    _refresh_ts = _pipeline_meta.get("generated_at", "")
    if _refresh_ts:
        try:
            _refresh_dt = datetime.fromisoformat(_refresh_ts)
            _ago = datetime.now() - _refresh_dt
            _hours_ago = round(_ago.total_seconds() / 3600, 1)
            if _hours_ago < 1:
                _freshness = f"{round(_ago.total_seconds() / 60)}m ago"
            elif _hours_ago < 24:
                _freshness = f"{_hours_ago:.0f}h ago"
            else:
                _freshness = f"{_hours_ago / 24:.0f}d ago"
            st.caption(f"Last data refresh: **{_freshness}** · {_refresh_dt.strftime('%b %d, %Y %I:%M %p')}")
        except Exception:
            st.caption(f"Last data refresh: {_refresh_ts[:16]}")

    from collections import Counter as _PulseCounter
    # Split signals into recent (14d) vs older for trend comparison
    _14d_ago = (datetime.now() - __import__('datetime').timedelta(days=14)).strftime("%Y-%m-%d")
    _recent = [i for i in normalized if (i.get("post_date", "") or "") >= _14d_ago]
    _older = [i for i in normalized if (i.get("post_date", "") or "") < _14d_ago]

    _pulse_neg = sum(1 for i in normalized if i.get("brand_sentiment") in ("Negative", "Complaint"))
    _pulse_pos = sum(1 for i in normalized if i.get("brand_sentiment") in ("Positive", "Praise"))
    _pulse_complaints = sum(1 for i in normalized if _taxonomy_type(i) == "Complaint")
    _pulse_churn = sum(1 for i in normalized if i.get("type_tag") == "Churn Signal")
    _pulse_requests = sum(1 for i in normalized if _taxonomy_type(i) == "Feature Request")

    # Recent-period counts for delta
    _recent_neg = sum(1 for i in _recent if i.get("brand_sentiment") in ("Negative", "Complaint"))
    _recent_complaints = sum(1 for i in _recent if _taxonomy_type(i) == "Complaint")
    _recent_churn = sum(1 for i in _recent if i.get("type_tag") == "Churn Signal")
    _recent_requests = sum(1 for i in _recent if _taxonomy_type(i) == "Feature Request")
    _recent_pos = sum(1 for i in _recent if i.get("brand_sentiment") in ("Positive", "Praise"))

    _neg_pct = round(_pulse_neg / max(total, 1) * 100)

    _ep1, _ep2, _ep3, _ep4, _ep5 = st.columns(5)
    _ep1.metric("Negative", _pulse_neg, delta=f"{_recent_neg} in last 14d", delta_color="inverse" if _recent_neg else "off")
    _ep2.metric("Complaints", _pulse_complaints, delta=f"{_recent_complaints} recent", delta_color="inverse" if _recent_complaints else "off")
    _ep3.metric("Churn Risks", _pulse_churn, delta=f"{_recent_churn} recent", delta_color="inverse" if _recent_churn else "off")
    _ep4.metric("Feature Asks", _pulse_requests, delta=f"{_recent_requests} recent", delta_color="off")
    _ep5.metric("Positive", _pulse_pos, delta=f"{_recent_pos} recent", delta_color="off")

    # ── Trend Alerts (from trend_detector) ──
    if _trend_alerts and _trend_alerts.get("alerts"):
        _alerts = _trend_alerts["alerts"]
        _high_alerts = [a for a in _alerts if a.get("severity") == "high"]
        _med_alerts = [a for a in _alerts if a.get("severity") == "medium"]
        _absences = _trend_alerts.get("absences", [])

        with st.expander(f"📈 Trend Alerts ({len(_high_alerts)} high, {len(_med_alerts)} medium)", expanded=bool(_high_alerts)):
            if _high_alerts:
                st.markdown("#### 🔴 High-Severity Alerts")
                for a in _high_alerts[:5]:
                    _icon = {"volume_spike": "📈", "sentiment_shift": "😤", "emerging": "🆕", "declining": "📉"}.get(a["alert_type"], "⚠️")
                    st.markdown(f"{_icon} **{a['message']}** (confidence: {a['confidence']:.0%})")
            if _med_alerts:
                st.markdown("#### 🟡 Medium-Severity Alerts")
                for a in _med_alerts[:5]:
                    _icon = {"volume_spike": "📈", "sentiment_shift": "😤", "emerging": "🆕", "declining": "📉"}.get(a["alert_type"], "⚠️")
                    st.markdown(f"{_icon} {a['message']}")
            if _absences:
                st.markdown("#### 🔇 Topics Gone Silent")
                for a in _absences[:3]:
                    st.markdown(f"🔇 {a['message']}")
                    st.caption(a.get("hypothesis", ""))
            _meta = _trend_alerts.get("metadata", {})
            st.caption(f"Analysis: {_meta.get('periods_analyzed', '?')} periods × {_meta.get('window_days', '?')}-day windows, {_meta.get('topics_tracked', '?')} topics tracked")

    # Signal health breakdown by topic
    _topic_counts = _PulseCounter(_taxonomy_topic(i) for i in normalized)
    _topic_counts.pop("General", None)
    _topic_counts.pop("Unknown", None)
    if _topic_counts:
        st.markdown("#### Signal Health by Topic")
        _top_topics = _topic_counts.most_common(8)
        for _tag, _cnt in _top_topics:
            _tag_posts = [i for i in normalized if _taxonomy_topic(i) == _tag]
            _needs_attn = len([
                p for p in _tag_posts
                if p.get("brand_sentiment") == "Negative"
                or _taxonomy_type(p) in ("Complaint", "Bug Report")
            ])
            _attn_pct = round(_needs_attn / max(_cnt, 1) * 100)
            _is_red = _attn_pct > 40 or _needs_attn >= 20
            _is_yellow = _attn_pct > 15 or _needs_attn >= 10
            _bar = "🔴" if _is_red else ("🟡" if _is_yellow else "🟢")
            st.markdown(f"{_bar} **{_tag}** — {_needs_attn} of {_cnt} signals need attention ({_attn_pct}%)")

    # Source distribution
    _src_dist = defaultdict(int)
    for i in normalized:
        _src_dist[i.get("source", "Unknown")] += 1
    if _src_dist:
        _top_srcs = sorted(_src_dist.items(), key=lambda x: -x[1])[:10]
        st.markdown("#### 📡 Source Distribution (Top 10)")
        for _sn, _sc in _top_srcs:
            _pct = round(_sc / max(total, 1) * 100, 1)
            st.caption(f"**{_sn}** — {_sc:,} signals ({_pct}%)")
        st.caption(f"Total unique sources: {len(_src_dist)}")

    # Competitor quick snapshot
    if competitor_posts_raw:
        _comp_counts = _PulseCounter(
            p.get("competitor", "?") for p in competitor_posts_raw
            if p.get("competitor_type") != "ebay_subsidiary"
        )
        if _comp_counts:
            st.markdown("#### ⚔️ Competitor Snapshot")
            _comp_parts = []
            for _cn, _cc in _comp_counts.most_common(5):
                _comp_parts.append(f"**{_cn}** ({_cc})")
            st.caption(" · ".join(_comp_parts) + " — see **Competitor Intel** tab for full analysis")

    st.markdown("---")

    # ── Strategic Themes ──
    st.markdown("### 🧠 Strategic Themes")
    st.caption("AI-clustered themes from user signals. Drill into any theme → opportunity area → supporting signals, then generate PRDs, BRDs, PRFAQs, or Jira tickets.")
    try:
        display_clustered_insight_cards(normalized)
    except Exception as e:
        st.error(f"Cluster view error: {e}")


