from typing import List, Optional
from pydantic import BaseModel

# ----- [기본] Ask / Chat (오류 해결을 위해 필수) -----
class AskRequest(BaseModel):
    prompt: str

class AskResponse(BaseModel):
    response: str

# ----- [기본] Search (Everything) -----
class SearchRequest(BaseModel):
    query: str

class SearchResultItem(BaseModel):
    name: str
    path: str

class SearchResponse(BaseModel):
    results: List[SearchResultItem]

# ----- [기본] RAG / 문서 처리 -----
class ProcessRequest(BaseModel):
    file_path: str

class ProcessResponse(BaseModel):
    content: str
    format: str  # "markdown" 또는 "text"

# ----- [기본] Health Check -----
class HealthStatusDetail(BaseModel):
    status: str
    detail: str

class HealthStatus(BaseModel):
    ollama_status: HealthStatusDetail
    everything_status: HealthStatusDetail

# ----- [확장] Agent (이전 단계의 AI 에이전트용) -----
class AgentRequest(BaseModel):
    user_query: str

class AgentResponse(BaseModel):
    message: str
    action_type: str
    results: List[SearchResultItem] = []