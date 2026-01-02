from typing import List
from datetime import datetime
from app.db.mongo import mongodb_client
from app.core.config import settings

def get_repos_collection():
    return mongodb_client.get_client()[settings.DB_NAME][settings.REPOS_COLLECTION_NAME]

# Store ingested repository data
def store_ingested_repo(repo_name: str, ingested_files: List[str]) -> bool:
    try:
        # Get repositories collection
        repos_collection = get_repos_collection()

        # Simple document format
        repo_doc = {
            "_id": repo_name,  # Use repo name as unique ID
            "repo_name": repo_name,
            "ingested_files": ingested_files,
            "file_count": len(ingested_files),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Upsert the document (update if exists, insert if not)
        repos_collection.replace_one({"_id": repo_name}, repo_doc, upsert=True)

        print(f"✅ Successfully stored data for repository: {repo_name} with {len(ingested_files)} ingested files.")
        return True

    except Exception as e:
        print(f"❌ Error storing data for repository {repo_name}: {e}")
        return False
    
def get_available_repos():
    try:
        repos_collection = get_repos_collection()

        # Get all repository names
        repos = repos_collection.find({}, {"repo_name": 1})
        repo_list = [repo["repo_name"] for repo in repos]

        if repo_list:
            return sorted(repo_list)
        else:
            # Fallback to hardcoded list if no repos in database
            return []

    except Exception as e:
        print(f"Error getting repos from database: {e}")
        # Fallback to hardcoded list
        return []

# Get detailed information about all repositories
def get_repo_details():
    """Get detailed information about all repositories"""
    try:
        repos_collection = get_repos_collection()
        
        # Get all repository details
        repos = repos_collection.find({})
        repo_details = []
        
        # Process each repository
        for repo in repos:
            print(f"DEBUG: Processing repo {repo.get('repo_name')}")
            print(f"DEBUG: Repo keys: {repo.keys()}")
            print(f"DEBUG: last_updated val: {repo.get('last_updated')}")
            
            repo_info = {
                "repo_name": repo.get("repo_name", "Unknown"),
                "file_count": repo.get("file_count", 0),
                "last_updated": repo.get("last_updated", "Unknown"),
                "ingested_files": repo.get("ingested_files", [])
            }
            repo_details.append(repo_info)
        
        return repo_details
        
    except Exception as e:
        print(f"Error getting repository details: {e}")
        return []

# Delete repository data
def delete_repository_data(repo_name):
    try:
        result = {
            "success": False,
            "message": "",
            "vector_docs_deleted": 0,
            "repo_record_deleted": False,
        }

        # Delete from vector store (documents with this repo metadata)
        collection = mongodb_client.get_client()[settings.DB_NAME][settings.COLLECTION_NAME]
        vector_delete_result = collection.delete_many({"metadata.repo": repo_name})
        result["vector_docs_deleted"] = vector_delete_result.deleted_count

        # Delete from repos tracking collection
        repos_collection = get_repos_collection()
        repo_delete_result = repos_collection.delete_one({"_id": repo_name})
        result["repo_record_deleted"] = repo_delete_result.deleted_count > 0

        if result["vector_docs_deleted"] > 0 or result["repo_record_deleted"]:
            result["success"] = True
            result["message"] = f"✅ Successfully deleted repository '{repo_name}'"
            if result["vector_docs_deleted"] > 0:
                result["message"] += (
                    f" ({result['vector_docs_deleted']} documents removed)"
                )
        else:
            result["message"] = (
                f"⚠️ Repository '{repo_name}' not found or already deleted"
            )

        print(result["message"])
        return result

    except Exception as e:
        error_msg = f"❌ Error deleting repository '{repo_name}': {str(e)}"
        print(error_msg)
        return {
            "success": False,
            "message": error_msg,
            "vector_docs_deleted": 0,
            "repo_record_deleted": False,
        }

# Get repository statistics
def get_repository_stats():
    try:
        # Get repositories collection
        repos_collection = get_repos_collection()
        collection = mongodb_client.get_client()[settings.DB_NAME][settings.COLLECTION_NAME]

        # Count total repositories
        total_repos = repos_collection.count_documents({})

        # Count total documents in vector store
        total_docs = collection.count_documents({})

        # Get total files across all repos
        total_files = 0
        repos = repos_collection.find({}, {"file_count": 1})
        for repo in repos:
            total_files += repo.get("file_count", 0)

        return {
            "total_repositories": total_repos,
            "total_documents": total_docs,
            "total_files": total_files,
        }

    except Exception as e:
        print(f"Error getting repository stats: {e}")
        return {"total_repositories": 0, "total_documents": 0, "total_files": 0}
