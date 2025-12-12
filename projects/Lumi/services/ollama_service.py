import os
from typing import Dict

import httpx
from fastapi import HTTPException


class OllamaService:
    """
    Ollama 서버와 HTTP로 통신하는 서비스.
    - 기본 URL: http://127.0.0.1:11434
    - 기본 모델: 환경변수 LUMI_OLLAMA_MODEL (없으면 'gemma:2b')
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("LUMI_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        # 여기서 기본값을 llama3.1 -> gemma:2b 로 변경
        self.model = os.getenv("LUMI_OLLAMA_MODEL", "gemma:2b")

    async def check_ollama_health(self) -> Dict[str, str]:
        """
        Ollama 서버 헬스 체크.
        /api/tags 에 GET 을 보내서 서버/모델 상태를 확인한다.
        항상 dict(status, detail) 형태를 반환한다.
        """
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=3.0) as client:
                resp = await client.get("/api/tags")

            if resp.status_code != 200:
                return {
                    "status": "ERROR",
                    "detail": f"Ollama 응답 코드: {resp.status_code}",
                }

            data = resp.json()
            models = [m.get("name") for m in data.get("models", [])]

            if self.model in models:
                return {
                    "status": "OK",
                    "detail": f"Ollama 서버 연결 성공, 모델 '{self.model}' 사용 가능",
                }
            else:
                return {
                    "status": "WARN",
                    "detail": (
                        f"Ollama 서버는 응답하지만, 모델 '{self.model}' 을(를) 찾지 못했습니다. "
                        f"사용 가능한 모델: {models}"
                    ),
                }

        except Exception as e:
            return {
                "status": "NOT_FOUND",
                "detail": f"Ollama 서버에 연결하지 못했습니다: {e}",
            }

    async def ask(self, prompt: str) -> str:
        """
        Ollama /api/chat 엔드포인트에 질의를 보내고, 응답 텍스트만 문자열로 반환한다.
        """
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
                resp = await client.post("/api/chat", json=payload)

            if resp.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Ollama 응답 코드: {resp.status_code}, body={resp.text}",
                )

            data = resp.json()
            # 표준 Ollama /api/chat 응답: {"message": {"role": "assistant", "content": "..."}}
            message = data.get("message") or {}
            content = message.get("content")

            if not content:
                raise RuntimeError(f"Ollama 응답에서 content 를 찾지 못했습니다: {data!r}")

            return str(content)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama 요청 중 오류 발생: {e}",
            )


def get_ollama_service() -> OllamaService:
    return OllamaService()
