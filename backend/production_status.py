import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
LOOP_DIR = WORKSPACE_ROOT / "workspace_docs" / "n8n" / "loop" / "runs"
JOBONLINE_OUTPUT_DIR = WORKSPACE_ROOT / "tools" / "jobonline-poc" / "output"
PRIVATE_DATA_DIR = PROJECT_ROOT / "private_data"

PENDING_REVIEW_STATUSES = {"pending_review", "needs_evidence"}


def get_production_workbench_status() -> dict:
    runs = list_recent_runs()
    latest_run = runs[0] if runs else None
    source = build_source_summary()
    write = build_write_summary(source)
    review = build_review_summary()
    index = build_index_summary(runs)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "latest_run": latest_run,
        "runs": runs[:6],
        "source": source,
        "write": write,
        "review": review,
        "index": index,
        "boundaries": [
            "只读状态页，不执行写入、覆盖、删除、索引或投递。",
            "不访问外部招聘平台，不绕过登录、验证码、反爬或平台限制。",
            "不提交敏感数据，不自动覆盖真实简历。",
        ],
        "warnings": build_warnings(source, index),
    }


def list_recent_runs() -> list[dict]:
    if not LOOP_DIR.exists():
        return []
    runs = []
    for path in LOOP_DIR.glob("LOOP-*-production-run*.md"):
        parsed = parse_loop_file(path)
        if parsed:
            runs.append(parsed)
    return sorted(runs, key=lambda item: (item["run_number"], item["modified_at"]), reverse=True)


def parse_loop_file(path: Path) -> dict | None:
    match = re.search(r"production-run(\d+)", path.name)
    if not match:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    status_match = re.search(r"^- 当前状态：(.+)$", text, flags=re.MULTILINE)
    loop_match = re.search(r"^- LOOP 编号：(.+)$", text, flags=re.MULTILINE)
    theme_match = re.search(r"^- 本轮主题：(.+)$", text, flags=re.MULTILINE)
    return {
        "run_number": int(match.group(1)),
        "loop_id": clean_text(loop_match.group(1) if loop_match else path.stem),
        "title": clean_text(title_match.group(1) if title_match else path.stem),
        "status": clean_text(status_match.group(1) if status_match else "未知"),
        "theme": clean_text(theme_match.group(1) if theme_match else ""),
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "relative_path": path.relative_to(WORKSPACE_ROOT).as_posix(),
    }


def build_source_summary() -> dict:
    audit = read_latest_source_audit()
    if not audit:
        return {
            "status": "missing",
            "source_id": "",
            "source_name": "",
            "gate_decision": "unknown",
            "gate_allowed": False,
            "channel": "",
            "collected_count": 0,
            "schema_valid": False,
            "schema_error_count": 0,
            "evidence_file": "",
        }
    compliance_gate = as_dict(audit.get("compliance_gate"))
    source_snapshot = as_dict(compliance_gate.get("source_snapshot"))
    feeds = [as_dict(item) for item in audit.get("feeds", []) if isinstance(item, dict)]
    extraction = as_dict(audit.get("extraction"))
    schema_validation = as_dict(audit.get("schema_validation"))
    channels = sorted({str(item.get("channel", "")).strip() for item in feeds if item.get("channel")})
    evidence_path = audit.get("_evidence_path", "")
    return {
        "status": str(audit.get("status", "unknown")),
        "source_id": str(audit.get("source_id") or compliance_gate.get("source_id") or ""),
        "source_name": str(source_snapshot.get("display_name") or ""),
        "gate_decision": str(compliance_gate.get("decision", "unknown")),
        "gate_allowed": bool(compliance_gate.get("allowed", False)),
        "channel": "、".join(channels) if channels else str(audit.get("action", "")),
        "collected_count": int_value(extraction.get("unique_count", extraction.get("extracted_count", 0))),
        "schema_valid": bool(schema_validation.get("valid", False)),
        "schema_error_count": int_value(schema_validation.get("error_count", 0)),
        "evidence_file": evidence_path,
    }


def read_latest_source_audit() -> dict | None:
    if not JOBONLINE_OUTPUT_DIR.exists():
        return None
    candidates = sorted(
        (path for path in JOBONLINE_OUTPUT_DIR.rglob("*.json") if path.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in candidates[:300]:
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        if "compliance_gate" not in payload and "source_audit" not in payload:
            continue
        payload["_evidence_path"] = path.relative_to(WORKSPACE_ROOT).as_posix()
        return payload
    return None


def build_write_summary(source: dict) -> dict:
    audit = read_json(WORKSPACE_ROOT / source["evidence_file"]) if source.get("evidence_file") else {}
    write = as_dict(audit.get("write")) if isinstance(audit, dict) else {}
    extraction = as_dict(audit.get("extraction")) if isinstance(audit, dict) else {}
    schema_validation = as_dict(audit.get("schema_validation")) if isinstance(audit, dict) else {}
    return {
        "written_count": int_value(write.get("written_count", 0)),
        "skipped_count": int_value(extraction.get("duplicate_count", 0)),
        "failed_count": int_value(schema_validation.get("error_count", 0)),
        "job_file_count": count_markdown_files(PRIVATE_DATA_DIR / "job_descriptions"),
        "out_dir": "private_data/job_descriptions",
    }


def build_review_summary() -> dict:
    reports = count_review_directory(PRIVATE_DATA_DIR / "job_match_reports", ".review.json")
    batches = count_review_directory(PRIVATE_DATA_DIR / "job_match_report_batches", ".batch.json")
    resume_reviews = count_review_directory(PRIVATE_DATA_DIR / "resume_write_reviews", ".review.json")
    resume_drafts = count_markdown_files(PRIVATE_DATA_DIR / "resume_revision_drafts")
    job_drafts = count_markdown_files(PRIVATE_DATA_DIR / "job_match_drafts")
    pending_count = reports["pending_count"] + batches["pending_count"] + resume_reviews["pending_count"]
    return {
        "pending_count": pending_count,
        "job_report_count": reports["total_count"],
        "batch_queue_count": batches["total_count"],
        "resume_write_review_count": resume_reviews["total_count"],
        "resume_draft_count": resume_drafts,
        "job_draft_count": job_drafts,
    }


def build_index_summary(runs: list[dict]) -> dict:
    status_file = find_latest_file("index_job_status.json")
    queue_file = find_latest_file("pending_index_queue.json")
    status_payload = read_json(status_file) if status_file else {}
    queue_payload = read_json(queue_file) if queue_file else {}
    run6_text = read_latest_run_text(6)
    if isinstance(status_payload, dict) and status_payload:
        indexed_count = int_value(status_payload.get("indexed_count", 0))
        skipped_count = int_value(status_payload.get("skipped_unchanged_count", 0))
        failed_count = int_value(status_payload.get("failed_count", 0))
        changed_count = len(status_payload.get("changed_sources", []) or [])
        status = str(status_payload.get("status", "unknown"))
        evidence_file = status_file.relative_to(WORKSPACE_ROOT).as_posix() if status_file else ""
    else:
        indexed_count = int_from_text(run6_text, r"first_indexed_count = (\d+)")
        skipped_count = int_from_text(run6_text, r"second_skipped_unchanged_count = (\d+)")
        failed_count = 0
        changed_count = int_from_text(run6_text, r"first_changed_sources_count = (\d+)")
        status = "verified_by_run6" if any(item["run_number"] >= 6 and item["status"] == "已完成" for item in runs) else "unknown"
        evidence_file = latest_run_path(6)
    pending_count = int_value(queue_payload.get("count", 0)) if isinstance(queue_payload, dict) else 0
    return {
        "status": status,
        "indexed_count": indexed_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "changed_source_count": changed_count,
        "pending_count": pending_count,
        "evidence_file": evidence_file,
    }


def build_warnings(source: dict, index: dict) -> list[str]:
    warnings = []
    if not source.get("gate_allowed"):
        warnings.append("未找到已放行的来源门禁证据。")
    if index.get("status") == "unknown":
        warnings.append("未找到可展示的索引任务状态证据。")
    return warnings


def count_markdown_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.glob("*.md") if path.is_file())


def count_review_directory(directory: Path, metadata_suffix: str) -> dict:
    total = 0
    pending = 0
    if not directory.exists():
        return {"total_count": 0, "pending_count": 0}
    for path in directory.glob("*.md"):
        if not path.is_file():
            continue
        total += 1
        metadata = read_json(path.with_suffix(metadata_suffix))
        status = "pending_review"
        if isinstance(metadata, dict):
            status = str(metadata.get("review_status", "pending_review"))
        if status in PENDING_REVIEW_STATUSES:
            pending += 1
    return {"total_count": total, "pending_count": pending}


def find_latest_file(name: str) -> Path | None:
    if not JOBONLINE_OUTPUT_DIR.exists():
        return None
    matches = [path for path in JOBONLINE_OUTPUT_DIR.rglob(name) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def read_latest_run_text(run_number: int) -> str:
    path = latest_loop_path(run_number)
    if not path:
        return ""
    return path.read_text(encoding="utf-8")


def latest_run_path(run_number: int) -> str:
    path = latest_loop_path(run_number)
    return path.relative_to(WORKSPACE_ROOT).as_posix() if path else ""


def latest_loop_path(run_number: int) -> Path | None:
    if not LOOP_DIR.exists():
        return None
    matches = list(LOOP_DIR.glob(f"LOOP-*-production-run{run_number}*.md"))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def read_json(path: Path) -> Any:
    if not path or not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def int_from_text(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def clean_text(value: str) -> str:
    return value.strip().strip("`")
