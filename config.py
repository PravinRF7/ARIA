"""
ARIA — Shared Configuration & Constants
─────────────────────────────────────────
Central place for keywords, settings, and helpers used across all fetchers.
"""

import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── API Keys ──────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Phase 4: Notification Keys ───────────────────────
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ARIA_EMAIL_TO = os.getenv("ARIA_EMAIL_TO", "")
ARIA_EMAIL_FROM = os.getenv("ARIA_EMAIL_FROM", "aria@example.com")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
NOTIFY_MODE = os.getenv("NOTIFY_MODE", "False").lower() == "true"

# ── Agent Models ─────────────────────────────────────
COLLECTOR_MODEL = "llama-3.1-8b-instant"
HISTORIAN_MODEL = "llama-3.1-8b-instant"
ANALYST_MODEL = "llama-3.3-70b-versatile"

# ── Collector Config ─────────────────────────────────
COLLECTOR_BATCH_SIZE = 10      # items per LLM batch
COLLECTOR_BATCH_DELAY = 2.0    # seconds between batches
COLLECTOR_MIN_SCORE = 7        # only items ≥ 7 pass through
COLLECTOR_MAX_ITEMS = 20       # cap on items going to analyst

COLLECTOR_SYSTEM_PROMPT = (
    "You are a technical relevance scorer. Given a news item or repository, "
    "score it 1-10 based on: (1) Is this genuinely new, not trivial? "
    "(2) Does it represent a meaningful shift in capability or approach? "
    "(3) Is it from a credible source with measurable engagement? "
    "HARD RULE: Any item about politics, military, sports, entertainment, finance, "
    "or general world news must receive a score of 1 regardless of any other factor. "
    "ARIA covers ONLY: AI models, machine learning, cloud infrastructure, developer "
    "tools, and open source software. "
    "Score 7+ only for items a senior AI/cloud engineer would stop scrolling for. "
    "Return ONLY valid JSON: {\"score\": <int>, \"domain_tags\": [<strings from: "
    "AI_MODEL, AWS, DEV_TOOL, OPEN_SOURCE>], \"reason\": \"<one sentence max>\"}."
)

HISTORIAN_SYSTEM_PROMPT = (
    "You are a technical historian with perfect memory of past AI and tech developments. "
    "You will receive a new item and up to 3 historically similar items from a database. "
    "Your job: (1) Determine if any historical item is a genuine predecessor to the new item — "
    "same product line, direct competitor, or technology it replaces. "
    "(2) If yes, write one paragraph starting with 'Compared to [predecessor name]...' that states the specific delta: "
    "versions, benchmarks, pricing, context windows, or whatever metrics are relevant. "
    "(3) If no genuine predecessor exists, write exactly: 'This appears to be a new category entry with no direct predecessor in our records.' "
    "Return only the comparison paragraph, nothing else."
)

ANALYST_SYSTEM_PROMPT = (
    "You are a senior technical analyst writing for an experienced developer. "
    "Be direct and opinionated. Only state benchmarks or metrics derivable from "
    "the input data — do not invent numbers. For each item write exactly 5 sections "
    "using these exact Markdown headers:\n\n"
    "### What It Is\n2-3 sentence plain English explanation.\n\n"
    "### The Delta\nThis section must exist immediately after 'What It Is'. Look at the 'Historical Delta Input' "
    "provided in the prompt. If it says 'new category entry', write exactly: "
    "**First appearance in ARIA's radar — no predecessor on record.** "
    "Otherwise, insert the Historical Delta Input paragraph exactly as it was provided.\n\n"
    "### Why It Matters\nOne paragraph on practical significance.\n\n"
    "### Where To Use It\n3-5 concrete, specific use cases as a numbered list.\n\n"
    "### Impact Score\nOne of: Low / Medium / High / Game-Changer, "
    "followed by a one sentence justification."
)

# ── Keyword Relevance Filter ─────────────────────────
# An item is relevant if its title or snippet contains ANY of these (case-insensitive)
RELEVANCE_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "ml",
    "llm", "large language model", "gpt", "gemini", "claude",
    "mistral", "llama", "open source", "open-source",
    "framework", "agent", "agentic",
    "aws", "amazon web services", "sagemaker", "bedrock",
    "cloud", "serverless", "kubernetes", "docker",
    "deep learning", "neural network", "transformer",
    "benchmark", "state-of-the-art", "sota",
    "diffusion", "generative", "rag", "retrieval",
    "vector database", "embedding",
    "devtool", "developer tool", "sdk", "api",
]

# ── HackerNews Config ────────────────────────────────
HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_FETCH_LIMIT = 100  # how many top story IDs to fetch
HN_MIN_SCORE = 50     # skip stories below this score

# ── GitHub Trending Config ────────────────────────────
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# ── ArXiv Config ──────────────────────────────────────
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]
ARXIV_MAX_RESULTS = 100

# ── AWS Blog RSS Config ──────────────────────────────
AWS_FEEDS = [
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://aws.amazon.com/blogs/machine-learning/feed/",
]

# ── Tavily Config ─────────────────────────────────────
TAVILY_QUERIES = [
    "new AI model release site:techcrunch.com OR site:huggingface.co OR site:arxiv.org",
    "new AI framework launched site:github.com OR site:techcrunch.com",
    "AI tool open source today site:github.com OR site:huggingface.co",
    "AWS announcement today site:aws.amazon.com",
    "AI research breakthrough today site:arxiv.org OR site:techcrunch.com",
]

# ── Snippet length ────────────────────────────────────
MAX_SNIPPET_WORDS = 150


# ── Helpers ───────────────────────────────────────────
def is_relevant(text: str) -> bool:
    """Return True if text contains at least one relevance keyword."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in RELEVANCE_KEYWORDS)


def truncate_snippet(text: str, max_words: int = MAX_SNIPPET_WORDS) -> str:
    """Truncate text to max_words and add ellipsis if needed."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"
