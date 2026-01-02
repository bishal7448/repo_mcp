from llama_index.embeddings.nebius import NebiusEmbedding
from app.core.config import settings

class EmbeddingProvider:
    def __init__(self):
        self.embedding = NebiusEmbedding(
            api_key=settings.NEBIUS_API_KEY,
            model_name="BAAI/bge-en-icl", # TODO: change model
            embed_batch_size=10
        )

    def get_embedding(self):
        return self.embedding
    
embedding_provider = EmbeddingProvider()
