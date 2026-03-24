# components/floating_filters.py — Simple filter UI with time
import streamlit as st
from datetime import datetime, timedelta


def _nested_get(obj, path, default=None):
    cur = obj
    for part in str(path).split("."):
        if not isinstance(cur, dict):
            return default
        if part not in cur:
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def render_floating_filters(insights, filter_fields, key_prefix=""):
    """Render filter dropdowns: Topic, Type, and Time range."""
    filters = {}
    topic_field = filter_fields.get("Topic", "taxonomy.topic")
    type_field = filter_fields.get("Type", "taxonomy.type")
    
    # Extract unique topics
    topics = sorted({
        _nested_get(ins, topic_field, ins.get("subtag", "")) for ins in insights
        if _nested_get(ins, topic_field, ins.get("subtag", ""))
        and str(_nested_get(ins, topic_field, ins.get("subtag", ""))).lower() not in ("unknown", "general", "")
    })
    
    # Extract unique types
    types = sorted({
        _nested_get(ins, type_field, ins.get("type_tag", "")) for ins in insights
        if _nested_get(ins, type_field, ins.get("type_tag", ""))
        and str(_nested_get(ins, type_field, ins.get("type_tag", ""))).lower() not in ("unknown", "unclassified", "")
    })
    
    # Render 3 columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if topics:
            topic = st.selectbox("Topic", ["All"] + topics, key=f"{key_prefix}_topic")
            filters[topic_field] = [topic] if topic != "All" else ["All"]
    
    with col2:
        if types:
            typ = st.selectbox("Type", ["All"] + types, key=f"{key_prefix}_type")
            filters[type_field] = [typ] if typ != "All" else ["All"]
    
    with col3:
        time_range = st.selectbox(
            "Time", 
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
            key=f"{key_prefix}_time"
        )
        filters["_time_range"] = time_range
    
    return filters


def filter_by_time(insights, time_range):
    """Filter insights by time range."""
    if time_range == "All Time":
        return insights
    
    days_map = {
        "Last 7 Days": 7,
        "Last 30 Days": 30,
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
    }
    days = days_map.get(time_range, 0)
    if not days:
        return insights
    
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    
    return [
        ins for ins in insights 
        if ins.get("post_date", "2000-01-01") >= cutoff_str
    ]
