# enhanced_insight_view.py — insight card rendering with GPT tools, pagination, badges, and feedback-aware updates
import os
import streamlit as st
from slugify import slugify
from sentence_transformers import util
from components.ai_suggester import (
    generate_pm_ideas, generate_prd_docx, generate_brd_docx,
    generate_prfaq_docx, generate_jira_bug_ticket, generate_gpt_doc,
    generate_multi_signal_prd
)

BADGE_COLORS = {
    "Complaint": "#FF6B6B", "Confusion": "#FFD166", "Feature Request": "#06D6A0",
    "Discussion": "#118AB2", "Praise": "#8AC926", "Neutral": "#A9A9A9",
    "Low": "#B5E48C", "Medium": "#F9C74F", "High": "#F94144",
    "Clear": "#4CAF50", "Needs Clarification": "#FF9800",
    "Discovery": "#90BE6D", "Purchase": "#F8961E", "Fulfillment": "#577590",
    "Post-Purchase": "#43AA8B", "Live Shopping": "#BC6FF1", "Search": "#118AB2"
}

def badge(label, color):
    return f"<span style='background:{color}; padding:4px 8px; border-radius:8px; color:white; font-size:0.85em'>{label}</span>"

OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

def render_insight_cards(filtered, model, per_page=10, key_prefix="insight"):
    if not filtered:
        st.info("No matching insights.")
        return

    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    if "page" not in st.session_state:
        st.session_state.page = 1

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.page = max(1, st.session_state.page - 1)
    with col2:
        st.markdown(f"**Page {st.session_state.page} of {total_pages}**")
    with col3:
        if st.button("Next ➡️"):
            st.session_state.page = min(total_pages, st.session_state.page + 1)

    start = (st.session_state.page - 1) * per_page
    paged = filtered[start:start + per_page]

    for idx, i in enumerate(paged, start=start):
        unique_id = f"{key_prefix}_{idx}"
        st.markdown(f"### 🧠 Insight: {i.get('title', i.get('text', '')[:60])}")

        tags = [
            badge(i.get("type_tag"), BADGE_COLORS.get(i.get("type_tag"), "#ccc")),
            badge(i.get("brand_sentiment"), BADGE_COLORS.get(i.get("brand_sentiment"), "#ccc")),
            badge(i.get("effort"), BADGE_COLORS.get(i.get("effort"), "#ccc")),
            badge(i.get("journey_stage"), BADGE_COLORS.get(i.get("journey_stage"), "#ccc")),
            badge(i.get("clarity"), BADGE_COLORS.get(i.get("clarity"), "#ccc"))
        ]
        st.markdown(" ".join(tags), unsafe_allow_html=True)

        st.caption(
            f"Score: {i.get('score', 0)} | Type: {i.get('type_tag')} > {i.get('type_subtag', '')} "
            f"({i.get('type_confidence')}%) | Effort: {i.get('effort')} | Brand: {i.get('target_brand')} | "
            f"Sentiment: {i.get('brand_sentiment')} ({i.get('sentiment_confidence')}%) | Persona: {i.get('persona')}"
        )

        # Link to original post if available
        if i.get("url"):
            st.markdown(f"[🔗 View Original Post]({i['url']})", unsafe_allow_html=True)

        with st.expander("🧠 Full Insight"):
            text = i.get("text", "")
            brand = i.get("target_brand", "eBay")
            st.markdown("**User Quote:**")
            st.markdown(f"> {text}")

            if OPENAI_KEY_PRESENT:
                with st.spinner("💡 Generating PM Suggestions..."):
                    try:
                        i["ideas"] = generate_pm_ideas(text, brand)
                    except Exception as e:
                        i["ideas"] = [f"[❌ GPT error: {str(e)}]"]

            if i.get("ideas"):
                st.markdown("**💡 PM Suggestions:**")
                for idea in i["ideas"]:
                    st.markdown(f"- {idea}")

            if st.button("🧼 Clarify This Insight", key=f"{unique_id}_clarify"):
                with st.spinner("Clarifying..."):
                    clarified = generate_gpt_doc(
                        f"Rewrite this vague user feedback in a clearer, more specific way:\n\n{text}",
                        "You are a PM rephrasing vague customer input."
                    )
                    st.success("✅ Clarified Insight:")
                    st.markdown(f"> {clarified}")

            if st.button("🏷️ Suggest Tags", key=f"{unique_id}_tags"):
                with st.spinner("Analyzing..."):
                    tags = generate_gpt_doc(
                        f"Suggest 3–5 product tags for this user feedback:\n\n{text}",
                        "You are tagging this signal with product themes."
                    )
                    st.info("💡 Suggested Tags:")
                    st.markdown(f"`{tags}`")

            if st.button("🧩 Bundle Similar Insights", key=f"{unique_id}_bundle"):
                base_embed = model.encode(text, convert_to_tensor=True)
                all_texts = [x["text"] for x in filtered]
                all_embeds = model.encode(all_texts, convert_to_tensor=True)
                similarities = util.pytorch_cos_sim(base_embed, all_embeds)[0]
                top_indices = similarities.argsort(descending=True)[:5]
                bundled = []
                st.markdown("**🧠 Related Insights:**")
                for j in top_indices:
                    related = filtered[j]
                    st.markdown(f"- _{related['text'][:180]}_")
                    bundled.append(related["text"])

                if st.button("📄 Generate Combined PRD", key=f"{unique_id}_bundle_prd"):
                    file_path = generate_multi_signal_prd(bundled, filename=f"bundle-{idx}")
                    if file_path and os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                "⬇️ Download Combined PRD",
                                f,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"{unique_id}_dl_bundle_prd"
                            )

            filename = slugify(i.get("title", text[:40]))[:64]
            doc_type = st.selectbox("Select document type to generate:", ["PRD", "BRD", "PRFAQ", "JIRA"], key=f"{unique_id}_doc_type")
            if st.button(f"Generate {doc_type}", key=f"{unique_id}_generate_doc"):
                with st.spinner(f"Generating {doc_type}..."):
                    file_path = None
                    if doc_type == "PRD":
                        file_path = generate_prd_docx(text, brand, filename)
                    elif doc_type == "BRD":
                        file_path = generate_brd_docx(text, brand, filename + "-brd")
                    elif doc_type == "PRFAQ":
                        file_path = generate_prfaq_docx(text, brand, filename + "-prfaq")
                    elif doc_type == "JIRA":
                        file_content = generate_jira_bug_ticket(text, brand)
                        st.download_button("⬇️ Download JIRA", file_content, file_name=f"jira-{filename}.md", mime="text/markdown", key=f"{unique_id}_dl_jira")

                    if file_path and os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                f"⬇️ Download {doc_type}",
                                f,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"{unique_id}_dl_doc"
                            )
                    else:
                        st.warning(f"⚠️ Failed to generate or locate {doc_type} document.")
