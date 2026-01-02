import asyncio
import os
import sys
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.getcwd())
load_dotenv()

from app.repositories.metadata import get_repos_collection

async def inspect_repos():
    try:
        collection = get_repos_collection()
        repos = collection.find({})
        print(f"Found {collection.count_documents({})} repos.")
        for repo in repos:
            print(f"Repo: {repo.get('repo_name')}")
            print(f"  Last Updated: {repo.get('last_updated')} (Type: {type(repo.get('last_updated'))})")
            print(f"  Keys: {list(repo.keys())}")
            print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(inspect_repos())
