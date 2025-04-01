# components/floating_filters.py

import streamlit as st

def render_floating_filters(insights, filter_fields, key_prefix=""):
    filters = {}

    with st.expander("🧰 Advanced Filters", expanded=True):
        field_items = list(filter_fields.items())
        for i in range(0, len(field_items), 3):  # Max 3 filters per row
            cols = st.columns(min(3, len(field_items[i:i+3])))
            for col, (label, key) in zip(cols, field_items[i:i+3]):
                options = ["All"] + sorted({str(i.get(key, "Unknown")) for i in insights})
                unique_key = f"{key_prefix}_filter_{key}"
                filters[key] = col.selectbox(label, options, key=unique_key)
    return filters
