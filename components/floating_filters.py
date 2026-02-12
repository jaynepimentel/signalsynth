# components/floating_filters.py — Simple filter UI with time
import streamlit as st
from datetime import datetime, timedelta


def render_floating_filters(insights, filter_fields, key_prefix=""):
    """Render filter dropdowns: Topic, Type, and Time range."""
    filters = {}
    
    # Extract unique topics
    topics = sorted({
        ins.get("subtag", "") for ins in insights 
        if ins.get("subtag") and ins.get("subtag").lower() not in ("unknown", "general", "")
    })
    
    # Extract unique types
    types = sorted({
        ins.get("type_tag", "") for ins in insights
        if ins.get("type_tag") and ins.get("type_tag").lower() not in ("unknown", "unclassified", "")
    })
    
    # Render 3 columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if topics:
            topic = st.selectbox("Topic", ["All"] + topics, key=f"{key_prefix}_topic")
            filters["subtag"] = [topic] if topic != "All" else ["All"]
    
    with col2:
        if types:
            typ = st.selectbox("Type", ["All"] + types, key=f"{key_prefix}_type")
            filters["type_tag"] = [typ] if typ != "All" else ["All"]
    
    with col3:
        time_range = st.selectbox(
            "Time", 
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days"],
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 9 Months"],
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
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
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
<<<<<<< C:/Users/jayne/repo/signalsynth/components/floating_filters.py
        "Last 90 Days": 90,
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
=======
        "Last 3 Months": 90,
        "Last 6 Months": 180,
        "Last 9 Months": 270,
>>>>>>> C:/Users/jayne/.windsurf/worktrees/signalsynth/signalsynth-24efd192/components/floating_filters.py
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
