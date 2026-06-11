import os
import re
import sys
import time
from pathlib import Path

import requests


API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V4-Pro"
REQUEST_TIMEOUT = 90
DOCUMENT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_project.md"


def get_api_key() -> str:
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 SILICONFLOW_API_KEY，请先配置环境变量。")
    return api_key.strip()


def load_document(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"文档不存在：{path}")
    return path.read_text(encoding="utf-8")


def split_markdown_sections(text: str) -> list[dict]:
    sections = []
    current_title = "文档开头"
    current_lines = []

    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append(
                    {
                        "title": current_title,
                        "content": "\n".join(current_lines).strip(),
                    }
                )
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(
            {
                "title": current_title,
                "content": "\n".join(current_lines).strip(),
            }
        )

    return [section for section in sections if section["content"]]


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
    stop_words = {"的", "了", "是", "有", "和", "或", "吗", "么", "什", "这", "那"}
    return {word for word in words if word not in stop_words}


def retrieve_sections(question: str, sections: list[dict], top_k: int = 2) -> list[dict]:
    question_tokens = tokenize(question)
    scored_sections = []

    for section in sections:
        section_tokens = tokenize(section["title"] + "\n" + section["content"])
        score = len(question_tokens & section_tokens)
        if score > 0:
            scored_sections.append((score, section))

    scored_sections.sort(key=lambda item: item[0], reverse=True)
    return [section for _, section in scored_sections[:top_k]]


def build_rag_prompt(question: str, sections: list[dict]) -> str:
    context = "\n\n".join(
        f"来源标题：{section['title']}\n内容：\n{section['content']}" for section in sections
    )
    return f"""请基于给定资料回答用户问题。

要求：
- 只能使用资料中的信息回答
- 如果资料不足，请明确说明“当前资料不足，无法确定”
- 回答后列出引用来源标题
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
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "max_tokens": 700,
        "temperature": 0.3,
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
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


def main() -> int:
    try:
        api_key = get_api_key()
        document = load_document(DOCUMENT_PATH)
        sections = split_markdown_sections(document)
    except RuntimeError as exc:
        print(f"初始化失败：{exc}")
        return 1

    print("已读取 SILICONFLOW_API_KEY。")
    print(f"已加载文档：{DOCUMENT_PATH}")
    print(f"已切分片段数量：{len(sections)}")

    question = input("请输入你的问题：").strip()
    if not question:
        print("问题不能为空。")
        return 1

    retrieved_sections = retrieve_sections(question, sections)
    if not retrieved_sections:
        print("未检索到相关片段，请换一种问法。")
        return 1

    print("\n检索到的引用来源：")
    for section in retrieved_sections:
        print(f"- {section['title']}")

    prompt = build_rag_prompt(question, retrieved_sections)

    try:
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
