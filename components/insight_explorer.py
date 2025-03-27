# insight_explorer.py — Explorer Mode with styled card layout and doc dropdown

import streamlit as st
from slugify import slugify
import os
from components.ai_suggester import (
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket
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
        with st.container():
            summary = i.get("summary", i.get("text", "")[:80])
            text = i.get("text", "")
            brand = i.get("target_brand", "eBay")
            filename = slugify(summary)[:64]

            st.markdown(f"### 🧠 {summary}")
            cols = st.columns([2, 2, 2, 2])
            cols[0].markdown(f"**Score:** {i.get('score', 0)}")
            cols[1].markdown(f"**Type:** {i.get('type_tag')} > {i.get('type_subtag', '')}")
            cols[2].markdown(f"**Sentiment:** {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%)")
            cols[3].markdown(f"**Brand:** {brand}")

            st.markdown("**Feedback:**")
            st.markdown(f"> {text}")

            doc_type = st.selectbox("Generate document", ["PRD", "BRD", "PRFAQ", "JIRA"], key=f"explorer_doc_type_{idx}")
            if st.button(f"Generate {doc_type}", key=f"explorer_generate_{idx}"):
                with st.spinner(f"Generating {doc_type}..."):
                    if doc_type == "PRD":
                        file_path = generate_prd_docx(text, brand, filename)
                    elif doc_type == "BRD":
                        file_path = generate_brd_docx(text, brand, filename)
                    elif doc_type == "PRFAQ":
                        file_path = generate_prfaq_docx(text, brand, filename)
                    elif doc_type == "JIRA":
                        file_content = generate_jira_bug_ticket(text, brand)
                        st.download_button("⬇️ Download JIRA", file_content, file_name=f"jira-{filename}.md", mime="text/markdown", key=f"dl_jira_exp_{idx}")
                        file_path = None

                    if file_path and os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                f"⬇️ Download {doc_type}",
                                f,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_doc_exp_{idx}"
                            )
