# insight_explorer.py — Insight Explorer Mode with search, filter, and dynamic preview

import streamlit as st

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

    st.subheader("🔍 Insight Explorer")
    query = st.text_input("Search insights (keywords, issues, or quotes)")

    # Extract unique options
    all_tags = sorted({i.get("type_subtag", "General") for i in insights})
    all_brands = sorted({i.get("target_brand", "Unknown") for i in insights})
    all_sentiments = sorted({i.get("brand_sentiment", "Neutral") for i in insights})

    # Filters
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

    # Optional sorting
    sort_field = st.selectbox("Sort by", ["score", "type_tag", "target_brand", "brand_sentiment"])
    results = sorted(results, key=lambda x: x.get(sort_field, ""), reverse=True if sort_field == "score" else False)

    # Display insights
    for idx, i in enumerate(results[:100]):  # limit to 100 to keep it fast
        with st.expander(f"🧠 {i.get('summary', i.get('text')[:80])}"):
            st.markdown(f"- **Brand:** {i.get('target_brand')}")
            st.markdown(f"- **Sentiment:** {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%)")
            st.markdown(f"- **Type:** {i.get('type_tag')} > {i.get('type_subtag')}")
            st.markdown(f"- **Persona:** {i.get('persona', 'Unknown')}")
            st.markdown(f"- **Effort Estimate:** {i.get('effort', 'N/A')}")
            st.markdown(f"- **Score:** {i.get('score', 0)}")

            st.markdown("**Original Feedback:**")
            st.markdown(f"> {i.get('text')}")

            if i.get("ideas"):
                st.markdown("**💡 PM Suggestions:**")
                for idea in i["ideas"]:
                    st.markdown(f"- {idea}")