"""
ARIA — ArXiv Fetcher
─────────────────────
Queries the ArXiv API for recent papers in AI-related categories
(cs.AI, cs.LG, cs.CL), filters by relevance keywords in the abstract,
and returns structured items.
"""

import asyncio
import aiohttp
import xmltodict
from datetime import datetime, timedelta, timezone
from config import (
    ARXIV_API_URL,
    ARXIV_CATEGORIES,
    ARXIV_MAX_RESULTS,
    is_relevant,
    truncate_snippet,
)


async def fetch_arxiv() -> list[dict]:
    """
    Query ArXiv for the latest AI papers submitted in the last 24 hours.
    Returns a list of standardized item dicts.
    """
    items = []

    # Build the query: search across all target categories
    # ArXiv API needs the query in the URL directly (aiohttp re-encodes + signs)
    cat_parts = " OR ".join(f"cat:{cat}" for cat in ARXIV_CATEGORIES)
    query_string = f"({cat_parts})"
    full_url = (
        f"{ARXIV_API_URL}?search_query={query_string}"
        f"&start=0&max_results={ARXIV_MAX_RESULTS}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                full_url,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    print(f"  ⚠  ArXiv: HTTP {resp.status}")
                    return []
                xml_data = await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"  ⚠  ArXiv: connection error — {e}")
        return []

    # Parse XML response
    try:
        parsed = xmltodict.parse(xml_data)
    except Exception as e:
        print(f"  ⚠  ArXiv: XML parse error — {e}")
        return []

    feed = parsed.get("feed", {})
    entries = feed.get("entry", [])

    # Handle single entry (xmltodict returns a dict instead of list)
    if isinstance(entries, dict):
        entries = [entries]

    # 24 hours ago cutoff
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)  # 72h to catch ArXiv batch delays

    for entry in entries:
        try:
            title = entry.get("title", "").replace("\n", " ").strip()
            abstract = entry.get("summary", "").replace("\n", " ").strip()

            # Published date
            published_str = entry.get("published", "")
            if published_str:
                published = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
                if published < cutoff:
                    continue  # older than our window

            # Authors
            authors_raw = entry.get("author", [])
            if isinstance(authors_raw, dict):
                authors_raw = [authors_raw]
            authors = [a.get("name", "") for a in authors_raw if isinstance(a, dict)]
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += f" (+{len(authors) - 3} more)"

            # PDF link
            links = entry.get("link", [])
            if isinstance(links, dict):
                links = [links]
            pdf_url = ""
            abstract_url = ""
            for link in links:
                if isinstance(link, dict):
                    if link.get("@title") == "pdf":
                        pdf_url = link.get("@href", "")
                    elif link.get("@type") == "text/html":
                        abstract_url = link.get("@href", "")
                    elif not abstract_url and link.get("@rel") == "alternate":
                        abstract_url = link.get("@href", "")

            url = pdf_url or abstract_url

            # Relevance filter on title + abstract
            combined = f"{title} {abstract}"
            if not is_relevant(combined):
                continue

            snippet = truncate_snippet(abstract)

            items.append(
                {
                    "source": "arxiv",
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "authors": authors_str,
                    "published": published_str,
                }
            )

        except Exception:
            continue

    return items


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    async def _test():
        print("=" * 60)
        print("  ARIA — ArXiv Fetcher Test")
        print("=" * 60)
        results = await fetch_arxiv()
        print(f"\n  Found {len(results)} relevant papers\n")
        for i, item in enumerate(results[:10], 1):
            print(f"  [{i}] {item['title'][:80]}")
            print(f"      🔗 {item['url']}")
            print(f"      ✍️  {item['authors']}")
            print(f"      📝 {item['snippet'][:120]}…")
            print()

    asyncio.run(_test())
