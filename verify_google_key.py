import os
import sys
from llama_index.embeddings.google import GeminiEmbedding
from app.core.config import settings
from dotenv import load_dotenv

# Load env vars
load_dotenv()

api_key = settings.GOOGLE_API_KEY
if not api_key:
    print("Error: GOOGLE_API_KEY not found in environment variables.")
    sys.exit(1)

print(f"Testing API Key: {api_key[:5]}...{api_key[-5:]}")

try:
    embed_model = GeminiEmbedding(
        model_name="models/text-embedding-004",
        api_key=''
    )
    # Try actual embedding
    embedding = embed_model.get_text_embedding("Hello world")
    print("Success: API key is valid and embedding generated.")
    print(f"Embedding length: {len(embedding)}")
except Exception as e:
    print(f"Error: Failed to generate embedding. {e}")
    sys.exit(1)
