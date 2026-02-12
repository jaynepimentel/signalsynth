# app.py — SignalSynth: AI-Powered Collectibles Intelligence Platform

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from slugify import slugify

# 🔧 MUST BE FIRST STREAMLIT CALL
st.set_page_config(
    page_title="SignalSynth | Collectibles Intelligence",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    """
    Lazy-load embedding model only when needed. Returns None if not available.
    For Streamlit Cloud, we skip this to avoid slow torch loading.
    """
    # Skip on Streamlit Cloud to avoid 10+ minute boot times
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
    # Default fields
    i["persona"] = i.get("persona", "Unknown")
    i["journey_stage"] = i.get("journey_stage", "Unknown")
    i["type_tag"] = i.get("type_tag", "Unclassified")
    i["brand_sentiment"] = i.get("brand_sentiment", "Neutral")
    i["clarity"] = i.get("clarity", "Unknown")
    i["effort"] = i.get("effort", "Unknown")
    i["target_brand"] = i.get("target_brand", "Unknown")
    i["action_type"] = i.get("action_type", "Unclear")
    i["opportunity_tag"] = i.get("opportunity_tag", "General Insight")
    
    # Subtag (primary category) - derive from topic_focus if missing
    if not i.get("subtag"):
        tf = i.get("topic_focus_list") or i.get("topic_focus") or []
        if isinstance(tf, list) and tf:
            i["subtag"] = tf[0]
        elif isinstance(tf, str) and tf.strip():
            i["subtag"] = tf.strip()
        else:
            i["subtag"] = "General"

    # Topic focus safe-list
    if isinstance(i.get("topic_focus"), list):
        i["topic_focus_list"] = sorted({t for t in i["topic_focus"] if isinstance(t, str) and t})
    elif isinstance(i.get("topic_focus"), str) and i["topic_focus"].strip():
        i["topic_focus_list"] = [i["topic_focus"].strip()]
    else:
        i["topic_focus_list"] = []

    # Payments / UPI / High-ASP flags (as Yes/No strings for filtering)
    i["_payment_issue_str"] = coerce_bool(i.get("_payment_issue", False))
    i["_upi_flag_str"] = coerce_bool(i.get("_upi_flag", False))
    i["_high_end_flag_str"] = coerce_bool(i.get("_high_end_flag", False))

    # Carrier, program, customs
    i["carrier"] = (i.get("carrier") or "Unknown").upper() if isinstance(i.get("carrier"), str) else "Unknown"
    i["intl_program"] = (i.get("intl_program") or "Unknown").upper() if isinstance(i.get("intl_program"), str) else "Unknown"
    i["customs_flag_str"] = coerce_bool(i.get("customs_flag", False))

    # Evidence collapse & dates
    i["evidence_count"] = i.get("evidence_count", 1)
    i["last_seen"] = i.get("last_seen") or i.get("_logged_date") or i.get("post_date") or "Unknown"
    return i

def get_field_values(insight, field):
    """
    Return a list of values for a given field to support multiselect filters across
    scalars, lists, and comma-separated strings.
    """
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

def kpi_chip(label, value, help_text=None):
    with st.container():
        st.metric(label=label, value=value, help=help_text)

# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
# Clean header with subtle branding
st.markdown("""
<div style="margin-bottom: 0.5rem;">
    <h1 style="margin-bottom: 0; font-size: 2.2rem;">📡 SignalSynth</h1>
    <p style="color: #6b7280; font-size: 1rem; margin-top: 0.25rem;">AI-Powered Collectibles Intelligence Platform</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
      /* Hide sidebar */
      [data-testid="collapsedControl"] { display: none }
      section[data-testid="stSidebar"] { width: 0px !important; display: none }
      
      /* Executive-grade styling */
      .hero-stat {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1.5rem;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
      }
      .hero-stat h1 { color: white; margin: 0; font-size: 2.5rem; }
      .hero-stat p { color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1rem; }
      
      .stat-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
      }
      .stat-card .number { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
      .stat-card .label { font-size: 0.85rem; color: #64748b; margin-top: 0.25rem; }
      
      /* Cleaner metrics */
      [data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 600; }
      [data-testid="stMetricLabel"] { font-size: 0.9rem !important; }
      
      /* Better tab styling */
      .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; border-bottom: 2px solid #e2e8f0; }
      .stTabs [data-baseweb="tab"] { 
        font-weight: 500; 
        padding: 0.75rem 1.25rem !important;
        border-radius: 8px 8px 0 0;
      }
      
      /* Card containers */
      .stContainer { border-radius: 12px !important; }
      
      /* Better buttons */
      .stButton > button {
        min-height: 42px;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
      }
      .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
      
      /* Cleaner expanders */
      .streamlit-expanderHeader { font-weight: 500; }
      
      /* Mobile-responsive */
      @media (max-width: 768px) {
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.25rem !important; }
        [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
        [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
        .stButton > button { min-height: 44px !important; }
        .stTabs [data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; }
        .stTabs [data-baseweb="tab"] { white-space: nowrap !important; padding: 8px 12px !important; }
      }
    </style>
""", unsafe_allow_html=True)

# Onboarding
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.container(border=True):
        col_intro, col_dismiss = st.columns([6, 1])
        with col_intro:
            st.markdown("### 🚀 Quick Start Guide")
        with col_dismiss:
            st.button("✖️ Close", on_click=lambda: st.session_state.update({"show_intro": False}), type="secondary")
        
        st.markdown("""
**Transform community discussions into product decisions.** SignalSynth monitors Reddit, X/Twitter, and competitor channels to surface what collectors are saying about your products.

<div style="display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0;">
    <div style="flex: 1; min-width: 200px; padding: 1rem; background: #f0f9ff; border-radius: 8px; border-left: 4px solid #0ea5e9;">
        <strong>🧱 Clusters</strong><br/>
        <span style="color: #64748b; font-size: 0.9rem;">Strategic epics with AI-generated PRDs, BRDs, and Jira tickets</span>
    </div>
    <div style="flex: 1; min-width: 200px; padding: 1rem; background: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
        <strong>⚔️ Competitors</strong><br/>
        <span style="color: #64748b; font-size: 0.9rem;">War Games analysis for Fanatics, Heritage, Alt</span>
    </div>
    <div style="flex: 1; min-width: 200px; padding: 1rem; background: #dcfce7; border-radius: 8px; border-left: 4px solid #22c55e;">
        <strong>🏪 Subsidiaries</strong><br/>
        <span style="color: #64748b; font-size: 0.9rem;">Action plans for Goldin & TCGPlayer improvement</span>
    </div>
</div>

**🏷️ Auto-detected signals:** Payments · Authentication · Shipping · Vault · Grading · UPI
        """, unsafe_allow_html=True)

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

    # Load raw data counts for impressive stats
    raw_posts_count = 0
    try:
        with open("data/all_scraped_posts.json", "r", encoding="utf-8") as f:
            raw_posts_count = len(json.load(f))
    except:
        pass
    
    competitor_posts_count = 0
    try:
        with open("data/scraped_competitor_posts.json", "r", encoding="utf-8") as f:
            competitor_posts_count = len(json.load(f))
    except:
        pass
    
    clusters_count = 0
    try:
        with open("precomputed_clusters.json", "r", encoding="utf-8") as f:
            clusters_data = json.load(f)
            clusters_count = len(clusters_data.get("clusters", []))
    except:
        pass

    # Normalize
    normalized = [normalize_insight(i, cache) for i in scraped_insights]

    # KPIs - dynamic counts
    total = len(normalized)
    complaints = sum(1 for i in normalized if i.get("type_tag") == "Complaint" or i.get("brand_sentiment") == "Negative")
    payments = sum(1 for i in normalized if i.get("_payment_issue"))
    upi = sum(1 for i in normalized if i.get("_upi_flag"))
    
    # Calculate hours saved (conservative estimate: 2 min per post to read, analyze, categorize)
    total_posts_analyzed = raw_posts_count + competitor_posts_count
    hours_saved = round((total_posts_analyzed * 2) / 60, 1)

    # Calculate date range from insights
    dates = [i.get("post_date", "") for i in scraped_insights if i.get("post_date")]
    date_range = ""
    if dates:
        valid_dates = sorted([d for d in dates if d and len(d) >= 10])
        if valid_dates:
            date_range = f"{valid_dates[0]} to {valid_dates[-1]}"
    
    # Hero stats banner - impactful executive summary
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); border-radius: 12px; padding: 1.5rem 2rem; margin: 1rem 0; color: white;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div>
                <div style="font-size: 2.5rem; font-weight: 700;">{hours_saved}<span style="font-size: 1.2rem; font-weight: 400;"> hrs saved</span></div>
                <div style="opacity: 0.85; font-size: 0.95rem;">vs. manual research</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 2rem; font-weight: 600;">{total_posts_analyzed:,}</div>
                <div style="opacity: 0.85; font-size: 0.9rem;">posts analyzed</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 2rem; font-weight: 600;">{total:,}</div>
                <div style="opacity: 0.85; font-size: 0.9rem;">actionable insights</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 2rem; font-weight: 600;">{clusters_count}</div>
                <div style="opacity: 0.85; font-size: 0.9rem;">strategic epics</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Data freshness - subtle but visible
    freshness_text = f"📅 {date_range}" if date_range else ""
    st.caption(f"{freshness_text}  ·  Last updated: {datetime.now().strftime('%b %d, %Y at %H:%M')}")

    # KPI Row - cleaner, more scannable
    total_posts = raw_posts_count + competitor_posts_count
    signal_ratio = round(total/total_posts*100, 1) if total_posts > 0 else 0
    complaint_ratio = round(complaints/total*100) if total > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: 
        st.metric("� Complaints", f"{complaints:,}", f"{complaint_ratio}% of insights", delta_color="inverse")
    with col2: 
        st.metric("💳 Payment Issues", f"{payments:,}", help="Payment flow problems")
    with col3: 
        st.metric("🚫 Unpaid Items", f"{upi:,}", help="UPI/non-paying buyer issues")
    with col4:
        vault_count = sum(1 for i in normalized if i.get("is_vault_signal"))
        st.metric("🏦 Vault Signals", f"{vault_count:,}", help="Vault-related feedback")

except Exception as e:
    st.error(f"❌ Failed to load insights: {e}")
    st.stop()

# ─────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────
filter_fields = {
    "Topic": "subtag",
    "Type": "type_tag",
}

# Build filtered base list
quick_filtered = normalized

# ─────────────────────────────────────────────
# Tabs (simplified to essential views)
# ─────────────────────────────────────────────
# Tabs with cleaner labels
tabs = st.tabs([
    "🧱 Strategic Epics", "📌 All Insights", "⚔️ Competitors", "🏪 Subsidiaries", "📈 Trends"
])

# 🧱 CLUSTERS - Strategic epics (first tab now)
with tabs[0]:
    st.markdown("""
    <div style="margin-bottom: 1rem;">
        <p style="color: #64748b; margin: 0;">AI-clustered themes from community feedback. Click any epic to generate PRDs, BRDs, or Jira tickets.</p>
    </div>
    """, unsafe_allow_html=True)
    try:
        display_clustered_insight_cards(quick_filtered)
    except Exception as e:
        st.error(f"❌ Cluster view error: {e}")

# 📌 INSIGHTS - Individual view with filters
with tabs[1]:
    st.markdown("Filter and explore individual signals from the community.")
    try:
        filters = render_floating_filters(quick_filtered, filter_fields, key_prefix="insights")
        filtered = [i for i in quick_filtered if match_multiselect_filters(i, filters, filter_fields)]
        # Apply time filter
        time_range = filters.get("_time_range", "All Time")
        filtered = filter_by_time(filtered, time_range)
        st.caption(f"Showing {len(filtered)} of {len(quick_filtered)} insights")
        model = get_model()
        render_insight_cards(filtered, model, key_prefix="insights")
    except Exception as e:
        st.error(f"❌ Insights tab error: {e}")

# ⚔️ COMPETITORS - Competitor insights only
with tabs[2]:
    st.markdown("""
    <div style="background: #fef3c7; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #f59e0b;">
        <strong>⚔️ Competitive Intelligence</strong><br/>
        <span style="color: #64748b;">See what collectors say about Fanatics, Heritage, and Alt. Use <strong>War Games</strong> to generate strategic responses.</span>
    </div>
    """, unsafe_allow_html=True)
    
    # War Games LLM function for competitors
    def generate_war_games(competitor: str, post_text: str, post_title: str) -> str:
        """Generate competitive war games strategy."""
        try:
            from components.ai_suggester import _chat, MODEL_MAIN
        except ImportError:
            return "LLM not available. Please configure OpenAI API key."
        
        prompt = f"""You are a Senior Product Strategist at eBay running a competitive war games exercise.

COMPETITOR: {competitor}
USER FEEDBACK:
Title: {post_title}
Content: {post_text}

Analyze this competitive signal and generate a WAR GAMES STRATEGY BRIEF:

1. **SIGNAL TYPE**: Is this a competitive threat, competitive advantage they have, or user pain point with {competitor}?

2. **THREAT LEVEL**: Low / Medium / High — and why?

3. **USER SENTIMENT**: What does the community actually want? What are they praising or complaining about?

4. **eBay RESPONSE OPTIONS** (pick 2-3):
   - **Defend**: How could eBay protect its collectibles position?
   - **Attack**: How could eBay win users from {competitor}?
   - **Differentiate**: What unique value can eBay offer that {competitor} can't?
   - **Exploit Weakness**: If users are complaining about {competitor}, how can eBay capitalize?

5. **RECOMMENDED PLAY**: One specific action for the eBay Collectibles PM team.

Be direct, strategic, and actionable. Think like a competitive strategist."""

        try:
            return _chat(
                MODEL_MAIN,
                "You are an expert competitive strategist who writes crisp, actionable war games briefs.",
                prompt,
                max_completion_tokens=600,
                temperature=0.5
            )
        except Exception as e:
            return f"War games generation failed: {e}"
    
    # Subsidiary improvement LLM function
    def generate_subsidiary_action(subsidiary: str, post_text: str, post_title: str) -> str:
        """Generate improvement action plan for eBay subsidiary."""
        try:
            from components.ai_suggester import _chat, MODEL_MAIN
        except ImportError:
            return "LLM not available. Please configure OpenAI API key."
        
        prompt = f"""You are a Senior Product Manager at eBay responsible for improving {subsidiary} (an eBay-owned subsidiary).

SUBSIDIARY: {subsidiary} (owned by eBay)
USER FEEDBACK:
Title: {post_title}
Content: {post_text}

Analyze this user feedback and generate an IMPROVEMENT ACTION PLAN:

1. **FEEDBACK TYPE**: Is this a bug/issue, feature request, UX complaint, or positive feedback?

2. **SEVERITY/PRIORITY**: P0 (critical) / P1 (high) / P2 (medium) / P3 (low) — and why?

3. **USER PAIN POINT**: What specific problem is the user experiencing? Be concrete.

4. **ROOT CAUSE HYPOTHESIS**: What's likely causing this issue or gap?

5. **RECOMMENDED FIXES** (pick 1-2):
   - **Quick Win**: What can be fixed in the next sprint?
   - **Strategic Investment**: What longer-term improvement would address this?
   - **Cross-Platform Synergy**: How could eBay marketplace integration help?

6. **SUCCESS METRIC**: How would we measure if this fix worked?

Be specific and actionable. Think like a PM who owns {subsidiary}."""

        try:
            return _chat(
                MODEL_MAIN,
                "You are an expert product manager who writes clear, actionable improvement plans.",
                prompt,
                max_completion_tokens=600,
                temperature=0.4
            )
        except Exception as e:
            return f"Action plan generation failed: {e}"
    
    try:
        # Load competitor data
        competitor_posts = []
        try:
            with open("data/scraped_competitor_posts.json", "r", encoding="utf-8") as f:
                competitor_posts = json.load(f)
        except:
            st.warning("No competitor data found. Run `python utils/scrape_competitors.py` to scrape.")
        
        if competitor_posts:
            # Separate competitors from subsidiaries
            from collections import defaultdict
            comp_groups = defaultdict(list)
            sub_groups = defaultdict(list)
            for p in competitor_posts:
                comp = p.get("competitor", "Unknown")
                if p.get("competitor_type") == "ebay_subsidiary":
                    sub_groups[comp].append(p)
                else:
                    comp_groups[comp].append(p)
            
            # Competitor filter (competitors only)
            all_comps = sorted(comp_groups.keys())
            if all_comps:
                selected_comp = st.selectbox("Select Competitor", ["All"] + all_comps, key="comp_select")
                
                # Metrics for competitors only
                total_comp = sum(len(v) for v in comp_groups.values())
                st.metric("Total Competitor Posts", total_comp)
                
                st.markdown("---")
                
                # Show competitor posts
                for comp_name in (all_comps if selected_comp == "All" else [selected_comp]):
                    posts = comp_groups.get(comp_name, [])
                    if not posts:
                        continue
                    
                    with st.container(border=True):
                        st.subheader(f"🏢 {comp_name} ({len(posts)} posts)")
                        
                        sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
                        
                        # Determine how many posts to show
                        show_all_key = f"show_all_comp_{comp_name}"
                        posts_to_show = len(sorted_posts) if st.session_state.get(show_all_key) else 10
                        
                        for idx, post in enumerate(sorted_posts[:posts_to_show], 1):
                            title = post.get("title", "")[:80] or post.get("text", "")[:80]
                            score = post.get("score", 0)
                            date = post.get("post_date", "")
                            url = post.get("url", "")
                            post_id = post.get("post_id", f"{comp_name}_{idx}")
                            
                            with st.expander(f"{idx}. {title}... (⬆️ {score})"):
                                st.markdown(f"> {post.get('text', '')[:500]}")
                                st.caption(f"**Date:** {date} | **Subreddit:** r/{post.get('subreddit', '')} | [View Original]({url})")
                                
                                # War Games button
                                wargames_key = f"wargames_{post_id}"
                                if st.button("⚔️ War Games", key=f"btn_{wargames_key}", help="Generate competitive strategy"):
                                    st.session_state[wargames_key] = True
                                    st.rerun()
                                
                                if st.session_state.get(wargames_key):
                                    with st.spinner("Generating war games strategy..."):
                                        strategy = generate_war_games(comp_name, post.get("text", ""), post.get("title", ""))
                                    st.info(strategy)
                                    if st.button("❌ Close", key=f"close_{wargames_key}"):
                                        st.session_state[wargames_key] = False
                                        st.rerun()
                        
                        # Load more / Show less button
                        if len(posts) > 10:
                            if st.session_state.get(show_all_key):
                                if st.button(f"📤 Show Less", key=f"less_{comp_name}"):
                                    st.session_state[show_all_key] = False
                                    st.rerun()
                            else:
                                if st.button(f"📥 Load {len(posts) - 10} More Posts", key=f"more_{comp_name}"):
                                    st.session_state[show_all_key] = True
                                    st.rerun()
            else:
                st.info("No competitor posts found.")
            
    except Exception as e:
        st.error(f"❌ Competitors tab error: {e}")

# 🏪 SUBSIDIARIES - Goldin & TCGPlayer (separate tab)
with tabs[3]:
    st.markdown("""
    <div style="background: #dcfce7; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #22c55e;">
        <strong>🏪 Your Subsidiaries</strong><br/>
        <span style="color: #64748b;">Goldin & TCGPlayer feedback. Generate <strong>Action Plans</strong> to improve these eBay-owned platforms.</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Subsidiary improvement LLM function (defined here for this tab)
    def generate_subsidiary_action_tab(subsidiary: str, post_text: str, post_title: str) -> str:
        """Generate improvement action plan for eBay subsidiary."""
        try:
            from components.ai_suggester import _chat, MODEL_MAIN
        except ImportError:
            return "LLM not available. Please configure OpenAI API key."
        
        prompt = f"""You are a Senior Product Manager at eBay responsible for improving {subsidiary} (an eBay-owned subsidiary).

SUBSIDIARY: {subsidiary} (owned by eBay)
USER FEEDBACK:
Title: {post_title}
Content: {post_text}

Analyze this user feedback and generate an IMPROVEMENT ACTION PLAN:

1. **FEEDBACK TYPE**: Is this a bug/issue, feature request, UX complaint, or positive feedback?

2. **SEVERITY/PRIORITY**: P0 (critical) / P1 (high) / P2 (medium) / P3 (low) — and why?

3. **USER PAIN POINT**: What specific problem is the user experiencing? Be concrete.

4. **ROOT CAUSE HYPOTHESIS**: What's likely causing this issue or gap?

5. **RECOMMENDED FIXES** (pick 1-2):
   - **Quick Win**: What can be fixed in the next sprint?
   - **Strategic Investment**: What longer-term improvement would address this?
   - **Cross-Platform Synergy**: How could eBay marketplace integration help?

6. **SUCCESS METRIC**: How would we measure if this fix worked?

Be specific and actionable. Think like a PM who owns {subsidiary}."""

        try:
            return _chat(
                MODEL_MAIN,
                "You are an expert product manager who writes clear, actionable improvement plans.",
                prompt,
                max_completion_tokens=600,
                temperature=0.4
            )
        except Exception as e:
            return f"Action plan generation failed: {e}"
    
    try:
        # Load subsidiary data
        sub_posts = []
        try:
            with open("data/scraped_competitor_posts.json", "r", encoding="utf-8") as f:
                all_comp_data = json.load(f)
                sub_posts = [p for p in all_comp_data if p.get("competitor_type") == "ebay_subsidiary"]
        except:
            st.warning("No subsidiary data found. Run `python utils/scrape_competitors.py` to scrape.")
        
        if sub_posts:
            # Group by subsidiary
            from collections import defaultdict
            sub_groups = defaultdict(list)
            for p in sub_posts:
                sub = p.get("competitor", "Unknown")
                sub_groups[sub].append(p)
            
            all_subs = sorted(sub_groups.keys())
            selected_sub = st.selectbox("Select Subsidiary", ["All"] + all_subs, key="sub_select_tab")
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Posts", len(sub_posts))
            with col2:
                goldin_count = len([p for p in sub_posts if p.get("competitor") == "Goldin"])
                st.metric("Goldin", goldin_count)
            with col3:
                tcg_count = len([p for p in sub_posts if p.get("competitor") == "TCGPlayer"])
                st.metric("TCGPlayer", tcg_count)
            
            st.markdown("---")
            
            # Show subsidiary posts
            for sub_name in (all_subs if selected_sub == "All" else [selected_sub]):
                posts = sub_groups.get(sub_name, [])
                if not posts:
                    continue
                
                with st.container(border=True):
                    st.subheader(f"🏪 {sub_name} ({len(posts)} posts)")
                    
                    sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
                    
                    # Determine how many posts to show
                    show_all_key = f"show_all_sub_{sub_name}"
                    posts_to_show = len(sorted_posts) if st.session_state.get(show_all_key) else 10
                    
                    for idx, post in enumerate(sorted_posts[:posts_to_show], 1):
                        title = post.get("title", "")[:80] or post.get("text", "")[:80]
                        score = post.get("score", 0)
                        date = post.get("post_date", "")
                        url = post.get("url", "")
                        post_id = post.get("post_id", f"{sub_name}_sub_{idx}")
                        
                        with st.expander(f"{idx}. {title}... (⬆️ {score})"):
                            st.markdown(f"> {post.get('text', '')[:500]}")
                            st.caption(f"**Date:** {date} | **Subreddit:** r/{post.get('subreddit', '')} | [View Original]({url})")
                            
                            # Action Plan button
                            action_key = f"action_sub_{post_id}"
                            if st.button("🔧 Action Plan", key=f"btn_{action_key}", help="Generate improvement action plan"):
                                st.session_state[action_key] = True
                                st.rerun()
                            
                            if st.session_state.get(action_key):
                                with st.spinner("Generating action plan..."):
                                    plan = generate_subsidiary_action_tab(sub_name, post.get("text", ""), post.get("title", ""))
                                st.success(plan)
                                if st.button("❌ Close", key=f"close_{action_key}"):
                                    st.session_state[action_key] = False
                                    st.rerun()
                    
                    # Load more / Show less button
                    if len(posts) > 10:
                        if st.session_state.get(show_all_key):
                            if st.button(f"📤 Show Less", key=f"less_sub_{sub_name}"):
                                st.session_state[show_all_key] = False
                                st.rerun()
                        else:
                            if st.button(f"📥 Load {len(posts) - 10} More Posts", key=f"more_sub_{sub_name}"):
                                st.session_state[show_all_key] = True
                                st.rerun()
        else:
            st.info("No subsidiary posts found.")
    except Exception as e:
        st.error(f"❌ Subsidiaries tab error: {e}")

# 📈 TRENDS - Charts and summary
with tabs[4]:
    st.markdown("Visualize patterns in sentiment, topics, and signal volume over time.")
    try:
        display_insight_charts(quick_filtered)
    except Exception as e:
        st.error(f"❌ Charts error: {e}")
    try:
        display_brand_dashboard(quick_filtered)
    except Exception as e:
        st.error(f"❌ Dashboard error: {e}")
