from .task_router import TaskType


MAX_SECTION_CHARS = 700


TASK_INSTRUCTIONS = {
    TaskType.PROJECT_REVIEW: """任务类型：项目复盘。
请优先围绕用户当前问题回答，不要机械输出所有栏目。
可用栏目包括：
- 结论
- 依据
- 适合写进简历的表达
- 面试时可以这样说
- 局限性
如果资料缺少某个字段，请指出缺少的具体字段，不要笼统回答“当前资料不足”。""",
    TaskType.JOB_MATCH: """任务类型：岗位匹配分析。
请按以下结构回答：
- 匹配点
- 依据
- 可以强化的表达
- 仍需补强
必须把简历、项目资料和目标岗位要求对应起来，不要只复述其中一方。""",
    TaskType.RESUME_IMPROVEMENT: """任务类型：简历修改建议。
请按以下结构回答：
- 优先修改项
- 修改原因
- 示例表达
- 对应岗位要求
只要资料中包含当前简历，就给出有限但可执行的建议。岗位资料不足时，需要说明建议依据有限。""",
    TaskType.JOB_RECOMMENDATION: """任务类型：岗位推荐。
请按以下结构回答：
- 优先推荐
- 可以尝试
- 暂不优先
- 原因
- 下一步补强建议
必须覆盖候选岗位集合，不能因为某一个岗位片段命中就只推荐该岗位。""",
    TaskType.TECHNICAL_EXPLANATION: """任务类型：技术解释。
请按以下结构回答：
- 基于资料
- 模型通用知识补充
- 结合当前项目的建议
必须明确区分资料内容和通用知识。不要把通用知识说成项目事实。""",
    TaskType.KNOWLEDGE_BASE_GUIDANCE: """任务类型：知识库维护指导。
请按以下结构回答：
- 应该补什么
- 放在哪里
- 事实卡片模板
- 如何更新索引
- 如何验证
- 注意事项
不得编造不存在的脚本或 API。当前真实入口包括 src/build_index.py、POST /api/index/build、Web 工作台的索引状态页。""",
    TaskType.INTERVIEW_SYNTHESIS: """任务类型：面试表达整合。
请按以下结构回答：
- 可直接说的一段话
- 不能夸大的边界
- 如果被追问可以补充
表达要像真实面试口述，不要写成宣传文案。""",
    TaskType.GENERAL_CHAT: """任务类型：通用问答。
请简洁回答。涉及简历、岗位、项目资料时，应提醒需要基于已索引资料。""",
}


def build_prompt_for_task(
    task_type: TaskType,
    question: str,
    sections: list[dict],
    history_text: str = "",
) -> str:
    context = format_context(sections)
    history_block = f"\n对话历史：\n{history_text}\n" if history_text else ""
    knowledge_rule = build_knowledge_rule(task_type)
    task_instruction = build_task_instruction(task_type, question)

    return f"""你是一个求职导向的 AI 应用开发学习助手。

请基于给定资料回答用户问题。

通用要求：
{knowledge_rule}
- 不要编造资料中没有的用户项目事实、简历事实或岗位事实。
- 不要夸大项目为生产级企业系统。
- 不要声称数据完全不出本地。
- 不要在回答正文中列出引用来源，系统会在界面右侧单独展示引用来源。
- 回答要直接、可执行、中文优先。
- 回答必须以完整句子结束，不要停在“并返回”“包括”“以及”“例如”“：”这类半句上。

{task_instruction}
{history_block}

资料：
{context}

用户问题：
{question}
"""


def build_task_instruction(task_type: TaskType, question: str) -> str:
    if task_type == TaskType.PROJECT_REVIEW:
        return build_project_review_instruction(question)
    return TASK_INSTRUCTIONS.get(task_type, TASK_INSTRUCTIONS[TaskType.GENERAL_CHAT])


def build_project_review_instruction(question: str) -> str:
    normalized = question.lower()
    if has_any(normalized, ["局限性", "局限", "不足", "边界", "不能做什么"]):
        return """任务类型：项目复盘 - 项目局限性。
只回答项目局限性，不要输出简历表达或面试表达，除非用户明确要求。
请按以下结构回答：
- 结论
- 主要局限
- 后续改进方向
回答控制在 5-8 条要点内。"""

    if has_any(normalized, ["解决了什么问题", "解决什么问题", "核心问题", "痛点"]):
        return """任务类型：项目复盘 - 解决的问题。
只回答项目解决的问题和项目价值，不要输出简历表达、面试表达或局限性，除非用户明确要求。
请按以下结构回答：
- 结论
- 解决的问题
- 项目价值
回答控制在 4-6 条要点内。"""

    if has_any(normalized, ["rag 流程", "rag流程", "流程是什么", "怎么实现", "实现流程"]):
        return """任务类型：项目复盘 - RAG 流程。
只解释该项目的 RAG 流程，不要扩展到简历表达或岗位匹配。
请按以下结构回答：
- 流程概览
- 每一步做什么
- 这个流程的工程价值
必须完整输出以上三个小节，不要只输出“流程概览”。
回答要简洁，避免泛泛解释 RAG 概念。
最后一句必须是：以上就是该项目的 RAG 流程。"""

    if has_any(normalized, ["适合写进简历", "简历怎么写", "写进简历", "简历表达"]):
        return """任务类型：项目复盘 - 简历表达。
请按以下结构回答：
- 是否适合写进简历
- 推荐表达
- 不要夸大的边界
表达要符合初级 AI 应用开发求职，不要包装成资深工程师。"""

    if has_any(normalized, ["面试", "口述", "可以这样说", "怎么讲"]):
        return """任务类型：项目复盘 - 面试表达。
请按以下结构回答：
- 可直接说的一段话
- 如果被追问可以补充
- 不能夸大的边界
回答要像真实面试口述，不要写成宣传文案。"""

    return """任务类型：项目复盘。
请只围绕用户当前问题回答，不要机械输出所有栏目。
可用栏目包括：结论、依据、项目价值、局限性、简历表达、面试表达。
只选择与当前问题直接相关的栏目。
如果资料缺少某个字段，请指出缺少的具体字段，不要笼统回答“当前资料不足”。"""


def build_knowledge_rule(task_type: TaskType) -> str:
    if task_type == TaskType.TECHNICAL_EXPLANATION:
        return (
            "- 先基于资料回答。\n"
            "- 如果资料不足以解释通用技术概念，可以在“模型通用知识补充”小节补充。\n"
            "- 通用知识补充必须明确标注，不得伪装成资料原文。"
        )
    return "- 只能使用资料中的事实回答。资料不足时，说明缺少哪类资料或哪个字段。"


def has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def format_context(sections: list[dict]) -> str:
    return "\n\n".join(
        (
            f"来源文件：{section.get('source_file', 'unknown')}\n"
            f"来源标题：{section.get('title', 'unknown')}\n"
            f"内容：\n{truncate_text(section.get('content', ''))}"
        )
        for section in sections
    )


def truncate_text(text: str, max_chars: int = MAX_SECTION_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...（内容已截断）"
