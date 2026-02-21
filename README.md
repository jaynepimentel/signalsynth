# 📡 SignalSynth

**AI-powered intelligence engine for eBay Collectibles & Trading Cards** — continuously scrapes 20+ community sources, enriches every post with sentiment and signal analysis, and synthesizes thousands of discussions into executive-ready product intelligence.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat&logo=python&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-green?style=flat&logo=openai&logoColor=white)

---

## Table of Contents

1. [What is SignalSynth?](#what-is-signalsynth)
2. [Getting Started (Users)](#getting-started-users)
3. [Tab Guide](#tab-guide)
4. [Ask AI — Your Starting Point](#ask-ai--your-starting-point)
5. [Where the Data Comes From](#where-the-data-comes-from)
6. [How Signals Are Enriched](#how-signals-are-enriched)
7. [Local Development](#local-development)
8. [Data Pipeline](#data-pipeline)
9. [Project Structure](#project-structure)
10. [Configuration](#configuration)
11. [Troubleshooting](#troubleshooting)

---

## What is SignalSynth?

SignalSynth is an internal intelligence tool built for eBay Collectibles & Trading Cards leadership. It solves a simple problem: **there are thousands of community discussions happening every week across Reddit, Twitter, YouTube, forums, and news sites — and no human can read them all.**

SignalSynth:
- **Scrapes** 20+ sources continuously (Reddit, Twitter/X, YouTube, eBay Forums, Bluesky, industry news, podcasts, competitor platforms, and more)
- **Enriches** every post with sentiment, topic classification, persona detection, churn risk scoring, and signal strength
- **Clusters** related signals into strategic themes automatically
- **Synthesizes** raw data into executive-ready briefs, PRDs, BRDs, and Jira tickets using GPT-4o

The target audience is VP/GM-level product leaders who need to answer questions like:
- *"What are the top complaints about the PSA Vault right now?"*
- *"How does Whatnot threaten us in live breaks?"*
- *"What do sellers want us to build next?"*

---

## Getting Started (Users)

### First Visit

1. Open SignalSynth in your browser
2. You'll see the **KPI banner** at the top (posts scraped, actionable insights, themes, estimated hours saved)
3. Below that is **Ask AI** — this is the fastest way to get answers
4. The **5 tabs** below contain structured views of all the data

### Daily Workflow (Recommended)

1. **Start with Ask AI** — type a question about anything on your mind. The AI will search all signals, cite sources, and give you a strategic answer.
2. **Check the Executive Pulse** on the Strategy & Overview tab — see sentiment metrics, signal health by topic (🔴🟡🟢), and competitor snapshot.
3. **Drill into issues** via Customer Signals → Issues & Health sub-tab if you need to understand a specific problem area.
4. **Generate artifacts** — when you find a theme worth acting on, use the 🧠 AI buttons to generate issue briefs, competitive analyses, or Problem → Solution syntheses. Use the Strategy tab to generate PRDs, BRDs, PRFAQs, or Jira tickets from any strategic theme.

### Tips

- **Ask AI is your power tool** — it searches all 4,000+ enriched signals, cites sources with links, and adapts its response format to your question type (competitive, strategic, product, or general).
- **Filters matter** — on the Customer Signals tab, use Topic, Type, and Time filters to focus on what you care about. Filters apply across all sub-tab sections.
- **Look for 🧠 buttons** — throughout the app, these generate AI-powered executive briefs, competitive analyses, and per-category summaries.
- **Copy and share** — AI Q&A responses have a 📋 Copy button so you can paste into Slack, email, or docs.
- **Live-search the web** — if Ask AI's answer has thin data, it will offer to scrape 6 live sources for that topic, add the results to the dataset, and re-analyze automatically.

---

## Tab Guide

SignalSynth has **5 tabs**, each serving a different analytical purpose:

### 📋 Strategy & Overview

Your executive dashboard. Contains:

| Section | What it shows |
|---------|--------------|
| **Executive Pulse** | Sentiment breakdown (negative, complaints, churn risks, feature asks, positive), last refresh timestamp |
| **Signal Health by Topic** | 🔴🟡🟢 health indicators for each product area (Vault, Shipping, Fees, etc.) based on % of negative signals |
| **Competitor Snapshot** | Quick signal counts per competitor |
| **Strategic Themes** | AI-clustered groups of related signals. Each theme represents a strategic area like "Vault Trust Issues" or "Shipping Friction." Drill into any theme → opportunity areas → supporting signals. Generate **PRDs, BRDs, PRFAQs, or Jira tickets** with one click. |

The **New Here?** expander (collapsed by default) contains the full onboarding guide and data source table.

### ⚔️ Competitor Intel

Competitive intelligence across Whatnot, Fanatics, Heritage Auctions, Alt, Goldin, TCGPlayer, Beckett, and PSA Consignment. For each competitor:

- **Actionable metrics** — complaints (conquest opportunities), praise (competitive threats), platform comparisons, policy/product changes
- **🧠 AI Competitive Brief** — generates threat assessment, vulnerability analysis, and eBay response playbook
- **Subsidiaries view** — separate analysis for Goldin and TCGPlayer (eBay-owned properties)
- **Per-signal AI briefs** — click ⚔️ on any complaint to generate a targeted conquest analysis

### 🎯 Customer Signals

Deep-dive executive briefing with **3 sub-tabs**:

**Issues & Health:**
- Health snapshot (6 metrics + top topics)
- Top issues to fix (broken windows analysis across 12 categories: Returns/INAD, Trust/Fraud, Vault Bugs, Fee Confusion, Shipping, Payments, Seller Protection, App/UX, Account/Policy, Search, Promoted Listings, Authentication)
- Problem breakdown by area with per-category AI analysis
- Each issue has owner assignment and severity scoring

**Asks & Churn:**
- Churn & retention risks — signals where users mention leaving eBay or switching
- What customers are asking for — grouped by product area (Vault, Shipping, Fees, etc.) with AI "Problem → Solution" synthesis that generates: 🔴 The Problem, 💡 What They Want, 📊 Evidence, 🎯 Suggested Jira Epic

**Partners & Explorer:**
- Partner health metrics for PSA Vault, PSA Grading, PSA Consignment, PSA Offers, and COMC
- Deep Dive Explorer — toggle to browse all signals with full AI analysis and document generation

### 📰 Industry & Trends

Market context from across the collectibles ecosystem:

- **Top Industry News** — time-weighted ranking (recency × engagement)
- **Industry News & Podcasts** — curated feed from Cllct, Beckett, Cardlines, Sports Card Nonsense, and more
- **eBay Price Guide Signals** — dedicated section for Card Ladder / Scan-to-Price feedback (positive, confused, negative breakdowns)
- **Full Industry Feed** — paginated, filterable feed of all industry content with source/search filters

### 📦 Releases & Checklists

Upcoming sealed product launches and published checklists from Topps, Panini, Bowman, Leaf, Upper Deck, and more. Filterable by sport/category and brand.

---

## Ask AI — Your Starting Point

Ask AI is the most powerful feature in SignalSynth. It sits above all tabs and is always accessible.

### How it works

1. **Type any question** in natural language
2. The system searches all enriched signals using term expansion (e.g., "vault" also searches "storage", "withdraw", "stuck in vault")
3. It builds context from the top 25 matching signals, cluster themes, competitor landscape, and recent industry news
4. GPT-4o generates a strategic response in an **adaptive format**:
   - **Competitive questions** → Executive Answer, Competitive Evidence, Threat Assessment, Strategic Response
   - **Strategic questions** → Strategic Assessment, Signal Evidence, Market Context, Recommended Strategy
   - **Product questions** → Product Assessment, User Evidence, Impact Analysis, Recommended Fixes
   - **General questions** → Executive Answer, What the Signals Show, Implications, Recommended Actions
5. Every claim is grounded in cited signals with **[S#] references** linked to source posts

### Example prompts

Use the **dropdown selector** below the input field to try pre-built prompts:
- *Is there any signal about PSA vault issues?*
- *How are buyers responding to the new unpaid item policies?*
- *What are sellers saying about authenticity guarantee rejections?*
- *How does Whatnot threaten eBay in live breaks?*
- *What shipping complaints are driving the most churn risk?*

### Live web search

If your question returns fewer than 5 matching signals, SignalSynth will offer to **live-search the web** — scraping Google News, Bing News, Reddit, Twitter/X, YouTube, and Bluesky for that topic in real-time, enriching the results, adding them to the dataset, and re-analyzing with the new data.

---

## Where the Data Comes From

SignalSynth pulls from **20+ sources** across the collectibles ecosystem:

| Source | What it captures | Scraper |
|--------|-----------------|---------|
| **Reddit** | 40+ subreddits: r/baseballcards, r/sportscards, r/eBay, r/pokemontcg, r/footballcards, r/funkopop, r/coins, and more | `scrape_reddit.py` |
| **Twitter / X** | Hobby influencers, eBay mentions, competitor chatter | `scrape_twitter.py` |
| **YouTube** | Jabs Family, Sports Card Investor, Stacking Slabs, CardShopLive, Gary Vee, Goldin — transcripts + top comments | `scrape_youtube.py` |
| **eBay Forums** | Seller & buyer discussions from eBay Community (real-time via Lithium API) | `scrape_ebay_forums.py` |
| **Bluesky** | Emerging hobby community signals | `scrape_bluesky.py` |
| **Cllct** | Industry news from Cllct.com | `scrape_cllct.py` |
| **News RSS** | Beckett, Cardlines, Cardboard Connection, Dave and Adams, Sports Collectors Daily, PSA Blog, Blowout Buzz, Just Collect Blog | `scrape_news_rss.py` |
| **Podcasts** | Sports Cards Nonsense, Sports Card Investor, Stacking Slabs, Hobby News Daily, The Pull-Tab Podcast, Collector Nation | `scrape_podcasts.py` |
| **Forums & Blogs** | Blowout Forums, Net54, Bench Trading, Alt.xyz, COMC, Whatnot, Fanatics Collect, TCDB | `scrape_forums_blogs.py` |
| **Competitors** | Whatnot, Fanatics Collect, Fanatics Live, Heritage Auctions, Alt, Goldin, TCGPlayer, Beckett, PSA Consignment | `scrape_competitors.py` |
| **Releases** | Upcoming sealed product launches and checklists | `scrape_releases.py` |

**Current dataset size:** ~22,000 posts scraped → ~3,900 actionable insights across 22 unique sources.

---

## How Signals Are Enriched

Every scraped post goes through a multi-step enrichment pipeline (`quick_process.py`):

1. **Relevance filtering** — keyword and context matching to keep only collectibles/marketplace-relevant posts
2. **Sentiment classification** — Positive / Negative / Neutral brand sentiment
3. **Topic classification** — Vault, Shipping, Fees, Trust, Grading, Authentication, Returns, App/UX, etc.
4. **Type tagging** — Complaint, Feature Request, Bug Report, Discussion, Praise, Churn Signal
5. **Persona detection** — Power Seller, Collector, Investor, New Seller, Casual Buyer
6. **Signal strength scoring** — 0-100 score based on engagement, specificity, and actionability
7. **Churn risk flagging** — detects "leaving eBay", "switching to", "done with" signals
8. **Theme assignment** — maps to strategic themes for the cluster view
9. **Deduplication** — fuzzy text matching and URL dedup across sources

The enriched data is saved to `precomputed_insights.json`. Strategic clusters are computed separately in `precompute_clusters.py` using embedding-based similarity grouping, saved to `precomputed_clusters.json`.

---

## Local Development

### Prerequisites

- Python 3.11+
- OpenAI API key (required for AI features)

### Setup

```bash
# Clone the repo
git clone https://github.com/jaynepimentel/signalsynth.git
cd signalsynth

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your OpenAI API key

# Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## Data Pipeline

The full data refresh pipeline runs in 3 stages:

### Stage 1: Scrape

```bash
# Run all scrapers at once (recommended)
python utils/scrape_all.py

# Or run individual scrapers
python utils/scrape_reddit.py
python utils/scrape_ebay_forums.py
python utils/scrape_competitors.py
python utils/scrape_youtube.py
python utils/scrape_twitter.py
python utils/scrape_bluesky.py
python utils/scrape_cllct.py
python utils/scrape_news_rss.py
python utils/scrape_podcasts.py
python utils/scrape_forums_blogs.py
python utils/scrape_releases.py
```

Output: JSON files in `data/` directory (e.g., `data/all_scraped_posts.json`, `data/scraped_competitor_posts.json`).

### Stage 2: Process & Enrich

```bash
python quick_process.py
```

This filters for relevance, enriches with sentiment/topic/persona tags, deduplicates, and saves:
- `precomputed_insights.json` — all enriched insights
- `_pipeline_meta.json` — pipeline statistics (post counts, source distribution, timestamp)

### Stage 3: Cluster

```bash
python precompute_clusters.py
```

Groups related signals into strategic themes using embedding similarity, saves to `precomputed_clusters.json`.

### Full refresh (all 3 stages)

```bash
python utils/scrape_all.py && python quick_process.py && python precompute_clusters.py
```

After running the pipeline, restart the Streamlit app to see updated data.

---

## Project Structure

```
signalsynth/
├── app.py                          # Main Streamlit application (2,400 lines)
│
├── components/                     # UI components and AI integrations
│   ├── ai_suggester.py             # LLM integration (GPT-4o), document generation
│   ├── cluster_view_simple.py      # Strategic theme display + PRD/BRD/PRFAQ/Jira generation
│   ├── enhanced_insight_view.py    # Individual insight cards with AI analysis
│   ├── floating_filters.py         # Topic/Type/Time filter UI
│   ├── scoring_utils.py            # Signal strength and relevance scoring
│   ├── cluster_synthesizer.py      # Cluster creation and summarization
│   ├── brand_sentiment_classifier.py # Sentiment classification
│   ├── enhanced_classifier.py      # Multi-label topic classification
│   └── export_utils.py             # DOCX export utilities
│
├── utils/                          # Data scrapers
│   ├── scrape_all.py               # Master scraper (runs all sources)
│   ├── scrape_reddit.py            # Reddit (40+ subreddits)
│   ├── scrape_ebay_forums.py       # eBay Community Forums (Lithium API)
│   ├── scrape_competitors.py       # 9 competitors & eBay subsidiaries
│   ├── scrape_youtube.py           # YouTube transcripts + comments
│   ├── scrape_twitter.py           # Twitter/X (via Google News indexing)
│   ├── scrape_bluesky.py           # Bluesky public API
│   ├── scrape_cllct.py             # Cllct.com industry news
│   ├── scrape_news_rss.py          # 8 RSS news feeds
│   ├── scrape_podcasts.py          # 6 podcast feeds
│   ├── scrape_forums_blogs.py      # 8 forums and blogs
│   ├── scrape_releases.py          # Product releases and checklists
│   ├── adhoc_scrape.py             # On-demand web search (6 sources)
│   └── load_scraped_insights.py    # Data loading utilities
│
├── data/                           # Scraped raw data (gitignored)
│   ├── all_scraped_posts.json
│   ├── scraped_competitor_posts.json
│   ├── scraped_youtube_posts.json
│   └── ... (12+ source files)
│
├── quick_process.py                # Enrichment pipeline
├── precompute_clusters.py          # Cluster generation
├── precomputed_insights.json       # Enriched insights (loaded by app)
├── precomputed_clusters.json       # Strategic clusters (loaded by app)
├── _pipeline_meta.json             # Pipeline stats (freshness, counts)
│
├── .env                            # API keys (gitignored)
├── .env.example                    # Template for .env
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | Powers all AI features (Ask AI, briefs, document generation) |
| `OPENAI_MODEL_PREMIUM` | No | Reasoning model for Ask AI (default: `o3-mini`) — best analytical depth |
| `OPENAI_MODEL_MAIN` | No | Primary model for briefs, PRDs, competitive analysis (default: `gpt-4.1`) |
| `OPENAI_MODEL_SCREENER` | No | Fast model for classification/screening (default: `gpt-4.1-mini`) |
| `TWITTER_BEARER_TOKEN` | No | Twitter API access (currently uses Google News fallback) |

### Streamlit Cloud Deployment

For Streamlit Cloud, add secrets in the dashboard:

```toml
# .streamlit/secrets.toml
OPENAI_API_KEY = "sk-..."
```

---

## Signal Types & Severity

### Signal types detected automatically

| Type | Description |
|------|-------------|
| **Complaint** | User expressing frustration with a product, feature, or policy |
| **Feature Request** | User asking for something new or improved |
| **Bug Report** | User reporting a technical issue |
| **Discussion** | General conversation about a topic |
| **Praise** | Positive feedback about eBay or a feature |
| **Churn Signal** | User mentioning leaving eBay or switching to a competitor |

### Severity indicators

| Indicator | Meaning |
|-----------|---------|
| 🔴 | High severity — >40% negative signals or 20+ issues in the area |
| 🟡 | Medium severity — >15% negative signals or 10+ issues |
| 🟢 | Healthy — low proportion of negative signals |

### Product areas tracked

Vault · Trust · Payments · Shipping · Grading · Authentication · Returns & Refunds · Fees · Seller Experience · Buyer Experience · App & UX · Price Guide · Search · Promoted Listings · Account Issues · Customer Service

---

## Troubleshooting

### App won't start

```
streamlit run app.py
```

If you see `Failed to load data`, ensure `precomputed_insights.json` exists. Run the pipeline:
```bash
python quick_process.py
python precompute_clusters.py
```

### AI features not working

Check that `OPENAI_API_KEY` is set in your `.env` file and is valid. The app will show a warning banner if the key is missing.

### Data looks stale

Check the **Last data refresh** timestamp on the Strategy & Overview tab. If it's old, re-run the scraping pipeline:
```bash
python utils/scrape_all.py && python quick_process.py && python precompute_clusters.py
```
Then restart the Streamlit app (the file watcher is disabled for performance).

### Streamlit changes not appearing

The file watcher is intentionally disabled (`STREAMLIT_SERVER_FILE_WATCHER_TYPE=none` in `app.py`). You must restart the Streamlit process to see code changes:
```bash
# Kill existing process and restart
streamlit run app.py
```

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

Built for the eBay Collectibles & Trading Cards team.
