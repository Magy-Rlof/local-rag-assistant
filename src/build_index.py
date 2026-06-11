import hashlib
import sys
import uuid
from collections import defaultdict

from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct
from requests import HTTPError, RequestException, Timeout

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


def main() -> int:
    try:
        api_key = get_api_key()
        documents = load_knowledge_documents(DATA_DIR, PRIVATE_DATA_DIR)
        sections = split_documents(documents)
    except RuntimeError as exc:
        print(f"初始化失败：{exc}")
        return 1

    if not sections:
        print("没有可写入索引的文档片段。")
        return 1

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
    try:
        for source_file in removed_sources:
            delete_document_points(client, source_file)
            print(f"已删除过期文档索引：{source_file}")

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
                print(f"已生成向量：{section['source_file']} / {section['title']}")

            if points:
                client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
                written_points += len(points)
    except HTTPError as exc:
        print(f"Embedding API 请求失败：{exc}")
        return 1
    except Timeout:
        print("Embedding 请求超时：可以稍后重试。")
        return 1
    except RequestException as exc:
        print(f"Embedding 网络请求异常：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"处理失败：{exc}")
        return 1

    print("\nQdrant 增量索引完成。")
    print(f"新增或更新文档数量：{len(changed_sources)}")
    print(f"跳过未变更文档数量：{len(skipped_sources)}")
    print(f"删除过期文档数量：{len(removed_sources)}")
    print(f"本次写入片段数量：{written_points}")
    print(f"collection：{COLLECTION_NAME}")
    print(f"storage：{QDRANT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
