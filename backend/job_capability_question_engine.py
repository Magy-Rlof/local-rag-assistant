ANSWER_KEYS = ["A", "B", "C", "D"]
DEFAULT_RULE_QUESTION_COUNT = 8
RULE_BLOCKED_CATEGORIES = {"experience_filter", "benefit_or_condition"}

DOMAIN_PRIORITY = [
    "agent_orchestration",
    "rag_retrieval",
    "llm_api_prompt",
    "backend_api",
    "linux_ops",
    "web_server_ops",
    "database_ops",
    "middleware_ops",
    "monitoring_ops",
    "ci_cd_release",
    "it_support",
    "content_ops",
    "soft_skill",
    "business_analysis",
    "evidence_boundary",
]

DOMAIN_SPECS = {
    "rag_retrieval": {
        "label": "RAG retrieval",
        "choice": [
            (
                "RAG 检索链路中，chunk、embedding、召回和 rerank 的核心分工是什么？",
                "chunk 负责切分知识片段，embedding 负责语义表示，召回找候选片段，rerank 对候选片段重新排序。",
                ["rerank 直接生成最终答案，不需要召回。", "embedding 只负责页面展示，不参与检索。", "chunk 越长越好，可以完全跳过来源追踪。"],
                "RAG 质量依赖可追踪片段、语义检索和排序策略，不能只看最终文本是否流畅。",
            ),
            (
                "评估 RAG 召回质量时，哪一组指标最能发现岗位知识库问答问题？",
                "命中率、召回片段相关性、来源覆盖、排序质量和无结果 fallback 记录。",
                ["只看回答字数是否足够长。", "只看模型是否给出肯定语气。", "只要向量库有数据就不需要评估。"],
                "RAG 评估必须核对问题、召回片段和 source_refs，不能只看生成结果。",
            ),
        ],
        "true_false": [
            ("RAG 回答必须能追溯到具体来源片段，否则很难判断答案是否来自岗位资料。", "正确", "source_refs 是事实核验边界，不是装饰字段。"),
            ("只要大模型回答看起来合理，RAG 系统就可以忽略检索无结果和低相关片段。", "错误", "检索失败和低相关片段必须进入 fallback 或风险提示。"),
        ],
        "short": [
            ("请说明如何为一个 RAG 知识库设计召回质量验收方案。", ["准备代表性问题集", "检查召回片段和 source_refs", "记录无结果、噪声和排序问题"]),
            ("请说明 RAG 中 source_refs 失真会带来哪些风险，以及如何修复。", ["答案不可核验", "可能引用错误岗位资料", "绑定片段 ID 并做输出校验"]),
        ],
    },
    "agent_orchestration": {
        "label": "AI Agent orchestration",
        "choice": [
            (
                "设计 Agent 工具调用流程时，最需要先明确哪一组内容？",
                "工具输入输出 schema、调用前置条件、错误处理、超时重试、状态记录和停止条件。",
                ["先让 Agent 自由循环调用工具，再观察是否能成功。", "只写工具名称，不定义参数和错误码。", "把所有业务逻辑都放进提示词，工具无需校验。"],
                "Agent 落地的关键是可控编排、明确边界和失败恢复。",
            ),
            (
                "多轮 Agent 对话中，避免错误工具调用不断累积的关键做法是什么？",
                "维护状态、限制调用次数、记录中间结果，并在低置信度或重复失败时触发人工确认或 fallback。",
                ["允许无限调用，直到模型自己停止。", "每轮都丢弃上下文，避免保存状态。", "只保留最终回答，不记录工具执行结果。"],
                "Agent 需要状态管理、循环控制和可审计工具结果。",
            ),
        ],
        "true_false": [
            ("Agent 工具调用链应明确输入输出、权限边界和失败处理，不能只依赖提示词自我约束。", "正确", "工具编排需要工程契约和运行保护。"),
            ("只要岗位提到 Agent，就可以把工业数据清洗题作为通用替代题。", "错误", "Agent 能力域应围绕流程编排、工具调用、多轮状态和 LLM 集成。"),
        ],
        "short": [
            ("请说明一个 Agent 工具调用模块上线前应验证哪些内容。", ["工具 schema 和权限", "超时、重试和错误处理", "调用日志、停止条件和回滚方案"]),
            ("请说明如何避免 Agent 陷入无限循环或反复调用错误工具。", ["设置调用上限", "检测重复失败", "引入人工确认或 fallback"]),
        ],
    },
    "llm_api_prompt": {
        "label": "LLM API and Prompt",
        "choice": [
            (
                "调用大模型 API 时，接口层最需要控制哪一组风险？",
                "超时、限流、成本、输出格式、上下文长度、敏感信息和失败 fallback。",
                ["只关注模型名称是否热门。", "不需要限制输出格式，前端自行猜测即可。", "把完整隐私材料默认发给模型。"],
                "LLM API 是工程依赖，需要稳定契约、成本控制和隐私边界。",
            ),
            (
                "Prompt 工程中，结构化输出不稳定时应优先怎么处理？",
                "收紧 schema、增加示例、做 JSON 校验，并在校验失败时修复或回退。",
                ["继续提高 temperature，让输出更丰富。", "直接展示未校验文本。", "删除错误处理以减少代码量。"],
                "Prompt 结果进入系统链路前必须可解析、可校验。",
            ),
        ],
        "true_false": [
            ("大模型 API 接入应记录模型版本、参数、超时和输出校验结果，方便复现问题。", "正确", "可观测性和复现能力是 LLM 应用稳定性的基础。"),
            ("Prompt 写得越长越好，不需要考虑上下文窗口和结构化输出。", "错误", "Prompt 应服务于任务约束和可解析输出。"),
        ],
        "short": [
            ("请说明 LLM API 调用失败时的 fallback 方案应包含哪些环节。", ["错误分类", "重试和降级", "结构化告警和用户提示"]),
            ("请说明如何评估一个 Prompt 是否适合生产链路。", ["输出稳定可解析", "边界条件覆盖", "成本、延迟和安全约束明确"]),
        ],
    },
    "backend_api": {
        "label": "backend API",
        "choice": [
            (
                "后端 API 对外提供服务时，接口契约最需要明确哪一组内容？",
                "请求参数、响应 schema、错误码、鉴权、超时、幂等性和日志追踪。",
                ["只定义接口名称，字段含义由调用方猜测。", "只保证本机 demo 可用即可。", "错误时返回任意自然语言文本。"],
                "稳定 API 依赖明确契约和可观测错误处理。",
            ),
            (
                "Python/FastAPI 服务上线前，哪项检查更符合工程实践？",
                "校验输入输出模型、异常处理、健康检查、日志和部署配置。",
                ["只在开发机手动点一次接口。", "隐藏所有错误信息且不记录日志。", "不区分业务错误和系统错误。"],
                "后端服务需要可测试、可部署、可追踪。",
            ),
        ],
        "true_false": [
            ("后端接口字段变更应考虑版本兼容或迁移策略，避免直接破坏调用方。", "正确", "接口契约变更会影响前端、自动化和外部调用。"),
            ("只要会写 Python，就可以默认跳过接口契约、错误处理和部署约束。", "错误", "Python 可能服务于脚本、后端、运维或数据处理，题目必须按来源要求对应能力域。"),
        ],
        "short": [
            ("请说明岗位资料查询 API 应如何保证返回结果可被前端稳定消费。", ["固定响应 schema", "清晰错误码", "source_refs 和日志可追踪"]),
            ("请说明接口超时和重试策略设计时要注意哪些边界。", ["区分可重试错误", "设置超时和重试上限", "保持幂等和日志记录"]),
        ],
    },
    "linux_ops": {
        "label": "Linux operations",
        "choice": [
            (
                "Linux 服务无法启动时，排查顺序哪一项更合理？",
                "查看 systemd 状态、服务日志、端口占用、配置变更、权限和依赖资源。",
                ["先重装系统，避免分析日志。", "只看 CPU 使用率，不看服务日志。", "直接修改生产配置但不记录变更。"],
                "运维排障需要从状态、日志、配置和依赖逐层定位。",
            ),
            (
                "定位 Linux 主机 CPU、内存或磁盘 IO 异常时，哪组信息更关键？",
                "进程资源占用、系统负载、磁盘队列、日志异常、近期发布和容量趋势。",
                ["只看当前登录用户是谁。", "只重启服务，不保留现场信息。", "只检查前端页面是否能打开。"],
                "系统性能问题要结合指标、进程、日志和变更历史。",
            ),
        ],
        "true_false": [
            ("Linux 运维题应围绕系统管理、服务配置、性能、日志和故障处理，不应无来源地扩展到 AI 模型部署。", "正确", "题目主题必须和来源要求一致。"),
            ("遇到线上故障时，保留日志、变更记录和回滚路径比盲目重启更可靠。", "正确", "排障需要可追踪证据和恢复路径。"),
        ],
        "short": [
            ("请说明 Linux 服务器磁盘空间异常增长时的排查步骤。", ["定位目录和大文件", "确认日志轮转和业务写入", "评估清理、扩容和告警策略"]),
            ("请说明 Shell/Python 运维脚本如何处理日志、错误和幂等性。", ["记录关键执行日志", "捕获错误并退出", "重复执行不破坏状态"]),
        ],
    },
    "web_server_ops": {
        "label": "web server operations",
        "choice": [
            (
                "Nginx/Tomcat 服务访问异常时，哪组排查更贴近 Web 容器运维？",
                "检查进程、端口、配置语法、访问日志、错误日志、上游状态和防火墙。",
                ["只修改首页文案，不检查服务状态。", "只清理浏览器缓存，不看上游服务。", "只重启一次，不保留日志和配置变更记录。"],
                "Web 容器排障应围绕配置、进程、网络和上游依赖。",
            ),
        ],
        "true_false": [
            ("反向代理配置变更前后应做语法校验、灰度或回滚准备。", "正确", "配置错误会直接影响服务可用性。"),
            ("Nginx 题可以直接替换成 RAG 召回题。", "错误", "Web server 能力域和 RAG 能力域不能混用。"),
        ],
        "short": [
            ("请说明 Nginx 反向代理 502 问题的排查路径。", ["检查上游服务", "查看错误日志", "验证网络、端口和超时配置"]),
        ],
    },
    "database_ops": {
        "label": "database operations",
        "choice": [
            (
                "数据库连接或性能异常时，哪一组信息最关键？",
                "连接状态、错误日志、慢查询、资源使用、网络连通性和近期配置变更。",
                ["只检查页面样式。", "只看数据库名称，不看复制状态。", "只重启应用服务，不检查数据库日志。"],
                "数据库问题应从连接、日志、查询、资源和变更记录定位。",
            ),
            (
                "验证数据库备份恢复方案是否可用，最关键的做法是什么？",
                "定期在隔离环境恢复备份，核对数据完整性、恢复耗时和恢复点目标。",
                ["只确认备份文件存在。", "只在生产库上直接覆盖恢复。", "只看磁盘剩余空间。"],
                "备份策略必须通过恢复演练验证。",
            ),
        ],
        "true_false": [
            ("慢查询优化通常要结合执行计划、索引、数据量和业务访问模式判断。", "正确", "数据库优化不能只靠猜测字段名。"),
            ("数据库题可以无条件替换成工业数据清洗题。", "错误", "数据库运维和数据清洗不是同一能力域。"),
        ],
        "short": [
            ("请说明数据库慢查询问题的基本排查步骤。", ["定位慢 SQL 和执行计划", "检查索引和数据量", "评估改写、缓存或拆分方案"]),
            ("请说明数据库高可用方案需要关注哪些运行指标。", ["复制延迟", "故障切换耗时", "备份恢复可用性"]),
        ],
    },
    "middleware_ops": {
        "label": "middleware operations",
        "choice": [
            (
                "Redis/Kafka/ZooKeeper 集群故障排查时，哪组信息更关键？",
                "节点状态、集群拓扑、日志、资源使用、网络连通性和客户端错误。",
                ["只看网页标题。", "只检查客户端页面样式。", "只重启业务应用，不看中间件节点状态。"],
                "中间件排障应围绕集群状态、日志、资源和客户端表现。",
            ),
        ],
        "true_false": [
            ("消息队列积压需要同时检查生产速度、消费速度、消费者错误和分区分配。", "正确", "积压通常是链路问题，不是单点现象。"),
            ("缓存集群题可以直接生成 Linux 内核编译题。", "错误", "题目应保持在来源要求指向的中间件范围内。"),
        ],
        "short": [
            ("请说明 Kafka 消费积压的排查路径。", ["检查消费组 lag", "查看消费者错误和吞吐", "评估扩容、限流或重试策略"]),
        ],
    },
    "monitoring_ops": {
        "label": "monitoring operations",
        "choice": [
            (
                "设计监控告警时，哪组内容更能减少误报和漏报？",
                "核心指标、阈值依据、告警分级、静默策略、通知路径和处理手册。",
                ["所有指标都设置同一个固定阈值。", "只在用户投诉后人工查看。", "只保留告警截图不记录处理过程。"],
                "监控告警要服务于可行动的故障响应。",
            ),
        ],
        "true_false": [
            ("Prometheus/Zabbix 告警应结合业务影响和处理手册，而不只是堆积指标。", "正确", "可行动性是告警质量的重要标准。"),
            ("监控题可以无来源地扩展成 AI 训练集评估题。", "错误", "监控运维和 AI 训练评估不能混用。"),
        ],
        "short": [
            ("请说明如何为一个 Web 服务设计基础监控指标。", ["可用性和响应时间", "错误率和资源使用", "告警分级和处理手册"]),
        ],
    },
    "ci_cd_release": {
        "label": "CI/CD release",
        "choice": [
            (
                "使用 Git/Jenkins 做发布时，哪项最能降低发布风险？",
                "明确分支策略、构建产物、环境配置、发布检查、回滚方案和审计日志。",
                ["直接在生产机手工改代码。", "不记录版本号，方便快速覆盖。", "发布失败后删除日志。"],
                "发布管理需要可复现、可回滚、可审计。",
            ),
        ],
        "true_false": [
            ("发布前应确认构建版本、配置差异、依赖状态和回滚路径。", "正确", "这些信息决定发布可控性。"),
            ("版本管理只需要记住最后一次提交人，不需要分支和 tag。", "错误", "版本管理需要稳定追踪发布来源。"),
        ],
        "short": [
            ("请说明 Jenkins 发布流水线应包含哪些关键阶段。", ["拉取代码和构建", "自动检查和制品归档", "部署、验证和回滚"]),
        ],
    },
    "it_support": {
        "label": "IT support",
        "choice": [
            (
                "处理 Helpdesk 工单时，哪种做法更符合 IT 支持流程？",
                "记录用户现象、影响范围、设备和账号信息，分级处理并保留解决记录。",
                ["只让用户重启，不记录任何信息。", "直接关闭工单，避免积压。", "把所有问题都升级给开发团队。"],
                "IT 支持需要可追踪工单、分级和知识沉淀。",
            ),
            (
                "排查办公网络 Wi-Fi 不稳定时，哪组信息最相关？",
                "终端范围、AP/交换机状态、信号强度、认证日志、IP 分配和近期变更。",
                ["只检查 RAG chunk 设置。", "只查看广告投放转化。", "只调整数据库主从复制。"],
                "办公网络问题应围绕终端、网络设备、认证和地址分配排查。",
            ),
        ],
        "true_false": [
            ("PC、Office、局域网和打印机支持题应围绕用户问题定位和资产维护。", "正确", "这是 IT support 的主要能力域。"),
            ("IT 支持问题可以不记录工单、不确认影响范围，直接口头处理。", "错误", "IT 支持需要可追踪记录、影响范围和处理闭环。"),
        ],
        "short": [
            ("请说明处理 Helpdesk 用户支持工单的基本闭环。", ["确认用户现象和影响范围", "定位账号、终端、网络或软件问题", "记录处理结果并沉淀知识"]),
        ],
    },
    "content_ops": {
        "label": "content operations",
        "choice": [
            (
                "短视频投流效果分析时，哪组指标最应优先关注？",
                "曝光、点击率、转化率、获客成本、素材消耗、留存或成交质量。",
                ["只看点赞数，不看转化和成本。", "只看单条素材主观好不好看。", "只看投放消耗，不分析人群和转化质量。"],
                "新媒体运营题应围绕内容、投流、素材和转化指标。",
            ),
            (
                "判断短视频选题是否有效时，哪种做法更合理？",
                "结合账号定位、平台趋势、完播互动、转化数据和竞品内容持续复盘。",
                ["只按个人喜好选题。", "只复制竞品标题，不看账号定位。", "只看发布数量，不复盘互动和转化。"],
                "内容运营要基于平台、用户和转化数据迭代。",
            ),
        ],
        "true_false": [
            ("新媒体运营岗位的面试题应围绕内容策划、平台趋势、投流和转化分析。", "正确", "题目必须贴合来源岗位职责。"),
            ("新媒体运营岗位可以默认生成 RAG、Linux、数据库高可用题。", "错误", "这些属于无关技术能力域，除非来源要求明确包含。"),
        ],
        "short": [
            ("请说明如何复盘一条短视频广告素材的投放效果。", ["看曝光、点击和转化", "分析素材卖点和受众", "提出迭代测试方案"]),
            ("请说明账号孵化早期如何规划内容节奏。", ["明确账号定位", "建立选题池和发布节奏", "用互动和转化数据复盘"]),
        ],
    },
    "soft_skill": {
        "label": "soft skill evidence",
        "choice": [
            (
                "面试中核验沟通、协作或责任感这类软能力时，哪种回答最可验证？",
                "结合真实场景说明目标、对象、个人行动、冲突处理和结果证据。",
                ["只说自己沟通能力强。", "把软能力改写成无关专业能力。", "只复述岗位原文，不给任何场景。"],
                "软能力应通过行为证据核验，不能生成无关技术题。",
            ),
            (
                "面对“学习能力强、执行力好”这类岗位要求，面试追问应优先关注什么？",
                "候选人如何学习新任务、拆解目标、交付结果并复盘改进。",
                ["只问候选人是否性格外向。", "只要求背诵岗位原文。", "只看自我评价，不追问具体行为。"],
                "软能力题应围绕行为过程和证据边界。",
            ),
        ],
        "true_false": [
            ("软能力要求可以生成行为面试或证据核验题，但不应生成无关技术题。", "正确", "题型应匹配来源要求的主题。"),
            ("如果 source_requirement 是团队协作，就可以直接生成数据库高可用题。", "错误", "团队协作不是数据库能力来源。"),
        ],
        "short": [
            ("请说明如何回答沟通协作类要求，才能让面试官看到可核验行为证据。", ["说明具体场景和目标", "描述个人沟通动作", "给出结果和复盘"]),
            ("请说明如何证明学习能力，而不是空泛声称自己学习快。", ["给出学习任务", "说明方法和时间线", "展示交付物或改进结果"]),
        ],
    },
    "business_analysis": {
        "label": "business analysis",
        "choice": [
            (
                "把业务需求拆成可落地方案时，最需要先确认什么？",
                "业务目标、用户场景、输入输出、验收指标、约束条件和风险边界。",
                ["先选择最热门工具，再反推需求。", "只复述岗位原文，不定义验收标准。", "只看学历和年限条件。"],
                "业务分析题应考查需求拆解和证据边界，不套技术模板。",
            ),
        ],
        "true_false": [
            ("无法稳定识别技术域时，应降级为岗位理解、证据核验或方案拆解题。", "正确", "不应为了凑题数套用无关技术模板。"),
            ("业务需求不清楚时，最好的做法是直接生成数据库高可用题。", "错误", "题目必须来自可识别要求或降级为证据核验。"),
        ],
        "short": [
            ("请说明如何把一条宽泛岗位职责拆成可验证的面试追问。", ["识别业务目标", "定义候选人行动证据", "明确结果指标和边界"]),
        ],
    },
    "evidence_boundary": {
        "label": "evidence boundary",
        "choice": [
            (
                "当来源要求没有稳定技术能力域时，最合适的面试题方向是什么？",
                "要求候选人说明岗位理解、证据边界、学习计划或如何核验相关经历，而不是套无关技术题。",
                ["直接生成无关技术题。", "直接套用热门题库。", "把岗位条件改写成具体能力经历。"],
                "无法识别技术域时应降级为证据核验，而不是强行套模板。",
            ),
        ],
        "true_false": [
            ("来源要求没有明确技术点时，应优先核验岗位理解和证据边界。", "正确", "这能避免引入无关技术域。"),
            ("无法识别能力域时，可以为了凑满题数直接生成热门技术题。", "错误", "题目数量不能优先于相关性。"),
        ],
        "short": [
            ("请说明如何回答泛化岗位要求时避免伪造成具体技术经历。", ["给出真实场景", "说明个人行动和边界", "明确证据和后续补齐计划"]),
            ("请说明如何核验候选人对岗位要求的理解，而不引入无关技术域。", ["复述岗位目标", "拆解关键职责", "说明可验证证据"]),
        ],
    },
}

AI_DOMAINS = {"rag_retrieval", "agent_orchestration", "llm_api_prompt"}
OPS_DOMAINS = {
    "linux_ops",
    "web_server_ops",
    "database_ops",
    "middleware_ops",
    "monitoring_ops",
    "ci_cd_release",
    "it_support",
}
FORBIDDEN_DOMAIN_TERMS = {
    "ai": ["rag", "llm", "ai pipeline", "ai 模型", "agent", "prompt"],
    "ops": ["linux", "nginx", "mysql", "数据库高可用", "redis", "kafka"],
    "content": ["短视频", "新媒体", "投流", "素材", "账号"],
    "industrial_data": ["工业数据", "数据清洗", "特征工程", "aoi"],
}


def build_rule_interview_question_set(
    job_profile: dict,
    skill_requirements: list[dict],
    question_count: int = DEFAULT_RULE_QUESTION_COUNT,
) -> dict:
    sources = build_question_sources(skill_requirements)
    questions = generate_domain_questions(job_profile, sources, question_count)
    return {
        "job_profile": job_profile,
        "questions": questions,
        "markdown_preview": render_questions_markdown(job_profile, questions),
        "coverage": build_coverage(questions),
        "warnings": build_rule_warnings(skill_requirements, sources, questions, question_count),
    }


def build_question_sources(skill_requirements: list[dict]) -> list[dict]:
    sources = []
    seen = set()
    for requirement in skill_requirements:
        category = requirement.get("requirement_category") or requirement.get("category", "")
        if category in RULE_BLOCKED_CATEGORIES or requirement.get("is_questionable") is False:
            continue
        domains = list(requirement.get("domains") or [])
        if not domains:
            domains = ["soft_skill" if category == "soft_skill" else "evidence_boundary" if category == "unknown" else "business_analysis"]
        for domain in sorted(domains, key=domain_sort_key):
            if domain not in DOMAIN_SPECS:
                continue
            key = (requirement.get("requirement_id", ""), domain)
            if key in seen:
                continue
            seen.add(key)
            sources.append({"requirement": requirement, "domain": domain})
    sources.sort(key=lambda item: domain_sort_key(item["domain"]))
    return sources


def generate_domain_questions(job_profile: dict, sources: list[dict], question_count: int) -> list[dict]:
    if not sources:
        return []
    type_plan = (["single_choice"] * 4 + ["true_false"] * 2 + ["short_answer"] * 2)[:question_count]
    questions: list[dict] = []
    seen_stems: set[str] = set()
    source_index = 0
    attempts = 0
    while len(questions) < len(type_plan) and attempts < max(80, len(sources) * 10):
        question_type = type_plan[len(questions)]
        source = sources[source_index % len(sources)]
        source_index += 1
        attempts += 1
        question = build_domain_question_payload(
            len(questions) + 1,
            question_type,
            source,
            attempts + len(questions),
            job_profile,
        )
        gate = run_quality_gate(question, source, seen_stems)
        if not gate["accepted"]:
            continue
        question["quality_gate"] = gate
        questions.append(question)
        seen_stems.add(normalize_text(question.get("question", ""))[:80])
    return questions


def build_domain_question_payload(
    index: int,
    question_type: str,
    source: dict,
    variant: int,
    job_profile: dict,
) -> dict:
    requirement = source["requirement"]
    domain = source["domain"]
    spec = pick_domain_spec(domain, question_type, variant)
    source_refs = requirement.get("source_refs") or [build_source_ref(job_profile, requirement)]
    skill_label = DOMAIN_SPECS[domain]["label"]
    if question_type == "single_choice":
        answer_key = ["C", "A", "D", "B"][index % 4]
        options = place_correct_option(spec["correct"], spec["distractors"], answer_key, variant)
        correct_answer: str | list[str] = answer_key
        explanation = spec["explanation"]
        stem = spec["stem"]
    elif question_type == "true_false":
        options = [{"key": "正确", "text": "正确"}, {"key": "错误", "text": "错误"}]
        correct_answer = spec["answer"]
        explanation = spec["explanation"]
        stem = spec["stem"]
    else:
        options = []
        correct_answer = spec["points"]
        explanation = "参考答案应覆盖：" + "；".join(spec["points"])
        stem = spec["stem"]
    safety_note = "本题只用于面试准备和知识核验，不得把岗位要求直接改写成个人已经具备的经历。"
    return {
        "question_id": index,
        "question_type": question_type,
        "type": question_type,
        "stem": stem,
        "question": stem,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "difficulty": map_difficulty(requirement),
        "tested_skill": skill_label,
        "skill_area": skill_label,
        "capability_domain": domain,
        "source_requirement_id": requirement.get("requirement_id", f"REQ{index:03d}"),
        "source_requirement": requirement.get("requirement_text", ""),
        "source_refs": source_refs,
        "safety_note": safety_note,
        "risk_hint": safety_note,
        "requirement": requirement.get("requirement_text", ""),
        "intent": f"检验候选人对 {skill_label} 能力域的理解，并核对题干主题与来源要求一致。",
        "answer_checkpoints": build_domain_answer_checkpoints(question_type, domain),
        "risk_reminder": safety_note,
    }


def pick_domain_spec(domain: str, question_type: str, variant: int) -> dict:
    specs = DOMAIN_SPECS[domain]
    if question_type == "single_choice":
        raw = specs["choice"][variant % len(specs["choice"])]
        return {"stem": raw[0], "correct": raw[1], "distractors": raw[2], "explanation": raw[3]}
    if question_type == "true_false":
        raw = specs["true_false"][variant % len(specs["true_false"])]
        return {"stem": raw[0], "answer": raw[1], "explanation": raw[2]}
    raw = specs["short"][variant % len(specs["short"])]
    return {"stem": raw[0], "points": raw[1]}


def run_quality_gate(question: dict, source: dict, seen_stems: set[str]) -> dict:
    requirement = source["requirement"]
    domain = source["domain"]
    source_domains = set(requirement.get("domains") or [])
    source_category = requirement.get("requirement_category") or requirement.get("category", "")
    stem = question.get("question") or question.get("stem", "")
    full_text = build_question_text_for_gate(question)
    checks = {
        "source_not_filter": source_category not in RULE_BLOCKED_CATEGORIES,
        "domain_matches_source": domain in source_domains or domain in {"evidence_boundary", "business_analysis", "soft_skill"},
        "not_duplicate": normalize_text(stem)[:80] not in seen_stems,
        "not_irrelevant_template": not has_irrelevant_domain_terms(full_text, source_domains, domain),
        "short_answer_has_points": question.get("type") != "short_answer" or len(question.get("correct_answer") or []) >= 3,
    }
    accepted = all(checks.values())
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "accepted": accepted,
        "reason": "" if accepted else "quality gate failed: " + ", ".join(failed),
        "checks": checks,
    }


def has_irrelevant_domain_terms(stem: str, source_domains: set[str], domain: str) -> bool:
    text = stem.lower()
    if not source_domains and domain in {"evidence_boundary", "business_analysis"}:
        return False
    if not source_domains.intersection(AI_DOMAINS) and contains_forbidden(text, FORBIDDEN_DOMAIN_TERMS["ai"]):
        return True
    if not source_domains.intersection(OPS_DOMAINS) and contains_forbidden(text, FORBIDDEN_DOMAIN_TERMS["ops"]):
        return True
    if "content_ops" not in source_domains and contains_forbidden(text, FORBIDDEN_DOMAIN_TERMS["content"]):
        return True
    if "business_analysis" not in source_domains and contains_forbidden(text, FORBIDDEN_DOMAIN_TERMS["industrial_data"]):
        return True
    return False


def build_domain_answer_checkpoints(question_type: str, domain: str) -> list[str]:
    label = DOMAIN_SPECS[domain]["label"]
    if question_type == "short_answer":
        return [
            f"是否围绕 {label} 回答，而不是切换到无关技术域。",
            "是否包含步骤、指标或验证方法。",
            "是否说明风险、边界或 fallback。",
        ]
    return [
        f"是否理解 {label} 的核心概念。",
        "是否能区分正确流程和常见误区。",
        "是否能把答案和来源岗位要求对应起来。",
    ]


def build_rule_warnings(
    skill_requirements: list[dict],
    sources: list[dict],
    questions: list[dict],
    question_count: int,
) -> list[str]:
    warnings: list[str] = []
    blocked_count = sum(
        1
        for item in skill_requirements
        if (item.get("requirement_category") or item.get("category", "")) in RULE_BLOCKED_CATEGORIES
    )
    if blocked_count:
        warnings.append(f"已过滤 {blocked_count} 条学历、年限、薪资、福利或条件类要求，未将其作为技术题来源。")
    if not sources:
        warnings.append("目标岗位资料中没有稳定可出题的能力域，未套用无关技术模板。")
    if len(questions) < question_count:
        warnings.append(f"质量闸门后仅生成 {len(questions)} 道题；为避免无关题，未强行凑满 {question_count} 道。")
    return warnings


def build_source_ref(job_profile: dict, requirement: dict) -> dict[str, str]:
    return {
        "type": "job_description",
        "source_id": job_profile.get("job_id", ""),
        "relative_path": job_profile.get("source_file", ""),
        "section": "岗位要求",
        "quote": requirement.get("requirement_text", ""),
    }


def build_coverage(questions: list[dict]) -> dict:
    skills = []
    requirement_ids = []
    type_summary = {"single_choice": 0, "true_false": 0, "short_answer": 0}
    for question in questions:
        skill = question.get("skill_area", "")
        requirement_id = question.get("source_requirement_id", "")
        if skill and skill not in skills:
            skills.append(skill)
        if requirement_id and requirement_id not in requirement_ids:
            requirement_ids.append(requirement_id)
        question_type = question.get("question_type") or question.get("type")
        if question_type in type_summary:
            type_summary[question_type] += 1
    return {
        "skill_count": len(skills),
        "requirement_count": len(requirement_ids),
        "skills": skills,
        "requirement_ids": requirement_ids,
        "type_summary": type_summary,
    }


def render_questions_markdown(job_profile: dict, questions: list[dict]) -> str:
    lines = [
        f"# 面试题预览：{job_profile.get('title') or '目标岗位'}",
        "",
        f"- 来源岗位 ID：{job_profile.get('job_id') or ''}",
        f"- 来源文件：{job_profile.get('source_file') or ''}",
        "",
        "## 题目",
    ]
    for question in questions:
        lines.extend(render_question_markdown(question))
    return "\n".join(lines)


def render_question_markdown(question: dict) -> list[str]:
    lines = ["", f"### Q{question.get('question_id')} {question.get('question_type')}", "", question.get("question", "")]
    if question.get("options"):
        lines.append("")
        lines.append("选项：")
        lines.extend(f"- {option.get('key')}. {option.get('text')}" for option in question["options"])
    answer = question.get("correct_answer", "")
    if isinstance(answer, list):
        answer = "；".join(str(item) for item in answer)
    lines.extend(
        [
            "",
            f"- 正确答案：{answer}",
            f"- 解析：{question.get('explanation', '')}",
            f"- 测试能力：{question.get('skill_area', '')}",
            f"- 来源岗位要求：{question.get('source_requirement', '')}",
        ]
    )
    return lines


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


def map_difficulty(requirement: dict) -> str:
    value = requirement.get("difficulty_hint", "")
    if value == "advanced":
        return "进阶"
    if value == "intermediate":
        return "综合"
    return "基础"


def domain_sort_key(domain: str) -> int:
    try:
        return DOMAIN_PRIORITY.index(domain)
    except ValueError:
        return len(DOMAIN_PRIORITY)


def normalize_text(text: str) -> str:
    return "".join(str(text or "").lower().split())


def contains_forbidden(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def build_question_text_for_gate(question: dict) -> str:
    parts = [
        question.get("question", ""),
        question.get("stem", ""),
        question.get("explanation", ""),
        str(question.get("correct_answer", "")),
    ]
    for option in question.get("options") or []:
        parts.append(option.get("text", ""))
    return " ".join(str(part) for part in parts).lower()
