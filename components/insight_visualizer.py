# insight_explorer.py - Explorer Mode with styled card layout and GPT utilities (FULLY UPDATED)
import streamlit as st
from slugify import slugify
import os
import json
from components.ai_suggester import (
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket,
    generate_gpt_doc
)

def filter_insights_by_search(insights, query, selected_tags=[], selected_brands=[], selected_sentiments=[]):
    results = []
    query = query.lower()
    for i in insights:
        text = i.get("text", "").lower()
        if query and query not in text:
            continue
        if selected_tags and i.get("type_subtag") not in selected_tags:
            continue
        if selected_brands and i.get("target_brand") not in selected_brands:
            continue
        if selected_sentiments and i.get("brand_sentiment") not in selected_sentiments:
            continue
        results.append(i)
    return results

def render_document_buttons(insight, idx):
    """Universal document generation buttons for any insight card"""
    text = insight.get("text", "")
    brand = insight.get("target_brand", "eBay")
    summary = insight.get("summary", text[:80])
    filename = slugify(summary)[:64]
    
    cols = st.columns(4)
    
    # PRD Button
    if cols[0].button("📝 PRD", key=f"prd_{idx}"):
        with st.spinner("Generating PRD..."):
            file_path = generate_prd_docx(text, brand, filename)
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    st.download_button(
                        "⬇️ PRD",
                        f,
                        file_name=os.path.basename(file_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_prd_{idx}"
                    )
    
    # JIRA Button
    if cols[3].button("🐞 JIRA", key=f"jira_{idx}"):
        with st.spinner("Generating JIRA..."):
            file_content = generate_jira_bug_ticket(text, brand)
            st.download_button(
                "⬇️ JIRA",
                file_content,
                file_name=f"jira-{filename}.md",
                mime="text/markdown",
                key=f"dl_jira_{idx}"
            )

def display_insight_explorer(insights):
    if not insights:
        st.info("No insights to explore yet.")
        return

    st.subheader("🔎 Insight Explorer")
    query = st.text_input("Search insights (keywords, issues, or quotes)")

    all_tags = sorted({i.get("type_subtag", "General") for i in insights})
    all_brands = sorted({i.get("target_brand", "Unknown") for i in insights})
    all_sentiments = sorted({i.get("brand_sentiment", "Neutral") for i in insights})

    with st.expander("🔎 Advanced Filters"):
        selected_tags = st.multiselect("Subtags", options=all_tags)
        selected_brands = st.multiselect("Brands", options=all_brands)
        selected_sentiments = st.multiselect("Sentiments", options=all_sentiments)

    results = filter_insights_by_search(
        insights,
        query,
        selected_tags,
        selected_brands,
        selected_sentiments,
    )

    st.success(f"{len(results)} results match your filters")

    sort_field = st.selectbox("Sort by", ["score", "type_tag", "target_brand", "brand_sentiment"])
    results = sorted(results, key=lambda x: x.get(sort_field, ""), reverse=True if sort_field == "score" else False)

    for idx, i in enumerate(results[:100]):
        with st.container(border=True):
            summary = i.get("summary", i.get("text", "")[:80])
            text = i.get("text", "")
            brand = i.get("target_brand", "eBay")

            st.markdown(f"### 🧠 {summary}")
            cols = st.columns([2, 2, 2, 2])
            cols[0].markdown(f"**Score:** {i.get('score', 0)}")
            cols[1].markdown(f"**Type:** {i.get('type_tag')} > {i.get('type_subtag', '')}")
            cols[2].markdown(f"**Sentiment:** {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%)")
            cols[3].markdown(f"**Brand:** {brand}")

            with st.expander("🧮 Scoring Breakdown"):
                st.markdown(f"""
                - **Insight Score:** {i.get("score", 0)}
                - **Severity Score:** {i.get("severity_score", 0)}
                - **Type Confidence:** {i.get("type_confidence", 50)}%
                - **Sentiment Confidence:** {i.get("sentiment_confidence", 50)}%
                - **PM Priority Score:** {i.get("pm_priority_score", 0)}
                """)

            st.markdown("**Feedback:**")
            st.markdown(f"> {text}")

            # ✨ GPT Actions
            with st.expander("✨ GPT Tools"):
                if st.button("🧼 Clarify This Insight", key=f"clarify_exp_{idx}"):
                    with st.spinner("Clarifying..."):
                        clarify_prompt = f"Rewrite this vague user feedback in a clearer, more specific way:\n\n{text}"
                        clarified = generate_gpt_doc(clarify_prompt, "You are rephrasing unclear feedback.")
                        st.success("✅ Clarified Insight:")
                        st.markdown(f"> {clarified}")

                if st.button("🏷️ Suggest Tags", key=f"tags_exp_{idx}"):
                    with st.spinner("Analyzing..."):
                        tag_prompt = f"""Suggest 3–5 product tags or themes based on this user signal:\n\n{text}"""
                        tag_output = generate_gpt_doc(tag_prompt, "You are tagging feedback into product themes.")
                        st.info("💡 Suggested Tags:")
                        st.markdown(f"`{tag_output}`")

            # Universal document buttons
            render_document_buttons(i, idx)
