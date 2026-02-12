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
            # Title
            title = i.get("title") or _truncate(text, max_chars=80)
            st.markdown(f"### 🧠 Insight: {title}")

            # Document generation row
            doc_cols = st.columns(4)

            # PRD button
            if doc_cols[0].button("📝 PRD", key=f"prd_{unique_id}"):
                with st.spinner("Generating PRD..."):
                    try:
                        file_path = generate_prd_docx(text, brand, filename, insight=i)
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    "⬇️ PRD",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime=(
                                        "application/vnd.openxmlformats-officedocument."
                                        "wordprocessingml.document"
                                    ),
                                    key=f"dl_prd_{unique_id}",
                                )
                        else:
                            st.error("PRD file was not created.")
                    except Exception as e:
                        st.error(f"PRD generation failed: {str(e)}")

            # BRD button
            if doc_cols[1].button("📊 BRD", key=f"brd_{unique_id}"):
                with st.spinner("Generating BRD..."):
                    try:
                        file_path = generate_brd_docx(text, brand, filename, insight=i)
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    "⬇️ BRD",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime=(
                                        "application/vnd.openxmlformats-officedocument."
                                        "wordprocessingml.document"
                                    ),
                                    key=f"dl_brd_{unique_id}",
                                )
                        else:
                            st.error("BRD file was not created.")
                    except Exception as e:
                        st.error(f"BRD generation failed: {str(e)}")

            # PRFAQ button
            if doc_cols[2].button("📰 PRFAQ", key=f"prfaq_{unique_id}"):
                with st.spinner("Generating PRFAQ..."):
                    try:
                        file_path = generate_prfaq_docx(text, brand, filename, insight=i)
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    "⬇️ PRFAQ",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime=(
                                        "application/vnd.openxmlformats-officedocument."
                                        "wordprocessingml.document"
                                    ),
                                    key=f"dl_prfaq_{unique_id}",
                                )
                        else:
                            st.error("PRFAQ file was not created.")
                    except Exception as e:
                        st.error(f"PRFAQ generation failed: {str(e)}")

            # JIRA button
            if doc_cols[3].button("🐞 JIRA", key=f"jira_{unique_id}"):
                with st.spinner("Generating JIRA..."):
                    try:
                        file_content = generate_jira_bug_ticket(text, brand, insight=i)
                        if file_content:
                            st.download_button(
                                "⬇️ JIRA",
                                file_content,
                                file_name=f"jira-{filename}.md",
                                mime="text/markdown",
                                key=f"dl_jira_{unique_id}",
                            )
                        else:
                            st.error("JIRA generation returned empty content.")
                    except Exception as e:
                        st.error(f"JIRA generation failed: {str(e)}")

            # Badges - only show meaningful ones
            tags = []
            
            # Type badge (always show)
            type_tag = i.get("type_tag") or "Feedback"
            tags.append(badge(type_tag, BADGE_COLORS.get(type_tag, "#118AB2")))
            
            # Sentiment badge (always show)
            sentiment = i.get("brand_sentiment") or "Neutral"
            tags.append(badge(sentiment, BADGE_COLORS.get(sentiment, "#A9A9A9")))
            
            # Subtag/Topic badge if meaningful
            subtag = i.get("subtag", "")
            if subtag and subtag.lower() not in ("general", "unknown", ""):
                tags.append(badge(subtag, BADGE_COLORS.get(subtag, "#5F0F40")))
            
            # High-value flag
            if i.get("_high_end_flag"):
                tags.append(badge("💎 High-Value", "#FFB703"))
            
            # Payment flag
            if i.get("_payment_issue"):
                tags.append(badge("💳 Payment", "#E63946"))

            st.markdown(" ".join(tags), unsafe_allow_html=True)

            # Simplified caption
            st.caption(
                f"Source: {i.get('source', 'Reddit')} | "
                f"Posted: {i.get('post_date') or 'Unknown'}"
            )

            if i.get("url"):
                st.markdown(f"[🔗 View Original Post]({i['url']})", unsafe_allow_html=True)

            # Preview quote and actions
            st.markdown("**📣 Example quote:**")
            st.markdown(f"> {_truncate(text)}")

            # Show PM suggestions if available (skip warning if empty - not critical)
            if ideas and any(idea.strip() for idea in ideas if isinstance(idea, str)):
                st.markdown("**💡 Suggested PM actions:**")
                for idea in ideas:
                    if isinstance(idea, str) and idea.strip() and not idea.startswith("[LLM disabled]"):
                        pretty = textwrap.shorten(str(idea), width=220, placeholder="...")
                        st.markdown(f"- {pretty}")

            # Full detail expander
            with st.expander("🔍 Full insight details"):
                st.markdown("**Full user quote:**")
                st.markdown(f"> {text}")
