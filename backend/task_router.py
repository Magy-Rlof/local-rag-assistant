from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    PROJECT_REVIEW = "project_review"
    JOB_MATCH = "job_match"
    RESUME_IMPROVEMENT = "resume_improvement"
    JOB_RECOMMENDATION = "job_recommendation"
    TECHNICAL_EXPLANATION = "technical_explanation"
    KNOWLEDGE_BASE_GUIDANCE = "knowledge_base_guidance"
    INTERVIEW_SYNTHESIS = "interview_synthesis"
    GENERAL_CHAT = "general_chat"


@dataclass(frozen=True)
class ConversationState:
    current_project: str | None = None
    current_job: str | None = None
    current_resume_required: bool = False
    last_task_type: TaskType | None = None


@dataclass(frozen=True)
class ForcedSourceGroup:
    name: str
    source_files: tuple[str, ...]
    limit_per_source: int


@dataclass(frozen=True)
class ContextPlan:
    task_type: TaskType
    require_current_resume: bool = False
    forced_source_groups: tuple[ForcedSourceGroup, ...] = ()


PROJECT_ALIASES = {
    "local-rag-assistant": "local-rag-assistant",
    "local rag assistant": "local-rag-assistant",
    "local_rag_assistant": "local-rag-assistant",
    "local rag": "local-rag-assistant",
}

JOB_ALIASES = {
    "ai 应用开发": "ai_application_engineer",
    "ai应用开发": "ai_application_engineer",
    "ai 应用工程师": "ai_application_engineer",
    "ai应用工程师": "ai_application_engineer",
    "大模型应用": "ai_application_engineer",
    "java 后端": "java_backend_engineer",
    "java后端": "java_backend_engineer",
    "python 后端": "python_backend_engineer",
    "python后端": "python_backend_engineer",
    "行业软件": "industry_software_engineer",
    "实施顾问": "implementation_consultant",
}

LOCAL_RAG_ASSISTANT_SOURCE = "projects/local_rag_assistant.md"

JOB_RECOMMENDATION_SOURCES = (
    "job_descriptions/ai_application_engineer.md",
    "job_descriptions/java_backend_engineer.md",
    "job_descriptions/python_backend_engineer.md",
    "job_descriptions/industry_software_engineer.md",
    "job_descriptions/implementation_consultant.md",
)

RESUME_IMPROVEMENT_SOURCES = (
    "job_descriptions/ai_application_engineer.md",
    LOCAL_RAG_ASSISTANT_SOURCE,
)

JOB_MATCH_SOURCES = (
    "job_descriptions/ai_application_engineer.md",
    LOCAL_RAG_ASSISTANT_SOURCE,
)

TECHNICAL_EXPLANATION_SOURCES = (
    "learning_notes/ai_app_frameworks.md",
    LOCAL_RAG_ASSISTANT_SOURCE,
)

KNOWLEDGE_BASE_GUIDANCE_SOURCES = (
    "learning_notes/knowledge_base_maintenance.md",
    LOCAL_RAG_ASSISTANT_SOURCE,
    "learning_notes/rag_basics.md",
)


def detect_task_type(question: str, history: list[dict] | None = None) -> TaskType:
    history = history or []
    state = build_conversation_state(question, history)
    text = question
    lower_text = question.lower()

    if has_any(lower_text, ["dify", "langchain", "llamaindex", "手写 rag", "手写rag"]) and has_any(
        text, ["区别", "对比", "不同", "怎么选", "选择", "必要", "引入"]
    ):
        return TaskType.TECHNICAL_EXPLANATION

    if has_any(text, ["知识库", "资料库", "资料不足", "事实卡片", "补充资料", "补充知识", "更新索引"]) and has_any(
        text, ["如何", "怎么", "应该", "模板", "包含哪些", "补充", "维护", "更新", "验证"]
    ):
        return TaskType.KNOWLEDGE_BASE_GUIDANCE

    if has_any(text, ["适合哪些岗位", "更适合哪些岗位", "推荐岗位", "岗位推荐", "优先推荐", "可以尝试", "暂不优先"]):
        return TaskType.JOB_RECOMMENDATION

    if state.current_project and is_project_review_question(text):
        return TaskType.PROJECT_REVIEW

    if has_any(text, ["修改简历", "优化简历", "简历应该怎么", "这份简历", "优先修改项", "修改原因", "示例表达"]):
        return TaskType.RESUME_IMPROVEMENT

    if has_any(text, ["匹配点", "岗位匹配", "项目经历和", "项目经历与", "对应岗位要求", "有哪些匹配"]):
        return TaskType.JOB_MATCH

    if has_any(text, ["面试口述", "面试中可以", "2 分钟", "两分钟", "总结成", "整合前面", "可以这样说"]):
        return TaskType.INTERVIEW_SYNTHESIS

    if state.current_project and is_project_review_question(text):
        return TaskType.PROJECT_REVIEW

    if state.last_task_type and is_contextual_follow_up(question):
        if has_any(question, ["这个项目", "这个系统", "这个应用"]) and not state.current_project:
            return TaskType.GENERAL_CHAT
        return state.last_task_type

    return TaskType.GENERAL_CHAT


def build_conversation_state(question: str, history: list[dict] | None = None) -> ConversationState:
    history = history or []
    current_text = build_task_text(question, history)
    lower_text = current_text.lower()
    current_project = detect_project(lower_text)
    if current_project is None and is_default_project_reference(question):
        current_project = "local-rag-assistant"
    current_job = detect_job(lower_text)
    current_resume_required = has_any(current_text, ["我的简历", "当前简历", "这份简历", "简历应该", "修改简历", "优化简历"])
    last_task_type = detect_last_task_type(history)
    return ConversationState(
        current_project=current_project,
        current_job=current_job,
        current_resume_required=current_resume_required,
        last_task_type=last_task_type,
    )


def task_requires_rag(task_type: TaskType) -> bool:
    return task_type != TaskType.GENERAL_CHAT


def task_allows_general_knowledge(task_type: TaskType) -> bool:
    return task_type == TaskType.TECHNICAL_EXPLANATION


def build_context_plan(task_type: TaskType, state: ConversationState) -> ContextPlan:
    forced_groups: list[ForcedSourceGroup] = []
    require_current_resume = state.current_resume_required

    if task_type == TaskType.PROJECT_REVIEW:
        if state.current_project == "local-rag-assistant":
            forced_groups.append(
                ForcedSourceGroup(
                    name="project_fact_card",
                    source_files=(LOCAL_RAG_ASSISTANT_SOURCE,),
                    limit_per_source=8,
                )
            )

    elif task_type == TaskType.JOB_RECOMMENDATION:
        require_current_resume = True
        forced_groups.extend(
            [
                ForcedSourceGroup("project_fact_card", (LOCAL_RAG_ASSISTANT_SOURCE,), 3),
                ForcedSourceGroup("candidate_jobs", JOB_RECOMMENDATION_SOURCES, 3),
            ]
        )

    elif task_type == TaskType.JOB_MATCH:
        require_current_resume = True
        forced_groups.append(ForcedSourceGroup("target_job_and_project", JOB_MATCH_SOURCES, 5))

    elif task_type == TaskType.RESUME_IMPROVEMENT:
        require_current_resume = True
        forced_groups.append(ForcedSourceGroup("resume_target_context", RESUME_IMPROVEMENT_SOURCES, 5))

    elif task_type == TaskType.TECHNICAL_EXPLANATION:
        forced_groups.append(ForcedSourceGroup("framework_notes", TECHNICAL_EXPLANATION_SOURCES, 10))

    elif task_type == TaskType.KNOWLEDGE_BASE_GUIDANCE:
        forced_groups.append(ForcedSourceGroup("knowledge_base_guidance", KNOWLEDGE_BASE_GUIDANCE_SOURCES, 10))

    elif task_type == TaskType.INTERVIEW_SYNTHESIS:
        if state.current_project == "local-rag-assistant":
            forced_groups.append(
                ForcedSourceGroup("project_fact_card", (LOCAL_RAG_ASSISTANT_SOURCE,), 8)
            )
        if state.current_job == "ai_application_engineer":
            forced_groups.append(
                ForcedSourceGroup("target_job", ("job_descriptions/ai_application_engineer.md",), 5)
            )
        require_current_resume = state.current_resume_required

    return ContextPlan(
        task_type=task_type,
        require_current_resume=require_current_resume,
        forced_source_groups=tuple(forced_groups),
    )


def build_task_text(question: str, history: list[dict] | None = None) -> str:
    recent_history = "\n".join(
        item.get("content", "")
        for item in (history or [])[-6:]
        if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)
    )
    return f"{recent_history}\n当前问题：{question}" if recent_history else question


def detect_project(lower_text: str) -> str | None:
    for alias, project in PROJECT_ALIASES.items():
        if alias in lower_text:
            return project
    return None


def detect_job(text: str) -> str | None:
    lower_text = text.lower()
    for alias, job in JOB_ALIASES.items():
        if alias.lower() in lower_text:
            return job
    return None


def is_default_project_reference(question: str) -> bool:
    return is_project_review_question(question) and has_any(
        question,
        [
            "这个项目",
            "本项目",
            "该项目",
            "这个系统",
            "这个应用",
        ],
    )


def detect_last_task_type(history: list[dict]) -> TaskType | None:
    for item in reversed(history[-6:]):
        content = item.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        detected = detect_task_type_shallow(content)
        if detected != TaskType.GENERAL_CHAT:
            return detected
    return None


def detect_task_type_shallow(text: str) -> TaskType:
    lower_text = text.lower()
    if has_any(lower_text, ["dify", "langchain", "llamaindex", "手写 rag", "手写rag"]):
        return TaskType.TECHNICAL_EXPLANATION
    if has_any(text, ["知识库", "资料不足", "事实卡片", "更新索引"]):
        return TaskType.KNOWLEDGE_BASE_GUIDANCE
    if has_any(text, ["推荐岗位", "优先推荐", "可以尝试", "暂不优先"]):
        return TaskType.JOB_RECOMMENDATION
    if has_any(text, ["修改简历", "优化简历", "优先修改项", "示例表达"]):
        return TaskType.RESUME_IMPROVEMENT
    if has_any(text, ["匹配点", "岗位匹配", "项目经历"]):
        return TaskType.JOB_MATCH
    if detect_project(lower_text):
        return TaskType.PROJECT_REVIEW
    return TaskType.GENERAL_CHAT


def is_contextual_follow_up(question: str) -> bool:
    normalized = question.strip()
    return has_any(
        normalized,
        [
            "这个",
            "它",
            "刚才",
            "上面",
            "继续",
            "进一步",
            "为什么",
            "哪些地方",
            "怎么改",
            "应该",
            "局限性",
            "后续",
            "改进方向",
            "面试",
            "口述",
            "解释",
        ],
    )


def is_project_review_question(text: str) -> bool:
    normalized = text.lower()
    return has_any(
        normalized,
        [
            "解决了什么问题",
            "rag 流程",
            "rag流程",
            "项目局限",
            "局限性",
            "后续改进",
            "改进方向",
            "适合写进简历",
            "写进简历",
            "写进 ai",
            "简历表达",
            "面试时",
            "这个项目",
            "这个系统",
            "这个应用",
            "它的局限",
        ],
    )


def has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
