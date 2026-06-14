import re
import time
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PRIVATE_DATA_DIR = PROJECT_ROOT / "private_data"
CURRENT_RESUME_STATE_PATH = PRIVATE_DATA_DIR / "current_resume.json"
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
    "resumes": CategoryConfig("resumes", "简历库", PRIVATE_DATA_DIR / "resumes", DATA_DIR / "resume_samples", include_private_root=True),
    "industries": CategoryConfig("industries", "行业资料", PRIVATE_DATA_DIR / "industries", DATA_DIR / "industries"),
    "jobs": CategoryConfig("jobs", "岗位资料", PRIVATE_DATA_DIR / "job_descriptions", DATA_DIR / "job_descriptions"),
    "projects": CategoryConfig("projects", "项目资料", PRIVATE_DATA_DIR / "projects", DATA_DIR / "projects"),
}


def get_category(category: str) -> CategoryConfig:
    if category not in CATEGORIES:
        raise ValueError(f"不支持的资料分类：{category}")
    return CATEGORIES[category]


def ensure_category_dirs() -> None:
    for config in CATEGORIES.values():
        config.private_directory.mkdir(parents=True, exist_ok=True)
        if config.public_directory:
            config.public_directory.mkdir(parents=True, exist_ok=True)


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
            documents.append(build_document_info(category, path, source=source, deletable=True))
    return documents


def build_document_info(category: str, path: Path, source: str, deletable: bool) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "category": category,
        "source": source,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "editable": path.suffix.lower() in EDITABLE_SUFFIXES,
        "deletable": deletable,
    }


def save_upload(category: str, file_name: str, file_object: BinaryIO, source: str = "private") -> dict:
    config = get_category(category)
    if source == "private":
        target_directory = config.private_directory
    elif source == "public":
        if config.public_directory is None:
            raise ValueError("当前分类没有公开示例资料。")
        target_directory = config.public_directory
    else:
        raise ValueError("不支持的资料来源。")

    target_directory.mkdir(parents=True, exist_ok=True)
    target_path = target_directory / clean_file_name(file_name)
    with target_path.open("wb") as target_file:
        target_file.write(file_object.read())
    return list_document(category, target_path.name, source=source)


def list_document(category: str, file_name: str, source: str = "private") -> dict:
    path = resolve_document_path(category, file_name, source=source)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(file_name)
    return build_document_info(category, path, source=source, deletable=True)


def read_markdown_document(category: str, file_name: str, source: str = "private") -> str:
    path = resolve_document_path(category, file_name, source=source)
    if path.suffix.lower() not in EDITABLE_SUFFIXES:
        raise ValueError("当前只支持查看 Markdown 文档内容。")
    return path.read_text(encoding="utf-8")


def write_markdown_document(category: str, file_name: str, content: str, source: str = "private") -> dict:
    path = resolve_document_path(category, file_name, source=source)
    if path.suffix.lower() not in EDITABLE_SUFFIXES:
        raise ValueError("当前只支持在线编辑 Markdown 文档。")
    path.write_text(content, encoding="utf-8")
    return list_document(category, file_name, source=source)


def delete_document(category: str, file_name: str, source: str = "private") -> None:
    path = resolve_document_path(category, file_name, source=source)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(file_name)
    path.unlink()
    current_resume = get_current_resume()
    if category == "resumes" and current_resume:
        if current_resume["name"] == file_name and current_resume["source"] == source:
            clear_current_resume()


def get_current_resume() -> dict | None:
    if not CURRENT_RESUME_STATE_PATH.exists():
        private_resumes = [
            document
            for document in list_documents("resumes")
            if document["source"] == "private"
        ]
        if len(private_resumes) == 1:
            return set_current_resume(private_resumes[0]["name"], source="private")
        return None
    try:
        payload = json.loads(CURRENT_RESUME_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    name = payload.get("name")
    source = payload.get("source", "private")
    if not isinstance(name, str) or source not in {"private", "public"}:
        return None
    try:
        return list_document("resumes", name, source=source)
    except (FileNotFoundError, ValueError):
        clear_current_resume()
        return None


def set_current_resume(file_name: str, source: str = "private") -> dict:
    resume = list_document("resumes", file_name, source=source)
    PRIVATE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_RESUME_STATE_PATH.write_text(
        json.dumps({"name": resume["name"], "source": resume["source"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resume


def clear_current_resume() -> None:
    if CURRENT_RESUME_STATE_PATH.exists():
        CURRENT_RESUME_STATE_PATH.unlink()


def get_current_resume_source_candidates() -> list[str]:
    current_resume = get_current_resume()
    if not current_resume:
        return []

    name = current_resume["name"]
    if current_resume["source"] == "public":
        return [f"resume_samples/{name}"]
    return [f"private_data/{name}", f"private_data/resumes/{name}"]
