"""
ARIA — Tavily Web Search Fetcher
──────────────────────────────────
Runs multiple tech-focused search queries via Tavily API
to catch breaking AI/cloud/dev-tools news not yet on HN or ArXiv.
"""

import asyncio
from tavily import TavilyClient
from config import TAVILY_API_KEY, TAVILY_QUERIES, is_relevant, truncate_snippet


async def fetch_tavily() -> list[dict]:
    """
    Run predefined Tavily search queries and return structured items.
    Returns a list of standardized item dicts.
    """
    if not TAVILY_API_KEY or TAVILY_API_KEY == "your_tavily_api_key_here":
        print("  ⚠  Tavily: No API key configured — skipping")
        print("     → Get a free key at https://tavily.com")
        return []

    items = []
    seen_urls = set()  # dedup within Tavily results

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
    except Exception as e:
        print(f"  ⚠  Tavily: client init error — {e}")
        return []

    # Run all queries (Tavily client is sync, so we run in executor)
    loop = asyncio.get_event_loop()

    for query in TAVILY_QUERIES:
        try:
            # Run sync call in thread pool to not block the event loop
            response = await loop.run_in_executor(
                None,
                lambda q=query: client.search(
                    query=q,
                    max_results=10,
                    search_depth="basic",
                    include_answer=False,
                ),
            )

            results = response.get("results", [])

            for result in results:
                url = result.get("url", "").strip()
                title = result.get("title", "").strip()
                content = result.get("content", "").strip()

                # Skip duplicates within Tavily
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Relevance filter
                combined = f"{title} {content}"
                if not is_relevant(combined):
                    continue

                snippet = truncate_snippet(content) if content else title

                items.append(
                    {
                        "source": "tavily",
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "search_query": query,
                    }
                )

        except Exception as e:
            print(f"  ⚠  Tavily: error on query '{query}' — {e}")
            continue

    return items


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    async def _test():
        print("=" * 60)
        print("  ARIA — Tavily Search Fetcher Test")
        print("=" * 60)
        results = await fetch_tavily()
        print(f"\n  Found {len(results)} relevant items\n")
        for i, item in enumerate(results[:10], 1):
            print(f"  [{i}] {item['title'][:80]}")
            print(f"      🔗 {item['url']}")
            print(f"      🔍 Query: {item['search_query']}")
            print(f"      📝 {item['snippet'][:120]}…")
            print()

    asyncio.run(_test())
