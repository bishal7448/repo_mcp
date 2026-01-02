import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.getcwd())
load_dotenv()

from app.repositories.metadata import store_ingested_repo, get_repos_collection

def test_storage():
    repo_name = "test-repo/simulation"
    files = ["README.md", "CONTRIBUTING.md"]
    
    print(f"Storing repo {repo_name}...")
    success = store_ingested_repo(repo_name, files)
    print(f"Store success: {success}")
    
    collection = get_repos_collection()
    doc = collection.find_one({"_id": repo_name})
    
    if doc:
        print(f"Retrieved doc keys: {doc.keys()}")
        print(f"Last Updated: {doc.get('last_updated')}")
        print(f"Type: {type(doc.get('last_updated'))}")
    else:
        print("Doc not found!")

if __name__ == "__main__":
    test_storage()
