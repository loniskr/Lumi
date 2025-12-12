import os
from typing import Tuple

from fastapi import HTTPException

import pymupdf4llm
import docx  # python-docx


class RAGService:
    """
    문서에서 텍스트를 추출하는 간단한 서비스.
    - PDF: pymupdf4llm.to_markdown() 으로 Markdown 텍스트 추출
    - DOCX: python-docx 로 본문 텍스트 추출
    """

    def __init__(self) -> None:
        pass

    def extract_text(self, file_path: str) -> Tuple[str, str]:
        """
        주어진 파일 경로에서 텍스트를 추출한다.
        반환값: (content, format)
          - format: 'markdown' 또는 'text'
        """
        if not file_path:
            raise HTTPException(status_code=400, detail="file_path 가 비었습니다.")

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"파일을 찾을 수 없습니다: {file_path}",
            )

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        try:
            if ext == ".pdf":
                # PDF -> Markdown
                content = pymupdf4llm.to_markdown(file_path)
                return content, "markdown"

            elif ext in (".docx", ".doc"):
                # DOCX -> 일반 텍스트
                document = docx.Document(file_path)
                paragraphs = [p.text for p in document.paragraphs if p.text]
                content = "\n".join(paragraphs)
                return content, "text"

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"지원하지 않는 파일 형식입니다: {ext}",
                )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"문서 처리 중 오류가 발생했습니다: {e}",
            )


def get_rag_service() -> RAGService:
    return RAGService()
