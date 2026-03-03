"""
ARIA — Output Router
─────────────────────
Orchestrates all output channels after the report is saved.
Currently wired to: MS Teams Webhook

Both channels run in parallel using asyncio.gather().
If one fails, the other still sends.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from output.teams_notifier import send_teams


async def dispatch(analyzed_items: list[dict], report_path: str, notify: bool = True) -> None:
    """
    Dispatch to all output channels in parallel.

    Args:
        analyzed_items: The full analyzed item list (with 'analysis' fields).
        report_path:    Absolute path to the saved markdown report.
        notify:         If False (TEST_MODE), skip all notifications.
    """
    if not notify:
        print("  ℹ️  Notifications suppressed (TEST_MODE or NOTIFY_MODE=False)")
        return

    print("\n  📣 Output Router — dispatching notifications...")

    results = await asyncio.gather(
        send_teams(analyzed_items, report_path),
        return_exceptions=True,   # never crash the pipeline
    )

    teams_result = results[0]
    if isinstance(teams_result, Exception):
        print(f"  ❌ Teams raised an exception: {teams_result}")
