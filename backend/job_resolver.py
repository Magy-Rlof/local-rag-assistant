import re
from dataclasses import dataclass
from pathlib import Path

from .document_service import get_category


FIELD_ALIASES = {
    "source": "来源",
    "source_channel": "来源渠道",
    "source_job_id": "来源岗位 ID",
    "source_url": "来源 URL",
    "marker": "真实岗位来源标识",
    "keyword": "抓取关键词",
    "fetched_at": "抓取时间",
    "converted_file_name": "转换文件名",
    "city": "城市",
    "company": "公司",
    "salary": "薪资范围",
    "experience": "经验要求",
    "education": "学历要求",
    "category": "招聘类型",
    "headcount": "招聘人数",
    "industry": "行业",
    "company_size": "公司规模",
    "company_nature": "公司性质",
}

JOB_IDENTIFIER_PATTERN = re.compile(
    r"(?i)(?:[a-z][a-z0-9]*_[a-z0-9][a-z0-9_]*|[a-z0-9][a-z0-9_-]+\.md|\b\d{8,}\b)"
)
JOB_IDENTIFIER_HINTS = ("stage", "jobonline", "unique", "source_job", "source-job", "job_dedupe")


@dataclass(frozen=True)
class JobCandidate:
    path: Path
    source: str
    title: str
    fields: dict[str, str]


def resolve_job(query: str) -> dict:
    best = find_best_job_candidate(query)
    if not best:
        return {
            "matched": False,
            "query": query,
            "job": None,
            "candidates": [],
        }

    normalized_query = normalize(query)
    candidates = [candidate for candidate in iter_job_candidates() if candidate_matches(candidate, normalized_query)]
    candidates.sort(key=lambda candidate: match_score(candidate, normalized_query), reverse=True)
    return {
        "matched": True,
        "query": query,
        "job": build_job_payload(best),
        "candidates": [build_candidate_payload(candidate) for candidate in candidates[:5]],
    }


def find_best_job_candidate(query: str) -> JobCandidate | None:
    normalized_query = normalize(query)
    if not normalized_query:
        raise ValueError("查询内容不能为空。")

    candidates = [candidate for candidate in iter_job_candidates() if candidate_matches(candidate, normalized_query)]
    candidates.sort(key=lambda candidate: match_score(candidate, normalized_query), reverse=True)
    return candidates[0] if candidates else None


def iter_job_candidates() -> list[JobCandidate]:
    config = get_category("jobs")
    candidates: list[JobCandidate] = []
    candidates.extend(iter_job_candidates_from_directory(config.private_directory, source="private"))
    if config.public_directory:
        candidates.extend(iter_job_candidates_from_directory(config.public_directory, source="public"))
    return candidates


def iter_job_candidates_from_directory(directory: Path, source: str) -> list[JobCandidate]:
    if not directory.exists():
        return []

    candidates: list[JobCandidate] = []
    for path in sorted(directory.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        title = parse_title(content) or path.stem
        fields = parse_basic_info(content)
        candidates.append(JobCandidate(path=path, source=source, title=title, fields=fields))
    return candidates


def parse_title(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def parse_basic_info(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    in_basic_info = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_basic_info = stripped == "## 基本信息"
            continue
        if not in_basic_info:
            continue
        match = re.match(r"^[-*]\s*([^：:]+)[：:]\s*(.*)$", stripped)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key:
            fields[key] = value
    return fields


def candidate_matches(candidate: JobCandidate, normalized_query: str) -> bool:
    values = searchable_values(candidate)
    if any(normalized_query in value for value in values):
        return True
    terms = extract_job_identifier_terms(normalized_query)
    return bool(terms) and any(term in value for term in terms for value in values)


def match_score(candidate: JobCandidate, normalized_query: str) -> int:
    file_name = normalize(candidate.path.name)
    file_stem = normalize(candidate.path.stem)
    source_job_id = normalize(candidate.fields.get(FIELD_ALIASES["source_job_id"], ""))
    marker = normalize(candidate.fields.get(FIELD_ALIASES["marker"], ""))
    source_url = normalize(candidate.fields.get(FIELD_ALIASES["source_url"], ""))

    if normalized_query in {file_name, file_stem, source_job_id, marker}:
        return 1000
    if normalized_query and normalized_query in source_job_id:
        return 900
    if normalized_query and normalized_query in marker:
        return 850
    if normalized_query and normalized_query in source_url:
        return 800
    if normalized_query and normalized_query in file_name:
        return 750
    term_score = 0
    for term in extract_job_identifier_terms(normalized_query):
        if term == source_job_id or term == marker or term == file_stem or term == file_name:
            term_score += 700
        elif term and term in source_job_id:
            term_score += 55 + min(len(term), 20) if len(term) >= 8 else 8
        elif term and term in marker:
            term_score += 50 + min(len(term), 20) if len(term) >= 8 else 8
        elif term and term in file_name:
            term_score += 45 + min(len(term), 20) if len(term) >= 8 else 8
        elif term and term in source_url:
            term_score += 35 + min(len(term), 20) if len(term) >= 8 else 5
    return term_score or 10


def searchable_values(candidate: JobCandidate) -> list[str]:
    values = [
        candidate.path.name,
        candidate.path.stem,
        candidate.title,
        *candidate.fields.values(),
    ]
    return [normalize(value) for value in values if value]


def build_job_payload(candidate: JobCandidate) -> dict:
    fields = candidate.fields
    return {
        "source_file": to_source_file(candidate),
        "file_name": candidate.path.name,
        "source": candidate.source,
        "title": candidate.title,
        "basic_info": fields,
        "source_name": fields.get(FIELD_ALIASES["source"], ""),
        "source_channel": fields.get(FIELD_ALIASES["source_channel"], ""),
        "source_job_id": fields.get(FIELD_ALIASES["source_job_id"], ""),
        "source_url": fields.get(FIELD_ALIASES["source_url"], ""),
        "marker": fields.get(FIELD_ALIASES["marker"], ""),
        "city": fields.get(FIELD_ALIASES["city"], ""),
        "company": fields.get(FIELD_ALIASES["company"], ""),
        "salary": fields.get(FIELD_ALIASES["salary"], ""),
        "experience": fields.get(FIELD_ALIASES["experience"], ""),
        "education": fields.get(FIELD_ALIASES["education"], ""),
        "job_category": fields.get(FIELD_ALIASES["category"], ""),
        "headcount": fields.get(FIELD_ALIASES["headcount"], ""),
        "industry": fields.get(FIELD_ALIASES["industry"], ""),
        "company_size": fields.get(FIELD_ALIASES["company_size"], ""),
        "company_nature": fields.get(FIELD_ALIASES["company_nature"], ""),
    }


def build_candidate_payload(candidate: JobCandidate) -> dict:
    return {
        "source_file": to_source_file(candidate),
        "file_name": candidate.path.name,
        "source": candidate.source,
        "title": candidate.title,
        "source_job_id": candidate.fields.get(FIELD_ALIASES["source_job_id"], ""),
        "marker": candidate.fields.get(FIELD_ALIASES["marker"], ""),
    }


def to_source_file(candidate: JobCandidate) -> str:
    if candidate.source == "private":
        return f"private_data/job_descriptions/{candidate.path.name}"
    return f"job_descriptions/{candidate.path.name}"


def normalize(value: str) -> str:
    return value.strip().lower()


def extract_job_identifier_terms(text: str) -> list[str]:
    normalized = normalize(text)
    terms: list[str] = []
    for match in JOB_IDENTIFIER_PATTERN.findall(normalized):
        term = match.strip(" ，,。；;：:（）()[]【】<>《》\"'")
        if not term or term in terms:
            continue
        if "_" in term or term.endswith(".md") or term.isdigit() or any(hint in term for hint in JOB_IDENTIFIER_HINTS):
            terms.append(term)
    for hint in JOB_IDENTIFIER_HINTS:
        if hint in normalized and hint not in terms:
            terms.append(hint)
    return terms
