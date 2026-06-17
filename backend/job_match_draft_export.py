import re
from datetime import datetime
from pathlib import Path

from .job_match_draft import build_job_match_draft


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "private_data" / "job_match_drafts"


def export_job_match_draft(query: str, confirm_save: bool, note: str = "") -> dict:
    if not confirm_save:
        raise ValueError("保存可审核草稿前必须显式设置 confirm_save=true。")

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
            "warnings": draft_response["warnings"],
        }

    draft = draft_response["draft"]
    target_job = draft_response["target_job"]
    content = render_export_content(draft_response, note)
    file_name = build_export_file_name(draft["target_confirmation"])
    target_path = unique_export_path(file_name)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    relative_path = target_path.relative_to(PROJECT_ROOT).as_posix()

    return {
        "exported": True,
        "query": query,
        "target_job": target_job,
        "current_resume": draft_response["current_resume"],
        "file_name": target_path.name,
        "relative_path": relative_path,
        "size_bytes": target_path.stat().st_size,
        "content_preview": content[:500],
        "warnings": build_export_warnings(draft_response),
    }


def list_job_match_draft_exports() -> dict:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    drafts = []
    for path in sorted(EXPORT_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        drafts.append(
            {
                "file_name": path.name,
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return {
        "drafts": drafts,
        "count": len(drafts),
        "directory": EXPORT_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Draft exports are private review copies.",
            "Draft exports are not indexed by default and do not overwrite real resumes.",
        ],
    }


def read_job_match_draft_export(file_name: str) -> dict:
    path = resolve_export_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    return {
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "content": content,
    }


def delete_job_match_draft_export(file_name: str) -> dict:
    path = resolve_export_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    path.unlink()
    return {
        "deleted": True,
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Only the selected private draft copy was deleted.",
            "No real resume, job description, index, or source document was modified.",
        ],
    }


def resolve_export_file(file_name: str) -> Path:
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Invalid draft file name.")
    if Path(file_name).suffix.lower() != ".md":
        raise ValueError("Only Markdown draft exports can be managed.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    root = EXPORT_DIR.resolve()
    candidate = (EXPORT_DIR / file_name).resolve()
    if candidate.parent != root:
        raise ValueError("Draft export path is outside the allowed directory.")
    return candidate


def render_export_content(draft_response: dict, note: str) -> str:
    draft = draft_response["draft"]
    confirmation = draft["target_confirmation"]
    current_resume = draft_response["current_resume"]
    lines = [
        f"# 求职分析草稿：{confirmation['title']}",
        "",
        "## 草稿边界",
        "",
        "- 本文件是可审核草稿副本，不是正式简历。",
        "- 本文件不会自动覆盖真实简历。",
        "- 可写入简历的内容必须先由用户审核，并需要简历或项目资料证据。",
        "- 面试表达、学习计划和不能声称的能力不得混入正式简历。",
        "- 本导出不调用 LLM、不访问招聘平台、不触发索引、不自动投递。",
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
        f"- 草稿生成时间：{datetime.now().isoformat(timespec='seconds')}",
    ]
    if note.strip():
        lines.extend(["", "## 用户备注", "", note.strip()])

    lines.extend(["", "## 岗位核心要求", ""])
    lines.extend(render_list(draft["job_core_requirements"]))
    lines.extend(["", "## 岗位核心职责", ""])
    lines.extend(render_list(draft["job_core_responsibilities"]))
    lines.extend(["", "## 当前资料匹配点", ""])
    lines.extend(render_match_points(draft["current_material_match_points"]))
    lines.extend(["", "## 可写入简历候选", ""])
    lines.extend(render_list(draft["resume_revision_candidates"]["can_write_to_resume"]))
    lines.extend(["", "## 需要证据后才能写入简历", ""])
    lines.extend(render_evidence_required(draft["resume_revision_candidates"]["requires_evidence_before_resume"]))
    lines.extend(["", "## 只适合面试准备", ""])
    lines.extend(render_interview_only(draft["resume_revision_candidates"]["interview_only"]))
    lines.extend(["", "## 不能声称的能力边界", ""])
    lines.extend(render_cannot_claim(draft["resume_revision_candidates"]["cannot_claim"]))
    lines.extend(["", "## 面试准备问题", ""])
    lines.extend(render_list(draft["interview_questions"]))
    lines.extend(["", "## 证据缺口", ""])
    lines.extend(render_list(draft["evidence_gaps"]))
    lines.extend(["", "## 安全说明", ""])
    lines.extend(render_list(draft["safety_notes"]))
    lines.extend(["", "## 原始 warnings", ""])
    lines.extend(render_list(draft_response["warnings"]))
    lines.append("")
    return "\n".join(lines)


def build_export_file_name(confirmation: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = slugify(confirmation["title"]) or "job"
    source_job_id = slugify(confirmation["source_job_id"]) or "unknown"
    return f"{timestamp}_{title}_{source_job_id}_match_draft.md"


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
    raise ValueError("无法生成唯一草稿文件名。")


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80]


def format_current_resume(current_resume: dict | None) -> str:
    if not current_resume:
        return "未设置当前简历"
    return f"{current_resume['source']}:{current_resume['name']}"


def render_list(items: list[str]) -> list[str]:
    if not items:
        return ["- 暂无"]
    return [f"- {item}" for item in items]


def render_match_points(items: list[dict]) -> list[str]:
    if not items:
        return ["- 暂无；当前只确认目标岗位，尚未核验简历具体能力。"]
    lines = []
    for item in items:
        lines.append(f"- 匹配点：{item['point']}")
        lines.append(f"  - 证据：{item['evidence']}")
        lines.append(f"  - 边界：{item['boundary']}")
    return lines


def render_evidence_required(items: list[dict]) -> list[str]:
    if not items:
        return ["- 暂无"]
    lines = []
    for item in items:
        lines.append(f"- 候选方向：{item['candidate_direction']}")
        lines.append(f"  - 所需证据：{item['required_evidence']}")
    return lines


def render_interview_only(items: list[dict]) -> list[str]:
    if not items:
        return ["- 暂无"]
    lines = []
    for item in items:
        lines.append(f"- 主题：{item['topic']}")
        lines.append(f"  - 用途：{item['usage']}")
    return lines


def render_cannot_claim(items: list[dict]) -> list[str]:
    if not items:
        return ["- 暂无"]
    lines = []
    for item in items:
        lines.append(f"- 不能声称：{item['claim']}")
        lines.append(f"  - 原因：{item['reason']}")
        lines.append(f"  - 来源要求：{item['source_requirement']}")
    return lines


def build_export_warnings(draft_response: dict) -> list[str]:
    warnings = list(draft_response["warnings"])
    warnings.append("已保存为单独草稿副本，未覆盖真实简历。")
    warnings.append("该草稿目录不加入默认资料分类，避免污染 RAG 索引。")
    return warnings
