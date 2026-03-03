"""
ARIA — GitHub Trending Fetcher
───────────────────────────────
Scrapes the GitHub Trending page for daily trending repositories,
filters by relevance to AI/cloud/dev-tools, and returns structured items.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from config import GITHUB_TRENDING_URL, is_relevant, truncate_snippet


async def fetch_github_trending() -> list[dict]:
    """
    Scrape GitHub's trending page for daily repos.
    Returns a list of standardized item dicts.
    """
    items = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GITHUB_TRENDING_URL,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "ARIA-Bot/1.0"},
            ) as resp:
                if resp.status != 200:
                    print(f"  ⚠  GitHub Trending: HTTP {resp.status}")
                    return []
                html = await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"  ⚠  GitHub Trending: connection error — {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Each trending repo is in an <article> with class "Box-row"
    repo_rows = soup.select("article.Box-row")
    if not repo_rows:
        # Fallback: GitHub occasionally changes the class
        repo_rows = soup.select("[class*='Box-row']")

    for row in repo_rows:
        try:
            # ── Repo name & URL ──
            h2 = row.select_one("h2 a") or row.select_one("h1 a")
            if not h2:
                continue
            repo_path = h2.get("href", "").strip()
            if not repo_path:
                continue
            full_url = f"https://github.com{repo_path}"
            repo_name = repo_path.lstrip("/")

            # ── Description ──
            desc_tag = row.select_one("p")
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            # ── Language ──
            lang_tag = row.select_one("[itemprop='programmingLanguage']")
            language = lang_tag.get_text(strip=True) if lang_tag else "Unknown"

            # ── Stars today ──
            stars_today_text = ""
            star_spans = row.select("span.d-inline-block.float-sm-right")
            if star_spans:
                stars_today_text = star_spans[-1].get_text(strip=True)
            # Fallback: look for the text "stars today"
            if not stars_today_text:
                for span in row.find_all("span"):
                    text = span.get_text(strip=True)
                    if "stars today" in text or "stars this week" in text:
                        stars_today_text = text
                        break

            # Parse star count
            stars_today = 0
            if stars_today_text:
                num_part = stars_today_text.replace(",", "").split()[0]
                try:
                    stars_today = int(num_part)
                except ValueError:
                    stars_today = 0

            # ── Total stars ──
            total_stars = 0
            star_links = row.select("a.Link--muted")
            for link in star_links:
                href = link.get("href", "")
                if "/stargazers" in href:
                    star_text = link.get_text(strip=True).replace(",", "")
                    try:
                        total_stars = int(star_text)
                    except ValueError:
                        pass
                    break

            # ── Relevance filter ──
            combined = f"{repo_name} {description} {language}"
            if not is_relevant(combined):
                continue

            snippet = truncate_snippet(description) if description else repo_name

            items.append(
                {
                    "source": "github",
                    "title": repo_name,
                    "url": full_url,
                    "snippet": snippet,
                    "language": language,
                    "stars_today": stars_today,
                    "total_stars": total_stars,
                }
            )

        except Exception:
            # Skip malformed rows silently
            continue

    # Sort by stars gained today
    items.sort(key=lambda x: x["stars_today"], reverse=True)
    return items


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    async def _test():
        print("=" * 60)
        print("  ARIA — GitHub Trending Fetcher Test")
        print("=" * 60)
        results = await fetch_github_trending()
        print(f"\n  Found {len(results)} relevant repos\n")
        for i, item in enumerate(results[:10], 1):
            print(f"  [{i}] {item['title']}")
            print(f"      🔗 {item['url']}")
            print(f"      ⭐ Today: {item['stars_today']}  |  Total: {item['total_stars']}  |  🔤 {item['language']}")
            print(f"      📝 {item['snippet'][:100]}")
            print()

    asyncio.run(_test())
