# app.py — SignalSynth (enhanced UI: Payments/UPI/high-ASP, evidence KPIs, carrier/ISP filters)

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import json
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
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
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

st.markdown("""
    <style>
      /* Hide sidebar */
      [data-testid="collapsedControl"] { display: none }
      section[data-testid="stSidebar"] { width: 0px !important; display: none }
      .kpi-row { margin-bottom: 0.5rem; }
      
      /* Mobile-responsive styles */
      @media (max-width: 768px) {
        /* Make title smaller on mobile */
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.25rem !important; }
        h3 { font-size: 1.1rem !important; }
        
        /* Stack columns vertically on mobile */
        [data-testid="column"] {
          width: 100% !important;
          flex: 1 1 100% !important;
          min-width: 100% !important;
        }
        
        /* Make metrics more compact */
        [data-testid="stMetricValue"] {
          font-size: 1.5rem !important;
        }
        
        /* Improve button touch targets */
        .stButton > button {
          min-height: 44px !important;
          font-size: 0.9rem !important;
        }
        
        /* Make expanders easier to tap */
        .streamlit-expanderHeader {
          padding: 12px 8px !important;
        }
        
        /* Compact tables on mobile */
        table {
          font-size: 0.85rem !important;
        }
        
        /* Make tabs scrollable */
        .stTabs [data-baseweb="tab-list"] {
          overflow-x: auto !important;
          flex-wrap: nowrap !important;
        }
        
        .stTabs [data-baseweb="tab"] {
          white-space: nowrap !important;
          padding: 8px 12px !important;
        }
      }
      
      /* Improve touch targets for all devices */
      .stButton > button {
        min-height: 40px;
      }
      
      /* Better spacing for containers */
      [data-testid="stVerticalBlock"] > div {
        padding-bottom: 0.5rem;
      }
    </style>
""", unsafe_allow_html=True)

# Onboarding
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.container(border=True):
        st.markdown("### 🧠 Welcome to SignalSynth!")
        st.markdown("""
**SignalSynth** is your AI-powered insight engine for eBay Collectibles — transforming thousands of community discussions into actionable product intelligence.

---

**📊 What's Inside:**

| Source | Coverage |
|--------|----------|
| 📍 **Reddit** | 33 collectibles subreddits + targeted searches |
| 🏢 **Competitors** | Fanatics Collect, Fanatics Live, Heritage Auctions, Alt |
| 🏪 **Your Subsidiaries** | Goldin, TCGPlayer (you manage these!) |
| 🤝 **Strategic Partners** | PSA (Vault, Grading, Consignment, Offers), ComC |

---

**🗂️ Six Tabs to Explore:**

| Tab | Purpose | Key Action |
|-----|---------|------------|
| **🧱 Clusters** | Strategic epics grouped by theme | Generate PRDs, BRDs, Jira tickets |
| **📌 Insights** | Individual signals with filters | Filter by topic, type, sentiment |
| **🏢 Competitors** | What users say about rivals | ⚔️ **War Games** — competitive strategy |
| **🏪 Subsidiaries** | Goldin & TCGPlayer feedback | 🔧 **Action Plan** — improvement roadmap |
| **🤝 Partners** | PSA & ComC partner intelligence | 📋 **Partner Docs** — strategy & insights |
| **📈 Trends** | Sentiment & topic over time | Spot emerging issues |

---

**⚡ AI-Powered Document Generation (in Clusters):**
- 🤖 **Executive Summary** — Problem, impact, root cause, recommendation
- 📄 **PRD** — User stories, requirements, success metrics
- 💼 **BRD** — Business case for stakeholders
- 📰 **PRFAQ** — Amazon-style press release + FAQ
- 🎫 **Jira Tickets** — Sprint-ready with acceptance criteria

---

**🏷️ Auto-detected Signals:** 💳 Payments · 🛡️ Trust · 📦 Shipping · ✅ AG · 🏦 Vault · ⚠️ UPI · 🎯 Grading
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

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
    
    # Executive stats banner
    st.success(f"""
    📊 **Analysis Complete** | 🕐 **~{hours_saved} hours of manual research saved**
    
    **{total_posts_analyzed:,}** social posts scraped → **{total:,}** actionable insights → **{clusters_count}** strategic epics
    """)
    
    # Data freshness indicator
    if date_range:
        st.caption(f"📅 **Data Range:** {date_range} | 🔄 **Last Processed:** {datetime.now().strftime('%b %d, %Y')}")

# KPI Row - More impressive metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    total_posts = raw_posts_count + competitor_posts_count
    signal_ratio = round(total/total_posts*100, 1) if total_posts > 0 else 0
    complaint_ratio = round(complaints/total*100) if total > 0 else 0

    with col1: kpi_chip("📥 Posts Scraped", f"{total_posts:,}", "Reddit, Bluesky, Competitors")
    with col2: kpi_chip("🎯 Insights", f"{total:,}", f"{signal_ratio}% signal-to-noise")
    with col3: kpi_chip("😠 Complaints", f"{complaints:,}", f"{complaint_ratio}% of insights")
    with col4: kpi_chip("💳 Payments", f"{payments:,}", "Payment flow issues")
    with col5: kpi_chip("🚫 UPI", f"{upi:,}", "Unpaid item issues")

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
tabs = st.tabs([
    "🧱 Clusters", "📌 Insights", "🏢 Competitors", "🏪 Subsidiaries", "🤝 Partners", "📈 Trends"
])

# 🧱 CLUSTERS - Strategic epics (first tab now)
with tabs[0]:
    st.header("🧱 Strategic Epics")
    try:
        display_clustered_insight_cards(quick_filtered)
    except Exception as e:
        st.error(f"❌ Cluster view error: {e}")

# 📌 INSIGHTS - Individual view with filters
with tabs[1]:
    st.header("📌 Individual Insights")
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

# 🏢 COMPETITORS - Competitor insights only
with tabs[2]:
    st.header("🏢 Competitors")
    st.markdown("Track what users are saying about competitors. Use **⚔️ War Games** to generate competitive response strategies.")
    
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
    st.header("🏪 eBay Subsidiaries")
    st.info("**You manage these!** Track user feedback for Goldin & TCGPlayer and generate improvement action plans.")
    
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

# 🤝 STRATEGIC PARTNERS - PSA, ComC integration partners
with tabs[4]:
    st.header("🤝 Strategic Partners")
    st.markdown("Track user feedback on eBay's strategic partners. Use **📋 Partner Strategy** to generate partnership insights and recommendations.")
    
    # Partner Strategy LLM function
    def generate_partner_strategy(partner: str, post_text: str, post_title: str) -> str:
        """Generate partner strategy brief."""
        try:
            from components.ai_suggester import _chat, MODEL_MAIN
        except ImportError:
            return "LLM not available. Please configure OpenAI API key."
        
        prompt = f"""You are a Senior Partnerships Manager at eBay analyzing partner feedback.

PARTNER: {partner}
USER FEEDBACK:
Title: {post_title}
Content: {post_text}

Analyze this partner signal and generate a PARTNER STRATEGY BRIEF:

1. **SIGNAL TYPE**: Is this a partner service issue, integration problem, user experience gap, or positive feedback about {partner}?

2. **IMPACT ON EBAY**: How does this feedback affect eBay sellers/buyers using {partner} services?

3. **ROOT CAUSE**: What's likely causing this issue? Is it on the partner side, eBay integration side, or user education gap?

4. **RECOMMENDED ACTION**: What should eBay's partnerships team do?
   - Escalate to partner account team?
   - Improve integration/documentation?
   - Add feature to address gap?
   - No action needed?

5. **PARTNERSHIP HEALTH**: Rate the signal (🟢 Positive / 🟡 Neutral / 🔴 Concerning)

Be specific and actionable. Write for a partnerships manager."""
        
        try:
            return _chat(
                MODEL_MAIN,
                "You are an expert partnerships strategist who writes crisp, actionable partner strategy briefs.",
                prompt,
                max_completion_tokens=600,
                temperature=0.5
            )
        except Exception as e:
            return f"Partner strategy generation failed: {e}"
    
    STRATEGIC_PARTNERS = {
        "PSA Vault": {"icon": "🏦", "desc": "Secure storage and eBay selling", "keywords": ["psa vault", "vault storage", "vault sell", "vault auction", "vault withdraw"]},
        "PSA Grading": {"icon": "🎯", "desc": "Card grading and authentication", "keywords": ["psa grading", "psa grade", "psa turnaround", "psa submission", "psa 10", "psa 9"]},
        "PSA Consignment": {"icon": "📦", "desc": "Consignment selling service", "keywords": ["psa consignment", "psa consign", "consignment psa"]},
        "PSA Sell on eBay": {"icon": "🛒", "desc": "Direct selling through PSA", "keywords": ["psa sell ebay", "psa ebay", "sell through psa", "psa auction"]},
        "PSA Offers": {"icon": "💰", "desc": "Instant offer/buyback program", "keywords": ["psa offer", "psa buyback", "psa buy back", "psa instant"]},
        "ComC": {"icon": "📋", "desc": "Check Out My Cards - consignment partner", "keywords": ["comc", "check out my cards", "comc consignment", "comc selling"]},
    }
    
    try:
        partner_posts = {name: [] for name in STRATEGIC_PARTNERS.keys()}
        for insight in normalized:
            text = (insight.get("title", "") + " " + insight.get("text", "")).lower()
            for partner_name, config in STRATEGIC_PARTNERS.items():
                if any(kw in text for kw in config["keywords"]):
                    partner_posts[partner_name].append(insight)
        
        # Metrics row
        col1, col2, col3 = st.columns(3)
        total_partner = sum(len(posts) for posts in partner_posts.values())
        with col1:
            st.metric("Total Partner Signals", total_partner)
        with col2:
            psa_total = sum(len(posts) for name, posts in partner_posts.items() if name.startswith("PSA"))
            st.metric("PSA Signals", psa_total)
        with col3:
            st.metric("ComC Signals", len(partner_posts.get("ComC", [])))
        
        # Partner selector
        selected_partner = st.selectbox("Select Partner", ["All Partners"] + list(STRATEGIC_PARTNERS.keys()), key="partner_sel")
        partners_to_show = STRATEGIC_PARTNERS.keys() if selected_partner == "All Partners" else [selected_partner]
        
        for partner_name in partners_to_show:
            posts = partner_posts.get(partner_name, [])
            config = STRATEGIC_PARTNERS[partner_name]
            
            if posts or selected_partner != "All Partners":
                with st.container(border=True):
                    st.subheader(f"{config['icon']} {partner_name} ({len(posts)} signals)")
                    st.caption(config["desc"])
                    
                    if posts:
                        # Aggregate document generation buttons
                        st.markdown("**📊 Aggregate Documents** (based on all signals)")
                        doc_cols = st.columns(4)
                        with doc_cols[0]:
                            if st.button(f"📄 PRD", key=f"prd_{partner_name}", use_container_width=True):
                                st.session_state[f"gen_doc_{partner_name}"] = "PRD"
                        with doc_cols[1]:
                            if st.button(f"💼 BRD", key=f"brd_{partner_name}", use_container_width=True):
                                st.session_state[f"gen_doc_{partner_name}"] = "BRD"
                        with doc_cols[2]:
                            if st.button(f"🤖 Summary", key=f"sum_{partner_name}", use_container_width=True):
                                st.session_state[f"gen_doc_{partner_name}"] = "SUMMARY"
                        with doc_cols[3]:
                            if st.button(f"🎫 Jira", key=f"jira_{partner_name}", use_container_width=True):
                                st.session_state[f"gen_doc_{partner_name}"] = "JIRA"
                        
                        # Show generated document if any
                        if st.session_state.get(f"gen_doc_{partner_name}"):
                            doc_type = st.session_state[f"gen_doc_{partner_name}"]
                            with st.spinner(f"Generating {doc_type}..."):
                                context = "\n---\n".join([f"[{p.get('type_tag', 'Feedback')}] {p.get('text', '')[:300]}" for p in posts[:10]])
                                try:
                                    from components.ai_suggester import _chat, MODEL_MAIN
                                    if doc_type == "SUMMARY":
                                        prompt = f"Write an executive summary for {partner_name} based on {len(posts)} user signals:\n{context}"
                                    elif doc_type == "JIRA":
                                        prompt = f"Create 3 Jira tickets for {partner_name} issues based on:\n{context}"
                                    else:
                                        prompt = f"Write a {doc_type} for {partner_name} improvements based on:\n{context}"
                                    doc = _chat(MODEL_MAIN, f"You write excellent {doc_type}s.", prompt, max_completion_tokens=1200, temperature=0.4)
                                    st.markdown(f"### Generated {doc_type}")
                                    st.markdown(doc)
                                    if st.button("❌ Close", key=f"close_doc_{partner_name}"):
                                        st.session_state[f"gen_doc_{partner_name}"] = None
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Generation failed: {e}")
                                    st.session_state[f"gen_doc_{partner_name}"] = None
                        
                        st.markdown("---")
                        st.markdown("**📝 Individual Signals** (click 📋 Partner Strategy for per-signal analysis)")
                        
                        # Show posts with per-post Partner Strategy button
                        sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
                        show_key = f"show_all_{partner_name}"
                        display_count = len(sorted_posts) if st.session_state.get(show_key) else 5
                        
                        for idx, post in enumerate(sorted_posts[:display_count]):
                            post_id = post.get("fingerprint", f"{partner_name}_{idx}")
                            title = post.get("title", "")[:80] or post.get("text", "")[:80]
                            sentiment = post.get("brand_sentiment", "Neutral")
                            sent_icon = {"Negative": "🔴", "Positive": "🟢"}.get(sentiment, "⚪")
                            score = post.get("score", 0)
                            date = post.get("post_date", "")
                            url = post.get("url", "")
                            
                            with st.container(border=True):
                                st.markdown(f"**{sent_icon} {title}**")
                                st.markdown(f"> {post.get('text', '')[:500]}")
                                st.caption(f"**Score:** 👍 {score} | **Date:** {date} | [🔗 View Original]({url})" if url else f"**Score:** 👍 {score} | **Date:** {date}")
                                
                                # Partner Strategy button (like War Games)
                                strategy_key = f"partner_strategy_{post_id}"
                                if st.button("📋 Partner Strategy", key=f"btn_{strategy_key}", help="Generate partnership strategy brief"):
                                    st.session_state[strategy_key] = True
                                    st.rerun()
                                
                                if st.session_state.get(strategy_key):
                                    with st.spinner("Generating partner strategy..."):
                                        strategy = generate_partner_strategy(partner_name, post.get("text", ""), post.get("title", ""))
                                    st.info(strategy)
                                    if st.button("❌ Close", key=f"close_{strategy_key}"):
                                        st.session_state[strategy_key] = False
                                        st.rerun()
                        
                        if len(sorted_posts) > 5:
                            if st.session_state.get(show_key):
                                if st.button("📤 Show Less", key=f"less_{partner_name}"):
                                    st.session_state[show_key] = False
                                    st.rerun()
                            else:
                                if st.button(f"📥 Load {len(posts) - 5} More", key=f"more_{partner_name}"):
                                    st.session_state[show_key] = True
                                    st.rerun()
                    else:
                        st.info(f"No {partner_name} signals found. Run scraper to collect partner feedback.")
    
    except Exception as e:
        st.error(f"❌ Partners tab error: {e}")

# �� TRENDS - Charts and summary
with tabs[5]:
    st.header("📈 Trends & Summary")
    try:
        display_insight_charts(quick_filtered)
    except Exception as e:
        st.error(f"❌ Charts error: {e}")
    try:
        display_brand_dashboard(quick_filtered)
    except Exception as e:
        st.error(f"❌ Dashboard error: {e}")
