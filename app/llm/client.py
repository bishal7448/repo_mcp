from llama_index.llms.nebius import NebiusLLM
from app.core.config import settings

class LLMProvider:
    def __init__(self):
        self.llm = NebiusLLM(
            api_key=settings.NEBIUS_API_KEY,
            model="google/gemma-2-9b-it-fast" # TODO: change model
        )

    def get_llm(self):
        return self.llm

llm_provider = LLMProvider()
