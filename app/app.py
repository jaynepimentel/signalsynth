import json
import os
from datetime import datetime

import streamlit as st


DATA_PATH = os.path.join("data", "processed", "insights.json")


st.set_page_config(page_title="SignalSynth – PM Insights", layout="wide")
st.title("📡 SignalSynth: Collectibles Insight Engine")
st.caption(f"Local PM UI • Loaded at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


@st.cache_data(show_spinner="Loading processed insights…")
def load_insights(path: str):
    if not os.path.exists(path):
        st.error(f"Processed insights file not found: {path}")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            st.error("Expected insights.json to be a list of objects")
            return []
        return data
    except Exception as e:
        st.error(f"Failed to load insights: {e}")
        return []


insights = load_insights(DATA_PATH)

if not insights:
    st.info("No insights loaded yet. Run the scraper, then the pipeline, then refresh this page.")
    st.stop()


total = len(insights)
payments = sum(1 for i in insights if i.get("_payment_issue"))
upi = sum(1 for i in insights if i.get("_upi_flag"))
high_asp = sum(1 for i in insights if i.get("_high_end_flag"))
price_guide = sum(1 for i in insights if i.get("is_price_guide_signal"))


c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("All Insights", f"{total:,}")
with c2:
    st.metric("Payments Signals", f"{payments:,}")
with c3:
    st.metric("UPI Signals", f"{upi:,}")
with c4:
    st.metric("High-ASP Flags", f"{high_asp:,}")
with c5:
    st.metric("Price Guide / Scan", f"{price_guide:,}")


st.subheader("Insights (sample)")

source_filter = st.multiselect(
    "Source",
    options=sorted({i.get("source", "Unknown") for i in insights}),
    default=[],
)


def passes_source_filter(i):
    if not source_filter:
        return True
    return i.get("source", "Unknown") in source_filter


filtered = [i for i in insights if passes_source_filter(i)]

for i in filtered[:200]:
    with st.expander(f"{i.get('source', 'Unknown')} • {i.get('post_date', 'Unknown')} • {i.get('topic_hint') or i.get('topic_focus') or ''}"):
        st.write(i.get("text", ""))
        meta_cols = st.columns(4)
        with meta_cols[0]:
            st.caption(f"Sentiment: {i.get('brand_sentiment', 'Unknown')}")
        with meta_cols[1]:
            st.caption(f"Persona: {i.get('persona', 'Unknown')}")
        with meta_cols[2]:
            st.caption(f"Journey: {i.get('journey_stage', 'Unknown')}")
        with meta_cols[3]:
            st.caption(f"Payments: {'Yes' if i.get('_payment_issue') else 'No'} • UPI: {'Yes' if i.get('_upi_flag') else 'No'}")

        if i.get("url"):
            st.markdown(f"[Open source]({i['url']})")

        if i.get("top_comments"):
            st.markdown("**Top comments:**")
            for c in i["top_comments"]:
                st.markdown(f"- {c}")
