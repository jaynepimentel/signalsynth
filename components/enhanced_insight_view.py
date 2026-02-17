# enhanced_insight_view.py - Insight cards using precomputed GPT ideas (no GPT calls in UI)

import os
import textwrap
from typing import List, Dict, Any

import streamlit as st
from slugify import slugify

from components.ai_suggester import (
    generate_prd_docx,
    generate_brd_docx,
    generate_prfaq_docx,
    generate_jira_bug_ticket,
)

BADGE_COLORS = {
    "Complaint": "#FF6B6B",
    "Confusion": "#FFD166",
    "Feature Request": "#06D6A0",
    "Discussion": "#118AB2",
    "Praise": "#8AC926",
    "Neutral": "#A9A9A9",
    "Low": "#B5E48C",
    "Medium": "#F9C74F",
    "High": "#F94144",
    "Clear": "#4CAF50",
    "Needs Clarification": "#FF9800",
    "Discovery": "#90BE6D",
    "Purchase": "#F8961E",
    "Fulfillment": "#577590",
    "Post-Purchase": "#43AA8B",
    "Live Shopping": "#BC6FF1",
    "Search": "#118AB2",
    "Developer": "#7F00FF",
    "Buyer": "#38B000",
    "Seller": "#FF6700",
    "Collector": "#9D4EDD",
    "Vault": "#5F0F40",
    "PSA": "#FFB703",
    "Live": "#1D3557",
    "Post-Event": "#264653",
    "Canada": "#F72585",
    "Japan": "#7209B7",
    "Europe": "#3A0CA3",
}


def badge(label: str, color: str) -> str:
    return (
        f"<span style='background:{color}; padding:4px 8px; "
        f"border-radius:8px; color:white; font-size:0.85em'>{label}</span>"
    )


def _truncate(text: str, max_chars: int = 220) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3].rsplit(" ", 1)[0] + "..."


def _normalize_ideas(i: Dict[str, Any]) -> List[str]:
    """
    Normalize ideas coming from precompute_insights.
    This never calls GPT, it just cleans up what is already stored.
    """
    ideas = i.get("ideas") or []
    if isinstance(ideas, str):
        ideas = [ideas]
    ideas = [str(x).strip() for x in ideas if str(x).strip()]
    i["ideas"] = ideas
    return ideas


def render_insight_cards(
    filtered: List[Dict[str, Any]],
    model: Any,
    per_page: int = 10,
    key_prefix: str = "insight",
) -> None:
    """
    Render one card per insight.

    All PM suggestions are assumed to have been generated in precompute_insights.py.
    This UI never calls OpenAI directly, so it can run safely in environments without a key.
    """
    if not filtered:
        st.info("No matching insights.")
        return

    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    
    # Initialize session state for page
    page_key = f"{key_prefix}_current_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0  # index-based
    
    # Clamp to valid range
    st.session_state[page_key] = min(st.session_state[page_key], total_pages - 1)
    
    # Navigation buttons
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("◀ Prev", key=f"{key_prefix}_prev", disabled=st.session_state[page_key] == 0):
                st.session_state[page_key] -= 1
                st.rerun()
        with col2:
            st.markdown(f"**Page {st.session_state[page_key] + 1} of {total_pages}**")
        with col3:
            if st.button("Next ▶", key=f"{key_prefix}_next", disabled=st.session_state[page_key] >= total_pages - 1):
                st.session_state[page_key] += 1
                st.rerun()
    
    start = st.session_state[page_key] * per_page
    paged = filtered[start : start + per_page]

    for idx, i in enumerate(paged, start=start):
        unique_id = f"{key_prefix}_{idx}"
        text = i.get("text", "") or ""
        brand = i.get("target_brand", "eBay")
        summary = i.get("summary") or text[:80]
        filename = slugify(summary)[:64] or f"insight-{idx}"

        # Normalize ideas from precompute
        ideas = _normalize_ideas(i)

        with st.container(border=True):
            # ── Badges row ──
            tags = []
            type_tag = i.get("type_tag") or "Feedback"
            tags.append(badge(type_tag, BADGE_COLORS.get(type_tag, "#118AB2")))
            sentiment = i.get("brand_sentiment") or "Neutral"
            tags.append(badge(sentiment, BADGE_COLORS.get(sentiment, "#A9A9A9")))
            subtag = i.get("subtag", "")
            if subtag and subtag.lower() not in ("general", "unknown", ""):
                tags.append(badge(subtag, BADGE_COLORS.get(subtag, "#5F0F40")))
            if i.get("_high_end_flag"):
                tags.append(badge("\U0001f48e High-Value", "#FFB703"))
            if i.get("_payment_issue"):
                tags.append(badge("\U0001f4b3 Payment", "#E63946"))
            if i.get("is_shipping_issue"):
                tags.append(badge("\U0001f4e6 Shipping", "#577590"))
            if i.get("is_vault_signal"):
                tags.append(badge("\U0001f3e6 Vault", "#5F0F40"))
            if i.get("is_ag_signal"):
                tags.append(badge("\u2705 AG", "#4CAF50"))
            st.markdown(" ".join(tags), unsafe_allow_html=True)

            # ── User quote (prominent) ──
            st.markdown(f"> {_truncate(text, max_chars=350)}")

            # ── Source & date ──
            source = i.get("source", "Reddit")
            date = i.get("post_date") or "Unknown"
            score = i.get("score", 0)
            url = i.get("url", "")
            meta_parts = [f"**{source}**", f"{date}"]
            if score:
                meta_parts.append(f"\u2b06\ufe0f {score}")
            if url:
                meta_parts.append(f"[\U0001f517 Source]({url})")
            st.caption(" \u00b7 ".join(meta_parts))

            # ── Expandable AI Analysis ──
            with st.expander("\U0001f9e0 AI Analysis & Context"):
                # Synthesized takeaway from precomputed fields
                _render_ai_synthesis(i, ideas, unique_id)

                # On-demand GPT deep dive
                deep_key = f"deep_dive_{unique_id}"
                if st.button("\U0001f52c Generate Deep Dive", key=f"btn_{deep_key}", help="AI-powered detailed analysis"):
                    st.session_state[deep_key] = True
                    st.rerun()
                if st.session_state.get(deep_key):
                    with st.spinner("Generating deep dive..."):
                        analysis = _generate_deep_dive(text, i)
                    st.markdown(analysis)

                # Document generation (tucked in here)
                st.markdown("---")
                st.markdown("**\U0001f4c4 Generate Documents**")
                doc_cols = st.columns(4)
                _render_doc_buttons(doc_cols, unique_id, text, brand, filename, i)


def _render_ai_synthesis(i: Dict[str, Any], ideas: List[str], unique_id: str) -> None:
    """Render synthesized analysis from precomputed insight fields."""
    type_tag = i.get("type_tag") or "Feedback"
    sentiment = i.get("brand_sentiment") or "Neutral"
    persona = i.get("persona") or "Unknown"
    clarity = i.get("clarity") or "Unknown"
    subtag = i.get("subtag") or "General"
    topics = i.get("topic_focus_list") or i.get("topic_focus") or []
    if isinstance(topics, str):
        topics = [topics]

    # Takeaway line
    sentiment_word = {"Negative": "frustrated", "Positive": "satisfied", "Neutral": "sharing feedback"}.get(sentiment, "sharing feedback")
    takeaway = f"A **{persona.lower()}** is {sentiment_word}"
    if type_tag == "Complaint":
        takeaway += f" about a problem"
    elif type_tag == "Feature Request":
        takeaway += f" and requesting a new capability"
    elif type_tag == "Confusion":
        takeaway += f" and confused about how something works"
    elif type_tag == "Praise":
        takeaway += f" with a positive experience"
    else:
        takeaway += f" ({type_tag.lower()})"
    if subtag and subtag.lower() not in ("general", "unknown"):
        takeaway += f" related to **{subtag}**"
    takeaway += "."
    st.markdown(f"\U0001f3af **Takeaway:** {takeaway}")

    # Key themes
    if topics:
        theme_str = ", ".join([f"`{t}`" for t in topics[:5]])
        st.markdown(f"\U0001f3f7\ufe0f **Key Themes:** {theme_str}")

    # Signal flags
    signals = []
    if i.get("_payment_issue"):
        signals.append("\U0001f4b3 Payment issue detected")
    if i.get("_upi_flag"):
        signals.append("\u26a0\ufe0f Unpaid item (UPI) signal")
    if i.get("is_shipping_issue"):
        signals.append("\U0001f4e6 Shipping concern")
    if i.get("is_vault_signal"):
        signals.append("\U0001f3e6 Vault-related")
    if i.get("is_ag_signal"):
        signals.append("\u2705 Authenticity Guarantee signal")
    if i.get("is_psa_turnaround"):
        signals.append("\U0001f3af PSA grading/turnaround")
    if i.get("is_refund_issue"):
        signals.append("\U0001f4b0 Refund issue")
    if i.get("is_fees_concern"):
        signals.append("\U0001f4ca Fees concern")
    if i.get("_high_end_flag"):
        signals.append("\U0001f48e High-value item")
    if i.get("is_urgent"):
        signals.append("\U0001f6a8 Urgent")
    if signals:
        st.markdown("**\U0001f4e1 Detected Signals:**")
        for s in signals:
            st.markdown(f"- {s}")

    # PM suggestions
    if ideas and any(idea.strip() for idea in ideas if isinstance(idea, str)):
        st.markdown("**\U0001f4a1 PM Actions:**")
        for idea in ideas:
            if isinstance(idea, str) and idea.strip() and not idea.startswith("[LLM disabled]"):
                pretty = textwrap.shorten(str(idea), width=220, placeholder="...")
                st.markdown(f"- {pretty}")

    # Context metadata
    meta = []
    if persona and persona != "Unknown":
        meta.append(f"**Persona:** {persona}")
    if clarity and clarity != "Unknown":
        meta.append(f"**Clarity:** {clarity}")
    effort = i.get("effort")
    if effort and effort != "Unknown":
        meta.append(f"**Effort:** {effort}")
    if meta:
        st.caption(" \u00b7 ".join(meta))

    # Full quote
    text = i.get("text", "")
    if text and len(text) > 350:
        st.markdown("**Full user quote:**")
        st.markdown(f"> {text}")


def _generate_deep_dive(text: str, insight: Dict[str, Any]) -> str:
    """Generate an on-demand GPT deep dive analysis for a single insight."""
    try:
        from components.ai_suggester import _chat, MODEL_MAIN
    except ImportError:
        return "*LLM not available. Configure your OpenAI API key to enable deep dives.*"

    type_tag = insight.get("type_tag", "Feedback")
    sentiment = insight.get("brand_sentiment", "Neutral")
    persona = insight.get("persona", "Unknown")
    subtag = insight.get("subtag", "General")

    prompt = f"""Analyze this user feedback signal for a product manager at eBay Collectibles.

USER QUOTE:
\"{text[:800]}\"

METADATA: Type={type_tag}, Sentiment={sentiment}, Persona={persona}, Topic={subtag}

Write a concise analysis (150 words max) with:
1. **What happened** \u2014 one sentence summary of the user's experience
2. **Why it matters** \u2014 business impact (revenue, trust, retention, competitive risk)
3. **Root cause** \u2014 your best hypothesis for what's causing this
4. **Recommended action** \u2014 one specific, actionable next step

Be direct. No filler. Write for a PM who has 30 seconds to read this."""

    try:
        return _chat(
            MODEL_MAIN,
            "You are a senior product analyst who writes crisp, insight-dense analyses.",
            prompt,
            max_completion_tokens=300,
            temperature=0.3,
        )
    except Exception as e:
        return f"*Deep dive generation failed: {e}*"


def _render_doc_buttons(
    doc_cols, unique_id: str, text: str, brand: str, filename: str, insight: Dict[str, Any]
) -> None:
    """Render document generation buttons in columns."""
    if doc_cols[0].button("\U0001f4dd PRD", key=f"prd_{unique_id}"):
        with st.spinner("Generating PRD..."):
            try:
                file_path = generate_prd_docx(text, brand, filename, insight=insight)
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "\u2b07\ufe0f PRD", f,
                            file_name=os.path.basename(file_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_prd_{unique_id}",
                        )
                else:
                    st.error("PRD file was not created.")
            except Exception as e:
                st.error(f"PRD generation failed: {e}")

    if doc_cols[1].button("\U0001f4ca BRD", key=f"brd_{unique_id}"):
        with st.spinner("Generating BRD..."):
            try:
                file_path = generate_brd_docx(text, brand, filename, insight=insight)
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "\u2b07\ufe0f BRD", f,
                            file_name=os.path.basename(file_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_brd_{unique_id}",
                        )
                else:
                    st.error("BRD file was not created.")
            except Exception as e:
                st.error(f"BRD generation failed: {e}")

    if doc_cols[2].button("\U0001f4f0 PRFAQ", key=f"prfaq_{unique_id}"):
        with st.spinner("Generating PRFAQ..."):
            try:
                file_path = generate_prfaq_docx(text, brand, filename, insight=insight)
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "\u2b07\ufe0f PRFAQ", f,
                            file_name=os.path.basename(file_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_prfaq_{unique_id}",
                        )
                else:
                    st.error("PRFAQ file was not created.")
            except Exception as e:
                st.error(f"PRFAQ generation failed: {e}")

    if doc_cols[3].button("\U0001f41e JIRA", key=f"jira_{unique_id}"):
        with st.spinner("Generating JIRA..."):
            try:
                file_content = generate_jira_bug_ticket(text, brand, insight=insight)
                if file_content:
                    st.download_button(
                        "\u2b07\ufe0f JIRA", file_content,
                        file_name=f"jira-{filename}.md",
                        mime="text/markdown",
                        key=f"dl_jira_{unique_id}",
                    )
                else:
                    st.error("JIRA generation returned empty content.")
            except Exception as e:
                st.error(f"JIRA generation failed: {e}")
