# Local RAG Assistant

Local RAG Assistant 是一个面向求职资料、项目说明和岗位 JD 的本地 RAG 问答工具。它可以读取本地知识库文档，生成 Embedding，写入 Qdrant 本地向量库，并让大模型基于检索到的资料回答问题。

项目重点是展示 AI 应用开发中的可落地能力：文档加载、文本切分、向量化、向量检索、上下文拼接、引用来源展示、私有资料管理和可视化工作台。

## 功能

- 读取 `data/` 下的公开示例资料。
- 读取 `private_data/` 下的本地私有资料。
- 支持 `.md`、`.docx`、`.pdf` 文档。
- 使用 `BAAI/bge-m3` 生成文本向量。
- 使用 Qdrant 本地模式保存和检索向量。
- 使用大模型基于检索片段生成回答。
- 输出回答、引用来源、检索耗时和生成耗时。
- 支持增量索引：未修改文档不会重复生成 Embedding。
- 提供 React 工作台，支持资料上传、删除、Markdown 编辑、索引更新和问答分析。
- 保留 Streamlit 旧版入口，便于对照学习。

## 使用场景

- 根据简历分析适合的岗位方向。
- 针对某个岗位 JD，分析简历应该如何修改。
- 查询项目经历与岗位要求的匹配点。
- 对多个行业和岗位资料进行问答。
- 整理项目说明、学习笔记和面试表达。

## 技术栈

- Python 3
- FastAPI
- React
- TypeScript
- Vite
- Streamlit（旧版入口）
- requests
- qdrant-client
- python-docx
- pypdf
- 硅基流动 API
- Chat 模型：`deepseek-ai/DeepSeek-V4-Pro`
- Embedding 模型：`BAAI/bge-m3`
- Chat API：`https://api.siliconflow.cn/v1/chat/completions`
- Embedding API：`https://api.siliconflow.cn/v1/embeddings`

模型价格、限额和可用性以平台控制台为准。

## 项目结构

```text
local-rag-assistant/
  README.md
  requirements.txt
  .env.example
  .gitignore
  data/
    industries/
    job_descriptions/
    learning_notes/
    projects/
  private_data/          # 本地私有资料，不提交，支持 .md/.docx/.pdf
  qdrant_storage/        # 本地向量库，不提交
  backend/
    app.py               # FastAPI 后端入口
    document_service.py  # 私有资料管理
    rag_service.py       # RAG 问答服务
    schemas.py           # API 数据结构
  frontend/
    package.json
    src/
      App.tsx            # React 工作台
      api.ts             # 前端 API 调用
      styles.css         # 界面样式
  src/
    app.py               # Streamlit 旧版界面
    build_index.py       # 命令行增量索引入口
    document_loader.py   # 文档加载
    indexer.py           # 可复用增量索引逻辑
    main.py              # 命令行问答入口
```

## 准备 API Key

不要把真实 API Key 写进代码或提交到 GitHub。

PowerShell 临时设置：

```powershell
$env:SILICONFLOW_API_KEY="your_siliconflow_api_key_here"
```

也可以参考 `.env.example` 中的变量名，但不要提交真实 `.env` 文件。

## 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

前端依赖在 `frontend/` 下安装：

```powershell
cd frontend
npm install
```

## 构建索引

第一次运行前需要先构建 Qdrant 本地索引：

```powershell
python .\src\build_index.py
```

修改、添加或删除资料后，也需要重新运行索引。脚本会跳过未变化的文档，只处理新增、修改或删除的文档。

## 启动新版工作台

先启动后端：

```powershell
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

再启动前端：

```powershell
cd frontend
npm run dev
```

默认前端地址：

```text
http://127.0.0.1:5173
```

新版工作台支持：

- 问答分析：输入问题，查看回答和引用来源。
- 简历库：上传、查看、删除简历。
- 岗位资料：上传、查看、删除，Markdown 可在线编辑。
- 项目资料：上传、查看、删除，Markdown 可在线编辑。
- 学习笔记：上传、查看、删除，Markdown 可在线编辑。
- 索引状态：一键更新 Qdrant 本地向量索引。

## 启动旧版 Streamlit 界面

```powershell
streamlit run .\src\app.py
```

旧版 Streamlit 界面用于学习和对照，不是当前主推荐入口。

示例问题：

```text
根据我的简历，我更适合哪些岗位？
针对 AI 应用开发工程师岗位，这份简历应该怎么修改？
Java 后端和 AI 应用开发有哪些结合点？
企业软件行业有哪些 AI 应用场景？
```

## 命令行运行

如果不使用可视化界面，也可以运行命令行问答：

```powershell
python .\src\main.py
```

## 替换知识库资料

公开示例资料放在 `data/` 下，适合提交到 GitHub。可以用自己的模拟行业资料、岗位资料、学习笔记和项目说明替换。

建议：

1. 公开示例资料优先使用 Markdown。
2. Markdown 尽量用标题组织内容，例如 `# 文档标题`、`## 小节标题`。
3. 不要把真实简历、手机号、身份证号、API Key、公司内部资料放进 `data/`。
4. 更新资料后运行 `python .\src\build_index.py` 或在 Streamlit 界面点击“更新索引”。

## 使用私有资料

真实简历、真实岗位 JD、未公开项目说明会由新版工作台写入 `private_data/` 下的分类目录，也可以手动放入：

```text
private_data/
```

例如：

```text
private_data/
  resumes/
    resume.docx
  job_descriptions/
    target_job.md
  projects/
    project_notes.md
  learning_notes/
    rag_notes.md
```

`private_data/` 已加入 `.gitignore`，不会被提交到 GitHub。

注意：

- 真实资料在建索引和问答时会发送给硅基流动 API。
- 如果不希望第三方 API 处理真实隐私内容，请先脱敏，或暂时不要使用真实资料。
- PDF 文本提取质量取决于文件本身，扫描件当前不支持 OCR。
- Word 文档会尽量保留标题层级，便于按小节切分。

## RAG 流程

```text
用户上传或放入资料
-> 加载 md/docx/pdf
-> 按标题切分文档片段
-> 调用 Embedding API 生成向量
-> 写入 Qdrant 本地向量库
-> 用户提问
-> 为问题生成向量
-> Qdrant 检索相似片段
-> 拼接上下文并发送给 Chat 模型
-> 输出回答和引用来源
```

## 局限性

- 这是学习和作品集项目，不是生产系统。
- 内置行业和岗位资料是模拟示例，不代表实时招聘市场。
- 当前使用 Qdrant 本地文件模式，不是 Docker 或云端服务。
- PDF 扫描件暂不支持 OCR。
- 模型回答质量受资料质量、检索结果和模型能力影响。
- 使用真实私有资料时，需要自行评估隐私风险。

## 后续改进方向

- 增加检索过滤，例如按资料类型、行业、岗位筛选。
- 增加检索评估和重排序。
- 支持多轮对话。
- 增加更完整的资料详情和批量操作。
- 增加索引状态检查和错误恢复提示。
