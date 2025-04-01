import streamlit as st

def render_floating_filters(insights, filter_fields):
    filters = {}
    with st.container():
        cols = st.columns(len(filter_fields))
        for idx, (label, key) in enumerate(filter_fields.items()):
            options = ["All"] + sorted({str(i.get(key, "Unknown")) for i in insights})
            filters[key] = cols[idx].selectbox(label, options, key=f"floating_{key}")
    return filters
