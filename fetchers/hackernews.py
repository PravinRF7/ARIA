"""
ARIA — HackerNews Fetcher
──────────────────────────
Fetches top stories from the HackerNews Firebase API,
filters by relevance keywords, and returns structured items.
"""

import asyncio
import aiohttp
from config import (
    HN_TOP_STORIES_URL,
    HN_ITEM_URL,
    HN_FETCH_LIMIT,
    HN_MIN_SCORE,
    is_relevant,
    truncate_snippet,
)


async def _fetch_story(session: aiohttp.ClientSession, story_id: int) -> dict | None:
    """Fetch a single story by ID. Returns None on failure."""
    url = HN_ITEM_URL.format(story_id)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data or data.get("type") != "story":
                return None
            return data
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None


async def fetch_hackernews() -> list[dict]:
    """
    Fetch top HackerNews stories, filter by score and keyword relevance.
    Returns a list of standardized item dicts.
    """
    items = []

    async with aiohttp.ClientSession() as session:
        # 1. Get top story IDs
        try:
            async with session.get(
                HN_TOP_STORIES_URL, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    print("  ⚠  HackerNews: failed to fetch top stories list")
                    return []
                story_ids = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"  ⚠  HackerNews: connection error — {e}")
            return []

        # 2. Fetch individual stories (limit to top N)
        story_ids = story_ids[: HN_FETCH_LIMIT]
        tasks = [_fetch_story(session, sid) for sid in story_ids]
        results = await asyncio.gather(*tasks)

    # 3. Filter and structure
    for story in results:
        if story is None:
            continue

        title = story.get("title", "")
        url = story.get("url", f"https://news.ycombinator.com/item?id={story['id']}")
        score = story.get("score", 0)
        text = story.get("text", "")  # self-post body, if any

        # Skip low-score stories
        if score < HN_MIN_SCORE:
            continue

        # Relevance check on title + text
        combined_text = f"{title} {text}"
        if not is_relevant(combined_text):
            continue

        snippet = truncate_snippet(text) if text else title

        items.append(
            {
                "source": "hackernews",
                "title": title,
                "url": url,
                "snippet": snippet,
                "score": score,
                "comments": story.get("descendants", 0),
            }
        )

    # Sort by score descending
    items.sort(key=lambda x: x["score"], reverse=True)
    return items


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    async def _test():
        print("=" * 60)
        print("  ARIA — HackerNews Fetcher Test")
        print("=" * 60)
        results = await fetch_hackernews()
        print(f"\n  Found {len(results)} relevant stories\n")
        for i, item in enumerate(results[:10], 1):
            print(f"  [{i}] {item['title']}")
            print(f"      🔗 {item['url']}")
            print(f"      ⬆  Score: {item['score']}  |  💬 Comments: {item['comments']}")
            print()

    asyncio.run(_test())
