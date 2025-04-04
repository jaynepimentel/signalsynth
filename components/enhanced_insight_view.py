# enhanced_insight_view.py — Final merged version with advanced fields, badges, dev visibility, and GPT tools

import os
import streamlit as st
from slugify import slugify
from sentence_transformers import util
from components.ai_suggester import (
    generate_pm_ideas, generate_prd_docx, generate_brd_docx,
    generate_prfaq_docx, generate_jira_bug_ticket, generate_gpt_doc,
    generate_multi_signal_prd
)

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Discovery": "#90BE6D", "Purchase": "#F8961E", "Fulfillment": "#577590",
    "Post-Purchase": "#43AA8B", "Live Shopping": "#BC6FF1", "Search": "#118AB2",
    "Developer": "#7F00FF", "Buyer": "#38B000", "Seller": "#FF6700", "Collector": "#9D4EDD",
    "Vault": "#5F0F40", "PSA": "#FFB703", "Live": "#1D3557",
    "Post-Event": "#264653", "Canada": "#F72585", "Japan": "#7209B7", "Europe": "#3A0CA3"
}

def badge(label, color):
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

def render_insight_cards(filtered, model, per_page=10, key_prefix="insight"):
    if not filtered:
        st.info("No matching insights.")
        return

    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    page_key = f"{key_prefix}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous", key=f"{key_prefix}_prev"):
            st.session_state[page_key] = max(1, st.session_state[page_key] - 1)
    with col2:
        st.markdown(f"**Page {st.session_state[page_key]} of {total_pages}**")
    with col3:
        if st.button("Next ➡️", key=f"{key_prefix}_next"):
            st.session_state[page_key] = min(total_pages, st.session_state[page_key] + 1)

    start = (st.session_state[page_key] - 1) * per_page
    paged = filtered[start:start + per_page]

    for idx, i in enumerate(paged, start=start):
        unique_id = f"{key_prefix}_{idx}"
        st.markdown(f"### 🧠 Insight: {i.get('title', i.get('text', '')[:60])}")

        tags = [
            badge(i.get("type_tag"), BADGE_COLORS.get(i.get("type_tag"), "#ccc")),
            badge(i.get("brand_sentiment"), BADGE_COLORS.get(i.get("brand_sentiment"), "#ccc")),
            badge(i.get("effort"), BADGE_COLORS.get(i.get("effort"), "#ccc")),
            badge(i.get("journey_stage"), BADGE_COLORS.get(i.get("journey_stage"), "#ccc")),
            badge(i.get("clarity"), BADGE_COLORS.get(i.get("clarity"), "#ccc"))
        ]
        if i.get("signal_intent"): tags.append(badge(i["signal_intent"], BADGE_COLORS.get(i["signal_intent"], "#ccc")))
        if i.get("cohort"): tags.append(badge(i["cohort"], "#390099"))
        if i.get("region") and i["region"] != "Unknown": tags.append(badge(i["region"], BADGE_COLORS.get(i["region"], "#ccc")))
        if i.get("is_post_event_feedback"): tags.append(badge("Post-Event", BADGE_COLORS["Post-Event"]))
        if i.get("is_dev_feedback"): tags.append(badge("Developer", BADGE_COLORS["Developer"]))

        st.markdown(" ".join(tags), unsafe_allow_html=True)

        st.caption(
            f"Score: {i.get('score', 0)} | Intent: {i.get('signal_intent')} | Feature: {', '.join(i.get('feature_area', []))} | Type: {i.get('type_tag')} > {i.get('type_subtag', '')} "
            f"({i.get('type_confidence')}%) | Persona: {i.get('persona')} | Cohort: {i.get('cohort')} | Region: {i.get('region')} | "
            f"Post Date: {i.get('post_date') or i.get('_logged_date', 'N/A')}"
        )

        if i.get("url"):
            st.markdown(f"[🔗 View Original Post]({i['url']})", unsafe_allow_html=True)

        with st.expander("🧠 Full Insight"):
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
