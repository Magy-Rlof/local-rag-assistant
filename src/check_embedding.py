import os
import sys

import requests


API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_MODEL = "BAAI/bge-m3"
REQUEST_TIMEOUT = 60


def get_api_key() -> str:
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 SILICONFLOW_API_KEY，请先配置环境变量。")
    return api_key.strip()


def create_embedding(api_key: str, text: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
        "encoding_format": "float",
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def main() -> int:
    try:
        api_key = get_api_key()
        data = create_embedding(api_key, "这是一个用于验证 Embedding API 的非敏感测试文本。")
    except RuntimeError as exc:
        print(f"配置错误：{exc}")
        return 1
    except requests.HTTPError as exc:
        print(f"API 请求失败：{exc}")
        return 1
    except requests.RequestException as exc:
        print(f"网络请求异常：{exc}")
        return 1

    embeddings = data.get("data", [])
    if not embeddings or "embedding" not in embeddings[0]:
        print(f"无法解析 Embedding 返回结果：{data}")
        return 1

    embedding = embeddings[0]["embedding"]
    print("Embedding API 调用成功。")
    print(f"模型：{data.get('model', EMBEDDING_MODEL)}")
    print(f"向量维度：{len(embedding)}")
    print(f"usage：{data.get('usage')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
