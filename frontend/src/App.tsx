import {
  BriefcaseBusiness,
  CheckCircle2,
  Database,
  Download,
  FileSearch,
  FileText,
  Library,
  Loader2,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  Trash2,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  API_BASE_URL,
  AskResponse,
  CategoryKey,
  ChatArtifact,
  ChatMessage,
  DocumentInfo,
  IndexResponse,
  askQuestionStream,
  buildIndex,
  buildJobAgentSummary,
  buildJobInterviewFeedback,
  buildJobInterviewSession,
  buildJobMatchDraft,
  compareResumeRevisionWithCurrent,
  createJobMatchReportBatchQueue,
  createResumeWriteReviewItem,
  deleteJobMatchReportBatchQueue,
  deleteDocument,
  deleteJobMatchDraftExport,
  deleteJobMatchReportExport,
  deleteResumeRevisionDraftExport,
  deleteResumeWriteReviewItem,
  exportJobMatchDraft,
  exportJobMatchReport,
  exportResumeRevisionDraft,
  getProductionWorkbenchStatus,
  getCurrentResume,
  JobInterviewFeedbackResponse,
  JobInterviewSessionResponse,
  JobAgentSummaryResponse,
  InterviewQuestion,
  JobMatchDraftExportFile,
  JobMatchDraftExportContentResponse,
  JobMatchReportBatchQueueContentResponse,
  JobMatchReportBatchQueueFile,
  JobMatchReportExportFile,
  JobMatchReportExportContentResponse,
  JobMatchDraftResponse,
  ProductionWorkbenchStatus,
  listJobMatchDraftExports,
  listJobMatchReportBatchQueues,
  listJobMatchReportExports,
  listResumeRevisionDraftExports,
  listResumeWriteReviewItems,
  listDocuments,
  readJobMatchDraftExport,
  readJobMatchReportBatchQueue,
  readJobMatchReportExport,
  readResumeRevisionDraftExport,
  readResumeWriteReviewItem,
  readDocument,
  ResumeRevisionCompareResponse,
  ResumeRevisionDraftExportFile,
  ResumeRevisionDraftExportContentResponse,
  ResumeWriteReviewQueueContentResponse,
  ResumeWriteReviewQueueFile,
  setCurrentResume,
  updateDocument,
  updateJobMatchReportBatchReview,
  updateJobMatchReportReview,
  updateResumeWriteReviewItem,
  uploadDocument,
} from "./api";
import { VercelV0Chat } from "./components/ui/v0-ai-chat";

type PageKey = "ask" | "agent" | "resumes" | "library" | "index";
type AgentTabKey = "overview" | "copies" | "interview";
type AgentLaunch = {
  token: number;
  tab: AgentTabKey;
  query: string;
  artifactType: ChatArtifact["type"];
  fileName: string;
  artifact?: ChatArtifact;
};

type NavItem = {
  key: PageKey;
  label: string;
  description: string;
  icon: LucideIcon;
};

function formatRequestError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : "";
  if (
    message === "Failed to fetch" ||
    message.includes("Failed to fetch") ||
    message.includes("NetworkError") ||
    message.includes("Load failed")
  ) {
    return `无法连接后端服务（${API_BASE_URL}）。请确认 local-rag-assistant 后端已启动后再重试。`;
  }
  return message || fallback;
}

type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: AskResponse;
};

const navItems: NavItem[] = [
  { key: "ask", label: "问答分析", description: "简历与岗位匹配", icon: FileSearch },
  { key: "agent", label: "求职 Agent", description: "草稿与面试准备", icon: BriefcaseBusiness },
  { key: "resumes", label: "简历中心", description: "当前简历管理", icon: FileText },
  { key: "library", label: "资料库", description: "行业、岗位与项目", icon: Database },
  { key: "index", label: "索引状态", description: "更新向量索引", icon: RefreshCw },
];

const reportReviewOptions = [
  { value: "pending_review", label: "待审核" },
  { value: "accepted", label: "已采纳" },
  { value: "rejected", label: "已拒绝" },
  { value: "needs_evidence", label: "需补证据" },
];

const resumeWriteReviewOptions = [
  { value: "pending_review", label: "待审核" },
  { value: "approved_for_manual_copy", label: "人工采纳候选" },
  { value: "rejected", label: "已拒绝" },
  { value: "needs_evidence", label: "需补证据" },
];

const categoryMeta: Record<CategoryKey, { title: string; description: string; uploadText: string }> = {
  resumes: {
    title: "简历库",
    description: "简历文件",
    uploadText: "上传简历",
  },
  industries: {
    title: "行业资料",
    description: "行业知识",
    uploadText: "上传行业资料",
  },
  jobs: {
    title: "岗位资料",
    description: "岗位 JD",
    uploadText: "上传岗位资料",
  },
  projects: {
    title: "项目资料",
    description: "项目说明",
    uploadText: "上传项目资料",
  },
};

const libraryCategories: CategoryKey[] = ["industries", "jobs", "projects"];

function App() {
  const [activePage, setActivePage] = useState<PageKey>("ask");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [indexResult, setIndexResult] = useState<IndexResponse | null>(() => loadIndexResult());
  const [agentLaunch, setAgentLaunch] = useState<AgentLaunch | null>(null);

  function openAgentFromArtifact(artifact: ChatArtifact) {
    setAgentLaunch({
      token: Date.now(),
      tab: getArtifactTargetTab(artifact.type),
      query: artifact.query,
      artifactType: artifact.type,
      fileName: artifact.file_name,
      artifact,
    });
    setActivePage("agent");
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-main">
            <div className="brand-mark">
              <Library size={21} />
            </div>
            <div className="brand-copy">
              <div className="brand-title">Local RAG</div>
              <div className="brand-subtitle">求职资料工作台</div>
            </div>
          </div>
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setSidebarCollapsed((current) => !current)}
            aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={`nav-item ${activePage === item.key ? "active" : ""}`}
                onClick={() => setActivePage(item.key)}
                title={item.label}
              >
                <Icon size={18} />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="workspace">
        {activePage === "ask" && <AskPage onOpenAgent={openAgentFromArtifact} />}
        {activePage === "agent" && <JobAgentPage launch={agentLaunch} />}
        {activePage === "resumes" && <DocumentPage category="resumes" />}
        {activePage === "library" && <KnowledgeBasePage />}
        {activePage === "index" && <IndexPage result={indexResult} setResult={setIndexResult} />}
      </main>
    </div>
  );
}

function AskPage({ onOpenAgent }: { onOpenAgent: (artifact: ChatArtifact) => void }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>(() => loadAskMessages());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<ChatArtifact | null>(() => loadAskSelectedArtifact());
  const [showCitations, setShowCitations] = useState(false);
  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const [selectedCitationResponse, setSelectedCitationResponse] = useState<AskResponse | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const latestAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");
  const latestResponse = latestAssistantMessage?.response;
  const activeCitationResponse = selectedCitationResponse ?? latestResponse;
  const isEmptyConversation = messages.length === 0 && !error;
  const showSidePanel = Boolean(sidePanelOpen && (selectedArtifact || activeCitationResponse));

  function clearConversation() {
    activeRequestIdRef.current = null;
    setLoading(false);
    setMessages([]);
    setError("");
    setSelectedArtifact(null);
    setSelectedCitationResponse(null);
    setSidePanelOpen(false);
    clearAskConversationStorage();
  }

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    saveAskMessages(messages);
  }, [messages]);

  useEffect(() => {
    saveAskSelectedArtifact(selectedArtifact);
  }, [selectedArtifact]);

  async function submitQuestion(nextQuestion?: string) {
    if (loading) return;
    const trimmedQuestion = (nextQuestion ?? question).trim();
    if (!trimmedQuestion) {
      setError("请输入问题。");
      return;
    }

    setLoading(true);
    setError("");
    setSelectedArtifact(null);
    setSelectedCitationResponse(null);
    setShowCitations(false);
    setSidePanelOpen(false);
    const requestId = createRequestId();
    activeRequestIdRef.current = requestId;
    const userMessage: ConversationMessage = {
      id: createMessageId(),
      role: "user",
      content: trimmedQuestion,
    };
    const history: ChatMessage[] = messages
      .map((message) => ({ role: message.role, content: message.content }))
      .slice(-8);
    const assistantMessageId = createMessageId();
    const assistantMessage: ConversationMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      response: createEmptyAskResponse(),
    };
    setMessages((currentMessages) => [...currentMessages, userMessage, assistantMessage]);
    if (!nextQuestion) {
      setQuestion("");
    } else {
      setQuestion("");
    }
    try {
      const finalResponse = await askQuestionStream(trimmedQuestion, history, {
        onMeta: (meta) => {
          if (activeRequestIdRef.current !== requestId) return;
          setMessages((currentMessages) =>
            currentMessages.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    response: {
                      answer: message.content,
                      truncated: false,
                      sources: meta.sources,
                      retrieval_seconds: meta.retrieval_seconds,
                      generation_seconds: 0,
                      mode: meta.mode,
                      artifacts: [],
                    },
                  }
                : message
            )
          );
        },
        onDelta: (text) => {
          if (activeRequestIdRef.current !== requestId) return;
          setMessages((currentMessages) =>
            currentMessages.map((message) =>
              message.id === assistantMessageId ? appendAssistantDelta(message, text) : message
            )
          );
        },
        onDone: (nextResponse) => {
          if (activeRequestIdRef.current !== requestId) return;
          if (nextResponse.artifacts[0]) {
            setSelectedArtifact(nextResponse.artifacts[0]);
            setSelectedCitationResponse(null);
            setShowCitations(false);
            setSidePanelOpen(true);
          }
          setMessages((currentMessages) =>
            currentMessages.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    content: nextResponse.answer,
                    response: nextResponse,
                  }
                : message
            )
          );
        },
      }, { requestId });
      if (activeRequestIdRef.current !== requestId) return;
      if (finalResponse.artifacts[0]) {
        setSelectedArtifact(finalResponse.artifacts[0]);
        setSelectedCitationResponse(null);
        setShowCitations(false);
        setSidePanelOpen(true);
      }
      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: finalResponse.answer,
                response: finalResponse,
              }
            : message
        )
      );
    } catch (requestError) {
      if (activeRequestIdRef.current !== requestId) return;
      const errorMessage = formatRequestError(requestError, "生成回答失败。");
      setError(errorMessage);
      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: errorMessage,
                response: {
                  ...createEmptyAskResponse(),
                  answer: errorMessage,
                },
              }
            : message
        )
      );
    } finally {
      if (activeRequestIdRef.current === requestId) {
        activeRequestIdRef.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <section className={`page ask-page ${isEmptyConversation ? "empty-ask-page" : ""}`}>
      <div className={`ai-layout ${showSidePanel ? "with-side-panel" : "without-side-panel"} ${isEmptyConversation ? "empty-layout" : ""}`}>
        <div className={`chat-column ${isEmptyConversation ? "empty-chat-column" : ""}`}>
          {isEmptyConversation ? (
            <div className="empty-chat-center">
              <VercelV0Chat
                value={question}
                onValueChange={setQuestion}
                onSubmit={() => submitQuestion()}
                disabled={loading}
                loading={loading}
                title="问我关于简历、岗位或项目的问题"
              />
            </div>
          ) : (
          <>
          <section className="chat-surface">
            {error && <div className="error-box">{error}</div>}
            {messages.length > 0 && (
              <div className="message-list">
                {messages.map((message) => (
                  <article className={`chat-message ${message.role}`} key={message.id}>
                    <div className="message-role">{message.role === "user" ? "你" : "助手"}</div>
                    <div className="message-bubble">
                      {message.role === "assistant" ? (
                        message.content ? (
                          <ReactMarkdown>{cleanAnswer(message.content)}</ReactMarkdown>
                        ) : loading && message.id === messages[messages.length - 1]?.id ? (
                          <div className="pending-message">
                            <Loader2 className="spin" size={17} />
                            正在生成回答...
                          </div>
                        ) : null
                      ) : (
                        <p>{message.content}</p>
                      )}
                      {message.response?.truncated && (
                        <div className="warning-box compact-alert">回答可能不完整。可以缩小问题范围后重试。</div>
                      )}
                      {message.role === "assistant" && message.content && message.response && (
                        <div className="message-bubble-meta">
                          {message.response.mode === "rag" && message.response.sources.length > 0 && (
                            <button
                              className="message-bubble-meta-button"
                              type="button"
                              onClick={() => {
                                setSelectedArtifact(null);
                                setSelectedCitationResponse(message.response ?? null);
                                setShowCitations(true);
                                setSidePanelOpen(true);
                              }}
                            >
                              显示引用
                            </button>
                          )}
                          <span>{formatMode(message.response.mode)}</span>
                          <span>检索 {message.response.retrieval_seconds.toFixed(1)}s</span>
                          <span>生成 {message.response.generation_seconds.toFixed(1)}s</span>
                        </div>
                      )}
                    </div>
                    {message.role === "assistant" && Boolean(message.response?.artifacts.length) && (
                      <div className="chat-artifact-stack">
                        {message.response?.artifacts.map((artifact) => (
                          <ChatArtifactCard
                            artifact={artifact}
                            key={artifact.artifact_id}
                            selected={selectedArtifact?.artifact_id === artifact.artifact_id}
                            onSelect={() => {
                              setSelectedArtifact(artifact);
                              setSelectedCitationResponse(null);
                              setShowCitations(false);
                              setSidePanelOpen(true);
                            }}
                            onOpenAgent={onOpenAgent}
                          />
                        ))}
                      </div>
                    )}
                  </article>
                ))}
                {loading && messages[messages.length - 1]?.role !== "assistant" && (
                  <article className="chat-message assistant">
                    <div className="message-role">助手</div>
                    <div className="message-bubble pending-message">
                      <Loader2 className="spin" size={17} />
                      正在生成回答...
                    </div>
                  </article>
                )}
                <div ref={messageEndRef} />
              </div>
            )}
          </section>

          <VercelV0Chat
            value={question}
            onValueChange={setQuestion}
            onSubmit={() => submitQuestion()}
            disabled={loading}
            loading={loading}
            title=""
            toolbarLeft={
              messages.length > 0 ? (
                <button className="v0-chat-clear" type="button" onClick={clearConversation}>
                  清空对话
                </button>
              ) : null
            }
          />
          </>
          )}
        </div>

        {showSidePanel && (
        <aside className={`citation-rail ask-side-panel ${selectedArtifact && !showCitations ? "showing-artifact" : ""}`}>
          <div className="rail-title-row">
            <div className="rail-title">{selectedArtifact && !showCitations ? "结果预览" : "引用"}</div>
            <div className="rail-title-actions">
              <button
                className="secondary-button small-button"
                type="button"
                onClick={() => setSidePanelOpen(false)}
              >
                隐藏
              </button>
            </div>
          </div>
          {selectedArtifact && !showCitations && (
            <ChatArtifactPreview artifact={selectedArtifact} onOpenAgent={onOpenAgent} />
          )}
          <div className="citation-content">
          {!activeCitationResponse?.sources.length && <div className="empty-state compact">暂无引用</div>}
          <div className="source-list">
            {activeCitationResponse?.sources.map((source, index) => (
              <div className="source-card" key={`${source.source_file}-${source.title}-${index}`}>
                <strong title={source.title}>{source.title}</strong>
                <span title={source.source_file}>{source.source_file}</span>
                {source.score !== null && <small>score {source.score.toFixed(4)}</small>}
              </div>
            ))}
          </div>
          </div>
        </aside>
        )}
      </div>
    </section>
  );
}

function ChatArtifactCard({
  artifact,
  selected,
  onSelect,
  onOpenAgent,
}: {
  artifact: ChatArtifact;
  selected: boolean;
  onSelect: () => void;
  onOpenAgent: (artifact: ChatArtifact) => void;
}) {
  const highlights = getArtifactHighlights(artifact).slice(0, 4);
  const metricEntries = getArtifactMetricEntries(artifact).slice(0, 4);
  const cardDescription = getArtifactCardDescription(artifact);

  function handleAction(action: ChatArtifact["actions"][number]) {
    if (action.kind === "download_markdown") {
      downloadChatArtifact(artifact);
      return;
    }
    if (action.kind === "open_job_agent") {
      onOpenAgent(artifact);
    }
  }

  return (
    <section
      className={`chat-artifact-card ${artifact.type} ${selected ? "selected" : ""}`}
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="artifact-card-header">
        <div>
          <div className="artifact-type-label">{formatArtifactType(artifact.type)}</div>
          {cardDescription && <p>{cardDescription}</p>}
        </div>
        {artifact.file_name && (
          <span className="artifact-file-name" title={artifact.file_name}>
            {artifact.file_name}
          </span>
        )}
      </div>
      {metricEntries.length > 0 && (
        <div className="artifact-metric-row">
          {metricEntries.map(([key, value]) => (
            <span className="artifact-metric-chip" key={key}>
              {formatArtifactMetricLabel(key)}：{formatArtifactMetricValue(key, value)}
            </span>
          ))}
        </div>
      )}
      {artifact.resume_evidence_status_label && (
        <div className="artifact-evidence-status">
          <ShieldCheck size={15} />
          <span>{artifact.resume_evidence_status_label}</span>
        </div>
      )}
      {highlights.length > 0 && (
        <ul className="artifact-highlight-list">
          {highlights.map((highlight) => (
            <li key={highlight}>{highlight}</li>
          ))}
        </ul>
      )}
      {artifact.fallback_detail && (
        <div className="artifact-diagnostic">
          <strong>LLM 诊断</strong>
          <span>{artifact.fallback_detail}</span>
          {Boolean(artifact.validation_errors?.length) && <small>{artifact.validation_errors?.slice(0, 2).join("；")}</small>}
        </div>
      )}
      <div className="artifact-actions">
        {artifact.actions.map((action) => (
          <button
            className={action.kind === "open_job_agent" ? "primary-button small-button" : "secondary-button small-button"}
            key={`${artifact.artifact_id}-${action.kind}`}
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              handleAction(action);
            }}
          >
            {action.kind === "download_markdown" ? <Download size={15} /> : <BriefcaseBusiness size={15} />}
            {formatArtifactActionLabel(action, artifact.type)}
          </button>
        ))}
      </div>
    </section>
  );
}

function ChatArtifactPreview({
  artifact,
  onOpenAgent,
}: {
  artifact: ChatArtifact;
  onOpenAgent: (artifact: ChatArtifact) => void;
}) {
  const previewMarkdown = getArtifactPreviewMarkdown(artifact);
  return (
    <div className="artifact-detail-panel artifact-detail-panel-body-only">
      <div className="artifact-detail-content">
        <ReactMarkdown>{previewMarkdown}</ReactMarkdown>
      </div>
      <div className="artifact-actions">
        <button className="secondary-button small-button" type="button" onClick={() => downloadChatArtifact(artifact)}>
          <Download size={15} />
          下载 Markdown
        </button>
        <button className="primary-button small-button" type="button" onClick={() => onOpenAgent(artifact)}>
          <BriefcaseBusiness size={15} />
          {formatArtifactOpenActionLabel(artifact.type)}
        </button>
      </div>
    </div>
  );
}

function getArtifactPreviewMarkdown(artifact: ChatArtifact) {
  const markdown = artifact.content_markdown || artifact.content_preview || "暂无预览内容。";
  const userFacingMarkdown = removeMarkdownSections(markdown, [
    "## source_refs",
    "## 原始 warnings",
    "## 原简历备份证据",
  ]);
  if (artifact.type === "interview_session") {
    return stripMarkdownSections(userFacingMarkdown, ["## 回答边界", "## 来源与安全边界"]);
  }
  return stripMarkdownSections(userFacingMarkdown, ["## 来源与安全边界"]);
}

function stripMarkdownSections(markdown: string, headings: string[]) {
  let result = markdown;
  for (const heading of headings) {
    const index = result.indexOf(heading);
    if (index >= 0) result = result.slice(0, index).trim();
  }
  return result || markdown;
}

function removeMarkdownSections(markdown: string, headings: string[]) {
  let result = markdown;
  for (const heading of headings) {
    const escapedHeading = escapeRegExp(heading);
    const sectionPattern = new RegExp(`\\n?${escapedHeading}\\n[\\s\\S]*?(?=\\n##\\s|$)`, "g");
    result = result.replace(sectionPattern, "");
  }
  return result.trim() || markdown;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function getUserFacingDraftMarkdown(markdown: string) {
  return removeMarkdownSections(markdown, ["## source_refs", "## 原始 warnings", "## 原简历备份证据"]);
}

function getArtifactHighlights(artifact: ChatArtifact) {
  if (artifact.highlights?.length) return artifact.highlights.filter(Boolean);
  const preview = artifact.content_preview || "";
  return preview
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-#*\s]+/, "").trim())
    .filter(Boolean)
    .slice(0, 3);
}

function getArtifactCardDescription(artifact: ChatArtifact) {
  const description = artifact.description.trim();
  if (/^已生成\s*\d+\s*道题，包含选择题、判断题和简答题。?$/.test(description)) {
    return "";
  }
  return description;
}

function getArtifactMetricEntries(artifact: ChatArtifact): Array<[string, string | number | boolean]> {
  return Object.entries(artifact.metrics ?? {}).filter(([, value]) => value !== "" && value !== undefined && value !== null);
}

function formatArtifactMetricLabel(key: string) {
  const labels: Record<string, string> = {
    can_write: "可写入",
    requires_evidence: "需补证据",
    interview_only: "面试准备",
    cannot_claim: "不能声称",
    question_count: "题目",
    generation_mode: "生成模式",
    cache_hit: "缓存",
    single_choice: "选择题",
    multiple_choice: "多选题",
    true_false: "判断题",
    short_answer: "简答题",
    matched_jobs: "岗位",
    report_count: "报告",
  };
  return labels[key] ?? key;
}

function formatArtifactMetricValue(key: string, value: string | number | boolean) {
  if (key === "cache_hit" && typeof value === "boolean") {
    return value ? "命中" : "未命中";
  }
  return String(value);
}

function downloadChatArtifact(artifact: ChatArtifact) {
  const fileName = artifact.file_name || `${artifact.type}-${artifact.artifact_id}.md`;
  const blob = new Blob([artifact.content_markdown || artifact.content_preview || ""], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName.endsWith(".md") ? fileName : `${fileName}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function formatArtifactType(type: ChatArtifact["type"]) {
  switch (type) {
    case "job_summary":
      return "岗位汇总";
    case "job_match_report":
      return "匹配报告";
    case "resume_revision_draft":
      return "简历草稿";
    case "interview_session":
      return "面试模拟";
    default:
      return "求职卡片";
  }
}

function getArtifactTargetTab(type: ChatArtifact["type"]): AgentTabKey {
  if (type === "interview_session") return "interview";
  if (type === "job_summary") return "overview";
  return "copies";
}

function formatArtifactOpenActionLabel(type: ChatArtifact["type"]) {
  if (type === "interview_session") return "进入面试模拟";
  if (type === "job_match_report" || type === "resume_revision_draft") return "进入审核";
  return "进入求职 Agent";
}

function formatArtifactActionLabel(action: ChatArtifact["actions"][number], type: ChatArtifact["type"]) {
  if (action.kind === "download_markdown") return "下载 Markdown";
  if (action.kind === "open_job_agent") return formatArtifactOpenActionLabel(type);
  return action.label;
}

function JobAgentPage({ launch }: { launch: AgentLaunch | null }) {
  const [query, setQuery] = useState("");
  const [batchQueries, setBatchQueries] = useState("");
  const [note, setNote] = useState("");
  const [summary, setSummary] = useState<JobAgentSummaryResponse | null>(null);
  const [draft, setDraft] = useState<JobMatchDraftResponse | null>(null);
  const [interviewSession, setInterviewSession] = useState<JobInterviewSessionResponse | null>(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState<number | null>(null);
  const [interviewAnswer, setInterviewAnswer] = useState("");
  const [interviewFeedback, setInterviewFeedback] = useState<JobInterviewFeedbackResponse | null>(null);
  const [draftFiles, setDraftFiles] = useState<JobMatchDraftExportFile[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<JobMatchDraftExportContentResponse | null>(null);
  const [resumeDiffFiles, setResumeDiffFiles] = useState<ResumeRevisionDraftExportFile[]>([]);
  const [selectedResumeDiff, setSelectedResumeDiff] = useState<ResumeRevisionDraftExportContentResponse | null>(null);
  const [resumeDiffCompare, setResumeDiffCompare] = useState<ResumeRevisionCompareResponse | null>(null);
  const [resumeWriteReviewFiles, setResumeWriteReviewFiles] = useState<ResumeWriteReviewQueueFile[]>([]);
  const [selectedResumeWriteReview, setSelectedResumeWriteReview] = useState<ResumeWriteReviewQueueContentResponse | null>(null);
  const [resumeWriteReviewStatus, setResumeWriteReviewStatus] = useState("pending_review");
  const [resumeWriteReviewNote, setResumeWriteReviewNote] = useState("");
  const [reportFiles, setReportFiles] = useState<JobMatchReportExportFile[]>([]);
  const [selectedReport, setSelectedReport] = useState<JobMatchReportExportContentResponse | null>(null);
  const [reportReviewStatus, setReportReviewStatus] = useState("pending_review");
  const [reportReviewNote, setReportReviewNote] = useState("");
  const [batchReportFiles, setBatchReportFiles] = useState<JobMatchReportBatchQueueFile[]>([]);
  const [selectedBatchReport, setSelectedBatchReport] = useState<JobMatchReportBatchQueueContentResponse | null>(null);
  const [batchReportReviewStatus, setBatchReportReviewStatus] = useState("pending_review");
  const [batchReportReviewNote, setBatchReportReviewNote] = useState("");
  const [loadingAction, setLoadingAction] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [activeAgentTab, setActiveAgentTab] = useState<AgentTabKey>("overview");

  useEffect(() => {
    refreshDraftExports();
    refreshResumeDiffExports();
    refreshResumeWriteReviewItems();
    refreshReportExports();
    refreshBatchReportQueues();
  }, []);

  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(""), 2800);
    return () => window.clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    if (!launch) return;
    let cancelled = false;
    if (launch.query) {
      setQuery(launch.query);
    }

    async function openLaunchTarget() {
      if (!launch) return;
      setActiveAgentTab(launch.tab);

      if (launch.artifactType === "job_match_report" && launch.fileName) {
        await handleReadReport(launch.fileName);
      } else if (launch.artifactType === "resume_revision_draft" && launch.fileName) {
        await handleReadResumeDiff(launch.fileName);
      } else if (launch.artifactType === "interview_session" && launch.query) {
        const embeddedSession = launch.artifact?.session_payload;
        if (embeddedSession) {
          setInterviewSession(embeddedSession);
          setInterviewFeedback(null);
          setInterviewAnswer("");
          setSelectedQuestionId(embeddedSession.session?.questions[0]?.question_id ?? null);
          setActiveAgentTab("interview");
        } else {
          const data = await runAction("interview", () => buildJobInterviewSession(launch.query));
          if (!cancelled && data) {
            setInterviewSession(data);
            setInterviewFeedback(null);
            setInterviewAnswer("");
            setSelectedQuestionId(data.session?.questions[0]?.question_id ?? null);
            setActiveAgentTab("interview");
          }
        }
      } else if (launch.artifactType === "job_summary") {
        setActiveAgentTab("overview");
      }

      if (!cancelled) {
        setMessage("已从问答分析打开对应结果。");
      }
    }

    openLaunchTarget();
    return () => {
      cancelled = true;
    };
  }, [launch]);

  async function runAction<T>(action: string, handler: () => Promise<T>) {
    setLoadingAction(action);
    setError("");
    setMessage("");
    try {
      return await handler();
    } catch (requestError) {
      setError(formatRequestError(requestError, "操作失败。"));
      return null;
    } finally {
      setLoadingAction("");
    }
  }

  async function handleBuildSummary() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("summary", () => buildJobAgentSummary(trimmed));
    if (!data) return;
    setSummary(data);
    setInterviewFeedback(null);
    if (!data.matched) {
      setDraft(null);
      setInterviewSession(null);
      setSelectedQuestionId(null);
      setError("没有定位到目标岗位。");
      return;
    }
    setActiveAgentTab("overview");
    setMessage("已定位目标岗位。");
  }

  async function handleBuildDraft() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("draft", () => buildJobMatchDraft(trimmed));
    if (!data) return;
    setDraft(data);
    if (!data.matched) {
      setError("没有生成草稿，目标岗位未命中。");
      return;
    }
    setActiveAgentTab("overview");
    setMessage("已生成可审核草稿预览。");
  }

  async function handleBuildInterviewSession() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("interview", () => buildJobInterviewSession(trimmed));
    if (!data) return;
    setInterviewSession(data);
    setInterviewFeedback(null);
    setInterviewAnswer("");
    if (!data.matched || !data.session?.questions.length) {
      setSelectedQuestionId(null);
      setError("没有生成面试问题，目标岗位未命中或岗位要求不足。");
      return;
    }
    setSelectedQuestionId(data.session.questions[0].question_id);
    setActiveAgentTab("interview");
    setMessage("已生成面试模拟问题。");
  }

  async function handleSubmitInterviewAnswer() {
    const trimmed = query.trim();
    const answer = interviewAnswer.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    if (!selectedQuestionId) {
      setError("请先选择一个面试问题。");
      return;
    }
    if (!answer) {
      setError("请输入面试回答后再提交。");
      return;
    }
    const data = await runAction("feedback", () => buildJobInterviewFeedback(trimmed, selectedQuestionId, answer));
    if (!data) return;
    setInterviewFeedback(data);
    if (!data.matched || !data.feedback) {
      setError("没有生成反馈，目标岗位未命中。");
      return;
    }
    setMessage("已生成面试回答反馈。");
  }

  async function handleExportDraft() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("export", () => exportJobMatchDraft(trimmed, note.trim()));
    if (!data || !data.exported) return;
    await refreshDraftExports(data.file_name);
    setMessage("已保存为私有草稿副本。");
  }

  async function handleExportResumeDiff() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("resume-diff-export", () => exportResumeRevisionDraft(trimmed, note.trim()));
    if (!data || !data.exported) return;
    await refreshResumeDiffExports(data.file_name);
    setMessage("已保存为私有简历差异草稿。真实简历未受影响。");
  }

  async function handleExportReport() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("请输入岗位标题、来源 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("report-export", () => exportJobMatchReport(trimmed, note.trim()));
    if (!data || !data.exported) return;
    await refreshReportExports(data.file_name);
    setMessage("已保存为私有求职分析报告。");
  }

  async function handleCreateBatchReportQueue() {
    const queries = parseBatchQueries(batchQueries);
    if (queries.length < 2) {
      setError("批量报告队列至少需要 2 个唯一岗位 ID、marker 或文件名。");
      return;
    }
    const data = await runAction("batch-report-queue", () => createJobMatchReportBatchQueue(queries, note.trim()));
    if (!data?.queued) return;
    await refreshBatchReportQueues(data.file_name);
    await refreshReportExports();
    setActiveAgentTab("copies");
    setMessage(`已生成批量报告队列：${data.created_count} 份报告，${data.failed_count} 个失败项。`);
  }

  async function refreshDraftExports(nextSelectedFileName?: string) {
    const data = await runAction("list", () => listJobMatchDraftExports());
    if (!data) return;
    setDraftFiles(data.drafts);
    if (nextSelectedFileName) {
      await handleReadDraft(nextSelectedFileName);
    } else if (selectedDraft && !data.drafts.some((item) => item.file_name === selectedDraft.file_name)) {
      setSelectedDraft(null);
    }
  }

  async function handleRefreshCopies() {
    await refreshDraftExports();
    await refreshResumeDiffExports();
    await refreshResumeWriteReviewItems();
    await refreshReportExports();
    await refreshBatchReportQueues();
    setActiveAgentTab("copies");
  }

  async function handleReadDraft(fileName: string) {
    const data = await runAction("read", () => readJobMatchDraftExport(fileName));
    if (!data) return;
    setSelectedResumeDiff(null);
    setResumeDiffCompare(null);
    setSelectedResumeWriteReview(null);
    setSelectedReport(null);
    setSelectedBatchReport(null);
    setSelectedDraft(data);
    setActiveAgentTab("copies");
  }

  async function handleDeleteDraft(fileName: string) {
    const confirmed = window.confirm(`确认删除草稿副本 ${fileName}？`);
    if (!confirmed) return;
    const data = await runAction("delete", () => deleteJobMatchDraftExport(fileName));
    if (!data?.deleted) return;
    setSelectedDraft((current) => (current?.file_name === fileName ? null : current));
    await refreshDraftExports();
    setMessage("已删除草稿副本。真实简历未受影响。");
  }

  async function refreshResumeWriteReviewItems(nextSelectedFileName?: string) {
    const data = await runAction("resume-write-list", () => listResumeWriteReviewItems());
    if (!data) return;
    setResumeWriteReviewFiles(data.items);
    if (nextSelectedFileName) {
      await handleReadResumeWriteReview(nextSelectedFileName);
    } else if (selectedResumeWriteReview && !data.items.some((item) => item.file_name === selectedResumeWriteReview.file_name)) {
      setSelectedResumeWriteReview(null);
    }
  }

  async function refreshResumeDiffExports(nextSelectedFileName?: string) {
    const data = await runAction("resume-diff-list", () => listResumeRevisionDraftExports());
    if (!data) return;
    setResumeDiffFiles(data.drafts);
    if (nextSelectedFileName) {
      await handleReadResumeDiff(nextSelectedFileName);
    } else if (selectedResumeDiff && !data.drafts.some((item) => item.file_name === selectedResumeDiff.file_name)) {
      setSelectedResumeDiff(null);
      setResumeDiffCompare(null);
    }
  }

  async function handleReadResumeDiff(fileName: string) {
    const data = await runAction("resume-diff-read", () => readResumeRevisionDraftExport(fileName));
    if (!data) return;
    setSelectedDraft(null);
    setSelectedResumeWriteReview(null);
    setSelectedReport(null);
    setSelectedBatchReport(null);
    setResumeDiffCompare(null);
    setSelectedResumeDiff(data);
    setActiveAgentTab("copies");
  }

  async function handleCompareResumeDiff() {
    if (!selectedResumeDiff) return;
    if (resumeDiffCompare?.file_name === selectedResumeDiff.file_name) {
      setResumeDiffCompare(null);
      setMessage("已还原为仅查看简历差异草稿。");
      return;
    }
    const data = await runAction("resume-diff-compare", () => compareResumeRevisionWithCurrent(selectedResumeDiff.file_name));
    if (!data) return;
    setResumeDiffCompare(data);
    setMessage("已生成当前简历与差异草稿的只读对比。");
  }

  async function handleCreateResumeWriteReview() {
    if (!selectedResumeDiff) return;
    const data = await runAction("resume-write-queue", () =>
      createResumeWriteReviewItem(selectedResumeDiff.file_name, note.trim())
    );
    if (!data?.queued) return;
    await refreshResumeWriteReviewItems(data.file_name);
    setMessage("已加入写回前审核队列。真实简历未受影响。");
  }

  async function handleDeleteResumeDiff(fileName: string) {
    const confirmed = window.confirm(`确认删除简历差异草稿 ${fileName}？`);
    if (!confirmed) return;
    const data = await runAction("resume-diff-delete", () => deleteResumeRevisionDraftExport(fileName));
    if (!data?.deleted) return;
    setSelectedResumeDiff((current) => (current?.file_name === fileName ? null : current));
    setResumeDiffCompare((current) => (current?.file_name === fileName ? null : current));
    await refreshResumeDiffExports();
    setMessage("已删除简历差异草稿。真实简历未受影响。");
  }

  async function handleReadResumeWriteReview(fileName: string) {
    const data = await runAction("resume-write-read", () => readResumeWriteReviewItem(fileName));
    if (!data) return;
    setSelectedDraft(null);
    setSelectedResumeDiff(null);
    setResumeDiffCompare(null);
    setSelectedReport(null);
    setSelectedBatchReport(null);
    setSelectedResumeWriteReview(data);
    setResumeWriteReviewStatus(data.review_status);
    setResumeWriteReviewNote(data.review_note);
    setActiveAgentTab("copies");
  }

  async function handleUpdateResumeWriteReview() {
    if (!selectedResumeWriteReview) return;
    const data = await runAction("resume-write-review", () =>
      updateResumeWriteReviewItem(selectedResumeWriteReview.file_name, resumeWriteReviewStatus, resumeWriteReviewNote)
    );
    if (!data) return;
    setSelectedResumeWriteReview(data);
    setResumeWriteReviewStatus(data.review_status);
    setResumeWriteReviewNote(data.review_note);
    await refreshResumeWriteReviewItems();
    setMessage("已更新写回前审核状态。真实简历未受影响。");
  }

  async function handleDeleteResumeWriteReview(fileName: string) {
    const confirmed = window.confirm(`确认删除写回前审核项 ${fileName}？`);
    if (!confirmed) return;
    const data = await runAction("resume-write-delete", () => deleteResumeWriteReviewItem(fileName));
    if (!data?.deleted) return;
    setSelectedResumeWriteReview((current) => (current?.file_name === fileName ? null : current));
    await refreshResumeWriteReviewItems();
    setMessage("已删除写回前审核项。真实简历未受影响。");
  }

  async function refreshReportExports(nextSelectedFileName?: string) {
    const data = await runAction("report-list", () => listJobMatchReportExports());
    if (!data) return;
    setReportFiles(data.reports);
    if (nextSelectedFileName) {
      await handleReadReport(nextSelectedFileName);
    } else if (selectedReport && !data.reports.some((item) => item.file_name === selectedReport.file_name)) {
      setSelectedReport(null);
    }
  }

  async function handleReadReport(fileName: string) {
    const data = await runAction("report-read", () => readJobMatchReportExport(fileName));
    if (!data) return;
    setSelectedDraft(null);
    setSelectedResumeDiff(null);
    setResumeDiffCompare(null);
    setSelectedResumeWriteReview(null);
    setSelectedBatchReport(null);
    setSelectedReport(data);
    setReportReviewStatus(data.review_status);
    setReportReviewNote(data.review_note);
    setActiveAgentTab("copies");
  }

  async function handleDeleteReport(fileName: string) {
    const confirmed = window.confirm(`确认删除求职分析报告 ${fileName}？`);
    if (!confirmed) return;
    const data = await runAction("report-delete", () => deleteJobMatchReportExport(fileName));
    if (!data?.deleted) return;
    setSelectedReport((current) => (current?.file_name === fileName ? null : current));
    await refreshReportExports();
    setMessage("已删除求职分析报告。真实简历未受影响。");
  }

  async function handleUpdateReportReview() {
    if (!selectedReport) return;
    const data = await runAction("report-review", () =>
      updateJobMatchReportReview(selectedReport.file_name, reportReviewStatus, reportReviewNote)
    );
    if (!data) return;
    setSelectedReport(data);
    setReportReviewStatus(data.review_status);
    setReportReviewNote(data.review_note);
    await refreshReportExports();
    setMessage("已更新报告审核状态。真实简历未受影响。");
  }

  async function refreshBatchReportQueues(nextSelectedFileName?: string) {
    const data = await runAction("batch-report-list", () => listJobMatchReportBatchQueues());
    if (!data) return;
    setBatchReportFiles(data.batches);
    if (nextSelectedFileName) {
      await handleReadBatchReport(nextSelectedFileName);
    } else if (selectedBatchReport && !data.batches.some((item) => item.file_name === selectedBatchReport.file_name)) {
      setSelectedBatchReport(null);
    }
  }

  async function handleReadBatchReport(fileName: string) {
    const data = await runAction("batch-report-read", () => readJobMatchReportBatchQueue(fileName));
    if (!data) return;
    setSelectedDraft(null);
    setSelectedResumeDiff(null);
    setResumeDiffCompare(null);
    setSelectedResumeWriteReview(null);
    setSelectedReport(null);
    setSelectedBatchReport(data);
    setBatchReportReviewStatus(data.review_status);
    setBatchReportReviewNote(data.review_note);
    setActiveAgentTab("copies");
  }

  async function handleUpdateBatchReportReview() {
    if (!selectedBatchReport) return;
    const data = await runAction("batch-report-review", () =>
      updateJobMatchReportBatchReview(selectedBatchReport.file_name, batchReportReviewStatus, batchReportReviewNote)
    );
    if (!data) return;
    setSelectedBatchReport(data);
    setBatchReportReviewStatus(data.review_status);
    setBatchReportReviewNote(data.review_note);
    await refreshBatchReportQueues();
    setMessage("已更新批量报告队列审核状态。真实简历未受影响。");
  }

  async function handleDeleteBatchReport(fileName: string) {
    const confirmed = window.confirm(`确认删除批量报告队列清单 ${fileName}？生成的单岗位报告不会被自动删除。`);
    if (!confirmed) return;
    const data = await runAction("batch-report-delete", () => deleteJobMatchReportBatchQueue(fileName));
    if (!data?.deleted) return;
    setSelectedBatchReport((current) => (current?.file_name === fileName ? null : current));
    await refreshBatchReportQueues();
    setMessage("已删除批量报告队列清单。生成的单岗位报告未被自动删除。");
  }

  function handleDownloadSelectedCopy() {
    const selectedCopy = selectedBatchReport ?? selectedReport ?? selectedResumeWriteReview ?? selectedResumeDiff ?? selectedDraft;
    if (!selectedCopy) return;
    const blob = new Blob([selectedCopy.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = selectedCopy.file_name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  const busy = Boolean(loadingAction);
  const selectedCopy = selectedBatchReport ?? selectedReport ?? selectedResumeWriteReview ?? selectedResumeDiff ?? selectedDraft;
  const copyCount =
    draftFiles.length + resumeDiffFiles.length + resumeWriteReviewFiles.length + reportFiles.length + batchReportFiles.length;
  const agentTabs = (
    <div className="agent-subtabs" role="tablist" aria-label="求职 Agent 工作区">
      <button
        type="button"
        className={`agent-subtab ${activeAgentTab === "overview" ? "active" : ""}`}
        onClick={() => setActiveAgentTab("overview")}
        role="tab"
        aria-selected={activeAgentTab === "overview"}
      >
        <BriefcaseBusiness size={17} />
        <span>总览</span>
        <small>{summary?.matched ? "已定位" : "状态与草稿"}</small>
      </button>
      <button
        type="button"
        className={`agent-subtab ${activeAgentTab === "copies" ? "active" : ""}`}
        onClick={() => setActiveAgentTab("copies")}
        role="tab"
        aria-selected={activeAgentTab === "copies"}
      >
        <FileText size={17} />
        <span>草稿审核</span>
        <small>{copyCount} 个副本</small>
      </button>
      <button
        type="button"
        className={`agent-subtab ${activeAgentTab === "interview" ? "active" : ""}`}
        onClick={() => setActiveAgentTab("interview")}
        role="tab"
        aria-selected={activeAgentTab === "interview"}
      >
        <MessageSquareText size={17} />
        <span>面试模拟</span>
        <small>{loadingAction === "interview" ? "生成中" : `${interviewSession?.session?.questions.length ?? 0} 个问题`}</small>
      </button>
    </div>
  );

  return (
    <section className="page agent-page">
      <PageHeader title="求职 Agent" description="目标岗位、可审核草稿副本与面试准备" />
      {message && (
        <div className="toast-stack" role="status" aria-live="polite">
          <div className="toast-message">
            <CheckCircle2 size={16} />
            <span>{message}</span>
          </div>
        </div>
      )}
      {error && <div className="error-box compact-alert">{error}</div>}

      {agentTabs}

      <div className={`agent-workspace agent-workspace-${activeAgentTab}`}>
        {activeAgentTab === "overview" && (
          <section className="panel agent-control-panel">
            <div className="panel-heading">
              <div>
                <h2>目标岗位</h2>
                <p>输入岗位标题、来源 ID、marker 或文件名。</p>
              </div>
            </div>
            <div className="agent-input-grid">
              <input
                className="agent-query-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="例如：1988156943977824258"
              />
              <textarea
                className="agent-note-input"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="草稿备注，可选"
              />
              <textarea
                className="agent-note-input batch-query-input"
                value={batchQueries}
                onChange={(event) => setBatchQueries(event.target.value)}
                placeholder="批量报告队列：每行一个岗位 ID、marker 或文件名，至少 2 个，最多 5 个"
              />
            </div>
            <div className="agent-action-grid">
              <button className="secondary-button" onClick={handleBuildSummary} disabled={busy || !query.trim()}>
                {loadingAction === "summary" ? <Loader2 className="spin" size={17} /> : <BriefcaseBusiness size={17} />}
                定位岗位
              </button>
              <button className="secondary-button" onClick={handleBuildDraft} disabled={busy || !query.trim()}>
                {loadingAction === "draft" ? <Loader2 className="spin" size={17} /> : <FileText size={17} />}
                生成草稿
              </button>
              <button className="primary-button" onClick={handleExportDraft} disabled={busy || !query.trim()}>
                {loadingAction === "export" ? <Loader2 className="spin" size={17} /> : <Save size={17} />}
                保存副本
              </button>
              <button className="primary-button" onClick={handleExportResumeDiff} disabled={busy || !query.trim()}>
                {loadingAction === "resume-diff-export" ? <Loader2 className="spin" size={17} /> : <FileText size={17} />}
                保存差异
              </button>
              <button className="primary-button" onClick={handleExportReport} disabled={busy || !query.trim()}>
                {loadingAction === "report-export" ? <Loader2 className="spin" size={17} /> : <FileText size={17} />}
                保存报告
              </button>
              <button
                className="secondary-button"
                onClick={handleCreateBatchReportQueue}
                disabled={busy || parseBatchQueries(batchQueries).length < 2}
              >
                {loadingAction === "batch-report-queue" ? <Loader2 className="spin" size={17} /> : <FileText size={17} />}
                批量报告
              </button>
              <button className="secondary-button" onClick={handleRefreshCopies} disabled={busy}>
                {loadingAction === "list" ||
                loadingAction === "resume-diff-list" ||
                loadingAction === "report-list" ||
                loadingAction === "batch-report-list" ? (
                  <Loader2 className="spin" size={17} />
                ) : (
                  <RefreshCw size={17} />
                )}
                刷新副本
              </button>
              <button className="secondary-button" onClick={handleBuildInterviewSession} disabled={busy || !query.trim()}>
                {loadingAction === "interview" ? <Loader2 className="spin" size={17} /> : <MessageSquareText size={17} />}
                生成面试问题
              </button>
            </div>
            <div className="agent-boundary-box">
              <ShieldCheck size={17} />
              <span>草稿只保存到私有副本目录，不覆盖真实简历，不自动投递。</span>
            </div>
          </section>
        )}

        <div className="agent-main-grid">
          <div className="agent-column agent-context-column">
            <section className="panel agent-summary-panel">
              <div className="panel-heading">
                <div>
                  <h2>Agent 状态</h2>
                  <p>{summary?.matched ? "目标岗位已定位" : "等待定位目标岗位"}</p>
                </div>
              </div>
              {!summary?.matched && <div className="empty-state">尚未生成 Agent 状态。</div>}
              {summary?.matched && summary.summary && (
                <div className="agent-status-list">
                  <div className="agent-target-card">
                    <strong>{summary.summary.target_confirmation.title}</strong>
                    <span>{summary.summary.target_confirmation.company || "公司未提供"}</span>
                    <code title={summary.summary.target_confirmation.source_file}>
                      {summary.summary.target_confirmation.source_job_id}
                    </code>
                  </div>
                  {summary.summary.pipeline_status.map((item) => (
                    <div className="agent-status-row" key={item.step}>
                      <span className={`status-dot ${item.status}`} />
                      <div>
                        <strong>{item.label}</strong>
                        <p>{item.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="panel agent-draft-panel">
              <div className="panel-heading">
                <div>
                  <h2>草稿预览</h2>
                  <p>{draft?.matched ? "候选内容按可写入、需证据、仅面试和不能声称分组" : "先生成草稿"}</p>
                </div>
              </div>
              {!draft?.matched || !draft.draft ? (
                <div className="empty-state">暂无草稿预览。</div>
              ) : (
                <div className="draft-preview-grid">
                  <DraftList title="可写入简历" items={draft.draft.resume_revision_candidates.can_write_to_resume} />
                  <DraftList
                    title="需补证据"
                    items={draft.draft.resume_revision_candidates.requires_evidence_before_resume.map(
                      (item) => `${item.candidate_direction}：${item.required_evidence}`
                    )}
                  />
                  <DraftList
                    title="仅适合面试"
                    items={draft.draft.resume_revision_candidates.interview_only.map((item) => `${item.topic}：${item.usage}`)}
                  />
                  <DraftList
                    title="不能声称"
                    items={draft.draft.resume_revision_candidates.cannot_claim.map((item) => `${item.claim}：${item.reason}`)}
                  />
                </div>
              )}
            </section>
          </div>

          <section className="panel draft-list-panel">
            <div className="panel-heading">
              <div>
                <h2>审核副本</h2>
                <p>
                  {draftFiles.length} 个草稿 · {resumeDiffFiles.length} 个差异 · {resumeWriteReviewFiles.length} 个写回审核 ·{" "}
                  {reportFiles.length} 个报告 · {batchReportFiles.length} 个批量队列
                </p>
              </div>
            </div>
          <div className="draft-file-list">
            <div className="draft-file-section">
              <div className="copy-section-heading">草稿副本</div>
              {draftFiles.length === 0 && <div className="empty-state compact">暂无草稿副本。</div>}
              {draftFiles.map((file) => (
                <div
                  className={`draft-file-row ${selectedDraft?.file_name === file.file_name ? "selected" : ""}`}
                  key={file.file_name}
                >
                  <button type="button" onClick={() => handleReadDraft(file.file_name)} title={file.file_name}>
                    <strong>{file.file_name}</strong>
                    <span>{formatSize(file.size_bytes)} · {formatDate(file.modified_at)}</span>
                  </button>
                  <button
                    className="icon-button danger"
                    onClick={() => handleDeleteDraft(file.file_name)}
                    disabled={busy}
                    title="删除草稿副本"
                    aria-label="删除草稿副本"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="draft-file-section">
              <div className="copy-section-heading">简历差异草稿</div>
              {resumeDiffFiles.length === 0 && <div className="empty-state compact">暂无简历差异草稿。</div>}
              {resumeDiffFiles.map((file) => (
                <div
                  className={`draft-file-row resume-diff-file-row ${
                    selectedResumeDiff?.file_name === file.file_name ? "selected" : ""
                  }`}
                  key={file.file_name}
                >
                  <button type="button" onClick={() => handleReadResumeDiff(file.file_name)} title={file.file_name}>
                    <strong>{file.file_name}</strong>
                    <span>{formatSize(file.size_bytes)} · {formatDate(file.modified_at)}</span>
                  </button>
                  <button
                    className="icon-button danger"
                    onClick={() => handleDeleteResumeDiff(file.file_name)}
                    disabled={busy}
                    title="删除简历差异草稿"
                    aria-label="删除简历差异草稿"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="draft-file-section">
              <div className="copy-section-heading">求职分析报告</div>
              {reportFiles.length === 0 && <div className="empty-state compact">暂无报告副本。</div>}
              {reportFiles.map((file) => (
                <div
                  className={`draft-file-row report-file-row ${
                    selectedReport?.file_name === file.file_name ? "selected" : ""
                  }`}
                  key={file.file_name}
                >
                  <button type="button" onClick={() => handleReadReport(file.file_name)} title={file.file_name}>
                    <strong>{file.file_name}</strong>
                    <span>{formatSize(file.size_bytes)} · {formatDate(file.modified_at)}</span>
                    <span className={`review-status-pill ${file.review_status}`}>{file.review_label}</span>
                  </button>
                  <button
                    className="icon-button danger"
                    onClick={() => handleDeleteReport(file.file_name)}
                    disabled={busy}
                    title="删除求职分析报告"
                    aria-label="删除求职分析报告"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="draft-file-section">
              <div className="copy-section-heading">批量报告队列</div>
              {batchReportFiles.length === 0 && <div className="empty-state compact">暂无批量报告队列。</div>}
              {batchReportFiles.map((file) => (
                <div
                  className={`draft-file-row batch-report-file-row ${
                    selectedBatchReport?.file_name === file.file_name ? "selected" : ""
                  }`}
                  key={file.file_name}
                >
                  <button type="button" onClick={() => handleReadBatchReport(file.file_name)} title={file.file_name}>
                    <strong>{file.file_name}</strong>
                    <span>
                      {file.created_count} 份报告 · {file.failed_count} 个失败 · {formatDate(file.modified_at)}
                    </span>
                    <span className={`review-status-pill ${file.review_status}`}>{file.review_label}</span>
                  </button>
                  <button
                    className="icon-button danger"
                    onClick={() => handleDeleteBatchReport(file.file_name)}
                    disabled={busy}
                    title="删除批量报告队列清单"
                    aria-label="删除批量报告队列清单"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="draft-file-section">
              <div className="copy-section-heading">写回前审核</div>
              {resumeWriteReviewFiles.length === 0 && <div className="empty-state compact">暂无写回前审核项。</div>}
              {resumeWriteReviewFiles.map((file) => (
                <div
                  className={`draft-file-row resume-write-review-file-row ${
                    selectedResumeWriteReview?.file_name === file.file_name ? "selected" : ""
                  }`}
                  key={file.file_name}
                >
                  <button type="button" onClick={() => handleReadResumeWriteReview(file.file_name)} title={file.file_name}>
                    <strong>{file.file_name}</strong>
                    <span>{formatSize(file.size_bytes)} · {formatDate(file.modified_at)}</span>
                    <span className={`review-status-pill ${file.review_status}`}>{file.review_label}</span>
                  </button>
                  <button
                    className="icon-button danger"
                    onClick={() => handleDeleteResumeWriteReview(file.file_name)}
                    disabled={busy}
                    title="删除写回前审核项"
                    aria-label="删除写回前审核项"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>
          </section>

          <div className="agent-column agent-output-column">
            <section className="panel interview-panel">
              <div className="panel-heading">
                <div>
                  <h2>面试模拟</h2>
                  <p>{interviewSession?.matched ? "选择问题，提交回答并查看反馈" : "先生成面试问题"}</p>
                </div>
                <button
                  className="secondary-button small-button"
                  type="button"
                  onClick={handleBuildInterviewSession}
                  disabled={busy || !query.trim()}
                >
                  {loadingAction === "interview" ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
                  重新生成
                </button>
              </div>
              {loadingAction === "interview" ? (
                <div className="empty-state">正在生成面试问题，请稍候。</div>
              ) : !interviewSession?.matched || !interviewSession.session ? (
                <div className="empty-state">暂无面试问题。</div>
              ) : (
                <div className="interview-workbench">
                  <div className="interview-question-list">
                    {interviewSession.session.questions.map((question) => (
                      <button
                        className={`interview-question-row ${
                          selectedQuestionId === question.question_id ? "selected" : ""
                        }`}
                        key={question.question_id}
                        type="button"
                        onClick={() => {
                          setSelectedQuestionId(question.question_id);
                          setInterviewFeedback(null);
                        }}
                      >
                        <strong>问题 {question.question_id}</strong>
                        <span>{question.question}</span>
                      </button>
                    ))}
                  </div>
                  <InterviewQuestionDetail question={getSelectedInterviewQuestion(interviewSession, selectedQuestionId)} />
                  <textarea
                    className="interview-answer-input"
                    value={interviewAnswer}
                    onChange={(event) => setInterviewAnswer(event.target.value)}
                    placeholder="输入你的面试回答，聚焦真实项目、本人动作、证据和能力边界。"
                  />
                  <button
                    className="primary-button"
                    onClick={handleSubmitInterviewAnswer}
                    disabled={busy || !selectedQuestionId || !interviewAnswer.trim()}
                  >
                    {loadingAction === "feedback" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                    提交回答
                  </button>
                  {interviewFeedback?.feedback && <InterviewFeedbackCard feedback={interviewFeedback} />}
                </div>
              )}
            </section>

            <section className="panel draft-content-panel">
          <div className="panel-heading">
            <div>
              <h2>副本内容</h2>
              {selectedCopy && <p title={selectedCopy.relative_path}>{selectedCopy.relative_path}</p>}
            </div>
            {selectedCopy && (
              <div className="panel-heading-actions">
                {selectedResumeDiff && (
                  <>
                    <button
                      className="secondary-button small-button"
                      onClick={handleCompareResumeDiff}
                      disabled={busy}
                    >
                      {loadingAction === "resume-diff-compare" ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <FileSearch size={16} />
                      )}
                      {resumeDiffCompare?.file_name === selectedResumeDiff.file_name ? "还原" : "对比当前简历"}
                    </button>
                    <button
                      className="secondary-button small-button"
                      onClick={handleCreateResumeWriteReview}
                      disabled={busy}
                    >
                      {loadingAction === "resume-write-queue" ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <ShieldCheck size={16} />
                      )}
                      加入审核
                    </button>
                  </>
                )}
                <button className="secondary-button small-button" onClick={handleDownloadSelectedCopy}>
                  <Download size={16} />
                  下载
                </button>
              </div>
            )}
          </div>
          {!selectedCopy && <div className="empty-state">从审核副本选择一个草稿或报告副本。</div>}
          {selectedCopy && (
            <div className="draft-content-scroll">
              {selectedBatchReport && (
                <div className="report-review-box batch-report-review-box">
                  <div className="report-review-controls">
                    <label>
                      批量审核状态
                      <select
                        value={batchReportReviewStatus}
                        onChange={(event) => setBatchReportReviewStatus(event.target.value)}
                        disabled={busy}
                      >
                        {reportReviewOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="secondary-button small-button"
                      onClick={handleUpdateBatchReportReview}
                      disabled={busy || !selectedBatchReport}
                    >
                      {loadingAction === "batch-report-review" ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <CheckCircle2 size={16} />
                      )}
                      更新状态
                    </button>
                  </div>
                  <textarea
                    className="report-review-note"
                    value={batchReportReviewNote}
                    onChange={(event) => setBatchReportReviewNote(event.target.value)}
                    placeholder="批量审核备注，例如：逐份报告核对证据后再采纳。"
                    disabled={busy}
                  />
                  {selectedBatchReport.review_updated_at && (
                    <p className="report-review-meta">
                      当前状态：{selectedBatchReport.review_label} · 更新于{" "}
                      {formatDate(selectedBatchReport.review_updated_at)}
                    </p>
                  )}
                </div>
              )}
              {selectedReport && (
                <div className="report-review-box">
                  <div className="report-review-controls">
                    <label>
                      审核状态
                      <select
                        value={reportReviewStatus}
                        onChange={(event) => setReportReviewStatus(event.target.value)}
                        disabled={busy}
                      >
                        {reportReviewOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="secondary-button small-button"
                      onClick={handleUpdateReportReview}
                      disabled={busy || !selectedReport}
                    >
                      {loadingAction === "report-review" ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />}
                      更新状态
                    </button>
                  </div>
                  <textarea
                    className="report-review-note"
                    value={reportReviewNote}
                    onChange={(event) => setReportReviewNote(event.target.value)}
                    placeholder="审核备注，例如：需补充项目证据后再采纳。"
                    disabled={busy}
                  />
                  {selectedReport.review_updated_at && (
                    <p className="report-review-meta">
                      当前状态：{selectedReport.review_label} · 更新于 {formatDate(selectedReport.review_updated_at)}
                    </p>
                  )}
                </div>
              )}
              {selectedResumeWriteReview && (
                <div className="report-review-box resume-write-review-box">
                  <div className="report-review-controls">
                    <label>
                      审核状态
                      <select
                        value={resumeWriteReviewStatus}
                        onChange={(event) => setResumeWriteReviewStatus(event.target.value)}
                        disabled={busy}
                      >
                        {resumeWriteReviewOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="secondary-button small-button"
                      onClick={handleUpdateResumeWriteReview}
                      disabled={busy || !selectedResumeWriteReview}
                    >
                      {loadingAction === "resume-write-review" ? (
                        <Loader2 className="spin" size={16} />
                      ) : (
                        <CheckCircle2 size={16} />
                      )}
                      更新状态
                    </button>
                  </div>
                  <textarea
                    className="report-review-note"
                    value={resumeWriteReviewNote}
                    onChange={(event) => setResumeWriteReviewNote(event.target.value)}
                    placeholder="审核备注，例如：证据充足时可人工复制候选表达。"
                    disabled={busy}
                  />
                  {selectedResumeWriteReview.review_updated_at && (
                    <p className="report-review-meta">
                      当前状态：{selectedResumeWriteReview.review_label} · 更新于{" "}
                      {formatDate(selectedResumeWriteReview.review_updated_at)}
                    </p>
                  )}
                </div>
              )}
              {selectedResumeDiff && resumeDiffCompare && (
                <div className="resume-diff-compare-panel">
                  <div className="compare-status-row">
                    <span>只读对比</span>
                    <span>不会覆盖真实简历</span>
                  </div>
                  <div className="resume-diff-compare-grid">
                    <section className="compare-column">
                      <h3>当前简历</h3>
                      <p title={resumeDiffCompare.current_resume?.name ?? ""}>
                        {resumeDiffCompare.current_resume?.name ?? "未设置当前简历"}
                      </p>
                      <article className="markdown-preview compare-markdown">
                        {resumeDiffCompare.current_resume_readable ? (
                          <ReactMarkdown>{resumeDiffCompare.current_resume_content}</ReactMarkdown>
                        ) : (
                          <div className="empty-state compact">当前简历无法以内联 Markdown 方式展示。</div>
                        )}
                      </article>
                    </section>
                    <section className="compare-column">
                      <h3>差异草稿</h3>
                      <p title={resumeDiffCompare.relative_path}>{resumeDiffCompare.relative_path}</p>
                      <article className="markdown-preview compare-markdown">
                        <ReactMarkdown>{getUserFacingDraftMarkdown(resumeDiffCompare.resume_diff_content)}</ReactMarkdown>
                      </article>
                    </section>
                  </div>
                  {resumeDiffCompare.warnings.length > 0 && (
                    <ul className="compare-warning-list">
                      {resumeDiffCompare.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              <article className="markdown-preview draft-markdown-preview">
                <ReactMarkdown>{getUserFacingDraftMarkdown(selectedCopy.content)}</ReactMarkdown>
              </article>
            </div>
          )}
            </section>
          </div>
        </div>
      </div>
    </section>
  );
}

function getSelectedInterviewQuestion(
  session: JobInterviewSessionResponse,
  questionId: number | null
): InterviewQuestion | null {
  if (!questionId || !session.session) return null;
  return session.session.questions.find((question) => question.question_id === questionId) ?? null;
}

function InterviewQuestionDetail({ question }: { question: InterviewQuestion | null }) {
  if (!question) return <div className="empty-state compact">请选择一个问题。</div>;
  const questionType = question.question_type || question.type;
  const questionText = question.stem || question.question;
  const skillLabel = question.tested_skill || question.skill_area;
  const riskText = question.safety_note || question.risk_hint || question.risk_reminder;
  const questionTypeLabel =
    questionType === "single_choice"
      ? "单选题"
      : questionType === "multiple_choice"
        ? "多选题"
        : questionType === "true_false"
          ? "判断题"
          : questionType === "short_answer"
            ? "简答题"
            : "开放题";
  const correctAnswer = Array.isArray(question.correct_answer)
    ? question.correct_answer.join(questionType === "short_answer" ? "；" : "、")
    : question.correct_answer || "";
  return (
    <div className="interview-question-detail">
      <div className="interview-question-meta">
        <span>{questionTypeLabel}</span>
        {skillLabel && <span>{skillLabel}</span>}
      </div>
      <p className="interview-question-main">{questionText}</p>
      {Boolean(question.options?.length) && (
        <div className="interview-options">
          {question.options?.map((option) => (
            <div className="interview-option" key={option.key}>
              <strong>{option.key}</strong>
              <span>{option.text}</span>
            </div>
          ))}
        </div>
      )}
      {correctAnswer && (
        <div className="interview-answer-box">
          <strong>正确答案：{correctAnswer}</strong>
          {question.explanation && <p>{question.explanation}</p>}
        </div>
      )}
      <p>{question.intent}</p>
      <ul>
        {(question.answer_checkpoints ?? []).map((checkpoint) => (
          <li key={checkpoint}>{checkpoint}</li>
        ))}
      </ul>
      {(question.source_requirement || question.requirement) && (
        <div className="artifact-detail-path">来源岗位要求：{question.source_requirement || question.requirement}</div>
      )}
      {riskText && <div className="warning-box compact-alert">{riskText}</div>}
    </div>
  );
}

function InterviewFeedbackCard({ feedback }: { feedback: JobInterviewFeedbackResponse }) {
  if (!feedback.feedback) return null;
  return (
    <div className="interview-feedback-card">
      <h3>回答反馈</h3>
      <div className="interview-feedback-metrics">
        <span>清晰度：{feedback.feedback.clarity}</span>
        <span>证据：{feedback.feedback.evidence_strength}</span>
        <span>边界：{feedback.feedback.boundary_risk}</span>
      </div>
      <p>{feedback.feedback.summary}</p>
      <DraftList title="亮点" items={feedback.feedback.strengths} />
      <DraftList title="改进建议" items={feedback.feedback.improvements} />
      <DraftList title="风险提醒" items={feedback.feedback.risk_flags} />
      <DraftList title="下一版回答结构" items={feedback.feedback.suggested_next_answer_shape} />
    </div>
  );
}

function DraftList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="draft-list-block">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="muted-text">暂无内容。</p>
      ) : (
        <ul>
          {items.slice(0, 5).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function KnowledgeBasePage() {
  const [activeCategory, setActiveCategory] = useState<CategoryKey>("industries");

  return (
    <section className="page library-page">
      <PageHeader title="资料库" />
      <div className="category-tabs">
        {libraryCategories.map((category) => {
          const meta = categoryMeta[category];
          return (
            <button
              key={category}
              className={activeCategory === category ? "active" : ""}
              onClick={() => setActiveCategory(category)}
            >
              {meta.title}
            </button>
          );
        })}
      </div>
      <DocumentPage category={activeCategory} embedded />
    </section>
  );
}

function DocumentPage({ category, embedded = false }: { category: CategoryKey; embedded?: boolean }) {
  const meta = categoryMeta[category];
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selected, setSelected] = useState<DocumentInfo | null>(null);
  const [currentResume, setCurrentResumeState] = useState<DocumentInfo | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [uploadSource, setUploadSource] = useState<"private" | "public">("private");
  const privateDocuments = documents.filter((documentInfo) => documentInfo.source === "private");
  const publicDocuments = documents.filter((documentInfo) => documentInfo.source === "public");

  useEffect(() => {
    refreshDocuments();
    setSelected(null);
    setContent("");
  }, [category]);

  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(""), 2800);
    return () => window.clearTimeout(timer);
  }, [message]);

  async function refreshDocuments() {
    setLoading(true);
    setError("");
    try {
      setDocuments(await listDocuments(category));
      if (category === "resumes") {
        setCurrentResumeState(await getCurrentResume());
      }
    } catch (requestError) {
      setError(formatRequestError(requestError, "读取文档列表失败。"));
    } finally {
      setLoading(false);
    }
  }

  async function handleSetCurrentResume(documentInfo: DocumentInfo) {
    setMessage("");
    setError("");
    try {
      const nextCurrentResume = await setCurrentResume(documentInfo);
      setCurrentResumeState(nextCurrentResume);
      setMessage("已设为当前简历。简历分析会优先使用这份资料。");
    } catch (requestError) {
      setError(formatRequestError(requestError, "设置当前简历失败。"));
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setMessage("");
    setError("");
    try {
      await uploadDocument(category, file, uploadSource);
      await refreshDocuments();
      setMessage("上传成功。请到索引状态页更新向量索引。");
    } catch (requestError) {
      setError(formatRequestError(requestError, "上传失败。"));
    } finally {
      event.target.value = "";
    }
  }

  async function handleDelete(documentInfo: DocumentInfo) {
    const confirmed = window.confirm(`确认删除 ${documentInfo.name}？`);
    if (!confirmed) return;
    setMessage("");
    setError("");
    try {
      await deleteDocument(category, documentInfo.name, documentInfo.source);
      if (selected?.name === documentInfo.name) {
        setSelected(null);
        setContent("");
      }
      await refreshDocuments();
      setMessage("已删除。请到索引状态页更新向量索引。");
    } catch (requestError) {
      setError(formatRequestError(requestError, "删除失败。"));
    }
  }

  async function handleSelect(documentInfo: DocumentInfo) {
    setSelected(documentInfo);
    setMessage("");
    setError("");
    if (!canPreviewMarkdown(documentInfo)) {
      setContent("");
      return;
    }
    try {
      setContent(await readDocument(category, documentInfo));
    } catch (requestError) {
      setError(formatRequestError(requestError, "读取文档失败。"));
    }
  }

  async function handleSave() {
    if (!selected) return;
    setMessage("");
    setError("");
    try {
      await updateDocument(category, selected.name, content, selected.source);
      await refreshDocuments();
      setMessage("已保存。请到索引状态页更新向量索引。");
    } catch (requestError) {
      setError(formatRequestError(requestError, "保存失败。"));
    }
  }

  return (
    <section className={embedded ? "document-page embedded-document-page" : "page document-page"}>
      {!embedded && <PageHeader title={meta.title} description={meta.description} />}
      <div className="document-toolbar">
        <label className="source-select">
          <span>上传到</span>
          <select value={uploadSource} onChange={(event) => setUploadSource(event.target.value as "private" | "public")}>
            <option value="private">本地私有资料</option>
            <option value="public">公开示例资料</option>
          </select>
        </label>
        <label className="upload-button">
          <Upload size={17} />
          {meta.uploadText}
          <input type="file" accept=".md,.docx,.pdf" onChange={handleUpload} />
        </label>
        <button className="secondary-button" onClick={refreshDocuments} disabled={loading}>
          <RefreshCw size={17} />
          刷新列表
        </button>
      </div>
      {message && (
        <div className="toast-stack" role="status" aria-live="polite">
          <div className="toast-message">
            <CheckCircle2 size={16} />
            <span>{message}</span>
          </div>
        </div>
      )}
      {error && <div className="error-box compact-alert">{error}</div>}

      <div className="document-layout">
        <section className="panel document-list-panel">
          <div className="panel-heading">
            <div>
              <h2>文档列表</h2>
              <p>{privateDocuments.length} 私有 · {publicDocuments.length} 示例</p>
            </div>
          </div>
          {category === "resumes" && currentResume && (
            <div className="current-resume-card" title={currentResume.name}>
              <CheckCircle2 size={16} />
              <span>当前简历：{currentResume.name}</span>
            </div>
          )}
          {documents.length === 0 && <div className="empty-state">当前分类还没有文档。</div>}
          <div className="document-list-scroll">
            <DocumentGroup
              title="本地私有资料"
              documents={privateDocuments}
              selected={selected}
              currentDocument={category === "resumes" ? currentResume : null}
              onSelect={handleSelect}
              onDelete={handleDelete}
              onSetCurrent={category === "resumes" ? handleSetCurrentResume : undefined}
            />
            <DocumentGroup
              title="公开示例资料"
              documents={publicDocuments}
              selected={selected}
              currentDocument={category === "resumes" ? currentResume : null}
              onSelect={handleSelect}
              onDelete={handleDelete}
              onSetCurrent={category === "resumes" ? handleSetCurrentResume : undefined}
            />
          </div>
        </section>

        <section className="panel editor-panel">
          <div className="panel-heading">
            <div>
              <h2>文档内容</h2>
            </div>
            {selected?.editable && (
              <button className="primary-button small" onClick={handleSave}>保存</button>
            )}
          </div>
          <div className="editor-body">
            {!selected && <div className="empty-state">从左侧选择一个文档。</div>}
            {selected && !canPreviewMarkdown(selected) && (
              <div className="empty-state">
                <strong>{selected.name}</strong>
                <span>
                {selected.source === "public" ? "暂不支持预览。" : "暂不支持编辑。"}
                </span>
              </div>
            )}
            {selected && canPreviewMarkdown(selected) && selected.editable && (
              <textarea className="markdown-editor" value={content} onChange={(event) => setContent(event.target.value)} />
            )}
            {selected && canPreviewMarkdown(selected) && !selected.editable && (
              <article className="markdown-preview">
                <ReactMarkdown>{content}</ReactMarkdown>
              </article>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function DocumentGroup({
  title,
  documents,
  selected,
  currentDocument,
  onSelect,
  onDelete,
  onSetCurrent,
  readonly = false,
}: {
  title: string;
  documents: DocumentInfo[];
  selected: DocumentInfo | null;
  currentDocument: DocumentInfo | null;
  onSelect: (documentInfo: DocumentInfo) => void;
  onDelete: (documentInfo: DocumentInfo) => void;
  onSetCurrent?: (documentInfo: DocumentInfo) => void;
  readonly?: boolean;
}) {
  if (documents.length === 0) {
    return (
      <div className="document-group">
        <div className="document-group-title">{title}</div>
        <div className="empty-state compact">暂无文档。</div>
      </div>
    );
  }

  return (
    <div className="document-group">
      <div className="document-group-title">{title}</div>
      <div className="document-list">
        {documents.map((documentInfo) => {
          const isCurrent =
            currentDocument?.name === documentInfo.name &&
            currentDocument?.source === documentInfo.source;
          return (
          <div
            key={`${documentInfo.source}-${documentInfo.name}`}
            className={`document-row ${
              selected?.name === documentInfo.name && selected?.source === documentInfo.source ? "selected" : ""
            } ${isCurrent ? "current-document" : ""
            }`}
            onClick={() => onSelect(documentInfo)}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(documentInfo);
              }
            }}
          >
            <div className="document-main">
              <strong>
                <span className="document-name" title={documentInfo.name}>{documentInfo.name}</span>
              </strong>
              <span>
                {formatSize(documentInfo.size_bytes)} · {formatDate(documentInfo.modified_at)}
              </span>
            </div>
            <div className="document-actions">
              {isCurrent && (
                <span className="current-text-badge">当前简历</span>
              )}
              {onSetCurrent && documentInfo.source === "private" && !isCurrent && (
                <button
                  className="text-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSetCurrent(documentInfo);
                  }}
                  title="设为当前简历"
                >
                  设为当前
                </button>
              )}
              {documentInfo.deletable && !readonly && (
                <button
                  className="icon-button danger"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(documentInfo);
                  }}
                  title="删除文档"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

function IndexPage({
  result,
  setResult,
}: {
  result: IndexResponse | null;
  setResult: (result: IndexResponse | null) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [productionStatus, setProductionStatus] = useState<ProductionWorkbenchStatus | null>(null);
  const [productionLoading, setProductionLoading] = useState(false);
  const [productionError, setProductionError] = useState("");

  useEffect(() => {
    refreshProductionStatus();
  }, []);

  async function refreshProductionStatus() {
    setProductionLoading(true);
    setProductionError("");
    try {
      setProductionStatus(await getProductionWorkbenchStatus());
    } catch (requestError) {
      setProductionError(formatRequestError(requestError, "读取生产运行状态失败。"));
    } finally {
      setProductionLoading(false);
    }
  }

  async function handleBuildIndex() {
    setLoading(true);
    setError("");
    try {
      const nextResult = await buildIndex();
      setResult(nextResult);
      sessionStorage.setItem("local-rag-index-result", JSON.stringify(nextResult));
    } catch (requestError) {
      setError(formatRequestError(requestError, "索引更新失败。"));
    } finally {
      setLoading(false);
    }
  }

  const metrics = useMemo(
    () => [
      ["更新文档", result?.changed_sources.length ?? 0],
      ["跳过文档", result?.skipped_sources.length ?? 0],
      ["删除文档", result?.removed_sources.length ?? 0],
      ["写入片段", result?.written_points ?? 0],
    ],
    [result]
  );

  return (
    <section className="page index-page">
      <PageHeader title="索引状态" />
      <ProductionStatusPanel
        status={productionStatus}
        loading={productionLoading}
        error={productionError}
        onRefresh={refreshProductionStatus}
      />
      <div className="index-actions">
        <button className="primary-button" onClick={handleBuildIndex} disabled={loading}>
          {loading ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
          更新索引
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div className="metric-grid">
        {metrics.map(([label, value]) => (
          <div className="metric-card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <section className="panel index-log-panel">
        <div className="panel-heading">
          <div>
            <h2>索引日志</h2>
          </div>
        </div>
        {!result && <div className="empty-state">暂无索引结果。</div>}
        {result && (
          <div className="log-list">
            <p>collection：{result.collection_name}</p>
            <p>storage：{result.storage_path}</p>
            {result.logs.slice(0, 60).map((logItem) => (
              <code key={logItem}>{logItem}</code>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

function ProductionStatusPanel({
  status,
  loading,
  error,
  onRefresh,
}: {
  status: ProductionWorkbenchStatus | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  const latestRun = status?.latest_run;
  const source = status?.source;
  const write = status?.write;
  const review = status?.review;
  const index = status?.index;
  const metrics = [
    ["来源", source?.gate_allowed ? "已放行" : "待确认", source?.source_name || source?.source_id || "暂无证据"],
    ["写入", write?.written_count ?? 0, `${write?.job_file_count ?? 0} 个岗位文件`],
    ["跳过", write?.skipped_count ?? 0, "去重或未变化"],
    ["失败", (write?.failed_count ?? 0) + (index?.failed_count ?? 0), "写入/索引失败"],
    ["待审核", review?.pending_count ?? 0, "报告/批次/写回"],
    ["索引", index?.status ? formatProductionIndexStatus(index.status) : "未知", `${index?.pending_count ?? 0} 待索引`],
  ] as const;

  return (
    <section className="panel production-status-panel" aria-label="生产运行状态">
      <div className="panel-heading production-status-heading">
        <div>
          <h2>生产运行</h2>
          <p>
            {latestRun
              ? `最近 RUN ${latestRun.run_number}：${latestRun.status} · ${latestRun.theme || latestRun.loop_id}`
              : "暂无 RUN 记录"}
          </p>
        </div>
        <button className="secondary-button small-button" type="button" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
          刷新
        </button>
      </div>
      {error && <div className="error-box compact-alert">{error}</div>}
      {!status && !error && <div className="empty-state compact">正在读取生产运行证据。</div>}
      {status && (
        <>
          <div className="production-metric-grid">
            {metrics.map(([label, value, detail]) => (
              <div className="production-metric" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
                <small>{detail}</small>
              </div>
            ))}
          </div>
          <div className="production-detail-grid">
            <div className="production-detail">
              <div className="detail-label">来源门禁</div>
              <div className="detail-value">
                {source?.gate_decision || "unknown"} · {source?.channel || "无来源通道"}
              </div>
              <div className="detail-note">
                采集 {source?.collected_count ?? 0} · schema 错误 {source?.schema_error_count ?? 0}
              </div>
            </div>
            <div className="production-detail">
              <div className="detail-label">审核队列</div>
              <div className="detail-value">
                报告 {review?.job_report_count ?? 0} · 批次 {review?.batch_queue_count ?? 0} · 写回 {review?.resume_write_review_count ?? 0}
              </div>
              <div className="detail-note">
                简历草稿 {review?.resume_draft_count ?? 0} · 岗位草稿 {review?.job_draft_count ?? 0}
              </div>
            </div>
            <div className="production-detail">
              <div className="detail-label">索引证据</div>
              <div className="detail-value">
                变化 {index?.changed_source_count ?? 0} · 索引 {index?.indexed_count ?? 0} · 跳过 {index?.skipped_count ?? 0}
              </div>
              <div className="detail-note" title={index?.evidence_file || ""}>
                {index?.evidence_file || "暂无证据文件"}
              </div>
            </div>
          </div>
          {status.warnings.length > 0 && (
            <div className="warning-box compact-alert">
              {status.warnings.map((item) => (
                <div key={item}>{item}</div>
              ))}
            </div>
          )}
          <div className="production-boundary">
            <ShieldCheck size={16} />
            <span>{status.boundaries[0]}</span>
          </div>
        </>
      )}
    </section>
  );
}

function formatProductionIndexStatus(status: string) {
  if (status === "verified_by_run6") return "RUN6 已验";
  if (status === "success") return "成功";
  if (status === "failed") return "失败";
  return status || "未知";
}

function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
    </header>
  );
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return value.replace("T", " ");
}

function formatMode(mode: AskResponse["mode"]) {
  if (mode === "rag") return "资料问答";
  if (mode === "system") return "系统信息";
  return "普通对话";
}

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createRequestId() {
  return crypto.randomUUID?.() ?? createMessageId();
}

function createEmptyAskResponse(): AskResponse {
  return {
    answer: "",
    truncated: false,
    sources: [],
    retrieval_seconds: 0,
    generation_seconds: 0,
    mode: "chat",
    artifacts: [],
  };
}

function appendAssistantDelta(message: ConversationMessage, text: string): ConversationMessage {
  const nextContent = message.content + text;
  return {
    ...message,
    content: nextContent,
    response: {
      ...(message.response ?? createEmptyAskResponse()),
      answer: nextContent,
      artifacts: message.response?.artifacts ?? [],
    },
  };
}

function cleanAnswer(answer: string) {
  return answer
    .replace(/(?:\n|^)\s*(?:#{1,6}\s*)?\*\*引用来源\*\*[:：]?\s*\n[\s\S]*$/u, "")
    .replace(/(?:\n|^)\s*(?:#{1,6}\s*)?引用来源[:：]?\s*\n[\s\S]*$/u, "")
    .trim();
}

function parseBatchQueries(value: string) {
  const results: string[] = [];
  for (const item of value.split(/[\n,，\t]+/u)) {
    const trimmed = item.trim();
    if (trimmed && !results.includes(trimmed)) {
      results.push(trimmed);
    }
  }
  return results;
}

function canPreviewMarkdown(documentInfo: DocumentInfo) {
  return documentInfo.name.toLowerCase().endsWith(".md");
}

function loadIndexResult() {
  const raw = sessionStorage.getItem("local-rag-index-result");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as IndexResponse;
  } catch {
    return null;
  }
}

const ASK_MESSAGES_STORAGE_KEY = "local-rag-ask-messages-v1";
const ASK_SELECTED_ARTIFACT_STORAGE_KEY = "local-rag-ask-selected-artifact-v1";

function loadAskMessages(): ConversationMessage[] {
  const raw = localStorage.getItem(ASK_MESSAGES_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isConversationMessage);
  } catch {
    return [];
  }
}

function saveAskMessages(messages: ConversationMessage[]) {
  localStorage.setItem(ASK_MESSAGES_STORAGE_KEY, JSON.stringify(messages));
}

function loadAskSelectedArtifact(): ChatArtifact | null {
  const raw = localStorage.getItem(ASK_SELECTED_ARTIFACT_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return isChatArtifact(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function saveAskSelectedArtifact(artifact: ChatArtifact | null) {
  if (!artifact) {
    localStorage.removeItem(ASK_SELECTED_ARTIFACT_STORAGE_KEY);
    return;
  }
  localStorage.setItem(ASK_SELECTED_ARTIFACT_STORAGE_KEY, JSON.stringify(artifact));
}

function clearAskConversationStorage() {
  localStorage.removeItem(ASK_MESSAGES_STORAGE_KEY);
  localStorage.removeItem(ASK_SELECTED_ARTIFACT_STORAGE_KEY);
}

function isConversationMessage(value: unknown): value is ConversationMessage {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<ConversationMessage>;
  return (
    typeof item.id === "string" &&
    (item.role === "user" || item.role === "assistant") &&
    typeof item.content === "string"
  );
}

function isChatArtifact(value: unknown): value is ChatArtifact {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<ChatArtifact>;
  return (
    typeof item.artifact_id === "string" &&
    typeof item.type === "string" &&
    typeof item.title === "string" &&
    typeof item.description === "string"
  );
}

export default App;
