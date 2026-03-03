"""
ARIA — HTML Dashboard Generator
────────────────────────────────
Generates a self-contained, responsive, beautiful HTML dashboard 
for the full 20-item daily report, saving it to the /reports/ directory.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IMPACT_COLORS = {
    "game-changer": "background: rgba(123, 47, 190, 0.2); color: #c47cff; border: 1px solid rgba(123, 47, 190, 0.5);",
    "high": "background: rgba(192, 57, 43, 0.2); color: #ff7b72; border: 1px solid rgba(192, 57, 43, 0.5);",
    "medium": "background: rgba(214, 137, 16, 0.2); color: #e3b341; border: 1px solid rgba(214, 137, 16, 0.5);",
    "low": "background: rgba(56, 56, 56, 0.5); color: #8b949e; border: 1px solid rgba(80, 80, 80, 0.5);",
}

IMPACT_EMOJIS = {
    "game-changer": "⚡",
    "high": "🔴",
    "medium": "🟡",
    "low": "⚪",
}

def _parse_impact(analysis_text: str) -> str:
    if not analysis_text: return "low"
    lower = analysis_text.lower()
    if "game-changer" in lower or "game changer" in lower: return "game-changer"
    if "high" in lower: return "high"
    if "medium" in lower: return "medium"
    return "low"

def generate_html_dashboard(analyzed_items: list[dict], reports_dir: str = None) -> str:
    """Generate and save the HTML dashboard to disk."""
    if not reports_dir:
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reports"
        )
    
    os.makedirs(reports_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(reports_dir, f"aria_dashboard_{date_str}.html")

    # Sort items by impact (high to low)
    rank_val = {"game-changer": 4, "high": 3, "medium": 2, "low": 1}
    sorted_items = sorted(
        analyzed_items, 
        key=lambda x: rank_val.get(_parse_impact(x.get("analysis", "")), 0),
        reverse=True
    )

    high_count = sum(1 for i in sorted_items if _parse_impact(i.get("analysis", "")) in ("high", "game-changer"))

    # HTML Template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ARIA Radar | {date_str}</title>
    <style>
        :root {{
            --bg-main: #0d1117;
            --bg-card: #161b22;
            --border: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        h1 {{ font-size: 28px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }}
        .meta-stats {{ color: var(--text-secondary); font-size: 14px; }}
        
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 24px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .card:hover {{
            border-color: #8b949e;
            transform: translateY(-2px);
        }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            gap: 16px;
        }}
        
        .card-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--accent);
            text-decoration: none;
            line-height: 1.3;
        }}
        .card-title:hover {{ text-decoration: underline; }}
        
        .badges {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 12px;
        }}
        
        .badge {{
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .tag-badge {{
            background: rgba(139, 148, 158, 0.1);
            border: 1px solid rgba(139, 148, 158, 0.2);
            color: var(--text-secondary);
        }}
        
        .analysis-content {{
            font-size: 14px;
            color: #c9d1d9;
        }}
        
        .analysis-content h3 {{
            color: var(--text-primary);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 16px 0 6px 0;
            color: var(--text-secondary);
        }}
        
        .analysis-content p, .analysis-content ul {{
            margin-bottom: 12px;
        }}
        
        .analysis-content ul {{
            padding-left: 20px;
        }}
        
        .source-meta {{
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            gap: 16px;
        }}
        
        .footer {{
            margin-top: 60px;
            text-align: center;
            font-size: 13px;
            color: var(--text-secondary);
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🛰️ ARIA Intelligence Radar</h1>
            <div class="meta-stats">
                {date_str} &nbsp;•&nbsp; {len(sorted_items)} Items Analyzed &nbsp;•&nbsp; {high_count} High-Impact Signals
            </div>
        </header>

        <main>
"""

    for item in sorted_items:
        title = item.get("title", "Unknown")
        url = item.get("url", "#")
        source = item.get("source", "unknown").upper()
        tags = item.get("domain_tags", [])
        
        raw_analysis = item.get("analysis", "_No analysis generated._")
        impact = _parse_impact(raw_analysis)
        
        # Format the markdown analysis into simple HTML
        formatted_analysis = raw_analysis.replace("### What It Is", "<h3>What It Is</h3><p>")
        formatted_analysis = formatted_analysis.replace("### The Delta", "</p><h3>The Delta</h3><p>")
        formatted_analysis = formatted_analysis.replace("### Why It Matters", "</p><h3>Why It Matters</h3><p>")
        formatted_analysis = formatted_analysis.replace("### Where To Use It", "</p><h3>Where To Use It</h3><p>")
        formatted_analysis = formatted_analysis.replace("### Impact Score", "</p><h3>Impact Score</h3><p>")
        # Close the final paragraph cleanly (crudely but effective for this format)
        formatted_analysis += "</p>"
        
        # Fix list rendering (newlines followed by numbers)
        import re
        formatted_analysis = re.sub(r'(\n|^)(\d+\.\s)', r'<br>\2', formatted_analysis)

        html += f"""
            <article class="card">
                <div class="card-header">
                    <div>
                        <a href="{url}" target="_blank" class="card-title">{title}</a>
                        <div class="badges">
                            <span class="badge" style="{IMPACT_COLORS.get(impact, '')}">
                                {IMPACT_EMOJIS.get(impact, '')} {impact.replace('-', ' ')}
                            </span>
                            {''.join(f'<span class="badge tag-badge">{tag}</span>' for tag in tags)}
                        </div>
                    </div>
                </div>
                
                <div class="analysis-content">
                    {formatted_analysis}
                </div>
                
                <div class="source-meta">
                    <span>📡 Source: {source}</span>
                    <span>🔗 <a href="{url}" target="_blank" style="color: var(--text-secondary);">{url.split('/')[2] if '//' in url else 'Link'}</a></span>
                </div>
            </article>
"""

    html += """
        </main>
        
        <footer class="footer">
            Generated autonomously by the ARIA Multi-Agent Pipeline.
        </footer>
    </div>
</body>
</html>
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
        
    return filepath
