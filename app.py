# app.py — SignalSynth UI with merged Explorer, GPT, and Cluster View with filters and trends

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
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket
)

load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))
st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"📅 Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# Load insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found. Please run `precompute_insights.py`.")
    st.stop()

st.sidebar.header("⚙️ Settings")
use_gpt = st.sidebar.checkbox("💡 Enable GPT-4 PM Suggestions", value=OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("⚠️ Missing OpenAI API Key — GPT disabled.")

# Sidebar filters
st.sidebar.header("🔍 Filter Insights")
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
filters = {
    key: st.sidebar.selectbox(label, ["All"] + sorted({str(i.get(key, "Unknown")) for i in scraped_insights}), key=f"sidebar_{key}")
    for label, key in filter_fields.items()
}

show_trends_only = st.sidebar.checkbox("Highlight Emerging Topics Only", value=False)

# Keyword trends
topic_keywords = ["vault", "psa", "graded", "fanatics", "cancel", "authenticity", "shipping", "refund"]
trend_counter = Counter()
for i in scraped_insights:
    text = i.get("text", "").lower()
    for word in topic_keywords:
        if word in text:
            trend_counter[word] += 1
rising_trends = [t for t, count in trend_counter.items() if count >= 5]

if rising_trends:
    with st.expander("🔥 Emerging Trends Detected", expanded=True):
        for t in sorted(rising_trends):
            st.markdown(f"- **{t.title()}** ({trend_counter[t]} mentions)")
else:
    st.info("No trends above threshold this cycle.")

# Filtering
filtered = [
    i for i in scraped_insights
    if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)
    and (not show_trends_only or any(w in i.get("text", "").lower() for w in rising_trends))
]

# Summary + dashboard
st.subheader("📊 Brand Summary")
display_brand_dashboard(scraped_insights)

st.subheader("📈 Insight Trends")
display_insight_charts(scraped_insights)

# Explorer
st.subheader("🧭 Insight Explorer")
display_insight_explorer(filtered[:25])

# Individual View
st.subheader("📌 Individual Insights")
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

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800"
}

def badge(label, color):
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

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

        if use_gpt and OPENAI_KEY_PRESENT:
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

# Clustered view
st.subheader("🧱 Clustered Insight Mode")
display_clustered_insight_cards(filtered)

st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨")
