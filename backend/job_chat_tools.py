import json
import re
from datetime import datetime
from pathlib import Path

from .job_interview import build_interview_session
from .job_matcher import build_job_evidence
from .job_match_report_export import export_job_match_report, read_job_match_report_export
from .job_profile import clean_requirement_text, is_internal_process_requirement
from .job_resolver import (
    build_job_payload,
    extract_job_identifier_terms,
    find_best_job_candidate,
    find_job_candidates,
    iter_job_candidates,
    to_source_file,
)
from .resume_revision_draft_export import export_resume_revision_draft, read_resume_revision_draft_export


SCOPE_NOTE = "范围限定：仅基于当前资料库、已索引、已合法导入的岗位资料，不代表全网或招聘平台全部岗位。"
SAFETY_NOTE = "安全边界：不自动投递，不覆盖真实简历，不绕过登录、验证码、反爬或平台限制。"
MANUAL_SCREENSHOT_MARKER = "manual_screenshot_"
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_INTAKE_OUTPUT_DIR = WORKSPACE_ROOT / "tools" / "jobonline-poc" / "output" / "production-job-intake-to-rag"


def build_job_chat_tool_result(question: str, history: list[dict] | None = None) -> dict:
    current_text = question or ""
    private_job_list_answer = build_private_local_job_list_answer(current_text)
    if private_job_list_answer:
        return {"artifacts": [], "answer_note": private_job_list_answer, "generation_seconds": 0.0}

    screenshot_list_answer = build_manual_screenshot_job_list_answer(current_text)
    if screenshot_list_answer:
        return {"artifacts": [], "answer_note": screenshot_list_answer, "generation_seconds": 0.0}

    recent_import_answer = build_recent_imported_job_list_answer(current_text)
    if recent_import_answer:
        return {"artifacts": [], "answer_note": recent_import_answer, "generation_seconds": 0.0}

    direct_lookup_answer = build_direct_job_lookup_answer(current_text)
    if direct_lookup_answer:
        return {"artifacts": [], "answer_note": direct_lookup_answer, "generation_seconds": 0.0}

    if not is_job_tool_intent(current_text):
        return {"artifacts": [], "answer_note": ""}

    artifacts: list[dict] = []
    notices: list[str] = []
    target_query = extract_target_query(current_text)
    intent = detect_job_tool_intent(current_text)

    if intent == "job_summary":
        summary_artifact = build_job_summary_artifact(current_text)
        if summary_artifact:
            artifacts.append(summary_artifact)
        elif target_query:
            report = build_report_artifact(target_query)
            if report:
                artifacts.append(report)
        else:
            notices.append("没有在当前资料库中命中可汇总的岗位。请先通过 n8n 合法导入岗位并更新索引，或提供岗位 ID、marker、文件名。")

    elif intent == "resume_revision":
        if not target_query:
            notices.append("简历不足分析需要一个明确岗位。请提供当前资料库中的岗位 ID、marker、文件名或明确标题。")
        else:
            artifact = build_resume_revision_artifact(target_query)
            if artifact:
                artifacts.append(artifact)
            else:
                notices.append("没有生成简历优化草稿。请确认目标岗位已合法导入，并且已设置当前简历。")

    elif intent == "interview":
        if not target_query:
            notices.append("面试模拟需要一个明确岗位。请提供当前资料库中的岗位 ID、marker、文件名或明确标题。")
        else:
            artifact = build_interview_artifact(target_query)
            if artifact:
                artifacts.append(artifact)
            else:
                notices.append("未找到目标岗位或岗位 ID 不存在，没有生成面试模拟卡片。请确认目标岗位已合法导入。")

    else:
        if target_query:
            report = build_report_artifact(target_query)
            if report:
                artifacts.append(report)
        if not artifacts:
            notices.append("已识别求职分析意图，但需要更明确的岗位 ID、marker、文件名或岗位标题才能生成可审核卡片。")

    return {
        "artifacts": artifacts,
        "answer_note": build_answer_note(artifacts, notices),
        "generation_seconds": sum(float(artifact.get("generation_seconds", 0.0) or 0.0) for artifact in artifacts),
    }


def append_job_tool_note(answer: str, tool_result: dict | None) -> str:
    note = (tool_result or {}).get("answer_note", "").strip()
    if not note:
        return answer
    return f"{answer.rstrip()}\n\n{note}" if answer.strip() else note


def is_job_tool_intent(text: str) -> bool:
    normalized = text.strip()
    lowered = normalized.lower()
    if not normalized or is_generic_non_job_tool_question(normalized):
        return False

    direct_action_phrases = (
        "生成面试题",
        "生成面试模拟题",
        "面试模拟题",
        "面试模拟",
        "模拟面试",
        "面试题",
        "优化简历",
        "修改简历",
        "简历优化",
        "简历不足",
        "简历草稿",
        "岗位匹配",
        "匹配报告",
        "批量报告",
        "求职 agent",
        "求职Agent",
        "求职分析",
    )
    if any(phrase in normalized or phrase.lower() in lowered for phrase in direct_action_phrases):
        return True

    object_patterns = (
        re.search(r"\b\d{8,}\b", normalized) is not None,
        any(keyword in normalized for keyword in ("岗位", "职位", "JD", "jd", "简历", "求职")),
    )
    action_keywords = (
        "生成",
        "分析",
        "匹配",
        "草稿",
        "报告",
        "面试",
        "审核",
        "优化",
        "修改",
    )
    return any(object_patterns) and any(keyword in normalized for keyword in action_keywords)


def is_generic_non_job_tool_question(text: str) -> bool:
    compact = re.sub(r"\s+", "", text.lower())
    deny_substrings = (
        "什么是rag",
        "rag是什么",
        "简单说下",
        "解释一下",
        "rag和微调有什么区别",
        "rag和微调区别",
        "llm是什么",
        "当前使用的模型",
        "当前模型",
        "使用的是什么模型",
        "什么模型",
        "哪个模型",
    )
    return any(pattern in compact for pattern in deny_substrings)


def build_direct_job_lookup_answer(text: str) -> str:
    if not is_direct_job_lookup_question(text):
        return ""
    try:
        candidate = find_best_job_candidate(extract_target_query(text) or extract_lookup_target_query(text) or text)
    except ValueError:
        return ""
    if not candidate:
        return (
            "没有在当前本地岗位资料库中找到这个岗位。请确认岗位 ID、marker 或文件名是否正确，"
            "并确认 n8n 工作流已写入岗位且索引已更新。"
        )

    payload = build_job_payload(candidate)
    content = candidate.path.read_text(encoding="utf-8-sig")
    evidence = build_job_evidence(content, candidate.title, to_source_file(candidate))
    responsibilities = summarize_job_field(evidence.get("responsibilities_text", ""), "岗位职责")
    requirements = summarize_job_field(evidence.get("requirements_text", ""), "任职要求")
    lines = [
        "已找到这条本地岗位资料：",
        "",
        f"- 岗位标题：{payload.get('title') or '来源未提供'}",
        f"- 公司：{payload.get('company') or '来源未提供'}",
        f"- 城市：{payload.get('city') or '来源未提供'}",
        f"- 来源岗位 ID：{payload.get('source_job_id') or '来源未提供'}",
        f"- 岗位职责摘要：{responsibilities}",
        f"- 任职要求摘要：{requirements}",
        "",
        SCOPE_NOTE,
        SAFETY_NOTE,
    ]
    return "\n".join(lines)


def build_private_local_job_list_answer(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    compact = re.sub(r"\s+", "", normalized.lower())
    triggers = (
        "本地私有岗位有哪些",
        "私有岗位有哪些",
        "本地岗位有哪些",
        "本地岗位列表",
        "本地私有职位",
        "本地私有岗位",
    )
    if not any(trigger in compact for trigger in triggers):
        return ""

    jobs = []
    for candidate in iter_job_candidates():
        if candidate.source != "private":
            continue
        payload = build_job_payload(candidate)
        if is_user_facing_private_job_payload(payload):
            jobs.append(payload)

    if not jobs:
        return "\n".join(
            [
                "当前本地私有岗位资料库中没有可列出的岗位。",
                "",
                SCOPE_NOTE,
                SAFETY_NOTE,
            ]
        )

    lines = ["当前本地私有岗位资料库中的岗位包括：", ""]
    visible_jobs = jobs[:10]
    lines.extend(["说明：默认只显示截图导入、授权导出和公众号授权文本岗位；阶段自测、样本、远程和公共来源岗位已隐藏。", ""])
    for index, job in enumerate(visible_jobs, start=1):
        lines.extend(
            [
                f"{index}. {job.get('title') or '未命名岗位'}｜{job.get('company') or '来源未提供'}｜{job.get('city') or '来源未提供'}",
                f"   - 来源岗位 ID：{job.get('source_job_id') or job.get('marker') or '来源未提供'}",
            ]
        )
    hidden_count = len(jobs) - len(visible_jobs)
    if hidden_count > 0:
        lines.append(f"... 其余 {hidden_count} 条未展开。")
    lines.extend(["", SCOPE_NOTE, SAFETY_NOTE])
    return "\n".join(lines)


def is_user_facing_private_job_payload(job: dict) -> bool:
    source_id = str(job.get("source_job_id") or "").strip()
    marker = str(job.get("marker") or "").strip()
    title = str(job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    city = str(job.get("city") or "").strip()
    source_file = str(job.get("source_file") or "").strip()

    if not source_id or source_id in {"来源未提供", "source not provided"}:
        return False

    allowed_prefixes = ("manual_screenshot_", "authorized_export_", "wechat_auth_")
    if not any(source_id.startswith(prefix) or marker.startswith(prefix) for prefix in allowed_prefixes):
        return False

    haystack = f"{source_id} {marker} {title} {company} {city} {source_file}".lower()
    blocked_terms = (
        "stage",
        "gate",
        "selftest",
        "fixture",
        "sample",
        "csv",
        "batch",
        "阶段",
        "自测",
        "样本",
        "唯一写入",
        "批量",
        "原文粘贴",
        "字段填写",
    )
    if any(term.lower() in haystack for term in blocked_terms):
        return False
    if "远程" in city or "远程" in title or "remote" in city.lower() or "remote" in title.lower():
        return False
    return True


def extract_lookup_target_query(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"^(请|帮我|麻烦)?为(岗位|职位)?", "", cleaned).strip()
    cleaned = re.sub(r"^(请|帮我|麻烦)?(查找|查询|找一下|找|看看|检索)", "", cleaned).strip()
    cleaned = re.sub(r"(这个|这条)?(岗位|职位|JD|jd)$", "", cleaned).strip()
    cleaned = re.sub(r"(生成|做|创建).*$", "", cleaned).strip()
    cleaned = re.sub(r"(这个|这条)?(岗位|职位|JD|jd)$", "", cleaned).strip()
    return cleaned.strip(" ：:，,。.;；")


def build_job_candidate_selection_answer(text: str, action_label: str) -> str:
    query = extract_target_query(text) or extract_lookup_target_query(text) or text
    if not query:
        return ""
    try:
        candidates = find_job_candidates(query, limit=5)
    except ValueError:
        return ""
    if not candidates:
        return ""

    lines = [
        f"我找到了 {len(candidates)} 个可能相关的岗位。请用来源岗位 ID 明确要{action_label}的岗位：",
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        payload = build_job_payload(candidate)
        lines.extend(
            [
                f"{index}. {payload.get('title') or '未命名岗位'}｜{payload.get('company') or '来源未提供'}｜{payload.get('city') or '来源未提供'}",
                f"   - 来源岗位 ID：{payload.get('source_job_id') or payload.get('marker') or '来源未提供'}",
            ]
        )
    lines.extend(["", f"例如：请为岗位 {build_job_payload(candidates[0]).get('source_job_id') or '岗位ID'} {action_label}"])
    return "\n".join(lines)


def build_manual_screenshot_job_list_answer(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    if not ("截图" in normalized and "岗位" in normalized):
        return ""
    if not any(keyword in normalized for keyword in ("刚导入", "导入", "有哪些", "哪些", "列表", "全部")):
        return ""

    jobs = []
    for candidate in iter_job_candidates():
        payload = build_job_payload(candidate)
        source_id = str(payload.get("source_job_id", ""))
        source_file = str(payload.get("source_file", ""))
        marker = str(payload.get("marker", ""))
        if (
            source_id.startswith(MANUAL_SCREENSHOT_MARKER)
            or MANUAL_SCREENSHOT_MARKER in source_file
            or marker.startswith(MANUAL_SCREENSHOT_MARKER)
        ):
            jobs.append(payload)

    if not jobs:
        return (
            "当前本地岗位资料库中没有找到截图导入岗位。请确认截图岗位已通过授权导入工作流写入岗位资料目录，"
            "并且 local-rag-assistant 索引已更新。"
        )

    lines = ["当前资料库中已导入的截图岗位有：", ""]
    for index, job in enumerate(jobs, start=1):
        lines.extend(
            [
                f"{index}. {job.get('title') or '未命名岗位'}｜{job.get('company') or '来源未提供'}｜{job.get('city') or '来源未提供'}",
                f"   - 来源岗位 ID：{job.get('source_job_id') or '来源未提供'}",
            ]
        )
    lines.extend(["", SCOPE_NOTE, SAFETY_NOTE])
    return "\n".join(lines)


def read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_recent_production_intake_answer() -> str:
    manifest = read_json_file(PRODUCTION_INTAKE_OUTPUT_DIR / "manifest.json")
    audit = read_json_file(PRODUCTION_INTAKE_OUTPUT_DIR / "audit.json")
    if manifest.get("stage") != "production_job_intake_manifest" and audit.get("stage") != "production_job_intake_audit":
        return ""

    schema_validation = audit.get("schema_validation") or {}
    write = audit.get("write") or {}
    dedupe = audit.get("dedupe") or {}
    source_stats = audit.get("source_stats") or manifest.get("source_stats") or []
    files = manifest.get("files") or []
    source_job_ids = [str(item.get("source_job_id") or "") for item in files if item.get("source_job_id")]

    lines = [
        "最近一次 n8n production-job-intake-to-rag 导入结果：",
        "",
        f"- run_id：{manifest.get('run_id') or audit.get('run_id') or '未记录'}",
        f"- 状态：{audit.get('status') or '未记录'}",
        f"- 批量档位：{manifest.get('batch_profile') or audit.get('batch_profile') or '未记录'}",
        f"- 处理岗位数：{(audit.get('input') or {}).get('processed_count', 0)}",
        f"- 有效岗位数：{schema_validation.get('valid_count', 0)}",
        f"- 新写入岗位数：{write.get('written_count', 0)}",
        f"- 已存在幂等跳过：{write.get('existing_count', 0)}",
        f"- 重复/跳过：{dedupe.get('skipped_count', 0)}",
        f"- 进入审核：{dedupe.get('review_required_count', 0)}",
        f"- 失败项：{len(audit.get('failed_items') or [])}",
        "",
        "本轮来源统计：",
    ]
    if source_stats:
        for item in source_stats:
            lines.append(
                "- "
                f"{item.get('source_id') or 'unknown'} / {item.get('connector') or 'unknown'}："
                f"采集 {item.get('collected_count', 0)}，"
                f"有效 {item.get('valid_count', 0)}，"
                f"写入 {item.get('written_count', 0)}，"
                f"已存在 {item.get('existing_count', 0)}，"
                f"审核 {item.get('review_count', 0)}，"
                f"失败 {item.get('failed_count', 0)}"
            )
    else:
        lines.append("- 未记录 source_stats。")

    if source_job_ids:
        lines.extend(["", "本轮 manifest 中的岗位 ID："])
        for index, source_job_id in enumerate(source_job_ids[:20], start=1):
            lines.append(f"{index}. {source_job_id}")
        if len(source_job_ids) > 20:
            lines.append(f"... 其余 {len(source_job_ids) - 20} 条见 manifest.json")

    lines.extend(["", SCOPE_NOTE, SAFETY_NOTE])
    return "\n".join(lines)


def build_recent_imported_job_list_answer(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    if not any(keyword in normalized for keyword in ("资料库", "岗位资料", "刚导入", "导入", "新增")):
        return ""
    if not any(keyword in normalized for keyword in ("岗位", "职位", "JD", "jd")):
        return ""
    if not any(keyword in normalized for keyword in ("有哪些", "哪些", "列出", "清单", "列表", "刚导入")):
        return ""

    recent_run_answer = build_recent_production_intake_answer()
    if recent_run_answer:
        return recent_run_answer

    jobs = []
    for candidate in iter_job_candidates():
        payload = build_job_payload(candidate)
        source_file = str(payload.get("source_file") or "")
        if source_file.startswith("private_data/job_descriptions/"):
            jobs.append(payload)

    if not jobs:
        return (
            "当前本地岗位资料库中没有找到已导入岗位。请先通过 n8n 的合法授权导入工作流写入岗位资料，"
            "再更新索引或使用岗位 ID 精确查询。"
        )

    jobs = jobs[:10]
    lines = [
        "当前本地岗位资料库中最近可见的岗位包括：",
        "",
    ]
    for index, job in enumerate(jobs, start=1):
        lines.extend(
            [
                f"{index}. {job.get('title') or '未命名岗位'} - {job.get('company') or '来源未提供'} - {job.get('city') or '来源未提供'}",
                f"   - 来源岗位 ID：{job.get('source_job_id') or '来源未提供'}",
            ]
        )
    lines.extend(
        [
            "",
            "范围限定：仅基于当前 local-rag-assistant 本地岗位资料库，不代表全网或招聘平台全部岗位。",
            "安全边界：不自动投递，不覆盖真实简历，不绕过登录、验证码、反爬或平台限制。",
        ]
    )
    return "\n".join(lines)


def is_direct_job_lookup_question(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if any(keyword in normalized for keyword in ("生成面试", "面试题", "面试模拟", "优化简历", "修改简历", "简历不足", "岗位匹配", "匹配报告")):
        return False
    if any(keyword in normalized for keyword in ("查找", "查询", "找一下", "找", "检索", "看看")) and any(keyword in normalized for keyword in ("岗位", "职位", "JD", "jd", "资料库")):
        try:
            return bool(find_job_candidates(extract_lookup_target_query(normalized) or normalized, limit=1))
        except ValueError:
            return False
    artifact_keywords = (
        "生成面试",
        "面试题",
        "面试模拟",
        "模拟面试",
        "优化简历",
        "修改简历",
        "简历不足",
        "岗位匹配",
        "匹配报告",
        "报告",
    )
    if any(keyword in normalized for keyword in artifact_keywords):
        return False

    lookup_keywords = ("查找", "查询", "找", "刚导入", "唯一写入", "这个岗位", "这条岗位", "岗位是什么")
    has_lookup_action = any(keyword in normalized for keyword in lookup_keywords)
    has_job_object = any(keyword in normalized for keyword in ("岗位", "职位", "JD", "jd", "资料库"))
    has_identifier = bool(extract_job_identifier_terms(normalized)) or ".md" in normalized.lower()
    if has_identifier and (has_lookup_action or has_job_object):
        return True
    if has_lookup_action and has_job_object:
        try:
            return bool(find_job_candidates(extract_lookup_target_query(normalized) or normalized, limit=1))
        except ValueError:
            return False
    return False


def summarize_job_field(text: str, label: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned or cleaned == "来源未提供":
        return f"{label}字段缺失或未提供。"
    useful_parts = []
    for part in re.split(r"[。；;\n]+", cleaned):
        item = clean_requirement_text(part)
        if item and not is_internal_process_requirement(item):
            useful_parts.append(item)
    if not useful_parts:
        return f"{label}字段主要包含内部导入或测试流程说明，未识别到可用{label}内容。"
    useful_text = "；".join(useful_parts)
    return useful_text[:220].rstrip() + ("..." if len(useful_text) > 220 else "")


def detect_job_tool_intent(text: str) -> str:
    if any(keyword in text for keyword in ("面试", "模拟面试", "面试题", "口述")):
        return "interview"
    if any(keyword in text for keyword in ("优化简历", "修改简历", "简历优化", "简历不足", "差距", "不足")):
        return "resume_revision"
    if any(keyword in text for keyword in ("所有", "全部", "汇总", "岗位要求", "找", "筛选")):
        return "job_summary"
    if any(keyword in text for keyword in ("匹配", "报告", "分析")):
        return "job_report"
    return "job_report"


def build_intent_text(question: str, history: list[dict]) -> str:
    # Kept for backwards compatibility with older callers. Job tool triggering
    # must not use history; build_job_chat_tool_result intentionally ignores it.
    recent_user_text = "\n".join(
        item.get("content", "")
        for item in history[-6:]
        if item.get("role") == "user" and isinstance(item.get("content"), str)
    )
    return f"{recent_user_text}\n{question}" if recent_user_text else question


def extract_target_query(text: str) -> str:
    id_match = re.search(r"\b\d{8,}\b", text)
    if id_match:
        return id_match.group(0)

    identifier_terms = extract_job_identifier_terms(text)
    if identifier_terms:
        best_term = max(identifier_terms, key=len)
        try:
            candidate = find_best_job_candidate(best_term)
        except ValueError:
            candidate = None
        if candidate:
            payload = build_job_payload(candidate)
            return payload.get("source_job_id") or payload.get("marker") or payload.get("file_name") or best_term
        return best_term

    lookup_query = extract_lookup_target_query(text)
    if lookup_query and lookup_query != text:
        try:
            candidates = find_job_candidates(lookup_query, limit=1)
        except ValueError:
            candidates = []
        if candidates:
            payload = build_job_payload(candidates[0])
            return payload.get("source_job_id") or payload.get("marker") or payload.get("file_name") or candidates[0].title

    lowered = text.lower()
    best = ""
    for candidate in iter_job_candidates():
        payload = build_job_payload(candidate)
        values = [
            payload.get("source_job_id", ""),
            payload.get("marker", ""),
            payload.get("file_name", ""),
            payload.get("title", ""),
        ]
        for value in values:
            normalized = str(value).strip().lower()
            if normalized and normalized in lowered:
                return str(value)
        title = str(payload.get("title", "")).strip()
        if title and title.lower() in lowered:
            best = title
    if best:
        return best
    lookup_query = extract_lookup_target_query(text)
    if lookup_query:
        try:
            candidates = find_job_candidates(lookup_query, limit=1)
        except ValueError:
            candidates = []
        if candidates:
            payload = build_job_payload(candidates[0])
            return payload.get("source_job_id") or payload.get("marker") or payload.get("file_name") or candidates[0].title
    return best


def build_job_summary_artifact(text: str) -> dict | None:
    matches = find_matching_jobs(text)
    if not matches:
        return None

    lines = [
        "# 当前资料库岗位汇总",
        "",
        "## 摘要",
        "",
        f"- 当前资料库命中 {len(matches)} 个候选岗位。",
        "- 结果只来自本地已合法导入资料，不访问招聘平台。",
        "",
        "## 岗位清单",
    ]
    for index, job in enumerate(matches[:10], start=1):
        lines.extend(
            [
                f"{index}. {job.get('title') or '未命名岗位'}",
                f"   - 公司：{job.get('company') or '来源未提供'}",
                f"   - 城市：{job.get('city') or '来源未提供'}",
                f"   - 来源 ID：{job.get('source_job_id') or job.get('marker') or '来源未提供'}",
                f"   - 文件：{job.get('source_file')}",
            ]
        )
    lines.extend(["", "## 来源与边界", "", f"- {SCOPE_NOTE}", f"- {SAFETY_NOTE}"])

    content = "\n".join(lines)
    return {
        "artifact_id": build_artifact_id("job_summary"),
        "type": "job_summary",
        "title": "当前资料库岗位汇总",
        "description": f"命中 {len(matches)} 个本地候选岗位。",
        "query": text,
        "scope_note": SCOPE_NOTE,
        "content_preview": content[:500],
        "content_markdown": content,
        "highlights": [
            f"命中 {len(matches)} 个本地岗位。",
            "只汇总已合法导入、已索引资料。",
            "未访问外部招聘平台。",
        ],
        "metrics": {"matched_jobs": len(matches)},
        "warnings": ["未访问外部招聘平台；结果不代表全网全部岗位。"],
        "actions": [
            {"label": "下载 Markdown", "kind": "download_markdown"},
            {"label": "进入求职 Agent", "kind": "open_job_agent"},
        ],
    }


def find_matching_jobs(text: str) -> list[dict]:
    terms = extract_search_terms(text)
    jobs = [build_job_payload(candidate) for candidate in iter_job_candidates()]
    if not terms:
        return jobs[:10]

    results = []
    for job in jobs:
        haystack = " ".join(str(value).lower() for value in job.values() if isinstance(value, str))
        if all(term in haystack for term in terms):
            results.append(job)
    if results:
        return results[:10]

    relaxed = []
    for job in jobs:
        haystack = " ".join(str(value).lower() for value in job.values() if isinstance(value, str))
        score = sum(1 for term in terms if term in haystack)
        if score:
            relaxed.append((score, job))
    relaxed.sort(key=lambda item: item[0], reverse=True)
    return [job for _, job in relaxed[:10]]


def extract_search_terms(text: str) -> list[str]:
    terms = []
    for keyword in ("成都", "成都市", "AI", "ai", "人工智能", "应用开发", "应用工程师", "非远程", "远程"):
        if keyword in text:
            normalized = keyword.lower()
            if normalized not in terms:
                terms.append(normalized)
    if "成都市" in terms:
        terms.remove("成都市")
        if "成都" not in terms:
            terms.append("成都")
    return terms[:4]


def build_report_artifact(query: str) -> dict | None:
    try:
        response = export_job_match_report(query, confirm_save=True, note="created from Ask analysis artifact")
    except Exception:
        return None
    if not response.get("exported"):
        return None
    content = read_job_match_report_export(response["file_name"]).get("content", response.get("content_preview", ""))
    target_job = response.get("target_job") or {}
    title = target_job.get("title") or "目标岗位"
    return {
        "artifact_id": build_artifact_id("job_match_report"),
        "type": "job_match_report",
        "title": "岗位匹配报告",
        "description": f"{title} 的可审核匹配报告已生成。",
        "query": query,
        "scope_note": SCOPE_NOTE,
        "file_name": response.get("file_name", ""),
        "relative_path": response.get("relative_path", ""),
        "content_preview": response.get("content_preview", ""),
        "content_markdown": content,
        "review_status": response.get("review_status", ""),
        "highlights": [
            f"目标岗位：{title}",
            "已保存为独立报告副本，可进入审核。",
            "不会自动投递或修改简历。",
        ],
        "metrics": {"report_count": 1},
        "warnings": response.get("warnings", []),
        "actions": [
            {"label": "下载 Markdown", "kind": "download_markdown"},
            {"label": "进入审核", "kind": "open_job_agent"},
        ],
    }


def build_resume_revision_artifact(query: str) -> dict | None:
    try:
        response = export_resume_revision_draft(query, confirm_save=True, note="created from Ask analysis artifact")
    except Exception:
        return None
    if not response.get("exported"):
        return None

    content = read_resume_revision_draft_export(response["file_name"]).get("content", response.get("content_preview", ""))
    target_job = response.get("target_job") or {}
    title = target_job.get("title") or "目标岗位"
    metrics = parse_resume_revision_metrics(content)
    evidence_status = build_resume_evidence_status(response.get("current_resume"), metrics)
    highlights = build_resume_revision_highlights(title, metrics, evidence_status)
    summary_markdown = build_resume_revision_preview_markdown(title, response, metrics, evidence_status, highlights, content)
    return {
        "artifact_id": build_artifact_id("resume_revision_draft"),
        "type": "resume_revision_draft",
        "title": "简历优化草稿",
        "description": f"{title}：{metrics['requires_evidence']} 条需补证据，{metrics['cannot_claim']} 条不能直接声称。",
        "query": query,
        "scope_note": SCOPE_NOTE,
        "file_name": response.get("file_name", ""),
        "relative_path": response.get("relative_path", ""),
        "content_preview": summary_markdown[:500],
        "content_markdown": summary_markdown,
        "review_status": "",
        "highlights": highlights,
        "metrics": metrics,
        "resume_evidence_status": evidence_status["code"],
        "resume_evidence_status_label": evidence_status["label"],
        "warnings": response.get("warnings", []),
        "actions": [
            {"label": "下载 Markdown", "kind": "download_markdown"},
            {"label": "进入审核", "kind": "open_job_agent"},
        ],
    }


def parse_resume_revision_metrics(content: str) -> dict:
    labels = {
        "可直接考虑写入": "can_write",
        "需补证据后再考虑": "requires_evidence",
        "仅适合面试准备": "interview_only",
        "不能声称能力": "cannot_claim",
    }
    metrics = {value: 0 for value in labels.values()}
    for label, key in labels.items():
        match = re.search(rf"{re.escape(label)}[：:]\s*(\d+)", content)
        if match:
            metrics[key] = int(match.group(1))
    return metrics


def build_resume_evidence_status(current_resume: dict | None, metrics: dict) -> dict:
    if not current_resume:
        return {"code": "not_configured", "label": "未配置当前简历", "detail": "请先在简历中心设置当前简历。"}
    if metrics.get("can_write", 0) > 0:
        return {
            "code": "parsed_with_relevant_evidence",
            "label": "已解析且有相关证据",
            "detail": "当前资料中已有可考虑写入简历的候选表达，仍需人工审核。",
        }
    if metrics.get("requires_evidence", 0) > 0 or metrics.get("cannot_claim", 0) > 0:
        return {
            "code": "parsed_without_relevant_evidence",
            "label": "已设置简历但未命中可直接写入证据",
            "detail": "系统能识别当前简历文件，但缺少可支撑岗位核心要求的明确事实证据。",
        }
    return {
        "code": "configured_unverified",
        "label": "已设置简历，证据状态待人工复核",
        "detail": "当前接口未能进一步确认简历是否覆盖岗位要求。",
    }


def build_resume_revision_highlights(title: str, metrics: dict, evidence_status: dict) -> list[str]:
    highlights = [
        f"目标岗位：{title}",
        f"当前简历证据状态：{evidence_status['label']}",
        f"可直接考虑写入 {metrics['can_write']} 条；需补证据 {metrics['requires_evidence']} 条。",
        f"仅适合面试准备 {metrics['interview_only']} 条；不能直接声称 {metrics['cannot_claim']} 条。",
    ]
    if metrics["can_write"] == 0:
        highlights.append("核心结论：暂不建议把新能力直接写进正式简历，应先补充真实项目或简历证据。")
    return highlights


def build_resume_revision_preview_markdown(
    title: str,
    response: dict,
    metrics: dict,
    evidence_status: dict,
    highlights: list[str],
    original_content: str,
) -> str:
    lines = [
        f"# 简历优化草稿：{title}",
        "",
        "## 核心结论",
        "",
        *[f"- {item}" for item in highlights],
        "",
        "## 数量统计",
        "",
        f"- 可直接考虑写入：{metrics['can_write']} 条",
        f"- 需补证据后再考虑：{metrics['requires_evidence']} 条",
        f"- 仅适合面试准备：{metrics['interview_only']} 条",
        f"- 不能声称能力：{metrics['cannot_claim']} 条",
        "",
        "## 当前简历证据状态",
        "",
        f"- 状态：{evidence_status['label']}",
        f"- 说明：{evidence_status['detail']}",
        f"- 当前简历：{format_resume_name(response.get('current_resume'))}",
        "",
        "## 下一步建议",
        "",
        "- 先补充真实项目、简历或资料库证据，再生成可写入版本。",
        "- 证据不足的内容只能用于面试准备或学习计划。",
        "- 下载 Markdown 或进入审核页查看完整明细。",
        "",
        "## 来源与安全边界",
        "",
        f"- {SCOPE_NOTE}",
        f"- {SAFETY_NOTE}",
        "",
        "## 完整明细",
        "",
        original_content,
    ]
    return "\n".join(lines)


def format_resume_name(current_resume: dict | None) -> str:
    if not current_resume:
        return "未配置"
    return f"{current_resume.get('source', 'private')}:{current_resume.get('name', '未命名')}"


def build_interview_artifact(query: str) -> dict | None:
    try:
        response = build_interview_session(query)
    except Exception:
        return None
    if not response.get("matched") or not response.get("session"):
        return None

    session = response["session"]
    questions = session.get("questions", [])
    type_summary = summarize_question_types(questions)
    skill_areas = dedupe([question.get("skill_area", "") for question in questions if question.get("skill_area")])[:5]
    content = build_interview_markdown(questions, session)
    generation_mode = session.get("generation_mode", response.get("generation_mode", "rule_fallback"))
    generation_model = session.get("generation_model", response.get("generation_model", ""))
    llm_attempted = bool(session.get("llm_attempted", response.get("llm_attempted", False)))
    llm_repair_attempted = bool(session.get("llm_repair_attempted", response.get("llm_repair_attempted", False)))
    fallback_reason = session.get("fallback_reason", response.get("fallback_reason", ""))
    fallback_detail = session.get("fallback_detail", response.get("fallback_detail", ""))
    cache_hit = bool(session.get("cache_hit", response.get("cache_hit", False)))
    validation_errors = session.get("validation_errors", response.get("validation_errors", []))
    if generation_mode == "llm":
        generation_mode_label = "LLM 生成"
        generation_highlight = "生成模式：LLM 生成。"
    elif llm_attempted:
        generation_mode_label = "本地规则回退（已尝试 LLM）"
        reason_text = fallback_reason or "未返回原因"
        generation_highlight = f"生成模式：本地规则回退；已尝试 LLM，因 {reason_text} 回退。"
    else:
        generation_mode_label = "本地规则回退（LLM 未启用）"
        generation_highlight = "生成模式：本地规则回退；LLM 未启用。"
    type_summary_label = format_question_type_summary(type_summary)
    highlights = [
        generation_highlight,
        f"已生成 {len(questions)} 道面试模拟题。",
        f"题型分布：{type_summary_label}。",
        "每题包含正确答案、解析、来源岗位要求和风险提示。",
    ]
    if cache_hit:
        highlights.append("缓存命中：本次复用了同一岗位和参数的已生成题目。")
    if fallback_detail:
        highlights.append(f"回退说明：{fallback_detail}")
    if skill_areas:
        highlights.append(f"覆盖方向：{'、'.join(skill_areas)}。")
    return {
        "artifact_id": build_artifact_id("interview_session"),
        "type": "interview_session",
        "title": "面试模拟",
        "description": f"已生成 {len(questions)} 道题，包含选择题、判断题和简答题。",
        "query": query,
        "scope_note": SCOPE_NOTE,
        "content_preview": content[:500],
        "content_markdown": content,
        "highlights": highlights,
        "metrics": {
            "question_count": len(questions),
            "generation_mode": generation_mode_label,
            "cache_hit": cache_hit,
            **{key: value for key, value in type_summary.items() if value > 0},
        },
        "generation_mode": generation_mode,
        "generation_model": generation_model,
        "generation_seconds": session.get("generation_seconds", response.get("generation_seconds", 0.0)),
        "llm_attempted": llm_attempted,
        "llm_repair_attempted": llm_repair_attempted,
        "fallback_reason": fallback_reason,
        "fallback_detail": fallback_detail,
        "cache_hit": cache_hit,
        "validation_errors": validation_errors,
        "question_type_summary": type_summary,
        "skill_areas": skill_areas,
        "session_payload": response,
        "warnings": filter_interview_warnings(response.get("warnings", [])),
        "actions": [
            {"label": "下载 Markdown", "kind": "download_markdown"},
            {"label": "进入求职 Agent", "kind": "open_job_agent"},
        ],
    }


def summarize_question_types(questions: list[dict]) -> dict:
    summary = {"single_choice": 0, "multiple_choice": 0, "true_false": 0, "short_answer": 0}
    for question in questions:
        question_type = question.get("type")
        if question_type in summary:
            summary[question_type] += 1
    return summary


def format_question_type_summary(summary: dict) -> str:
    labels = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "short_answer": "简答题",
    }
    parts = [f"{labels[key]} {value} 道" for key, value in summary.items() if value > 0]
    return "，".join(parts) if parts else "暂无题目"


def filter_interview_warnings(warnings: list[str]) -> list[str]:
    blocked_terms = ("写入简历", "简历差异", "简历草稿", "覆盖真实简历")
    return [warning for warning in warnings if not any(term in warning for term in blocked_terms)]


def build_interview_markdown(questions: list[dict], session: dict) -> str:
    lines = [
        "# 面试模拟",
        "",
        "## 摘要",
        "",
        f"- 共 {len(questions)} 题，包含选择题、判断题和简答题。",
        f"- 生成模式：{format_interview_generation_mode(session)}",
        "- 每题都包含答案、解析、来源岗位要求和风险提示。",
        "",
        "## 题目",
    ]
    for question in questions:
        lines.extend(render_interview_question_markdown(question))
    lines.extend(["", "## 回答边界", *[f"- {item}" for item in session.get("safety_notes", [])]])
    lines.extend(["", "## 来源与安全边界", "", f"- {SCOPE_NOTE}", f"- {SAFETY_NOTE}"])
    return "\n".join(lines)


def format_interview_generation_mode(session: dict) -> str:
    cache_note = "；缓存命中" if session.get("cache_hit") else ""
    if session.get("generation_mode") == "llm":
        return f"LLM 生成{cache_note}"
    if session.get("llm_attempted"):
        reason = session.get("fallback_reason") or "未返回原因"
        detail = session.get("fallback_detail") or "已尝试 LLM，但未通过生成或校验，已回退到本地规则。"
        return f"本地规则回退（已尝试 LLM；原因：{reason}；说明：{detail}{cache_note}）"
    return f"本地规则回退（LLM 未启用{cache_note}）"


def render_interview_question_markdown(question: dict) -> list[str]:
    question_type_labels = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "short_answer": "简答题",
    }
    question_type = question_type_labels.get(question.get("type"), "面试题")
    correct_answer = question.get("correct_answer", "")
    if isinstance(correct_answer, list):
        correct_answer_text = "、".join(str(item) for item in correct_answer)
    else:
        correct_answer_text = str(correct_answer)
    lines = [
        "",
        f"### Q{question.get('question_id')} {question_type}",
        "",
        question.get("question", ""),
    ]
    options = question.get("options") or []
    if options:
        lines.extend(["", "选项："])
        lines.extend(f"- {option.get('key')}. {option.get('text')}" for option in options)
    lines.extend(
        [
            "",
            f"- 正确答案：{correct_answer_text}",
            f"- 解释：{question.get('explanation', '')}",
            f"- 来源岗位要求：{question.get('source_requirement') or question.get('requirement', '')}",
            f"- 风险提示：{question.get('risk_hint') or question.get('risk_reminder', '')}",
        ]
    )
    return lines


def build_answer_note(artifacts: list[dict], notices: list[str]) -> str:
    if artifacts:
        artifact = artifacts[0]
        if artifact["type"] == "resume_revision_draft":
            return build_resume_revision_answer(artifact)
        if artifact["type"] == "interview_session":
            return build_interview_answer(artifact)
        if artifact["type"] == "job_summary":
            return build_summary_answer(artifact)
        if artifact["type"] == "job_match_report":
            return build_report_answer(artifact)

    if notices:
        return "\n".join(["没有生成可审核卡片。", "", *[f"- {notice}" for notice in notices], "", SAFETY_NOTE])
    return ""


def build_resume_revision_answer(artifact: dict) -> str:
    lines = [
        "我已经生成了简历不足分析和优化草稿。核心结论是：当前资料还不足以直接把新能力写进正式简历，需要先补证据。",
        "",
        "主要结果：",
    ]
    lines.extend(f"- {item}" for item in artifact.get("highlights", [])[:5])
    lines.extend(["", "草稿已保存为独立可审核副本，可在卡片中下载或进入审核；不会覆盖真实简历。", SAFETY_NOTE])
    return "\n".join(lines)


def build_interview_answer(artifact: dict) -> str:
    if artifact.get("generation_mode") == "llm":
        mode_line = "本次题目由 LLM 生成，并已通过结构化校验。"
    elif artifact.get("llm_attempted"):
        mode_line = f"系统已尝试 LLM，但因 {artifact.get('fallback_reason') or '未返回原因'} 回退到本地规则；卡片中保留了诊断说明。"
    else:
        mode_line = "LLM 面试出题未启用，本次使用本地规则生成。"
    lines = [
        "我已经按目标岗位生成了面试模拟题，包含选择题、判断题和简答题，方便你先快速自测。",
        mode_line,
        "",
        "主要结果：",
    ]
    lines.extend(f"- {item}" for item in artifact.get("highlights", [])[:4])
    lines.extend(["", "你可以在卡片中下载 Markdown，或进入求职 Agent 继续做题和查看反馈。", SAFETY_NOTE])
    return "\n".join(lines)


def build_summary_answer(artifact: dict) -> str:
    lines = ["已基于当前本地资料库完成岗位汇总。", "", "主要结果："]
    lines.extend(f"- {item}" for item in artifact.get("highlights", [])[:4])
    lines.extend(["", SAFETY_NOTE])
    return "\n".join(lines)


def build_report_answer(artifact: dict) -> str:
    lines = ["已生成岗位匹配报告。", "", "主要结果："]
    lines.extend(f"- {item}" for item in artifact.get("highlights", [])[:4])
    lines.extend(["", "报告已保存为独立副本，可下载或进入审核。", SAFETY_NOTE])
    return "\n".join(lines)


def build_artifact_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def dedupe(values: list[str]) -> list[str]:
    results = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results
