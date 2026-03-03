"""
ARIA — Collector Agent
───────────────────────
Takes raw items from the data pipeline, sends them in batches to Llama 3.3 70B (via Groq)
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
                    response_format={"type": "json_object"}, # ensure valid JSON wrapper
                    max_tokens=2000,
                )
            
            response = await asyncio.wait_for(loop.run_in_executor(None, make_call), timeout=45.0)
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            print(f"      ⏳ Groq Timeout (attempt {attempt + 1}), retrying...")
            wait = (2 ** attempt) + 0.5
            await asyncio.sleep(wait)
        except Exception as e:
            wait = (2 ** attempt) + 0.5  # 1.5s, 2.5s, 4.5s, 8.5s
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                print(f"      ⏳ Rate limited (attempt {attempt + 1}/{max_retries}), retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            elif attempt < max_retries - 1:
                print(f"      ⚠ Groq error (attempt {attempt + 1}): {err_str[:80]}, retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            else:
                print(f"      ❌ Groq failed after {max_retries} attempts: {err_str[:80]}")
                return None
    return None


def _parse_batch_response(text: str) -> list | None:
    """Parse the JSON array response from the Collector LLM."""
    if not text:
        return None

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
        # Handle if the model returned a dict with an array inside (due to json_object format)
        if isinstance(data, dict):
            # Find the first list in the dict values
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
            else:
                # Fallback: maybe it's { "results": [...] }
                data = data.get("results", data.get("items", []))

        if not isinstance(data, list):
            return None

        valid_tags = {"AI_MODEL", "AWS", "DEV_TOOL", "OPEN_SOURCE"}
        parsed_results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            
            idx = item.get("index")
            score = int(item.get("score", 0))
            tags = item.get("domain_tags", [])
            if not isinstance(tags, list):
                tags = []
            tags = [t for t in tags if t in valid_tags]
            reason = item.get("reason", "")
            
            parsed_results.append({
                "index": idx,
                "score": score,
                "domain_tags": tags,
                "reason": reason
            })
        return parsed_results
    except Exception as e:
        print(f"      ⚠ JSON parsing error: {e}")
        return None


def _build_batch_prompt(batch: list[dict]) -> str:
    """Build the JSON string prompt for scoring a batch of items."""
    extracted = []
    for i, item in enumerate(batch):
        obj = {
            "index": i,
            "source": item.get('source', 'unknown'),
            "title": item.get('title', 'No title'),
            "snippet": item.get('snippet', '')
        }
        if item.get("score"): obj["hn_score"] = item["score"]
        if item.get("comments"): obj["hn_comments"] = item["comments"]
        if item.get("stars_today"): obj["stars_today"] = item["stars_today"]
        if item.get("language"): obj["language"] = item["language"]
        extracted.append(obj)
    
    # We pass it as a clean JSON request.
    return json.dumps({"items": extracted}, indent=2)


# ── Public API ───────────────────────────────────────
async def run_collector(items: list[dict]) -> list[dict]:
    """
    Score all items using Groq in batches of COLLECTOR_BATCH_SIZE to save API requests,
    filter to 7+, and return the top COLLECTOR_MAX_ITEMS items sorted by score descending.
    """
    print(f"\n  🔬 Collector Agent starting — {len(items)} items to score")
    print(f"     Model: {COLLECTOR_MODEL} (via Groq)")
    print(f"     Batch size: {COLLECTOR_BATCH_SIZE}, limit: 30 RPM (Free Tier)")
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

        prompt = _build_batch_prompt(batch)
        raw_response = await _call_with_backoff(client, prompt)
        parsed_list = _parse_batch_response(raw_response)

        if not parsed_list:
            print("      ⚠ Batch failed to return valid JSON scoring array.")
            failed += len(batch)
            continue

        # Map scores back to original items
        for res in parsed_list:
            idx = res.get("index")
            if idx is not None and 0 <= idx < len(batch):
                item = batch[idx]
                item["relevance_score"] = res["score"]
                item["domain_tags"] = res["domain_tags"]
                item["score_reason"] = res["reason"]

                if res["score"] >= COLLECTOR_MIN_SCORE:
                    scored_items.append(item)

        # Delay between batches (not after the last one)
        if batch_end < len(items):
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
            "snippet": "OpenAI has raised $110 billion in one of the largest private funding rounds in history.",
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
            "snippet": "Standard mixed-precision training of neural networks requires many bytes of accelerator memory.",
            "authors": "Jose Javier Gonzalez Ortiz, Abhay Gupta",
        },
        {
            "source": "aws_blog",
            "title": "Reinforcement fine-tuning for Amazon Nova",
            "url": "https://aws.amazon.com/blogs/machine-learning/",
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
