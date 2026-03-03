import os
import chromadb

def test_chroma():
    memory_dir = os.path.join(os.path.dirname(__file__), "memory", "chroma_db")
    os.makedirs(memory_dir, exist_ok=True)
    
    print(f"Initializing ChromaDB persistent client at: {memory_dir}")
    # ChromaDB's PersistentClient uses the specific path to store sqlite and parquet files
    client = chromadb.PersistentClient(path=memory_dir)
    
    # Create or get collection
    collection = client.get_or_create_collection(name="aria_items")
    print(f"Collection 'aria_items' created/loaded. Current count: {collection.count()}")
    
    # 3 Dummy items conforming to the metadata schema requirements
    dummy_items = [
        {
            "id": "test_item_1",
            "title": "GPT-4 Released",
            "snippet": "OpenAI releases GPT-4, a large multimodal model.",
            "date": "2023-03-14T00:00:00Z",
            "domain_tags": "AI_MODEL",
            "impact_score": "10",
            "source": "hackernews"
        },
        {
            "id": "test_item_2",
            "title": "Llama 3 Announced",
            "snippet": "Meta announces Llama 3 with 70B and 8B parameters.",
            "date": "2024-04-18T00:00:00Z",
            "domain_tags": "AI_MODEL,OPEN_SOURCE",
            "impact_score": "9",
            "source": "hackernews"
        },
        {
            "id": "test_item_3",
            "title": "AWS Bedrock adds Anthropic Claude 3",
            "snippet": "AWS announces general availability of Claude 3 on Amazon Bedrock.",
            "date": "2024-03-04T00:00:00Z",
            "domain_tags": "AWS,AI_MODEL",
            "impact_score": "8",
            "source": "aws_blog"
        }
    ]
    
    print("\nStoring 3 dummy items...")
    
    ids = [item["id"] for item in dummy_items]
    # We embed title + snippet as requested by the user
    documents = [f"{item['title']} - {item['snippet']}" for item in dummy_items]
    metadatas = [
        {
            "date": item["date"],
            "domain_tags": item["domain_tags"],
            "title": item["title"],
            "impact_score": item["impact_score"],
            "source": item["source"]
        } for item in dummy_items
    ]
    
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print(f"Collection count is now: {collection.count()}")
    
    print("\nTesting Query: 'New open source model with 70B parameters'")
    results = collection.query(
        query_texts=["New open source model with 70B parameters"],
        n_results=2
    )
    
    print("\nQuery Results:")
    for i in range(len(results["ids"][0])):
        print(f"  Match {i+1}:")
        print(f"    ID: {results['ids'][0][i]}")
        print(f"    Distance: {results['distances'][0][i]}")
        print(f"    Document: {results['documents'][0][i]}")
        print(f"    Metadata: {results['metadatas'][0][i]}")
    
if __name__ == "__main__":
    test_chroma()
