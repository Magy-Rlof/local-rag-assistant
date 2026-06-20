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
from .job_resolver import resolve_job  # noqa: E402
from .job_matcher import build_job_match_context  # noqa: E402
from .job_match_draft import build_job_match_draft  # noqa: E402
from .job_match_draft_export import (  # noqa: E402
    delete_job_match_draft_export,
    export_job_match_draft,
    list_job_match_draft_exports,
    read_job_match_draft_export,
)
from .job_match_report_export import (  # noqa: E402
    delete_job_match_report_export,
    export_job_match_report,
    list_job_match_report_exports,
    read_job_match_report_export,
    update_job_match_report_review,
)
from .job_batch_report_queue import (  # noqa: E402
    create_job_match_report_batch_queue,
    delete_job_match_report_batch_queue,
    list_job_match_report_batch_queues,
    read_job_match_report_batch_queue,
    update_job_match_report_batch_review,
)
from .resume_revision_draft_export import (  # noqa: E402
    delete_resume_revision_draft_export,
    export_resume_revision_draft,
    list_resume_revision_draft_exports,
    read_resume_revision_draft_export,
)
from .resume_revision_compare import compare_resume_revision_with_current  # noqa: E402
from .resume_write_review_queue import (  # noqa: E402
    create_resume_write_review_item,
    delete_resume_write_review_item,
    list_resume_write_review_items,
    read_resume_write_review_item,
    update_resume_write_review_item,
)
from .job_interview import build_interview_feedback, build_interview_session  # noqa: E402
from .job_agent_summary import build_job_agent_summary  # noqa: E402
from .production_status import get_production_workbench_status  # noqa: E402
from .rag_service import ask_with_rag, stream_event, stream_with_rag  # noqa: E402
from .schemas import (  # noqa: E402
    AskRequest,
    AskResponse,
    DocumentContent,
    DocumentInfo,
    IndexResponse,
    InterviewFeedbackRequest,
    JobAgentSummaryResponse,
    JobMatchDraftExportContentResponse,
    JobMatchDraftExportDeleteResponse,
    JobMatchDraftExportListResponse,
    JobMatchDraftExportRequest,
    JobMatchDraftExportResponse,
    JobMatchReportExportContentResponse,
    JobMatchReportExportDeleteResponse,
    JobMatchReportExportListResponse,
    JobMatchReportExportRequest,
    JobMatchReportExportResponse,
    JobMatchReportBatchDeleteResponse,
    JobMatchReportBatchQueueContentResponse,
    JobMatchReportBatchQueueListResponse,
    JobMatchReportBatchQueueRequest,
    JobMatchReportBatchQueueResponse,
    JobMatchReportBatchReviewUpdateRequest,
    JobMatchReportBatchReviewUpdateResponse,
    JobMatchReportReviewUpdateRequest,
    JobMatchReportReviewUpdateResponse,
    ProductionWorkbenchStatusResponse,
    JobInterviewFeedbackResponse,
    JobInterviewSessionResponse,
    JobMatchContextResponse,
    JobMatchDraftResponse,
    JobResolveResponse,
    ResumeRevisionCompareResponse,
    ResumeRevisionDraftExportContentResponse,
    ResumeRevisionDraftExportDeleteResponse,
    ResumeRevisionDraftExportListResponse,
    ResumeRevisionDraftExportRequest,
    ResumeRevisionDraftExportResponse,
    ResumeWriteReviewDeleteResponse,
    ResumeWriteReviewQueueContentResponse,
    ResumeWriteReviewQueueListResponse,
    ResumeWriteReviewQueueRequest,
    ResumeWriteReviewQueueResponse,
    ResumeWriteReviewUpdateRequest,
    ResumeWriteReviewUpdateResponse,
    SetCurrentResumeRequest,
    UpdateDocumentRequest,
)


app = FastAPI(title="Local RAG Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
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


@app.get("/api/production/status", response_model=ProductionWorkbenchStatusResponse)
def production_workbench_status() -> dict:
    return get_production_workbench_status()


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


@app.get("/api/jobs/resolve", response_model=JobResolveResponse)
def resolve_job_endpoint(query: str) -> dict:
    try:
        return resolve_job(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/context", response_model=JobMatchContextResponse)
def build_job_match_context_endpoint(query: str) -> dict:
    try:
        return build_job_match_context(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/draft", response_model=JobMatchDraftResponse)
def build_job_match_draft_endpoint(query: str) -> dict:
    try:
        return build_job_match_draft(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/match/draft/export", response_model=JobMatchDraftExportResponse)
def export_job_match_draft_endpoint(request: JobMatchDraftExportRequest) -> dict:
    try:
        return export_job_match_draft(request.query, request.confirm_save, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/draft/exports", response_model=JobMatchDraftExportListResponse)
def list_job_match_draft_exports_endpoint() -> dict:
    try:
        return list_job_match_draft_exports()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/draft/exports/{file_name}", response_model=JobMatchDraftExportContentResponse)
def read_job_match_draft_export_endpoint(file_name: str) -> dict:
    try:
        return read_job_match_draft_export(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft export does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/jobs/match/draft/exports/{file_name}", response_model=JobMatchDraftExportDeleteResponse)
def delete_job_match_draft_export_endpoint(file_name: str) -> dict:
    try:
        return delete_job_match_draft_export(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft export does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/match/resume-diff/export", response_model=ResumeRevisionDraftExportResponse)
def export_resume_revision_draft_endpoint(request: ResumeRevisionDraftExportRequest) -> dict:
    try:
        return export_resume_revision_draft(request.query, request.confirm_save, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/resume-diff/exports", response_model=ResumeRevisionDraftExportListResponse)
def list_resume_revision_draft_exports_endpoint() -> dict:
    try:
        return list_resume_revision_draft_exports()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/resume-diff/exports/{file_name}", response_model=ResumeRevisionDraftExportContentResponse)
def read_resume_revision_draft_export_endpoint(file_name: str) -> dict:
    try:
        return read_resume_revision_draft_export(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume revision draft does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/jobs/match/resume-diff/exports/{file_name}/compare-current",
    response_model=ResumeRevisionCompareResponse,
)
def compare_resume_revision_with_current_endpoint(file_name: str) -> dict:
    try:
        return compare_resume_revision_with_current(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume revision draft does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/jobs/match/resume-diff/exports/{file_name}", response_model=ResumeRevisionDraftExportDeleteResponse)
def delete_resume_revision_draft_export_endpoint(file_name: str) -> dict:
    try:
        return delete_resume_revision_draft_export(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume revision draft does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/match/resume-write-review/queue", response_model=ResumeWriteReviewQueueResponse)
def create_resume_write_review_item_endpoint(request: ResumeWriteReviewQueueRequest) -> dict:
    try:
        return create_resume_write_review_item(request.diff_file_name, request.confirm_queue, request.note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume revision draft does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/resume-write-review/queue", response_model=ResumeWriteReviewQueueListResponse)
def list_resume_write_review_items_endpoint() -> dict:
    try:
        return list_resume_write_review_items()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/resume-write-review/queue/{file_name}", response_model=ResumeWriteReviewQueueContentResponse)
def read_resume_write_review_item_endpoint(file_name: str) -> dict:
    try:
        return read_resume_write_review_item(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume write review item does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/jobs/match/resume-write-review/queue/{file_name}/review", response_model=ResumeWriteReviewUpdateResponse)
def update_resume_write_review_item_endpoint(file_name: str, request: ResumeWriteReviewUpdateRequest) -> dict:
    try:
        return update_resume_write_review_item(file_name, request.review_status, request.review_note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume write review item does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/jobs/match/resume-write-review/queue/{file_name}", response_model=ResumeWriteReviewDeleteResponse)
def delete_resume_write_review_item_endpoint(file_name: str) -> dict:
    try:
        return delete_resume_write_review_item(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume write review item does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/match/report/export", response_model=JobMatchReportExportResponse)
def export_job_match_report_endpoint(request: JobMatchReportExportRequest) -> dict:
    try:
        return export_job_match_report(request.query, request.confirm_save, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/report/exports", response_model=JobMatchReportExportListResponse)
def list_job_match_report_exports_endpoint() -> dict:
    try:
        return list_job_match_report_exports()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/report/exports/{file_name}", response_model=JobMatchReportExportContentResponse)
def read_job_match_report_export_endpoint(file_name: str) -> dict:
    try:
        return read_job_match_report_export(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report export does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/jobs/match/report/exports/{file_name}", response_model=JobMatchReportExportDeleteResponse)
def delete_job_match_report_export_endpoint(file_name: str) -> dict:
    try:
        return delete_job_match_report_export(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report export does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/jobs/match/report/exports/{file_name}/review", response_model=JobMatchReportReviewUpdateResponse)
def update_job_match_report_review_endpoint(file_name: str, request: JobMatchReportReviewUpdateRequest) -> dict:
    try:
        return update_job_match_report_review(file_name, request.review_status, request.review_note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report export does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/match/report/batch-queue", response_model=JobMatchReportBatchQueueResponse)
def create_job_match_report_batch_queue_endpoint(request: JobMatchReportBatchQueueRequest) -> dict:
    try:
        return create_job_match_report_batch_queue(request.queries, request.confirm_queue, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/report/batch-queue", response_model=JobMatchReportBatchQueueListResponse)
def list_job_match_report_batch_queues_endpoint() -> dict:
    try:
        return list_job_match_report_batch_queues()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/match/report/batch-queue/{file_name}", response_model=JobMatchReportBatchQueueContentResponse)
def read_job_match_report_batch_queue_endpoint(file_name: str) -> dict:
    try:
        return read_job_match_report_batch_queue(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch report queue does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put(
    "/api/jobs/match/report/batch-queue/{file_name}/review",
    response_model=JobMatchReportBatchReviewUpdateResponse,
)
def update_job_match_report_batch_review_endpoint(
    file_name: str,
    request: JobMatchReportBatchReviewUpdateRequest,
) -> dict:
    try:
        return update_job_match_report_batch_review(file_name, request.review_status, request.review_note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch report queue does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/jobs/match/report/batch-queue/{file_name}", response_model=JobMatchReportBatchDeleteResponse)
def delete_job_match_report_batch_queue_endpoint(file_name: str) -> dict:
    try:
        return delete_job_match_report_batch_queue(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch report queue does not exist.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/interview/session", response_model=JobInterviewSessionResponse)
def build_interview_session_endpoint(query: str) -> dict:
    try:
        return build_interview_session(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/interview/feedback", response_model=JobInterviewFeedbackResponse)
def build_interview_feedback_endpoint(request: InterviewFeedbackRequest) -> dict:
    try:
        return build_interview_feedback(request.query, request.question_id, request.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/agent/summary", response_model=JobAgentSummaryResponse)
def build_job_agent_summary_endpoint(query: str) -> dict:
    try:
        return build_job_agent_summary(query)
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
