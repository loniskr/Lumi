import os
import sys
import ctypes
from typing import Dict, List
from fastapi import HTTPException

# ----- DLL 경로 유틸 (기존 유지) -----
def get_dll_path() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "Everything64.dll")
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(current_dir)
        return os.path.join(base_path, "bin", "Everything64.dll")

# ----- 상수 및 DLL 설정 -----
EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME = 0x00000004
EVERYTHING_SORT_SIZE_DESCENDING = 6          # [신규] 크기순 (폴더의 경우 크기 인덱싱 필요할 수 있음)
EVERYTHING_SORT_DATE_MODIFIED_DESCENDING = 14 # [수정] 기존 2 -> 14 (Everything 표준)

try:
    FINAL_DLL_PATH = get_dll_path()
    everything_dll = ctypes.WinDLL(FINAL_DLL_PATH)

    # 기존 함수 정의
    everything_dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
    everything_dll.Everything_SetSearchW.restype = None
    everything_dll.Everything_SetRequestFlags.argtypes = [ctypes.c_uint]
    everything_dll.Everything_SetRequestFlags.restype = None
    everything_dll.Everything_QueryW.argtypes = [ctypes.c_bool]
    everything_dll.Everything_QueryW.restype = ctypes.c_bool
    everything_dll.Everything_GetNumResults.argtypes = []
    everything_dll.Everything_GetNumResults.restype = ctypes.c_uint
    everything_dll.Everything_GetResultFullPathNameW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
    everything_dll.Everything_GetResultFullPathNameW.restype = None
    everything_dll.Everything_GetLastError.argtypes = []
    everything_dll.Everything_GetLastError.restype = ctypes.c_uint

    # [추가] 정렬 함수 정의
    everything_dll.Everything_SetSort.argtypes = [ctypes.c_uint]
    everything_dll.Everything_SetSort.restype = None

except Exception as e:
    print(f"Everything DLL 로드 실패: {e}")
    everything_dll = None

# ----- 서비스 클래스 -----
class SearchService:
    def __init__(self) -> None:
        if everything_dll is None:
            raise RuntimeError("Everything DLL을 로드할 수 없습니다.")

    def check_es_health(self) -> Dict[str, str]:
        # (기존 헬스 체크 로직 유지 - 생략 가능하나 전체 코드 완성을 위해 포함 권장)
        try:
            everything_dll.Everything_SetSearchW("")
            everything_dll.Everything_QueryW(True)
            return {"status": "OK", "detail": "Connected"}
        except:
            return {"status": "ERROR", "detail": "Disconnected"}

    def search(self, query: str, max_results: int = 30, sort_mode: int = 0) -> List[Dict[str, str]]:
        """
        sort_mode: 0(기본), 6(크기순), 14(날짜순)
        """
        try:
            everything_dll.Everything_SetSearchW(query)
            everything_dll.Everything_SetRequestFlags(EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME)
            
            # [추가] 정렬 적용
            if sort_mode != 0:
                everything_dll.Everything_SetSort(sort_mode)

            ok = everything_dll.Everything_QueryW(True)
            if not ok:
                raise HTTPException(status_code=500, detail="Query Failed")

            num_results = everything_dll.Everything_GetNumResults()
            num = min(num_results, max_results)
            
            results_list = []
            buffer = ctypes.create_unicode_buffer(260)

            for i in range(num):
                everything_dll.Everything_GetResultFullPathNameW(i, buffer, 260)
                full_path = buffer.value
                path_dir, file_name = os.path.split(full_path)
                results_list.append({"name": file_name, "path": path_dir})

            return results_list
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

def get_search_service() -> SearchService:
    return SearchService()