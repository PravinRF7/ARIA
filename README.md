# 🛰️ ARIA: AI Research & Intelligence Aggregator

ARIA is an autonomous, multi-agent intelligence pipeline designed to combat information overload in the AI and Cloud engineering spaces. It fetches hundreds of raw data points daily, filters them via LLMs to find the signal in the noise, compares new items against historical data, and delivers a curated, high-impact daily brief.

Built with Python, `asyncio`, ChromaDB, Groq (Llama 3.3), and Google AI Studio.

---

## 🏗️ Architecture (The 4 Phases)

ARIA operates in a fully automated, four-phase daily pipeline:

### 1. Data Ingestion (Parallel Fetchers)
ARIA concurrently pulls raw data from 5 targeted sources using asynchronous Python:
*   **HackerNews:** Top 100 trending tech stories.
*   **GitHub Trending:** Daily trending open-source repositories.
*   **ArXiv:** Latest papers in `cs.AI`, `cs.LG`, and `cs.CL`.
*   **AWS Blogs:** Official ML and Architecture RSS feeds.
*   **Tavily Search API:** Live search for breaking news on AI models and tools.
*   *Output:* Deduplicated list of ~200 raw items.

### 2. The Collector Agent (Groq + Llama 3.3 70B)
Acting as the high-volume triage layer, the Collector processes the 200 raw items in batches. It enforces a strict scoring rubric (1-10) and drops anything scoring below a 7 or anything related to general world news.
*   *Output:* A refined list of the 10-20 most critical technical updates.

### 3. The Historian Agent & Memory (ChromaDB)
The Historian provides crucial context. Using local vector storage (ChromaDB), it queries the memory bank for the 3 most semantically similar past items. A Groq-powered LLM then compares the new item to its predecessors (e.g., Llama 4 vs Llama 3) to articulate the exact "Delta".
*   *Output:* An "Old vs. New" contextual paragraph attached to the item before saving back to the DB.

### 4. The Analyst & Output Router (Groq/Gemini + MS Teams)
The Analyst takes the filtered, contextualized items and writes a detailed, opinionated brief containing: *What It Is, The Delta, Why It Matters, Where To Use It, and an Impact Score (Low/Medium/High/Game-Changer)*.
The Output Router then:
*   Saves the full brief as a beautifully formatted local Markdown report.
*   Broadcasts the top 3 High/Game-Changer items to an **MS Teams** channel via Webhook.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.11+
*   API Keys for: Groq, Gemini (optional fallback), Tavily

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/PravinRF7/ARIA.git
    cd ARIA
    ```

2.  **Set up the virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: Ensure `chromadb`, `sentence-transformers`, `groq`, `google-generativeai`, `tavily-python`, and `requests` are installed).*

4.  **Configure Environment Variables:**
    Create a `.env` file in the root directory and add your keys:
    ```env
    GROQ_API_KEY=your_groq_key
    GEMINI_API_KEY=your_gemini_key
    TAVILY_API_KEY=your_tavily_key
    TEAMS_WEBHOOK_URL=your_ms_teams_webhook_url
    NOTIFY_MODE=True
    ```

---

## 🛠️ Usage

### Run the Pipeline Manually
To execute the full end-to-end pipeline immediately:
```bash
source .venv/bin/activate
python main.py
```

### Run in Test Mode
To test the pipeline without burning through your API limits, edit `main.py` and set `TEST_MODE = True`. This truncates the fetch list to just 3 items.

### Automated Cron Job
A shell script (`run_aria.sh`) is included to automate the pipeline. To run it daily at 6:30 PM IST (13:00 UTC), add this to your crontab:
```bash
0 13 * * * /path/to/ARIA/run_aria.sh >> /path/to/ARIA/logs/cron.log 2>&1
```

---

## 📁 Project Structure

```text
ARIA/
├── agents/
│   ├── analyst.py       # Writes the final detailed briefs
│   ├── collector.py     # High-volume scoring and filtering
│   └── historian.py     # ChromaDB contextual analysis
├── fetchers/            # Async data ingestion scripts
│   ├── arxiv.py
│   ├── aws_blog.py
│   ├── github_trending.py
│   ├── hackernews.py
│   └── tavily_search.py
├── memory/              # Local persistent ChromaDB storage
├── output/              # Output Routing
│   ├── router.py        # Orchestrates the broadcast
│   └── teams_notifier.py# MS Teams Adaptive Cards
├── reports/             # Generated daily Markdown reports
├── logs/                # System execution logs
├── config.py            # Centralized settings and prompts
├── main.py              # The pipeline orchestrator
├── backfill.py          # Script to pre-load ChromaDB from old reports
└── run_aria.sh          # Cron execution script
```

---
*Built as a multi-agent engineering architecture demonstration.*
