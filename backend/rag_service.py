import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main import (  # noqa: E402
    CAREER_ANALYSIS_CANDIDATE_K,
    CHAT_MODEL,
    COLLECTION_NAME,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    ask_model_result,
    ask_model_messages_result,
    build_rag_prompt,
    create_embedding,
    get_api_key,
    is_career_analysis_question,
    search_qdrant,
    select_sections_for_question,
)


MAX_HISTORY_MESSAGES = 8


def ask_with_rag(question: str, history: list[dict] | None = None) -> dict:
    api_key = get_api_key()
    safe_history = normalize_history(history or [])

    system_answer = answer_system_question(question)
    if system_answer:
        return {
            "answer": system_answer,
            "truncated": False,
            "sources": [],
            "retrieval_seconds": 0.0,
            "generation_seconds": 0.0,
            "mode": "system",
        }

    if not should_use_rag(question, safe_history):
        return ask_with_chat(api_key, question, safe_history)

    start_time = time.perf_counter()
    query_text = build_query_text(question, safe_history)
    query_vector = create_embedding(api_key, query_text)
    retrieval_seconds = time.perf_counter() - start_time

    candidate_k = CAREER_ANALYSIS_CANDIDATE_K if is_career_analysis_question(question) else DEFAULT_TOP_K
    candidate_sections = search_qdrant(query_vector, top_k=candidate_k)
    retrieved_sections = select_sections_for_question(question, candidate_sections)
    if not retrieved_sections:
        raise RuntimeError("未检索到相关片段，请换一种问法。")

    prompt = build_rag_prompt(
        question,
        retrieved_sections,
        include_citations=False,
        history_text=format_history_for_prompt(safe_history),
    )
    generation_start = time.perf_counter()
    model_result = ask_model_result(api_key, prompt)
    generation_seconds = time.perf_counter() - generation_start

    return {
        "answer": model_result["content"],
        "truncated": model_result["truncated"],
        "sources": [
            {
                "source_file": section["source_file"],
                "title": section["title"],
                "score": section.get("score"),
            }
            for section in retrieved_sections
        ],
        "retrieval_seconds": retrieval_seconds,
        "generation_seconds": generation_seconds,
        "mode": "rag",
    }


def ask_with_chat(api_key: str, question: str, history: list[dict]) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "你是 Local RAG Assistant 的求职资料助手。"
                "你可以进行普通对话，也可以解释本项目的功能边界。"
                "当前项目使用的 Chat 模型是 "
                f"{CHAT_MODEL}，Embedding 模型是 {EMBEDDING_MODEL}，"
                f"向量库 collection 是 {COLLECTION_NAME}。"
                "如果用户询问简历、岗位、项目资料中的具体内容，应提醒需要基于已索引资料分析。"
                "回答要简洁、直接、中文优先。"
            ),
        },
        *history[-MAX_HISTORY_MESSAGES:],
        {"role": "user", "content": question},
    ]
    generation_start = time.perf_counter()
    model_result = ask_model_messages_result(api_key, messages)
    generation_seconds = time.perf_counter() - generation_start
    return {
        "answer": model_result["content"],
        "truncated": model_result["truncated"],
        "sources": [],
        "retrieval_seconds": 0.0,
        "generation_seconds": generation_seconds,
        "mode": "chat",
    }


def should_use_rag(question: str, history: list[dict] | None = None) -> bool:
    rag_keywords = [
        "简历",
        "岗位",
        "jd",
        "JD",
        "项目经历",
        "项目资料",
        "学习笔记",
        "资料里",
        "文档里",
        "根据我的",
        "匹配",
        "修改简历",
        "优化简历",
        "适合哪些",
        "核心能力",
    ]
    if any(keyword in question for keyword in rag_keywords):
        return True

    contextual_keywords = ["这个", "它", "刚才", "上面", "继续", "那", "还有", "进一步"]
    if not any(keyword in question for keyword in contextual_keywords):
        return False

    recent_history = "\n".join(item["content"] for item in (history or [])[-4:])
    return any(keyword in recent_history for keyword in rag_keywords)


def answer_system_question(question: str) -> str:
    model_keywords = ["哪个模型", "什么模型", "使用的模型", "正在使用", "chat模型", "Chat 模型"]
    embedding_keywords = ["embedding", "Embedding", "向量模型", "嵌入模型"]
    vector_keywords = ["向量库", "qdrant", "Qdrant", "collection"]
    if any(keyword in question for keyword in model_keywords):
        return (
            f"当前 Chat 模型是 `{CHAT_MODEL}`，Embedding 模型是 `{EMBEDDING_MODEL}`。"
            "系统会在求职资料相关问题上先走 Qdrant 检索，再把相关片段交给 Chat 模型生成回答。"
        )
    if any(keyword in question for keyword in embedding_keywords):
        return f"当前 Embedding 模型是 `{EMBEDDING_MODEL}`，用于把问题和文档片段转换为向量。"
    if any(keyword in question for keyword in vector_keywords):
        return f"当前使用本地 Qdrant 向量库，collection 名称是 `{COLLECTION_NAME}`。"
    return ""


def normalize_history(history: list[dict]) -> list[dict]:
    normalized = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        normalized.append({"role": role, "content": content.strip()[:1200]})
    return normalized


def format_history_for_prompt(history: list[dict]) -> str:
    lines = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        role_label = "用户" if item["role"] == "user" else "助手"
        lines.append(f"{role_label}：{item['content']}")
    return "\n".join(lines)


def build_query_text(question: str, history: list[dict]) -> str:
    history_text = format_history_for_prompt(history[-4:])
    if not history_text:
        return question
    return f"{history_text}\n当前问题：{question}"
