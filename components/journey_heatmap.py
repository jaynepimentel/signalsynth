# journey_heatmap.py — Persona × Journey Stage heatmap view

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def display_journey_heatmap(insights, metric="count"):
    st.header("🧭 Persona × Journey Stage Heatmap")

    df = pd.DataFrame(insights)
    if "persona" not in df.columns or "journey_stage" not in df.columns:
        st.warning("Missing persona or journey stage data.")
        return

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
        title = "Average PM Priority by Persona × Journey"
        fmt = ".1f"
    else:
        heat_df = df.groupby(["persona", "journey_stage"]).size().unstack(fill_value=0)
        title = "Count of Insights by Persona × Journey"
        fmt = "d"

    if heat_df.empty:
        st.info("Not enough data to render heatmap.")
        return

    st.markdown(f"### 📊 {title}")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.heatmap(heat_df, annot=True, fmt=fmt, cmap="YlOrRd", linewidths=0.5)
    st.pyplot(fig)

    # Toggle between metrics
    toggle = st.radio("Switch Metric", options=["Count", "Priority"], index=0, horizontal=True)
    if toggle.lower() != metric:
        display_journey_heatmap(insights, metric=toggle.lower())
