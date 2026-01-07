from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Repo-MCP"
    
    # API Keys
    GITHUB_API_KEY: str = "default_github_api_key"
    NEBIUS_API_KEY: str = "default_nebius_api_key"
    GOOGLE_API_KEY: str = "default_google_api_key"
    MONGODB_URI: str = "default_mongodb_uri"
    
    # Database
    DB_NAME: str = "doc_mcp_db"
    COLLECTION_NAME: str = "doc_mcp_collection"
    REPOS_COLLECTION_NAME: str = "ingested_repos"
    
    # Search Indices
    VS_INDEX_NAME: str = "doc_mcp_vector_index"
    FTS_INDEX_NAME: str = "doc_mcp_fts_index"
    
    # Model Config
    EMBEDDING_DIM: int = 768

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
