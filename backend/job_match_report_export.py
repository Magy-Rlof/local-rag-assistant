import json
import re
from datetime import datetime
from pathlib import Path

from .job_agent_summary import build_job_agent_summary
from .job_interview import build_interview_session
from .job_match_draft import build_job_match_draft
from .job_match_draft_export import (
    format_current_resume,
    render_cannot_claim,
    render_evidence_required,
    render_interview_only,
    render_list,
    render_match_points,
    render_source_refs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "private_data" / "job_match_reports"
VALID_REVIEW_STATUSES = {
    "pending_review": "待审核",
    "accepted": "已采纳",
    "rejected": "已拒绝",
    "needs_evidence": "需补证据",
}


def export_job_match_report(query: str, confirm_save: bool, note: str = "") -> dict:
    if not confirm_save:
        raise ValueError("保存求职分析报告前必须显式设置 confirm_save=true。")

    draft_response = build_job_match_draft(query)
    if not draft_response["matched"]:
        return {
            "exported": False,
            "query": query,
            "target_job": None,
            "current_resume": draft_response["current_resume"],
            "file_name": "",
            "relative_path": "",
            "size_bytes": 0,
            "content_preview": "",
            **default_review_metadata(),
            "warnings": draft_response["warnings"],
        }

    interview_response = build_interview_session(query)
    summary_response = build_job_agent_summary(query)
    content = render_report_content(draft_response, interview_response, summary_response, note)
    file_name = build_report_file_name(draft_response["draft"]["target_confirmation"])
    target_path = unique_export_path(file_name)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    review = write_review_metadata(target_path, "pending_review", "")

    return {
        "exported": True,
        "query": query,
        "target_job": draft_response["target_job"],
        "current_resume": draft_response["current_resume"],
        "file_name": target_path.name,
        "relative_path": target_path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": target_path.stat().st_size,
        "content_preview": content[:500],
        **review,
        "warnings": build_report_warnings(draft_response, interview_response, summary_response),
    }


def list_job_match_report_exports() -> dict:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in sorted(EXPORT_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        review = read_review_metadata(path)
        reports.append(
            {
                "file_name": path.name,
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                **review,
            }
        )
    return {
        "reports": reports,
        "count": len(reports),
        "directory": EXPORT_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Report exports are private review copies.",
            "Report exports are not indexed by default and do not overwrite real resumes.",
        ],
    }


def read_job_match_report_export(file_name: str) -> dict:
    path = resolve_export_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    review = read_review_metadata(path)
    return {
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        **review,
        "content": content,
    }


def delete_job_match_report_export(file_name: str) -> dict:
    path = resolve_export_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    path.unlink()
    review_path = review_metadata_path(path)
    if review_path.exists():
        review_path.unlink()
    return {
        "deleted": True,
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Only the selected private report copy was deleted.",
            "No real resume, job description, index, or source document was modified.",
        ],
    }


def update_job_match_report_review(file_name: str, review_status: str, review_note: str = "") -> dict:
    path = resolve_export_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid report review status.")
    note = (review_note or "").strip()
    if len(note) > 1000:
        raise ValueError("Review note is too long.")
    write_review_metadata(path, review_status, note)
    result = read_job_match_report_export(file_name)
    result["warnings"] = [
        "Only the selected private report review metadata was updated.",
        "No real resume, job description, index, or source document was modified.",
    ]
    return result


def resolve_export_file(file_name: str) -> Path:
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Invalid report file name.")
    if Path(file_name).suffix.lower() != ".md":
        raise ValueError("Only Markdown report exports can be managed.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    root = EXPORT_DIR.resolve()
    candidate = (EXPORT_DIR / file_name).resolve()
    if candidate.parent != root:
        raise ValueError("Report export path is outside the allowed directory.")
    return candidate


def review_metadata_path(report_path: Path) -> Path:
    return report_path.with_suffix(".review.json")


def default_review_metadata() -> dict:
    return {
        "review_status": "pending_review",
        "review_label": VALID_REVIEW_STATUSES["pending_review"],
        "review_note": "",
        "review_updated_at": "",
    }


def read_review_metadata(report_path: Path) -> dict:
    metadata_path = review_metadata_path(report_path)
    if not metadata_path.exists():
        return default_review_metadata()
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_review_metadata()
    status = payload.get("review_status", "pending_review")
    if status not in VALID_REVIEW_STATUSES:
        status = "pending_review"
    return {
        "review_status": status,
        "review_label": VALID_REVIEW_STATUSES[status],
        "review_note": str(payload.get("review_note", ""))[:1000],
        "review_updated_at": str(payload.get("review_updated_at", "")),
    }


def write_review_metadata(report_path: Path, review_status: str, review_note: str) -> dict:
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid report review status.")
    metadata = {
        "review_status": review_status,
        "review_label": VALID_REVIEW_STATUSES[review_status],
        "review_note": review_note,
        "review_updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    review_metadata_path(report_path).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def render_report_content(draft_response: dict, interview_response: dict, summary_response: dict, note: str) -> str:
    draft = draft_response["draft"]
    confirmation = draft["target_confirmation"]
    current_resume = draft_response["current_resume"]
    session = interview_response.get("session")
    summary = summary_response.get("summary")
    revision = draft["resume_revision_candidates"]
    lines = [
        f"# 求职分析报告：{confirmation['title']}",
        "",
        "## 报告边界",
        "",
        "- 本文件是本地私有求职分析报告副本，不是正式简历。",
        "- 本文件不会自动覆盖真实简历，不会自动投递，也不会写入岗位资料目录。",
        "- 可写入简历的候选内容必须先由用户审核，并需要简历或项目资料证据。",
        "- 面试表达、学习计划和不能声称的能力不得混入正式简历。",
        "- 本报告生成不调用 LLM、不访问招聘平台、不触发索引。",
        "",
        "## 目标岗位确认",
        "",
        f"- 岗位名称：{confirmation['title']}",
        f"- 公司：{confirmation['company']}",
        f"- 城市：{confirmation['city']}",
        f"- 来源岗位 ID：{confirmation['source_job_id']}",
        f"- 来源标识：{confirmation['marker']}",
        f"- 来源文件：{confirmation['source_file']}",
        f"- 来源 URL：{confirmation['source_url']}",
        "",
        "## 当前简历状态",
        "",
        f"- 当前简历：{format_current_resume(current_resume)}",
        f"- 报告生成时间：{datetime.now().isoformat(timespec='seconds')}",
    ]
    if note.strip():
        lines.extend(["", "## 用户备注", "", note.strip()])

    lines.extend(
        [
            "",
            "## 审核摘要",
            "",
            f"- 岗位核心要求：{len(draft['job_core_requirements'])} 条",
            f"- 岗位核心职责：{len(draft['job_core_responsibilities'])} 条",
            f"- 可写入简历候选：{len(revision['can_write_to_resume'])} 条",
            f"- 需补证据候选：{len(revision['requires_evidence_before_resume'])} 条",
            f"- 仅适合面试表达：{len(revision['interview_only'])} 条",
            f"- 不能声称能力：{len(revision['cannot_claim'])} 条",
            f"- 面试问题：{len(session['questions']) if session else 0} 个",
        ]
    )

    if summary:
        lines.extend(["", "## Agent 状态", ""])
        for item in summary["pipeline_status"]:
            lines.append(f"- {item['label']}：{item['status']}；{item['detail']}")

    lines.extend(["", "## 岗位核心要求", ""])
    lines.extend(render_list(draft["job_core_requirements"]))
    lines.extend(["", "## 岗位核心职责", ""])
    lines.extend(render_list(draft["job_core_responsibilities"]))
    lines.extend(["", "## 当前资料匹配点", ""])
    lines.extend(render_match_points(draft["current_material_match_points"]))
    lines.extend(["", "## 可写入简历候选", ""])
    lines.extend(render_list(revision["can_write_to_resume"]))
    lines.extend(["", "## 需要证据后才能写入简历", ""])
    lines.extend(render_evidence_required(revision["requires_evidence_before_resume"]))
    lines.extend(["", "## 只适合面试准备", ""])
    lines.extend(render_interview_only(revision["interview_only"]))
    lines.extend(["", "## 不能声称的能力边界", ""])
    lines.extend(render_cannot_claim(revision["cannot_claim"]))
    lines.extend(["", "## 面试模拟问题", ""])
    lines.extend(render_interview_questions(session))
    lines.extend(["", "## source_refs", ""])
    lines.extend(render_source_refs(draft))
    lines.extend(["", "## 证据缺口", ""])
    lines.extend(render_list(draft["evidence_gaps"]))
    if summary:
        lines.extend(["", "## 推荐下一步", ""])
        lines.extend(render_list(summary["recommended_next_steps"]))
    lines.extend(["", "## 安全说明", ""])
    lines.extend(render_list(draft["safety_notes"]))
    if session:
        lines.extend(render_list(session["safety_notes"]))
    lines.extend(["", "## 原始 warnings", ""])
    lines.extend(render_list(build_report_warnings(draft_response, interview_response, summary_response)))
    lines.append("")
    return "\n".join(lines)


def render_interview_questions(session: dict | None) -> list[str]:
    if not session or not session["questions"]:
        return ["- 暂无"]
    lines = []
    for question in session["questions"][:8]:
        lines.append(f"- 问题 {question['question_id']}：{question['question']}")
        lines.append(f"  - 考察意图：{question['intent']}")
        for checkpoint in question["answer_checkpoints"][:4]:
            lines.append(f"  - 回答检查点：{checkpoint}")
        for ref in question.get("source_refs", [])[:3]:
            lines.append(
                "  - source_ref："
                f"{ref.get('type', '')} | {ref.get('source_id', '')} | "
                f"{ref.get('relative_path', '')} | {ref.get('section', '')} | {ref.get('quote', '')}"
            )
        lines.append(f"  - 风险提醒：{question['risk_reminder']}")
    return lines


def build_report_file_name(confirmation: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = slugify(confirmation["title"]) or "job"
    source_job_id = slugify(confirmation["source_job_id"]) or "unknown"
    return f"{timestamp}_{title}_{source_job_id}_match_report.md"


def unique_export_path(file_name: str) -> Path:
    candidate = EXPORT_DIR / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 100):
        next_candidate = EXPORT_DIR / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise ValueError("无法生成唯一报告文件名。")


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80]


def build_report_warnings(draft_response: dict, interview_response: dict, summary_response: dict) -> list[str]:
    warnings: list[str] = []
    warnings.extend(draft_response.get("warnings", []))
    warnings.extend(interview_response.get("warnings", []))
    warnings.extend(summary_response.get("warnings", []))
    warnings.extend(
        [
            "已保存为单独求职分析报告副本，未覆盖真实简历。",
            "该报告目录不加入默认资料分类，避免污染 RAG 索引。",
            "该报告仅用于用户审核，不代表自动投递或生产级求职闭环。",
        ]
    )
    return dedupe(warnings)


def dedupe(values: list[str]) -> list[str]:
    results = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results
