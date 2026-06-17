import re

from .job_match_draft import build_job_match_draft
from .job_interview_llm import generate_interview_questions_with_llm_fallback


MAX_INTERVIEW_ITEMS = 8
CHOICE_COUNT = 5
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
    generated = generate_interview_questions_with_llm_fallback(draft_response)
    questions = generated["questions"]
    session = {
        "target_confirmation": draft["target_confirmation"],
        "generation_mode": generated["generation_mode"],
        "generation_model": generated["generation_model"],
        "generation_seconds": generated["generation_seconds"],
        "llm_attempted": generated.get("llm_attempted", False),
        "llm_repair_attempted": generated.get("llm_repair_attempted", False),
        "fallback_reason": generated.get("fallback_reason", ""),
        "fallback_detail": generated.get("fallback_detail", ""),
        "validation_errors": generated.get("validation_errors", []),
        "questions": questions,
        "answer_guidance": [
            "选择题和判断题用于快速校准岗位要求，不代表你已经具备对应能力。",
            "面试回答仍建议使用 STAR 结构：背景、任务、行动、结果。",
            "每个回答至少给出一个真实项目、具体动作和可核查证据。",
            "不会的内容可以说明学习计划或补齐路径，不要把未验证能力说成已经具备。",
        ],
        "safety_notes": [
            "本接口只做面试准备与回答反馈，不自动修改简历。",
            "LLM 面试题生成只在显式启用时调用；默认不发送完整真实简历，只发送岗位要求和简历证据状态摘要。",
            "本接口不访问招聘平台、不触发索引、不自动投递。",
            "反馈结果是启发式检查，不能替代真实面试官判断。",
        ],
    }
    return {
        "matched": True,
        "query": query,
        "target_job": draft_response["target_job"],
        "current_resume": draft_response["current_resume"],
        "session": session,
        "warnings": dedupe(filter_interview_warnings(draft_response["warnings"]) + generated["warnings"]),
        "generation_mode": generated["generation_mode"],
        "generation_model": generated["generation_model"],
        "generation_seconds": generated["generation_seconds"],
        "llm_attempted": generated.get("llm_attempted", False),
        "llm_repair_attempted": generated.get("llm_repair_attempted", False),
        "fallback_reason": generated.get("fallback_reason", ""),
        "fallback_detail": generated.get("fallback_detail", ""),
        "validation_errors": generated.get("validation_errors", []),
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
        if index <= CHOICE_COUNT:
            questions.append(build_choice_question(index, item))
        else:
            questions.append(build_true_false_question(index, item))
    return questions


def build_choice_question(index: int, requirement: str) -> dict:
    skill_area = extract_skill_area(requirement)
    question = f"针对岗位要求“{requirement}”，以下哪种面试回答最适合作为可核查表达？"
    options = [
        {
            "key": "A",
            "text": f"直接声称自己精通{skill_area}，不需要补充项目证据。",
        },
        {
            "key": "B",
            "text": f"结合一个真实项目说明自己如何接触或补齐{skill_area}，明确本人动作、工具和结果。",
        },
        {
            "key": "C",
            "text": "只复述岗位 JD 的原句，避免说明自己的实际经历。",
        },
        {
            "key": "D",
            "text": "把正在学习的能力直接写成已在生产环境长期使用。",
        },
    ]
    return {
        "question_id": index,
        "type": "single_choice",
        "skill_area": skill_area,
        "question": question,
        "options": options,
        "correct_answer": "B",
        "explanation": "B 同时给出真实项目、本人动作和证据边界，最符合岗位匹配和简历安全要求。",
        "source_requirement": requirement,
        "risk_hint": "不要把岗位要求直接改写成个人能力；缺少证据时只能作为学习计划或面试准备。",
        "requirement": requirement,
        "intent": "验证候选人是否能把岗位要求映射到真实项目、具体行动和证据。",
        "answer_checkpoints": [
            "是否给出真实项目或学习实践。",
            "是否说明本人具体负责的动作。",
            "是否给出工具、接口、数据、结果或引用来源等证据。",
            "是否避免夸大未验证能力。",
        ],
        "risk_reminder": "如果没有相关经历，应说明学习计划或补齐路径，不要编造项目经验。",
    }


def build_true_false_question(index: int, requirement: str) -> dict:
    skill_area = extract_skill_area(requirement)
    statement = f"如果当前简历没有证明“{skill_area}”的真实项目证据，也可以把该能力直接写入正式简历。"
    return {
        "question_id": index,
        "type": "true_false",
        "skill_area": skill_area,
        "question": statement,
        "options": [
            {"key": "正确", "text": "可以直接写入。"},
            {"key": "错误", "text": "不应直接写入，需要先补充真实证据。"},
        ],
        "correct_answer": "错误",
        "explanation": "证据不足时不能把岗位要求包装成个人能力；可以先用于面试准备、学习计划或证据补齐清单。",
        "source_requirement": requirement,
        "risk_hint": "简历表达必须由真实简历、项目资料或其他可信证据支撑。",
        "requirement": requirement,
        "intent": "检查候选人是否理解简历表达和面试准备之间的安全边界。",
        "answer_checkpoints": [
            "是否明确不能无证据写入简历。",
            "是否能区分面试准备、学习计划和正式简历表达。",
            "是否能指出需要补充真实项目证据。",
        ],
        "risk_reminder": "缺少证据时，不能把学习计划或岗位要求写成已具备能力。",
    }


def extract_skill_area(requirement: str) -> str:
    text = requirement or ""
    preferred_terms = [
        "RAG",
        "LLM",
        "多模态",
        "微调",
        "PyTorch",
        "TensorFlow",
        "Python",
        "C++",
        "Java",
        "Pandas",
        "Spark",
        "API",
        "AI pipeline",
        "云部署",
        "图像识别",
    ]
    lowered = text.lower()
    for term in preferred_terms:
        if term.lower() in lowered:
            return term
    cleaned = re.sub(r"\s+", " ", text).strip(" 。；;，,")
    return cleaned[:24] or "目标能力"


def filter_interview_warnings(warnings: list[str]) -> list[str]:
    blocked_terms = ("写入简历", "简历差异", "简历草稿", "覆盖真实简历")
    return [warning for warning in warnings if not any(term in warning for term in blocked_terms)]


def dedupe(values: list[str]) -> list[str]:
    results = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results


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
    keywords = [item for item in re.split(r"[、，；。:：（）()\s]+", requirement) if len(item) >= 4]
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
