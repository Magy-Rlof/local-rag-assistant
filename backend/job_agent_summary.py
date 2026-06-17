from .job_interview import build_interview_session
from .job_match_draft import build_job_match_draft


def build_job_agent_summary(query: str) -> dict:
    draft_response = build_job_match_draft(query)
    interview_response = build_interview_session(query)
    warnings = merge_warnings(draft_response.get("warnings", []), interview_response.get("warnings", []))

    if not draft_response["matched"]:
        return {
            "matched": False,
            "query": query,
            "target_job": None,
            "current_resume": draft_response["current_resume"],
            "summary": None,
            "warnings": warnings,
        }

    draft = draft_response["draft"]
    session = interview_response["session"] if interview_response["matched"] else None
    summary = {
        "target_confirmation": draft["target_confirmation"],
        "pipeline_status": build_pipeline_status(draft, session),
        "available_actions": build_available_actions(),
        "disabled_actions": build_disabled_actions(),
        "draft_preview": build_draft_preview(draft),
        "interview_preview": build_interview_preview(session),
        "safety_notes": build_safety_notes(draft, session),
        "recommended_next_steps": build_recommended_next_steps(draft, session),
    }
    return {
        "matched": True,
        "query": query,
        "target_job": draft_response["target_job"],
        "current_resume": draft_response["current_resume"],
        "summary": summary,
        "warnings": warnings,
    }


def build_pipeline_status(draft: dict, session: dict | None) -> list[dict]:
    return [
        {
            "step": "target_job_resolved",
            "label": "目标岗位确认",
            "status": "ready",
            "detail": f"{draft['target_confirmation']['title']} / {draft['target_confirmation']['source_job_id']}",
        },
        {
            "step": "auditable_match_draft",
            "label": "可审核匹配草稿",
            "status": "ready",
            "detail": f"{len(draft['job_core_requirements'])} 条岗位要求，{len(draft['resume_revision_candidates']['cannot_claim'])} 条不能自动声称的能力。",
        },
        {
            "step": "interview_session",
            "label": "面试模拟问题",
            "status": "ready" if session else "not_ready",
            "detail": f"{len(session['questions'])} 个问题。" if session else "面试 session 未生成。",
        },
        {
            "step": "auditable_match_report",
            "label": "可审核求职报告",
            "status": "ready",
            "detail": "可保存为本地私有报告副本，聚合目标岗位、草稿和面试准备。",
        },
        {
            "step": "batch_match_report_queue",
            "label": "批量报告队列",
            "status": "ready",
            "detail": "可基于多个已入库岗位生成本地私有批量报告清单，不访问招聘平台。",
        },
        {
            "step": "resume_revision_draft",
            "label": "简历差异草稿",
            "status": "ready",
            "detail": "可保存为本地私有差异草稿副本，但不会自动覆盖真实简历。",
        },
        {
            "step": "resume_write",
            "label": "可写入简历内容",
            "status": "needs_evidence",
            "detail": "需要先用简历和项目资料引用证明，当前不会自动写入简历。",
        },
        {
            "step": "auto_apply",
            "label": "自动投递",
            "status": "disabled",
            "detail": "系统边界禁止自动投递。",
        },
    ]


def build_available_actions() -> list[dict]:
    return [
        {
            "action": "resolve_target_job",
            "label": "确认目标岗位",
            "endpoint": "GET /api/jobs/resolve?query=...",
        },
        {
            "action": "build_match_context",
            "label": "生成岗位匹配上下文",
            "endpoint": "GET /api/jobs/match/context?query=...",
        },
        {
            "action": "build_auditable_draft",
            "label": "生成可审核求职分析草稿",
            "endpoint": "GET /api/jobs/match/draft?query=...",
        },
        {
            "action": "export_auditable_draft",
            "label": "保存可审核草稿副本",
            "endpoint": "POST /api/jobs/match/draft/export",
        },
        {
            "action": "list_auditable_draft_exports",
            "label": "查看已保存草稿副本列表",
            "endpoint": "GET /api/jobs/match/draft/exports",
        },
        {
            "action": "read_auditable_draft_export",
            "label": "读取已保存草稿副本",
            "endpoint": "GET /api/jobs/match/draft/exports/{file_name}",
        },
        {
            "action": "delete_auditable_draft_export",
            "label": "删除已保存草稿副本",
            "endpoint": "DELETE /api/jobs/match/draft/exports/{file_name}",
        },
        {
            "action": "export_resume_revision_draft",
            "label": "保存简历差异草稿副本",
            "endpoint": "POST /api/jobs/match/resume-diff/export",
        },
        {
            "action": "list_resume_revision_draft_exports",
            "label": "查看已保存简历差异草稿",
            "endpoint": "GET /api/jobs/match/resume-diff/exports",
        },
        {
            "action": "read_resume_revision_draft_export",
            "label": "读取已保存简历差异草稿",
            "endpoint": "GET /api/jobs/match/resume-diff/exports/{file_name}",
        },
        {
            "action": "compare_resume_revision_with_current",
            "label": "对比当前简历与差异草稿",
            "endpoint": "GET /api/jobs/match/resume-diff/exports/{file_name}/compare-current",
        },
        {
            "action": "delete_resume_revision_draft_export",
            "label": "删除已保存简历差异草稿",
            "endpoint": "DELETE /api/jobs/match/resume-diff/exports/{file_name}",
        },
        {
            "action": "queue_resume_write_review",
            "label": "加入真实简历写回前审核队列",
            "endpoint": "POST /api/jobs/match/resume-write-review/queue",
        },
        {
            "action": "list_resume_write_review_queue",
            "label": "查看写回前审核队列",
            "endpoint": "GET /api/jobs/match/resume-write-review/queue",
        },
        {
            "action": "update_resume_write_review",
            "label": "更新写回前审核状态",
            "endpoint": "PUT /api/jobs/match/resume-write-review/queue/{file_name}/review",
        },
        {
            "action": "export_auditable_match_report",
            "label": "保存可审核求职分析报告",
            "endpoint": "POST /api/jobs/match/report/export",
        },
        {
            "action": "list_auditable_match_reports",
            "label": "查看已保存求职分析报告",
            "endpoint": "GET /api/jobs/match/report/exports",
        },
        {
            "action": "read_auditable_match_report",
            "label": "读取已保存求职分析报告",
            "endpoint": "GET /api/jobs/match/report/exports/{file_name}",
        },
        {
            "action": "update_auditable_match_report_review",
            "label": "更新求职分析报告审核状态",
            "endpoint": "PUT /api/jobs/match/report/exports/{file_name}/review",
        },
        {
            "action": "delete_auditable_match_report",
            "label": "删除已保存求职分析报告",
            "endpoint": "DELETE /api/jobs/match/report/exports/{file_name}",
        },
        {
            "action": "queue_batch_match_reports",
            "label": "生成批量求职分析报告队列",
            "endpoint": "POST /api/jobs/match/report/batch-queue",
        },
        {
            "action": "list_batch_match_report_queue",
            "label": "查看批量求职分析报告队列",
            "endpoint": "GET /api/jobs/match/report/batch-queue",
        },
        {
            "action": "update_batch_match_report_review",
            "label": "更新批量报告队列审核状态",
            "endpoint": "PUT /api/jobs/match/report/batch-queue/{file_name}/review",
        },
        {
            "action": "delete_batch_match_report_queue",
            "label": "删除批量报告队列清单",
            "endpoint": "DELETE /api/jobs/match/report/batch-queue/{file_name}",
        },
        {
            "action": "start_interview_session",
            "label": "生成面试模拟问题",
            "endpoint": "GET /api/jobs/interview/session?query=...",
        },
        {
            "action": "review_interview_answer",
            "label": "反馈面试回答",
            "endpoint": "POST /api/jobs/interview/feedback",
        },
    ]


def build_disabled_actions() -> list[dict]:
    return [
        {
            "action": "auto_overwrite_resume",
            "reason": "禁止自动覆盖真实简历；只能生成候选表达、差异建议或单独副本。",
        },
        {
            "action": "auto_apply_job",
            "reason": "禁止自动投递、自动收藏、自动沟通招聘方。",
        },
        {
            "action": "bypass_platform_restrictions",
            "reason": "禁止绕过登录、验证码、反爬、风控、签名或加密限制。",
        },
        {
            "action": "claim_unverified_skills",
            "reason": "不能把岗位要求或面试表达写成用户已经具备的真实能力。",
        },
    ]


def build_draft_preview(draft: dict) -> dict:
    revision = draft["resume_revision_candidates"]
    return {
        "requirements_count": len(draft["job_core_requirements"]),
        "responsibilities_count": len(draft["job_core_responsibilities"]),
        "can_write_count": len(revision["can_write_to_resume"]),
        "requires_evidence_count": len(revision["requires_evidence_before_resume"]),
        "interview_only_count": len(revision["interview_only"]),
        "cannot_claim_count": len(revision["cannot_claim"]),
        "evidence_gaps": draft["evidence_gaps"],
    }


def build_interview_preview(session: dict | None) -> dict:
    if not session:
        return {
            "question_count": 0,
            "first_question": "",
            "answer_guidance": [],
        }
    first_question = session["questions"][0]["question"] if session["questions"] else ""
    return {
        "question_count": len(session["questions"]),
        "first_question": first_question,
        "answer_guidance": session["answer_guidance"],
    }


def build_safety_notes(draft: dict, session: dict | None) -> list[str]:
    notes = []
    notes.extend(draft["safety_notes"])
    if session:
        notes.extend(session["safety_notes"])
    notes.extend(
        [
            "本聚合接口只读取和组合本地已有能力，不保存文件、不触发索引、不调用 LLM。",
            "当前 summary 表示 Agent-like 后端入口可用，不代表完整产品闭环已经全部完成。",
        ]
    )
    return dedupe(notes)


def build_recommended_next_steps(draft: dict, session: dict | None) -> list[str]:
    steps = [
        "先核对 target_confirmation 是否为当前目标岗位。",
        "查看 draft_preview.evidence_gaps，补齐简历和项目证据。",
        "使用 interview_preview.first_question 开始第一轮面试准备。",
        "所有可写入简历的内容必须先经过用户审核。",
    ]
    if draft["resume_revision_candidates"]["requires_evidence_before_resume"]:
        steps.append("将 requires_evidence_before_resume 中的候选方向逐条映射到真实简历或项目资料引用。")
    if session:
        steps.append("回答面试问题后调用 POST /api/jobs/interview/feedback 获取结构化反馈。")
    return steps


def merge_warnings(*groups: list[str]) -> list[str]:
    warnings: list[str] = []
    for group in groups:
        warnings.extend(group)
    return dedupe(warnings)


def dedupe(values: list[str]) -> list[str]:
    results: list[str] = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results
