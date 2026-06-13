import json
import os
import sys
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main import (  # noqa: E402
    CAREER_ANALYSIS_CANDIDATE_K,
    CHAT_MODEL,
    CHAT_API_URL,
    CHAT_MAX_TOKENS,
    COLLECTION_NAME,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    REQUEST_TIMEOUT,
    ask_model_messages_result,
    create_embedding,
    get_api_key,
    get_focused_project_sources,
    get_sections_by_source_files,
    is_career_analysis_question,
    is_knowledge_base_guidance_question,
    is_technical_explanation_question,
    search_qdrant,
    select_sections_for_question,
)

from .document_service import CATEGORIES, get_current_resume_source_candidates, list_documents  # noqa: E402
from .prompt_templates import build_prompt_for_task  # noqa: E402
from .task_router import (  # noqa: E402
    TaskType,
    build_context_plan,
    build_conversation_state,
    detect_task_type,
    task_requires_rag,
)


MAX_HISTORY_MESSAGES = 8
MAX_CONTINUATION_ATTEMPTS = 1
LOG_ANSWERS_TO_CONSOLE = os.getenv("LOCAL_RAG_LOG_ANSWERS", "0") == "1"
DANGLING_ANSWER_SUFFIXES = (
    "并返回",
    "并附带",
    "并给出",
    "并说明",
    "并",
    "包括",
    "包含",
    "例如",
    "比如",
    "以及",
    "或者",
    "然后",
    "通过",
    "基于",
    "返回",
    "输出",
    "生成",
    "调用",
    "写入",
)
DANGLING_ANSWER_ENDINGS = ("，", "、", "：", ":", "；", ";", "→", "->")


def stream_with_rag(question: str, history: list[dict] | None = None):
    api_key = get_api_key()
    prepared = prepare_generation(question, history or [])
    yield stream_event(
        "meta",
        {
            "sources": prepared["sources"],
            "retrieval_seconds": prepared["retrieval_seconds"],
            "mode": prepared["mode"],
        },
    )

    if prepared.get("direct_answer"):
        answer = prepared["direct_answer"]
        yield stream_event("delta", {"text": answer})
        log_answer_to_console(
            phase="stream-direct",
            question=question,
            prepared=prepared,
            answer=answer,
            truncated=False,
            finish_reason=None,
            continuation_attempts=0,
        )
        yield stream_event(
            "done",
            {
                "answer": answer,
                "truncated": False,
                "sources": prepared["sources"],
                "retrieval_seconds": prepared["retrieval_seconds"],
                "generation_seconds": 0.0,
                "mode": prepared["mode"],
            },
        )
        return

    generation_start = time.perf_counter()
    answer_parts: list[str] = []
    finish_reason = None
    for chunk, next_finish_reason in stream_model_messages(api_key, prepared["messages"]):
        if chunk:
            answer_parts.append(chunk)
            yield stream_event("delta", {"text": chunk})
        if next_finish_reason:
            finish_reason = next_finish_reason

    answer = "".join(answer_parts).strip()
    continuation_attempts = 0
    while continuation_attempts < MAX_CONTINUATION_ATTEMPTS and needs_continuation(answer, prepared):
        continuation_attempts += 1
        continuation_messages = build_continuation_messages(prepared["messages"], answer, prepared)
        for chunk, next_finish_reason in stream_model_messages(api_key, continuation_messages, temperature=0.2):
            if chunk:
                answer_parts.append(chunk)
                yield stream_event("delta", {"text": chunk})
            if next_finish_reason:
                finish_reason = next_finish_reason
        answer = "".join(answer_parts).strip()

    generation_seconds = time.perf_counter() - generation_start
    truncated = finish_reason == "length" or needs_continuation(answer, prepared)
    log_answer_to_console(
        phase="stream",
        question=question,
        prepared=prepared,
        answer=answer,
        truncated=truncated,
        finish_reason=finish_reason,
        continuation_attempts=continuation_attempts,
    )
    yield stream_event(
        "done",
        {
            "answer": answer,
            "truncated": truncated,
            "sources": prepared["sources"],
            "retrieval_seconds": prepared["retrieval_seconds"],
            "generation_seconds": generation_seconds,
            "mode": prepared["mode"],
        },
    )


def stream_event(event: str, payload: dict) -> str:
    return json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n"


def log_answer_to_console(
    *,
    phase: str,
    question: str,
    prepared: dict,
    answer: str,
    truncated: bool,
    finish_reason: str | None,
    continuation_attempts: int,
) -> None:
    if not LOG_ANSWERS_TO_CONSOLE:
        return

    task_type = prepared.get("task_type")
    task_value = task_type.value if isinstance(task_type, TaskType) else str(task_type)
    print("\n" + "=" * 80, flush=True)
    print("[Local RAG Answer Debug]", flush=True)
    print(f"phase: {phase}", flush=True)
    print(f"mode: {prepared.get('mode')}", flush=True)
    print(f"task_type: {task_value}", flush=True)
    print(f"finish_reason: {finish_reason}", flush=True)
    print(f"continuation_attempts: {continuation_attempts}", flush=True)
    print(f"truncated: {truncated}", flush=True)
    print(f"answer_chars: {len(answer)}", flush=True)
    print(f"question: {question}", flush=True)
    print("-" * 80, flush=True)
    print(answer, flush=True)
    print("=" * 80 + "\n", flush=True)


def needs_continuation(answer: str, prepared: dict) -> bool:
    if looks_incomplete_answer(answer):
        return True
    return missing_required_structure(answer, prepared.get("task_type"), prepared.get("question", ""))


def missing_required_structure(answer: str, task_type: TaskType | None, question: str) -> bool:
    if task_type != TaskType.PROJECT_REVIEW or not is_rag_flow_question(question):
        return False

    final_sentence = "以上就是该项目的 RAG 流程。"
    required_groups = [
        ("流程概览",),
        ("每一步做什么", "每一步", "步骤"),
        ("工程价值", "项目价值", "这个流程的工程价值"),
    ]
    return final_sentence not in answer or any(
        not any(keyword in answer for keyword in group) for group in required_groups
    )


def is_rag_flow_question(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in ("rag 流程", "rag流程", "流程是什么", "实现流程"))


def build_continuation_messages(original_messages: list[dict], partial_answer: str, prepared: dict) -> list[dict]:
    instruction = (
        "上一条回答明显未完成，或缺少当前任务要求的必要小节。\n"
        "请只续写缺失的后续内容，不要重复前文，不要重新开始回答。\n"
        "如果上一句停在半句，请从该半句后面自然接上。\n"
        "续写必须以完整句子结束。"
    )
    if prepared.get("task_type") == TaskType.PROJECT_REVIEW and is_rag_flow_question(prepared.get("question", "")):
        instruction += "\n请补齐缺失的 RAG 流程结构，必须包含“每一步做什么”和“这个流程的工程价值”。最后一句必须是：以上就是该项目的 RAG 流程。"

    return [
        *original_messages,
        {"role": "assistant", "content": partial_answer},
        {"role": "user", "content": instruction},
    ]


def complete_answer_once(api_key: str, messages: list[dict], answer: str, prepared: dict) -> tuple[str, bool]:
    if not needs_continuation(answer, prepared):
        return answer, False

    continuation_messages = build_continuation_messages(messages, answer, prepared)
    continuation_result = ask_model_messages_result(api_key, continuation_messages, temperature=0.2)
    completed_answer = (answer + continuation_result["content"]).strip()
    return completed_answer, continuation_result["truncated"] or needs_continuation(completed_answer, prepared)


def stream_model_messages(api_key: str, messages: list[dict], temperature: float = 0.3):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "max_tokens": CHAT_MAX_TOKENS,
        "temperature": temperature,
        "stream": True,
    }

    with requests.post(
        CHAT_API_URL,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
        stream=True,
    ) as response:
        response.raise_for_status()
        response.encoding = "utf-8"
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                break
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "error":
                error = data.get("error", {})
                error_type = error.get("type", "unknown_error")
                error_message = error.get("message", "硅基流动返回了未知错误。")
                raise RuntimeError(f"硅基流动返回错误 {error_type}：{error_message}")
            choices = data.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            content = delta.get("content") if isinstance(delta, dict) else ""
            yield content or "", choice.get("finish_reason")


def prepare_generation(question: str, history: list[dict] | None = None) -> dict:
    safe_history = normalize_history(history or [])
    task_type = detect_task_type(question, safe_history)
    conversation_state = build_conversation_state(question, safe_history)
    context_plan = build_context_plan(task_type, conversation_state)

    system_answer = answer_system_question(question)
    if system_answer:
        return {
            "messages": [],
            "direct_answer": system_answer,
            "sources": [],
            "retrieval_seconds": 0.0,
            "mode": "system",
            "task_type": task_type,
            "question": question,
        }

    overview_answer = answer_library_overview_question(question, safe_history)
    if overview_answer:
        return {
            "messages": [],
            "direct_answer": overview_answer,
            "sources": [],
            "retrieval_seconds": 0.0,
            "mode": "system",
            "task_type": task_type,
            "question": question,
        }

    if not should_use_rag(question, safe_history, task_type):
        return {
            "messages": build_chat_messages(question, safe_history),
            "sources": [],
            "retrieval_seconds": 0.0,
            "mode": "chat",
            "task_type": task_type,
            "question": question,
        }

    start_time = time.perf_counter()
    intent_text = build_intent_text(question, safe_history)
    query_text = build_query_text(question, safe_history)
    query_vector = create_embedding(get_api_key(), query_text)
    retrieval_seconds = time.perf_counter() - start_time

    retrieved_sections = retrieve_context_sections(
        intent_text,
        task_type,
        conversation_state,
        context_plan,
        query_vector,
    )
    prompt = build_prompt_for_task(
        task_type,
        build_question_for_prompt(question, intent_text),
        retrieved_sections,
        history_text=format_history_for_prompt(safe_history),
    )
    return {
        "messages": [{"role": "user", "content": prompt}],
        "sources": format_sources(retrieved_sections),
        "retrieval_seconds": retrieval_seconds,
        "mode": "rag",
        "task_type": task_type,
        "question": question,
    }


def build_chat_messages(question: str, history: list[dict]) -> list[dict]:
    return [
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


def retrieve_context_sections(
    intent_text: str,
    task_type: TaskType,
    conversation_state,
    context_plan,
    query_vector: list[float],
) -> list[dict]:
    candidate_k = CAREER_ANALYSIS_CANDIDATE_K if is_career_analysis_question(intent_text) else DEFAULT_TOP_K
    candidate_sections = search_qdrant(query_vector, top_k=candidate_k)
    current_resume_sources = get_current_resume_source_candidates()
    forced_resume_sections = []
    if context_plan.require_current_resume or is_current_resume_required(intent_text):
        if not current_resume_sources:
            raise RuntimeError("请先在简历中心设置当前简历。")
        forced_resume_sections = get_sections_by_source_files(current_resume_sources, limit_per_source=5)
        if not forced_resume_sections:
            raise RuntimeError("当前简历尚未进入向量索引，请先到索引状态页更新索引。")

    forced_context_sections = get_forced_context_sections(context_plan)
    focused_project_sources = get_focused_project_sources(intent_text)
    if (
        not forced_context_sections
        and task_type == TaskType.PROJECT_REVIEW
        and conversation_state.current_project == "local-rag-assistant"
    ):
        focused_project_sources = ["projects/local_rag_assistant.md"]
    forced_project_sections = []
    if focused_project_sources:
        forced_project_sections = get_sections_by_source_files(focused_project_sources, limit_per_source=8)

    retrieved_sections = select_sections_for_question(
        intent_text,
        forced_resume_sections
        + forced_context_sections
        + forced_project_sections
        + candidate_sections,
        current_resume_sources=current_resume_sources,
    )
    if not retrieved_sections:
        raise RuntimeError("未检索到相关片段，请换一种问法。")
    return retrieved_sections


def format_sources(sections: list[dict]) -> list[dict]:
    return [
        {
            "source_file": section["source_file"],
            "title": section["title"],
            "score": section.get("score"),
        }
        for section in sections
    ]


def ask_with_rag(question: str, history: list[dict] | None = None) -> dict:
    api_key = get_api_key()
    safe_history = normalize_history(history or [])
    task_type = detect_task_type(question, safe_history)
    conversation_state = build_conversation_state(question, safe_history)
    context_plan = build_context_plan(task_type, conversation_state)

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

    if not should_use_rag(question, safe_history, task_type):
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
    if context_plan.require_current_resume or is_current_resume_required(intent_text):
        if not current_resume_sources:
            raise RuntimeError("请先在简历中心设置当前简历。")
        forced_resume_sections = get_sections_by_source_files(current_resume_sources, limit_per_source=5)
        if not forced_resume_sections:
            raise RuntimeError("当前简历尚未进入向量索引，请先到索引状态页更新索引。")

    forced_context_sections = get_forced_context_sections(context_plan)
    focused_project_sources = get_focused_project_sources(intent_text)
    if (
        not forced_context_sections
        and task_type == TaskType.PROJECT_REVIEW
        and conversation_state.current_project == "local-rag-assistant"
    ):
        focused_project_sources = ["projects/local_rag_assistant.md"]
    forced_project_sections = []
    if focused_project_sources:
        forced_project_sections = get_sections_by_source_files(focused_project_sources, limit_per_source=8)

    retrieved_sections = select_sections_for_question(
        intent_text,
        forced_resume_sections
        + forced_context_sections
        + forced_project_sections
        + candidate_sections,
        current_resume_sources=current_resume_sources,
    )
    if not retrieved_sections:
        raise RuntimeError("未检索到相关片段，请换一种问法。")

    prompt = build_prompt_for_task(
        task_type,
        build_question_for_prompt(question, intent_text),
        retrieved_sections,
        history_text=format_history_for_prompt(safe_history),
    )
    messages = [{"role": "user", "content": prompt}]
    generation_start = time.perf_counter()
    model_result = ask_model_messages_result(api_key, messages)
    answer = model_result["content"]
    prepared = {
        "messages": messages,
        "task_type": task_type,
        "question": question,
    }
    answer, continuation_truncated = complete_answer_once(api_key, messages, answer, prepared)
    generation_seconds = time.perf_counter() - generation_start
    truncated = continuation_truncated or needs_continuation(answer, prepared)
    log_answer_to_console(
        phase="sync-rag",
        question=question,
        prepared={**prepared, "mode": "rag"},
        answer=answer,
        truncated=truncated,
        finish_reason=model_result.get("finish_reason"),
        continuation_attempts=1 if continuation_truncated else 0,
    )

    return {
        "answer": answer,
        "truncated": truncated,
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


def get_forced_context_sections(context_plan) -> list[dict]:
    forced_sections = []
    for group in context_plan.forced_source_groups:
        forced_sections.extend(
            get_sections_by_source_files(
                list(group.source_files),
                limit_per_source=group.limit_per_source,
            )
        )
    return forced_sections


def ask_with_chat(api_key: str, question: str, history: list[dict]) -> dict:
    messages = build_chat_messages(question, history)
    generation_start = time.perf_counter()
    model_result = ask_model_messages_result(api_key, messages)
    answer = model_result["content"]
    prepared = {
        "messages": messages,
        "task_type": TaskType.GENERAL_CHAT,
        "question": question,
    }
    answer, continuation_truncated = complete_answer_once(api_key, messages, answer, prepared)
    generation_seconds = time.perf_counter() - generation_start
    truncated = continuation_truncated or needs_continuation(answer, prepared)
    log_answer_to_console(
        phase="sync-chat",
        question=question,
        prepared={**prepared, "mode": "chat"},
        answer=answer,
        truncated=truncated,
        finish_reason=model_result.get("finish_reason"),
        continuation_attempts=1 if continuation_truncated else 0,
    )
    return {
        "answer": answer,
        "truncated": truncated,
        "sources": [],
        "retrieval_seconds": 0.0,
        "generation_seconds": generation_seconds,
        "mode": "chat",
    }


def looks_incomplete_answer(answer: str) -> bool:
    text = answer.strip()
    if not text:
        return True

    compact = text.rstrip(" \t\r\n`*_>）)]】》\"'")
    if not compact:
        return True

    if compact.endswith(DANGLING_ANSWER_ENDINGS):
        return True

    return any(compact.endswith(suffix) for suffix in DANGLING_ANSWER_SUFFIXES)


def should_use_rag(
    question: str,
    history: list[dict] | None = None,
    task_type: TaskType | None = None,
) -> bool:
    if task_type and task_requires_rag(task_type):
        return True

    if is_technical_explanation_question(question) or is_knowledge_base_guidance_question(question):
        return True

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
        "项目资料",
        "基于资料",
        "结合资料",
        "结合项目资料",
        "知识库",
        "资料不足",
        "根据我的",
        "匹配",
        "修改简历",
        "优化简历",
        "适合哪些",
        "核心能力",
    ]
    if any(keyword in question for keyword in rag_keywords):
        return True

    contextual_keywords = [
        "这个",
        "它",
        "刚才",
        "上面",
        "继续",
        "那",
        "还有",
        "进一步",
        "为什么",
        "哪些地方",
        "优先",
        "怎么改",
        "应该",
        "局限性",
        "后续",
        "改进方向",
        "面试",
    ]
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
    contextual_keywords = [
        "这个",
        "这个项目",
        "它",
        "为什么",
        "哪些地方",
        "优先",
        "怎么改",
        "修改",
        "优化",
        "那我",
        "继续",
        "具体",
        "追问",
        "局限性",
        "后续",
        "改进方向",
        "面试",
        "口述",
        "解释",
    ]
    return any(keyword in question for keyword in contextual_keywords)


def is_current_resume_required(intent_text: str) -> bool:
    resume_keywords = ["我的简历", "根据我的简历", "这份简历", "简历修改", "修改简历", "优化简历", "当前简历"]
    return any(keyword in intent_text for keyword in resume_keywords)


def build_question_for_prompt(question: str, intent_text: str) -> str:
    if intent_text == question:
        return question
    return f"{intent_text}\n请回答当前追问：{question}"
