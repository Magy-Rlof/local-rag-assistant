import os
import re
import sys
import time
from pathlib import Path

import requests
from qdrant_client import QdrantClient


CHAT_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
EMBEDDING_MODEL = "BAAI/bge-m3"
COLLECTION_NAME = "local_rag_sections"
VECTOR_SIZE = 1024
REQUEST_TIMEOUT = 90
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QDRANT_PATH = Path(__file__).resolve().parent.parent / "qdrant_storage"


def get_api_key() -> str:
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 SILICONFLOW_API_KEY，请先配置环境变量。")
    return api_key.strip()


def load_document(path: Path) -> tuple[str, str]:
    if not path.exists():
        raise RuntimeError(f"文档不存在：{path}")
    return path.name, path.read_text(encoding="utf-8")


def load_markdown_documents(data_dir: Path) -> list[tuple[str, str]]:
    if not data_dir.exists():
        raise RuntimeError(f"数据目录不存在：{data_dir}")

    document_paths = sorted(data_dir.glob("*.md"))
    if not document_paths:
        raise RuntimeError(f"数据目录中没有 Markdown 文档：{data_dir}")

    return [load_document(path) for path in document_paths]


def split_markdown_sections(source_file: str, text: str) -> list[dict]:
    sections = []
    current_title = "文档开头"
    current_lines = []

    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                content = "\n".join(current_lines).strip()
                if has_body_content(content):
                    sections.append(
                        {
                            "source_file": source_file,
                            "title": current_title,
                            "content": content,
                        }
                    )
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if has_body_content(content):
            sections.append(
                {
                    "source_file": source_file,
                    "title": current_title,
                    "content": content,
                }
            )

    return [section for section in sections if section["content"]]


def has_body_content(section_text: str) -> bool:
    body_lines = [line for line in section_text.splitlines() if not line.startswith("#")]
    return bool("".join(body_lines).strip())


def split_documents(documents: list[tuple[str, str]]) -> list[dict]:
    sections = []
    for source_file, text in documents:
        sections.extend(split_markdown_sections(source_file, text))
    return sections


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
    stop_words = {"的", "了", "是", "有", "和", "或", "吗", "么", "什", "这", "那"}
    return {word for word in words if word not in stop_words}


def retrieve_sections(question: str, sections: list[dict], top_k: int = 4) -> list[dict]:
    question_tokens = tokenize(question)
    scored_sections = []

    for section in sections:
        section_text = section["source_file"] + "\n" + section["title"] + "\n" + section["content"]
        section_tokens = tokenize(section_text)
        score = len(question_tokens & section_tokens)
        score += rule_based_boost(question, section)
        if score > 0:
            scored_sections.append((score, section))

    scored_sections.sort(key=lambda item: item[0], reverse=True)
    selected_sections = select_required_sources(question, scored_sections, top_k)
    if selected_sections:
        return selected_sections
    return [section for _, section in scored_sections[:top_k]]


def select_required_sources(question: str, scored_sections: list[tuple[int, dict]], top_k: int) -> list[dict]:
    if any(keyword in question for keyword in ["项目和岗位", "匹配", "匹配点"]):
        selected = []
        selected.extend(take_by_source(scored_sections, "sample_project", limit=2))
        selected.extend(take_by_source(scored_sections, "job_description", limit=2))
        return dedupe_sections(selected)[:top_k]

    if any(keyword in question for keyword in ["学习", "笔记"]):
        selected = take_by_source(scored_sections, "learning_note", limit=top_k)
        return selected[:top_k]

    return []


def take_by_source(scored_sections: list[tuple[int, dict]], source_keyword: str, limit: int) -> list[dict]:
    sections = []
    for _, section in scored_sections:
        if source_keyword in section["source_file"]:
            sections.append(section)
        if len(sections) >= limit:
            break
    return sections


def dedupe_sections(sections: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for section in sections:
        key = (section["source_file"], section["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(section)
    return deduped


def rule_based_boost(question: str, section: dict) -> int:
    score = 0
    source_file = section["source_file"]
    title = section["title"]

    if any(keyword in question for keyword in ["岗位", "要求", "职责", "加分"]):
        if "job_description" in source_file:
            score += 3
        if any(keyword in title for keyword in ["能力要求", "主要职责", "加分项", "岗位定位"]):
            score += 3

    if any(keyword in question for keyword in ["学习", "笔记", "API", "RAG", "Prompt", "结构化", "Tool"]):
        if "learning_note" in source_file:
            score += 3

    if any(keyword in question for keyword in ["匹配", "匹配点", "项目和岗位"]):
        if "sample_project" in source_file:
            score += 2
        if "job_description" in source_file:
            score += 2
        if any(keyword in title for keyword in ["核心功能", "项目定位", "能力要求", "主要职责"]):
            score += 2

    return score


def build_rag_prompt(question: str, sections: list[dict]) -> str:
    context = "\n\n".join(
        (
            f"来源文件：{section['source_file']}\n"
            f"来源标题：{section['title']}\n"
            f"内容：\n{section['content']}"
        )
        for section in sections
    )
    return f"""请基于给定资料回答用户问题。

要求：
- 只能使用资料中的信息回答
- 如果资料不足，请明确说明“当前资料不足，无法确定”
- 回答后列出引用来源文件和标题
- 不要编造资料中没有的信息

资料：
{context}

用户问题：
{question}
"""


def ask_model(api_key: str, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "max_tokens": 700,
        "temperature": 0.3,
    }

    response = requests.post(CHAT_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    if data.get("type") == "error":
        error = data.get("error", {})
        error_type = error.get("type", "unknown_error")
        error_message = error.get("message", "硅基流动返回了未知错误。")
        raise RuntimeError(f"硅基流动返回错误 {error_type}：{error_message}")

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    raise RuntimeError(f"无法解析模型返回结果：{data}")


def create_embedding(api_key: str, text: str) -> list[float]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
        "encoding_format": "float",
    }

    response = requests.post(EMBEDDING_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    embeddings = data.get("data", [])
    if not embeddings or "embedding" not in embeddings[0]:
        raise RuntimeError(f"无法解析 Embedding 返回结果：{data}")

    embedding = embeddings[0]["embedding"]
    if len(embedding) != VECTOR_SIZE:
        raise RuntimeError(f"Embedding 维度异常：期望 {VECTOR_SIZE}，实际 {len(embedding)}")
    return embedding


def search_qdrant(query_vector: list[float], top_k: int = 4) -> list[dict]:
    client = QdrantClient(path=str(QDRANT_PATH))
    if not client.collection_exists(COLLECTION_NAME):
        raise RuntimeError("未找到 Qdrant 索引，请先运行 src/build_index.py。")

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        with_payload=True,
        limit=top_k,
    ).points

    sections = []
    for result in results:
        payload = result.payload or {}
        sections.append(
            {
                "source_file": payload.get("source_file", "unknown"),
                "title": payload.get("title", "unknown"),
                "content": payload.get("content", ""),
                "score": result.score,
            }
        )
    return sections


def main() -> int:
    try:
        api_key = get_api_key()
    except RuntimeError as exc:
        print(f"初始化失败：{exc}")
        return 1

    print("已读取 SILICONFLOW_API_KEY。")
    print("检索模式：Qdrant 向量检索")

    question = input("请输入你的问题：").strip()
    if not question:
        print("问题不能为空。")
        return 1

    try:
        print("正在生成问题向量...")
        query_vector = create_embedding(api_key, question)
        retrieved_sections = search_qdrant(query_vector)
        if not retrieved_sections:
            print("未检索到相关片段，请换一种问法。")
            return 1

        print("\n检索到的引用来源：")
        for section in retrieved_sections:
            print(f"- {section['source_file']} / {section['title']} / score={section['score']:.4f}")

        prompt = build_rag_prompt(question, retrieved_sections)
        print("\n正在请求模型，请稍候...")
        start_time = time.perf_counter()
        answer = ask_model(api_key, prompt)
        elapsed_seconds = time.perf_counter() - start_time
    except requests.HTTPError as exc:
        print(f"API 请求失败：{exc}")
        return 1
    except requests.Timeout:
        print("请求超时：模型响应较慢，可以稍后重试或减少上下文长度。")
        return 1
    except requests.RequestException as exc:
        print(f"网络请求异常：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"处理失败：{exc}")
        return 1

    print("\n模型回答：")
    print(answer)
    print(f"\n本次耗时：{elapsed_seconds:.1f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
