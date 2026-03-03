"""
ARIA — MS Teams Notifier
─────────────────────────
Posts the top-impact items to an MS Teams channel via Incoming Webhook.
Uses only `requests` — no extra library needed.

Rules:
  - Top 3 items by impact score (high, game-changer first)
  - Low impact items are never posted
  - If zero high-impact items → single fallback message
  - Fires ONLY after the report is successfully saved
"""

import os
import sys
import asyncio
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SLACK_WEBHOOK_URL as TEAMS_WEBHOOK_URL   # reuse key, rename below

# The actual env var we read is TEAMS_WEBHOOK_URL
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "") or os.getenv("SLACK_WEBHOOK_URL", "")

IMPACT_RANK = {"game-changer": 4, "high": 3, "medium": 2, "low": 1}
IMPACT_EMOJI = {"game-changer": "⚡", "high": "🔴", "medium": "🟡", "low": "⚪"}


def _parse_impact(analysis_text: str) -> str:
    """Extract impact level from the Analyst's output text."""
    if not analysis_text:
        return "low"
    text_lower = analysis_text.lower()
    if "game-changer" in text_lower or "game changer" in text_lower:
        return "game-changer"
    if "high" in text_lower:
        return "high"
    if "medium" in text_lower:
        return "medium"
    return "low"


def _one_sentence(analysis_text: str) -> str:
    """Extract the first meaningful sentence from the analysis (Why It Matters section)."""
    if not analysis_text:
        return "No summary available."
    marker = "### Why It Matters"
    idx = analysis_text.find(marker)
    if idx != -1:
        after = analysis_text[idx + len(marker):].strip()
        # Take first sentence
        for end in (".", "\n"):
            pos = after.find(end)
            if pos > 10:
                return after[:pos + 1].strip()
    # Fallback: first 120 chars
    return analysis_text.strip()[:120] + "…"


def _build_payload(items: list[dict], date_str: str, report_path: str) -> dict:
    """Build the MessageCard payload for MS Teams O365 Connector webhook."""

    # Sort by impact rank descending, exclude Low
    ranked = sorted(
        [i for i in items if _parse_impact(i.get("analysis", "")) != "low"],
        key=lambda x: IMPACT_RANK.get(_parse_impact(x.get("analysis", "")), 0),
        reverse=True,
    )
    top3 = ranked[:3]
    report_name = os.path.basename(report_path) if report_path else "N/A"

    if not top3:
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary": f"ARIA Radar — {date_str}",
            "text": f"🛰️ **ARIA Radar — {date_str}** — No high-impact items today.",
        }

    sections = []
    for item in top3:
        title = item.get("title", "Unknown")
        url = item.get("url", "#")
        analysis = item.get("analysis", "")
        impact = _parse_impact(analysis)
        emoji = IMPACT_EMOJI.get(impact, "")
        summary = _one_sentence(analysis)
        color_map = {"game-changer": "7B2FBE", "high": "C0392B", "medium": "D68910", "low": "555555"}

        sections.append({
            "activityTitle": f"**{title}**",
            "activitySubtitle": f"{emoji} {impact.title()}",
            "activityText": summary,
            "facts": [{"name": "Source", "value": f"[{url}]({url})"}],
            "themeColor": color_map.get(impact, "0076D7"),
        })

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "0076D7",
        "summary": f"ARIA Radar — {date_str} — {len(top3)} high-impact items",
        "title": f"🛰️ ARIA Daily Radar — {date_str}",
        "text": f"{len(items)} items analyzed · {len(top3)} high-impact · Report: `{report_name}`",
        "sections": sections,
    }


async def send_teams(analyzed_items: list[dict], report_path: str = "") -> bool:
    """
    Post the ARIA digest to MS Teams via Incoming Webhook.
    Returns True on success, False on failure.
    """
    if not TEAMS_WEBHOOK_URL or "your_" in TEAMS_WEBHOOK_URL:
        print("  ⚠️  Teams: TEAMS_WEBHOOK_URL not configured — skipping")
        return False

    date_str = datetime.now().strftime("%Y-%m-%d")
    payload = _build_payload(analyzed_items, date_str, report_path)

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                TEAMS_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
        )
        if response.status_code == 200:
            print(f"  ✅ Teams: Notification posted successfully")
            return True
        else:
            print(f"  ❌ Teams: Webhook returned HTTP {response.status_code} — {response.text[:100]}")
            return False
    except Exception as e:
        print(f"  ❌ Teams notification failed: {e}")
        return False


# ── Standalone test ───────────────────────────────────
if __name__ == "__main__":
    sample_items = [
        {
            "title": "OpenAI raises $110B on $730B valuation",
            "url": "https://techcrunch.com/2026/02/27/openai-raises-110b/",
            "domain_tags": ["AI_MODEL"],
            "analysis": "### What It Is\nRecord funding.\n\n### The Delta\nFirst appearance.\n\n### Why It Matters\nThis signals massive market confidence in frontier AI models.\n\n### Where To Use It\n1. Benchmark AI infra budgets.\n\n### Impact Score\nGame-Changer — Largest AI private round in history.",
        },
        {
            "title": "Meta releases Llama 4 Scout and Maverick",
            "url": "https://ai.meta.com/llama/",
            "domain_tags": ["AI_MODEL", "OPEN_SOURCE"],
            "analysis": "### What It Is\nMeta's next-gen open LLMs.\n\n### The Delta\nFaster edge inference than Llama 3.3.\n\n### Why It Matters\nOpen-source frontier competition intensifies significantly.\n\n### Where To Use It\n1. Self-hosted inference.\n\n### Impact Score\nHigh — Real benchmark improvements in open models.",
        },
        {
            "title": "Minor EC2 pricing tweak",
            "url": "https://aws.amazon.com",
            "domain_tags": ["AWS"],
            "analysis": "### Impact Score\nLow — Routine adjustment.",
        },
    ]
    print("Sending Teams test notification...")
    asyncio.run(send_teams(sample_items, "/aria/reports/aria_report_2026-02-28.md"))
