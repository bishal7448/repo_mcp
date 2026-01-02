from typing import List
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import (FilterOperator, MetadataFilter, MetadataFilters)
from app.db.vector import vector_store_factory
from app.repositories.metadata import get_available_repos as get_repos_from_db
from app.core.prompts import QA_PROMPT

class QueryRetriever:
    def __init__(self, repo):
        self.vector_store_index = VectorStoreIndex.from_vector_store(vector_store_factory.create())
        self.filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="metadata.repo",
                    value=repo,
                    operator=FilterOperator.EQ,
                )
            ]
        )

    def make_query(self, query: str, mode: str = "default") -> dict:
        """
        Retrieve relevant documentation context for a given query using specified retrieval mode.

        This function is designed to support Retrieval-Augmented Generation (RAG) by extracting
        the most relevant context chunks from indexed documentation sources.

        Args:
            query (str): The user's input query related to the documentation.
            mode (str, optional): Retrieval strategy to use. One of:
                - "default": Standard semantic similarity search.
                - "text_search": Keyword-based search.
                - "hybrid": Combines semantic and keyword-based methods.
                Defaults to "default".

        Returns:
            dict: Dictionary with 'response' and 'source_nodes' keys
        """
        query_engine = self.vector_store_index.as_query_engine(
            similarity_top_k=5,
            vector_store_query_mode=mode,
            filters=self.filters,
            response_mode="refine",
            text_qa_template=QA_PROMPT,
        )

        response = query_engine.query(query)
        nodes = []
        for node in response.source_nodes:
            nodes.append(
                {
                    "file_name": node.metadata.get("file_name", "Unknown"),
                    "url": node.metadata.get("url", "#"),
                    "score": float(node.score) if node.score else 0.0,
                    "content": node.get_content(),
                }
            )

        return {"response": str(response.response), "source_nodes": nodes}

    @staticmethod
    def get_available_repos() -> List[str]:
        """Get list of available repositories in the vector store"""
        try:
            print("fetching repos")
            re = get_repos_from_db()

            print(re)
            return re
        except Exception as e:
            print(f"Error getting repos from database: {e}")
            # Fallback to hardcoded list
            return ["mindsdb/mindsdb", "run-llama/llama_index"]
    