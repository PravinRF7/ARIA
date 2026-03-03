"""
ARIA Phase 3 — Backfill Script
───────────────────────────────
Parses existing markdown reports in aria/reports/ and loads them into ChromaDB
so the Historian Agent doesn't start with an empty brain.
"""

import os
import re
import datetime
import chromadb

def _parse_report(filepath: str) -> list[dict]:
    """Parse a single markdown report into a list of item dictionaries."""
    items = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Extract the date from the header
    date_match = re.search(r"\*\*Date:\*\* (\d{4}-\d{2}-\d{2})", content)
    report_date = date_match.group(1) if date_match else "unknown"
    
    # ISO string for ChromaDB
    try:
        iso_date = datetime.datetime.strptime(report_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
    except ValueError:
        iso_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
    # Split the document by item headers (## 1. Title, ## 2. Title, etc.)
    # The regex looks for ## followed by optional digits and a period, then the title
    blocks = re.split(r"## \d+\. ", content)
        
    for block in blocks[1:]:  # Skip the summary section before the first item
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
            
        title = lines[0]
        
        # We need URL to generate a stable ID
        url_match = re.search(r"🔗 \[(.*?)\]", block)
        url = url_match.group(1) if url_match else None
        item_id = str(hash(url or title))
        
        # Parse tags and relevance score
        # Format: 🏷️ **AI_MODEL, DEV_TOOL** — Relevance: **8/10**  
        tags_match = re.search(r"🏷️ \*\*(.*?)\*\*", block)
        domain_tags_str = tags_match.group(1) if tags_match else ""
        
        score_match = re.search(r"Relevance: \*\*(\d+)/10\*\*", block)
        impact_score = score_match.group(1) if score_match else "0"
        
        # Parse source
        # Format: 📡 HACKERNEWS  |  ...
        source_match = re.search(r"📡 ([A-Z_]+)\s*\|", block)
        source = source_match.group(1).lower() if source_match else "unknown"
        
        # We don't have the snippet in the report directly, we'll store the title as the document
        document = title

        items.append({
            "id": item_id,
            "document": document,
            "metadata": {
                "date": iso_date,
                "domain_tags": domain_tags_str,
                "title": title,
                "impact_score": impact_score,
                "source": source
            }
        })
        
    return items

def run_backfill():
    # Correctly resolve paths from root
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Accommodate potential nesting "aria/reports" or "aria/aria/reports"
    dir_options = [
        os.path.join(root_dir, "aria", "reports"),
        os.path.join(root_dir, "reports")
    ]
    
    reports_dir = None
    md_files = []
    
    for d in dir_options:
        if os.path.exists(d):
            files = [f for f in os.listdir(d) if f.endswith(".md")]
            if files:
                reports_dir = d
                md_files = files
                break
                
    if not reports_dir:
        print(f"Could not find any .md reports in {dir_options}. Nothing to backfill.")
        return
        
    memory_dir = os.path.join(root_dir, "memory", "chroma_db")
    os.makedirs(memory_dir, exist_ok=True)
    
    print(f"Initializing ChromaDB persistent client at: {memory_dir}")
    client = chromadb.PersistentClient(path=memory_dir)
    collection = client.get_or_create_collection(name="aria_items")
    
    print(f"Current DB size: {collection.count()}")
    
    md_files = [f for f in os.listdir(reports_dir) if f.endswith(".md")]
    print(f"Found {len(md_files)} reports to parse.\n")
    
    total_added = 0
    for file in md_files:
        filepath = os.path.join(reports_dir, file)
        items = _parse_report(filepath)
        
        if not items:
            print(f"  • {file}: 0 items parsed.")
            continue
            
        ids = [i["id"] for i in items]
        documents = [i["document"] for i in items]
        metadatas = [i["metadata"] for i in items]
        
        try:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            total_added += len(items)
            print(f"  • {file}: Backfilled {len(items)} items ✅")
        except Exception as e:
            print(f"  • {file}: Failed to backfill items — {e} ❌")
            
    print(f"\nBackfill complete. New DB size: {collection.count()}")

if __name__ == "__main__":
    run_backfill()
