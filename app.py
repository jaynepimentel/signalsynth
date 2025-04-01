# app.py — SignalSynth with polished UX, fixed tabs, badge colors, and sidebar minimized
import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import Counter
from slugify import slugify
from datetime import datetime

from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.cluster_view import display_clustered_insight_cards
from components.emerging_themes import detect_emerging_topics, render_emerging_topics
from components.floating_filters import render_floating_filters
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket
)
from components.strategic_tools import (
    display_signal_digest,
    display_journey_breakdown,
    display_brand_comparator,
    display_impact_heatmap,
    display_prd_bundler,
    display_spark_suggestions
)

# ───────────────────────────────────────
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# 🧠 Minimize the sidebar entirely
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

# 🧠 Onboarding Lightbox
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth! What Can You Do Here?", expanded=True):
        st.markdown("""
        SignalSynth helps you transform user signals into strategic action.

        **💥 Explore the full power of this tool:**

        - 🔍 **Filter by brand, persona, type, effort, etc.**
        - 📌 **Click any insight** to generate a PRD, BRD, PRFAQ, or JIRA ticket
        - 🧱 **View clusters** of similar feedback to spot themes
        - 📈 **Track sentiment and trends** over time
        - 🔥 **Spot emerging topics** from the community
        - 💡 **Enable GPT Suggestions** for AI-powered product ideas
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

# ───────────────────────────────────────
# Load precomputed insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found. Please run `precompute_insights.py`.")
    st.stop()

# ───────────────────────────────────────
# Tab setup
filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Effort Estimate": "effort",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity",
    "Opportunity Tag": "opportunity_tag",
    "Action Type": "action_type",
    "Topic Focus": "topic_focus_tags",
    "Mentions Competitor": "mentions_competitor"
}

tabs = st.tabs(["📌 Insights", "🧱 Clusters", "🔎 Explorer", "📈 Trends", "🔥 Emerging", "🧠 Strategic Tools"])

# Color-coded badge system
BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800"
}

def badge(label, color):
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

# ───────────────────────────────────────
# Tab 0: Individual Insights
with tabs[0]:
    st.header("📌 Individual Insights")

    topic_keywords = ["vault", "psa", "graded", "fanatics", "cancel", "authenticity", "shipping", "refund"]
    trend_counter = Counter()
    for i in scraped_insights:
        text = i.get("text", "").lower()
        for word in topic_keywords:
            if word in text:
                trend_counter[word] += 1
    rising_trends = [t for t, count in trend_counter.items() if count >= 5]

    filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="insights")
    filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]
    show_trends_only = st.checkbox("Highlight Emerging Topics Only", value=False)
    if show_trends_only:
        filtered = [i for i in filtered if any(w in i.get("text", "").lower() for w in rising_trends)]

    INSIGHTS_PER_PAGE = 10
    total_pages = max(1, (len(filtered) + INSIGHTS_PER_PAGE - 1) // INSIGHTS_PER_PAGE)
    if "page" not in st.session_state:
        st.session_state.page = 1

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.page = max(1, st.session_state.page - 1)
    with col2:
        st.markdown(f"**Page {st.session_state.page} of {total_pages}**")
    with col3:
        if st.button("Next ➡️"):
            st.session_state.page = min(total_pages, st.session_state.page + 1)

    start_idx = (st.session_state.page - 1) * INSIGHTS_PER_PAGE
    paged_insights = filtered[start_idx:start_idx + INSIGHTS_PER_PAGE]

    for idx, i in enumerate(paged_insights, start=start_idx):
        st.markdown(f"### 🧠 Insight: {i.get('title', i.get('text', '')[:60])}")
        tags = [
            badge(i.get("type_tag"), BADGE_COLORS.get(i.get("type_tag"), "#ccc")),
            badge(i.get("brand_sentiment"), BADGE_COLORS.get(i.get("brand_sentiment"), "#ccc")),
            badge(i.get("effort"), BADGE_COLORS.get(i.get("effort"), "#ccc")),
            badge(i.get("journey_stage"), BADGE_COLORS.get(i.get("journey_stage"), "#ccc")),
            badge(i.get("clarity"), BADGE_COLORS.get(i.get("clarity"), "#ccc"))
        ]
        st.markdown(" ".join(tags), unsafe_allow_html=True)

        st.caption(
            f"Score: {i.get('score', 0)} | Type: {i.get('type_tag')} > {i.get('type_subtag', '')} "
            f"({i.get('type_confidence')}%) | Effort: {i.get('effort')} | Brand: {i.get('target_brand')} | "
            f"Sentiment: {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%) | Persona: {i.get('persona')}"
        )

        with st.expander(f"🧠 Full Insight ({i.get('status', 'Unknown')})"):
            text = i.get("text", "")
            brand = i.get("target_brand", "eBay")
            st.markdown("**User Quote:**")
            st.markdown(f"> {text}")

            if OPENAI_KEY_PRESENT:
                with st.spinner("💡 Generating PM Suggestions..."):
                    try:
                        i["ideas"] = generate_pm_ideas(text, brand)
                    except Exception as e:
                        i["ideas"] = [f"[❌ GPT error: {str(e)}]"]

            if i.get("ideas"):
                st.markdown("**💡 PM Suggestions:**")
                for idea in i["ideas"]:
                    st.markdown(f"- {idea}")

            if i.get("clarity") == "Needs Clarification":
                st.warning("This insight may need refinement.")
                if st.button("🧼 Clarify This Insight", key=f"clarify_{idx}"):
                    st.info("(This would re-run the insight through GPT to rephrase or flag it for triage.)")

            filename = slugify(i.get("title", i.get("text", "")[:40]))[:64]
            doc_type = st.selectbox("Select document type to generate:", ["PRD", "BRD", "PRFAQ", "JIRA"], key=f"doc_type_{idx}")
            if st.button(f"Generate {doc_type}", key=f"generate_doc_{idx}"):
                with st.spinner(f"Generating {doc_type}..."):
                    if doc_type == "PRD":
                        file_path = generate_prd_docx(text, brand, filename)
                    elif doc_type == "BRD":
                        file_path = generate_brd_docx(text, brand, filename + "-brd")
                    elif doc_type == "PRFAQ":
                        file_path = generate_prfaq_docx(text, brand, filename + "-prfaq")
                    elif doc_type == "JIRA":
                        file_content = generate_jira_bug_ticket(text, brand)
                        st.download_button("⬇️ Download JIRA", file_content, file_name=f"jira-{filename}.md", mime="text/markdown", key=f"dl_jira_{idx}")
                        file_path = None
                    if file_path and os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                f"⬇️ Download {doc_type}",
                                f,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_doc_{idx}"
                            )

# ───────────────────────────────────────
# Tab 1: Cluster View
with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    display_clustered_insight_cards(scraped_insights)

# ───────────────────────────────────────
# Tab 2: Explorer View
with tabs[2]:
    st.header("🔍 Insight Explorer")
    explorer_filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="explorer")
    explorer_filtered = [i for i in scraped_insights if all(explorer_filters[k] == "All" or str(i.get(k, "Unknown")) == explorer_filters[k] for k in explorer_filters)]
    display_insight_explorer(explorer_filtered[:50])

# ───────────────────────────────────────
# Tab 3: Trends
with tabs[3]:
    st.header("📈 Trends + Brand Summary")
    display_insight_charts(scraped_insights)
    display_brand_dashboard(scraped_insights)

# ───────────────────────────────────────
# Tab 4: Emerging Topics
with tabs[4]:
    st.header("🔥 Emerging Topics")
    trends = detect_emerging_topics(scraped_insights)
    render_emerging_topics(trends)

# ───────────────────────────────────────
# Tab 5: Strategic Tools
with tabs[5]:
    st.header("🧠 Strategic Tools")
    st.markdown("This tab provides high-leverage tools for product strategy, prioritization, and portfolio decision-making.")
    display_spark_suggestions(scraped_insights)
    st.markdown("---")
    display_signal_digest(scraped_insights)
    st.markdown("---")
    display_impact_heatmap(scraped_insights)
    st.markdown("---")
    display_journey_breakdown(scraped_insights)
    st.markdown("---")
    display_brand_comparator(scraped_insights)
    st.markdown("---")
    display_prd_bundler(scraped_insights)
