# components/insight_visualizer.py — cleaned imports + safe _date derivation + temporal graph

import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import networkx as nx
import altair as alt
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
            
            # Signal trend over time - use signal flags for categorization
            if '_date' in df.columns and df['_date'].notna().any():
                st.subheader("📈 Signal Trend Over Time")
                st.caption("Hover over a line to highlight it. Excludes 'General' signals for clarity.")
                try:
                    df_dated = df[df['_date'].notna()].copy()
                    
                    # Categorize each insight by signal type
                    def get_signal_category(row):
                        if row.get('is_vault_signal'): return 'Vault'
                        if row.get('is_psa_turnaround'): return 'Grading'
                        if row.get('is_ag_signal'): return 'Authentication'
                        if row.get('is_shipping_issue'): return 'Shipping'
                        if row.get('_payment_issue'): return 'Payments'
                        if row.get('is_refund_issue'): return 'Refunds'
                        if row.get('is_fees_concern'): return 'Fees'
                        if row.get('_upi_flag'): return 'UPI'
                        return 'General'
                    
                    df_dated['signal_category'] = df_dated.apply(get_signal_category, axis=1)
                    
                    # Exclude General to reduce clutter
                    df_dated = df_dated[df_dated['signal_category'] != 'General']
                    
                    # Limit date range to last 90 days to avoid smooshed chart
                    max_date = df_dated['_date'].max()
                    min_date = max_date - pd.Timedelta(days=90)
                    df_dated = df_dated[df_dated['_date'] >= min_date]
                    
                    # Aggregate by week and signal category
                    df_dated['week'] = df_dated['_date'].dt.to_period('W').dt.start_time
                    trend_data = df_dated.groupby(['week', 'signal_category']).size().reset_index(name='count')
                    
                    # Show all categories with data
                    categories_with_data = trend_data.groupby('signal_category')['count'].sum()
                    categories_with_data = categories_with_data[categories_with_data > 0].index.tolist()
                    trend_data = trend_data[trend_data['signal_category'].isin(categories_with_data)]
                    
                    if len(trend_data) > 0:
                        # Create interactive Altair chart with hover highlight
                        highlight = alt.selection_point(
                            on='mouseover',
                            fields=['signal_category'],
                            nearest=True
                        )
                        
                        # Color scale for signal categories
                        color_scale = alt.Scale(
                            domain=['Vault', 'Grading', 'Authentication', 'Shipping', 'Payments', 'Refunds', 'Fees', 'UPI', 'General'],
                            range=['#8b5cf6', '#f59e0b', '#22c55e', '#3b82f6', '#ef4444', '#ec4899', '#14b8a6', '#f97316', '#6b7280']
                        )
                        
                        base = alt.Chart(trend_data).encode(
                            x=alt.X('week:T', title='Week', axis=alt.Axis(format='%b %d')),
                            y=alt.Y('count:Q', title='Signal Count'),
                            color=alt.Color('signal_category:N', title='Signal Type', scale=color_scale, legend=alt.Legend(orient='bottom', columns=5)),
                            tooltip=[
                                alt.Tooltip('signal_category:N', title='Signal'),
                                alt.Tooltip('week:T', title='Week', format='%b %d, %Y'),
                                alt.Tooltip('count:Q', title='Count')
                            ]
                        )
                        
                        # Lines - fade non-highlighted
                        lines = base.mark_line(strokeWidth=3).encode(
                            opacity=alt.condition(highlight, alt.value(1), alt.value(0.15)),
                            strokeWidth=alt.condition(highlight, alt.value(4), alt.value(1.5))
                        ).add_params(highlight)
                        
                        # Points - show on hover
                        points = base.mark_circle(size=80).encode(
                            opacity=alt.condition(highlight, alt.value(1), alt.value(0))
                        )
                        
                        chart = (lines + points).properties(
                            height=400
                        ).configure_axis(
                            labelFontSize=12,
                            titleFontSize=14
                        ).configure_legend(
                            labelFontSize=11,
                            titleFontSize=12
                        )
                        
                        st.altair_chart(chart, use_container_width=True)
                        
                        # Show signal counts summary
                        signal_totals = df_dated['signal_category'].value_counts()
                        st.caption(f"**Total signals:** {len(df_dated)} | " + " · ".join([f"{cat}: {cnt}" for cat, cnt in signal_totals.items()]))
                    else:
                        st.info("Not enough data for trend chart.")
                except Exception as e:
                    st.info(f"Trend chart unavailable: {e}")
            
    except Exception as e:
        st.error(f"Chart error: {e}")