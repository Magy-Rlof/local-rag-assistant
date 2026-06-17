import json
import re
from datetime import datetime
from pathlib import Path

from .job_match_report_export import delete_job_match_report_export, export_job_match_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = PROJECT_ROOT / "private_data" / "job_match_report_batches"
MAX_BATCH_QUERIES = 5
VALID_REVIEW_STATUSES = {
    "pending_review": "待审核",
    "accepted": "已采纳",
    "rejected": "已拒绝",
    "needs_evidence": "需补证据",
}


def create_job_match_report_batch_queue(queries: list[str], confirm_queue: bool, note: str = "") -> dict:
    if not confirm_queue:
        raise ValueError("加入批量报告队列前必须显式设置 confirm_queue=true。")

    cleaned_queries = dedupe_queries(queries)
    if len(cleaned_queries) < 2:
        raise ValueError("批量报告队列至少需要 2 个唯一岗位查询。")
    if len(cleaned_queries) > MAX_BATCH_QUERIES:
        raise ValueError(f"单个批量报告队列最多支持 {MAX_BATCH_QUERIES} 个岗位查询。")

    generated_reports: list[dict] = []
    failures: list[dict] = []
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    for index, query in enumerate(cleaned_queries, start=1):
        try:
            report = export_job_match_report(
                query,
                True,
                build_report_note(note, batch_id, index, len(cleaned_queries)),
            )
        except ValueError as exc:
            failures.append({"query": query, "error": str(exc)})
            continue
        if not report.get("exported"):
            failures.append({"query": query, "error": "目标岗位未命中，未生成报告。"})
            continue
        generated_reports.append(
            {
                "query": query,
                "file_name": report["file_name"],
                "relative_path": report["relative_path"],
                "size_bytes": report["size_bytes"],
                "target_job": report["target_job"],
            }
        )

    if not generated_reports:
        raise ValueError("批量报告队列未生成任何报告，请检查岗位查询是否已入库。")

    content = render_batch_content(batch_id, cleaned_queries, generated_reports, failures, note)
    file_name = build_batch_file_name(batch_id, generated_reports)
    target_path = unique_batch_path(file_name)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    metadata = write_batch_metadata(
        target_path,
        {
            "batch_id": batch_id,
            "queries": cleaned_queries,
            "generated_reports": generated_reports,
            "failures": failures,
            "review_status": "pending_review",
            "review_note": "",
        },
    )

    return {
        "queued": True,
        "batch_id": batch_id,
        "file_name": target_path.name,
        "relative_path": target_path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": target_path.stat().st_size,
        "query_count": len(cleaned_queries),
        "created_count": len(generated_reports),
        "failed_count": len(failures),
        "generated_reports": generated_reports,
        "failures": failures,
        "content_preview": content[:500],
        **review_fields(metadata),
        "warnings": build_batch_warnings(),
    }


def list_job_match_report_batch_queues() -> dict:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batches = []
    for path in sorted(BATCH_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        metadata = read_batch_metadata(path)
        batches.append(
            {
                "batch_id": metadata["batch_id"],
                "file_name": path.name,
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "query_count": len(metadata["queries"]),
                "created_count": len(metadata["generated_reports"]),
                "failed_count": len(metadata["failures"]),
                **review_fields(metadata),
            }
        )
    return {
        "batches": batches,
        "count": len(batches),
        "directory": BATCH_DIR.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Batch report queues are private review manifests.",
            "Batch manifests are not indexed by default and do not overwrite real resumes.",
            "Generated single-job reports remain separately reviewable and are not deleted when the batch manifest is deleted.",
        ],
    }


def read_job_match_report_batch_queue(file_name: str) -> dict:
    path = resolve_batch_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    metadata = read_batch_metadata(path)
    return {
        "batch_id": metadata["batch_id"],
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "query_count": len(metadata["queries"]),
        "created_count": len(metadata["generated_reports"]),
        "failed_count": len(metadata["failures"]),
        "queries": metadata["queries"],
        "generated_reports": metadata["generated_reports"],
        "failures": metadata["failures"],
        **review_fields(metadata),
        "content": content,
    }


def update_job_match_report_batch_review(file_name: str, review_status: str, review_note: str = "") -> dict:
    path = resolve_batch_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid batch report review status.")
    note = (review_note or "").strip()
    if len(note) > 1000:
        raise ValueError("Review note is too long.")
    metadata = read_batch_metadata(path)
    metadata["review_status"] = review_status
    metadata["review_note"] = note
    write_batch_metadata(path, metadata)
    result = read_job_match_report_batch_queue(file_name)
    result["warnings"] = [
        "Only the selected private batch report metadata was updated.",
        "No real resume, job description, index, generated report content, or source document was modified.",
    ]
    return result


def delete_job_match_report_batch_queue(file_name: str) -> dict:
    path = resolve_batch_file(file_name)
    if not path.exists():
        raise FileNotFoundError(file_name)
    path.unlink()
    metadata_path = batch_metadata_path(path)
    if metadata_path.exists():
        metadata_path.unlink()
    return {
        "deleted": True,
        "file_name": path.name,
        "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "warnings": [
            "Only the selected private batch report manifest was deleted.",
            "Generated single-job reports were not deleted by this endpoint.",
            "No real resume, job description, index, or source document was modified.",
        ],
    }


def delete_generated_reports_for_selftest(file_names: list[str]) -> list[dict]:
    results = []
    for file_name in file_names:
        try:
            results.append(delete_job_match_report_export(file_name))
        except FileNotFoundError:
            continue
    return results


def resolve_batch_file(file_name: str) -> Path:
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Invalid batch report file name.")
    if Path(file_name).suffix.lower() != ".md":
        raise ValueError("Only Markdown batch report manifests can be managed.")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    root = BATCH_DIR.resolve()
    candidate = (BATCH_DIR / file_name).resolve()
    if candidate.parent != root:
        raise ValueError("Batch report path is outside the allowed directory.")
    return candidate


def render_batch_content(
    batch_id: str,
    queries: list[str],
    generated_reports: list[dict],
    failures: list[dict],
    note: str,
) -> str:
    lines = [
        "# 批量求职分析报告队列",
        "",
        "## 队列边界",
        "",
        "- 本文件是本地私有批量报告清单，不是正式简历。",
        "- 本文件不覆盖真实简历，不自动投递，也不会写入岗位资料目录。",
        "- 本文件只记录本次批量生成结果；单岗位报告仍需逐份人工审核。",
        "- 本批量队列不访问招聘平台、不触发索引、不调用 LLM。",
        "",
        "## 批次信息",
        "",
        f"- 批次 ID：{batch_id}",
        f"- 查询数量：{len(queries)}",
        f"- 已生成报告：{len(generated_reports)}",
        f"- 失败数量：{len(failures)}",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
    ]
    if note.strip():
        lines.extend(["", "## 批次备注", "", note.strip()])
    lines.extend(["", "## 查询列表", ""])
    for query in queries:
        lines.append(f"- {query}")
    lines.extend(["", "## 已生成单岗位报告", ""])
    if generated_reports:
        for index, report in enumerate(generated_reports, start=1):
            target = report.get("target_job") or {}
            lines.extend(
                [
                    f"### {index}. {target.get('title') or '未命名岗位'}",
                    "",
                    f"- 查询：{report['query']}",
                    f"- 公司：{target.get('company') or '未提供'}",
                    f"- 城市：{target.get('city') or '未提供'}",
                    f"- 来源岗位 ID：{target.get('source_job_id') or ''}",
                    f"- 报告文件：{report['file_name']}",
                    f"- 报告路径：{report['relative_path']}",
                    "",
                ]
            )
    else:
        lines.append("- 暂无")
    lines.extend(["## 失败项", ""])
    if failures:
        for failure in failures:
            lines.append(f"- {failure['query']}：{failure['error']}")
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 审核动作", ""])
    lines.extend(
        [
            "- 逐份打开单岗位报告，核对目标岗位、当前资料匹配点、证据缺口和能力边界。",
            "- 证据不足的批次应标记为“需补证据”或“已拒绝”。",
            "- 如需采用报告内容，只能由用户人工复制候选表达，不允许自动写回真实简历。",
            "",
        ]
    )
    return "\n".join(lines)


def build_report_note(note: str, batch_id: str, index: int, total: int) -> str:
    lines = [
        f"批量报告队列：{batch_id}",
        f"批量序号：{index}/{total}",
        "本报告由批量队列触发生成，仍需单独审核；不自动投递，不覆盖真实简历。",
    ]
    if note.strip():
        lines.extend(["", note.strip()])
    return "\n".join(lines)


def build_batch_file_name(batch_id: str, generated_reports: list[dict]) -> str:
    first_target = generated_reports[0].get("target_job") or {}
    title = slugify(first_target.get("title", "")) or "job"
    return f"{batch_id}_{title}_batch_report_queue.md"


def unique_batch_path(file_name: str) -> Path:
    candidate = BATCH_DIR / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 100):
        next_candidate = BATCH_DIR / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise ValueError("无法生成唯一批量报告队列文件名。")


def batch_metadata_path(batch_path: Path) -> Path:
    return batch_path.with_suffix(".batch.json")


def default_batch_metadata(batch_path: Path) -> dict:
    return {
        "batch_id": batch_path.stem,
        "queries": [],
        "generated_reports": [],
        "failures": [],
        "review_status": "pending_review",
        "review_note": "",
        "review_updated_at": "",
    }


def read_batch_metadata(batch_path: Path) -> dict:
    metadata_path = batch_metadata_path(batch_path)
    if not metadata_path.exists():
        return default_batch_metadata(batch_path)
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_batch_metadata(batch_path)
    status = payload.get("review_status", "pending_review")
    if status not in VALID_REVIEW_STATUSES:
        status = "pending_review"
    return {
        "batch_id": str(payload.get("batch_id", batch_path.stem)),
        "queries": [str(item) for item in payload.get("queries", [])],
        "generated_reports": list(payload.get("generated_reports", [])),
        "failures": list(payload.get("failures", [])),
        "review_status": status,
        "review_note": str(payload.get("review_note", ""))[:1000],
        "review_updated_at": str(payload.get("review_updated_at", "")),
    }


def write_batch_metadata(batch_path: Path, metadata: dict) -> dict:
    status = metadata.get("review_status", "pending_review")
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError("Invalid batch report review status.")
    next_metadata = {
        "batch_id": metadata.get("batch_id", batch_path.stem),
        "queries": metadata.get("queries", []),
        "generated_reports": metadata.get("generated_reports", []),
        "failures": metadata.get("failures", []),
        "review_status": status,
        "review_label": VALID_REVIEW_STATUSES[status],
        "review_note": metadata.get("review_note", ""),
        "review_updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    batch_metadata_path(batch_path).write_text(
        json.dumps(next_metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return next_metadata


def review_fields(metadata: dict) -> dict:
    status = metadata.get("review_status", "pending_review")
    if status not in VALID_REVIEW_STATUSES:
        status = "pending_review"
    return {
        "review_status": status,
        "review_label": VALID_REVIEW_STATUSES[status],
        "review_note": str(metadata.get("review_note", ""))[:1000],
        "review_updated_at": str(metadata.get("review_updated_at", "")),
    }


def dedupe_queries(queries: list[str]) -> list[str]:
    results = []
    for query in queries or []:
        value = str(query).strip()
        if value and value not in results:
            results.append(value)
    return results


def build_batch_warnings() -> list[str]:
    return [
        "已生成本地私有批量报告队列，未覆盖真实简历。",
        "批量队列目录不加入默认资料分类，避免污染 RAG 索引。",
        "该批量队列不能自动投递，不能自动写回真实简历。",
        "删除批量队列清单不会自动删除已生成的单岗位报告。",
    ]


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80]
