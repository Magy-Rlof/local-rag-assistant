import sys
from pathlib import Path

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from indexer import build_index  # noqa: E402

from .document_service import (  # noqa: E402
    CATEGORIES,
    delete_document,
    ensure_category_dirs,
    get_current_resume,
    list_documents,
    read_markdown_document,
    save_upload,
    set_current_resume,
    write_markdown_document,
)
from .rag_service import ask_with_rag, stream_event, stream_with_rag  # noqa: E402
from .schemas import (  # noqa: E402
    AskRequest,
    AskResponse,
    DocumentContent,
    DocumentInfo,
    IndexResponse,
    SetCurrentResumeRequest,
    UpdateDocumentRequest,
)


app = FastAPI(title="Local RAG Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    ensure_category_dirs()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/categories")
def categories() -> list[dict]:
    return [{"key": item.key, "label": item.label} for item in CATEGORIES.values()]


@app.get("/api/documents/{category}", response_model=list[DocumentInfo])
def get_documents(category: str) -> list[dict]:
    try:
        return list_documents(category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/documents/{category}/upload", response_model=DocumentInfo)
def upload_document(category: str, file: UploadFile = File(...), source: str = "private") -> dict:
    try:
        return save_upload(category, file.filename or "document.md", file.file, source=source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/documents/{category}/{file_name}", response_model=DocumentContent)
def get_document_content(category: str, file_name: str, source: str = "private") -> dict:
    try:
        content = read_markdown_document(category, file_name, source=source)
        return {"name": file_name, "category": category, "source": source, "content": content}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/documents/{category}/{file_name}", response_model=DocumentInfo)
def update_document_content(category: str, file_name: str, request: UpdateDocumentRequest, source: str = "private") -> dict:
    try:
        return write_markdown_document(category, file_name, request.content, source=source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/documents/{category}/{file_name}")
def remove_document(category: str, file_name: str, source: str = "private") -> dict:
    try:
        delete_document(category, file_name, source=source)
        return {"deleted": True}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/resumes/current", response_model=DocumentInfo | None)
def get_active_resume() -> dict | None:
    return get_current_resume()


@app.put("/api/resumes/current", response_model=DocumentInfo)
def set_active_resume(request: SetCurrentResumeRequest) -> dict:
    try:
        return set_current_resume(request.name, source=request.source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="简历不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/index/build", response_model=IndexResponse)
def build_vector_index() -> dict:
    logs: list[str] = []
    try:
        result = build_index(log=logs.append)
        return {
            "changed_sources": result.changed_sources,
            "skipped_sources": result.skipped_sources,
            "removed_sources": result.removed_sources,
            "written_points": result.written_points,
            "collection_name": result.collection_name,
            "storage_path": result.storage_path,
            "logs": logs,
        }
    except requests.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail="Embedding API 请求超时，请稍后重试。新增资料较多时，索引构建可能需要更长时间。",
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Embedding API 网络请求失败：{exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rag/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")
    try:
        return ask_with_rag(question, [message.model_dump() for message in request.history])
    except requests.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail="模型 API 请求超时，请稍后重试。当前问题可能需要较长生成时间，或模型服务暂时不可用。",
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"模型 API 网络请求失败：{exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rag/ask/stream")
def ask_stream(request: AskRequest) -> StreamingResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")

    def generate():
        try:
            yield from stream_with_rag(question, [message.model_dump() for message in request.history])
        except requests.Timeout as exc:
            yield stream_event("error", {"message": f"模型 API 请求超时：{exc}"})
        except requests.RequestException as exc:
            yield stream_event("error", {"message": f"模型 API 网络请求失败：{exc}"})
        except RuntimeError as exc:
            yield stream_event("error", {"message": str(exc)})

    return StreamingResponse(generate(), media_type="application/x-ndjson")
