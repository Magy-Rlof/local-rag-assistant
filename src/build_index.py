import sys

from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct
from requests import HTTPError, RequestException, Timeout

from main import (
    COLLECTION_NAME,
    QDRANT_PATH,
    VECTOR_SIZE,
    create_embedding,
    get_api_key,
    load_markdown_documents,
    split_documents,
)


def build_section_text(section: dict) -> str:
    return (
        f"来源文件：{section['source_file']}\n"
        f"来源标题：{section['title']}\n"
        f"内容：\n{section['content']}"
    )


def recreate_collection(client: QdrantClient) -> None:
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )


def main() -> int:
    try:
        api_key = get_api_key()
        documents = load_markdown_documents(QDRANT_PATH.parent / "data")
        sections = split_documents(documents)
    except RuntimeError as exc:
        print(f"初始化失败：{exc}")
        return 1

    if not sections:
        print("没有可写入索引的文档片段。")
        return 1

    client = QdrantClient(path=str(QDRANT_PATH))
    recreate_collection(client)

    points = []
    try:
        for index, section in enumerate(sections, start=1):
            text = build_section_text(section)
            vector = create_embedding(api_key, text)
            points.append(
                PointStruct(
                    id=index,
                    vector=vector,
                    payload={
                        "source_file": section["source_file"],
                        "title": section["title"],
                        "content": section["content"],
                    },
                )
            )
            print(f"已生成向量：{section['source_file']} / {section['title']}")

        client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
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

    print(f"\nQdrant 索引构建完成。写入片段数量：{len(points)}")
    print(f"collection：{COLLECTION_NAME}")
    print(f"storage：{QDRANT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
