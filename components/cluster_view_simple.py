# cluster_view_simple.py - Strategic epic display with LLM summaries and document generation

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

import streamlit as st

# Import LLM function if available
try:
    from components.ai_suggester import _chat, MODEL_MAIN
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# Document type templates
DOC_TEMPLATES = {
    "PRD": {
        "name": "Product Requirements Document",
        "icon": "📄",
        "prompt": """You are a Senior Product Manager writing a PRD for engineering.

EPIC: {epic_name}
PRODUCT OPPORTUNITY: {product_opp}

USER SIGNALS ({total} signals, {complaints} complaints):
{context}

Write a complete PRD with these sections:
1. **Problem Statement** - What user problem are we solving?
2. **Goals & Success Metrics** - How will we measure success?
3. **User Stories** - 3-5 user stories in "As a [persona], I want [feature] so that [benefit]" format
4. **Requirements** - Functional requirements (P0, P1, P2)
5. **Out of Scope** - What we're NOT building
6. **Open Questions** - Unknowns to resolve

Be specific with examples from the signals. Write for engineers."""
    },
    "BRD": {
        "name": "Business Requirements Document",
        "icon": "💼",
        "prompt": """You are a Business Analyst writing a BRD for stakeholders.

EPIC: {epic_name}
PRODUCT OPPORTUNITY: {product_opp}

USER SIGNALS ({total} signals, {complaints} complaints):
{context}

Write a complete BRD with these sections:
1. **Executive Summary** - One paragraph overview
2. **Business Objectives** - What business outcomes do we expect?
3. **Stakeholders** - Who is impacted?
4. **Current State** - What's the problem today?
5. **Proposed Solution** - High-level approach
6. **Benefits & ROI** - Expected impact
7. **Risks & Mitigations** - What could go wrong?

Write for business stakeholders, not engineers."""
    },
    "PRFAQ": {
        "name": "Press Release / FAQ",
        "icon": "📰",
        "prompt": """You are writing an Amazon-style PRFAQ (Press Release + FAQ).

EPIC: {epic_name}
PRODUCT OPPORTUNITY: {product_opp}

USER SIGNALS ({total} signals, {complaints} complaints):
{context}

Write a PRFAQ with:

**PRESS RELEASE:**
- Headline (attention-grabbing)
- Subheadline (one sentence)
- First paragraph (who, what, when, where, why)
- Customer quote (fictional happy customer)
- How it works (2-3 sentences)
- Executive quote (fictional VP)
- Call to action

**FAQ (5 questions):**
- 2 customer questions
- 2 internal stakeholder questions  
- 1 technical question

Write as if the feature already launched successfully."""
    },
    "Jira": {
        "name": "Jira Tickets",
        "icon": "🎫",
        "prompt": """You are a Product Manager writing Jira tickets for a sprint.

EPIC: {epic_name}
PRODUCT OPPORTUNITY: {product_opp}

USER SIGNALS ({total} signals, {complaints} complaints):
{context}

Create 5 Jira tickets. For each ticket:

**[TICKET-001] Title**
- **Type:** Story / Bug / Task
- **Priority:** P0 / P1 / P2
- **Description:** What needs to be done
- **Acceptance Criteria:** 3-4 bullet points
- **Story Points:** 1, 2, 3, 5, 8, or 13

Make tickets specific and actionable. Include edge cases in acceptance criteria."""
    },
}


def _generate_document(doc_type: str, cluster: Dict[str, Any], selected_insights: List[Dict] = None) -> str:
    """Generate a document from cluster insights."""
    if not LLM_AVAILABLE:
        return "LLM not available. Please configure OpenAI API key."
    
    template = DOC_TEMPLATES.get(doc_type)
    if not template:
        return f"Unknown document type: {doc_type}"
    
    insights = selected_insights or cluster.get("insights", [])
    if not insights:
        return "No insights selected for document generation."
    
    # Build context from insights
    sorted_insights = sorted(insights, key=lambda x: x.get("type_tag") == "Complaint", reverse=True)
    sample_texts = [f"[{i.get('type_tag', 'Feedback')}] {i.get('text', '')[:200]}" for i in sorted_insights[:15]]
    context = "\n---\n".join(sample_texts)
    
    epic_name = cluster.get("title", "Unknown")
    product_opp = cluster.get("product_opportunity", "")
    signal_counts = cluster.get("signal_counts", {})
    total = len(insights)
    complaints = sum(1 for i in insights if i.get("type_tag") == "Complaint")
    
    prompt = template["prompt"].format(
        epic_name=epic_name,
        product_opp=product_opp,
        total=total,
        complaints=complaints,
        context=context
    )
    
    try:
        doc = _chat(
            MODEL_MAIN,
            f"You are an expert at writing {template['name']}s. Be specific and actionable.",
            prompt,
            max_completion_tokens=1500,
            temperature=0.4
        )
        return doc
    except Exception as e:
        return f"Document generation failed: {e}"


def _load_clusters() -> List[Dict[str, Any]]:
    """Load precomputed clusters from JSON file, merging cards with cluster insights."""
    path = Path(__file__).parent.parent / "precomputed_clusters.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Use cards for display data, merge with cluster insights
        cards = data.get("cards", [])
        clusters_raw = data.get("clusters", [])
        
        # Create lookup for cluster insights by cluster_id
        insights_by_id = {c.get("cluster_id"): c.get("insights", []) for c in clusters_raw}
        stats_by_id = {c.get("cluster_id"): c.get("stats", {}) for c in clusters_raw}
        
        result = []
        for card in cards:
            cid = card.get("cluster_id")
            cluster = {
                "title": card.get("title", "Unknown"),
                "label": card.get("title", "Unknown"),
                "size": card.get("insight_count", 0),
                "description": card.get("problem_statement", ""),
                "product_opportunity": card.get("theme", ""),
                "cluster_id": cid,
                "insights": insights_by_id.get(cid, []),
                "signal_counts": {
                    "total": card.get("insight_count", 0),
                    "complaints": stats_by_id.get(cid, {}).get("complaints", 0),
                    "feature_requests": stats_by_id.get(cid, {}).get("feature_requests", 0),
                    "negative": stats_by_id.get(cid, {}).get("negative", 0),
                    "positive": stats_by_id.get(cid, {}).get("positive", 0),
                },
                "coherent": card.get("coherent", True),
                "avg_similarity": card.get("avg_similarity", "0.75"),
            }
            result.append(cluster)
        
        return result
    except Exception:
        return []


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text to max length."""
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def _generate_cluster_summary(cluster: Dict[str, Any]) -> str:
    """Generate executive summary for a cluster."""
    if not LLM_AVAILABLE:
        return cluster.get("summary", "Summary not available.")
    
    # Check cache first
    cache_key = f"cluster_summary_{cluster.get('cluster_id', '')}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    insights = cluster.get("insights", [])
    if not insights:
        return "No insights to summarize."
    
    # Build context from top insights (prioritize complaints)
    sorted_insights = sorted(insights, key=lambda x: x.get("type_tag") == "Complaint", reverse=True)
    sample_texts = [f"[{i.get('type_tag', 'Feedback')}] {i.get('text', '')[:250]}" for i in sorted_insights[:12]]
    context = "\n---\n".join(sample_texts)
    
    epic_name = cluster.get("title", "Unknown")
    product_opp = cluster.get("product_opportunity", "")
    signal_counts = cluster.get("signal_counts", {})
    total = signal_counts.get("total", len(insights))
    complaints = signal_counts.get("complaints", 0)
    feature_requests = signal_counts.get("feature_requests", 0)
    
    prompt = f"""You are a Senior Product Manager preparing an executive briefing for leadership.

EPIC: {epic_name}
PRODUCT OPPORTUNITY: {product_opp}
SIGNAL VOLUME: {total} total ({complaints} complaints, {feature_requests} feature requests)

USER FEEDBACK SIGNALS:
{context}

Write an EXECUTIVE SUMMARY (4-5 sentences) that a VP of Product would read. Include:

1. **THE PROBLEM**: What specific pain point are users experiencing? Be concrete, not vague.
2. **BUSINESS IMPACT**: Why should we care? Revenue risk, churn signal, competitive threat, or brand damage?
3. **ROOT CAUSE HYPOTHESIS**: What's likely causing this based on the signals?
4. **RECOMMENDED ACTION**: One specific next step (investigate, build, fix, or deprioritize).

Write in a direct, confident executive tone. No bullet points. No hedging. Be specific with examples from the signals."""
    
    try:
        summary = _chat(
            MODEL_MAIN, 
            "You are a senior product strategist who writes crisp, actionable executive briefings. You never use filler words or vague statements.", 
            prompt, 
            max_completion_tokens=350, 
            temperature=0.4
        )
        st.session_state[cache_key] = summary
        return summary
    except Exception as e:
        return cluster.get("summary", f"Summary generation failed: {e}")


def _extract_top_themes(insights: List[Dict[str, Any]], n: int = 5) -> List[str]:
    """Extract top recurring themes/keywords from insights."""
    all_words = []
    stopwords = {"the", "a", "an", "is", "it", "to", "and", "of", "for", "in", "on", "with", "my", "i", "this", "that", "was", "have", "has", "had", "be", "been", "are", "were", "they", "them", "their", "we", "you", "your", "from", "but", "not", "so", "just", "got", "get", "would", "could", "should", "can", "will", "do", "does", "did", "about", "out", "up", "if", "or", "as", "at", "by", "no", "yes", "all", "any", "some", "what", "when", "how", "why", "who", "which", "there", "here", "more", "very", "than", "then", "now", "also", "only", "even", "still", "after", "before", "over", "into", "through", "during", "between", "both", "each", "other", "such", "these", "those", "being", "having", "doing", "going", "make", "made", "take", "took", "come", "came", "see", "saw", "know", "knew", "think", "thought", "want", "wanted", "use", "used", "find", "found", "give", "gave", "tell", "told", "one", "two", "first", "new", "way", "day", "time", "year", "back", "good", "bad", "thing", "things", "people", "really", "like", "don", "didn", "doesn", "isn", "wasn", "won", "wouldn", "couldn", "shouldn", "haven", "hasn", "hadn", "aren", "weren", "ve", "ll", "re", "im", "he", "she", "him", "her", "his", "hers", "its"}
    
    for ins in insights:
        text = (ins.get("text", "") + " " + ins.get("title", "")).lower()
        words = [w for w in text.split() if len(w) > 3 and w.isalpha() and w not in stopwords]
        all_words.extend(words)
    
    counts = Counter(all_words)
    return [word for word, _ in counts.most_common(n)]


def display_clustered_insight_cards(insights: List[Dict[str, Any]]) -> None:
    """Display strategic epic clusters with LLM summaries."""
    clusters = _load_clusters()
    
    if not clusters:
        st.info("No clusters available. Run `python precompute_clusters.py` to generate.")
        return
    
    # Header with sorting
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"📊 {len(clusters)} Strategic Epics")
    with col2:
        sort_options = ["Signals ↓", "Complaints ↓", "A→Z"]
        sort_by = st.selectbox(
            "Sort by",
            sort_options,
            key="cluster_sort",
            label_visibility="collapsed"
        )
    
    # Sort clusters based on selection
    if sort_by == "Complaints ↓":
        clusters = sorted(clusters, key=lambda x: x.get("signal_counts", {}).get("complaints", 0), reverse=True)
    elif sort_by == "A→Z":
        clusters = sorted(clusters, key=lambda x: (x.get("title", "") or "").lower())
    else:  # Default: Signals ↓
        clusters = sorted(clusters, key=lambda x: x.get("size", 0), reverse=True)
    
    for cluster in clusters:
        epic_name = cluster.get("title", "Unknown")
        label = cluster.get("label", epic_name)
        size = cluster.get("size", 0)
        description = cluster.get("description", "")
        product_opp = cluster.get("product_opportunity", "")
        signal_counts = cluster.get("signal_counts", {})
        cluster_insights = cluster.get("insights", [])
        cluster_id = cluster.get("cluster_id", epic_name)
        
        # Epic card using container (no expander)
        with st.container(border=True):
            st.subheader(f"{label} — {size} signals")
            
            # Product opportunity header
            if product_opp:
                st.markdown(f"**🎯 Product Opportunity:** {product_opp}")
            if description:
                st.caption(description)
            
            # Metrics row with color coding
            cols = st.columns(4)
            with cols[0]:
                st.metric("Total Signals", signal_counts.get("total", size))
            with cols[1]:
                complaints = signal_counts.get("complaints", 0)
                complaint_pct = round(complaints / max(size, 1) * 100)
                st.metric("Complaints", f"{complaints} ({complaint_pct}%)")
            with cols[2]:
                st.metric("Feature Requests", signal_counts.get("feature_requests", 0))
            with cols[3]:
                negative = signal_counts.get("negative", 0)
                positive = signal_counts.get("positive", 0)
                if negative > positive:
                    sentiment_label = f"� {negative} neg / {positive} pos"
                elif positive > negative:
                    sentiment_label = f"� {positive} pos / {negative} neg"
                else:
                    sentiment_label = f"😐 {negative} neg / {positive} pos"
                st.metric("Sentiment", sentiment_label)
            
            # Sample quote for context
            if cluster_insights:
                sample = cluster_insights[0]
                sample_text = (sample.get("text", "") or sample.get("title", ""))[:200]
                if sample_text:
                    st.markdown(f"📝 *\"{sample_text}...\"*")
            
            # Top themes
            themes = _extract_top_themes(cluster_insights)
            if themes:
                st.markdown("**🏷️ Top Themes:** " + " • ".join([f"`{t}`" for t in themes]))
            
            # Two-column action layout
            action_col1, action_col2 = st.columns([1, 2])
            
            # Left column: AI Summary button
            summary_key = f"show_summary_{cluster_id}"
            with action_col1:
                if st.button("🤖 Generate Executive Summary", key=f"gen_{cluster_id}", use_container_width=True):
                    st.session_state[summary_key] = True
                    st.rerun()
            
            # Right column: Document dropdown + generate button
            with action_col2:
                doc_col1, doc_col2 = st.columns([2, 1])
                with doc_col1:
                    doc_options = [f"{t['icon']} {t['name']}" for t in DOC_TEMPLATES.values()]
                    doc_keys = list(DOC_TEMPLATES.keys())
                    selected_doc_label = st.selectbox(
                        "📄 Generate Document",
                        doc_options,
                        key=f"doc_select_{cluster_id}",
                        label_visibility="collapsed"
                    )
                with doc_col2:
                    selected_idx = doc_options.index(selected_doc_label)
                    selected_doc_type = doc_keys[selected_idx]
                    doc_key = f"doc_{cluster_id}_{selected_doc_type}"
                    if st.button("📄 Generate", key=f"gen_doc_{cluster_id}", use_container_width=True):
                        st.session_state[doc_key] = True
                        st.rerun()
            
            # Show generated summary
            if summary_key in st.session_state and st.session_state[summary_key]:
                summary = _generate_cluster_summary(cluster)
                st.success(summary)
            
            # Show generated documents
            for doc_type, template in DOC_TEMPLATES.items():
                doc_key = f"doc_{cluster_id}_{doc_type}"
                if st.session_state.get(doc_key):
                    with st.container(border=True):
                        col_header, col_close = st.columns([4, 1])
                        with col_header:
                            st.markdown(f"### {template['icon']} {template['name']}")
                        with col_close:
                            if st.button("✖️", key=f"close_{doc_key}", help="Close"):
                                st.session_state[doc_key] = False
                                st.rerun()
                        
                        with st.spinner(f"Generating {template['name']}..."):
                            doc_content = _generate_document(doc_type, cluster)
                        st.markdown(doc_content)
                        
                        # Download button
                        st.download_button(
                            label=f"📥 Download as Markdown",
                            data=doc_content,
                            file_name=f"{cluster_id}_{doc_type.lower()}.md",
                            mime="text/markdown",
                            key=f"download_{doc_key}"
                        )
            
            # Collapsible insights section using button toggle (avoids nested expander issue)
            st.markdown("---")
            insights_key = f"show_insights_{cluster_id}"
            
            # Initialize state if not exists
            if insights_key not in st.session_state:
                st.session_state[insights_key] = False
            
            # Toggle button
            btn_label = f"📋 Hide {len(cluster_insights)} Insights" if st.session_state[insights_key] else f"📋 View {len(cluster_insights)} Insights"
            if st.button(btn_label, key=f"toggle_{cluster_id}", use_container_width=True):
                st.session_state[insights_key] = not st.session_state[insights_key]
                st.rerun()
            
            # Show insights if toggled on
            if st.session_state[insights_key]:
                for idx, ins in enumerate(cluster_insights[:25], 1):
                    title = ins.get("title") or _truncate(ins.get("text", ""), 60)
                    sentiment = ins.get("brand_sentiment", "Neutral")
                    type_tag = ins.get("type_tag", "Feedback")
                    sentiment_icon = "😊" if sentiment == "Positive" else "😠" if sentiment == "Negative" else "😐"
                    url = ins.get("url", "")
                    full_text = ins.get("text", "No text available")
                    
                    # Build signals list
                    signals = []
                    if ins.get("_payment_issue"): signals.append("💳")
                    if ins.get("_upi_flag"): signals.append("⚠️")
                    if ins.get("is_trust_issue"): signals.append("🛡️")
                    if ins.get("is_shipping_issue"): signals.append("📦")
                    if ins.get("is_ag_signal"): signals.append("✅")
                    if ins.get("is_vault_signal"): signals.append("🏦")
                    signal_str = " ".join(signals) if signals else ""
                    
                    # Compact card for each insight
                    with st.container(border=True):
                        st.markdown(f"**{idx}. {_truncate(title, 60)}** {sentiment_icon} `{type_tag}` {signal_str}")
                        st.caption(f"{_truncate(full_text, 150)}")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"📅 {ins.get('post_date', 'Unknown')} | 👤 {ins.get('persona', 'Unknown')}")
                        with col2:
                            if url:
                                st.markdown(f"[🔗 Source]({url})")
                
                # Load more button for insights
                if len(cluster_insights) > 25:
                    show_all_insights_key = f"show_all_insights_{cluster_id}"
                    if st.session_state.get(show_all_insights_key):
                        # Show remaining insights
                        for idx, ins in enumerate(cluster_insights[25:50], 26):
                            title = ins.get("title") or _truncate(ins.get("text", ""), 60)
                            sentiment = ins.get("brand_sentiment", "Neutral")
                            type_tag = ins.get("type_tag", "Feedback")
                            sentiment_icon = "😊" if sentiment == "Positive" else "😠" if sentiment == "Negative" else "😐"
                            url = ins.get("url", "")
                            full_text = ins.get("text", "No text available")
                            
                            with st.container(border=True):
                                st.markdown(f"**{idx}. {_truncate(title, 60)}** {sentiment_icon} `{type_tag}`")
                                st.caption(f"{_truncate(full_text, 150)}")
                                if url:
                                    st.markdown(f"[🔗 Source]({url})")
                        
                        if st.button("📤 Show Less", key=f"less_insights_{cluster_id}"):
                            st.session_state[show_all_insights_key] = False
                            st.rerun()
                    else:
                        remaining = len(cluster_insights) - 25
                        if st.button(f"📥 Load {min(remaining, 25)} More Insights", key=f"more_insights_{cluster_id}"):
                            st.session_state[show_all_insights_key] = True
                            st.rerun()
