import re

from .job_match_draft import build_job_match_draft


MAX_INTERVIEW_ITEMS = 8
EVIDENCE_SIGNALS = [
    "项目",
    "负责",
    "实现",
    "设计",
    "开发",
    "接口",
    "部署",
    "测试",
    "优化",
    "指标",
    "引用",
    "RAG",
    "n8n",
    "FastAPI",
    "Qdrant",
    "API",
    "Markdown",
    "JSON",
]
OVERCLAIM_PATTERNS = [
    "精通",
    "专家",
    "完全掌握",
    "企业级",
    "生产级",
    "千万级",
    "百万级",
    "绝对",
    "保证",
]


def build_interview_session(query: str) -> dict:
    draft_response = build_job_match_draft(query)
    if not draft_response["matched"]:
        return {
            "matched": False,
            "query": query,
            "target_job": None,
            "current_resume": draft_response["current_resume"],
            "session": None,
            "warnings": draft_response["warnings"],
        }

    draft = draft_response["draft"]
    questions = build_questions(draft)
    session = {
        "target_confirmation": draft["target_confirmation"],
        "questions": questions,
        "answer_guidance": [
            "优先使用 STAR 结构：背景、任务、行动、结果。",
            "每个回答至少给出一个真实项目、具体动作和可核查证据。",
            "不会的内容可以说明学习计划，不要把未验证能力说成已具备。",
            "如果回答涉及简历修改，仍需区分可写入简历和只适合面试表达。",
        ],
        "safety_notes": [
            "本接口只做面试准备与回答反馈，不自动修改简历。",
            "本接口不调用 LLM、不访问招聘平台、不触发索引、不自动投递。",
            "反馈结果是启发式检查，不能替代真实面试官判断。",
        ],
    }
    return {
        "matched": True,
        "query": query,
        "target_job": draft_response["target_job"],
        "current_resume": draft_response["current_resume"],
        "session": session,
        "warnings": draft_response["warnings"],
    }


def build_interview_feedback(query: str, question_id: int, answer: str) -> dict:
    session_response = build_interview_session(query)
    if not session_response["matched"]:
        return {
            "matched": False,
            "query": query,
            "target_job": None,
            "question": None,
            "feedback": None,
            "warnings": session_response["warnings"],
        }

    questions = session_response["session"]["questions"]
    selected = next((question for question in questions if question["question_id"] == question_id), None)
    if not selected:
        raise ValueError("面试问题 ID 不存在。")

    cleaned_answer = re.sub(r"\s+", " ", answer or "").strip()
    feedback = analyze_answer(selected, cleaned_answer)
    return {
        "matched": True,
        "query": query,
        "target_job": session_response["target_job"],
        "question": selected,
        "feedback": feedback,
        "warnings": session_response["warnings"],
    }


def build_questions(draft: dict) -> list[dict]:
    requirements = draft["job_core_requirements"]
    responsibilities = draft["job_core_responsibilities"]
    source_items = (requirements + responsibilities)[:MAX_INTERVIEW_ITEMS]
    if not source_items:
        source_items = ["请先补充目标岗位的职责和任职要求，再开始面试模拟。"]

    questions = []
    for index, item in enumerate(source_items, start=1):
        questions.append(
            {
                "question_id": index,
                "question": f"请结合一个真实项目，说明你如何应对或补齐：{item}",
                "requirement": item,
                "intent": "验证候选人是否能把岗位要求映射到真实项目、具体行动和证据。",
                "answer_checkpoints": [
                    "是否给出真实项目或学习实践。",
                    "是否说明本人具体负责的动作。",
                    "是否给出工具、接口、数据、结果或引用来源等证据。",
                    "是否避免夸大未验证能力。",
                ],
                "risk_reminder": "如果没有相关经历，应说明学习计划或补齐路径，不要编造项目经验。",
            }
        )
    return questions


def analyze_answer(question: dict, answer: str) -> dict:
    strengths: list[str] = []
    improvements: list[str] = []
    risk_flags: list[str] = []

    if not answer:
        return {
            "summary": "未提供回答，无法评估。",
            "clarity": "缺失",
            "evidence_strength": "缺失",
            "boundary_risk": "无法判断",
            "strengths": [],
            "improvements": ["先给出一个真实项目或学习实践，再说明你的具体动作和结果。"],
            "risk_flags": ["空回答不能作为面试准备结果。"],
            "suggested_next_answer_shape": build_answer_shape(question),
        }

    length = len(answer)
    evidence_hits = [signal for signal in EVIDENCE_SIGNALS if signal.lower() in answer.lower()]
    has_number = bool(re.search(r"\d", answer))
    overclaim_hits = [pattern for pattern in OVERCLAIM_PATTERNS if pattern in answer]

    if length >= 80:
        strengths.append("回答长度足以展开一个具体例子。")
    else:
        improvements.append("回答偏短，建议补充项目背景、本人动作和结果。")

    if evidence_hits:
        strengths.append(f"回答中出现了可继续追问的证据信号：{'、'.join(evidence_hits[:5])}。")
    else:
        improvements.append("回答缺少项目、工具、接口、结果或引用来源等证据信号。")

    if has_number:
        strengths.append("回答中包含数字，可进一步说明指标、规模或时间。")
    else:
        improvements.append("建议补充可核查的数字，例如处理数量、耗时、准确率、响应时间或迭代次数。")

    if overclaim_hits:
        risk_flags.append(f"回答中出现可能夸大的表述：{'、'.join(overclaim_hits)}。")
    if mentions_requirement_without_evidence(question["requirement"], answer, evidence_hits):
        risk_flags.append("回答复述了岗位要求，但缺少能证明本人具备该能力的事实。")
    if not risk_flags:
        risk_flags.append("未发现明显夸大风险，但仍需用真实证据支撑。")

    return {
        "summary": build_summary(length, evidence_hits, risk_flags),
        "clarity": "较清楚" if length >= 80 else "需要补充",
        "evidence_strength": "较强" if evidence_hits and has_number else "需要补强",
        "boundary_risk": "存在风险" if any("夸大" in item or "缺少" in item for item in risk_flags) else "较低",
        "strengths": strengths,
        "improvements": improvements,
        "risk_flags": risk_flags,
        "suggested_next_answer_shape": build_answer_shape(question),
    }


def mentions_requirement_without_evidence(requirement: str, answer: str, evidence_hits: list[str]) -> bool:
    keywords = [item for item in re.split(r"[、/，,（）()\s]+", requirement) if len(item) >= 4]
    return any(keyword in answer for keyword in keywords[:5]) and not evidence_hits


def build_summary(length: int, evidence_hits: list[str], risk_flags: list[str]) -> str:
    if length < 40:
        return "回答过短，暂时更像结论，缺少过程和证据。"
    if evidence_hits and not any("夸大" in item for item in risk_flags):
        return "回答已有可追问证据，下一步应补充结果和边界。"
    return "回答已有内容，但需要补强事实证据并控制能力边界。"


def build_answer_shape(question: dict) -> list[str]:
    requirement = question["requirement"]
    return [
        f"先说明你遇到的具体场景，必须和“{requirement}”相关。",
        "再说明你本人负责的动作，避免只说团队做了什么。",
        "补充工具、接口、数据、指标、引用来源或结果。",
        "最后说明仍未覆盖的部分和后续补齐计划。",
    ]
