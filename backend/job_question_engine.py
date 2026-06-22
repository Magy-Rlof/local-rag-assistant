ANSWER_KEYS = ["A", "B", "C", "D"]
DEFAULT_RULE_QUESTION_COUNT = 8
DEFAULT_RULE_CHOICE_COUNT = 4

ANGLE_LIBRARY = {
    "RAG": [
        "文档切分与索引",
        "召回质量评估",
        "引用绑定",
        "fallback 与错误处理",
        "API 契约与输出格式",
        "Markdown 与来源追踪",
        "n8n 流程编排",
        "JSON 结构化返回",
    ],
    "后端": [
        "接口契约",
        "错误处理",
        "JSON schema",
        "版本兼容",
        "日志追踪",
        "超时重试",
        "幂等性",
        "系统集成",
    ],
    "工程化": [
        "任务编排",
        "异常恢复",
        "端到端验收",
        "可观测性",
        "输入输出约束",
        "自动化流程",
        "稳定性",
        "集成边界",
    ],
}

DEFAULT_ANGLES = [
    "概念边界",
    "输入输出",
    "工程流程",
    "质量评估",
    "错误处理",
    "部署运行",
    "风险控制",
    "业务验收",
]


def build_rule_interview_question_set(
    job_profile: dict,
    skill_requirements: list[dict],
    question_count: int = DEFAULT_RULE_QUESTION_COUNT,
) -> dict:
    selected_requirements = select_requirements(skill_requirements, question_count)
    questions = []
    for index, requirement in enumerate(selected_requirements, start=1):
        if index <= DEFAULT_RULE_CHOICE_COUNT:
            questions.append(build_single_choice_question(index, requirement, job_profile))
        elif index <= DEFAULT_RULE_CHOICE_COUNT + 2:
            questions.append(build_true_false_question(index, requirement, job_profile))
        else:
            questions.append(build_short_answer_question(index, requirement, job_profile))
    markdown_preview = render_questions_markdown(job_profile, questions)
    return {
        "job_profile": job_profile,
        "questions": questions,
        "markdown_preview": markdown_preview,
        "coverage": build_coverage(questions),
        "warnings": [] if questions else ["目标岗位资料中没有可用于出题的技能要求。"],
    }


def select_requirements(skill_requirements: list[dict], question_count: int) -> list[dict]:
    if not skill_requirements:
        return []
    unique_requirements = []
    seen_requirement_keys = set()
    for requirement in skill_requirements:
        key = requirement_key(requirement)
        if key in seen_requirement_keys:
            continue
        unique_requirements.append(requirement)
        seen_requirement_keys.add(key)

    selected = []
    seen_categories = set()
    for requirement in unique_requirements:
        category = requirement.get("category", "")
        if category and category in seen_categories:
            continue
        selected.append(with_question_angle(requirement, len(selected)))
        seen_categories.add(category)
        if len(selected) >= question_count:
            return selected
    selected_keys = {requirement_key(requirement) for requirement in selected}
    for requirement in unique_requirements:
        if requirement_key(requirement) not in selected_keys:
            selected.append(with_question_angle(requirement, len(selected)))
            selected_keys.add(requirement_key(requirement))
        if len(selected) >= question_count:
            return selected
    index = 0
    while len(selected) < question_count:
        base_requirement = unique_requirements[index % len(unique_requirements)]
        selected.append(with_question_angle(base_requirement, len(selected)))
        index += 1
    return selected


def requirement_key(requirement: dict) -> tuple[str, str, str]:
    return (
        normalize_text(requirement.get("skill_name", "")),
        normalize_text(requirement.get("category", "")),
        normalize_text(requirement.get("requirement_text", "")),
    )


def with_question_angle(requirement: dict, index: int) -> dict:
    category = requirement.get("category", "")
    angles = ANGLE_LIBRARY.get(category) or DEFAULT_ANGLES
    angle = angles[index % len(angles)]
    cloned = dict(requirement)
    cloned["question_angle"] = angle
    cloned["source_requirement_id"] = requirement.get("requirement_id", "")
    cloned["requirement_id"] = f"{requirement.get('requirement_id', 'REQ')}-{index + 1:02d}"
    return cloned


def build_single_choice_question(index: int, requirement: dict, job_profile: dict) -> dict:
    skill_name = requirement.get("skill_name", "岗位能力")
    category = requirement.get("category", "业务理解")
    spec = build_choice_spec(requirement, job_profile)
    answer_key = ["C", "A", "D", "B"][index % 4]
    options = place_correct_option(spec["correct"], spec["distractors"], answer_key, index)
    return build_question_payload(
        index=index,
        question_type="single_choice",
        stem=spec["stem"],
        options=options,
        correct_answer=answer_key,
        explanation=spec["explanation"],
        tested_skill=skill_name,
        category=category,
        difficulty=map_difficulty(requirement),
        requirement=requirement,
        job_profile=job_profile,
        safety_note="本题只检验岗位知识点理解，不代表候选人已经具备该能力。",
    )


def build_true_false_question(index: int, requirement: dict, job_profile: dict) -> dict:
    skill_name = requirement.get("skill_name", "岗位能力")
    category = requirement.get("category", "业务理解")
    angle = requirement.get("question_angle") or "工程约束"
    if index % 2 == 0:
        stem = f"在处理“{skill_name}”的{angle}任务时，只要离线样例跑通一次，就可以省略线上监控、评估和回滚方案。"
        answer = "错误"
        explanation = "岗位能力落地需要持续评估、监控和回滚设计，单次离线样例不能证明线上可用。"
    else:
        stem = f"围绕“{skill_name}”的{angle}做方案判断时，应同时说明输入输出、数据质量、评估指标和工程约束。"
        answer = "正确"
        explanation = "岗位要求不只考概念，还要求能把技术点落到工程流程和可验证指标上。"
    return build_question_payload(
        index=index,
        question_type="true_false",
        stem=stem,
        options=[{"key": "正确", "text": "正确"}, {"key": "错误", "text": "错误"}],
        correct_answer=answer,
        explanation=explanation,
        tested_skill=skill_name,
        category=category,
        difficulty=map_difficulty(requirement),
        requirement=requirement,
        job_profile=job_profile,
        safety_note="本题用于知识判断；不得把岗位要求自动写成个人经历。",
    )


def build_short_answer_question(index: int, requirement: dict, job_profile: dict) -> dict:
    skill_name = requirement.get("skill_name", "岗位能力")
    category = requirement.get("category", "业务理解")
    angle = requirement.get("question_angle") or "落地方案"
    stem = (
        f"针对目标岗位中“{skill_name}”的{angle}相关要求，"
        "请用 3-5 句话说明一个可落地方案应包含哪些技术步骤、验证指标和风险控制。"
    )
    expected_points = build_short_answer_points(requirement)
    explanation = "参考答案应覆盖：" + "；".join(expected_points)
    return build_question_payload(
        index=index,
        question_type="short_answer",
        stem=stem,
        options=[],
        correct_answer=expected_points,
        explanation=explanation,
        tested_skill=skill_name,
        category=category,
        difficulty=map_difficulty(requirement),
        requirement=requirement,
        job_profile=job_profile,
        safety_note="可说明学习计划或方案设计，但不能编造真实项目经历、指标或生产结果。",
    )


def build_choice_spec(requirement: dict, job_profile: dict) -> dict:
    text = f"{requirement.get('requirement_text', '')} {requirement.get('skill_name', '')}".lower()
    angle = requirement.get("question_angle", "")
    if "rag" in text:
        return build_rag_choice_spec(angle)
    if any(term in text for term in ["llm", "微调", "多模态", "openai", "deepseek"]):
        return {
            "stem": "关于 LLM 应用、RAG 与微调的关系，下列哪项说法更准确？",
            "correct": "RAG 在推理时补充外部上下文，微调通常通过训练改变模型参数或行为。",
            "distractors": [
                "RAG 和微调完全等价，二者都会直接更新模型权重。",
                "多模态模型只能处理文本，不能处理图像或其他模态。",
                "调用 LLM API 不需要考虑超时、错误处理、成本和输出格式。",
            ],
            "explanation": "LLM 应用需要区分检索增强、模型训练、API 工程和多模态输入输出边界。",
        }
    if any(term in text for term in ["部署", "aws", "sagemaker", "amazon q", "监控", "边缘计算"]):
        return {
            "stem": "将 AI 模型部署为稳定服务时，哪组内容最应纳入验收？",
            "correct": "延迟、吞吐、错误率、资源消耗、模型版本、监控告警和回滚策略。",
            "distractors": [
                "只看训练集准确率，上线后不需要监控线上请求。",
                "只保存模型文件，不需要记录配置、版本或发布流程。",
                "只要云实例能启动，就可以忽略接口健康检查和日志。",
            ],
            "explanation": "部署能力要求服务化、可观测、可回滚，而不是只证明模型能在本机运行。",
        }
    if any(term in text for term in ["pandas", "spark", "numpy", "数据", "特征"]):
        return {
            "stem": "关于工业数据清洗与特征工程，下列哪项最符合工程实践？",
            "correct": "先确认数据来源、缺失值、异常值、时间窗口和标签口径，再设计可复现处理流程。",
            "distractors": [
                "只要模型足够复杂，就可以跳过数据质量检查。",
                "测试集信息可以提前混入训练过程，以便提高离线指标。",
                "只改字段名就完成了特征工程，不需要关注数据泄漏。",
            ],
            "explanation": "数据质量和口径决定模型评估可信度，工业场景尤其要避免泄漏和不可复现。",
        }
    if any(term in text for term in ["api", "flask", "streamlit", "python", "java", "c++", "pipeline"]):
        return {
            "stem": "在端到端 AI 应用 pipeline 中，接口契约最需要明确哪些内容？",
            "correct": "输入输出 schema、错误码、超时重试、幂等性、日志追踪和版本兼容策略。",
            "distractors": [
                "只定义接口名称，字段含义可以由调用方临时猜测。",
                "只展示模型回答文本，不需要处理错误、超时或重试。",
                "只要本机 demo 可用，就不需要考虑企业系统集成。",
            ],
            "explanation": "AI pipeline 是工程系统，稳定接口和可观测性直接影响集成可靠性。",
        }
    if any(term in text for term in ["工业", "aoi", "质检", "plc", "scada", "iot", "iiot", "产线"]):
        return {
            "stem": "在工业 AI 场景评估模型是否可落地时，哪项判断最关键？",
            "correct": "同时验证现场数据覆盖、误报漏报成本、设备接口、稳定性和业务流程集成。",
            "distractors": [
                "只看一次 demo 截图效果，不需要现场数据复测。",
                "只追求训练集准确率，不需要验证集和真实产线反馈。",
                "模型能输出标签即可，不需要和 PLC/SCADA 或业务流程对接。",
            ],
            "explanation": "工业 AI 落地要考虑现场变化、误报漏报成本、系统接口和业务闭环。",
        }
    return {
        "stem": f"针对岗位要求“{requirement.get('skill_name', '岗位能力')}”，判断方案是否可落地时最关键的依据是什么？",
        "correct": "明确输入输出、数据质量、技术路线、评估指标、部署方式和运行风险。",
        "distractors": [
            "只列出热门模型名称，不需要说明数据和指标。",
            "只完成一次离线实验，就可以认定生产可用。",
            "只复述岗位 JD，不需要给出工程判断。",
        ],
        "explanation": "岗位知识点必须落到可验证的工程方案，不能只停留在名词或 JD 复述。",
    }


def build_short_answer_points(requirement: dict) -> list[str]:
    category = requirement.get("category", "")
    angle = requirement.get("question_angle", "")
    if category == "RAG":
        if angle:
            return [f"{angle}的关键设计", "召回质量和引用绑定", "回答评估与失败回退"]
        return ["文档切分与索引策略", "召回质量和引用绑定", "回答评估与失败回退"]
    if category == "LLM":
        return ["模型或 API 选择依据", "提示词和结构化输出约束", "超时、成本和安全边界"]
    if category == "数据处理":
        return ["数据来源和质量检查", "特征处理和防泄漏", "可复现评估指标"]
    if category == "部署":
        return ["服务化接口", "监控告警和日志", "版本管理与回滚"]
    if category == "工程化":
        return ["接口契约和任务编排", "异常处理和幂等性", "端到端验收指标"]
    if category == "业务理解":
        return ["业务目标和约束", "现场数据或流程验证", "效果指标和人工复核"]
    return ["问题定义和输入输出", "技术路线和评估指标", "部署风险和边界说明"]


def build_question_payload(
    index: int,
    question_type: str,
    stem: str,
    options: list[dict[str, str]],
    correct_answer: str | list[str],
    explanation: str,
    tested_skill: str,
    category: str,
    difficulty: str,
    requirement: dict,
    job_profile: dict,
    safety_note: str,
) -> dict:
    source_refs = requirement.get("source_refs") or [build_source_ref(job_profile, requirement)]
    requirement_text = requirement.get("requirement_text", "")
    source_requirement_id = requirement.get("source_requirement_id") or requirement.get("requirement_id", f"REQ{index:03d}")
    return {
        "question_id": index,
        "question_type": question_type,
        "type": question_type,
        "stem": stem,
        "question": stem,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "tested_skill": tested_skill,
        "skill_area": tested_skill,
        "source_requirement_id": source_requirement_id,
        "source_requirement": requirement_text,
        "source_refs": source_refs,
        "safety_note": safety_note,
        "risk_hint": safety_note,
        "requirement": requirement_text,
        "intent": f"检验候选人对{category}方向岗位知识点和工程判断的理解。",
        "answer_checkpoints": build_answer_checkpoints(question_type, requirement),
        "risk_reminder": safety_note,
    }


def build_rag_choice_spec(angle: str) -> dict:
    specs = {
        "文档切分与索引": {
            "stem": "在 RAG 系统中，为了让岗位资料可被稳定召回，文档切分与索引通常应怎样设计？",
            "correct": "按标题和语义边界切分文档，保留来源元数据并生成向量索引，便于按问题召回相关片段。",
            "distractors": [
                "把整份资料作为一个超长字符串直接塞进提示词，不需要索引。",
                "只保存文件名，不保存正文片段和来源元数据。",
                "每次随机截取岗位资料片段，不需要相似度检索。",
            ],
            "explanation": "RAG 依赖可检索的片段和来源元数据，切分与索引质量会直接影响召回。",
        },
        "召回质量评估": {
            "stem": "评估 RAG 召回质量时，哪种做法最能发现岗位问答中的检索问题？",
            "correct": "用代表性问题检查召回片段是否覆盖关键岗位要求，并记录缺失、噪声和排序问题。",
            "distractors": [
                "只看最终回答字数是否足够长，不检查引用片段。",
                "只要向量库有数据，就认定召回质量合格。",
                "把模型生成内容当成唯一依据，不回看原始岗位资料。",
            ],
            "explanation": "召回评估要核对问题、片段和来源，不能只看生成结果。",
        },
        "引用绑定": {
            "stem": "在岗位资料 RAG 问答中，为什么需要把回答和来源引用绑定？",
            "correct": "方便核对答案来自哪份岗位 Markdown 和哪条要求，降低生成内容不可追溯的风险。",
            "distractors": [
                "来源引用只是装饰字段，不影响岗位事实核验。",
                "只要回答看起来合理，就不需要保留来源。",
                "引用绑定会自动证明候选人已经具备岗位能力。",
            ],
            "explanation": "引用绑定用于事实核验和边界说明，不能替代候选人的真实能力证据。",
        },
        "fallback 与错误处理": {
            "stem": "当 LLM 生成面试题超时或校验失败时，RAG 应用更稳妥的 fallback 是什么？",
            "correct": "回退到本地规则生成可校验题目，并明确记录回退原因、来源要求和安全边界。",
            "distractors": [
                "继续无限重试 LLM，直到用户关闭页面。",
                "返回上一份岗位的旧题目，避免显示错误。",
                "忽略校验失败，直接展示结构不完整的题目。",
            ],
            "explanation": "稳定 fallback 要可解释、可校验，且不能复用错误岗位或污染当前会话。",
        },
        "API 契约与输出格式": {
            "stem": "岗位要求同时提到 HTTP API、JSON 和 RAG 时，接口契约最需要保证什么？",
            "correct": "请求参数、响应 schema、错误码、超时行为和来源引用字段稳定可解析。",
            "distractors": [
                "只返回自然语言文本，不需要任何结构化字段。",
                "字段名可以每次随机变化，由前端自行猜测。",
                "接口只要本机能跑通一次，就不需要错误响应。",
            ],
            "explanation": "AI 应用接口需要稳定契约，前端和后续工具才能可靠消费结果。",
        },
        "Markdown 与来源追踪": {
            "stem": "把岗位资料保存为 Markdown 后，哪项做法最有利于 RAG 来源追踪？",
            "correct": "保留标题层级、基本信息、岗位职责、任职要求和来源文件路径等元数据。",
            "distractors": [
                "只保留一段无标题文本，删除来源 ID 和文件路径。",
                "把所有岗位混成一个文件，避免区分具体岗位。",
                "只保存公司介绍，不保存任职要求。",
            ],
            "explanation": "结构化 Markdown 能帮助切分、索引、引用和确定性岗位查询。",
        },
        "n8n 流程编排": {
            "stem": "使用 n8n 编排 AI 应用流程时，哪种设计最能保证 RAG 数据链路稳定？",
            "correct": "明确节点输入输出、失败重试、去重策略、索引更新触发条件和执行日志。",
            "distractors": [
                "所有节点都只传递自由文本，不需要字段契约和错误处理。",
                "只要流程运行过一次，就不需要保留执行日志。",
                "索引是否更新可以完全交给用户猜测，不需要状态返回。",
            ],
            "explanation": "n8n 编排要关注数据契约、失败恢复、去重、索引状态和可观测性。",
        },
        "JSON 结构化返回": {
            "stem": "面试题生成接口返回 JSON 时，为什么要校验题目数组、题型和答案字段？",
            "correct": "确保前端预览、求职 Agent 和后续答题反馈能稳定读取同一批题目。",
            "distractors": [
                "JSON 校验只会增加复杂度，对前端展示没有影响。",
                "题目数量为 0 也可以当作成功生成。",
                "答案字段缺失时可以让用户自己猜。",
            ],
            "explanation": "结构化校验能避免空 session、字段缺失和错误题目污染交互流程。",
        },
    }
    return specs.get(angle) or specs["文档切分与索引"]


def build_answer_checkpoints(question_type: str, requirement: dict) -> list[str]:
    category = requirement.get("category", "岗位能力")
    if question_type == "short_answer":
        return [
            f"是否围绕{category}要求说明技术步骤。",
            "是否包含验证指标或质量标准。",
            "是否说明风险、边界或 fallback。",
        ]
    return [
        f"是否理解{category}方向的核心概念。",
        "是否能区分正确工程流程和常见误区。",
        "是否避免把岗位要求直接包装成个人能力。",
    ]


def build_source_ref(job_profile: dict, requirement: dict) -> dict[str, str]:
    return {
        "type": "job_description",
        "source_id": job_profile.get("job_id", ""),
        "relative_path": job_profile.get("source_file", ""),
        "section": "岗位要求",
        "quote": requirement.get("requirement_text", ""),
    }


def normalize_text(text: str) -> str:
    return "".join(str(text or "").lower().split())


def place_correct_option(correct: str, distractors: list[str], answer_key: str, offset: int) -> list[dict[str, str]]:
    rotated = distractors[offset % len(distractors) :] + distractors[: offset % len(distractors)]
    options = []
    distractor_index = 0
    for key in ANSWER_KEYS:
        if key == answer_key:
            options.append({"key": key, "text": correct})
        else:
            options.append({"key": key, "text": rotated[distractor_index]})
            distractor_index += 1
    return options


def map_difficulty(requirement: dict) -> str:
    value = requirement.get("difficulty_hint", "")
    if value == "advanced":
        return "进阶"
    if value == "intermediate":
        return "综合"
    return "基础"


def build_coverage(questions: list[dict]) -> dict:
    skills = []
    requirement_ids = []
    categories = []
    type_summary = {"single_choice": 0, "true_false": 0, "short_answer": 0}
    for question in questions:
        skill = question.get("tested_skill") or question.get("skill_area", "")
        requirement_id = question.get("source_requirement_id", "")
        category = question.get("intent", "")
        if skill and skill not in skills:
            skills.append(skill)
        if requirement_id and requirement_id not in requirement_ids:
            requirement_ids.append(requirement_id)
        if category and category not in categories:
            categories.append(category)
        question_type = question.get("question_type") or question.get("type")
        if question_type in type_summary:
            type_summary[question_type] += 1
    return {
        "skill_count": len(skills),
        "requirement_count": len(requirement_ids),
        "skills": skills,
        "requirement_ids": requirement_ids,
        "type_summary": type_summary,
    }


def render_questions_markdown(job_profile: dict, questions: list[dict]) -> str:
    title = job_profile.get("title") or "目标岗位"
    company = job_profile.get("company") or "来源未提供"
    lines = [
        f"# 面试题预览：{title}",
        "",
        "## 岗位",
        "",
        f"- 公司：{company}",
        f"- 来源岗位 ID：{job_profile.get('job_id') or '来源未提供'}",
        "",
        "## 题目",
    ]
    for question in questions:
        lines.extend(render_question_markdown(question))
    lines.extend(
        [
            "",
            "## 安全边界",
            "",
            "- 题目只基于已合法导入本地资料库的岗位资料生成。",
            "- 不访问招聘平台，不自动投递，不覆盖真实简历。",
            "- 不得把岗位要求直接写成候选人已具备能力。",
        ]
    )
    return "\n".join(lines)


def render_question_markdown(question: dict) -> list[str]:
    type_labels = {
        "single_choice": "单选题",
        "true_false": "判断题",
        "short_answer": "简答题",
    }
    question_type = question.get("question_type") or question.get("type", "")
    answer = question.get("correct_answer", "")
    if isinstance(answer, list):
        answer_text = "；".join(str(item) for item in answer)
    else:
        answer_text = str(answer)
    lines = [
        "",
        f"### Q{question.get('question_id')} {type_labels.get(question_type, '面试题')}",
        "",
        question.get("stem") or question.get("question", ""),
    ]
    options = question.get("options") or []
    if options:
        lines.append("")
        lines.append("选项：")
        lines.extend(f"- {option.get('key')}. {option.get('text')}" for option in options)
    lines.extend(
        [
            "",
            f"- 正确答案：{answer_text}",
            f"- 解析：{question.get('explanation', '')}",
            f"- 测试技能：{question.get('tested_skill') or question.get('skill_area', '')}",
            f"- 来源要求：{question.get('source_requirement', '')}",
        ]
    )
    lines.append(f"- 安全提示：{question.get('safety_note') or question.get('risk_hint', '')}")
    return lines


from .job_capability_question_engine import build_rule_interview_question_set  # noqa: E402,F401
