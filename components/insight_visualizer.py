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
        st.warning("No insights available to visualize.")
        return
    
    try:
        df = pd.DataFrame(insights)
        
        # Safe date parsing
        df['_date'] = pd.NaT
        if 'post_date' in df.columns:
            df['_date'] = pd.to_datetime(df['post_date'], errors='coerce')
        elif '_logged_date' in df.columns:
            df['_date'] = pd.to_datetime(df['_logged_date'], errors='coerce')

        with st.expander("📈 Insight Trends & Distribution", expanded=True):
            # Topic Distribution (simple bar chart)
            if 'subtag' in df.columns:
                st.subheader("📊 Topic Distribution")
                st.bar_chart(df['subtag'].fillna("General").value_counts().head(10))
            
            # Sentiment Distribution
            if 'brand_sentiment' in df.columns:
                st.subheader("😊 Sentiment Distribution")
                st.bar_chart(df['brand_sentiment'].fillna("Unknown").value_counts())
            
            # Insight Type Distribution
            if 'type_tag' in df.columns:
                st.subheader("📋 Insight Type Distribution")
                st.bar_chart(df['type_tag'].fillna("Unknown").value_counts().head(8))
            
            # Topic trend over time (exclude eBay Marketplace to show other topics)
            if '_date' in df.columns and df['_date'].notna().any():
                st.subheader("📈 Topic Trend Over Time")
                st.caption("Excludes 'eBay Marketplace' to highlight specific topics")
                try:
                    df_dated = df[df['_date'].notna()].copy()
                    # Exclude eBay Marketplace and General to show specific topics
                    df_dated = df_dated[~df_dated['subtag'].isin(['eBay Marketplace', 'General', 'Unknown'])]
                    if 'subtag' in df_dated.columns and len(df_dated) > 0:
                        topic_trend = df_dated.groupby([pd.Grouper(key='_date', freq='W'), 'subtag']).size().unstack(fill_value=0)
                        if len(topic_trend) > 0:
                            st.line_chart(topic_trend, use_container_width=True)
                        else:
                            st.info("Not enough data for trend chart.")
                except Exception as e:
                    st.info(f"Trend chart unavailable: {e}")
            
    except Exception as e:
        st.error(f"Chart error: {e}")