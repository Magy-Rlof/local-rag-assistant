import json
import re
from datetime import datetime
from pathlib import Path

from .resume_revision_draft_export import read_resume_revision_draft_export


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = PROJECT_ROOT / "private_data" / "resume_write_reviews"
VALID_REVIEW_STATUSES = {
    "pending_review": "待审核",
    "approved_for_manual_copy": "人工采纳候选",
    "rejected": "已拒绝",
    "needs_evidence": "需补证据",
}


def create_resume_write_review_item(diff_file_name: str, confirm_queue: bool, note: str = "") -> dict:
    if not confirm_queue:
        raise ValueError("加入写回前审核队列前必须显式设置 confirm_queue=true。")

    draft = read_resume_revision_draft_export(diff_file_name)
    content = render_review_content(draft, note)
    file_name = build_review_file_name(diff_file_name)
    target_path = unique_queue_path(file_name)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    review = write_review_metadata(target_path, "pending_review", "")

    return {
        "queued": True,
        "source_diff_file_name": draft["file_name"],
        "source_diff_relative_path": draft["relative_path"],
        "file_name": target_path.name,
        "relative_path": target_path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": target_path.stat().st_size,
        "content_preview": content[:500],
        **review,
        "warnings": build_queue_warnings(),
    }


def list_resume_write_review_items() -> dict:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(QUEUE_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        review = read_review_metadata(path)
        source = read_source_metadata(path)
        items.append(
            {
                "file_name": path.name,
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                **review,
                **source,
            }
        )
    return {
        "items": items,
        "count": len(items),
        "directory": QUEUE_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Resume write review items are private review copies.",
            "Review items are not indexed by default and do not overwrite real resumes.",
            "Approved items still require manual copy; no automatic resume write-back is available.",
        ],
    }


def read_resume_write_review_item(file_name: str) -> dict:
    path = resolve_queue_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    review = read_review_metadata(path)
    source = read_source_metadata(path)
    return {
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        **review,
        **source,
        "content": content,
    }


def update_resume_write_review_item(file_name: str, review_status: str, review_note: str = "") -> dict:
    path = resolve_queue_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid resume write review status.")
    note = (review_note or "").strip()
    if len(note) > 1000:
        raise ValueError("Review note is too long.")
    write_review_metadata(path, review_status, note)
    result = read_resume_write_review_item(file_name)
    result["warnings"] = [
        "Only the selected private resume write review metadata was updated.",
        "No real resume, job description, index, or source document was modified.",
        "Approved status means manual copy candidate only; no automatic resume write-back was performed.",
    ]
    return result


def delete_resume_write_review_item(file_name: str) -> dict:
    path = resolve_queue_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    path.unlink()
    metadata_path = review_metadata_path(path)
    if metadata_path.exists():
        metadata_path.unlink()
    return {
        "deleted": True,
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Only the selected private resume write review item was deleted.",
            "No real resume, job description, index, or source document was modified.",
        ],
    }


def resolve_queue_file(file_name: str) -> Path:
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Invalid resume write review file name.")
    if Path(file_name).suffix.lower() != ".md":
        raise ValueError("Only Markdown resume write review items can be managed.")

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    root = QUEUE_DIR.resolve()
    candidate = (QUEUE_DIR / file_name).resolve()
    if candidate.parent != root:
        raise ValueError("Resume write review path is outside the allowed directory.")
    return candidate


def render_review_content(draft: dict, note: str) -> str:
    lines = [
        "# 简历写回前审核",
        "",
        "## 审核边界",
        "",
        "- 本文件是写回真实简历前的本地私有审核项，不是正式简历。",
        "- 本文件不覆盖真实简历，不提供自动写回，不会自动投递，也不会写入岗位资料目录。",
        "- 审核通过只表示可人工复制候选内容；系统不会自动修改真实简历。",
        "- 本审核项不调用 LLM、不访问招聘平台、不触发索引。",
        "",
        "## 来源差异草稿",
        "",
        f"- 来源文件：{draft['file_name']}",
        f"- 来源路径：{draft['relative_path']}",
        f"- 入队时间：{datetime.now().isoformat(timespec='seconds')}",
    ]
    if note.strip():
        lines.extend(["", "## 入队备注", "", note.strip()])
    lines.extend(
        [
            "",
            "## 审核动作",
            "",
            "- 逐条核对候选表达是否有真实简历、项目资料或其他可信证据。",
            "- 证据不足的内容应标记为“需补证据”或“已拒绝”。",
            "- 如需采用，只能由用户人工复制到真实简历版本中。",
            "",
            "## 差异草稿正文",
            "",
            draft["content"].strip(),
            "",
        ]
    )
    return "\n".join(lines)


def build_review_file_name(diff_file_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(diff_file_name).stem
    stem = re.sub(r"_resume_diff$", "", stem)
    stem = slugify(stem) or "resume_diff"
    return f"{timestamp}_{stem}_write_review.md"


def unique_queue_path(file_name: str) -> Path:
    candidate = QUEUE_DIR / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 100):
        next_candidate = QUEUE_DIR / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise ValueError("无法生成唯一简历写回审核文件名。")


def review_metadata_path(item_path: Path) -> Path:
    return item_path.with_suffix(".review.json")


def default_review_metadata() -> dict:
    return {
        "review_status": "pending_review",
        "review_label": VALID_REVIEW_STATUSES["pending_review"],
        "review_note": "",
        "review_updated_at": "",
    }


def read_review_metadata(item_path: Path) -> dict:
    metadata_path = review_metadata_path(item_path)
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


def write_review_metadata(item_path: Path, review_status: str, review_note: str) -> dict:
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid resume write review status.")
    metadata = {
        "review_status": review_status,
        "review_label": VALID_REVIEW_STATUSES[review_status],
        "review_note": review_note,
        "review_updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    review_metadata_path(item_path).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def read_source_metadata(item_path: Path) -> dict:
    try:
        content = item_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"source_diff_file_name": "", "source_diff_relative_path": ""}
    file_match = re.search(r"^- 来源文件：(.+)$", content, flags=re.MULTILINE)
    path_match = re.search(r"^- 来源路径：(.+)$", content, flags=re.MULTILINE)
    return {
        "source_diff_file_name": file_match.group(1).strip() if file_match else "",
        "source_diff_relative_path": path_match.group(1).strip() if path_match else "",
    }


def build_queue_warnings() -> list[str]:
    return [
        "已加入本地私有写回前审核队列，未覆盖真实简历。",
        "审核项目录不加入默认资料分类，避免污染 RAG 索引。",
        "该审核项不能自动投递，不能自动写回真实简历。",
    ]


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:100]
