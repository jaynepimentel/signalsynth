# app.py — Optimized for performance, clarity, and reliability

import os
import json
import streamlit as st
from dotenv import load_dotenv
from collections import Counter
from slugify import slugify
from datetime import datetime
from sentence_transformers import SentenceTransformer, util
import torch
st.set_page_config(page_title="SignalSynth", layout="wide")
st.title("📱 SignalSynth: Collectibles Insight Engine")
st.caption(f"🗕️ Last Updated: {datetime.now().strftime('%b %d, %Y %H:%M')}")

# Load embedding model with caching
@st.cache_resource(show_spinner="Loading sentence transformer model...")
def get_embedding_model():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    model = model.to(torch.device("cpu"))  # Ensure compatibility with CPU environments
    return model

model = get_embedding_model()

# Component imports
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
    generate_jira_bug_ticket,
    generate_gpt_doc,
    generate_multi_signal_prd
)
from components.strategic_tools import (
    display_signal_digest,
    display_journey_breakdown,
    display_brand_comparator,
    display_impact_heatmap,
    display_prd_bundler,
    display_spark_suggestions
)
from components.journey_heatmap import display_journey_heatmap

# App setup
load_dotenv()
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

# Hide sidebar
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none }
    section[data-testid="stSidebar"] { width: 0px !important; display: none }
    </style>
""", unsafe_allow_html=True)

# Intro guide
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    with st.expander("🧠 Welcome to SignalSynth! What Can You Do Here?", expanded=True):
        st.markdown("""
        SignalSynth helps you transform user signals into strategic action.

        **💥 Explore the full power of this tool:**
        - 🔍 Filter by brand, persona, journey stage, and sentiment
        - 📌 Click any insight to generate a PRD, BRD, PRFAQ, or JIRA ticket
        - 📈 Visualize trend shifts and brand sentiment
        - 🧠 Bundle insights, clarify vague signals, or suggest tags
        """)
        st.button("✅ Got it — Hide this guide", on_click=lambda: st.session_state.update({"show_intro": False}))

# Load insights
if os.path.exists("precomputed_insights.json"):
    with open("precomputed_insights.json", "r", encoding="utf-8") as f:
        scraped_insights = json.load(f)
    st.success(f"✅ Loaded {len(scraped_insights)} precomputed insights")
else:
    st.error("❌ No precomputed insights found.")
    st.stop()

# Filtering setup
filter_fields = {
    "Target Brand": "target_brand",
    "Persona": "persona",
    "Journey Stage": "journey_stage",
    "Insight Type": "type_tag",
    "Effort Estimate": "effort",
    "Brand Sentiment": "brand_sentiment",
    "Clarity": "clarity"
}

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800"
}

def badge(label, color):
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

# Tabs
TABS = [
    "📌 Insights", "🧱 Clusters", "🔎 Explorer", "📈 Trends", 
    "🔥 Emerging", "🧠 Strategic Tools", "📺 Journey Heatmap"
]
tabs = st.tabs(TABS)

# Tab 0: Insights
with tabs[0]:
    st.header("📌 Individual Insights")

    filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="insights")
    filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]

    INSIGHTS_PER_PAGE = 10
    total_pages = max(1, (len(filtered) + INSIGHTS_PER_PAGE - 1) // INSIGHTS_PER_PAGE)
    if "insights_page" not in st.session_state:
        st.session_state.insights_page = 1

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.insights_page = max(1, st.session_state.insights_page - 1)
    with col2:
        st.markdown(f"**Page {st.session_state.insights_page} of {total_pages}**")
    with col3:
        if st.button("Next ➡️"):
            st.session_state.insights_page = min(total_pages, st.session_state.insights_page + 1)

    start_idx = (st.session_state.insights_page - 1) * INSIGHTS_PER_PAGE
    paged_insights = filtered[start_idx:start_idx + INSIGHTS_PER_PAGE]

    for idx, i in enumerate(paged_insights, start=start_idx):
        text = i.get("text", "")
        if not text:
            st.warning("⚠️ Missing insight text.")
            continue

        st.markdown(f"### 🧠 Insight: {i.get('title', text[:60])}")
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

        with st.expander("🧮 Scoring Breakdown"):
            st.markdown(f"""
            - **Insight Score**: {i.get('score', 0)}
            - **Severity Score**: {i.get('severity_score', 0)}
            - **Type Confidence**: {i.get('type_confidence', 50)}%
            - **Sentiment Confidence**: {i.get('sentiment_confidence', 50)}%
            - **PM Priority Score**: {i.get('pm_priority_score', 0)}
            """)

        with st.expander("🧠 Full Insight"):
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

            if st.button("🧼 Clarify This Insight", key=f"clarify_{idx}"):
                with st.spinner("Clarifying..."):
                    prompt = f"Rewrite this vague user feedback in a clearer, more specific way:\n\n{text}"
                    clarified = generate_gpt_doc(prompt, "You are a PM rephrasing vague customer input.")
                    st.success("✅ Clarified Insight:")
                    st.markdown(f"> {clarified}")

            if st.button("🏷️ Suggest Tags", key=f"tags_{idx}"):
                with st.spinner("Analyzing..."):
                    prompt = f"""Suggest 3–5 product tags for this user feedback:\n\n{text}"""
                    tags = generate_gpt_doc(prompt, "You are tagging this signal with product themes.")
                    st.info("💡 Suggested Tags:")
                    st.markdown(f"`{tags}`")

            if st.button("🧹 Bundle Similar Insights", key=f"bundle_{idx}"):
                base_embed = model.encode(text, convert_to_tensor=True)
                all_texts = [x["text"] for x in filtered if x.get("text")]
                all_embeds = model.encode(all_texts, convert_to_tensor=True)
                similarities = util.pytorch_cos_sim(base_embed, all_embeds)[0]
                top_indices = similarities.argsort(descending=True)[:5]
                bundled = []
                st.markdown("**🧠 Related Insights:**")
                for j in top_indices:
                    try:
                        related = filtered[j]
                        st.markdown(f"- _{related['text'][:180]}_")
                        bundled.append(related["text"])
                    except IndexError:
                        continue

                if st.button("📄 Generate Combined PRD", key=f"bundle_prd_{idx}"):
                    file_path = generate_multi_signal_prd(bundled, filename=f"bundle-{idx}")
                    if file_path and os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                "⬇️ Download Combined PRD",
                                f,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_bundle_prd_{idx}"
                            )

        filename = slugify(i.get("title", text[:40]))[:64]
        doc_type = st.selectbox("Select document type to generate:", ["PRD", "BRD", "PRFAQ", "JIRA"], key=f"doc_type_{idx}")
        if st.button(f"Generate {doc_type}", key=f"generate_doc_{idx}"):
            with st.spinner(f"Generating {doc_type}..."):
                file_path = None
                if doc_type == "PRD":
                    file_path = generate_prd_docx(text, brand, filename)
                elif doc_type == "BRD":
                    file_path = generate_brd_docx(text, brand, filename + "-brd")
                elif doc_type == "PRFAQ":
                    file_path = generate_prfaq_docx(text, brand, filename + "-prfaq")
                elif doc_type == "JIRA":
                    content = generate_jira_bug_ticket(text, brand)
                    st.download_button("⬇️ Download JIRA", content, file_name=f"jira-{filename}.md", mime="text/markdown", key=f"dl_jira_{idx}")
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            f"⬇️ Download {doc_type}",
                            f,
                            file_name=os.path.basename(file_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_doc_{idx}"
                        )

# Other tabs
with tabs[1]:
    st.header("🧱 Clustered Insight Mode")
    try:
        display_clustered_insight_cards(scraped_insights)
    except Exception as e:
        st.error(f"⚠️ Cluster view error: {e}")

with tabs[2]:
    st.header("🔎 Insight Explorer")
    try:
        filters = render_floating_filters(scraped_insights, filter_fields, key_prefix="explorer")
        filtered = [i for i in scraped_insights if all(filters[k] == "All" or str(i.get(k, "Unknown")) == filters[k] for k in filters)]
        display_insight_explorer(filtered[:50])
    except Exception as e:
        st.error(f"⚠️ Explorer error: {e}")

with tabs[3]:
    st.header("📈 Trends + Brand Summary")
    try:
        display_insight_charts(scraped_insights)
        display_brand_dashboard(scraped_insights)
    except Exception as e:
        st.error(f"⚠️ Trend dashboard error: {e}")

with tabs[4]:
    st.header("🔥 Emerging Topics")
    try:
        trends = detect_emerging_topics(scraped_insights)
        render_emerging_topics(trends)
    except Exception as e:
        st.error(f"⚠️ Emerging topics error: {e}")

with tabs[5]:
    st.header("🧠 Strategic Tools")
    try:
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
    except Exception as e:
        st.error(f"⚠️ Strategic tools error: {e}")

with tabs[6]:
    st.header("📺 Journey Heatmap")
    try:
        display_journey_heatmap(scraped_insights)
    except Exception as e:
        st.error(f"⚠️ Heatmap failed: {e}")
