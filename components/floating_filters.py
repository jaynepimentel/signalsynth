# components/floating_filters.py

import streamlit as st

def render_floating_filters(insights, filter_fields):
    """
    Renders a floating row of filters as dropdowns based on available insight metadata.
    Returns a dictionary of selected filters keyed by field name.
    """
    filters = {}
    with st.container():
        cols = st.columns(len(filter_fields))
        for idx, (label, key) in enumerate(filter_fields.items()):
            options = ["All"] + sorted({str(i.get(key, "Unknown")) for i in insights})
            filters[key] = cols[idx].selectbox(label, options, key=f"filter_{key}")
    return filters
