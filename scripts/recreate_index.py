import sys
import os
import time
from pymongo.errors import OperationFailure

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.db.mongo import mongodb_client
from app.db.vector import vector_store_factory

def recreate_index():
    print(f"Connecting to database: {settings.DB_NAME}")
    client = mongodb_client.get_client()
    db = client[settings.DB_NAME]
    collection = db[settings.COLLECTION_NAME]

    index_name = settings.VS_INDEX_NAME
    print(f"Target index: {index_name}")

    # 1. Drop existing index
    try:
        print(f"Attempting to drop index: {index_name}")
        collection.drop_search_index(index_name)
        print("Drop command sent. Waiting for index to be removed...")
        
        # Wait until index is gone
        while True:
            indexes = list(collection.list_search_indexes())
            if not any(idx['name'] == index_name for idx in indexes):
                print("Index successfully removed.")
                break
            print("Index still exists, waiting...")
            time.sleep(2)
            
    except OperationFailure as e:
        print(f"Result of drop attempt: {e}")
        # Validate if it was because it didn't exist
        print("Continuing...")

    # 2. Create new index
    print("Creating new index...")
    # vector_store_factory is initialized with current settings, so it should have 768 dims
    # We only want to recreate the vector index, but create_search_indexes takes a list
    # Let's verify the dimension in the factory
    
    # Access the definition directly to verify
    for field in vector_store_factory.vs_index.document['definition']['fields']:
        if field.get('type') == 'vector':
            print(f"Creating index with dimension: {field.get('numDimensions')}")
    
    try:
        result = collection.create_search_indexes([vector_store_factory.vs_index])
        print(f"Index creation initiated: {result}")
        print("Note: Index creation on MongoDB Atlas is asynchronous and may take a few minutes.")
    except Exception as e:
        print(f"Failed to create index: {e}")

if __name__ == "__main__":
    recreate_index()
