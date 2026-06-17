import json
import re
import sys
import time
from copy import deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main import (  # noqa: E402
    ask_model_messages_result,
    get_api_key,
    get_llm_interview_max_tokens,
    get_llm_interview_model,
    get_llm_interview_timeout_seconds,
    is_llm_interview_repair_enabled,
    is_llm_interview_enabled,
    should_send_resume_to_llm_interview,
)

from .job_profile import build_job_skill_analysis  # noqa: E402
from .job_question_engine import build_rule_interview_question_set  # noqa: E402


DEFAULT_QUESTION_COUNT = 8
DEFAULT_CHOICE_COUNT = 5
FORBIDDEN_PHRASES = [
    "可以直接声称",
    "可以直接写入正式简历",
    "无需证据",
    "伪造",
    "编造经历",
    "绕过验证码",
    "绕过反爬",
    "Cookie",
    "Token",
    "账号密码",
]
ANSWER_KEYS = ["A", "B", "C", "D"]
TRUE_FALSE_KEYS = ["正确", "错误"]
INTERVIEW_CACHE_SCHEMA_VERSION = "job_interview_v1_rule_skillreq_cache_v1"
INTERVIEW_QUESTION_CACHE: dict[str, dict] = {}


def generate_interview_questions_with_llm_fallback(draft_response: dict) -> dict:
    draft = draft_response["draft"]
    warnings: list[str] = []
    cache_key = build_interview_cache_key(draft_response)
    cached = read_interview_question_cache(cache_key)
    if cached:
        return cached

    if not is_llm_interview_enabled():
        result = build_fallback_result(
            draft=draft,
            model="",
            started_at=None,
            fallback_reason="disabled",
            fallback_detail="LLM 面试题生成未启用，已使用本地规则回退。",
            warnings=["LLM 面试题生成未启用，已使用本地规则回退。"],
            llm_attempted=False,
        )
        write_interview_question_cache(cache_key, result)
        return result

    started_at = time.perf_counter()
    model = get_llm_interview_model()
    context = build_interview_context(draft_response)
    repair_attempted = False
    validation_errors: list[str] = []
    try:
        api_key = get_api_key()
        result = call_llm_interview_generator(api_key, model, context)
        validation = validate_interview_payload(result["content"], context)
        validation_errors = validation["errors"]
        if not validation["valid"] and is_llm_interview_repair_enabled():
            repair_attempted = True
            repaired = repair_llm_interview_json(api_key, model, context, result["content"], validation["errors"])
            validation = validate_interview_payload(repaired["content"], context)
            validation_errors = validation["errors"]
        if validation["valid"]:
            result = {
                "questions": validation["questions"],
                "generation_mode": "llm",
                "generation_model": model,
                "generation_seconds": time.perf_counter() - started_at,
                "warnings": warnings,
                "llm_attempted": True,
                "llm_repair_attempted": repair_attempted,
                "fallback_reason": "",
                "fallback_detail": "",
                "validation_errors": [],
                "cache_hit": False,
            }
            write_interview_question_cache(cache_key, result)
            return result
        if any("不是 JSON" in error or "JSON" in error and "不是" in error for error in validation_errors):
            fallback_reason = "json_parse_failed"
        else:
            fallback_reason = "repair_failed" if repair_attempted else "schema_validation_failed"
        fallback_detail = "LLM 面试题 JSON 校验失败，已使用本地规则回退：" + "；".join(validation_errors[:4])
        warnings.append(fallback_detail)
    except requests.Timeout as exc:
        fallback_reason = "timeout"
        fallback_detail = f"LLM 面试题生成超时，已使用本地规则回退：{summarize_exception(exc)}"
        warnings.append(fallback_detail)
    except Exception as exc:
        fallback_reason = "provider_error"
        fallback_detail = f"LLM 面试题生成失败，已使用本地规则回退：{summarize_exception(exc)}"
        warnings.append(fallback_detail)

    result = build_fallback_result(
        draft=draft,
        model=model,
        started_at=started_at,
        fallback_reason=fallback_reason,
        fallback_detail=fallback_detail,
        warnings=warnings,
        llm_attempted=True,
        repair_attempted=repair_attempted,
        validation_errors=validation_errors,
    )
    write_interview_question_cache(cache_key, result)
    return result


def build_fallback_result(
    draft: dict,
    model: str,
    started_at: float | None,
    fallback_reason: str,
    fallback_detail: str,
    warnings: list[str],
    llm_attempted: bool,
    repair_attempted: bool = False,
    validation_errors: list[str] | None = None,
) -> dict:
    return {
        "questions": build_rule_fallback_questions(draft),
        "generation_mode": "rule_fallback",
        "generation_model": model,
        "generation_seconds": time.perf_counter() - started_at if started_at else 0.0,
        "warnings": warnings,
        "llm_attempted": llm_attempted,
        "llm_repair_attempted": repair_attempted,
        "fallback_reason": fallback_reason,
        "fallback_detail": fallback_detail,
        "validation_errors": validation_errors or [],
        "cache_hit": False,
    }


def build_interview_cache_key(draft_response: dict) -> str:
    draft = draft_response["draft"]
    confirmation = draft.get("target_confirmation", {})
    cache_payload = {
        "schema_version": INTERVIEW_CACHE_SCHEMA_VERSION,
        "job_id": confirmation.get("source_job_id", ""),
        "marker": confirmation.get("marker", ""),
        "source_file": confirmation.get("source_file", ""),
        "source_url": confirmation.get("source_url", ""),
        "requirements": draft.get("job_core_requirements", []),
        "responsibilities": draft.get("job_core_responsibilities", []),
        "llm_enabled": is_llm_interview_enabled(),
        "llm_model": get_llm_interview_model() if is_llm_interview_enabled() else "",
        "repair_enabled": is_llm_interview_repair_enabled(),
        "send_resume": should_send_resume_to_llm_interview(),
    }
    raw = json.dumps(cache_payload, ensure_ascii=False, sort_keys=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def read_interview_question_cache(cache_key: str) -> dict | None:
    cached = INTERVIEW_QUESTION_CACHE.get(cache_key)
    if not cached:
        return None
    result = deepcopy(cached)
    result["cache_hit"] = True
    result["generation_seconds"] = 0.0
    return result


def write_interview_question_cache(cache_key: str, result: dict) -> None:
    cached = deepcopy(result)
    cached["cache_hit"] = False
    INTERVIEW_QUESTION_CACHE[cache_key] = cached


def clear_interview_question_cache() -> None:
    INTERVIEW_QUESTION_CACHE.clear()


def build_interview_context(draft_response: dict) -> dict:
    draft = draft_response["draft"]
    confirmation = draft["target_confirmation"]
    requirement_items = (draft["job_core_requirements"] + draft["job_core_responsibilities"])[:DEFAULT_QUESTION_COUNT]
    if not requirement_items:
        requirement_items = ["目标岗位资料中缺少明确要求，请围绕如何确认岗位要求和证据边界出题。"]
    requirement_items = repeat_to_count(requirement_items, DEFAULT_QUESTION_COUNT)
    numbered_requirements = [
        {"id": f"R{index}", "text": requirement}
        for index, requirement in enumerate(requirement_items, start=1)
    ]
    resume_state = draft["resume_revision_candidates"].get("resume_state", "未确认当前简历状态")
    if should_send_resume_to_llm_interview():
        resume_policy = "当前开关允许发送简历摘要，但本链路 v1 仍只发送证据状态，不发送完整简历正文。"
    else:
        resume_policy = "默认不发送完整真实简历，只发送当前简历证据状态摘要。"
    return {
        "job_id": confirmation.get("source_job_id", ""),
        "job_title": confirmation.get("title", ""),
        "company": confirmation.get("company", ""),
        "source_file": confirmation.get("source_file", ""),
        "requirements": requirement_items,
        "numbered_requirements": numbered_requirements,
        "requirement_map": {item["id"]: item["text"] for item in numbered_requirements},
        "resume_evidence_status_summary": resume_state,
        "resume_policy": resume_policy,
    }


def call_llm_interview_generator(api_key: str, model: str, context: dict) -> dict:
    return ask_model_messages_result(
        api_key,
        build_llm_interview_messages(context),
        temperature=0.55,
        model=model,
        max_tokens=get_llm_interview_max_tokens(),
        timeout=get_llm_interview_timeout_seconds(),
    )


def repair_llm_interview_json(api_key: str, model: str, context: dict, dirty_content: str, errors: list[str]) -> dict:
    messages = build_llm_interview_messages(context)
    messages.append(
        {
            "role": "user",
            "content": (
                "上一次输出未通过校验。只返回修复后的 JSON，不要解释。\n"
                f"校验错误：{json.dumps(errors, ensure_ascii=False)}\n"
                f"上一次输出：\n{dirty_content[:5000]}"
            ),
        }
    )
    return ask_model_messages_result(
        api_key,
        messages,
        temperature=0.25,
        model=model,
        max_tokens=get_llm_interview_max_tokens(),
        timeout=get_llm_interview_timeout_seconds(),
    )


def build_llm_interview_messages(context: dict) -> list[dict]:
    llm_context = {
        "job_id": context["job_id"],
        "job_title": context["job_title"],
        "company": context["company"],
        "requirements": context["numbered_requirements"],
        "resume_evidence_status_summary": context["resume_evidence_status_summary"],
        "resume_policy": context["resume_policy"],
    }
    schema = {
        "generation_mode": "llm",
        "job_id": context["job_id"],
        "job_title": context["job_title"],
        "summary": {
            "total": DEFAULT_QUESTION_COUNT,
            "single_choice": DEFAULT_CHOICE_COUNT,
            "true_false": DEFAULT_QUESTION_COUNT - DEFAULT_CHOICE_COUNT,
            "coverage": [],
        },
        "questions": [
            {
                "question_id": 1,
                "type": "single_choice",
                "difficulty": "基础|进阶|综合",
                "skill_area": "RAG",
                "question": "题干",
                "options": [
                    {"key": "A", "text": "选项 A"},
                    {"key": "B", "text": "选项 B"},
                    {"key": "C", "text": "选项 C"},
                    {"key": "D", "text": "选项 D"},
                ],
                "correct_answer": ["C"],
                "explanation": "解释为什么正确，为什么其他选项不合适。",
                "source_requirement_id": "R1",
                "risk_hint": "能力声称和简历写入边界。",
            }
        ],
        "safety_notes": [],
    }
    return [
        {
            "role": "system",
            "content": (
                "你是求职面试知识点出题器。你只能基于用户提供的岗位要求出题。"
                "题目应考查岗位相关概念、工程判断、技术流程、工具差异和落地注意点，"
                "不要只考查如何包装经历、如何回答面试官、如何声称能力。"
                "不得新增岗位事实，不得声称用户已具备某能力，不得引导伪造经历。"
                "输出必须是严格 JSON，不要 Markdown，不要代码块。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请生成 8 道中文面试模拟题：5 道单选题、3 道判断题。\n"
                "题目必须以知识点和工程判断为主，例如 RAG 流程、LLM 与微调/检索增强的区别、"
                "模型部署、API pipeline、数据处理、框架使用和工业场景验证。\n"
                "不要把题目写成“哪种回答最稳妥”“如何证明自己”“如何转化为面试表达”。\n"
                "题目要覆盖至少 4 个不同技能方向，不能套同一个模板，不能所有正确答案相同，不能所有选项重复。\n"
                "每题必须包含答案、解析、source_requirement_id 和风险提示。\n"
                "source_requirement_id 必须从 requirements 的 id 中选择，只返回 R1/R2 这类 ID，不要输出 source_refs。\n"
                "默认不发送完整真实简历；以下只提供简历证据状态摘要。\n\n"
                f"上下文 JSON：{json.dumps(llm_context, ensure_ascii=False)}\n\n"
                f"输出 schema 示例：{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]


def validate_interview_payload(content: str, context: dict) -> dict:
    errors: list[str] = []
    payload = parse_json_object(content)
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["LLM 输出不是 JSON 对象。"], "questions": []}

    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list):
        return {"valid": False, "errors": ["questions 不是数组。"], "questions": []}
    if len(raw_questions) != DEFAULT_QUESTION_COUNT:
        errors.append(f"questions 数量应为 {DEFAULT_QUESTION_COUNT}，实际为 {len(raw_questions)}。")

    allowed_requirements = context["requirements"]
    requirement_map = context.get("requirement_map", {})
    normalized_questions: list[dict] = []
    for index, raw_question in enumerate(raw_questions[:DEFAULT_QUESTION_COUNT], start=1):
        normalized = normalize_question(raw_question, index, context, allowed_requirements, requirement_map)
        if normalized["errors"]:
            errors.extend([f"Q{index}: {error}" for error in normalized["errors"]])
        else:
            normalized_questions.append(normalized["question"])

    errors.extend(validate_quality(normalized_questions))
    return {"valid": not errors, "errors": errors, "questions": normalized_questions}


def parse_json_object(content: str) -> dict | None:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def normalize_question(
    raw_question: dict,
    index: int,
    context: dict,
    allowed_requirements: list[str],
    requirement_map: dict[str, str] | None = None,
) -> dict:
    errors: list[str] = []
    if not isinstance(raw_question, dict):
        return {"errors": ["题目不是对象。"], "question": {}}

    question_type = str(raw_question.get("type", "")).strip()
    if question_type not in {"single_choice", "true_false", "multiple_choice"}:
        errors.append("type 非法。")
    question_text = str(raw_question.get("question", "")).strip()
    if len(question_text) < 10:
        errors.append("question 过短。")
    source_requirement_id = str(raw_question.get("source_requirement_id", "")).strip().upper()
    source_requirement = ""
    if requirement_map and source_requirement_id in requirement_map:
        source_requirement = requirement_map[source_requirement_id]
    else:
        source_requirement = match_source_requirement(str(raw_question.get("source_requirement", "")).strip(), allowed_requirements)
        if source_requirement:
            source_requirement_id = find_requirement_id(source_requirement, requirement_map or {})
    if not source_requirement:
        errors.append("source_requirement_id 未匹配输入岗位要求。")

    options = normalize_options(raw_question.get("options"), question_type)
    correct_answer = normalize_correct_answer(raw_question.get("correct_answer"), question_type, options)
    if not correct_answer:
        errors.append("correct_answer 非法或不在选项中。")
    explanation = str(raw_question.get("explanation", "")).strip()
    if len(explanation) < 12:
        errors.append("explanation 过短。")
    skill_area = str(raw_question.get("skill_area", "")).strip() or extract_skill_area(source_requirement or question_text)
    risk_hint = str(raw_question.get("risk_hint", "")).strip() or "不得把岗位要求直接写成个人已具备能力；缺少证据时只能用于面试准备。"

    joined_text = json.dumps(raw_question, ensure_ascii=False)
    if any(phrase in joined_text for phrase in FORBIDDEN_PHRASES):
        errors.append("包含越界或不安全表述。")

    question = {
        "question_id": index,
        "type": question_type,
        "difficulty": str(raw_question.get("difficulty", "")).strip() or "综合",
        "skill_area": skill_area[:40],
        "question": question_text,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "source_requirement_id": source_requirement_id,
        "source_requirement": source_requirement,
        "source_refs": [build_source_ref(context, source_requirement)],
        "risk_hint": risk_hint,
        "requirement": source_requirement,
        "intent": "检验候选人是否理解岗位要求、证据边界和可核查表达。",
        "answer_checkpoints": [
            "是否能识别题目对应的岗位要求。",
            "是否能说明答案背后的证据边界。",
            "是否避免把岗位要求伪造成个人能力。",
        ],
        "risk_reminder": risk_hint,
    }
    return {"errors": errors, "question": question}


def normalize_options(options: object, question_type: str) -> list[dict[str, str]]:
    if question_type == "true_false":
        return [{"key": "正确", "text": "正确"}, {"key": "错误", "text": "错误"}]
    if not isinstance(options, list):
        return []
    normalized = []
    seen_keys = set()
    seen_texts = set()
    for option in options:
        if not isinstance(option, dict):
            continue
        key = str(option.get("key", "")).strip().upper()
        text = str(option.get("text", "")).strip()
        if key in ANSWER_KEYS and key not in seen_keys and text and text not in seen_texts:
            normalized.append({"key": key, "text": text})
            seen_keys.add(key)
            seen_texts.add(text)
    normalized.sort(key=lambda item: ANSWER_KEYS.index(item["key"]))
    return normalized if len(normalized) == 4 else []


def normalize_correct_answer(answer: object, question_type: str, options: list[dict[str, str]]) -> str | list[str]:
    if question_type == "true_false":
        if isinstance(answer, bool):
            return "正确" if answer else "错误"
        text = str(answer).strip()
        if text in TRUE_FALSE_KEYS:
            return text
        if text.lower() in {"true", "yes"}:
            return "正确"
        if text.lower() in {"false", "no"}:
            return "错误"
        return ""

    option_keys = {option["key"] for option in options}
    if isinstance(answer, list):
        answers = [str(item).strip().upper() for item in answer]
    else:
        answers = [str(answer).strip().upper()]
    answers = [item for item in answers if item in option_keys]
    if question_type == "multiple_choice":
        deduped = list(dict.fromkeys(answers))
        return deduped if len(deduped) >= 2 else []
    return answers[0] if len(answers) == 1 else ""


def match_source_requirement(candidate: str, allowed_requirements: list[str]) -> str:
    if not allowed_requirements:
        return ""
    if candidate in allowed_requirements:
        return candidate
    best_item = ""
    best_score = 0.0
    for item in allowed_requirements:
        score = SequenceMatcher(None, normalize_text(candidate), normalize_text(item)).ratio()
        if score > best_score:
            best_item = item
            best_score = score
    return best_item if best_score >= 0.42 else ""


def find_requirement_id(requirement: str, requirement_map: dict[str, str]) -> str:
    for requirement_id, text in requirement_map.items():
        if text == requirement:
            return requirement_id
    return ""


def summarize_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    return message[:500]


def validate_quality(questions: list[dict]) -> list[str]:
    errors: list[str] = []
    if len(questions) != DEFAULT_QUESTION_COUNT:
        return errors
    choice_questions = [item for item in questions if item["type"] == "single_choice"]
    true_false_questions = [item for item in questions if item["type"] == "true_false"]
    if len(choice_questions) < DEFAULT_CHOICE_COUNT:
        errors.append("单选题数量不足。")
    if len(true_false_questions) < DEFAULT_QUESTION_COUNT - DEFAULT_CHOICE_COUNT:
        errors.append("判断题数量不足。")

    choice_answers = [str(item["correct_answer"]) for item in choice_questions]
    if len(set(choice_answers)) <= 1 and len(choice_answers) > 1:
        errors.append("选择题正确答案全部相同。")

    option_sets = [tuple(option["text"] for option in item["options"]) for item in choice_questions]
    if len(set(option_sets)) <= 1 and len(option_sets) > 1:
        errors.append("选择题选项组高度重复。")

    question_stems = [normalize_text(item["question"])[:35] for item in questions]
    if len(set(question_stems)) < 5:
        errors.append("题干模板化程度过高。")

    skill_areas = [item["skill_area"] for item in questions if item["skill_area"]]
    if len(set(skill_areas)) < 4:
        errors.append("技能方向覆盖不足。")
    return errors


def build_rule_fallback_questions(draft: dict) -> list[dict]:
    target = draft["target_confirmation"]
    query = target.get("source_job_id") or target.get("marker") or target.get("title") or ""
    if query:
        analysis = build_job_skill_analysis(query)
        if analysis.get("matched") and analysis.get("skill_requirements"):
            question_set = build_rule_interview_question_set(
                analysis["job_profile"],
                analysis["skill_requirements"],
                question_count=DEFAULT_QUESTION_COUNT,
            )
            if question_set["questions"]:
                return question_set["questions"]

    source_items = (draft["job_core_requirements"] + draft["job_core_responsibilities"])[:DEFAULT_QUESTION_COUNT]
    if not source_items:
        source_items = ["目标岗位资料中缺少明确要求，请先补充岗位职责和任职要求。"]
    source_items = repeat_to_count(source_items, DEFAULT_QUESTION_COUNT)
    context = {
        "job_id": draft["target_confirmation"].get("source_job_id", ""),
        "source_file": draft["target_confirmation"].get("source_file", ""),
    }
    questions = []
    for index, requirement in enumerate(source_items, start=1):
        if index <= DEFAULT_CHOICE_COUNT:
            questions.append(build_varied_choice_question(index, requirement, context))
        else:
            questions.append(build_varied_true_false_question(index, requirement, context))
    return questions


def build_varied_choice_question(index: int, requirement: str, context: dict) -> dict:
    skill_area = extract_skill_area(requirement)
    answer_key = ["C", "A", "D", "B", "C"][index - 1]
    spec = build_knowledge_choice_spec(requirement, skill_area)
    options = place_correct_option(spec["correct"], spec["distractors"], answer_key, index)
    return build_question_payload(
        index=index,
        question_type="single_choice",
        skill_area=skill_area,
        question=spec["question"],
        options=options,
        correct_answer=answer_key,
        explanation=spec["explanation"],
        requirement=requirement,
        context=context,
        risk_hint="本题用于知识点自测；是否能写入简历仍必须由真实项目、简历或资料证据支撑。",
    )


def build_varied_true_false_question(index: int, requirement: str, context: dict) -> dict:
    skill_area = extract_skill_area(requirement)
    spec = build_knowledge_true_false_spec(requirement, skill_area, index)
    return build_question_payload(
        index=index,
        question_type="true_false",
        skill_area=skill_area,
        question=spec["question"],
        options=[{"key": "正确", "text": "正确"}, {"key": "错误", "text": "错误"}],
        correct_answer=spec["answer"],
        explanation=spec["explanation"],
        requirement=requirement,
        context=context,
        risk_hint="本题用于知识点自测；不得把未验证能力包装成真实经历，也不得自动修改简历或自动投递。",
    )


def build_knowledge_choice_spec(requirement: str, skill_area: str) -> dict:
    text = f"{requirement} {skill_area}".lower()
    if "rag" in text:
        return {
            "question": "在 RAG 系统中，检索增强生成的核心流程通常是什么？",
            "correct": "将文档切分并向量化，按查询召回相关片段，再把片段作为上下文交给模型生成回答。",
            "distractors": [
                "直接让模型重新训练全部参数，从而记住所有岗位资料。",
                "只把用户问题发给模型，不需要检索资料或引用来源。",
                "用关键词随机抽取文档，忽略语义相似度和来源追踪。",
            ],
            "explanation": "RAG 的关键是先检索可引用上下文，再让模型基于上下文回答；它不是自动微调模型参数。",
        }
    if any(term in text for term in ["llm", "微调", "多模态"]):
        return {
            "question": "关于 LLM 应用中的 RAG 与微调，下列说法哪一项更准确？",
            "correct": "RAG 主要在推理时补充外部上下文，微调通常会改变模型参数以适配特定任务或风格。",
            "distractors": [
                "RAG 和微调完全等价，二者都会直接改写模型权重。",
                "微调只是在提示词里增加文档片段，不涉及训练数据和参数更新。",
                "多模态模型只能处理文本，不能结合图像、语音或其他模态输入。",
            ],
            "explanation": "RAG 与微调解决的问题不同：RAG强调检索上下文，微调强调通过训练改变模型行为。",
        }
    if any(term in text for term in ["aws", "sagemaker", "amazon q", "云", "部署"]):
        return {
            "question": "把 AI 模型部署为线上服务时，哪一组指标最需要持续监控？",
            "correct": "延迟、吞吐、错误率、资源消耗、模型版本和输入输出漂移。",
            "distractors": [
                "只关注训练集准确率，上线后无需监控请求表现。",
                "只保存最终模型文件，不需要记录版本、配置或回滚方案。",
                "只要云平台能启动实例，就不需要接口健康检查。",
            ],
            "explanation": "模型部署是工程系统，需要同时关注服务稳定性、资源、版本和数据分布变化。",
        }
    if any(term in text for term in ["api", "pipeline", "端到端"]):
        return {
            "question": "在端到端 AI pipeline 中，接口契约通常应优先明确哪些内容？",
            "correct": "输入输出 schema、错误码、超时重试、幂等性、日志追踪和版本兼容策略。",
            "distractors": [
                "只定义接口名称，输入输出字段可以由调用方临时猜测。",
                "只关心模型回答文本，不需要处理错误、超时或重试。",
                "只在前端展示结果，不需要保存请求链路和审计信息。",
            ],
            "explanation": "AI pipeline 不只是模型调用，稳定的接口契约和可观测性决定系统能否可靠集成。",
        }
    if any(term in text for term in ["pytorch", "tensorflow", "深度学习"]):
        return {
            "question": "在 PyTorch 或 TensorFlow 训练深度学习模型时，训练模式与推理模式的核心区别是什么？",
            "correct": "训练模式会计算梯度并更新参数，推理模式通常关闭梯度更新并使用已训练参数预测。",
            "distractors": [
                "推理模式会自动扩大训练集，并重新标注所有样本。",
                "训练模式不需要损失函数，也不需要优化器。",
                "训练和推理完全相同，都必须每次更新模型参数。",
            ],
            "explanation": "深度学习框架的训练阶段涉及损失、梯度和参数更新；推理阶段重点是稳定输出预测结果。",
        }
    if any(term in text for term in ["python", "c++", "java"]):
        return {
            "question": "在 AI 工程落地中，Python 与 C++/Java 常见分工哪一项更合理？",
            "correct": "Python 常用于模型实验和服务编排，C++/Java 可用于高性能模块、工程集成或既有系统对接。",
            "distractors": [
                "Python 不能调用任何机器学习库，只能写脚本。",
                "C++/Java 一定比 Python 更适合所有模型训练任务。",
                "只要会 Python，就不需要理解接口、性能和部署约束。",
            ],
            "explanation": "AI 项目通常需要兼顾实验效率、服务化、性能和企业系统集成，不同语言承担不同角色。",
        }
    if any(term in text for term in ["pandas", "spark", "数据清洗", "特征工程"]):
        return {
            "question": "关于 Pandas 与 Spark 在数据处理中的适用场景，下列说法哪一项更准确？",
            "correct": "Pandas 更适合单机内存内数据处理，Spark 更适合分布式大数据处理和集群计算。",
            "distractors": [
                "Pandas 默认会把任务自动分发到集群所有节点。",
                "Spark 只能处理图片，不能处理结构化数据。",
                "特征工程只需要改列名，不需要处理缺失值、异常值或数据泄漏。",
            ],
            "explanation": "数据处理工具选择取决于数据规模、计算资源和任务形态，特征工程还需要关注质量和泄漏风险。",
        }
    if any(term in text for term in ["图像", "aoi", "质检", "工业"]):
        return {
            "question": "在工业 AOI 图像识别场景中，评估模型是否可落地时最应关注哪一项？",
            "correct": "缺陷检出率、误报率、样本覆盖、现场光照/设备变化和上线后的稳定性。",
            "distractors": [
                "只看一次 demo 的截图效果，不需要持续验证。",
                "只追求训练集准确率，不需要测试集和现场数据。",
                "只要模型能输出标签，就不需要和产线流程集成。",
            ],
            "explanation": "工业视觉落地需要关注真实场景稳定性、误报漏报成本和流程集成，而不是只看离线示例。",
        }
    if "开源" in text or "模型" in text:
        return {
            "question": "把开源 AI 模型集成到企业应用前，哪一组检查最关键？",
            "correct": "许可证、模型来源、输入输出格式、推理资源、延迟、隐私边界和更新维护策略。",
            "distractors": [
                "只看模型下载量，下载量高就可以直接上线。",
                "只复制示例代码，不需要确认许可证和数据边界。",
                "只在本机跑通一次，不需要评估线上资源和接口稳定性。",
            ],
            "explanation": "企业集成开源模型需要同时考虑合规、接口、资源、稳定性和后续维护。",
        }
    return {
        "question": f"针对岗位要求“{skill_area}”，判断一个 AI/ML 方案是否可落地时最关键的技术要素是什么？",
        "correct": "明确输入输出、数据质量、模型或算法选择、评估指标、部署方式和监控回滚机制。",
        "distractors": [
            "只写一个概念说明，不需要数据、指标或部署方案。",
            "只要模型名称足够新，就可以忽略业务约束。",
            "只在离线样例上成功一次，就可以认定生产可用。",
        ],
        "explanation": "AI/ML 落地需要同时满足数据、模型、工程、评估和运行维护要求。",
    }


def build_knowledge_true_false_spec(requirement: str, skill_area: str, index: int) -> dict:
    text = f"{requirement} {skill_area}".lower()
    if any(term in text for term in ["pytorch", "tensorflow", "深度学习"]):
        return {
            "question": "在深度学习训练中，只看训练集表现而不看验证集或测试集，容易高估模型泛化能力。",
            "answer": "正确",
            "explanation": "训练集表现不能代表泛化能力，验证集和测试集用于发现过拟合和评估真实效果。",
        }
    if any(term in text for term in ["python", "c++", "java"]):
        return {
            "question": "AI 算法落地通常不仅要求会写模型代码，还需要理解接口、数据流、性能和部署约束。",
            "answer": "正确",
            "explanation": "岗位中的算法落地强调工程交付，不能只停留在单个脚本或离线实验。",
        }
    if any(term in text for term in ["pandas", "spark", "数据清洗", "特征工程"]):
        return {
            "question": "特征工程中如果把测试集信息泄漏到训练过程，离线评估结果可能虚高。",
            "answer": "正确",
            "explanation": "数据泄漏会让模型提前看到不该看到的信息，导致评估结果失真。",
        }
    statements = [
        {
            "question": f"理解“{skill_area}”时，应同时关注概念定义、输入输出、评估指标和工程约束。",
            "answer": "正确",
            "explanation": "岗位知识点不仅是名词解释，还要能落到系统设计和结果验证。",
        },
        {
            "question": f"只要岗位 JD 提到“{skill_area}”，就可以跳过技术原理，直接把该能力写成已熟练掌握。",
            "answer": "错误",
            "explanation": "岗位要求不能自动变成个人能力；知识理解和简历声称都需要真实证据支撑。",
        },
    ]
    return statements[index % len(statements)]


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


def build_question_payload(
    index: int,
    question_type: str,
    skill_area: str,
    question: str,
    options: list[dict[str, str]],
    correct_answer: str | list[str],
    explanation: str,
    requirement: str,
    context: dict,
    risk_hint: str,
) -> dict:
    return {
        "question_id": index,
        "type": question_type,
        "difficulty": "综合",
        "skill_area": skill_area,
        "question": question,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "source_requirement_id": f"R{index}",
        "source_requirement": requirement,
        "source_refs": [build_source_ref(context, requirement)],
        "risk_hint": risk_hint,
        "requirement": requirement,
        "intent": "检验候选人是否理解岗位相关知识点和工程判断。",
        "answer_checkpoints": [
            "能否准确理解题目对应的技术概念。",
            "能否区分相近技术路线或工具的适用边界。",
            "能否把知识点落到工程流程、指标或约束上。",
        ],
        "risk_reminder": risk_hint,
    }


def build_source_ref(context: dict, requirement: str) -> dict[str, str]:
    return {
        "type": "job_description",
        "source_id": context.get("job_id", ""),
        "relative_path": context.get("source_file", ""),
        "quote": requirement,
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
        "工业",
    ]
    lowered = text.lower()
    for term in preferred_terms:
        if term.lower() in lowered:
            return term
    cleaned = re.sub(r"\s+", " ", text).strip(" 。；;，,")
    return cleaned[:24] or "目标能力"


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def repeat_to_count(items: list[str], count: int) -> list[str]:
    if not items:
        return []
    results = []
    index = 0
    while len(results) < count:
        results.append(items[index % len(items)])
        index += 1
    return results
