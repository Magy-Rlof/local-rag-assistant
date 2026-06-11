import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PRIVATE_DATA_DIR = PROJECT_ROOT / "private_data"
SUPPORTED_SUFFIXES = {".md", ".docx", ".pdf"}
EDITABLE_SUFFIXES = {".md"}


@dataclass(frozen=True)
class CategoryConfig:
    key: str
    label: str
    private_directory: Path
    public_directory: Path | None = None
    include_private_root: bool = False


CATEGORIES = {
    "resumes": CategoryConfig("resumes", "简历库", PRIVATE_DATA_DIR / "resumes", include_private_root=True),
    "jobs": CategoryConfig("jobs", "岗位资料", PRIVATE_DATA_DIR / "job_descriptions", DATA_DIR / "job_descriptions"),
    "projects": CategoryConfig("projects", "项目资料", PRIVATE_DATA_DIR / "projects", DATA_DIR / "projects"),
    "notes": CategoryConfig("notes", "学习笔记", PRIVATE_DATA_DIR / "learning_notes", DATA_DIR / "learning_notes"),
}


def get_category(category: str) -> CategoryConfig:
    if category not in CATEGORIES:
        raise ValueError(f"不支持的资料分类：{category}")
    return CATEGORIES[category]


def ensure_category_dirs() -> None:
    for config in CATEGORIES.values():
        config.private_directory.mkdir(parents=True, exist_ok=True)


def clean_file_name(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件格式：{suffix}")

    stem = Path(file_name).stem.strip() or "document"
    safe_stem = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1f]+', "_", stem)
    safe_stem = re.sub(r"\s+", "_", safe_stem).strip("._")
    if not safe_stem:
        safe_stem = "document"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{safe_stem}{suffix}"


def resolve_document_path(category: str, file_name: str, source: str = "private") -> Path:
    config = get_category(category)
    safe_name = Path(file_name).name

    if source == "private":
        candidate = (config.private_directory / safe_name).resolve()
        allowed_dirs = [config.private_directory.resolve()]
        if config.include_private_root:
            legacy_candidate = (PRIVATE_DATA_DIR / safe_name).resolve()
            if legacy_candidate.exists():
                candidate = legacy_candidate
            allowed_dirs.append(PRIVATE_DATA_DIR.resolve())
    elif source == "public":
        if config.public_directory is None:
            raise ValueError("当前分类没有公开示例资料。")
        candidate = (config.public_directory / safe_name).resolve()
        allowed_dirs = [config.public_directory.resolve()]
    else:
        raise ValueError("不支持的资料来源。")

    if candidate.parent not in allowed_dirs:
        raise ValueError("文件路径不合法。")
    return candidate


def list_documents(category: str) -> list[dict]:
    config = get_category(category)
    config.private_directory.mkdir(parents=True, exist_ok=True)
    documents = []
    documents.extend(list_documents_from_directory(category, config.private_directory, source="private"))

    if config.include_private_root and PRIVATE_DATA_DIR.exists():
        legacy_documents = []
        for path in sorted(PRIVATE_DATA_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                legacy_documents.append(build_document_info(category, path, source="private", deletable=True))
        existing_names = {document["name"] for document in documents}
        documents.extend(document for document in legacy_documents if document["name"] not in existing_names)

    if config.public_directory and config.public_directory.exists():
        documents.extend(list_documents_from_directory(category, config.public_directory, source="public"))
    return documents


def list_documents_from_directory(category: str, directory: Path, source: str) -> list[dict]:
    documents = []
    for path in sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            documents.append(build_document_info(category, path, source=source, deletable=source == "private"))
    return documents


def build_document_info(category: str, path: Path, source: str, deletable: bool) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "category": category,
        "source": source,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "editable": source == "private" and path.suffix.lower() in EDITABLE_SUFFIXES,
        "deletable": deletable,
    }


def save_upload(category: str, file_name: str, file_object: BinaryIO) -> dict:
    config = get_category(category)
    config.private_directory.mkdir(parents=True, exist_ok=True)
    target_path = config.private_directory / clean_file_name(file_name)
    with target_path.open("wb") as target_file:
        target_file.write(file_object.read())
    return list_document(category, target_path.name, source="private")


def list_document(category: str, file_name: str, source: str = "private") -> dict:
    path = resolve_document_path(category, file_name, source=source)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(file_name)
    return build_document_info(category, path, source=source, deletable=source == "private")


def read_markdown_document(category: str, file_name: str, source: str = "private") -> str:
    path = resolve_document_path(category, file_name, source=source)
    if path.suffix.lower() not in EDITABLE_SUFFIXES:
        raise ValueError("当前只支持查看 Markdown 文档内容。")
    return path.read_text(encoding="utf-8")


def write_markdown_document(category: str, file_name: str, content: str) -> dict:
    path = resolve_document_path(category, file_name, source="private")
    if path.suffix.lower() not in EDITABLE_SUFFIXES:
        raise ValueError("当前只支持在线编辑 Markdown 文档。")
    path.write_text(content, encoding="utf-8")
    return list_document(category, file_name, source="private")


def delete_document(category: str, file_name: str) -> None:
    path = resolve_document_path(category, file_name, source="private")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(file_name)
    path.unlink()
