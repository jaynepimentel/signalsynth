# components/emerging_themes.py

import streamlit as st
from collections import Counter

def detect_emerging_topics(insights, keywords=None, threshold=5):
    """
    Identifies emerging topics based on keyword frequency.
    Returns a list of (keyword, count) tuples.
    """
    if not keywords:
        keywords = [
            "vault", "psa", "graded", "fanatics", "cancel",
            "authenticity", "shipping", "refund", "fees",
            "tracking", "return", "delay", "counterfeit"
        ]

    trend_counter = Counter()
    for i in insights:
        text = i.get("text", "").lower()
        for word in keywords:
            if word in text:
                trend_counter[word] += 1

    return [(k, v) for k, v in trend_counter.items() if v >= threshold]


def render_emerging_topics(topics):
    """
    Renders a bullet list of trending keywords with mention counts.
    """
    if topics:
        st.success("🔥 Emerging Topics Detected")
        for word, count in sorted(topics, key=lambda x: -x[1]):
            st.markdown(f"- **{word.title()}** ({count} mentions)")
    else:
        st.info("No trends above threshold this cycle.")