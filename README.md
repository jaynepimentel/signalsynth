# 🧠 SignalSynth

**AI-powered insight engine for eBay Collectibles** — transforming thousands of community discussions into actionable product intelligence.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat&logo=python&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-green?style=flat&logo=openai&logoColor=white)

## 🚀 Live Demo

**[signalsynth.streamlit.app](https://jaynebrain.streamlit.app)**

---

## 📊 Features

### Six Strategic Tabs

| Tab | Purpose | Key Action |
|-----|---------|------------|
| 🧱 **Clusters** | Strategic epics grouped by theme | Generate PRDs, BRDs, Jira tickets |
| 📌 **Insights** | Individual signals with filters | Filter by topic, type, sentiment |
| 🏢 **Competitors** | What users say about rivals | ⚔️ War Games — competitive strategy |
| 🏪 **Subsidiaries** | Goldin & TCGPlayer feedback | 🔧 Action Plan — improvement roadmap |
| 🤝 **Partners** | PSA & ComC partner intelligence | 📋 Partner Docs — strategy briefs |
| 📈 **Trends** | Sentiment & volume over time | Spot emerging issues |

### Data Sources

- **Reddit** — 33 collectibles subreddits + targeted searches
- **Competitors** — Fanatics, Heritage Auctions, Alt, PWCC
- **Subsidiaries** — Goldin, TCGPlayer
- **Partners** — PSA (Vault, Grading, Consignment), ComC

### AI-Powered Documents

- 🤖 **Executive Summary** — Problem, impact, key drivers, recommendation
- 📄 **PRD** — User stories, requirements, success metrics
- 💼 **BRD** — Business case for stakeholders
- 📰 **PRFAQ** — Amazon-style press release + FAQ
- 🎫 **Jira Tickets** — Sprint-ready with acceptance criteria

---

## 🛠️ Local Development

### Prerequisites

- Python 3.11+
- OpenAI API key

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
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Run the app
streamlit run app.py
```

### Data Pipeline

```bash
# Scrape new data
python utils/scrape_reddit.py
python utils/scrape_competitors.py

# Process insights
python process_scraped_data.py

# Generate clusters
python precompute_clusters.py
```

---

## 📁 Project Structure

```
signalsynth/
├── app.py                      # Main Streamlit app
├── components/                 # UI components
│   ├── cluster_view_simple.py  # Cluster display + doc generation
│   ├── brand_trend_dashboard.py # Trends & brand analysis
│   ├── insight_visualizer.py   # Charts & graphs
│   └── ai_suggester.py         # LLM integration
├── utils/                      # Scrapers
│   ├── scrape_reddit.py
│   ├── scrape_competitors.py
│   └── scrape_bluesky.py
├── data/                       # Scraped posts (gitignored)
├── precomputed_insights.json   # Processed insights
├── precomputed_clusters.json   # Clustered epics
└── requirements.txt
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for LLM features |
| `REDDIT_CLIENT_ID` | Optional: for Reddit scraping |
| `REDDIT_CLIENT_SECRET` | Optional: for Reddit scraping |

### Streamlit Secrets (Cloud)

Add secrets in Streamlit Cloud dashboard:

```toml
OPENAI_API_KEY = "sk-..."
```

---

## 📈 Signal Detection

Auto-detected signal types:
- 💳 **Payments** — Payment flow issues
- 🛡️ **Trust** — Authenticity concerns
- 📦 **Shipping** — Delivery problems
- ✅ **AG** — Authenticity Guarantee
- 🏦 **Vault** — PSA Vault signals
- ⚠️ **UPI** — Unpaid item issues
- 🎯 **Grading** — PSA turnaround

---

## 📝 License

MIT License — See [LICENSE](LICENSE) for details.

---

Built with ❤️
