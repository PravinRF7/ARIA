"""
ARIA — Historian Agent
───────────────────────
Runs between the Collector and the Analyst.
Queries ChromaDB for similar historical items, uses Llama 3.3 70B via Groq
to generate a specific 'Old vs New' delta paragraph, then stores the new item.
Outputs the field: `historical_context`
"""

import asyncio
import os
import sys
import datetime
from groq import Groq
import chromadb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GROQ_API_KEY,
    HISTORIAN_MODEL,
    HISTORIAN_SYSTEM_PROMPT,
)

# ── Setup ChromaDB ───────────────────────────────────
def _get_db_collection():
    """Initializes and returns the ChromaDB aria_items collection."""
    memory_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "chroma_db")
    os.makedirs(memory_dir, exist_ok=True)
    
    # Initialize persistent client
    client = chromadb.PersistentClient(path=memory_dir)
    collection = client.get_or_create_collection(name="aria_items")
    return collection


# ── Setup Groq ───────────────────────────────────────
def _init_model():
    """Configure and return the Historian's Groq client."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not set for Historian Agent.")
    return Groq(api_key=GROQ_API_KEY)


# ── Core Logic ───────────────────────────────────────
async def _call_vllm_backoff(client, prompt: str, max_retries: int = 3) -> str:
    """Call Groq specifically for the Historian comparison."""
    for attempt in range(max_retries):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=HISTORIAN_MODEL,
                    messages=[
                        {"role": "system", "content": HISTORIAN_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=300,
                ),
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            wait = (2 ** attempt) + 1.0
            print(f"      ⏳ Historian Groq retry in {wait}s due to error: {e}")
            await asyncio.sleep(wait)
            
    return "This appears to be a new category entry with no direct predecessor in our records."


def _format_query_context(current_item: dict, similar_docs: list, similar_meta: list) -> str:
    """Format the retrieved records for the Historian LLM."""
    prompt = "--- CURRENT NEW ITEM ---\n"
    prompt += f"Title: {current_item.get('title', '')}\n"
    prompt += f"Snippet: {current_item.get('snippet', '')}\n\n"
    
    prompt += "--- POTENTIAL HISTORICAL PREDECESSORS ---\n"
    if not similar_docs or len(similar_docs) == 0:
        prompt += "(No historical records found in memory)\n"
    else:
        for i, (doc, meta) in enumerate(zip(similar_docs, similar_meta), 1):
            prompt += f"[{i}] Date: {meta.get('date', 'Unknown')} - "
            prompt += f"Source: {meta.get('source', 'Unknown')}\n"
            prompt += f"Content: {doc}\n\n"
            
    return prompt


async def run_historian(items: list[dict]) -> list[dict]:
    """
    For each item:
    1. Query ChromaDB for 3 similar past items.
    2. Generate historical delta using Groq.
    3. Save the new item to ChromaDB.
    """
    print(f"\n  📚 Historian Agent starting — processing {len(items)} items")
    
    collection = _get_db_collection()
    print(f"     Connected to ChromaDB (Current DB size: {collection.count()})")
    
    client = _init_model()
    
    # Today's date for storage metadata
    today_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    processed_items = []
    failed = 0
    
    for idx, item in enumerate(items, 1):
        print(f"     [{idx}/{len(items)}] Contextualizing: {item.get('title', '')[:50]}...")
        
        # 1. QUERY
        query_text = f"{item.get('title', '')} - {item.get('snippet', '')}"
        
        # Guard against completely empty items
        if not query_text.strip() or query_text.strip() == "-":
            item["historical_context"] = "This appears to be a new category entry with no direct predecessor in our records."
            processed_items.append(item)
            continue
            
        similar_docs = []
        similar_meta = []
        try:
            if collection.count() > 0:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=min(3, collection.count())
                )
                similar_docs = results["documents"][0] if results and "documents" in results and results["documents"] else []
                similar_meta = results["metadatas"][0] if results and "metadatas" in results and results["metadatas"] else []
        except Exception as e:
            print(f"      ⚠ ChromaDB query error: {e}")
            
        # 2. GENERATE
        prompt = _format_query_context(item, similar_docs, similar_meta)
        delta_text = await _call_vllm_backoff(client, prompt)
        item["historical_context"] = delta_text
        
        # 3. STORE
        # Generate a unique ID for ChromaDB using the URL or a hash of the title if no URL
        item_id = item.get("url") or str(hash(item.get("title", str(idx))))
        
        # Comma-separated domain string
        domain_tags_str = ",".join(item.get("domain_tags", []))
        
        try:
            collection.upsert(
                ids=[item_id],
                documents=[query_text],
                metadatas=[{
                    "date": today_iso,
                    "domain_tags": domain_tags_str,
                    "title": item.get("title", "Unknown"),
                    "impact_score": str(item.get("relevance_score", 0)),
                    "source": item.get("source", "Unknown")
                }]
            )
        except Exception as e:
            print(f"      ⚠ Failed to store item in ChromaDB: {e}")
            failed += 1
            
        processed_items.append(item)
        # Delay to keep Groq's Requests-Per-Minute limit happy on free tier
        await asyncio.sleep(4.0)
        
    print(f"\n  ✅ Historian complete:")
    print(f"     • Processed: {len(processed_items)} items")
    print(f"     • ChromaDB current size: {collection.count()}")
    print()
    
    return processed_items


if __name__ == "__main__":
    # Test script for the Historian alone
    async def _test():
        # Clean test DB for fresh test run
        memory_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "chroma_db")
        if os.path.exists(memory_dir):
            client = chromadb.PersistentClient(path=memory_dir)
            try:
                # Clear all previous tests
                client.delete_collection("aria_items")
            except:
                pass
                
        # Inject the dummy history from earlier
        import test_chroma
        test_chroma.test_chroma()
        
        print("\n" + "="*50)
        print("TESTING HISTORIAN AGENT")
        print("="*50)
        
        sample_item = {
            "title": "Meta drops Llama 4 with 120B parameters",
            "snippet": "Meta formally announced Llama 4 today, moving to a 120B parameter dense model.",
            "url": "https://example.com/llama4",
            "source": "hackernews",
            "domain_tags": ["AI_MODEL", "OPEN_SOURCE"],
            "relevance_score": 9
        }
        
        results = await run_historian([sample_item])
        print("\nHistorian Output:")
        print(results[0]["historical_context"])
        
    asyncio.run(_test())
