# Local RAG Assistant

一个本地 RAG Demo，用于演示如何从 Markdown 文档中生成 Embedding，写入 Qdrant 本地向量库，并让大模型基于检索片段回答问题。

本项目是“AI 求职与项目知识库助手”的 RAG 原型，重点学习 RAG 的基础流程，而不是追求复杂框架。

## 功能

- 读取本地多个 Markdown 文档
- 按 Markdown 标题切分文档片段
- 使用 `BAAI/bge-m3` 生成文档片段向量
- 使用 Qdrant 本地模式保存和检索向量
- 将检索结果作为上下文发送给模型
- 输出模型回答和引用来源

## 技术栈

- Python 3
- requests
- qdrant-client
- 硅基流动 API
- Chat 模型：`deepseek-ai/DeepSeek-V4-Pro`
- Embedding 模型：`BAAI/bge-m3`
- Chat API：`https://api.siliconflow.cn/v1/chat/completions`
- Embedding API：`https://api.siliconflow.cn/v1/embeddings`

## 项目结构

```text
local-rag-assistant/
  README.md
  requirements.txt
  .env.example
  .gitignore
  data/
    sample_job_description.md
    sample_learning_note.md
    sample_project.md
  qdrant_storage/        # 本地生成，不提交
  src/
    build_index.py
    check_embedding.py
    main.py
```

## 准备 API Key

不要把真实 API Key 写进代码或提交到 GitHub。

在 PowerShell 中设置环境变量：

```powershell
$env:SILICONFLOW_API_KEY="your_siliconflow_api_key_here"
```

也可以参考 `.env.example` 中的变量名，但不要提交真实 `.env` 文件。

## 安装依赖

建议先创建 Python 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行方式

先构建本地向量索引：

```powershell
python .\src\build_index.py
```

再运行问答程序：

```powershell
python .\src\main.py
```

按提示输入问题，例如：

```text
这个示例项目有哪些功能？
这个示例项目有什么局限性？
这个示例项目适合用来学习什么？
这个示例岗位需要哪些能力？
学习笔记里提到了哪些 AI 应用基础能力？
```

程序会从 Qdrant 本地向量库中检索 `data/` 目录对应的 Markdown 片段，并让模型基于相关片段回答。

## RAG 流程

```text
用户提问
-> 读取多个 Markdown 文档
-> 按标题切分文档
-> 调用 Embedding API 生成向量
-> 写入 Qdrant 本地向量库
-> 用户问题生成向量
-> Qdrant 相似度检索相关片段
-> 将片段作为上下文交给模型
-> 输出回答和引用来源
```

## 局限性

- 仅为学习 Demo，不是生产系统。
- 当前只读取 `data/` 目录下的 Markdown 示例文档。
- 当前使用 Qdrant 本地文件模式，不是 Docker 或云端服务。
- 文档变更后需要重新运行 `build_index.py` 更新向量索引。
- Embedding 和 Chat API 调用依赖硅基流动服务状态和账号权限。
- 未实现多轮对话、权限系统、文件上传或 Web 页面。
- 模型回答质量受检索片段质量和模型能力影响。

## 后续改进方向

- 支持更多文档格式，例如 PDF、Word 或网页内容。
- 增加 metadata 过滤，例如按文档类型检索岗位、项目或学习笔记。
- 增加索引增量更新，避免每次重建全部向量。
- 增加检索评估和重排序。
- 扩展为简历、项目和岗位 JD 的知识库问答助手。
