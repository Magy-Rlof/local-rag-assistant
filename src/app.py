import re
import time
from pathlib import Path

import streamlit as st
from requests import HTTPError, RequestException, Timeout

from indexer import build_index
from main import (
    CAREER_ANALYSIS_CANDIDATE_K,
    DEFAULT_TOP_K,
    PRIVATE_DATA_DIR,
    QDRANT_PATH,
    ask_model,
    build_rag_prompt,
    create_embedding,
    get_api_key,
    is_career_analysis_question,
    search_qdrant,
    select_sections_for_question,
)


EXAMPLE_QUESTIONS = [
    "根据我的简历，我更适合哪些岗位？",
    "针对 AI 应用开发工程师岗位，这份简历应该怎么修改？",
    "Java 后端和 AI 应用开发有哪些结合点？",
    "企业软件行业有哪些 AI 应用场景？",
]
SUPPORTED_UPLOAD_TYPES = ["md", "docx", "pdf"]
UPLOAD_DIR = PRIVATE_DATA_DIR / "uploads"


def apply_page_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --page: #f6f7fb;
            --surface: #ffffff;
            --surface-subtle: #f8fafc;
            --ink: #111827;
            --muted: #5b6472;
            --line: #d9e0ea;
            --accent: #2563eb;
            --accent-hover: #1d4ed8;
            --accent-soft: #eaf1ff;
            --success-soft: #ecfdf5;
            --success: #047857;
            --warning-soft: #fff7ed;
            --warning: #9a3412;
        }

        .stApp {
            background: var(--page);
            color: var(--ink);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
        }

        .block-container {
            max-width: 1180px;
            padding: 2.4rem 2rem 3rem;
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] * {
            color: var(--ink);
        }

        [data-testid="stSidebar"] code {
            color: #1e40af;
            background: #eef4ff;
            border: 1px solid #cbdaf7;
            border-radius: 8px;
            padding: 0.2rem 0.35rem;
            white-space: pre-wrap;
            word-break: break-all;
        }

        h1, h2, h3 {
            color: var(--ink);
            letter-spacing: 0;
        }

        h1 {
            font-size: 2rem;
            line-height: 1.15;
            margin: 0 0 0.4rem;
        }

        h2 {
            font-size: 1.25rem;
            margin: 0.2rem 0 0.75rem;
        }

        h3 {
            font-size: 1rem;
            margin: 0 0 0.6rem;
        }

        p, li, label {
            color: var(--ink);
        }

        .app-kicker {
            color: var(--muted);
            font-size: 0.98rem;
            line-height: 1.6;
            max-width: 70ch;
            margin-bottom: 1.2rem;
        }

        .section-title {
            color: var(--ink);
            font-size: 0.96rem;
            font-weight: 700;
            margin: 1.2rem 0 0.55rem;
        }

        .surface {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 1rem 1.05rem;
        }

        .surface p {
            margin: 0 0 1rem;
            line-height: 1.55;
        }

        .surface p:last-child {
            margin-bottom: 0;
        }

        .answer-box {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 1rem 1.1rem;
            line-height: 1.75;
            margin-top: 0.7rem;
        }

        .source-item {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 0.85rem 0.95rem;
            margin-bottom: 0.65rem;
        }

        .source-title {
            font-weight: 700;
            color: var(--ink);
            margin-bottom: 0.2rem;
        }

        .source-meta {
            color: var(--muted);
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .metric-row {
            display: flex;
            gap: 0.65rem;
            flex-wrap: wrap;
            margin: 0.8rem 0 0.4rem;
        }

        .metric-pill {
            background: var(--accent-soft);
            color: #1744a3;
            border-radius: 999px;
            padding: 0.32rem 0.65rem;
            font-size: 0.86rem;
            font-weight: 650;
        }

        .privacy-note {
            background: var(--warning-soft);
            border: 1px solid #fed7aa;
            border-radius: 10px;
            color: var(--warning);
            font-size: 0.9rem;
            line-height: 1.55;
            padding: 0.75rem 0.85rem;
            margin-top: 0.8rem;
        }

        .flow-note {
            background: var(--success-soft);
            border: 1px solid #bbf7d0;
            border-radius: 10px;
            color: var(--success);
            font-size: 0.9rem;
            line-height: 1.55;
            padding: 0.75rem 0.85rem;
            margin-top: 0.8rem;
        }

        .question-list {
            display: flex;
            flex-direction: column;
            gap: 0.55rem;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 8px;
            border: 1px solid var(--line);
            background: var(--surface);
            color: var(--ink);
            min-height: 2.4rem;
            font-weight: 650;
            box-shadow: none;
        }

        div[data-testid="stButton"] > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            border-color: #b8c6da;
            background: var(--surface-subtle);
            color: var(--ink);
        }

        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
            background: var(--accent) !important;
            border-color: var(--accent) !important;
            color: #ffffff !important;
        }

        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            background: var(--accent-hover) !important;
            border-color: var(--accent-hover) !important;
            color: #ffffff !important;
        }

        [data-testid="stTextArea"] textarea {
            background: var(--surface) !important;
            color: var(--ink) !important;
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            min-height: 136px !important;
        }

        [data-testid="stTextArea"] textarea::placeholder {
            color: #6b7280 !important;
            opacity: 1 !important;
        }

        [data-testid="stTextArea"] label,
        [data-testid="stFileUploader"] label {
            font-weight: 700;
            color: var(--ink);
        }

        [data-testid="stAlert"] {
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def clean_upload_name(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    stem = Path(file_name).stem.strip() or "document"
    safe_stem = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1f]+', "_", stem)
    safe_stem = re.sub(r"\s+", "_", safe_stem).strip("._")
    if not safe_stem:
        safe_stem = "document"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{safe_stem}{suffix}"


def save_uploaded_files(uploaded_files: list) -> list[Path]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    for uploaded_file in uploaded_files:
        target_path = UPLOAD_DIR / clean_upload_name(uploaded_file.name)
        target_path.write_bytes(uploaded_file.getbuffer())
        saved_paths.append(target_path)
    return saved_paths


def run_rag(question: str) -> tuple[str, list[dict], float, float]:
    api_key = get_api_key()
    start_time = time.perf_counter()
    query_vector = create_embedding(api_key, question)
    retrieval_seconds = time.perf_counter() - start_time

    candidate_k = CAREER_ANALYSIS_CANDIDATE_K if is_career_analysis_question(question) else DEFAULT_TOP_K
    candidate_sections = search_qdrant(query_vector, top_k=candidate_k)
    retrieved_sections = select_sections_for_question(question, candidate_sections)
    if not retrieved_sections:
        raise RuntimeError("未检索到相关片段，请换一种问法。")

    prompt = build_rag_prompt(question, retrieved_sections)
    generation_start = time.perf_counter()
    answer = ask_model(api_key, prompt)
    generation_seconds = time.perf_counter() - generation_start
    return answer, retrieved_sections, retrieval_seconds, generation_seconds


def render_sidebar() -> None:
    st.sidebar.title("资料库")
    st.sidebar.caption("上传简历、岗位 JD 或项目说明，然后更新本地向量索引。")

    uploaded_files = st.sidebar.file_uploader(
        "上传私有资料",
        type=SUPPORTED_UPLOAD_TYPES,
        accept_multiple_files=True,
        help="文件会保存到 private_data/uploads/，该目录不会提交到 GitHub。",
    )

    if uploaded_files:
        if st.sidebar.button("保存上传文件", use_container_width=True):
            saved_paths = save_uploaded_files(uploaded_files)
            st.session_state["uploaded_saved"] = [path.name for path in saved_paths]
            st.sidebar.success(f"已保存 {len(saved_paths)} 个文件。")

    if st.session_state.get("uploaded_saved"):
        st.sidebar.markdown("已保存：")
        for file_name in st.session_state["uploaded_saved"]:
            st.sidebar.code(file_name, language=None)

    st.sidebar.divider()
    if st.sidebar.button("更新索引", type="primary", use_container_width=True):
        try:
            with st.sidebar:
                with st.status("正在更新索引...", expanded=True) as status:
                    messages: list[str] = []

                    def log(message: str) -> None:
                        messages.append(message)
                        if len(messages) <= 8:
                            st.write(message)

                    result = build_index(log=log)
                    status.update(label="索引更新完成", state="complete")
            st.sidebar.success(
                f"更新 {len(result.changed_sources)} 个文档，"
                f"跳过 {len(result.skipped_sources)} 个未变更文档，"
                f"写入 {result.written_points} 个片段。"
            )
        except RuntimeError as exc:
            st.sidebar.error(f"处理失败：{exc}")
        except HTTPError as exc:
            st.sidebar.error(f"Embedding API 请求失败：{exc}")
        except Timeout:
            st.sidebar.error("Embedding 请求超时，可以稍后重试。")
        except RequestException as exc:
            st.sidebar.error(f"Embedding 网络请求异常：{exc}")

    st.sidebar.divider()
    st.sidebar.caption("本地存储")
    st.sidebar.code(str(QDRANT_PATH), language=None)
    st.sidebar.markdown(
        """
        - `data/` 公开示例资料
        - `private_data/` 本地私有资料
        - `qdrant_storage/` 本地向量库
        """
    )
    st.sidebar.markdown(
        '<div class="privacy-note">真实简历会在建索引和问答时发送给模型 API。公开仓库只提交示例资料，不提交 private_data。</div>',
        unsafe_allow_html=True,
    )


def render_examples() -> None:
    st.markdown('<div class="section-title">常用问题</div>', unsafe_allow_html=True)
    st.markdown('<div class="question-list">', unsafe_allow_html=True)
    for index, question in enumerate(EXAMPLE_QUESTIONS):
        if st.button(question, use_container_width=True, key=f"example_{index}"):
            st.session_state["question"] = question
    st.markdown("</div>", unsafe_allow_html=True)


def render_sources(sections: list[dict]) -> None:
    st.markdown('<div class="section-title">引用来源</div>', unsafe_allow_html=True)
    for section in sections:
        score = section.get("score")
        score_text = f"{score:.4f}" if isinstance(score, float) else "unknown"
        st.markdown(
            f"""
            <div class="source-item">
              <div class="source-title">{section["title"]}</div>
              <div class="source-meta">{section["source_file"]} · score={score_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_answer(answer: str, sources: list[dict], retrieval_seconds: float, generation_seconds: float) -> None:
    st.markdown('<div class="section-title">回答</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="answer-box">{answer}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="metric-row">
          <span class="metric-pill">检索 {retrieval_seconds:.1f}s</span>
          <span class="metric-pill">生成 {generation_seconds:.1f}s</span>
          <span class="metric-pill">引用 {len(sources)} 条</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_sources(sources)


def main() -> None:
    st.set_page_config(
        page_title="Local RAG Assistant",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_page_style()
    render_sidebar()

    if "question" not in st.session_state:
        st.session_state["question"] = ""

    st.title("Local RAG Assistant")
    st.markdown(
        '<p class="app-kicker">面向求职资料、项目说明和岗位 JD 的本地 RAG 问答工具。上传资料后更新索引，再用自然语言询问岗位匹配、简历修改和项目表达。</p>',
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([0.62, 0.38], gap="large")

    with left_col:
        render_examples()
        st.markdown('<div class="section-title">输入问题</div>', unsafe_allow_html=True)
        with st.form("rag_question_form", clear_on_submit=False):
            question = st.text_area(
                "问题",
                key="question",
                placeholder="例如：根据我的简历，我更适合哪些岗位？",
                label_visibility="collapsed",
            )
            submit = st.form_submit_button("生成回答", type="primary", use_container_width=True)

    with right_col:
        st.markdown('<div class="section-title">当前流程</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="surface">
              <p><strong>1. 上传资料</strong><br>简历、JD 或项目说明放入私有资料库。</p>
              <p><strong>2. 更新索引</strong><br>只处理新增或变化的文档。</p>
              <p><strong>3. 提问分析</strong><br>答案会附带引用来源，便于核对。</p>
              <div class="flow-note">支持上传 .md、.docx、.pdf。上传后请在左侧点击“更新索引”。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not submit:
        return

    question_text = st.session_state["question"].strip()
    if not question_text:
        st.warning("请输入问题。")
        return

    try:
        with st.spinner("正在检索知识库并生成回答..."):
            answer, sources, retrieval_seconds, generation_seconds = run_rag(question_text)
    except RuntimeError as exc:
        st.error(f"处理失败：{exc}")
        return
    except HTTPError as exc:
        st.error(f"API 请求失败：{exc}")
        return
    except Timeout:
        st.error("请求超时：模型响应较慢，可以稍后重试或减少问题范围。")
        return
    except RequestException as exc:
        st.error(f"网络请求异常：{exc}")
        return

    render_answer(answer, sources, retrieval_seconds, generation_seconds)


if __name__ == "__main__":
    main()
