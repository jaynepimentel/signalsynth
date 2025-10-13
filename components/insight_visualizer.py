# components/insight_visualizer.py — cleaned imports + safe _date derivation + temporal graph

import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import networkx as nx
from datetime import datetime, timedelta

TEMPORAL_WINDOW = timedelta(days=14)

def build_temporal_graph(insights):
    G = nx.DiGraph()
    for idx, ins in enumerate(insights):
        pid = ins.get("fingerprint") or f"ins_{idx}"
        date = ins.get("_logged_date") or ins.get("post_date")
        try: d = pd.to_datetime(date, errors="coerce")
        except: d = pd.NaT
        G.add_node(pid, text=ins.get("text",""), date=d, tags=ins.get("type_subtags", []))
    nodes = list(G.nodes())
    for i in range(len(nodes)-1):
        s = nodes[i]; sdate = G.nodes[s]["date"]
        for j in range(i+1, min(i+6, len(nodes))):
            t = nodes[j]; tdate = G.nodes[t]["date"]
            if pd.isna(sdate) or pd.isna(tdate): continue
            if abs((sdate - tdate).days) <= TEMPORAL_WINDOW.days:
                G.add_edge(s, t, weight=1 - (abs((sdate - tdate).days)/14), relation_type="temporal")
    return G

def visualize_temporal_graph(G):
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42)
    node_colors = []
    for _, data in G.nodes(data=True):
        tags = data.get('tags', [])
        if 'Complaint' in tags: node_colors.append('red')
        elif 'Feature Request' in tags: node_colors.append('green')
        else: node_colors.append('blue')
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=50)
    nx.draw_networkx_edges(G, pos, edge_color='gray', alpha=0.3)
    plt.title("Temporal Signal Relationships"); plt.axis('off')
    return plt.gcf()

def display_insight_charts(insights):
    if not insights:
        st.warning("No insights available to visualize."); return
    df = pd.DataFrame(insights)
    # best-effort date
    df['_date'] = pd.to_datetime(df.get('_logged_date') or df.get('post_date') or datetime.today(), errors='coerce')

    with st.expander("📈 Insight Trends & Distribution", expanded=False):
        st.subheader("Sentiment Distribution"); st.bar_chart(df['brand_sentiment'].value_counts())
        st.subheader("Top Mentioned Brands");  st.bar_chart(df['target_brand'].fillna("Unknown").value_counts().head(8))
        st.subheader("Insight Type Distribution"); st.bar_chart(df['type_tag'].fillna("Unknown").value_counts().head(8))
        st.subheader("🕰️ Temporal Signal Relationships"); st.pyplot(visualize_temporal_graph(build_temporal_graph(insights)))

        if 'topic_focus' in df.columns:
            st.subheader("Topic Focus Breakdown")
            flat = [t for sub in df['topic_focus'].dropna() for t in (sub if isinstance(sub, list) else [])]
            if flat: st.bar_chart(pd.Series(flat).value_counts().head(10))

        if 'pm_priority_score' in df.columns:
            st.subheader("📊 PM Priority Score Trend (7-day Avg)")
            trend = df.set_index('_date').resample('7D')['pm_priority_score'].mean().dropna()
            if not trend.empty: st.line_chart(trend, use_container_width=True)

        if 'brand_sentiment' in df.columns:
            st.subheader("📊 Complaint vs Praise Over Time")
            sent = df.groupby([pd.Grouper(key='_date', freq='W'), 'brand_sentiment']).size().unstack(fill_value=0)
            if not sent.empty: st.area_chart(sent, use_container_width=True)

        if '_trend_keywords' in df.columns:
            st.subheader("🔥 Top Emerging Keywords")
            kw = df.explode('_trend_keywords')['_trend_keywords'].value_counts().head(10)
            if not kw.empty: st.bar_chart(kw)

        if 'effort' in df.columns:
            st.subheader("💼 Effort Breakdown"); st.bar_chart(df['effort'].value_counts())

        if 'persona' in df.columns and 'journey_stage' in df.columns:
            st.subheader("🧩 Persona × Journey Stage (Avg PM Priority)")
            if 'pm_priority_score' not in df.columns: df['pm_priority_score'] = 50
            hm = df.pivot_table(index='persona', columns='journey_stage', values='pm_priority_score', aggfunc='mean').fillna(0)
            if hm.empty: st.info("Not enough data to render heatmap.")
            else:
                fig, ax = plt.subplots(figsize=(10,4))
                sns.heatmap(hm, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=0.5)
                st.pyplot(fig)
