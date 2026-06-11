import hashlib
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct

from document_loader import load_knowledge_documents
from main import (
    COLLECTION_NAME,
    DATA_DIR,
    PRIVATE_DATA_DIR,
    QDRANT_PATH,
    VECTOR_SIZE,
    create_embedding,
    get_api_key,
    split_documents,
)


LogFn = Callable[[str], None]


@dataclass
class IndexBuildResult:
    changed_sources: list[str]
    skipped_sources: list[str]
    removed_sources: list[str]
    written_points: int
    collection_name: str
    storage_path: str


def build_section_text(section: dict) -> str:
    return (
        f"来源文件：{section['source_file']}\n"
        f"来源标题：{section['title']}\n"
        f"内容：\n{section['content']}"
    )


def ensure_collection(client: QdrantClient) -> None:
    if client.collection_exists(COLLECTION_NAME):
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_indexed_document_hashes(client: QdrantClient) -> dict[str, str]:
    if not client.collection_exists(COLLECTION_NAME):
        return {}

    indexed_hashes = {}
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for record in records:
            payload = record.payload or {}
            source_file = payload.get("source_file")
            document_hash = payload.get("document_hash")
            if source_file and document_hash:
                indexed_hashes[source_file] = document_hash
            elif source_file:
                indexed_hashes[source_file] = ""

        if offset is None:
            break

    return indexed_hashes


def delete_document_points(client: QdrantClient, source_file: str) -> None:
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_file",
                        match=models.MatchValue(value=source_file),
                    )
                ]
            )
        ),
        wait=True,
    )


def build_point_id(source_file: str, section_index: int, title: str) -> str:
    raw_id = f"local-rag-assistant:{source_file}:{section_index}:{title}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))


def group_sections_by_source(sections: list[dict]) -> dict[str, list[dict]]:
    grouped_sections = defaultdict(list)
    for section in sections:
        grouped_sections[section["source_file"]].append(section)
    return dict(grouped_sections)


def build_index(api_key: str | None = None, log: LogFn | None = None) -> IndexBuildResult:
    if api_key is None:
        api_key = get_api_key()

    documents = load_knowledge_documents(DATA_DIR, PRIVATE_DATA_DIR)
    sections = split_documents(documents)
    if not sections:
        raise RuntimeError("没有可写入索引的文档片段。")

    client = QdrantClient(path=str(QDRANT_PATH))
    ensure_collection(client)

    current_hashes = {source_file: hash_text(text) for source_file, text in documents}
    indexed_hashes = get_indexed_document_hashes(client)
    sections_by_source = group_sections_by_source(sections)

    removed_sources = sorted(set(indexed_hashes) - set(current_hashes))
    changed_sources = [
        source_file
        for source_file, document_hash in current_hashes.items()
        if indexed_hashes.get(source_file) != document_hash
    ]
    skipped_sources = sorted(set(current_hashes) - set(changed_sources))

    written_points = 0
    for source_file in removed_sources:
        delete_document_points(client, source_file)
        if log:
            log(f"已删除过期文档索引：{source_file}")

    for source_file in changed_sources:
        delete_document_points(client, source_file)
        points = []
        document_hash = current_hashes[source_file]
        for section_index, section in enumerate(sections_by_source.get(source_file, []), start=1):
            text = build_section_text(section)
            vector = create_embedding(api_key, text)
            points.append(
                PointStruct(
                    id=build_point_id(source_file, section_index, section["title"]),
                    vector=vector,
                    payload={
                        "source_file": section["source_file"],
                        "title": section["title"],
                        "content": section["content"],
                        "document_hash": document_hash,
                    },
                )
            )
            if log:
                log(f"已生成向量：{section['source_file']} / {section['title']}")

        if points:
            client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
            written_points += len(points)

    return IndexBuildResult(
        changed_sources=changed_sources,
        skipped_sources=skipped_sources,
        removed_sources=removed_sources,
        written_points=written_points,
        collection_name=COLLECTION_NAME,
        storage_path=str(QDRANT_PATH),
    )
