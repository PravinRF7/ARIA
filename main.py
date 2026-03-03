"""
ARIA — Main Pipeline (Phase 1)
───────────────────────────────
Runs all 5 data fetchers in parallel using asyncio,
deduplicates results by URL, and prints a structured report to the terminal.
"""

import asyncio
import sys
import os
from datetime import datetime

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetchers.hackernews import fetch_hackernews
from fetchers.github_trending import fetch_github_trending
from fetchers.arxiv import fetch_arxiv
from fetchers.aws_blog import fetch_aws_blog
from fetchers.tavily_search import fetch_tavily


# ── ANSI colors for terminal output ──────────────────
class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


SOURCE_COLORS = {
    "hackernews": C.YELLOW,
    "github": C.GREEN,
    "arxiv": C.CYAN,
    "aws_blog": C.BLUE,
    "tavily": C.RED,
}

SOURCE_ICONS = {
    "hackernews": "🔶",
    "github": "🐙",
    "arxiv": "📄",
    "aws_blog": "☁️ ",
    "tavily": "🔍",
}


def deduplicate(all_items: list[dict]) -> list[dict]:
    """
    Deduplicate items by URL.
    If the same URL appears from multiple sources, keep the first one
    and note all sources in a 'sources' list.
    """
    seen = {}  # url -> item

    for item in all_items:
        url = item.get("url", "")
        if not url:
            continue

        if url in seen:
            # Merge source info
            existing = seen[url]
            existing_sources = existing.get("sources", [existing["source"]])
            if item["source"] not in existing_sources:
                existing_sources.append(item["source"])
            existing["sources"] = existing_sources
        else:
            item["sources"] = [item["source"]]
            seen[url] = item

    return list(seen.values())


def print_report(items: list[dict], source_counts: dict):
    """Pretty-print all items to the terminal."""

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print(f"{C.BOLD}{'═' * 70}{C.END}")
    print(f"{C.BOLD}{C.HEADER}  ╔═══════════════════════════════════════════════╗{C.END}")
    print(f"{C.BOLD}{C.HEADER}  ║     🛰️  ARIA — AI Research & Intelligence     ║{C.END}")
    print(f"{C.BOLD}{C.HEADER}  ║           Aggregator  ·  Phase 1              ║{C.END}")
    print(f"{C.BOLD}{C.HEADER}  ╚═══════════════════════════════════════════════╝{C.END}")
    print(f"{C.BOLD}{'═' * 70}{C.END}")
    print(f"  {C.DIM}Generated: {now}{C.END}")
    print()

    # ── Source summary ──
    print(f"  {C.BOLD}📊 Source Breakdown:{C.END}")
    total = 0
    for source, count in source_counts.items():
        icon = SOURCE_ICONS.get(source, "•")
        color = SOURCE_COLORS.get(source, "")
        print(f"     {icon} {color}{source:15s}{C.END} → {count} items")
        total += count
    print(f"     {'─' * 40}")
    print(f"     📦 Total raw:       {total}")
    print(f"     🧹 After dedup:     {len(items)}")
    print()
    print(f"  {C.BOLD}{'─' * 66}{C.END}")

    # ── Items grouped by source ──
    # Group items by primary source
    by_source = {}
    for item in items:
        src = item["source"]
        by_source.setdefault(src, []).append(item)

    source_order = ["hackernews", "github", "arxiv", "aws_blog", "tavily"]

    for source in source_order:
        src_items = by_source.get(source, [])
        if not src_items:
            continue

        icon = SOURCE_ICONS.get(source, "•")
        color = SOURCE_COLORS.get(source, "")
        print()
        print(f"  {C.BOLD}{color}  {icon}  {source.upper()} ({len(src_items)} items){C.END}")
        print(f"  {color}  {'─' * 50}{C.END}")

        for i, item in enumerate(src_items[:15], 1):  # cap at 15 per source
            title = item.get("title", "No title")
            url = item.get("url", "")
            snippet = item.get("snippet", "")

            # Multi-source badge
            sources = item.get("sources", [])
            multi_badge = ""
            if len(sources) > 1:
                multi_badge = f" {C.RED}[also: {', '.join(s for s in sources if s != source)}]{C.END}"

            print(f"    {C.BOLD}{i:2d}. {title[:80]}{C.END}{multi_badge}")
            print(f"        {C.DIM}🔗 {url}{C.END}")

            # Source-specific metadata
            if source == "hackernews":
                score = item.get("score", 0)
                comments = item.get("comments", 0)
                print(f"        ⬆ {score}  💬 {comments}")
            elif source == "github":
                stars = item.get("stars_today", 0)
                lang = item.get("language", "")
                print(f"        ⭐ +{stars} today  🔤 {lang}")
            elif source == "arxiv":
                authors = item.get("authors", "")
                print(f"        ✍️  {authors}")
            elif source == "aws_blog":
                tags = item.get("tags", [])
                if tags:
                    print(f"        🏷️  {', '.join(tags[:4])}")

            # Snippet (truncated for display)
            if snippet and snippet != title:
                display_snippet = snippet[:150] + "…" if len(snippet) > 150 else snippet
                print(f"        {C.DIM}{display_snippet}{C.END}")
            print()

    print(f"  {C.BOLD}{'═' * 66}{C.END}")
    print(f"  {C.DIM}🛰️  ARIA Phase 1 — Data pipeline complete{C.END}")
    print(f"  {C.BOLD}{'═' * 66}{C.END}")
    print()


from agents.collector import run_collector
from agents.historian import run_historian
from agents.analyst import run_analyst
from output.html_dashboard import generate_html_dashboard
from output.router import dispatch
from config import NOTIFY_MODE


async def run_pipeline():
    """Run all fetchers in parallel, collect, contextualize, analyze, and save report."""

    print(f"\n  {C.BOLD}🚀 Starting ARIA data pipeline...{C.END}\n")

    # 1. Fetch data
    print(f"  {C.DIM}  Fetching from 5 sources in parallel...{C.END}")
    hn_task = asyncio.create_task(fetch_hackernews())
    gh_task = asyncio.create_task(fetch_github_trending())
    ax_task = asyncio.create_task(fetch_arxiv())
    aws_task = asyncio.create_task(fetch_aws_blog())
    tav_task = asyncio.create_task(fetch_tavily())

    hn_items = await hn_task
    gh_items = await gh_task
    ax_items = await ax_task
    aws_items = await aws_task
    tav_items = await tav_task

    # Combine and deduplicate
    all_items = hn_items + gh_items + ax_items + aws_items + tav_items
    deduped = deduplicate(all_items)

    print(f"    ✅ Total items fetched & deduplicated: {len(deduped)}")

    # ── Test Mode to preserve limits ──
    TEST_MODE = False   # Set True to limit to 3 items when testing
    MAX_ITEMS = 3 if TEST_MODE else 200
    if TEST_MODE:
        deduped = deduped[:MAX_ITEMS]
        print(f"    ⚠️  TEST MODE ENABLED — Truncated fetch list to {MAX_ITEMS} items to save API quota.")

    if not deduped:
        print(f"  {C.YELLOW}⚠ No items found from any source.{C.END}")
        return

    # 2. Run Collector Agent
    scored_items = await run_collector(deduped)

    if not scored_items:
        print(f"  {C.YELLOW}⚠ No items passed the Collector's relevance filter.{C.END}")
        return

    # 3. Run Historian Agent
    contextualized_items = await run_historian(scored_items)

    # 4. Run Analyst Agent
    _ = await run_analyst(contextualized_items)

    # 5. Save HTML Dashboard
    saved_path = generate_html_dashboard(contextualized_items)

    # 6. Dispatch Notifications
    should_notify = NOTIFY_MODE and not TEST_MODE
    await dispatch(contextualized_items, saved_path, notify=should_notify)

    # Final summary
    print(f"\n  {C.BOLD}{'═' * 66}{C.END}")
    print(f"  {C.BOLD}{C.GREEN}🎉 ARIA Pipeline Complete!{C.END}")
    print(f"  {C.BOLD}{'═' * 66}{C.END}")
    print(f"  🔹 Fetched Items:   {len(deduped)}")
    print(f"  🔹 Relevant Items:  {len(scored_items)} (Passed 7+ Score)")
    print(f"  🔹 Report Saved:    {saved_path}")
    print(f"  🔹 Notifications:   {'✅ Sent' if should_notify else '⏭️  Suppressed (TEST_MODE or NOTIFY_MODE=False)'}")
    print(f"  {C.BOLD}{'═' * 66}{C.END}\n")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
