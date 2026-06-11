from pathlib import Path

from docx import Document
from pypdf import PdfReader


SUPPORTED_SUFFIXES = {".md", ".docx", ".pdf"}


def load_knowledge_documents(data_dir: Path, private_data_dir: Path) -> list[tuple[str, str]]:
    documents = []
    documents.extend(load_documents_from_dir(data_dir, source_prefix=""))

    if private_data_dir.exists():
        documents.extend(load_documents_from_dir(private_data_dir, source_prefix="private_data"))

    if not documents:
        raise RuntimeError("没有找到可加载的知识库文档。")

    return documents


def load_documents_from_dir(directory: Path, source_prefix: str) -> list[tuple[str, str]]:
    if not directory.exists():
        raise RuntimeError(f"数据目录不存在：{directory}")

    documents = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        source_file = path.relative_to(directory).as_posix()
        if source_prefix:
            source_file = f"{source_prefix}/{source_file}"

        text = load_document_text(path)
        if text.strip():
            documents.append((source_file, text))

    return documents


def load_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return load_docx_text(path)
    if suffix == ".pdf":
        return load_pdf_text(path)
    raise RuntimeError(f"不支持的文档格式：{path}")


def load_docx_text(path: Path) -> str:
    document = Document(path)
    lines = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.startswith("Heading"):
            heading_level = extract_heading_level(style_name)
            prefix = "#" * heading_level
            lines.append(f"{prefix} {text}")
        else:
            lines.append(text)

    return "\n\n".join(lines)


def extract_heading_level(style_name: str) -> int:
    parts = style_name.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return max(1, min(int(parts[-1]), 6))
    return 2


def load_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    page_texts = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            page_texts.append(f"# 第 {index} 页\n\n{text.strip()}")
    return "\n\n".join(page_texts)
