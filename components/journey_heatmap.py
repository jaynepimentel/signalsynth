# journey_heatmap.py — Enhanced with competitor + Live Commerce segmentation

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def display_journey_heatmap(insights):
    st.header("🧭 Persona × Journey Stage Heatmap")

    df = pd.DataFrame(insights)
    if "persona" not in df.columns or "journey_stage" not in df.columns:
        st.warning("Missing persona or journey stage data.")
        return

    # Toggle for metric (count vs priority)
    if "journey_heatmap_metric" not in st.session_state:
        st.session_state.journey_heatmap_metric = "count"
    metric_toggle = st.radio(
        "Switch Metric",
        options=["Count", "Priority"],
        index=0 if st.session_state.journey_heatmap_metric == "count" else 1,
        horizontal=True,
        key="journey_heatmap_radio"
    )
    st.session_state.journey_heatmap_metric = metric_toggle.lower()
    metric = st.session_state.journey_heatmap_metric

    # Filter dropdown for competitor or Live
    brands = sorted(set(df.get("target_brand", "Unknown")))
    competitors = sorted(set(b for b in brands if b.lower() not in ["ebay", "unknown"]))
    filter_options = ["All Insights", "Live Commerce Only"] + competitors

    selected_filter = st.selectbox("Filter by Competitor or Topic", filter_options, index=0)

    if selected_filter == "Live Commerce Only":
        df = df[df["topic_focus_str"].str.contains("Live Shopping|Case Break", na=False)]
    elif selected_filter != "All Insights":
        df = df[df["target_brand"].str.lower() == selected_filter.lower()]

    if df.empty:
        st.info("No matching insights to visualize.")
        return

    # Heatmap logic
    if metric == "priority":
        if "pm_priority_score" not in df.columns:
            st.warning("Missing pm_priority_score field.")
            return
        heat_df = df.pivot_table(
            index="persona",
            columns="journey_stage",
            values="pm_priority_score",
            aggfunc="mean"
        ).fillna(0)
        title = f"🔍 Avg PM Priority — {selected_filter}"
        fmt = ".1f"
    else:
        heat_df = df.groupby(["persona", "journey_stage"]).size().unstack(fill_value=0)
        title = f"🔍 Insight Count — {selected_filter}"
        fmt = "d"

    if heat_df.empty:
        st.info("Not enough data to render heatmap.")
        return

    st.markdown(f"### 📊 {title}")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.heatmap(heat_df, annot=True, fmt=fmt, cmap="YlOrRd", linewidths=0.5)
    st.pyplot(fig)
