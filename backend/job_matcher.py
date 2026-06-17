import re

from .document_service import get_current_resume
from .job_resolver import build_job_payload, find_best_job_candidate, to_source_file


MAX_EVIDENCE_CHARS = 2200


def build_job_match_context(query: str) -> dict:
    candidate = find_best_job_candidate(query)
    if not candidate:
        return {
            "matched": False,
            "query": query,
            "target_job": None,
            "current_resume": get_current_resume(),
            "job_evidence": None,
            "output_contract": build_output_contract(),
            "analysis_prompt": "",
            "warnings": ["未找到目标岗位。请使用来源岗位 ID、真实岗位来源标识或岗位文件名重试。"],
        }

    content = candidate.path.read_text(encoding="utf-8-sig")
    target_job = build_job_payload(candidate)
    current_resume = get_current_resume()
    job_evidence = build_job_evidence(content, candidate.title, to_source_file(candidate))
    warnings = build_warnings(current_resume, job_evidence)
    analysis_prompt = build_analysis_prompt(target_job, job_evidence, current_resume)

    return {
        "matched": True,
        "query": query,
        "target_job": target_job,
        "current_resume": current_resume,
        "job_evidence": job_evidence,
        "output_contract": build_output_contract(),
        "analysis_prompt": analysis_prompt,
        "warnings": warnings,
    }


def build_job_evidence(content: str, title: str, source_file: str) -> dict:
    raw_description = extract_fenced_text(extract_section(content, "原始岗位描述"))
    responsibilities_section = clean_section_text(extract_section(content, "岗位职责"))
    requirements_section = clean_section_text(extract_section(content, "任职要求"))

    responsibilities = responsibilities_section
    requirements = requirements_section
    if is_weak_section(responsibilities):
        responsibilities = extract_between(raw_description, "岗位职责", "任职要求") or raw_description
    if is_weak_section(requirements):
        requirements = extract_after(raw_description, "任职要求") or raw_description

    return {
        "source_file": source_file,
        "title": title,
        "responsibilities_text": truncate(responsibilities),
        "requirements_text": truncate(requirements),
        "raw_description_excerpt": truncate(raw_description),
    }


def build_output_contract() -> dict:
    return {
        "sections": [
            "目标岗位确认",
            "岗位核心要求",
            "当前资料匹配点",
            "简历修改建议候选素材",
            "面试准备问题",
            "不应夸大的能力边界",
        ],
        "resume_safety_rules": [
            "只生成候选素材、差异建议或单独草稿，不自动覆盖真实简历。",
            "区分可写入简历、只适合面试表达、不能声称。",
            "不得编造真实公司、项目经历、职责、年限、学历或成果。",
        ],
        "evidence_rules": [
            "岗位事实必须来自 target_job 或 job_evidence。",
            "简历和项目事实必须来自当前简历、项目资料或后续 RAG 引用。",
            "资料不足时说明缺少的具体资料，不得把推测写成事实。",
        ],
    }


def build_warnings(current_resume: dict | None, job_evidence: dict) -> list[str]:
    warnings: list[str] = []
    if not current_resume:
        warnings.append("当前未设置简历；后续只能生成岗位侧分析，不能生成完整简历匹配结论。")
    if is_weak_section(job_evidence["requirements_text"]):
        warnings.append("目标岗位任职要求文本较弱或缺失；后续分析需要标注岗位要求依据有限。")
    return warnings


def build_analysis_prompt(target_job: dict, job_evidence: dict, current_resume: dict | None) -> str:
    resume_line = (
        f"当前简历：{current_resume['source']}:{current_resume['name']}"
        if current_resume
        else "当前简历：未设置"
    )
    return f"""请基于已确认目标岗位生成求职分析草稿。

目标岗位确认：
- 岗位名称：{target_job['title']}
- 公司：{target_job['company'] or '来源未提供'}
- 城市：{target_job['city'] or '来源未提供'}
- 来源岗位 ID：{target_job['source_job_id'] or '来源未提供'}
- 来源文件：{target_job['source_file']}
- 来源 URL：{target_job['source_url'] or '来源未提供'}
- {resume_line}

岗位职责证据：
{job_evidence['responsibilities_text'] or '来源未提供'}

任职要求证据：
{job_evidence['requirements_text'] or '来源未提供'}

输出结构：
1. 目标岗位确认
2. 岗位核心要求
3. 当前资料匹配点
4. 简历修改建议候选素材
5. 面试准备问题
6. 不应夸大的能力边界

边界：
- 不自动覆盖真实简历。
- 不编造公司、项目、职责、年限、学历或成果。
- 把“可写入简历”“只适合面试表达”“不能声称”分开。
- 资料不足时说明具体缺少什么。
"""


def extract_section(content: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", content[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content)
    return content[start:end].strip()


def extract_fenced_text(section: str) -> str:
    match = re.search(r"```(?:\w+)?\s*(.*?)```", section, re.DOTALL)
    if match:
        return match.group(1).strip()
    return clean_section_text(section)


def clean_section_text(section: str) -> str:
    lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("- 真实岗位来源标识"):
            continue
        if stripped in {"- 来源未提供", "来源未提供"}:
            continue
        lines.append(stripped.lstrip("- ").strip())
    return "\n".join(lines).strip()


def extract_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        return text[start:].strip()
    return text[start:end].strip()


def extract_after(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    return text[start + len(marker) :].strip()


def is_weak_section(text: str) -> bool:
    stripped = text.strip()
    return not stripped or stripped == "来源未提供" or len(stripped) < 12


def truncate(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= MAX_EVIDENCE_CHARS:
        return cleaned
    return cleaned[:MAX_EVIDENCE_CHARS].rstrip() + " ...（已截断）"
