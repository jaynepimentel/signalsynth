# insight_explorer.py — updated with topic_focus filtering
import streamlit as st

def filter_insights_by_search(insights, query, selected_tags=[], selected_brands=[], selected_sentiments=[], selected_topics=[]):
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
        if selected_topics and not any(t in i.get("topic_focus", []) for t in selected_topics):
            continue

        results.append(i)
    return results

def display_insight_explorer(insights):
    if not insights:
        st.info("No insights to explore yet.")
        return

    st.subheader("🔎 Insight Explorer")
    query = st.text_input("Search text")

    all_tags = sorted({i.get("type_subtag", "General") for i in insights})
    all_brands = sorted({i.get("target_brand", "Unknown") for i in insights})
    all_sentiments = sorted({i.get("brand_sentiment", "Neutral") for i in insights})
    all_topics = sorted({t for i in insights for t in i.get("topic_focus", [])})

    selected_tags = st.multiselect("Subtags", options=all_tags)
    selected_brands = st.multiselect("Brands", options=all_brands)
    selected_sentiments = st.multiselect("Sentiments", options=all_sentiments)
    selected_topics = st.multiselect("Topic Focus", options=all_topics)

    results = filter_insights_by_search(
        insights,
        query,
        selected_tags,
        selected_brands,
        selected_sentiments,
        selected_topics
    )

    st.success(f"{len(results)} results match your filters")

    return results