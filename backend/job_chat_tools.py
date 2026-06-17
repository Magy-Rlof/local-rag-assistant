import re
from datetime import datetime

from .job_interview import build_interview_session
from .job_match_report_export import export_job_match_report, read_job_match_report_export
from .job_resolver import build_job_payload, iter_job_candidates
from .resume_revision_draft_export import export_resume_revision_draft, read_resume_revision_draft_export


SCOPE_NOTE = "范围限定：仅基于当前资料库、已索引、已合法导入的岗位资料，不代表全网或招聘平台全部岗位。"


def build_job_chat_tool_result(question: str, history: list[dict] | None = None) -> dict:
    current_text = question or ""
    context_text = build_intent_text(question, history or [])
    if not is_job_tool_intent(current_text) and not is_job_tool_intent(context_text):
        return {"artifacts": [], "answer_note": ""}

    artifacts: list[dict] = []
    notices: list[str] = []
    target_query = extract_target_query(current_text) or extract_target_query(context_text)
    intent = detect_job_tool_intent(current_text if is_job_tool_intent(current_text) else context_text)

    if intent == "job_summary":
        summary_artifact = build_job_summary_artifact(current_text or context_text)
        if summary_artifact:
            artifacts.append(summary_artifact)
        elif target_query:
            report = build_report_artifact(target_query)
            if report:
                artifacts.append(report)
        else:
            notices.append("未在当前资料库中匹配到可汇总的岗位。请先通过 n8n 合法导入岗位并更新索引，或提供岗位 ID、marker、文件名。")

    elif intent == "resume_revision":
        if not target_query:
            notices.append("简历差距分析需要一个明确岗位。请提供当前资料库中的岗位 ID、marker、文件名或明确标题。")
        else:
            artifact = build_resume_revision_artifact(target_query)
            if artifact:
                artifacts.append(artifact)
            else:
                notices.append("未能生成简历优化草稿。请确认目标岗位已合法导入，并且已设置当前简历。")

    elif intent == "interview":
        if not target_query:
            notices.append("面试模拟需要一个明确岗位。请提供当前资料库中的岗位 ID、marker、文件名或明确标题。")
        else:
            artifact = build_interview_artifact(target_query)
            if artifact:
                artifacts.append(artifact)
            else:
                notices.append("未能生成面试模拟卡片。请确认目标岗位已合法导入。")

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
    }


def append_job_tool_note(answer: str, tool_result: dict | None) -> str:
    note = (tool_result or {}).get("answer_note", "").strip()
    if not note:
        return answer
    return f"{answer.rstrip()}\n\n{note}" if answer.strip() else note


def is_job_tool_intent(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "岗位",
            "职位",
            "JD",
            "jd",
            "简历",
            "面试",
            "匹配",
            "差距",
            "不足",
            "优化",
            "报告",
            "求职",
        )
    )


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
    return best


def build_job_summary_artifact(text: str) -> dict | None:
    matches = find_matching_jobs(text)
    if not matches:
        return None

    lines = [
        "# 当前资料库岗位汇总",
        "",
        SCOPE_NOTE,
        "",
        f"- 匹配岗位数：{len(matches)}",
        "- 说明：这里只汇总本地资料库中已存在的岗位，不访问招聘平台、不登录、不绕过验证码或反爬限制。",
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

    content = "\n".join(lines)
    return {
        "artifact_id": build_artifact_id("job_summary"),
        "type": "job_summary",
        "title": "当前资料库岗位汇总",
        "description": f"在当前已合法导入岗位中匹配到 {len(matches)} 个候选岗位。",
        "query": text,
        "scope_note": SCOPE_NOTE,
        "content_preview": content[:500],
        "content_markdown": content,
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
    return {
        "artifact_id": build_artifact_id("job_match_report"),
        "type": "job_match_report",
        "title": "岗位匹配报告",
        "description": response.get("target_job", {}).get("title") or "已生成可审核岗位匹配报告。",
        "query": query,
        "scope_note": SCOPE_NOTE,
        "file_name": response.get("file_name", ""),
        "relative_path": response.get("relative_path", ""),
        "content_preview": response.get("content_preview", ""),
        "content_markdown": content,
        "review_status": response.get("review_status", ""),
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
    return {
        "artifact_id": build_artifact_id("resume_revision_draft"),
        "type": "resume_revision_draft",
        "title": "简历优化草稿",
        "description": response.get("target_job", {}).get("title") or "已生成私有简历优化草稿。",
        "query": query,
        "scope_note": SCOPE_NOTE,
        "file_name": response.get("file_name", ""),
        "relative_path": response.get("relative_path", ""),
        "content_preview": response.get("content_preview", ""),
        "content_markdown": content,
        "warnings": response.get("warnings", []),
        "actions": [
            {"label": "下载 Markdown", "kind": "download_markdown"},
            {"label": "进入审核", "kind": "open_job_agent"},
        ],
    }


def build_interview_artifact(query: str) -> dict | None:
    try:
        response = build_interview_session(query)
    except Exception:
        return None
    if not response.get("matched") or not response.get("session"):
        return None

    session = response["session"]
    questions = session.get("questions", [])
    lines = [
        "# 面试模拟",
        "",
        SCOPE_NOTE,
        "",
        "## 面试问题",
    ]
    for question in questions:
        lines.extend(
            [
                f"- Q{question.get('question_id')}: {question.get('question')}",
                f"  - 考察点：{question.get('intent') or question.get('requirement')}",
            ]
        )
    lines.extend(["", "## 回答边界", *[f"- {item}" for item in session.get("safety_notes", [])]])
    content = "\n".join(lines)
    return {
        "artifact_id": build_artifact_id("interview_session"),
        "type": "interview_session",
        "title": "面试模拟卡片",
        "description": f"已生成 {len(questions)} 个面试问题。",
        "query": query,
        "scope_note": SCOPE_NOTE,
        "content_preview": content[:500],
        "content_markdown": content,
        "warnings": response.get("warnings", []),
        "actions": [
            {"label": "下载 Markdown", "kind": "download_markdown"},
            {"label": "进入求职 Agent", "kind": "open_job_agent"},
        ],
    }


def build_answer_note(artifacts: list[dict], notices: list[str]) -> str:
    lines = ["**求职 Agent 工具结果**", "", SCOPE_NOTE]
    if artifacts:
        lines.extend(["", "已生成以下可审核卡片："])
        for artifact in artifacts:
            path = artifact.get("relative_path")
            path_note = f"（{path}）" if path else ""
            lines.append(f"- {artifact['title']}：{artifact['description']}{path_note}")
    if notices:
        lines.extend(["", "需要注意："])
        lines.extend(f"- {notice}" for notice in notices)
    lines.extend(
        [
            "",
            "安全边界：不自动投递，不覆盖真实简历，不绕过登录、验证码、反爬或平台限制。",
        ]
    )
    return "\n".join(lines)


def build_artifact_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
