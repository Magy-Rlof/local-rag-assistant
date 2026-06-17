import re

from .job_matcher import build_job_match_context


MAX_REQUIREMENT_ITEMS = 12
MAX_INTERVIEW_QUESTIONS = 8
MAX_TEXT_CHARS = 120

HIGH_RISK_KEYWORDS = [
    "PyTorch",
    "Transformers",
    "Ollama",
    "vLLM",
    "LM Studio",
    "LangChain",
    "LlamaIndex",
    "Docker",
    "Linux",
    "Git",
    "C#",
    "C++",
    "多模态",
    "图像",
    "工业AI",
    "智能制造",
    "视觉AI",
    "私有化部署",
    "微调",
    "推理优化",
    "内网",
]


def build_job_match_draft(query: str) -> dict:
    context = build_job_match_context(query)
    if not context["matched"]:
        return {
            "matched": False,
            "query": query,
            "target_job": None,
            "current_resume": context["current_resume"],
            "draft": None,
            "warnings": context["warnings"],
        }

    target_job = context["target_job"]
    job_evidence = context["job_evidence"]
    current_resume = context["current_resume"]
    requirement_items = extract_requirement_items(job_evidence["requirements_text"], job_evidence["raw_description_excerpt"])
    responsibility_items = extract_requirement_items(job_evidence["responsibilities_text"], job_evidence["raw_description_excerpt"])
    cannot_claim = build_cannot_claim_items(requirement_items + responsibility_items)

    draft = {
        "target_confirmation": build_target_confirmation(target_job),
        "job_core_requirements": requirement_items,
        "job_core_responsibilities": responsibility_items,
        "current_material_match_points": build_current_material_match_points(current_resume),
        "resume_revision_candidates": build_resume_revision_candidates(requirement_items, cannot_claim, current_resume),
        "interview_questions": build_interview_questions(requirement_items, responsibility_items),
        "evidence_gaps": build_evidence_gaps(requirement_items, cannot_claim, current_resume),
        "safety_notes": [
            "本接口只生成可审核草稿结构，不自动覆盖真实简历。",
            "可写入简历的内容必须先有简历、项目资料或引用来源证据。",
            "面试表达和简历表达必须分开，不能把未验证能力写进简历。",
            "本接口不调用 LLM、不访问招聘平台、不触发索引、不自动投递。",
        ],
    }

    warnings = list(context["warnings"])
    if not draft["resume_revision_candidates"]["can_write_to_resume"]:
        warnings.append("当前没有足够的用户事实证据生成可直接写入简历的表达。")

    return {
        "matched": True,
        "query": query,
        "target_job": target_job,
        "current_resume": current_resume,
        "draft": draft,
        "warnings": warnings,
    }


def build_target_confirmation(target_job: dict) -> dict:
    return {
        "title": target_job["title"],
        "company": target_job["company"] or "来源未提供",
        "city": target_job["city"] or "来源未提供",
        "source_job_id": target_job["source_job_id"] or "来源未提供",
        "marker": target_job["marker"] or "来源未提供",
        "source_file": target_job["source_file"],
        "source_url": target_job["source_url"] or "来源未提供",
    }


def extract_requirement_items(primary_text: str, fallback_text: str) -> list[str]:
    source_text = primary_text if has_meaningful_text(primary_text) else fallback_text
    normalized = normalize_job_text(source_text)
    parts = re.split(r"(?:[。；;]\s*|\s+o\s+|\n+|(?:\d+[、.])\s*)", normalized)
    items: list[str] = []
    for part in parts:
        item = clean_item(part)
        if not item or is_noise_item(item) or item in items:
            continue
        items.append(item)
        if len(items) >= MAX_REQUIREMENT_ITEMS:
            break
    return items


def normalize_job_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("二、任职要求", "任职要求")
    text = text.replace("技术能力", "。技术能力：")
    text = text.replace("工程与集成能力", "。工程与集成能力：")
    text = text.replace("教育与经验", "。教育与经验：")
    text = text.replace("加分项", "。加分项：")
    return text


def clean_item(text: str) -> str:
    item = text.strip(" -；;。")
    item = re.sub(r"^(岗位职责|任职要求|技术能力|工程与集成能力|教育与经验|加分项)[:：]?", "", item).strip()
    if len(item) > MAX_TEXT_CHARS:
        item = item[:MAX_TEXT_CHARS].rstrip() + "..."
    return item


def has_meaningful_text(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped and stripped != "来源未提供" and len(stripped) >= 12)


def is_noise_item(item: str) -> bool:
    if not item:
        return True
    if item in {"来源未提供", "真实岗位来源标识"}:
        return True
    if item.startswith("真实岗位来源标识"):
        return True
    return len(item) < 4


def build_current_material_match_points(current_resume: dict | None) -> list[dict]:
    if not current_resume:
        return []
    return [
        {
            "point": "当前已设置简历文件，可作为后续匹配分析的候选资料。",
            "evidence": f"{current_resume['source']}:{current_resume['name']}",
            "boundary": "这里只确认简历文件存在，不代表已确认其中包含某项具体能力。",
        }
    ]


def build_resume_revision_candidates(requirements: list[str], cannot_claim: list[dict], current_resume: dict | None) -> dict:
    evidence_required = [
        {
            "candidate_direction": f"如果简历或项目资料能证明“{item}”，可再生成可写入简历的候选表达。",
            "required_evidence": "需要来自当前简历、项目资料或后续 RAG 引用的明确事实证据。",
        }
        for item in requirements[:5]
    ]
    interview_only = [
        {
            "topic": item,
            "usage": "适合用于面试准备或自查，不应在缺少证据时直接写入简历。",
        }
        for item in requirements[:5]
    ]
    return {
        "can_write_to_resume": [],
        "requires_evidence_before_resume": evidence_required,
        "interview_only": interview_only,
        "cannot_claim": cannot_claim,
        "resume_state": "已设置当前简历" if current_resume else "未设置当前简历",
    }


def build_cannot_claim_items(items: list[str]) -> list[dict]:
    results: list[dict] = []
    for item in items:
        keyword = first_keyword_in_text(item)
        if not keyword:
            continue
        claim = {
            "claim": f"熟练或有实际经验：{keyword}",
            "reason": f"岗位要求中出现“{keyword}”，但当前接口没有读取到用户事实证据，不能自动声称。",
            "source_requirement": item,
        }
        if claim not in results:
            results.append(claim)
    return results[:10]


def first_keyword_in_text(text: str) -> str:
    lowered = text.lower()
    for keyword in HIGH_RISK_KEYWORDS:
        if keyword.lower() in lowered:
            return keyword
    return ""


def build_interview_questions(requirements: list[str], responsibilities: list[str]) -> list[str]:
    questions: list[str] = []
    for item in (requirements + responsibilities)[:MAX_INTERVIEW_QUESTIONS]:
        questions.append(f"请结合一个真实项目，说明你是否具备“{item}”相关经验；如果没有，请说明你准备如何补齐。")
    if not questions:
        questions.append("请先补充目标岗位的职责和任职要求，再生成面试问题。")
    return questions


def build_evidence_gaps(requirements: list[str], cannot_claim: list[dict], current_resume: dict | None) -> list[str]:
    gaps: list[str] = []
    if not current_resume:
        gaps.append("未设置当前简历，无法确认哪些能力可写入简历。")
    if requirements:
        gaps.append("尚未逐条核对当前简历和项目资料是否覆盖岗位核心要求。")
    if cannot_claim:
        risky_terms = "、".join(item["claim"].split("：", 1)[-1] for item in cannot_claim[:5])
        gaps.append(f"以下能力需要明确证据后才能写入简历：{risky_terms}。")
    return gaps
