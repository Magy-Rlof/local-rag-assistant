import re

from .job_match_draft import extract_requirement_items
from .job_matcher import build_job_evidence
from .job_resolver import build_job_payload, find_best_job_candidate, to_source_file


MAX_SKILL_REQUIREMENTS = 16

INTERNAL_PROCESS_KEYWORDS = [
    "脱敏自测",
    "自测",
    "gate",
    "写入私有岗位目录",
    "私有岗位目录",
    "source_uid",
    "source uid",
    "normalized_key",
    "去重键",
    "去重候选键",
    "去重键版本",
    "去重键依据",
    "去重键置信度",
    "来源唯一键",
    "阶段4",
    "阶段 4",
    "阶段4.2m",
    "阶段 4.2m",
    "stage4",
    "stage 4",
]

CATEGORY_RULES = [
    (
        "RAG",
        [
            "RAG",
            "检索增强",
            "向量",
            "知识库",
            "引用来源",
        ],
    ),
    (
        "LLM",
        [
            "LLM",
            "大模型",
            "多模态",
            "生成式AI",
            "OpenAI",
            "DeepSeek",
            "LangChain",
            "Hugging Face",
            "自然语言处理",
            "NLP",
            "微调",
        ],
    ),
    (
        "AI/ML",
        [
            "AI/ML",
            "机器学习",
            "深度学习",
            "模型",
            "TensorFlow",
            "PyTorch",
            "scikit-learn",
            "算法",
            "预测性维护",
            "路径优化",
            "图像识别",
            "计算机视觉",
            "AOI",
        ],
    ),
    (
        "数据处理",
        [
            "Pandas",
            "Spark",
            "NumPy",
            "数据",
            "特征工程",
            "数据清洗",
            "时序",
            "多传感器",
        ],
    ),
    (
        "后端",
        [
            "API",
            "APIs",
            "HTTP",
            "JSON",
            "Markdown",
            "n8n",
            "Flask",
            "Streamlit",
            "C++",
            "Java",
            "Python",
            "接口",
            "企业应用程序",
        ],
    ),
    (
        "部署",
        [
            "部署",
            "AWS",
            "SageMaker",
            "Amazon Q",
            "边缘计算",
            "监控",
            "日志",
            "评估",
        ],
    ),
    (
        "工程化",
        [
            "pipeline",
            "pipelines",
            "端到端",
            "系统架构",
            "分布式",
            "高并发",
            "稳定性",
            "自动化",
            "调度",
            "协同",
            "MQTT",
            "OPC UA",
            "PLC",
            "SCADA",
            "IIoT",
            "IoT",
        ],
    ),
    (
        "业务理解",
        [
            "制造业",
            "生产排程",
            "设备管理",
            "供应链",
            "质量管控",
            "产线",
            "业务理解",
            "智能质检",
        ],
    ),
]

SKILL_KEYWORDS = [
    "RAG",
    "LLM",
    "多模态 AI",
    "多模态",
    "微调",
    "AWS",
    "SageMaker",
    "Amazon Q",
    "开源 AI 模型",
    "API",
    "HTTP API",
    "JSON",
    "Markdown",
    "n8n",
    "AI pipeline",
    "TensorFlow",
    "PyTorch",
    "Python",
    "C++",
    "Java",
    "Pandas",
    "Spark",
    "NumPy",
    "scikit-learn",
    "PLC",
    "SCADA",
    "AOI图像识别",
    "图像识别",
    "工业物联网",
    "IIoT",
    "MQTT",
    "OPC UA",
    "IoT数据采集",
    "Hugging Face",
    "自然语言处理",
    "Flask",
    "Streamlit",
    "OpenAI",
    "DeepSeek",
    "LangChain",
    "边缘计算",
    "分布式系统",
    "实时调度算法",
    "动态避障",
]


def build_job_skill_analysis(query: str) -> dict:
    candidate = find_best_job_candidate(query)
    if not candidate:
        return {
            "matched": False,
            "query": query,
            "job_profile": None,
            "skill_requirements": [],
            "warnings": ["未找到目标岗位。请使用来源岗位 ID、真实岗位来源标识或岗位文件名重试。"],
        }

    content = candidate.path.read_text(encoding="utf-8-sig")
    target_job = build_job_payload(candidate)
    source_file = to_source_file(candidate)
    job_evidence = build_job_evidence(content, candidate.title, source_file)
    profile = build_job_profile(target_job, job_evidence, content)
    skill_requirements = build_skill_requirements(profile)
    warnings = []
    if not skill_requirements:
        warnings.append("目标岗位资料中没有抽取到可用技能要求。")
    return {
        "matched": True,
        "query": query,
        "job_profile": profile,
        "skill_requirements": skill_requirements,
        "warnings": warnings,
    }


def build_job_profile(target_job: dict, job_evidence: dict, content: str) -> dict:
    metadata_keys = [
        "source_name",
        "source_channel",
        "marker",
        "salary",
        "experience",
        "education",
        "job_category",
        "headcount",
        "industry",
        "company_size",
        "company_nature",
    ]
    return {
        "job_id": target_job.get("source_job_id") or target_job.get("marker") or target_job.get("file_name", ""),
        "title": target_job.get("title", ""),
        "company": target_job.get("company", ""),
        "city": target_job.get("city", ""),
        "source_type": target_job.get("source", ""),
        "source_file": target_job.get("source_file", ""),
        "source_url": target_job.get("source_url", ""),
        "raw_requirements": job_evidence.get("requirements_text", ""),
        "responsibilities": job_evidence.get("responsibilities_text", ""),
        "metadata": {
            "file_name": target_job.get("file_name", ""),
            "raw_description_excerpt": job_evidence.get("raw_description_excerpt", ""),
            "available_sections": list_markdown_sections(content),
            **{key: target_job.get(key, "") for key in metadata_keys},
        },
    }


def build_skill_requirements(profile: dict) -> list[dict]:
    source_items = collect_requirement_items(profile)
    results = []
    seen_texts = set()
    for section, text in source_items:
        cleaned = clean_requirement_text(text)
        normalized = normalize_text(cleaned)
        if not cleaned or is_internal_process_requirement(cleaned) or normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        requirement_id = f"REQ{len(results) + 1:03d}"
        skill_name = extract_skill_name(cleaned)
        results.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": cleaned,
                "skill_name": skill_name,
                "category": classify_requirement(cleaned, skill_name),
                "difficulty_hint": infer_difficulty(cleaned),
                "evidence_level": "source_requirement" if section == "任职要求" else "source_context",
                "source_refs": [build_source_ref(profile, cleaned, section)],
            }
        )
        if len(results) >= MAX_SKILL_REQUIREMENTS:
            break
    return results


def collect_requirement_items(profile: dict) -> list[tuple[str, str]]:
    raw_description = profile.get("metadata", {}).get("raw_description_excerpt", "")
    requirements = extract_requirement_items(profile.get("raw_requirements", ""), raw_description)
    responsibilities = extract_requirement_items(profile.get("responsibilities", ""), raw_description)
    keyword_items = extract_inline_keyword_items(raw_description)

    items: list[tuple[str, str]] = []
    items.extend(("任职要求", item) for item in requirements)
    items.extend(("岗位职责", item) for item in responsibilities)
    items.extend(("原始岗位描述", item) for item in keyword_items)
    return items


def extract_inline_keyword_items(text: str) -> list[str]:
    if not text:
        return []
    results = []
    for sentence in split_sentences(text):
        if any(keyword.lower() in sentence.lower() for keyword in SKILL_KEYWORDS):
            results.append(sentence)
    return results


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    return [part.strip(" -；;。") for part in re.split(r"[。；;]\s*", normalized) if part.strip()]


def clean_requirement_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip(" -；;。")
    cleaned = re.sub(r"^(岗位职责|任职要求|职业技能|具备以下行业能力优先)[:：]\s*", "", cleaned)
    return cleaned


def is_internal_process_requirement(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    if text.startswith("真实岗位来源标识"):
        return True
    has_internal_keyword = any(normalize_text(keyword) in normalized for keyword in INTERNAL_PROCESS_KEYWORDS)
    has_skill_keyword = any(keyword.lower() in text.lower() for keyword in SKILL_KEYWORDS)
    if has_internal_keyword and not has_skill_keyword:
        return True
    process_only_patterns = [
        r"^用于.*自测",
        r"应经过\s*gate",
        r"写入.*目录",
        r"^阶段[\d.]+[a-zA-Z]*.*自测",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in process_only_patterns) and not has_skill_keyword


def classify_requirement(text: str, skill_name: str) -> str:
    haystack = f"{text} {skill_name}".lower()
    for category, keywords in CATEGORY_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return category
    return "业务理解"


def extract_skill_name(text: str) -> str:
    lowered = text.lower()
    for keyword in SKILL_KEYWORDS:
        if keyword.lower() in lowered:
            return keyword
    compact = re.sub(r"^(熟悉|精通|具备|掌握|了解|有|能|需)\s*", "", text)
    compact = re.split(r"[，,、：:（）()]", compact, maxsplit=1)[0].strip()
    return compact[:28] or "岗位能力"


def infer_difficulty(text: str) -> str:
    if any(keyword in text for keyword in ["架构", "高并发", "优化", "丰富", "精通", "深入", "调优", "实战经验"]):
        return "advanced"
    if any(keyword in text for keyword in ["部署", "集成", "开发", "设计", "实现", "熟练", "熟悉"]):
        return "intermediate"
    return "basic"


def build_source_ref(profile: dict, requirement_text: str, section: str) -> dict[str, str]:
    return {
        "type": "job_description",
        "source_id": profile.get("job_id", ""),
        "relative_path": profile.get("source_file", ""),
        "section": section,
        "quote": requirement_text,
    }


def list_markdown_sections(content: str) -> list[str]:
    sections = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            sections.append(stripped[3:].strip())
    return sections


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


# Universal capability-domain requirement classifier.
# This overrides the earlier keyword-only skill extraction without tying rules to job titles.
class RequirementCategory:
    TECHNICAL_SKILL = "technical_skill"
    TECHNICAL_RESPONSIBILITY = "technical_responsibility"
    EXPERIENCE_FILTER = "experience_filter"
    SOFT_SKILL = "soft_skill"
    BENEFIT_OR_CONDITION = "benefit_or_condition"
    UNKNOWN = "unknown"


QUESTIONABLE_CATEGORIES = {
    RequirementCategory.TECHNICAL_SKILL,
    RequirementCategory.TECHNICAL_RESPONSIBILITY,
    RequirementCategory.SOFT_SKILL,
    RequirementCategory.UNKNOWN,
}

DOMAIN_KEYWORDS = {
    "rag_retrieval": [
        "rag", "ragflow", "llamaindex", "lightrag", "graphrag", "vector", "embedding", "rerank",
        "source_refs", "knowledge base", "知识库", "检索", "召回", "重排", "引用",
        "鐭ヨ瘑搴", "鍚戦噺", "妫€绱", "閲嶆帓", "寮曠敤",
    ],
    "agent_orchestration": [
        "ai agent", "agent", "langchain", "coze", "dify", "tool use", "tools", "workflow",
        "orchestration", "澶氳疆", "浠诲姟鑷", "宸ュ叿", "娴佺▼缂", "鏅鸿兘浣",
    ],
    "llm_api_prompt": [
        "llm", "gpt", "claude", "openai", "deepseek", "prompt", "api", "large language",
        "澶фā", "澶ц", "涓婁笅鏂", "鍙傛暟", "璋冪敤",
    ],
    "backend_api": [
        "fastapi", "flask", "django", "http", "json", "api", "python", "java", "golang",
        "接口", "鎺ュ彛", "鍚庣", "schema",
    ],
    "linux_ops": [
        "linux", "shell", "systemd", "ssh", "cron", "kvm", "esxi", "服务器", "server",
        "存储", "网络设备", "巡检", "绯荤粺", "杩愮淮", "鎬ц兘璋", "鏁呴殰", "铏氭嫙",
    ],
    "web_server_ops": [
        "nginx", "apache", "tomcat", "web", "reverse proxy", "负载均衡", "瀹瑰櫒", "WEB",
    ],
    "database_ops": [
        "mysql", "oracle", "mongodb", "mssql", "sql", "database", "数据库", "鏁版嵁搴",
        "楂樺彲", "索引",
    ],
    "middleware_ops": [
        "redis", "kafka", "zookeeper", "mq", "消息队列", "缓存", "缂撳瓨", "闆嗙兢",
    ],
    "monitoring_ops": [
        "prometheus", "zabbix", "nagios", "cacti", "monitor", "alert", "日志", "鐩戞帶",
        "鍛婅", "鎸囨爣",
    ],
    "ci_cd_release": [
        "git", "svn", "jenkins", "ci", "cd", "release", "发布", "版本", "鍙戝竷", "鐗堟湰",
    ],
    "it_support": [
        "helpdesk", "pc", "office", "sharepoint", "sap", "wi-fi", "wifi", "firewall",
        "switch", "printer", "打印机", "局域网", "鐢ㄦ埛", "灞€鍩熺綉", "闃茬伀", "浜ゆ崲",
        "办公软件", "硬件", "电话", "弱电", "基础设施",
    ],
    "content_ops": [
        "短视频", "新媒体", "抖音", "小红书", "巨量千川", "投流", "广告", "素材", "账号",
        "运营", "内容", "转化", "鐭", "鏂板獟", "鎶栭煶", "灏忕孩", "宸ㄩ噺",
        "鎶曟祦", "骞垮憡", "绱犳潗", "璐﹀彿", "杩愯惀", "鍐呭", "杞寲",
    ],
    "business_analysis": [
        "业务", "需求", "指标", "验收", "场景", "转化", "流程", "涓氬姟", "闇€姹",
        "鎸囨爣", "楠屾敹", "鍦烘櫙",
    ],
}

EXPERIENCE_FILTER_KEYWORDS = [
    "学历", "本科", "大专", "硕士", "博士", "cet", "英语", "专业背景", "工作经验", "年经验",
    "年以上", "年以内", "项目佐证", "瀛﹀巻", "鏈", "澶т笓", "鑻辫", "涓撲笟",
    "缁忛獙", "骞", "椤圭洰浣愯瘉",
]

BENEFIT_OR_CONDITION_KEYWORDS = [
    "薪资", "福利", "五险", "公积金", "年终奖", "工作时间", "节假日", "生日", "团建",
    "加班", "大小周", "社保", "salary", "钖", "钖祫", "绂忓埄", "宸ヤ綔鏃堕棿",
    "绀句繚", "鍥㈤槦濂", "鑺傚亣",
]

SOFT_SKILL_KEYWORDS = [
    "沟通", "学习", "团队", "责任", "抗压", "态度", "执行力", "逻辑", "协作", "创新意识",
    "娌熼€", "瀛︿範", "鍥㈤槦", "璐ｄ换", "鎶楀帇", "鎵ц", "閫昏緫", "鍗忎綔",
]


def build_skill_requirements(profile: dict) -> list[dict]:
    source_items = collect_requirement_items(profile)
    results = []
    seen_texts = set()
    for section, text in source_items:
        cleaned = clean_requirement_text(text)
        normalized = normalize_text(cleaned)
        if not cleaned or is_internal_process_requirement(cleaned) or normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        classified = classify_requirement_record(cleaned, section)
        if classified["category"] in {
            RequirementCategory.EXPERIENCE_FILTER,
            RequirementCategory.BENEFIT_OR_CONDITION,
        }:
            continue
        requirement_id = f"REQ{len(results) + 1:03d}"
        results.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": cleaned,
                "skill_name": classified["skill_name"],
                "category": classified["primary_domain"] or classified["category"],
                "requirement_category": classified["category"],
                "skill_terms": classified["skill_terms"],
                "domains": classified["domains"],
                "is_questionable": classified["category"] in QUESTIONABLE_CATEGORIES,
                "classification_reason": classified["reason"],
                "difficulty_hint": infer_difficulty(cleaned),
                "evidence_level": "source_requirement" if section == "浠昏亴瑕佹眰" else "source_context",
                "source_refs": [build_source_ref(profile, cleaned, section)],
            }
        )
        if len(results) >= MAX_SKILL_REQUIREMENTS:
            break
    return results


def classify_requirement_record(text: str, section: str = "") -> dict:
    domains, skill_terms = map_capability_domains(text)
    if contains_any(text, BENEFIT_OR_CONDITION_KEYWORDS):
        category = RequirementCategory.BENEFIT_OR_CONDITION
        reason = "benefit or employment condition"
    elif is_experience_filter(text):
        category = RequirementCategory.EXPERIENCE_FILTER
        reason = "education, years, certificate, or evidence filter"
    elif domains:
        category = (
            RequirementCategory.TECHNICAL_RESPONSIBILITY
            if is_responsibility_section(section)
            else RequirementCategory.TECHNICAL_SKILL
        )
        reason = "matched capability-domain terms"
    elif contains_any(text, SOFT_SKILL_KEYWORDS):
        category = RequirementCategory.SOFT_SKILL
        reason = "soft-skill requirement"
    else:
        category = RequirementCategory.UNKNOWN
        reason = "no stable technical domain"
    primary_domain = domains[0] if domains else ""
    return {
        "text": text,
        "category": category,
        "skill_terms": skill_terms,
        "domains": domains,
        "primary_domain": primary_domain,
        "skill_name": build_skill_name(primary_domain, skill_terms, text),
        "is_questionable": category in QUESTIONABLE_CATEGORIES,
        "reason": reason,
    }


def map_capability_domains(text: str) -> tuple[list[str], list[str]]:
    lowered = text.lower()
    domains: list[str] = []
    skill_terms: list[str] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        matched = [keyword for keyword in keywords if keyword.lower() in lowered]
        if matched:
            domains.append(domain)
            skill_terms.extend(matched[:3])
    if "linux_ops" in domains and any(term in lowered for term in ["shell", "linux", "运维", "杩愮淮"]):
        domains = [domain for domain in domains if domain != "backend_api"]
    if "rag_retrieval" in domains and "agent" not in lowered and not any(term in lowered for term in ["coze", "dify", "tool use"]):
        domains = [domain for domain in domains if domain != "agent_orchestration"]
    if "llm_api_prompt" in domains and not any(
        term in lowered
        for term in ["llm", "gpt", "claude", "openai", "deepseek", "prompt", "large language", "大模型", "澶фā", "澶ц", "涓婁笅鏂"]
    ):
        domains = [domain for domain in domains if domain != "llm_api_prompt"]
    if "llm_api_prompt" in domains and "backend_api" in domains and not any(
        term in lowered for term in ["fastapi", "flask", "django", "http", "json", "接口开发", "后端", "鎺ュ彛寮", "鍚庣"]
    ):
        domains = [domain for domain in domains if domain != "backend_api"]
    if "it_support" in domains and any(term in lowered for term in ["服务器", "存储", "网络设备"]) and not any(
        term in lowered for term in ["pc", "office", "sharepoint", "printer", "打印机", "电话", "wi-fi", "wifi", "helpdesk", "办公软件"]
    ):
        domains = [domain for domain in domains if domain != "it_support"]
        if "linux_ops" not in domains:
            domains.append("linux_ops")
    if len(domains) > 1 and any(domain != "business_analysis" for domain in domains):
        domains = [domain for domain in domains if domain != "business_analysis"]
    return domains, dedupe_terms(skill_terms)


def is_experience_filter(text: str) -> bool:
    lowered = text.lower()
    if not contains_any(lowered, EXPERIENCE_FILTER_KEYWORDS):
        return False
    if any(keyword in lowered for keyword in ["学历", "本科", "大专", "cet", "瀛﹀巻", "鏈", "澶т笓"]):
        return True
    if re.search(r"\b\d+\s*[-~]?\s*\d*\s*(年|骞)", lowered):
        return True
    return "项目佐证" in text or "椤圭洰浣愯瘉" in text


def is_responsibility_section(section: str) -> bool:
    lowered = (section or "").lower()
    return any(keyword in lowered for keyword in ["职责", "responsibil", "宀椾綅鑱岃矗", "描述", "鎻忚"])


def build_skill_name(primary_domain: str, skill_terms: list[str], text: str) -> str:
    if primary_domain:
        return primary_domain
    if skill_terms:
        return skill_terms[0]
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:28] or "evidence_boundary"


def contains_any(text: str, keywords: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def dedupe_terms(values: list[str]) -> list[str]:
    results = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results
