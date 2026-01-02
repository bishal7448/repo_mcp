from typing import List, Optional
from pydantic import BaseModel, Field


class Node(BaseModel):
    file_name: str = Field(description="Name of the file")
    url: str = Field(description="GitHub repo url of the file")
    score: float = Field(description="Relevance score of the node")
    content: str = Field(description="Content of the node")


class ContextResponseModel(BaseModel):
    response: str = Field(description="Response for user's query")
    source_nodes: Optional[List[Node]] = Field(
        description="List of sources used to generate response"
    )

class ContextQueryModel(BaseModel):
    query: str = Field(description="User's query")
    source_nodes: Optional[List[Node]] = Field(
        description="List of sources used to generate response"
    )
