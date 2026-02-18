# brand_trend_dashboard.py — Strategic dashboard with competitors, partners, and brand insights
import pandas as pd
import streamlit as st
import altair as alt

# Define entity categories
COMPETITORS = ["Fanatics Collect", "Fanatics Live", "Heritage Auctions", "MySlabs", "Whatnot"]
PARTNERS = ["PSA", "ComC", "BGS", "CGC", "SGC"]
SUBSIDIARIES = ["Goldin", "TCGPlayer"]

def categorize_entity(text, subtag=None):
    """Categorize an insight by entity type based on text content.
    
    Returns a granular category instead of a single 'eBay Core' catch-all.
    External entities (Competitor, Partner, Subsidiary) are detected from text.
    eBay signals are split by product area using the subtag field.
    """
    text_lower = (text or "").lower()
    
    # Check partners first (PSA services)
    if any(p.lower() in text_lower for p in ["psa vault", "psa grading", "psa consignment", "psa offer", "comc", "check out my cards"]):
        return "Partner"
    
    # Check competitors
    if any(c.lower() in text_lower for c in COMPETITORS):
        return "Competitor"
    if any(phrase in text_lower for phrase in ["alt.xyz", "alt marketplace", "alt vault", "alt platform"]):
        return "Competitor"
    
    # Check subsidiaries
    if any(s.lower() in text_lower for s in SUBSIDIARIES):
        return "Subsidiary"
    
    # Split eBay signals by product area using subtag
    SUBTAG_TO_ENTITY = {
        "Trust": "Trust & Safety",
        "Payments": "Payments",
        "Vault": "Vault",
        "Authenticity Guarantee": "Authentication",
        "Shipping": "Shipping",
        "Returns & Refunds": "Returns & Refunds",
        "Fees": "Fees & Pricing",
        "Grading Turnaround": "Grading",
        "Price Guide": "Fees & Pricing",
        "Seller Experience": "Seller Experience",
        "Buyer Experience": "Buyer Experience",
        "Collecting": "Collecting",
        "High-Value": "High-Value Items",
    }
    if subtag and subtag in SUBTAG_TO_ENTITY:
        return SUBTAG_TO_ENTITY[subtag]
    
    # Fallback: try to detect from text
    if any(w in text_lower for w in ["scam", "fake", "counterfeit", "fraud", "trust", "legit"]):
        return "Trust & Safety"
    if any(w in text_lower for w in ["vault"]):
        return "Vault"
    if any(w in text_lower for w in ["authentication", "authenticity"]):
        return "Authentication"
    if any(w in text_lower for w in ["payment", "checkout", "payout"]):
        return "Payments"
    if any(w in text_lower for w in ["shipping", "delivery", "package"]):
        return "Shipping"
    if any(w in text_lower for w in ["seller", "listing", "sold"]):
        return "Seller Experience"
    if any(w in text_lower for w in ["buyer", "bought", "purchase"]):
        return "Buyer Experience"
    
    return "General"

def detect_brand_from_text(text):
    """Detect brand/entity from text content. Returns primary brand + signal type."""
    text_lower = (text or "").lower()
    
    # Partners - PSA services
    if "psa vault" in text_lower or ("vault" in text_lower and "psa" in text_lower):
        return "PSA Vault"
    if "psa" in text_lower and ("grading" in text_lower or "grade" in text_lower or "turnaround" in text_lower or "submission" in text_lower):
        return "PSA Grading"
    if "psa" in text_lower and ("consignment" in text_lower or "consign" in text_lower):
        return "PSA Consignment"
    if "psa" in text_lower and ("offer" in text_lower or "buyback" in text_lower):
        return "PSA Offers"
    if "psa" in text_lower:
        return "PSA"
    if "comc" in text_lower or "check out my cards" in text_lower:
        return "ComC"
    if "bgs" in text_lower or "beckett" in text_lower:
        return "BGS/Beckett"
    if "cgc" in text_lower:
        return "CGC"
    if "sgc" in text_lower:
        return "SGC"
    
    # Competitors
    if "fanatics" in text_lower:
        return "Fanatics"
    if "heritage" in text_lower:
        return "Heritage"
    if "alt.xyz" in text_lower or "alt marketplace" in text_lower or "alt vault" in text_lower:
        return "Alt"
    if "whatnot" in text_lower:
        return "Whatnot"
    if "pwcc" in text_lower:
        return "Fanatics Collect"  # PWCC rebranded to Fanatics Collect
    if "myslabs" in text_lower:
        return "MySlabs"
    
    # Subsidiaries
    if "goldin" in text_lower:
        return "Goldin"
    if "tcgplayer" in text_lower or "tcg player" in text_lower:
        return "TCGPlayer"
    
    # eBay specific features/issues
    if "vault" in text_lower and "ebay" in text_lower:
        return "eBay Vault"
    if "authenticity guarantee" in text_lower or " ag " in text_lower or "authentication" in text_lower:
        return "eBay AG"
    if "managed payments" in text_lower or "payout" in text_lower or "payment processing" in text_lower:
        return "eBay Payments"
    if "shipping" in text_lower and "ebay" in text_lower:
        return "eBay Shipping"
    if "fees" in text_lower and "ebay" in text_lower:
        return "eBay Fees"
    if "refund" in text_lower or "return" in text_lower:
        return "eBay Returns"
    
    # General eBay
    if "ebay" in text_lower:
        return "eBay"
    
    # Collectibles categories
    if "pokemon" in text_lower or "pokémon" in text_lower:
        return "Pokemon"
    if "sports card" in text_lower or "baseball card" in text_lower or "football card" in text_lower:
        return "Sports Cards"
    if "magic" in text_lower and ("gathering" in text_lower or "mtg" in text_lower or "card" in text_lower):
        return "MTG"
    if "yugioh" in text_lower or "yu-gi-oh" in text_lower:
        return "Yu-Gi-Oh"
    
    return "Other"


def summarize_brand_insights(insights):
    rows = []
    for i in insights:
        text = i.get("text", "") + " " + i.get("title", "")
        # Detect brand from text instead of relying on target_brand field
        brand = detect_brand_from_text(text)
        sentiment = i.get("brand_sentiment", "Neutral")
        logged_at = i.get("_logged_at") or i.get("post_date")
        entity_type = categorize_entity(text, subtag=i.get("subtag"))
        rows.append((brand, sentiment, logged_at, entity_type))

    df = pd.DataFrame(rows, columns=["Brand", "Sentiment", "Date", "EntityType"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    sentiment_counts = df.groupby(["Brand", "Sentiment"]).size().unstack(fill_value=0).reset_index()

    # Add Complaint %
    sentiment_cols = [col for col in sentiment_counts.columns if col not in ["Brand"]]
    sentiment_counts["Total"] = sentiment_counts[sentiment_cols].sum(axis=1)
    if "Negative" in sentiment_counts.columns:
        sentiment_counts["Complaint %"] = round((sentiment_counts["Negative"] / sentiment_counts["Total"].replace(0, 1)) * 100, 1)
    else:
        sentiment_counts["Complaint %"] = 0

    return df, sentiment_counts

def display_brand_dashboard(insights):
    st.header("📊 Strategic Intelligence Dashboard")
    
    df, summary = summarize_brand_insights(insights)
    
    # Strategic Overview Section
    st.subheader("🎯 Strategic Overview")
    
    # Entity type metrics — show top categories dynamically
    entity_counts = df["EntityType"].value_counts()
    top_entities = entity_counts.head(4)
    ENTITY_ICONS = {
        "Trust & Safety": "\U0001f6e1\ufe0f",
        "Seller Experience": "\U0001f4e6",
        "Buyer Experience": "\U0001f6d2",
        "Payments": "\U0001f4b3",
        "Vault": "\U0001f3e6",
        "Authentication": "\U0001f50d",
        "Shipping": "\U0001f69a",
        "Returns & Refunds": "\U0001f504",
        "Fees & Pricing": "\U0001f4b0",
        "Grading": "\U0001f3af",
        "High-Value Items": "\U0001f48e",
        "Collecting": "\U0001f0cf",
        "Competitor": "\u2694\ufe0f",
        "Partner": "\U0001f91d",
        "Subsidiary": "\U0001f3e2",
        "General": "\U0001f4cb",
    }
    metric_cols = st.columns(len(top_entities))
    for col, (entity, count) in zip(metric_cols, top_entities.items()):
        icon = ENTITY_ICONS.get(entity, "\U0001f4ca")
        col.metric(f"{icon} {entity}", count)
    
    # Sentiment by entity type
    st.subheader("📈 Sentiment by Entity Type")
    entity_sentiment = df.groupby(["EntityType", "Sentiment"]).size().reset_index(name="Count")
    
    if len(entity_sentiment) > 0:
        # Create highlight selection
        highlight = alt.selection_point(on='mouseover', fields=['EntityType'], nearest=True)
        
        chart = alt.Chart(entity_sentiment).mark_bar().encode(
            x=alt.X("EntityType:N", title="Entity Type", sort="-y"),
            y=alt.Y("Count:Q", title="Signal Count"),
            color=alt.Color("Sentiment:N", scale=alt.Scale(
                domain=["Positive", "Neutral", "Negative"],
                range=["#22c55e", "#94a3b8", "#ef4444"]
            )),
            opacity=alt.condition(highlight, alt.value(1), alt.value(0.6)),
            tooltip=["EntityType", "Sentiment", "Count"]
        ).add_params(highlight).properties(height=300)
        
        st.altair_chart(chart, use_container_width=True)
    
    # Competitor vs Partner Trend Over Time
    st.subheader("📉 Entity Trends Over Time")
    st.caption("Hover to highlight. Last 60 days only for readability.")
    
    df_dated = df[df["Date"].notna()].copy()
    if len(df_dated) > 0:
        # Limit to last 60 days for readability
        max_date = df_dated["Date"].max()
        min_date = max_date - pd.Timedelta(days=60)
        df_dated = df_dated[df_dated["Date"] >= min_date]
        
        df_dated["Week"] = df_dated["Date"].dt.to_period("W").dt.start_time
        trend_data = df_dated.groupby(["Week", "EntityType"]).size().reset_index(name="Count")
        
        if len(trend_data) > 0:
            highlight = alt.selection_point(on='mouseover', fields=['EntityType'], nearest=True)
            
            base = alt.Chart(trend_data).encode(
                x=alt.X("Week:T", title="Week", axis=alt.Axis(format="%b %d")),
                y=alt.Y("Count:Q", title="Signals"),
                color=alt.Color("EntityType:N", title="Entity", scale=alt.Scale(scheme="tableau10")),
                tooltip=[
                    alt.Tooltip("EntityType:N", title="Entity"),
                    alt.Tooltip("Week:T", title="Week", format="%b %d, %Y"),
                    alt.Tooltip("Count:Q", title="Signals")
                ]
            )
            
            lines = base.mark_line(strokeWidth=3).encode(
                opacity=alt.condition(highlight, alt.value(1), alt.value(0.2)),
                strokeWidth=alt.condition(highlight, alt.value(4), alt.value(1.5))
            ).add_params(highlight)
            
            points = base.mark_circle(size=60).encode(
                opacity=alt.condition(highlight, alt.value(1), alt.value(0))
            )
            
            chart = (lines + points).properties(height=350)
            st.altair_chart(chart, use_container_width=True)
    
    # Brand-Level Analysis (expandable)
    with st.expander("🏷️ Brand-Level Detail", expanded=False):
        st.markdown("Compare specific brands across competitors, partners, and subsidiaries.")
        
        # Exclude generic/untagged brands
        EXCLUDE_BRANDS = {"Other", "eBay"}
        brand_list = sorted([b for b in df["Brand"].dropna().unique() if b not in EXCLUDE_BRANDS])
        if not brand_list:
            st.info("No specific brands detected in the data.")
        else:
            selected_brands = st.multiselect("🔎 Filter by Brand", options=brand_list, default=brand_list[:10] if len(brand_list) > 10 else brand_list, key="brand_filter_trends")
            filtered_df = df[df["Brand"].isin(selected_brands)]
            filtered_summary = summary[summary["Brand"].isin(selected_brands)]

            # Summary Table
            if len(filtered_summary) > 0:
                st.dataframe(
                    filtered_summary.sort_values("Complaint %", ascending=False)[["Brand", "Total", "Complaint %"]].head(15),
                    use_container_width=True,
                    hide_index=True
                )

            # Brand trend chart
            if len(filtered_df) > 0 and filtered_df["Date"].notna().any():
                st.markdown("**📈 Brand Volume Over Time** (last 60 days)")
                
                brand_df = filtered_df[filtered_df["Date"].notna()].copy()
                max_date = brand_df["Date"].max()
                min_date = max_date - pd.Timedelta(days=60)
                brand_df = brand_df[brand_df["Date"] >= min_date]
                
                daily_counts = (
                    brand_df
                    .groupby([pd.Grouper(key="Date", freq="W"), "Brand"])
                    .size()
                    .reset_index(name="Mentions")
                )
                
                if len(daily_counts) > 0:
                    top_brands = daily_counts.groupby("Brand")["Mentions"].sum().nlargest(6).index.tolist()
                    daily_counts = daily_counts[daily_counts["Brand"].isin(top_brands)]
                    
                    highlight = alt.selection_point(on='mouseover', fields=['Brand'], nearest=True)
                    
                    base = alt.Chart(daily_counts).encode(
                        x=alt.X("Date:T", title="Week"),
                        y=alt.Y("Mentions:Q", title="Mentions"),
                        color=alt.Color("Brand:N", legend=alt.Legend(orient="bottom", columns=3)),
                        tooltip=["Brand", "Date:T", "Mentions"]
                    )
                    
                    lines = base.mark_line(strokeWidth=2).encode(
                        opacity=alt.condition(highlight, alt.value(1), alt.value(0.15)),
                        strokeWidth=alt.condition(highlight, alt.value(3), alt.value(1))
                    ).add_params(highlight)
                    
                    points = base.mark_circle(size=50).encode(
                        opacity=alt.condition(highlight, alt.value(1), alt.value(0))
                    )
                    
                    chart = (lines + points).properties(height=300)
                    st.altair_chart(chart, use_container_width=True)
    
    # Competitive Intelligence (expandable)
    with st.expander("⚔️ Competitive Intelligence", expanded=False):
        competitor_df = df[df["EntityType"] == "Competitor"]
        if len(competitor_df) > 0:
            comp_sentiment = competitor_df.groupby("Sentiment").size()
            neg_pct = round(comp_sentiment.get("Negative", 0) / max(len(competitor_df), 1) * 100, 1)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Competitor Signals", len(competitor_df))
            with col2:
                st.metric("Negative %", f"{neg_pct}%")
            with col3:
                # Exclude eBay-branded entries from competitor ranking
                comp_brands = competitor_df[~competitor_df["Brand"].str.startswith("eBay")]["Brand"].value_counts()
                top_comp = comp_brands.idxmax() if len(comp_brands) > 0 else "N/A"
                st.metric("Most Discussed", top_comp)
            
            st.markdown("**🎯 Competitor Opportunity:** High negative sentiment on competitors = potential win-back opportunity.")
        else:
            st.info("No competitor signals found in current data.")
    
    # Partner Intelligence (expandable)
    with st.expander("🤝 Partner Intelligence", expanded=False):
        partner_df = df[df["EntityType"] == "Partner"]
        if len(partner_df) > 0:
            partner_sentiment = partner_df.groupby("Sentiment").size()
            neg_pct = round(partner_sentiment.get("Negative", 0) / max(len(partner_df), 1) * 100, 1)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Partner Signals", len(partner_df))
            with col2:
                st.metric("Negative %", f"{neg_pct}%")
            with col3:
                if neg_pct > 30:
                    st.metric("Partner Health", "🔴 At Risk")
                elif neg_pct > 15:
                    st.metric("Partner Health", "🟡 Watch")
                else:
                    st.metric("Partner Health", "🟢 Healthy")
            
            if neg_pct > 30:
                st.markdown(f"**🤝 Partner Insight:** {neg_pct}% negative sentiment — partner experience is degrading eBay seller trust. Escalate to partnerships team.")
            elif neg_pct > 15:
                st.markdown(f"**🤝 Partner Insight:** {neg_pct}% negative sentiment — monitor for emerging partner service issues.")
            else:
                st.markdown("**🤝 Partner Insight:** Partner sentiment is healthy. Continue monitoring.")
        else:
            st.info("No partner signals found in current data.")
