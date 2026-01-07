
import sys
import os
import asyncio

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.vector import vector_store_factory
from app.llm.embedding import embedding_provider

def test_search():
    print("Initializing vector store...")
    vector_store = vector_store_factory.create()
    
    query = "test query for dimension check"
    print(f"Generating embedding for query: '{query}'")
    
    # We can inspect the embedding dimension
    embedding = embedding_provider.get_embedding().get_text_embedding(query)
    print(f"Embedding dimension: {len(embedding)}")
    
    print("Performing vector search...")
    try:
        # Perform a simple similarity search
        # Note: syntax depends on llama-index version, but usually query is called via query engine
        # Here we use the vector_store directly if possible, or we could just use the helper in app/services/search.py if available.
        # Let's try to use the low-level query on vector_store if possible or just standard mongodb atlas search via pymongo for raw check
        # But vector_store.query might expect a VectorStoreQuery object.
        
        # Simpler: use the pymongo client directly to run an aggregate pipeline to verify no error
        # This mirrors what failed in the user request
        
        from app.db.mongo import mongodb_client
        from app.core.config import settings
        
        client = mongodb_client.get_client()
        collection = client[settings.DB_NAME][settings.COLLECTION_NAME]
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": settings.VS_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": embedding,
                    "numCandidates": 10,
                    "limit": 5
                }
            }
        ]
        
        print("Running aggregation pipeline...")
        results = list(collection.aggregate(pipeline))
        print(f"Search successful! Found {len(results)} results.")
        
    except Exception as e:
        print(f"Search failed with error: {e}")

if __name__ == "__main__":
    test_search()
