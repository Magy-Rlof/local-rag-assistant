import os
import re
import sys
import time
from pathlib import Path

import requests
from qdrant_client import QdrantClient, models


CHAT_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
EMBEDDING_MODEL = "BAAI/bge-m3"
COLLECTION_NAME = "local_rag_sections"
VECTOR_SIZE = 1024
REQUEST_TIMEOUT = 90
CHAT_MAX_TOKENS = 1400
EMBEDDING_MAX_ATTEMPTS = 2
EMBEDDING_RETRY_DELAY_SECONDS = 1.5
DEFAULT_TOP_K = 4
CAREER_ANALYSIS_CANDIDATE_K = 20
CAREER_ANALYSIS_TOP_K = 8
JOB_RECOMMENDATION_TOP_K = 18
RESUME_IMPROVEMENT_TOP_K = 16
JOB_MATCH_TOP_K = 16
TECHNICAL_EXPLANATION_TOP_K = 14
KNOWLEDGE_BASE_GUIDANCE_TOP_K = 14
MAX_SECTION_CHARS = 700
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRIVATE_DATA_DIR = Path(__file__).resolve().parent.parent / "private_data"
QDRANT_PATH = Path(__file__).resolve().parent.parent / "qdrant_storage"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
TARGET_JOB_RECOMMENDATION_SOURCES = [
    "job_descriptions/ai_application_engineer.md",
    "job_descriptions/java_backend_engineer.md",
    "job_descriptions/python_backend_engineer.md",
    "job_descriptions/industry_software_engineer.md",
    "job_descriptions/implementation_consultant.md",
]
TARGET_RESUME_IMPROVEMENT_SOURCES = [
    "job_descriptions/ai_application_engineer.md",
    "projects/local_rag_assistant.md",
]
TARGET_JOB_MATCH_SOURCES = [
    "job_descriptions/ai_application_engineer.md",
    "projects/local_rag_assistant.md",
]
TECHNICAL_EXPLANATION_SOURCES = [
    "learning_notes/ai_app_frameworks.md",
    "projects/local_rag_assistant.md",
]
KNOWLEDGE_BASE_GUIDANCE_SOURCES = [
    "learning_notes/knowledge_base_maintenance.md",
    "projects/local_rag_assistant.md",
    "learning_notes/rag_basics.md",
]


def get_api_key() -> str:
    load_local_env()
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 SILICONFLOW_API_KEY，请先配置环境变量。")
    return api_key.strip()


def load_local_env() -> None:
    if not ENV_FILE.exists():
        return

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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


def build_rag_prompt(
    question: str,
    sections: list[dict],
    include_citations: bool = True,
    history_text: str = "",
    allow_general_knowledge: bool = False,
) -> str:
    context = "\n\n".join(
        (
            f"来源文件：{section['source_file']}\n"
            f"来源标题：{section['title']}\n"
            f"内容：\n{truncate_text(section['content'])}"
        )
        for section in sections
    )
    citation_rule = (
        "- 回答后列出引用来源文件和标题"
        if include_citations
        else "- 不要在回答正文中列出引用来源，系统会在界面右侧单独展示引用来源"
    )
    task_rule = build_task_rule(question)
    history_block = f"\n对话历史：\n{history_text}\n" if history_text else ""
    knowledge_rule = (
        "- 先基于资料回答；如果需要解释通用技术概念，可以在“模型通用知识补充”小节中补充，但必须明确这部分不是资料原文\n"
        "- 不要把模型通用知识伪装成资料中的事实"
        if allow_general_knowledge
        else "- 只能使用资料中的信息回答\n- 如果资料不足，请明确说明“当前资料不足，无法确定”"
    )
    return f"""请基于给定资料回答用户问题。

要求：
{knowledge_rule}
{citation_rule}
- 不要编造资料中没有的信息
{task_rule}
{history_block}

资料：
{context}

用户问题：
{question}
"""


def build_task_rule(question: str) -> str:
    resume_improvement_keywords = ["优先修改", "哪些地方", "怎么改", "修改简历", "优化简历", "简历修改", "修改哪些"]
    if any(keyword in question for keyword in resume_improvement_keywords):
        return (
            "- 如果用户询问简历修改或优化建议，只要资料中包含当前简历内容，就必须给出有限但可执行的建议，"
            "不要因为没有完整 JD 就直接回答资料不足\n"
            "- 简历优化类回答请按“优先修改项 / 修改原因 / 示例表达 / 对应岗位”组织\n"
            "- 如果岗位资料不足，可以明确说明建议是基于当前简历和已检索到的岗位资料得出的"
        )

    if any(keyword in question for keyword in ["适合哪些岗位", "适合哪些", "更适合"]):
        return (
            "- 岗位推荐类回答请区分“优先推荐 / 可以尝试 / 暂不优先”，并简要说明依据\n"
            "- 如果资料中包含当前简历，必须以当前简历为主要依据"
        )

    return ""


def truncate_text(text: str, max_chars: int = MAX_SECTION_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...（内容已截断）"


def ask_model_messages_result(api_key: str, messages: list[dict], temperature: float = 0.3) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "max_tokens": CHAT_MAX_TOKENS,
        "temperature": temperature,
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
        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return {
                "content": content.strip(),
                "truncated": choice.get("finish_reason") == "length",
            }

    raise RuntimeError(f"无法解析模型返回结果：{data}")


def ask_model_result(api_key: str, prompt: str) -> dict:
    return ask_model_messages_result(
        api_key,
        [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )


def ask_model(api_key: str, prompt: str) -> str:
    return ask_model_result(api_key, prompt)["content"]


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

    last_error = None
    for attempt in range(1, EMBEDDING_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(EMBEDDING_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            break
        except (requests.Timeout, requests.RequestException) as exc:
            last_error = exc
            if attempt >= EMBEDDING_MAX_ATTEMPTS:
                raise
            time.sleep(EMBEDDING_RETRY_DELAY_SECONDS)
    else:
        raise RuntimeError(f"Embedding API 调用失败：{last_error}")

    response.raise_for_status()
    data = response.json()

    embeddings = data.get("data", [])
    if not embeddings or "embedding" not in embeddings[0]:
        raise RuntimeError(f"无法解析 Embedding 返回结果：{data}")

    embedding = embeddings[0]["embedding"]
    if len(embedding) != VECTOR_SIZE:
        raise RuntimeError(f"Embedding 维度异常：期望 {VECTOR_SIZE}，实际 {len(embedding)}")
    return embedding


def search_qdrant(query_vector: list[float], top_k: int = DEFAULT_TOP_K) -> list[dict]:
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


def get_sections_by_source_files(source_files: list[str], limit_per_source: int = 5) -> list[dict]:
    if not source_files:
        return []

    client = QdrantClient(path=str(QDRANT_PATH))
    if not client.collection_exists(COLLECTION_NAME):
        raise RuntimeError("未找到 Qdrant 索引，请先运行 src/build_index.py。")

    sections = []
    for source_file in source_files:
        records, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_file",
                        match=models.MatchValue(value=source_file),
                    )
                ]
            ),
            limit=limit_per_source,
            with_payload=True,
            with_vectors=False,
        )
        for record in records:
            payload = record.payload or {}
            sections.append(
                {
                    "source_file": payload.get("source_file", "unknown"),
                    "title": payload.get("title", "unknown"),
                    "content": payload.get("content", ""),
                    "score": None,
                }
            )
    return sections


def is_career_analysis_question(question: str) -> bool:
    keywords = ["简历", "适合", "岗位", "匹配", "修改", "优化", "求职"]
    return any(keyword in question for keyword in keywords)


def is_job_recommendation_question(question: str) -> bool:
    keywords = [
        "适合哪些岗位",
        "更适合哪些岗位",
        "推荐岗位",
        "岗位推荐",
        "优先推荐",
        "可以尝试",
        "暂不优先",
    ]
    return any(keyword in question for keyword in keywords)


def is_resume_improvement_question(question: str) -> bool:
    keywords = [
        "修改简历",
        "优化简历",
        "简历应该怎么修改",
        "简历应该怎么改",
        "这份简历应该怎么修改",
        "这份简历应该怎么改",
        "优先修改项",
        "修改原因",
        "示例表达",
    ]
    return any(keyword in question for keyword in keywords)


def is_job_match_question(question: str) -> bool:
    keywords = [
        "匹配点",
        "有哪些匹配",
        "项目经历有哪些匹配",
        "项目经历和",
        "项目经历与",
        "岗位有哪些匹配",
    ]
    return any(keyword in question for keyword in keywords)


def is_technical_explanation_question(question: str) -> bool:
    framework_keywords = ["Dify", "dify", "LangChain", "langchain", "LlamaIndex", "llamaindex", "手写 RAG", "手写RAG"]
    comparison_keywords = ["区别", "对比", "有什么不同", "怎么选", "选择建议"]
    return any(keyword in question for keyword in framework_keywords) and any(
        keyword in question for keyword in comparison_keywords
    )


def is_knowledge_base_guidance_question(question: str) -> bool:
    knowledge_keywords = [
        "知识库",
        "资料库",
        "索引",
        "补充资料",
        "补充项目资料",
        "补充知识",
        "资料不足",
        "回答资料不足",
        "事实卡片",
    ]
    guidance_keywords = [
        "怎么补充",
        "如何补充",
        "怎么维护",
        "如何维护",
        "应该如何",
        "应该怎么",
        "更新索引",
        "包含哪些",
        "哪些部分",
        "模板",
    ]
    return any(keyword in question for keyword in knowledge_keywords) and any(
        keyword in question for keyword in guidance_keywords
    )


def select_sections_for_question(
    question: str,
    candidates: list[dict],
    current_resume_sources: list[str] | None = None,
) -> list[dict]:
    if not is_career_analysis_question(question):
        if is_technical_explanation_question(question):
            selected = take_sections_by_exact_sources(
                candidates,
                TECHNICAL_EXPLANATION_SOURCES,
                limit=TECHNICAL_EXPLANATION_TOP_K,
            )
            return dedupe_sections(selected)[:TECHNICAL_EXPLANATION_TOP_K] or candidates[:DEFAULT_TOP_K]

        if is_knowledge_base_guidance_question(question):
            selected = take_sections_by_exact_sources(
                candidates,
                KNOWLEDGE_BASE_GUIDANCE_SOURCES,
                limit=KNOWLEDGE_BASE_GUIDANCE_TOP_K,
            )
            return dedupe_sections(selected)[:KNOWLEDGE_BASE_GUIDANCE_TOP_K] or candidates[:DEFAULT_TOP_K]

        focused_project_sources = get_focused_project_sources(question)
        if focused_project_sources:
            focused_sections = take_sections_by_exact_sources(
                candidates,
                focused_project_sources,
                limit=CAREER_ANALYSIS_TOP_K,
            )
            if focused_sections:
                return focused_sections

        return candidates[:DEFAULT_TOP_K]

    selected = []
    current_resume_sources = current_resume_sources or []

    if is_job_recommendation_question(question):
        selected.extend(take_sections_by_exact_sources(candidates, current_resume_sources, limit=4))
        if not current_resume_sources:
            selected.extend(take_sections_by_prefix(candidates, "private_data/", limit=4))
        selected.extend(take_sections_by_exact_sources(candidates, ["projects/local_rag_assistant.md"], limit=2))
        selected.extend(
            take_sections_by_exact_sources(
                candidates,
                TARGET_JOB_RECOMMENDATION_SOURCES,
                limit=12,
            )
        )
        return dedupe_sections(selected)[:JOB_RECOMMENDATION_TOP_K] or candidates[:DEFAULT_TOP_K]

    if is_resume_improvement_question(question):
        selected.extend(take_sections_by_exact_sources(candidates, current_resume_sources, limit=5))
        if not current_resume_sources:
            selected.extend(take_sections_by_prefix(candidates, "private_data/", limit=4))
        selected.extend(
            take_sections_by_exact_sources(
                candidates,
                TARGET_RESUME_IMPROVEMENT_SOURCES,
                limit=10,
            )
        )
        return dedupe_sections(selected)[:RESUME_IMPROVEMENT_TOP_K] or candidates[:DEFAULT_TOP_K]

    if is_job_match_question(question):
        selected.extend(take_sections_by_exact_sources(candidates, current_resume_sources, limit=5))
        if not current_resume_sources:
            selected.extend(take_sections_by_prefix(candidates, "private_data/", limit=4))
        selected.extend(
            take_sections_by_exact_sources(
                candidates,
                TARGET_JOB_MATCH_SOURCES,
                limit=10,
            )
        )
        return dedupe_sections(selected)[:JOB_MATCH_TOP_K] or candidates[:DEFAULT_TOP_K]

    if is_technical_explanation_question(question):
        selected.extend(
            take_sections_by_exact_sources(
                candidates,
                TECHNICAL_EXPLANATION_SOURCES,
                limit=TECHNICAL_EXPLANATION_TOP_K,
            )
        )
        return dedupe_sections(selected)[:TECHNICAL_EXPLANATION_TOP_K] or candidates[:DEFAULT_TOP_K]

    if is_knowledge_base_guidance_question(question):
        selected.extend(
            take_sections_by_exact_sources(
                candidates,
                KNOWLEDGE_BASE_GUIDANCE_SOURCES,
                limit=KNOWLEDGE_BASE_GUIDANCE_TOP_K,
            )
        )
        return dedupe_sections(selected)[:KNOWLEDGE_BASE_GUIDANCE_TOP_K] or candidates[:DEFAULT_TOP_K]

    focused_project_sources = get_focused_project_sources(question)
    if focused_project_sources:
        focused_sections = take_sections_by_exact_sources(
            candidates,
            focused_project_sources,
            limit=CAREER_ANALYSIS_TOP_K,
        )
        if focused_sections:
            return focused_sections

    if "简历" in question:
        selected.extend(take_sections_by_exact_sources(candidates, current_resume_sources, limit=5))
        if not current_resume_sources:
            selected.extend(take_sections_by_prefix(candidates, "private_data/", limit=4))
        selected.extend(take_sections_by_prefix(candidates, "job_descriptions/", limit=2))
        selected.extend(take_sections_by_prefix(candidates, "projects/", limit=2))
        return dedupe_sections(selected)[:CAREER_ANALYSIS_TOP_K] or candidates[:DEFAULT_TOP_K]

    selected.extend(take_sections_by_prefix(candidates, "private_data/", limit=3))
    selected.extend(take_sections_by_prefix(candidates, "job_descriptions/", limit=4))

    if "项目" in question or "经历" in question:
        selected.extend(take_sections_by_prefix(candidates, "projects/", limit=2))

    return dedupe_sections(selected)[:CAREER_ANALYSIS_TOP_K] or candidates[:DEFAULT_TOP_K]


def get_focused_project_sources(question: str) -> list[str]:
    normalized_question = question.lower()
    project_source_map = {
        "projects/local_rag_assistant.md": [
            "local-rag-assistant",
            "local rag assistant",
            "local_rag_assistant",
            "local rag",
        ],
    }

    matched_sources = []
    for source_file, aliases in project_source_map.items():
        if any(alias in normalized_question for alias in aliases):
            matched_sources.append(source_file)
    return matched_sources


def take_sections_by_prefix(sections: list[dict], source_prefix: str, limit: int) -> list[dict]:
    matched_sections = []
    for section in sections:
        if section["source_file"].startswith(source_prefix):
            matched_sections.append(section)
        if len(matched_sections) >= limit:
            break
    return matched_sections


def take_sections_by_exact_sources(sections: list[dict], source_files: list[str], limit: int) -> list[dict]:
    if not source_files:
        return []

    source_set = set(source_files)
    matched_sections = []
    for section in sections:
        if section["source_file"] in source_set:
            matched_sections.append(section)
        if len(matched_sections) >= limit:
            break
    return matched_sections


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
        candidate_k = CAREER_ANALYSIS_CANDIDATE_K if is_career_analysis_question(question) else DEFAULT_TOP_K
        candidate_sections = search_qdrant(query_vector, top_k=candidate_k)
        retrieved_sections = select_sections_for_question(question, candidate_sections)
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
