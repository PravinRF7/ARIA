"""
ARIA — Email Sender (SendGrid)
───────────────────────────────
Sends the daily ARIA intelligence report as an HTML email via SendGrid.

Format:
  - Header: ARIA Daily Intelligence Report + date
  - Summary table: ALL items (number, title, domain tags, impact score)
  - Full detail sections: HIGH and GAME-CHANGER items only
  - Footer: full report path

Subject line: "ARIA Radar — [date] — [X] items, [Y] high-impact"
"""

import os
import sys
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SENDGRID_API_KEY,
    ARIA_EMAIL_TO,
    ARIA_EMAIL_FROM,
)


# ── HTML Helpers ─────────────────────────────────────
IMPACT_COLORS = {
    "game-changer": "#7B2FBE",
    "high": "#C0392B",
    "medium": "#D68910",
    "low": "#555555",
}

IMPACT_EMOJIS = {
    "game-changer": "⚡",
    "high": "🔴",
    "medium": "🟡",
    "low": "⚪",
}


def _parse_impact(analysis_text: str) -> str:
    """Extract impact level from the analysis text (e.g. '### Impact Score\\nHigh')."""
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


def _build_html(analyzed_items: list[dict], report_path: str) -> str:
    """Assemble the full HTML email body."""
    date_str = datetime.now().strftime("%B %d, %Y")

    high_impact = [
        item for item in analyzed_items
        if _parse_impact(item.get("analysis", "")) in ("high", "game-changer")
    ]

    # ── Styles ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background:#0d1117; color:#c9d1d9; margin:0; padding:20px; }}
  .container {{ max-width:700px; margin:auto; }}
  h1 {{ color:#58a6ff; font-size:22px; margin-bottom:4px; }}
  .subtitle {{ color:#8b949e; font-size:13px; margin-bottom:24px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:28px; font-size:13px; }}
  th {{ background:#161b22; color:#8b949e; text-align:left; padding:8px 10px; border-bottom:1px solid #30363d; }}
  td {{ padding:8px 10px; border-bottom:1px solid #21262d; vertical-align:top; }}
  .item-section {{ background:#161b22; border:1px solid #30363d; border-radius:8px;
                   padding:18px 20px; margin-bottom:16px; }}
  .item-title {{ color:#58a6ff; font-size:15px; font-weight:600; margin-bottom:6px; }}
  .item-meta {{ color:#8b949e; font-size:12px; margin-bottom:10px; }}
  .analysis {{ color:#c9d1d9; font-size:13px; line-height:1.6; white-space:pre-wrap; }}
  .section-header {{ color:#e6edf3; font-size:17px; font-weight:700;
                     margin:28px 0 12px; border-bottom:1px solid #30363d; padding-bottom:8px; }}
  .footer {{ color:#484f58; font-size:12px; margin-top:28px; border-top:1px solid #21262d; padding-top:10px; }}
  a {{ color:#58a6ff; text-decoration:none; }}
</style>
</head>
<body>
<div class="container">
  <h1>🛰️ ARIA Daily Intelligence Report</h1>
  <div class="subtitle">{date_str} &nbsp;·&nbsp; {len(analyzed_items)} items filtered &nbsp;·&nbsp; {len(high_impact)} high-impact</div>

  <div class="section-header">📋 Summary</div>
  <table>
    <tr>
      <th>#</th><th>Item</th><th>Domain</th><th>Impact</th>
    </tr>
"""
    for i, item in enumerate(analyzed_items, 1):
        title = item.get("title", "Unknown")[:70]
        url = item.get("url", "#")
        tags = ", ".join(item.get("domain_tags", []))
        impact = _parse_impact(item.get("analysis", ""))
        color = IMPACT_COLORS.get(impact, "#555")
        emoji = IMPACT_EMOJIS.get(impact, "⚪")
        html += f"""    <tr>
      <td>{i}</td>
      <td><a href="{url}">{title}</a></td>
      <td style="color:#8b949e">{tags}</td>
      <td style="color:{color}; font-weight:600">{emoji} {impact.title()}</td>
    </tr>\n"""

    html += "  </table>\n"

    # ── Full Detail: High + Game-Changer items only ──
    if high_impact:
        html += '  <div class="section-header">🔍 High-Impact Deep Dives</div>\n'
        for item in high_impact:
            title = item.get("title", "Unknown")
            url = item.get("url", "#")
            tags = ", ".join(item.get("domain_tags", []))
            analysis = item.get("analysis", "_Analysis not available._")
            impact = _parse_impact(analysis)
            color = IMPACT_COLORS.get(impact, "#555")
            emoji = IMPACT_EMOJIS.get(impact, "")

            html += f"""  <div class="item-section">
    <div class="item-title"><a href="{url}">{title}</a></div>
    <div class="item-meta">{tags} &nbsp;·&nbsp; <span style="color:{color}">{emoji} {impact.title()}</span></div>
    <div class="analysis">{analysis}</div>
  </div>\n"""

    report_name = os.path.basename(report_path) if report_path else "N/A"
    html += f"""
  <div class="footer">
    📁 Full report saved to: <code>{report_name}</code><br>
    Generated by ARIA v1.0 — AI Research &amp; Intelligence Aggregator
  </div>
</div>
</body>
</html>"""
    return html


# ── Public API ───────────────────────────────────────
async def send_email(analyzed_items: list[dict], report_path: str = "") -> bool:
    """
    Build and send the HTML digest email via SendGrid.
    Returns True on success, False on failure.
    """
    if not SENDGRID_API_KEY or SENDGRID_API_KEY == "your_sendgrid_key_here":
        print("  ⚠️  Email: SENDGRID_API_KEY not configured — skipping")
        return False
    if not ARIA_EMAIL_TO or ARIA_EMAIL_TO == "your_email@example.com":
        print("  ⚠️  Email: ARIA_EMAIL_TO not configured — skipping")
        return False

    date_str = datetime.now().strftime("%Y-%m-%d")
    high_count = sum(
        1 for item in analyzed_items
        if _parse_impact(item.get("analysis", "")) in ("high", "game-changer")
    )

    subject = f"ARIA Radar — {date_str} — {len(analyzed_items)} items, {high_count} high-impact"
    html_body = _build_html(analyzed_items, report_path)

    message = Mail(
        from_email=ARIA_EMAIL_FROM,
        to_emails=ARIA_EMAIL_TO,
        subject=subject,
        html_content=html_body,
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        status = response.status_code
        if 200 <= status < 300:
            print(f"  ✅ Email: Sent to {ARIA_EMAIL_TO} (HTTP {status})")
            return True
        else:
            print(f"  ❌ Email: SendGrid returned HTTP {status}")
            return False
    except Exception as e:
        print(f"  ❌ Email failed: {e}")
        return False


# ── Standalone test ──────────────────────────────────
if __name__ == "__main__":
    import asyncio

    # Quick smoke test with hardcoded data — fill in your keys in .env first
    sample_items = [
        {
            "title": "OpenAI raises $110B on $730B pre-money valuation",
            "url": "https://techcrunch.com/2026/02/27/openai-raises-110b/",
            "domain_tags": ["AI_MODEL"],
            "analysis": "### What It Is\nOpenAI raised $110 billion.\n\n### The Delta\nFirst appearance in ARIA's radar — no predecessor on record.\n\n### Why It Matters\nRecord-breaking round signals market confidence.\n\n### Where To Use It\n1. Evaluate AI infrastructure budgets.\n\n### Impact Score\nGame-Changer — Largest private AI funding round in history.",
        },
        {
            "title": "Meta releases Llama 4 Scout and Maverick models",
            "url": "https://ai.meta.com/llama/",
            "domain_tags": ["AI_MODEL", "OPEN_SOURCE"],
            "analysis": "### What It Is\nMeta's next-gen open LLMs.\n\n### The Delta\nCompared to Llama 3.3, Scout runs faster on edge devices.\n\n### Why It Matters\nOpen-source frontier model competition heats up.\n\n### Where To Use It\n1. Self-hosted inference.\n\n### Impact Score\nHigh — Frontier open model with real benchmark improvements.",
        },
        {
            "title": "Minor AWS EC2 pricing update",
            "url": "https://aws.amazon.com/ec2/pricing/",
            "domain_tags": ["AWS"],
            "analysis": "### What It Is\nSmall price adjustment.\n\n### The Delta\nFirst appearance in ARIA's radar — no predecessor on record.\n\n### Why It Matters\nMinor operational impact.\n\n### Where To Use It\n1. Re-evaluate reserved instances.\n\n### Impact Score\nLow — Routine pricing tweak.",
        },
    ]

    print("Sending test email...")
    result = asyncio.run(send_email(sample_items, "/aria/reports/aria_report_2026-02-28.md"))
    print("Result:", "SUCCESS" if result else "FAILED (check your .env keys)")
