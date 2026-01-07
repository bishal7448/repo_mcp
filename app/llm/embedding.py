import os
from dotenv import load_dotenv
from llama_index.embeddings.google import GeminiEmbedding
from app.core.config import settings

class EmbeddingProvider:
    def __init__(self):
        self.embedding = GeminiEmbedding(
            model_name="models/text-embedding-004",
            api_key="AIzaSyCKZTLLFExGXPrRhIE1uZurHrkp3ZTki6Q",
        )

    def get_embedding(self):
        return self.embedding

embedding_provider = EmbeddingProvider()
