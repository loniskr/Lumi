from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import multiprocessing
import re

import models
from services.search_service import get_search_service, SearchService
from services.ollama_service import OllamaService, get_ollama_service
from services.rag_service import RAGService, get_rag_service

app = FastAPI()

# ----- CORS 설정 -----
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- 헬스 체크 -----
@app.get("/api/health", response_model=models.HealthStatus)
async def health_check(
    search: SearchService = Depends(get_search_service),
    ollama: OllamaService = Depends(get_ollama_service),
):
    try:
        ollama_status_dict = await ollama.check_ollama_health()
    except Exception as e:
        ollama_status_dict = {"status": "NOT_FOUND", "detail": str(e)}

    try:
        everything_status_dict = search.check_es_health()
    except Exception as e:
        everything_status_dict = {"status": "NOT_FOUND", "detail": str(e)}

    return models.HealthStatus(
        ollama_status=models.HealthStatusDetail(**ollama_status_dict),
        everything_status=models.HealthStatusDetail(**everything_status_dict),
    )

# ----- Ollama 질의 -----
@app.post("/api/ask", response_model=models.AskResponse)
async def ask_ollama(request: models.AskRequest, ollama: OllamaService = Depends(get_ollama_service)):
    try:
        response_text = await ollama.ask(request.prompt)
        return models.AskResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----- Everything 검색 -----
@app.post("/api/search", response_model=models.SearchResponse)
def search_files(request: models.SearchRequest, search: SearchService = Depends(get_search_service)):
    try:
        results_list = search.search(request.query)
        return models.SearchResponse(results=results_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----- 문서 처리 -----
@app.post("/api/process_document", response_model=models.ProcessResponse)
def process_document(request: models.ProcessRequest, rag: RAGService = Depends(get_rag_service)):
    try:
        content, file_format = rag.extract_text(request.file_path)
        return models.ProcessResponse(content=content, format=file_format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----- [핵심] 파일 기반 RAG 채팅 -----
class ChatFileRequest(models.AskRequest):
    file_path: str

@app.post("/api/chat_with_file", response_model=models.AskResponse)
async def chat_with_file(
    request: ChatFileRequest,
    rag: RAGService = Depends(get_rag_service),
    ollama: OllamaService = Depends(get_ollama_service),
):
    try:
        file_content, _ = rag.extract_text(request.file_path)
        truncated_content = file_content[:10000]
        system_prompt = (
            f"You are a helpful assistant. Answer based on the file content.\n\n"
            f"--- File Content ---\n{truncated_content}\n--------------------\n"
        )
        full_prompt = f"{system_prompt}\n\nUser Question: {request.prompt}"
        response_text = await ollama.ask(full_prompt)
        return models.AskResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- [최종 수정] AI 에이전트 (하이브리드 방식) -----

@app.post("/api/agent", response_model=models.AgentResponse)
async def agent_action(
    request: models.AgentRequest,
    search: SearchService = Depends(get_search_service),
    ollama: OllamaService = Depends(get_ollama_service),
):
    user_q = request.user_query.strip()
    
    # ---------------------------------------------------------
    # [1단계] 경로 추출 (Path Extraction) - 토큰 기반 방식 (New)
    # 정규식 대신 어절(띄어쓰기) 단위로 분석하여 한글 경로도 완벽하게 잡습니다.
    # ---------------------------------------------------------
    
    # 1. 한국어 조사 및 불필요한 단어 제거 (경로에 붙어있을 수 있음)
    # 주의: "폴더"라는 단어는 경로의 일부일 수도 있으니(예: New Folder),
    #       단독으로 쓰인 한글 "폴더"만 조심스럽게 제거하거나,
    #       아예 제거하지 않고 "폴더"가 경로 뒤에 붙어있지 않게 띄어쓰기를 보장하는 것이 좋습니다.
    #       여기서는 안전하게 '드라이브'와 조사 '에서' 정도만 처리합니다.
    
    clean_q = user_q.replace("드라이브", ":") \
                    .replace("에서", " ") \
                    .replace("에 ", " ") # '에'는 뒤에 공백이 있을 때만 조사로 간주
    
    tokens = clean_q.split() # 띄어쓰기 기준으로 단어 분리
    path = None
    
    for token in tokens:
        # "C:", "D:\Work", "E:\민혁" 등 드라이브 문자로 시작하는 단어를 찾음
        # (윈도우 경로는 대소문자 구분이 없으므로 정규식으로 패턴 확인)
        if re.match(r'^[a-zA-Z]:', token):
            # 찾은 토큰을 경로로 지정 (따옴표 제거)
            path = token.replace('"', '').replace("'", "")
            break

    # ---------------------------------------------------------
    # [2단계] 의도(Intent) 파악 및 쿼리 조립
    # ---------------------------------------------------------
    query_str = None
    sort_mode = 0 # 기본(정확도순)
    
    user_q_lower = user_q.lower()
    
    # 기본 경로 문자열 (경로가 있으면 따옴표로 감쌈)
    base_path = f'\"{path}\"' if path else ""

    # (A) 빈 폴더 찾기
    if any(w in user_q_lower for w in ["빈 ", "비어있는", "empty"]):
        # 예: "E:\민혁" folder:childcount:0
        query_str = f'{base_path} folder:childcount:0'.strip()
        sort_mode = 0 
    
    # (B) 용량이 큰 파일
    elif any(w in user_q_lower for w in ["큰", "많은", "large", "biggest", "highest", "용량"]):
        # 예: "C:" file: (정렬은 코드에서 sizeDesc)
        query_str = f'{base_path} file:'.strip()
        sort_mode = 6 # Size Descending
        
    # (C) 최근 수정된 파일
    elif any(w in user_q_lower for w in ["최근", "recent", "오늘", "today", "방금", "newest"]):
        if any(w in user_q_lower for w in ["오늘", "today"]):
            query_str = f'{base_path} dm:today file:'.strip()
        else:
            query_str = f'{base_path} file:'.strip()
        sort_mode = 14 # Date Modified Descending

    # ---------------------------------------------------------
    # [3단계] AI Fallback (규칙에 안 걸리는 복잡한 요청)
    # ---------------------------------------------------------
    if not query_str:
        system_prompt = (
            "Translate the user's request into an 'Everything' search query.\n"
            "Output ONLY the query inside <query> tags.\n"
            "Rules:\n"
            "1. Wrap paths in double quotes (e.g. \"C:\\Work\").\n"
            "2. Do not include explanations.\n"
            "Examples:\n"
            "- 'Project excel files': <query>project ext:xlsx</query>\n"
            "- 'Files in D:\\Work': <query>\"D:\\Work\" file:</query>\n"
            f"User: {user_q}"
        )
        llm_resp = await ollama.ask(system_prompt)
        
        match = re.search(r"<query>(.*?)</query>", llm_resp, re.DOTALL)
        if match:
            query_str = match.group(1).strip()
        elif any(k in llm_resp for k in ["ext:", "size:", "file:", "folder:", ":\\"]):
            query_str = llm_resp.strip()

    # ---------------------------------------------------------
    # [4단계] 검색 실행
    # ---------------------------------------------------------
    if query_str:
        # 백틱 등 불필요한 문자 제거
        query_str = query_str.replace("`", "").strip()
        
        try:
            results = search.search(query_str, max_results=20, sort_mode=sort_mode)
            
            if not results:
                # 결과가 없을 때 디버깅하기 좋게 쿼리를 보여줌
                msg = f"🔍 검색어 '{query_str}' (정렬: {sort_mode})로 찾았으나 결과가 없습니다."
            else:
                msg = f"🔍 '{query_str}' 조건으로 {len(results)}개의 파일을 찾았습니다."

            return models.AgentResponse(
                message=msg,
                action_type="search",
                results=[models.SearchResultItem(**r) for r in results]
            )
        except Exception as e:
            return models.AgentResponse(message=f"검색 오류: {e}", action_type="chat")

    return models.AgentResponse(message="죄송합니다. 검색 명령을 이해하지 못했습니다.", action_type="chat")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
        log_config=None,
    )
