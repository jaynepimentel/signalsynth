# app.py — SignalSynth with AI-synthesized clusters and strategic UI
import streamlit as st
from utils.load_scraped_insights import load_scraped_posts, process_insights
from components.signal_scorer import filter_relevant_insights
from components.brand_trend_dashboard import display_brand_dashboard
from components.cluster_synthesizer import generate_synthesized_insights
from collections import Counter

st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")

# Load and score insights
raw_posts = load_scraped_posts()
processed = process_insights(raw_posts)
scraped_insights = filter_relevant_insights(processed, min_score=3)

# Add sidebar confirmation of data loaded
st.sidebar.info(f"✅ {len(scraped_insights)} insights loaded")

if not scraped_insights:
    st.warning("⚠️ No insights found to analyze. Try rerunning the scraper or lowering the score threshold.")
    st.stop()

# Brand-level dashboard
with st.expander("📊 Brand Summary Dashboard", expanded=False):
    display_brand_dashboard(scraped_insights)

# AI-synthesized themes
with st.expander("🧠 AI-Synthesized Themes (Beta)", expanded=True):
    synth_cards = generate_synthesized_insights(scraped_insights)
    for card in synth_cards:
        st.markdown(f"### {card['title']}")
        st.caption(f"**Brand:** {card['brand']}")
        st.markdown(f"**Summary:** {card['summary']}")
        st.markdown("**Top Quotes:**")
        for q in card['quotes']:
            st.markdown(q)
        if card['top_ideas']:
            st.markdown("**Suggested PM Actions:**")
            for idea in card['top_ideas']:
                st.markdown(f"- {idea}")
        if card.get("tags"):
            st.markdown("**Tags:** " + ", ".join(card["tags"]))

# Trend tracking
topic_keywords = ["vault", "psa", "graded", "funko", "cancel", "authenticity", "shipping", "refund"]
trend_counter = Counter()
for i in scraped_insights:
    text = i.get("text", "").lower()
    for word in topic_keywords:
        if word in text:
            trend_counter[word] += 1
rising_trends = [t for t, count in trend_counter.items() if count >= 5]

# Sidebar filters
st.sidebar.header("🔍 Filter Insights")
status_filter = st.sidebar.selectbox("Workflow Stage", ["All"] + sorted(set(i.get("status", "Unknown") for i in scraped_insights)))
effort_filter = st.sidebar.selectbox("Effort Estimate", ["All"] + sorted(set(i.get("effort", "Unknown") for i in scraped_insights)))
type_filter = st.sidebar.selectbox("Insight Type", ["All"] + sorted(set(i.get("type_tag", "Unknown") for i in scraped_insights)))
persona_filter = st.sidebar.selectbox("Persona", ["All"] + sorted(set(i.get("persona", "Unknown") for i in scraped_insights)))
brand_filter = st.sidebar.selectbox("Target Brand", ["All"] + sorted(set(i.get("target_brand", "Unknown") for i in scraped_insights)))
sentiment_filter = st.sidebar.selectbox("Brand Sentiment", ["All"] + sorted(set(i.get("brand_sentiment", "Unknown") for i in scraped_insights)))
show_trends_only = st.sidebar.checkbox("Highlight Emerging Topics Only", value=False)

# Filter logic
filtered = []
for i in scraped_insights:
    text = i.get("text", "").lower()
    if (
        (status_filter == "All" or i.get("status") == status_filter)
        and (effort_filter == "All" or i.get("effort") == effort_filter)
        and (type_filter == "All" or i.get("type_tag") == type_filter)
        and (persona_filter == "All" or i.get("persona") == persona_filter)
        and (brand_filter == "All" or i.get("target_brand") == brand_filter)
        and (sentiment_filter == "All" or i.get("brand_sentiment") == sentiment_filter)
        and (not show_trends_only or any(word in text for word in rising_trends))
    ):
        filtered.append(i)

# Emerging trend list
if rising_trends:
    with st.expander("🔥 Emerging Trends Detected", expanded=True):
        for t in sorted(rising_trends):
            st.markdown(f"- **{t.title()}** ({trend_counter[t]} mentions)")
else:
    st.info("No trends above threshold this cycle.")

# Show filtered insights
for idx, i in enumerate(filtered):
    insight_type = i.get("type", "🧠 Insight")
    summary = i.get("summary", i.get("text", "")[:80])
    score = i.get("score", 0)
    effort = i.get("effort", "Unknown")
    type_tag = i.get("type_tag", "Unclear")
    confidence = i.get("type_confidence", 0)
    reason = i.get("type_reason", "")
    brand = i.get("target_brand", "Unknown")
    sentiment = i.get("brand_sentiment", "Unknown")
    subtag = i.get("type_subtag", "General")
    sent_conf = i.get("sentiment_confidence", "N/A")

    st.markdown(f"### {insight_type} — {summary}")
    st.caption(f"Score: {score} | Type: {type_tag} > {subtag} ({confidence}%) | Effort: {effort} | Brand: {brand} | Sentiment: {sentiment} ({sent_conf}%)")

    if reason:
        st.markdown(f"💡 *Reason:* _{reason}_")

    with st.expander(f"🧠 Full Insight ({i.get('status', 'Unknown')})"):
        st.write(f"**Persona:** {i.get('persona', 'Unknown')}")
        st.write(f"**Source:** {i.get('source', 'N/A')} | Last Updated: {i.get('last_updated', 'N/A')} | Score: {score}")

        st.markdown("**User Quotes:**")
        for quote in i.get("cluster", []):
            st.markdown(f"- _{quote}_")

        if i.get("ideas"):
            st.markdown("**AI-Suggested Ideas:**")
            for idx2, idea in enumerate(i["ideas"]):
                st.markdown(f"- {idea}")
                st.button(
                    label=f"Create JIRA Ticket: {idea[:30]}...",
                    key=f"jira_{idx}_{idx2}",
                    help="(Simulated) This would create a JIRA epic with linked context."
                )

        if st.button(f"Generate PRD for: {summary[:30]}...", key=f"prd_{idx}"):
            st.success("✅ PRD Generated! (this would be sent to Airtable or JIRA in prod)")

st.sidebar.markdown("---")
st.sidebar.caption("Powered by your strategy + user signal ✨")
