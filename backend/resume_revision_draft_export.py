import re
from datetime import datetime
from pathlib import Path

from .job_match_draft import build_job_match_draft
from .job_match_draft_export import (
    format_current_resume,
    render_cannot_claim,
    render_evidence_required,
    render_interview_only,
    render_list,
)
from .resume_backup import create_current_resume_backup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "private_data" / "resume_revision_drafts"


def export_resume_revision_draft(query: str, confirm_save: bool, note: str = "") -> dict:
    if not confirm_save:
        raise ValueError("保存简历差异草稿前必须显式设置 confirm_save=true。")

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
            "resume_backup": None,
            "warnings": draft_response["warnings"],
        }

    resume_backup = create_current_resume_backup(
        draft_response["current_resume"],
        reason="before_resume_revision_draft_export",
    )
    content = render_resume_revision_content(draft_response, note, resume_backup)
    file_name = build_resume_revision_file_name(draft_response["draft"]["target_confirmation"])
    target_path = unique_export_path(file_name)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")

    return {
        "exported": True,
        "query": query,
        "target_job": draft_response["target_job"],
        "current_resume": draft_response["current_resume"],
        "file_name": target_path.name,
        "relative_path": target_path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": target_path.stat().st_size,
        "content_preview": content[:500],
        "resume_backup": resume_backup,
        "warnings": build_resume_revision_warnings(draft_response),
    }


def list_resume_revision_draft_exports() -> dict:
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
            "Resume revision drafts are private review copies.",
            "Resume revision drafts are not indexed by default and do not overwrite real resumes.",
        ],
    }


def read_resume_revision_draft_export(file_name: str) -> dict:
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


def delete_resume_revision_draft_export(file_name: str) -> dict:
    path = resolve_export_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    path.unlink()
    return {
        "deleted": True,
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Only the selected private resume revision draft was deleted.",
            "No real resume, job description, index, or source document was modified.",
        ],
    }


def resolve_export_file(file_name: str) -> Path:
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Invalid resume revision draft file name.")
    if Path(file_name).suffix.lower() != ".md":
        raise ValueError("Only Markdown resume revision drafts can be managed.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    root = EXPORT_DIR.resolve()
    candidate = (EXPORT_DIR / file_name).resolve()
    if candidate.parent != root:
        raise ValueError("Resume revision draft path is outside the allowed directory.")
    return candidate


def render_resume_revision_content(draft_response: dict, note: str, resume_backup: dict | None = None) -> str:
    draft = draft_response["draft"]
    confirmation = draft["target_confirmation"]
    current_resume = draft_response["current_resume"]
    revision = draft["resume_revision_candidates"]
    lines = [
        f"# 简历差异草稿：{confirmation['title']}",
        "",
        "## 草稿边界",
        "",
        "- 本文件是可审核的简历修改候选副本，不是正式简历。",
        "- 本文件不覆盖真实简历，不会自动覆盖真实简历，不会自动投递，也不会写入岗位资料目录。",
        "- 所有候选表达必须由用户审核，并需要简历、项目资料或其他可信证据支撑。",
        "- 仅适合面试表达或学习计划的内容不得写入正式简历。",
        "- 本导出不调用 LLM、不访问招聘平台、不触发索引。",
        "",
        "## 目标岗位确认",
        "",
        f"- 岗位名称：{confirmation['title']}",
        f"- 公司：{confirmation['company']}",
        f"- 城市：{confirmation['city']}",
        f"- 来源岗位 ID：{confirmation['source_job_id']}",
        "",
        "## 当前简历状态",
        "",
        f"- 当前简历：{format_current_resume(current_resume)}",
        f"- 草稿生成时间：{datetime.now().isoformat(timespec='seconds')}",
    ]
    lines.extend(render_resume_backup_section(resume_backup))
    if note.strip():
        lines.extend(["", "## 用户备注", "", note.strip()])

    lines.extend(["", "## 候选差异摘要", ""])
    lines.extend(
        [
            f"- 可直接考虑写入：{len(revision['can_write_to_resume'])} 条",
            f"- 需补证据后再考虑：{len(revision['requires_evidence_before_resume'])} 条",
            f"- 仅适合面试准备：{len(revision['interview_only'])} 条",
            f"- 不能声称能力：{len(revision['cannot_claim'])} 条",
        ]
    )
    lines.extend(render_auditable_modified_resume_section(current_resume, confirmation, revision))
    lines.extend(["", "## 可写入简历候选", ""])
    if revision["can_write_to_resume"]:
        lines.extend(render_list(revision["can_write_to_resume"]))
    else:
        lines.append("- 暂无可直接写入简历的候选表达；需要先补充当前简历或项目证据。")
    lines.extend(["", "## 需补证据后再考虑", ""])
    lines.extend(render_evidence_required(revision["requires_evidence_before_resume"]))
    lines.extend(["", "## 仅适合面试表达", ""])
    lines.extend(render_interview_only(revision["interview_only"]))
    lines.extend(["", "## 不能写入简历的能力边界", ""])
    lines.extend(render_cannot_claim(revision["cannot_claim"]))
    lines.extend(["", "## 建议人工审核动作", ""])
    lines.extend(
        [
            "- 先逐条核对“需补证据后再考虑”是否能在真实简历或项目资料中找到证据。",
            "- 证据不足的内容只保留为面试准备或学习计划，不写入正式简历。",
            "- 如需写入真实简历，应先生成单独差异版本并人工复核，不能自动覆盖原简历。",
        ]
    )
    lines.extend(["", "## 证据缺口", ""])
    lines.extend(render_list(draft["evidence_gaps"]))
    lines.extend(["", "## 安全说明", ""])
    lines.extend(render_list(draft["safety_notes"]))
    lines.extend(["", "## 原始 warnings", ""])
    lines.extend(render_list(build_resume_revision_warnings(draft_response)))
    lines.append("")
    return "\n".join(lines)


def render_resume_backup_section(resume_backup: dict | None) -> list[str]:
    lines = ["", "## 原简历备份", ""]
    if not resume_backup:
        lines.extend(
            [
                "- 当前未创建原简历备份。",
                "- 请先在简历中心设置当前简历，再生成可审核修改版。",
            ]
        )
        return lines
    lines.extend(
        [
            "- 已在生成草稿前备份当前简历。",
            f"- 原简历：{resume_backup['original_name']}",
            f"- 备份时间：{resume_backup['created_at']}",
            "- 备份仅用于人工恢复，系统不会自动覆盖真实简历。",
        ]
    )
    return lines


def render_auditable_modified_resume_section(
    current_resume: dict | None,
    confirmation: dict,
    revision: dict,
) -> list[str]:
    lines = [
        "",
        "## 可审核修改版简历草稿",
        "",
        "- 本节是基于备份后的当前简历生成的人工审核候选版本，不是正式简历。",
        "- 系统不会自动覆盖真实简历；如需采用，只能由用户人工复制并审核。",
        f"- 目标岗位：{confirmation['title']} / {confirmation['company']} / {confirmation['city']}",
        f"- 当前简历：{format_current_resume(current_resume)}",
        "",
        "### 建议新增或调整的简历表达",
        "",
    ]
    if revision["can_write_to_resume"]:
        lines.extend(render_list(revision["can_write_to_resume"]))
    else:
        lines.append("- 暂无可直接写入的表达；当前草稿不建议新增未经证据支持的能力。")

    lines.extend(["", "### 待补证据后再决定是否写入", ""])
    lines.extend(render_evidence_required(revision["requires_evidence_before_resume"]))
    lines.extend(["", "### 仅保留为面试准备，不写入正式简历", ""])
    lines.extend(render_interview_only(revision["interview_only"]))
    lines.extend(["", "### 不得写入正式简历的内容", ""])
    lines.extend(render_cannot_claim(revision["cannot_claim"]))
    return lines


def build_resume_revision_file_name(confirmation: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = slugify(confirmation["title"]) or "job"
    source_job_id = slugify(confirmation["source_job_id"]) or "unknown"
    return f"{timestamp}_{title}_{source_job_id}_resume_diff.md"


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
    raise ValueError("无法生成唯一简历差异草稿文件名。")


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80]


def build_resume_revision_warnings(draft_response: dict) -> list[str]:
    warnings = list(draft_response["warnings"])
    if draft_response.get("current_resume"):
        warnings.append("已在生成简历差异草稿前创建当前简历备份；备份仅供人工恢复，不会自动覆盖真实简历。")
    else:
        warnings.append("当前未设置简历，未创建原简历备份。")
    warnings.append("已保存为单独简历差异草稿副本，未覆盖真实简历。")
    warnings.append("该草稿目录不加入默认资料分类，避免污染 RAG 索引。")
    warnings.append("该草稿不能自动投递，不能自动写回真实简历。")
    return dedupe(warnings)


def dedupe(values: list[str]) -> list[str]:
    results = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results
