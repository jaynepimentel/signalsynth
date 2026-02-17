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
    """Render synthesized analysis from precomputed insight fields.
    
    Builds a real takeaway from the user's actual text, not a generic template.
    Focuses on what an eBay Collectibles PM needs to know.
    """
    type_tag = i.get("type_tag") or "Feedback"
    sentiment = i.get("brand_sentiment") or "Neutral"
    persona = i.get("persona") or "Unknown"
    clarity = i.get("clarity") or "Unknown"
    subtag = i.get("subtag") or "General"
    topics = i.get("topic_focus_list") or i.get("topic_focus") or []
    if isinstance(topics, str):
        topics = [topics]
    text = (i.get("text") or "").strip()
    text_lower = text.lower()

    # ── Quick Takeaway — extract the core issue from the actual text ──
    takeaway = _build_smart_takeaway(text, type_tag, sentiment, persona, subtag)
    st.markdown(f"\U0001f3af **Quick Take:** {takeaway}")

    # ── Actionability Assessment ──
    actionability, action_color = _assess_actionability(i, text_lower)
    st.markdown(
        f"**Actionability:** <span style='background:{action_color}; padding:3px 8px; "
        f"border-radius:6px; color:white; font-size:0.85em'>{actionability}</span>",
        unsafe_allow_html=True,
    )

    # ── What to watch / Why it matters (context-aware) ──
    context_line = _build_context_line(i, text_lower, subtag, sentiment)
    if context_line:
        st.markdown(f"\U0001f4a1 **Why it matters:** {context_line}")

    # ── Detected signals (compact, one line) ──
    signals = _collect_signals(i)
    if signals:
        st.markdown(f"**Signals:** {' \u00b7 '.join(signals)}")

    # ── PM suggestions from precompute ──
    if ideas and any(idea.strip() for idea in ideas if isinstance(idea, str)):
        st.markdown("**Suggested Actions:**")
        for idea in ideas:
            if isinstance(idea, str) and idea.strip() and not idea.startswith("[LLM disabled]"):
                pretty = textwrap.shorten(str(idea), width=220, placeholder="...")
                st.markdown(f"- {pretty}")

    # ── Compact metadata ──
    meta = []
    if persona and persona not in ("Unknown", "General"):
        meta.append(f"**Persona:** {persona}")
    if subtag and subtag.lower() not in ("general", "unknown"):
        meta.append(f"**Topic:** {subtag}")
    if topics:
        meta.append(f"**Themes:** {', '.join(topics[:4])}")
    if meta:
        st.caption(" \u00b7 ".join(meta))

    # Full quote (only if truncated above)
    if text and len(text) > 350:
        st.markdown("**Full user quote:**")
        st.markdown(f"> {text}")


def _build_smart_takeaway(text: str, type_tag: str, sentiment: str, persona: str, subtag: str) -> str:
    """Build a takeaway that actually summarizes the user's text, not a template."""
    text_lower = text.lower()
    # Extract the first meaningful sentence as the core signal
    sentences = [s.strip() for s in text.replace("\n", ". ").split(".") if len(s.strip()) > 15]
    core = sentences[0] if sentences else text[:150]
    # Cap at ~120 chars
    if len(core) > 120:
        core = core[:117].rsplit(" ", 1)[0] + "..."

    # Build a PM-oriented framing around the core
    if type_tag == "Complaint" and sentiment == "Negative":
        return f"User reports a problem: *\"{core}\"* \u2014 this is a negative experience that could drive churn."
    elif type_tag == "Feature Request":
        return f"User is requesting: *\"{core}\"* \u2014 evaluate whether this aligns with roadmap priorities."
    elif type_tag == "Question":
        return f"User is confused: *\"{core}\"* \u2014 may indicate a UX gap or missing documentation."
    elif sentiment == "Positive":
        return f"Positive signal: *\"{core}\"* \u2014 reinforces what's working well."
    else:
        return f"*\"{core}\"*"


def _assess_actionability(i: Dict[str, Any], text_lower: str) -> tuple:
    """Rate how actionable this insight is for a PM. Returns (label, color)."""
    score = 0
    # High-signal flags
    if i.get("is_urgent"):
        score += 3
    if i.get("_payment_issue") or i.get("is_refund_issue"):
        score += 2  # Revenue impact
    if i.get("is_vault_signal") or i.get("is_ag_signal"):
        score += 2  # Strategic product
    if i.get("brand_sentiment") == "Negative" and i.get("type_tag") == "Complaint":
        score += 2
    if i.get("type_tag") == "Feature Request":
        score += 1
    if i.get("_high_end_flag"):
        score += 1  # High-value segment
    # Text quality
    if len(i.get("text", "")) > 200:
        score += 1  # Detailed feedback
    if any(w in text_lower for w in ["switched to", "moved to", "leaving", "cancelled", "quit"]):
        score += 3  # Churn signal

    if score >= 5:
        return "High \u2014 investigate now", "#e63946"
    elif score >= 3:
        return "Medium \u2014 worth tracking", "#f59e0b"
    else:
        return "Low \u2014 monitor", "#6b7280"


def _build_context_line(i: Dict[str, Any], text_lower: str, subtag: str, sentiment: str) -> str:
    """Build a one-line context explanation of why this matters to eBay Collectibles."""
    # Competitive risk
    competitors = ["fanatics", "whatnot", "heritage", "alt.xyz", "pwcc", "myslabs"]
    mentioned_comp = [c for c in competitors if c in text_lower]
    if mentioned_comp:
        return f"Mentions competitor ({', '.join(mentioned_comp).title()}) \u2014 potential competitive risk or win-back signal."

    # Revenue/trust signals
    if any(w in text_lower for w in ["scam", "fake", "counterfeit", "fraud"]):
        return "Trust & safety concern \u2014 directly impacts buyer confidence and GMV."
    if any(w in text_lower for w in ["payment", "payout", "funds held", "checkout"]):
        return "Payment friction \u2014 blocks transactions and impacts seller retention."
    if "vault" in text_lower:
        return "Vault product signal \u2014 strategic growth area for high-value collectibles."
    if any(w in text_lower for w in ["authentication", "authenticity guarantee", " ag "]):
        return "Authentication signal \u2014 key differentiator vs competitors."
    if any(w in text_lower for w in ["shipping", "delivery", "tracking", "lost package"]):
        return "Shipping/fulfillment friction \u2014 impacts buyer satisfaction and repeat purchase."
    if any(w in text_lower for w in ["fee", "commission", "too expensive"]):
        return "Pricing/fee sensitivity \u2014 could push sellers to competing platforms."
    if any(w in text_lower for w in ["grading", "psa", "bgs", "cgc"]):
        return "Grading ecosystem signal \u2014 affects supply quality and buyer trust."
    if any(w in text_lower for w in ["comc", "check out my cards"]):
        return "COMC partner signal \u2014 impacts consignment pipeline and card supply."
    if sentiment == "Negative" and subtag in ("Seller Experience", "Buyer Experience"):
        return f"{subtag} friction \u2014 negative experiences drive users to competing platforms."
    return ""


def _collect_signals(i: Dict[str, Any]) -> list:
    """Collect detected signal flags as compact labels."""
    signals = []
    if i.get("_payment_issue"):
        signals.append("\U0001f4b3 Payment")
    if i.get("_upi_flag"):
        signals.append("\u26a0\ufe0f UPI")
    if i.get("is_shipping_issue"):
        signals.append("\U0001f4e6 Shipping")
    if i.get("is_vault_signal"):
        signals.append("\U0001f3e6 Vault")
    if i.get("is_ag_signal"):
        signals.append("\u2705 AG")
    if i.get("is_psa_turnaround"):
        signals.append("\U0001f3af Grading")
    if i.get("is_refund_issue"):
        signals.append("\U0001f504 Refund")
    if i.get("is_fees_concern"):
        signals.append("\U0001f4b0 Fees")
    if i.get("_high_end_flag"):
        signals.append("\U0001f48e High-Value")
    if i.get("is_urgent"):
        signals.append("\U0001f6a8 Urgent")
    return signals


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
    source = insight.get("source", "Unknown")
    topics = insight.get("topic_focus_list") or insight.get("topic_focus") or []
    if isinstance(topics, list):
        topics = ", ".join(topics)

    prompt = f"""You are analyzing a real user signal for a Product Manager on the eBay Collectibles team (trading cards, sports memorabilia, coins, comics). eBay competes with Fanatics Collect, Whatnot (live breaks), Heritage Auctions, PWCC, and Alt.xyz. Key eBay products include Vault (secure storage), Authenticity Guarantee, and integrations with grading companies (PSA, BGS, CGC).

USER QUOTE (from {source}):
\"{text[:1200]}\"

SIGNAL METADATA:
- Type: {type_tag} | Sentiment: {sentiment} | Persona: {persona}
- Topic: {subtag} | Themes: {topics}

Write a sharp analysis in this exact format:

**TL;DR:** [One sentence: what is this person saying and why should a PM care?]

**The Problem:** [2-3 sentences. What specifically went wrong or what is the user asking for? Be concrete — reference details from their quote.]

**Business Impact:** [1-2 sentences. How does this affect eBay's collectibles business? Think: GMV, seller/buyer retention, trust, competitive positioning. Be specific — e.g. "sellers moving to Whatnot" not just "retention risk".]

**Is This Actionable?** [Yes/No/Maybe + 1 sentence explaining. "Yes — this is a known Vault UX gap that could be fixed in a sprint" or "No — this is a one-off edge case" or "Maybe — need to check if this is a pattern across more signals".]

**Recommended Next Step:** [One specific action. Not "investigate further" — give a real action like "File a bug for the Vault withdrawal flow" or "Add to the Q3 Shipping roadmap" or "Share with Trust & Safety for policy review".]

Rules: Be direct. No filler. No hedging. Write for a PM who reads 50 of these a day and needs to decide in 10 seconds whether to act."""

    try:
        return _chat(
            MODEL_MAIN,
            "You are a senior product analyst at eBay who specializes in the collectibles vertical. You write crisp, opinionated analyses that help PMs make fast decisions. You never hedge or use vague language.",
            prompt,
            max_completion_tokens=500,
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
