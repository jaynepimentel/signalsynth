import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import Counter

# Component imports
from components.brand_trend_dashboard import display_brand_dashboard
from components.insight_visualizer import display_insight_charts
from components.insight_explorer import display_insight_explorer
from components.ai_suggester import (
    generate_pm_ideas,
    generate_prd_docx,
    generate_brd_docx,
    generate_jira_bug_ticket
)

# Load OpenAI key
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")

# Load insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found. Please run `precompute_insights.py` first.")
    st.stop()

# Sidebar
st.sidebar.header("⚙️ Settings")
use_gpt = st.sidebar.checkbox("💡 Enable GPT-4 PM Suggestions", value=True and OPENAI_KEY_PRESENT)
if use_gpt and not OPENAI_KEY_PRESENT:
    st.sidebar.warning("⚠️ No OpenAI API key found — GPT suggestions will be skipped.")

# Sidebar filters
st.sidebar.header("🔍 Filter Insights")
team_filter = st.sidebar.selectbox("Scrum Team", ["All"] + sorted(set(i.get("team", "Unknown") for i in scraped_insights)))
status_filter = st.sidebar.selectbox("Workflow Stage", ["All"] + sorted(set(i.get("status", "Unknown") for i in scraped_insights)))
effort_filter = st.sidebar.selectbox("Effort Estimate", ["All"] + sorted(set(i.get("effort", "Unknown") for i in scraped_insights)))
type_filter = st.sidebar.selectbox("Insight Type", ["All"] + sorted(set(i.get("type_tag", "Unknown") for i in scraped_insights)))
persona_filter = st.sidebar.selectbox("Persona", ["All"] + sorted(set(i.get("persona", "Unknown") for i in scraped_insights)))
brand_filter = st.sidebar.selectbox("Target Brand", ["All"] + sorted(set(i.get("target_brand", "Unknown") for i in scraped_insights)))
sentiment_filter = st.sidebar.selectbox("Brand Sentiment", ["All"] + sorted(set(i.get("brand_sentiment", "Unknown") for i in scraped_insights)))
show_trends_only = st.sidebar.checkbox("Highlight Emerging Topics Only", value=False)

# Dashboards
st.subheader("📊 Brand Summary Dashboard")
display_brand_dashboard(scraped_insights)

st.subheader("📈 Insight Charts")
display_insight_charts(scraped_insights)

# Trending detection
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

# Filter insights
filtered = []
for i in scraped_insights:
    text = i.get("text", "").lower()
    if (
        (team_filter == "All" or i.get("team") == team_filter) and
        (status_filter == "All" or i.get("status") == status_filter) and
        (effort_filter == "All" or i.get("effort") == effort_filter) and
        (type_filter == "All" or i.get("type_tag") == type_filter) and
        (persona_filter == "All" or i.get("persona") == persona_filter) and
        (brand_filter == "All" or i.get("target_brand") == brand_filter) and
        (sentiment_filter == "All" or i.get("brand_sentiment") == sentiment_filter) and
        (not show_trends_only or any(word in text for word in rising_trends))
    ):
        filtered.append(i)

# Pagination setup
INSIGHTS_PER_PAGE = 10
total_pages = max(1, (len(filtered) + INSIGHTS_PER_PAGE - 1) // INSIGHTS_PER_PAGE)

if "page" not in st.session_state:
    st.session_state.page = 1

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅️ Previous") and st.session_state.page > 1:
        st.session_state.page -= 1
with col2:
    st.markdown(f"**Page {st.session_state.page} of {total_pages}**", unsafe_allow_html=True)
with col3:
    if st.button("Next ➡️") and st.session_state.page < total_pages:
        st.session_state.page += 1

start_idx = (st.session_state.page - 1) * INSIGHTS_PER_PAGE
end_idx = start_idx + INSIGHTS_PER_PAGE
paged_insights = filtered[start_idx:end_idx]

# Show insights
for idx, i in enumerate(paged_insights, start=start_idx):
    summary = i.get("summary") or i.get("text", "")[:80]
    st.markdown(f"### 🧠 Insight: {summary}")

    st.caption(
        f"Score: {i.get('score', 0)} | Type: {i.get('type_tag')} > {i.get('type_subtag', '')} "
        f"({i.get('type_confidence')}%) | Effort: {i.get('effort')} | Brand: {i.get('target_brand')} | "
        f"Sentiment: {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%) | Persona: {i.get('persona')}"
    )

    if i.get("type_reason"):
        st.markdown(f"💡 *Reason:* _{i['type_reason']}_")

    with st.expander(f"🧠 Full Insight ({i.get('status', 'Unknown')})"):
        st.write(f"**Persona:** {i.get('persona', 'Unknown')}")
        st.write(f"**Scrum Team:** {i.get('team', 'Triage')} | Source: {i.get('source', 'N/A')} | "
                 f"Last Updated: {i.get('last_updated', 'N/A')} | Score: {i.get('score', 0)}")

        st.markdown("**User Quotes:**")
        for quote in i.get("cluster", []):
            st.markdown(f"- _{quote}_")

        insight_text = i["text"]
        brand = i.get("target_brand", "eBay")
        safe_summary = "".join(c for c in summary if c.isalnum() or c in (" ", "_", "-")).rstrip()

        if use_gpt and OPENAI_KEY_PRESENT:
            with st.spinner("💡 Generating PM Suggestions..."):
                try:
                    i["ideas"] = generate_pm_ideas(insight_text, brand)
                except Exception as e:
                    i["ideas"] = [f"[❌ GPT error: {str(e)}]"]

        if i.get("ideas"):
            st.markdown("**💡 PM Suggestions:**")
            for idx2, idea in enumerate(i["ideas"]):
                st.markdown(f"- {idea}")

        if st.button(f"📄 Generate PRD", key=f"gen_prd_{idx}"):
            file_path = generate_prd_docx(insight_text, brand, f"PRD - {safe_summary}")
            with open(file_path, "rb") as f:
                st.download_button("⬇️ Download PRD", f, file_name=os.path.basename(file_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        if st.button(f"📄 Generate BRD", key=f"gen_brd_{idx}"):
            file_path = generate_brd_docx(insight_text, brand, f"BRD - {safe_summary}")
            with open(file_path, "rb") as f:
                st.download_button("⬇️ Download BRD", f, file_name=os.path.basename(file_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        if st.button(f"🐞 Generate JIRA Bug Ticket", key=f"gen_jira_{idx}"):
            bug = generate_jira_bug_ticket(insight_text, brand)
            st.code(bug, language="markdown")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("🔁 Powered by strategic signal + customer voice ✨"