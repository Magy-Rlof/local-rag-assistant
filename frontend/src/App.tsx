import {
  BriefcaseBusiness,
  FileSearch,
  FileText,
  FolderKanban,
  GraduationCap,
  Library,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Send,
  Trash2,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  AskResponse,
  CategoryKey,
  DocumentInfo,
  IndexResponse,
  askQuestion,
  buildIndex,
  deleteDocument,
  listDocuments,
  readDocument,
  updateDocument,
  uploadDocument,
} from "./api";

type PageKey = "ask" | CategoryKey | "index";

type NavItem = {
  key: PageKey;
  label: string;
  description: string;
  icon: LucideIcon;
};

const navItems: NavItem[] = [
  { key: "ask", label: "问答分析", description: "简历与岗位匹配", icon: FileSearch },
  { key: "resumes", label: "简历库", description: "上传与删除简历", icon: FileText },
  { key: "jobs", label: "岗位资料", description: "JD 文档管理", icon: BriefcaseBusiness },
  { key: "projects", label: "项目资料", description: "项目说明管理", icon: FolderKanban },
  { key: "notes", label: "学习笔记", description: "知识笔记管理", icon: GraduationCap },
  { key: "index", label: "索引状态", description: "更新向量索引", icon: RefreshCw },
];

const categoryMeta: Record<CategoryKey, { title: string; description: string; uploadText: string }> = {
  resumes: {
    title: "简历库",
    description: "简历文件",
    uploadText: "上传简历",
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
  notes: {
    title: "学习笔记",
    description: "知识笔记",
    uploadText: "上传学习笔记",
  },
};

const exampleQuestions = [
  "根据我的简历，我更适合哪些岗位？",
  "针对 AI 应用开发工程师岗位，这份简历应该怎么修改？",
  "我的项目经历和 Java 后端岗位有哪些匹配点？",
  "岗位资料里提到的核心能力有哪些？",
];

function App() {
  const [activePage, setActivePage] = useState<PageKey>("ask");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [indexResult, setIndexResult] = useState<IndexResponse | null>(() => loadIndexResult());

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
        {activePage === "ask" && <AskPage />}
        {activePage === "resumes" && <DocumentPage category="resumes" />}
        {activePage === "jobs" && <DocumentPage category="jobs" />}
        {activePage === "projects" && <DocumentPage category="projects" />}
        {activePage === "notes" && <DocumentPage category="notes" />}
        {activePage === "index" && <IndexPage result={indexResult} setResult={setIndexResult} />}
      </main>
    </div>
  );
}

function AskPage() {
  const [question, setQuestion] = useState(exampleQuestions[0]);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitQuestion() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setError("请输入问题。");
      return;
    }

    setLoading(true);
    setError("");
    try {
      setResponse(await askQuestion(trimmedQuestion));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "生成回答失败。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page ask-page">
      <div className="ask-topline">
        <h1>问答分析</h1>
        {response && (
          <div className="metric-group">
            <span>检索 {response.retrieval_seconds.toFixed(1)}s</span>
            <span>生成 {response.generation_seconds.toFixed(1)}s</span>
          </div>
        )}
      </div>

      <div className="ai-layout">
        <div className="chat-column">
          <section className="chat-surface">
            {!response && !error && (
              <div className="welcome-state">
                <h2>问我关于简历、岗位或项目的问题</h2>
                <div className="suggestion-chips">
                  {exampleQuestions.map((item) => (
                    <button key={item} onClick={() => setQuestion(item)}>
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {error && <div className="error-box">{error}</div>}
            {response && (
              <article className="assistant-response">
                <ReactMarkdown>{cleanAnswer(response.answer)}</ReactMarkdown>
              </article>
            )}
            {response?.truncated && (
              <div className="warning-box">回答可能不完整。可以缩小问题范围后重试。</div>
            )}
          </section>

          <section className="composer">
            <textarea
              className="composer-input"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="输入问题，按生成回答"
            />
            <div className="composer-actions">
              <button className="primary-button" onClick={submitQuestion} disabled={loading}>
                {loading ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                生成回答
              </button>
            </div>
          </section>
        </div>

        <aside className="citation-rail">
          <div className="rail-title">引用</div>
          {!response && <div className="empty-state compact">暂无引用</div>}
          <div className="source-list">
            {response?.sources.map((source) => (
              <div className="source-card" key={`${source.source_file}-${source.title}`}>
                <strong>{source.title}</strong>
                <span>{source.source_file}</span>
                {source.score !== null && <small>score {source.score.toFixed(4)}</small>}
              </div>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function DocumentPage({ category }: { category: CategoryKey }) {
  const meta = categoryMeta[category];
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selected, setSelected] = useState<DocumentInfo | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const privateDocuments = documents.filter((documentInfo) => documentInfo.source === "private");
  const publicDocuments = documents.filter((documentInfo) => documentInfo.source === "public");

  useEffect(() => {
    refreshDocuments();
    setSelected(null);
    setContent("");
  }, [category]);

  async function refreshDocuments() {
    setLoading(true);
    setError("");
    try {
      setDocuments(await listDocuments(category));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "读取文档列表失败。");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setMessage("");
    setError("");
    try {
      await uploadDocument(category, file);
      await refreshDocuments();
      setMessage("上传成功。请到索引状态页更新向量索引。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "上传失败。");
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
      await deleteDocument(category, documentInfo.name);
      if (selected?.name === documentInfo.name) {
        setSelected(null);
        setContent("");
      }
      await refreshDocuments();
      setMessage("已删除。请到索引状态页更新向量索引。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "删除失败。");
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
      setError(requestError instanceof Error ? requestError.message : "读取文档失败。");
    }
  }

  async function handleSave() {
    if (!selected) return;
    setMessage("");
    setError("");
    try {
      await updateDocument(category, selected.name, content);
      await refreshDocuments();
      setMessage("已保存。请到索引状态页更新向量索引。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "保存失败。");
    }
  }

  return (
    <section className="page document-page">
      <PageHeader title={meta.title} description={meta.description} />
      <div className="document-toolbar">
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
      {message && <div className="success-box compact-alert">{message}</div>}
      {error && <div className="error-box compact-alert">{error}</div>}

      <div className="document-layout">
        <section className="panel document-list-panel">
          <div className="panel-heading">
            <div>
              <h2>文档列表</h2>
              <p>{privateDocuments.length} 私有 · {publicDocuments.length} 示例</p>
            </div>
          </div>
          {documents.length === 0 && <div className="empty-state">当前分类还没有文档。</div>}
          <div className="document-list-scroll">
            <DocumentGroup
              title="本地私有资料"
              documents={privateDocuments}
              selected={selected}
              onSelect={handleSelect}
              onDelete={handleDelete}
            />
            <DocumentGroup
              title="公开示例资料"
              documents={publicDocuments}
              selected={selected}
              onSelect={handleSelect}
              onDelete={handleDelete}
              readonly
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
  onSelect,
  onDelete,
  readonly = false,
}: {
  title: string;
  documents: DocumentInfo[];
  selected: DocumentInfo | null;
  onSelect: (documentInfo: DocumentInfo) => void;
  onDelete: (documentInfo: DocumentInfo) => void;
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
        {documents.map((documentInfo) => (
          <div
            key={`${documentInfo.source}-${documentInfo.name}`}
            className={`document-row ${
              selected?.name === documentInfo.name && selected?.source === documentInfo.source ? "selected" : ""
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
            <div>
              <strong>{documentInfo.name}</strong>
              <span>
                {formatSize(documentInfo.size_bytes)} · {formatDate(documentInfo.modified_at)}
              </span>
            </div>
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
        ))}
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

  async function handleBuildIndex() {
    setLoading(true);
    setError("");
    try {
      const nextResult = await buildIndex();
      setResult(nextResult);
      sessionStorage.setItem("local-rag-index-result", JSON.stringify(nextResult));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "索引更新失败。");
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
    <section className="page">
      <PageHeader title="索引状态" />
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
      <section className="panel">
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

function cleanAnswer(answer: string) {
  return answer
    .replace(/\n?\s*\*\*引用来源\*\*[:：]?[\s\S]*$/u, "")
    .replace(/\n?\s*引用来源[:：]?[\s\S]*$/u, "")
    .trim();
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

export default App;
