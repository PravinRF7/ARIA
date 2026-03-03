"""
ARIA — Collector Agent
───────────────────────
Takes raw items from the data pipeline, sends each to Llama 3.3 70B (via Groq)
for relevance scoring (1-10), domain tagging, and filtering.
Only items scoring 7+ pass through to the Analyst.
"""

import asyncio
import json
import sys
import os
from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GROQ_API_KEY,
    COLLECTOR_MODEL,
    COLLECTOR_SYSTEM_PROMPT,
    COLLECTOR_BATCH_SIZE,
    COLLECTOR_BATCH_DELAY,
    COLLECTOR_MIN_SCORE,
    COLLECTOR_MAX_ITEMS,
)


# ── Groq setup ───────────────────────────────────────
def _init_model():
    """Configure and return the Collector's Groq client."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError(
            "GROQ_API_KEY not set. Get one at https://console.groq.com/keys "
            "and add it to aria/.env"
        )
    client = Groq(api_key=GROQ_API_KEY)
    return client


# ── Exponential backoff wrapper ──────────────────────
async def _call_with_backoff(
    client, prompt: str, max_retries: int = 4
) -> str | None:
    """Call Groq with exponential backoff. Returns response text or None."""
    for attempt in range(max_retries):
        try:
            print(f"      [DEBUG] Preparing to call Groq (Attempt {attempt+1}/{max_retries})")
            # Run the sync chat.completions.create in a thread pool
            loop = asyncio.get_event_loop()
            
            def make_call():
                print("      [DEBUG] Inside thread executor, initiating HTTP request...")
                return client.chat.completions.create(
                    model=COLLECTOR_MODEL,
                    messages=[
                        {"role": "system", "content": COLLECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
            
            print("      [DEBUG] Yielding to run_in_executor...")
            response = await asyncio.wait_for(loop.run_in_executor(None, make_call), timeout=30.0)
            print("      [DEBUG] Groq request completed successfully!")
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            print(f"      [DEBUG] ❌ Groq request timed out after 30 seconds!")
            wait = (2 ** attempt) + 0.5
            await asyncio.sleep(wait)
        except Exception as e:
            wait = (2 ** attempt) + 0.5  # 1.5s, 2.5s, 4.5s, 8.5s
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                print(f"      ⏳ Rate limited (attempt {attempt + 1}/{max_retries}), "
                      f"retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            elif attempt < max_retries - 1:
                print(f"      ⚠ Groq error (attempt {attempt + 1}): {err_str[:80]}, "
                      f"retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            else:
                print(f"      ❌ Groq failed after {max_retries} attempts: {err_str[:80]}")
                return None
    return None


def _parse_score_response(text: str) -> dict | None:
    """Parse the JSON response from the Collector LLM. Returns dict or None."""
    if not text:
        return None

    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        # Sometimes smaller models might output extra characters before/after the JSON
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]

        data = json.loads(cleaned)
        # Validate expected fields
        score = int(data.get("score", 0))
        domain_tags = data.get("domain_tags", [])
        reason = data.get("reason", "")

        if not isinstance(domain_tags, list):
            domain_tags = []

        # Validate domain tags
        valid_tags = {"AI_MODEL", "AWS", "DEV_TOOL", "OPEN_SOURCE"}
        domain_tags = [t for t in domain_tags if t in valid_tags]

        return {
            "score": score,
            "domain_tags": domain_tags,
            "reason": reason,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return None


def _build_item_prompt(item: dict) -> str:
    """Build the prompt for scoring a single item."""
    parts = [
        f"Source: {item.get('source', 'unknown')}",
        f"Title: {item.get('title', 'No title')}",
        f"URL: {item.get('url', '')}",
    ]

    # Add source-specific metadata
    if item.get("score"):
        parts.append(f"HN Score: {item['score']}")
    if item.get("comments"):
        parts.append(f"Comments: {item['comments']}")
    if item.get("stars_today"):
        parts.append(f"GitHub Stars Today: {item['stars_today']}")
    if item.get("total_stars"):
        parts.append(f"GitHub Total Stars: {item['total_stars']}")
    if item.get("language"):
        parts.append(f"Language: {item['language']}")
    if item.get("authors"):
        parts.append(f"Authors: {item['authors']}")
    if item.get("tags"):
        parts.append(f"Tags: {', '.join(item['tags'])}")

    parts.append(f"Snippet: {item.get('snippet', '')}")

    return "\n".join(parts)


# ── Public API ───────────────────────────────────────
async def run_collector(items: list[dict]) -> list[dict]:
    """
    Score all items using Groq, filter to 7+, and return
    the top COLLECTOR_MAX_ITEMS items sorted by score descending.
    """
    print(f"\n  🔬 Collector Agent starting — {len(items)} items to score")
    print(f"     Model: {COLLECTOR_MODEL} (via Groq)")
    print(f"     Batch size: {COLLECTOR_BATCH_SIZE}, delay: {COLLECTOR_BATCH_DELAY}s")
    print(f"     Threshold: score ≥ {COLLECTOR_MIN_SCORE}\n")

    client = _init_model()
    scored_items = []
    failed = 0

    # Process in batches
    for batch_start in range(0, len(items), COLLECTOR_BATCH_SIZE):
        batch_end = min(batch_start + COLLECTOR_BATCH_SIZE, len(items))
        batch = items[batch_start:batch_end]
        batch_num = (batch_start // COLLECTOR_BATCH_SIZE) + 1
        total_batches = (len(items) + COLLECTOR_BATCH_SIZE - 1) // COLLECTOR_BATCH_SIZE

        print(f"     📦 Batch {batch_num}/{total_batches} "
              f"(items {batch_start + 1}–{batch_end})")

        for item in batch:
            prompt = _build_item_prompt(item)
            raw_response = await _call_with_backoff(client, prompt)
            parsed = _parse_score_response(raw_response)

            if parsed is None:
                failed += 1
                continue

            # Merge score data into the item
            item["relevance_score"] = parsed["score"]
            item["domain_tags"] = parsed["domain_tags"]
            item["score_reason"] = parsed["reason"]

            if parsed["score"] >= COLLECTOR_MIN_SCORE:
                scored_items.append(item)

        # Delay between batches (not after the last one)
        if batch_end < len(items):
            print(f"     ⏳ Waiting {COLLECTOR_BATCH_DELAY}s before next batch...")
            await asyncio.sleep(COLLECTOR_BATCH_DELAY)

    # Sort by score descending, cap at max
    scored_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    scored_items = scored_items[:COLLECTOR_MAX_ITEMS]

    print(f"\n  ✅ Collector complete:")
    print(f"     • Scored: {len(items) - failed}/{len(items)} items")
    print(f"     • Failed: {failed}")
    print(f"     • Passed (≥{COLLECTOR_MIN_SCORE}): {len(scored_items)} items")

    # Quick breakdown by domain
    tag_counts = {}
    for item in scored_items:
        for tag in item.get("domain_tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    if tag_counts:
        print(f"     • Domain breakdown: {tag_counts}")

    print()
    return scored_items


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    # Test with 5 sample items
    sample_items = [
        {
            "source": "hackernews",
            "title": "OpenAI raises $110B on $730B pre-money valuation",
            "url": "https://techcrunch.com/2026/02/27/openai-raises-110b/",
            "snippet": "OpenAI has raised $110 billion in one of the largest private funding rounds in history, valuing the company at $730 billion pre-money.",
            "score": 469,
            "comments": 515,
        },
        {
            "source": "github",
            "title": "obra/superpowers",
            "url": "https://github.com/obra/superpowers",
            "snippet": "An agentic skills framework & software development methodology that works.",
            "stars_today": 1546,
            "total_stars": 65245,
            "language": "Shell",
        },
        {
            "source": "arxiv",
            "title": "FlashOptim: Optimizers for Memory Efficient Training",
            "url": "https://arxiv.org/pdf/2602.23349v1",
            "snippet": "Standard mixed-precision training of neural networks requires many bytes of accelerator memory for each model parameter.",
            "authors": "Jose Javier Gonzalez Ortiz, Abhay Gupta",
        },
        {
            "source": "aws_blog",
            "title": "Reinforcement fine-tuning for Amazon Nova: Teaching AI through feedback",
            "url": "https://aws.amazon.com/blogs/machine-learning/reinforcement-fine-tuning-for-amazon-nova/",
            "snippet": "In this post, we explore reinforcement fine-tuning (RFT) for Amazon Nova models.",
            "tags": ["Amazon Bedrock", "Amazon Nova", "Artificial Intelligence"],
        },
        {
            "source": "hackernews",
            "title": "A better streams API is possible for JavaScript",
            "url": "https://blog.cloudflare.com/a-better-web-streams-api/",
            "snippet": "Cloudflare proposes a better Web Streams API for JavaScript.",
            "score": 401,
            "comments": 138,
        },
    ]

    async def _test():
        print("=" * 60)
        print("  ARIA — Collector Agent Test (5 sample items)")
        print("=" * 60)
        results = await run_collector(sample_items)
        print("  ── Items that passed ──")
        for i, item in enumerate(results, 1):
            print(f"  [{i}] Score: {item['relevance_score']}/10  "
                  f"Tags: {item['domain_tags']}")
            print(f"      {item['title']}")
            print(f"      Reason: {item['score_reason']}")
            print()

    asyncio.run(_test())
