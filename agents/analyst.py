"""
ARIA — Analyst Agent
─────────────────────
Takes scored items from the Collector and generates a comprehensive
markdown report using Gemini 2.5 Pro. For each item, produces:
  - What It Is
  - Why It Matters
  - Where To Use It
  - Impact Score
"""

import asyncio
import sys
import os
from datetime import datetime
from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GROQ_API_KEY,
    ANALYST_MODEL,
    ANALYST_SYSTEM_PROMPT,
)


# ── Groq setup ───────────────────────────────────────
def _init_model():
    """Configure and return the Analyst's Groq client."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError(
            "GROQ_API_KEY not set. Get one at https://console.groq.com/keys "
            "and add it to aria/.env"
        )
    return Groq(api_key=GROQ_API_KEY)


# ── Exponential backoff wrapper ──────────────────────
async def _call_with_backoff(
    client, prompt: str, max_retries: int = 4
) -> str | None:
    """Call Groq with exponential backoff. Returns response text or None."""
    for attempt in range(max_retries):
        try:
            print(f"      [LLM] Generating Analysis... (Attempt {attempt + 1}/{max_retries})")
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=ANALYST_MODEL,
                    messages=[
                        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                ),
            )
            print(f"      [LLM] Analysis generated successfully.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e)
            if attempt == max_retries - 1:
                print(f"      ❌ Groq failed after {max_retries} attempts: {err_str[:80]}")
                return None
                
            wait = (2 ** attempt) + 0.5
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                print(f"      ⏳ Rate limited (attempt {attempt + 1}/{max_retries}), "
                      f"retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            else:
                print(f"      ⚠ Groq error (attempt {attempt + 1}): {err_str[:80]}, "
                      f"retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
    return None


def _build_analysis_prompt(item: dict) -> str:
    """Build the prompt for analyzing a single item."""
    parts = [
        f"Analyze this item and write the 4 sections:",
        f"",
        f"Source: {item.get('source', 'unknown')}",
        f"Title: {item.get('title', 'No title')}",
        f"URL: {item.get('url', '')}",
        f"Relevance Score: {item.get('relevance_score', 'N/A')}/10",
        f"Domain Tags: {', '.join(item.get('domain_tags', []))}",
        f"Scorer Reasoning: {item.get('score_reason', 'N/A')}",
    ]

    # Source-specific metadata
    if item.get("score"):
        parts.append(f"HackerNews Score: {item['score']}")
    if item.get("comments"):
        parts.append(f"Comments: {item['comments']}")
    if item.get("stars_today"):
        parts.append(f"GitHub Stars Today: +{item['stars_today']}")
    if item.get("total_stars"):
        parts.append(f"GitHub Total Stars: {item['total_stars']}")
    if item.get("language"):
        parts.append(f"Language: {item['language']}")
    if item.get("authors"):
        parts.append(f"Authors: {item['authors']}")
    if item.get("tags"):
        parts.append(f"Tags: {', '.join(item['tags'])}")

    parts.append(f"")
    parts.append(f"Description/Snippet: {item.get('snippet', '')}")
    
    # Phase 3: Historian Output
    if item.get("historical_context"):
        parts.append(f"Historical Delta Input: {item['historical_context']}\n")

    return "\n".join(parts)


def _build_markdown_report(analyzed_items: list[dict]) -> str:
    """Assemble the final markdown report."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    lines = [
        f"# 🛰️ ARIA Daily Intelligence Report",
        f"",
        f"**Date:** {date_str}  ",
        f"**Generated:** {time_str}  ",
        f"**Items Analyzed:** {len(analyzed_items)}",
        f"",
        f"---",
        f"",
    ]

    # Table of contents
    lines.append("## 📋 Summary\n")
    lines.append("| # | Item | Domain | Impact |")
    lines.append("|---|------|--------|--------|")
    for i, item in enumerate(analyzed_items, 1):
        title = item.get("title", "Unknown")[:60]
        tags = ", ".join(item.get("domain_tags", []))
        score = item.get("relevance_score", "?")
        lines.append(f"| {i} | {title} | {tags} | {score}/10 |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Full analysis for each item
    for i, item in enumerate(analyzed_items, 1):
        title = item.get("title", "Unknown")
        url = item.get("url", "")
        source = item.get("source", "unknown")
        tags = ", ".join(item.get("domain_tags", []))
        score = item.get("relevance_score", "?")
        analysis = item.get("analysis", "_Analysis not available._")

        # Source-specific metadata line
        meta_parts = [f"📡 {source.upper()}"]
        if item.get("score"):
            meta_parts.append(f"⬆ HN:{item['score']}")
        if item.get("stars_today"):
            meta_parts.append(f"⭐ +{item['stars_today']} today")
        if item.get("language"):
            meta_parts.append(f"🔤 {item['language']}")
        meta_line = "  |  ".join(meta_parts)

        lines.extend([
            f"## {i}. {title}",
            f"",
            f"🔗 [{url}]({url})  ",
            f"🏷️ **{tags}** — Relevance: **{score}/10**  ",
            f"{meta_line}",
            f"",
            analysis,
            f"",
            f"---",
            f"",
        ])

    lines.append(f"*Report generated by ARIA v1.0 — AI Research & Intelligence Aggregator*")
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────
async def run_analyst(items: list[dict]) -> str:
    """
    Analyze each scored item and return a complete markdown report string.
    Also mutates each item dict to add an 'analysis' field.
    """
    print(f"\n  📝 Analyst Agent starting — {len(items)} items to analyze")
    print(f"     Model: {ANALYST_MODEL}\n")

    model = _init_model()
    analyzed = []
    failed = 0

    for i, item in enumerate(items, 1):
        title = item.get("title", "Unknown")[:60]
        print(f"     [{i}/{len(items)}] Analyzing: {title}...")

        prompt = _build_analysis_prompt(item)
        response = await _call_with_backoff(model, prompt)

        if response:
            item["analysis"] = response.strip()
            analyzed.append(item)
        else:
            item["analysis"] = "_Analysis could not be generated._"
            analyzed.append(item)
            failed += 1

        # Small delay between items to be gentle on rate limits
        if i < len(items):
            await asyncio.sleep(1.0)

    print(f"\n  ✅ Analyst complete:")
    print(f"     • Analyzed: {len(analyzed) - failed}/{len(analyzed)} items")
    if failed:
        print(f"     • Failed: {failed}")

    # Build the full report
    report = _build_markdown_report(analyzed)
    return report


def save_report(report: str, reports_dir: str = None) -> str:
    """Save the markdown report to disk. Returns the file path."""
    if reports_dir is None:
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "aria", "reports"
        )
        # Fallback: if running from within aria/
        if not os.path.basename(os.path.dirname(reports_dir)) == "aria":
            reports_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "reports"
            )

    os.makedirs(reports_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"aria_report_{date_str}.md"
    filepath = os.path.join(reports_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    return os.path.abspath(filepath)


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    # Test with 3 pre-scored items
    sample_items = [
        {
            "source": "hackernews",
            "title": "OpenAI raises $110B on $730B pre-money valuation",
            "url": "https://techcrunch.com/2026/02/27/openai-raises-110b/",
            "snippet": "OpenAI has raised $110 billion in one of the largest private funding rounds in history.",
            "score": 469,
            "comments": 515,
            "relevance_score": 9,
            "domain_tags": ["AI_MODEL"],
            "score_reason": "Record-breaking funding round signals massive market confidence in AI.",
        },
        {
            "source": "github",
            "title": "obra/superpowers",
            "url": "https://github.com/obra/superpowers",
            "snippet": "An agentic skills framework & software development methodology that works.",
            "stars_today": 1546,
            "total_stars": 65245,
            "language": "Shell",
            "relevance_score": 8,
            "domain_tags": ["DEV_TOOL", "OPEN_SOURCE"],
            "score_reason": "Rapidly trending agentic framework with massive community adoption.",
        },
        {
            "source": "aws_blog",
            "title": "Reinforcement fine-tuning for Amazon Nova",
            "url": "https://aws.amazon.com/blogs/machine-learning/reinforcement-fine-tuning-for-amazon-nova/",
            "snippet": "Reinforcement fine-tuning (RFT) for Amazon Nova models.",
            "tags": ["Amazon Bedrock", "Amazon Nova", "AI"],
            "relevance_score": 7,
            "domain_tags": ["AWS", "AI_MODEL"],
            "score_reason": "New fine-tuning approach for AWS-native models.",
        },
    ]

    async def _test():
        print("=" * 60)
        print("  ARIA — Analyst Agent Test (3 sample items)")
        print("=" * 60)
        report = await run_analyst(sample_items)
        print("\n" + "=" * 60)
        print("  Generated Report Preview (first 2000 chars):")
        print("=" * 60)
        print(report[:2000])

    asyncio.run(_test())
