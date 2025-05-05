# insight_explorer.py - Explorer Mode with styled card layout and GPT utilities
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
    """Filter insights based on search query and selected filters"""
    results = []
    query = query.lower()
    for insight in insights:
        text = insight.get("text", "").lower()
        if query and query not in text:
            continue
        if selected_tags and insight.get("type_subtag") not in selected_tags:
            continue
        if selected_brands and insight.get("target_brand") not in selected_brands:
            continue
        if selected_sentiments and insight.get("brand_sentiment") not in selected_sentiments:
            continue
        results.append(insight)
    return results

def display_insight_explorer(insights):
    """Main explorer view with document generation buttons per insight"""
    if not insights:
        st.info("No insights to explore yet.")
        return

    st.subheader("🔎 Insight Explorer")
    
    # Search and filters
    query = st.text_input("Search insights (keywords, issues, or quotes)")
    all_tags = sorted({i.get("type_subtag", "General") for i in insights})
    all_brands = sorted({i.get("target_brand", "Unknown") for i in insights})
    all_sentiments = sorted({i.get("brand_sentiment", "Neutral") for i in insights})

    with st.expander("🔎 Advanced Filters"):
        selected_tags = st.multiselect("Subtags", options=all_tags)
        selected_brands = st.multiselect("Brands", options=all_brands)
        selected_sentiments = st.multiselect("Sentiments", options=all_sentiments)

    # Filter results
    results = filter_insights_by_search(
        insights, query, selected_tags, selected_brands, selected_sentiments
    )
    
    if not results:
        st.warning("No matching insights found")
        return

    st.success(f"📊 {len(results)} insights match your filters")
    
    # Sorting
    sort_field = st.selectbox("Sort by", ["score", "type_tag", "target_brand", "brand_sentiment"])
    results = sorted(results, key=lambda x: x.get(sort_field, ""), reverse=sort_field == "score")

    # Display insights
    for idx, insight in enumerate(results[:100]):  # Limit to 100 for performance
        with st.container(border=True):
            # Header section
            summary = insight.get("summary", insight.get("text", "")[:80])
            st.markdown(f"### 🧠 {summary}")
            
            # Metadata columns
            cols = st.columns(4)
            cols[0].markdown(f"**Score:** {insight.get('score', 0)}")
            cols[1].markdown(f"**Type:** {insight.get('type_tag')} > {insight.get('type_subtag', '')}")
            cols[2].markdown(f"**Sentiment:** {insight.get('brand_sentiment')} ({insight.get('sentiment_confidence')}%)")
            cols[3].markdown(f"**Brand:** {insight.get('target_brand', 'Unknown')}")

            # Scoring details
            with st.expander("🧮 Scoring Breakdown"):
                st.markdown(f"""
                - **Insight Score:** {insight.get("score", 0)}
                - **Severity Score:** {insight.get("severity_score", 0)}
                - **Type Confidence:** {insight.get("type_confidence", 50)}%
                - **Sentiment Confidence:** {insight.get("sentiment_confidence", 50)}%
                - **PM Priority Score:** {insight.get("pm_priority_score", 0)}
                """)

            # Original feedback
            st.markdown(f"**Feedback:**\n> {insight.get('text', '')}")

            # GPT Tools
            with st.expander("✨ AI Enhancement Tools"):
                gpt_col1, gpt_col2 = st.columns(2)
                
                if gpt_col1.button("🧼 Clarify Insight", key=f"clarify_{idx}"):
                    with st.spinner("Clarifying..."):
                        clarified = generate_gpt_doc(
                            f"Rewrite this vague feedback clearly:\n{insight['text']}",
                            "You are rephrasing unclear feedback."
                        )
                        st.success("✅ Clarified:")
                        st.markdown(f"> {clarified}")
                
                if gpt_col2.button("🏷️ Suggest Tags", key=f"tags_{idx}"):
                    with st.spinner("Analyzing..."):
                        tags = generate_gpt_doc(
                            f"Suggest 3–5 product tags for:\n{insight['text']}",
                            "You are tagging feedback into product themes."
                        )
                        st.info("💡 Suggested Tags:")
                        st.markdown(f"`{tags}`")

            # Document generation buttons
            doc_cols = st.columns(4)
            filename = slugify(summary)[:64]
            brand = insight.get("target_brand", "eBay")
            
            # PRD Generation
            if doc_cols[0].button("📝 PRD", key=f"prd_{idx}"):
                with st.spinner("Generating PRD..."):
                    try:
                        prd_path = generate_prd_docx(insight["text"], brand, filename)
                        if os.path.exists(prd_path):
                            with open(prd_path, "rb") as f:
                                doc_cols[0].download_button(
                                    "⬇️ Download PRD",
                                    f.read(),
                                    file_name=f"prd_{filename}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_prd_{idx}"
                                )
                    except Exception as e:
                        st.error(f"PRD generation failed: {str(e)}")
            
            # BRD Generation
            if doc_cols[1].button("📋 BRD", key=f"brd_{idx}"):
                with st.spinner("Generating BRD..."):
                    try:
                        brd_path = generate_brd_docx(insight["text"], brand, filename)
                        if os.path.exists(brd_path):
                            with open(brd_path, "rb") as f:
                                doc_cols[1].download_button(
                                    "⬇️ Download BRD",
                                    f.read(),
                                    file_name=f"brd_{filename}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_brd_{idx}"
                                )
                    except Exception as e:
                        st.error(f"BRD generation failed: {str(e)}")
            
            # JIRA Generation
            if doc_cols[3].button("🐞 JIRA", key=f"jira_{idx}"):
                with st.spinner("Generating JIRA ticket..."):
                    try:
                        jira_content = generate_jira_bug_ticket(insight["text"], brand)
                        doc_cols[3].download_button(
                            "⬇️ Download JIRA",
                            jira_content,
                            file_name=f"jira_{filename}.md",
                            mime="text/markdown",
                            key=f"dl_jira_{idx}"
                        )
                    except Exception as e:
                        st.error(f"JIRA generation failed: {str(e)}")
