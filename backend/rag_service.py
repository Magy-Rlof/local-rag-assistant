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
    get_sections_by_source_files,
    is_career_analysis_question,
    search_qdrant,
    select_sections_for_question,
)

from .document_service import CATEGORIES, get_current_resume_source_candidates, list_documents  # noqa: E402


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

    overview_answer = answer_library_overview_question(question, safe_history)
    if overview_answer:
        return {
            "answer": overview_answer,
            "truncated": False,
            "sources": [],
            "retrieval_seconds": 0.0,
            "generation_seconds": 0.0,
            "mode": "system",
        }

    if not should_use_rag(question, safe_history):
        return ask_with_chat(api_key, question, safe_history)

    start_time = time.perf_counter()
    intent_text = build_intent_text(question, safe_history)
    query_text = build_query_text(question, safe_history)
    query_vector = create_embedding(api_key, query_text)
    retrieval_seconds = time.perf_counter() - start_time

    candidate_k = CAREER_ANALYSIS_CANDIDATE_K if is_career_analysis_question(intent_text) else DEFAULT_TOP_K
    candidate_sections = search_qdrant(query_vector, top_k=candidate_k)
    current_resume_sources = get_current_resume_source_candidates()
    forced_resume_sections = []
    if is_current_resume_required(intent_text):
        if not current_resume_sources:
            raise RuntimeError("请先在简历中心设置当前简历。")
        forced_resume_sections = get_sections_by_source_files(current_resume_sources, limit_per_source=5)
        if not forced_resume_sections:
            raise RuntimeError("当前简历尚未进入向量索引，请先到索引状态页更新索引。")

    retrieved_sections = select_sections_for_question(
        intent_text,
        forced_resume_sections + candidate_sections,
        current_resume_sources=current_resume_sources,
    )
    if not retrieved_sections:
        raise RuntimeError("未检索到相关片段，请换一种问法。")

    prompt = build_rag_prompt(
        build_question_for_prompt(question, intent_text),
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

    contextual_keywords = ["这个", "它", "刚才", "上面", "继续", "那", "还有", "进一步", "为什么", "哪些地方", "优先", "怎么改", "应该"]
    if not any(keyword in question for keyword in contextual_keywords):
        return False

    recent_history = "\n".join(item["content"] for item in (history or [])[-4:])
    return any(keyword in recent_history for keyword in rag_keywords)


def answer_library_overview_question(question: str, history: list[dict]) -> str:
    if not is_library_overview_question(question, history):
        return ""

    focused_category = get_focused_overview_category(question, history)
    if focused_category:
        return build_category_overview(focused_category)

    lines = ["当前资料库包含以下几类资料："]
    for category_key, config in CATEGORIES.items():
        lines.append(format_category_summary(category_key, config.label))

    lines.append("另外，公开示例资料主要存放在 data/ 目录，真实个人资料建议放在 private_data/ 目录。")
    lines.append("你可以继续追问某一类资料，例如“简历”“岗位资料”“项目资料”或“学习笔记”。")
    return "\n".join(lines)


def is_library_overview_question(question: str, history: list[dict]) -> bool:
    overview_keywords = ["资料库", "有哪些信息", "有哪些资料", "有哪些文档", "包含什么", "有什么内容"]
    if any(keyword in question for keyword in overview_keywords):
        return True

    focused_keywords = ["简历", "岗位", "项目", "学习笔记", "笔记", "行业"]
    if question.strip() in focused_keywords:
        if len(question.strip()) <= 8:
            return True
        recent_text = "\n".join(item["content"] for item in history[-4:])
        return any(keyword in recent_text for keyword in overview_keywords)

    return False


def get_focused_overview_category(question: str, history: list[dict]) -> str:
    recent_text = "\n".join(item["content"] for item in history[-4:])
    overview_keywords = ["资料库", "有哪些信息", "有哪些资料", "有哪些文档", "包含什么", "有什么内容"]
    is_follow_up = any(keyword in recent_text for keyword in overview_keywords)

    category_keywords = {
        "resumes": ["简历", "简历库", "简历样例"],
        "industries": ["行业", "行业资料"],
        "jobs": ["岗位", "岗位资料", "jd", "JD"],
        "projects": ["项目", "项目资料"],
        "notes": ["学习笔记", "笔记"],
    }
    for category_key, keywords in category_keywords.items():
        if any(keyword in question for keyword in keywords):
            if is_follow_up or len(question.strip()) <= 8:
                return category_key
    return ""


def build_category_overview(category_key: str) -> str:
    config = CATEGORIES[category_key]
    documents = list_documents(category_key)
    private_documents = [item for item in documents if item["source"] == "private"]
    public_documents = [item for item in documents if item["source"] == "public"]

    lines = [f"{config.label}当前共有 {len(documents)} 份资料。"]
    lines.append(f"- 本地私有资料：{len(private_documents)} 份")
    lines.append(f"- 公开示例资料：{len(public_documents)} 份")

    if private_documents:
        lines.append("私有资料示例：" + ", ".join(item["name"] for item in private_documents[:8]))
    if public_documents:
        lines.append("公开示例：" + ", ".join(item["name"] for item in public_documents[:8]))

    if category_key == "resumes":
        lines.append("真实个人简历建议放在 private_data/，公开仓库只提交脱敏样例。")
    else:
        lines.append("你可以继续追问某一份资料的用途、匹配点或修改建议。")
    return "\n".join(lines)


def format_category_summary(category_key: str, label: str) -> str:
    documents = list_documents(category_key)
    private_documents = [item for item in documents if item["source"] == "private"]
    public_documents = [item for item in documents if item["source"] == "public"]
    examples = ", ".join(item["name"] for item in documents[:5]) or "暂无文档"
    return (
        f"- {label}：共 {len(documents)} 份，"
        f"其中私有 {len(private_documents)} 份、公开示例 {len(public_documents)} 份。"
        f"示例：{examples}"
    )


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


def build_intent_text(question: str, history: list[dict]) -> str:
    if len(question.strip()) > 8 and not is_contextual_follow_up(question):
        return question

    recent_text = "\n".join(item["content"] for item in history[-4:])
    if not recent_text:
        return question
    return f"{recent_text}\n当前追问：{question}"


def is_contextual_follow_up(question: str) -> bool:
    contextual_keywords = ["为什么", "哪些地方", "优先", "怎么改", "修改", "优化", "那我", "继续", "具体"]
    return any(keyword in question for keyword in contextual_keywords)


def is_current_resume_required(intent_text: str) -> bool:
    resume_keywords = ["我的简历", "根据我的简历", "这份简历", "简历修改", "修改简历", "优化简历", "当前简历"]
    return any(keyword in intent_text for keyword in resume_keywords)


def build_question_for_prompt(question: str, intent_text: str) -> str:
    if intent_text == question:
        return question
    return f"{intent_text}\n请回答当前追问：{question}"
