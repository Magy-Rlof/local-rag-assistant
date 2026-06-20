import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .document_service import PROJECT_ROOT, resolve_document_path


BACKUP_DIR = PROJECT_ROOT / "private_data" / "resume_backups"


def create_current_resume_backup(current_resume: dict | None, reason: str) -> dict | None:
    if not current_resume:
        return None

    source_path = resolve_document_path(
        "resumes",
        current_resume["name"],
        source=current_resume.get("source", "private"),
    )
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(current_resume["name"])

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().isoformat(timespec="seconds")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = unique_backup_name(f"{timestamp}_{slugify(source_path.stem)}{source_path.suffix}.bak")
    backup_path = BACKUP_DIR / backup_name
    shutil.copy2(source_path, backup_path)

    payload = {
        "created": True,
        "created_at": created_at,
        "reason": reason,
        "original_name": current_resume["name"],
        "original_source": current_resume.get("source", "private"),
        "original_relative_path": source_path.relative_to(PROJECT_ROOT).as_posix(),
        "original_size_bytes": source_path.stat().st_size,
        "backup_file_name": backup_path.name,
        "backup_relative_path": backup_path.relative_to(PROJECT_ROOT).as_posix(),
        "backup_size_bytes": backup_path.stat().st_size,
        "sha256": sha256_file(backup_path),
        "not_indexed_by_default": True,
        "restore_note": "Manual restore only. This backup is a .bak copy and is not indexed by local-rag-assistant.",
    }
    metadata_path = backup_path.with_suffix(backup_path.suffix + ".json")
    payload["metadata_relative_path"] = metadata_path.relative_to(PROJECT_ROOT).as_posix()
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def unique_backup_name(file_name: str) -> str:
    candidate = BACKUP_DIR / file_name
    if not candidate.exists():
        return file_name
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 100):
        next_name = f"{stem}_{index}{suffix}"
        if not (BACKUP_DIR / next_name).exists():
            return next_name
    raise ValueError("Unable to generate a unique resume backup file name.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:100] or "resume"
