"""
ARIA — AWS Blog RSS Fetcher
────────────────────────────
Parses AWS blog RSS feeds for recent posts (last 24-48 hours),
filters by relevance keywords, and returns structured items.
"""

import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
from config import AWS_FEEDS, is_relevant, truncate_snippet


async def _fetch_feed(session: aiohttp.ClientSession, feed_url: str) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns raw entries."""
    try:
        async with session.get(
            feed_url,
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "ARIA-Bot/1.0"},
        ) as resp:
            if resp.status != 200:
                print(f"  ⚠  AWS RSS: HTTP {resp.status} for {feed_url}")
                return []
            body = await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"  ⚠  AWS RSS: error fetching {feed_url} — {e}")
        return []

    # feedparser works on strings
    feed = feedparser.parse(body)
    return feed.get("entries", [])


async def fetch_aws_blog() -> list[dict]:
    """
    Fetch recent AWS blog posts from multiple RSS feeds.
    Returns a list of standardized item dicts.
    """
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_feed(session, url) for url in AWS_FEEDS]
        results = await asyncio.gather(*tasks)

    # Flatten all entries from all feeds
    all_entries = []
    for entries in results:
        all_entries.extend(entries)

    for entry in all_entries:
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "").strip()

            # Parse published date
            published_str = entry.get("published", "") or entry.get("updated", "")
            if published_str:
                try:
                    published = dateparser.parse(published_str)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                    if published < cutoff:
                        continue  # too old
                except (ValueError, TypeError):
                    pass  # keep it if we can't parse the date

            # Remove HTML tags from summary (basic cleanup)
            import re
            clean_summary = re.sub(r"<[^>]+>", " ", summary)
            clean_summary = re.sub(r"\s+", " ", clean_summary).strip()

            # Relevance filter
            combined = f"{title} {clean_summary}"
            if not is_relevant(combined):
                continue

            # Tags from feed categories
            tags = [tag.get("term", "") for tag in entry.get("tags", [])]

            snippet = truncate_snippet(clean_summary) if clean_summary else title

            items.append(
                {
                    "source": "aws_blog",
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "tags": tags,
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
        print("  ARIA — AWS Blog RSS Fetcher Test")
        print("=" * 60)
        results = await fetch_aws_blog()
        print(f"\n  Found {len(results)} relevant posts\n")
        for i, item in enumerate(results[:10], 1):
            print(f"  [{i}] {item['title']}")
            print(f"      🔗 {item['url']}")
            if item.get("tags"):
                print(f"      🏷️  {', '.join(item['tags'][:5])}")
            print(f"      📝 {item['snippet'][:120]}…")
            print()

    asyncio.run(_test())
