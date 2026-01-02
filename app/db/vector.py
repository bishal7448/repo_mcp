from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
from pymongo.operations import SearchIndexModel
from app.db.mongo import mongodb_client
from app.core.config import settings

class VectorStoreFactory:
    def __init__(self):
        self.client = mongodb_client.get_client()

        self.vs_index = SearchIndexModel(
            name=settings.VS_INDEX_NAME,
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": settings.EMBEDDING_DIM,
                        "similarity": "cosine",
                    },
                    {"type": "filter", "path": "metadata.repo"},
                ]
            },
            type="vectorSearch"
        )

        self.fts_index = SearchIndexModel(
            name=settings.FTS_INDEX_NAME,
            definition={
                "mappings": {
                    "dynamic": False,
                    "fields": {"text": {"type": "string"}}
                }
            },
            type="search"
        )

    def create(self):
        collection = self.client[settings.DB_NAME][settings.COLLECTION_NAME]

        collection.create_search_indexes([self.vs_index, self.fts_index])

        return MongoDBAtlasVectorSearch(
            mongodb_client=self.client,
            db_name=settings.DB_NAME,
            collection_name=settings.COLLECTION_NAME,
            vector_index_name=settings.VS_INDEX_NAME,
            fulltext_index_name=settings.FTS_INDEX_NAME,
            embedding_model="embedding",
            text_key="text",
        )

vector_store_factory = VectorStoreFactory()
