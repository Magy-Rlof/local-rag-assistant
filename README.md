# Local RAG Assistant

一个最小 RAG Demo，用于演示如何从本地 Markdown 文档中检索相关片段，并让大模型基于片段回答问题。

本项目是“AI 求职与项目知识库助手”的 RAG 原型，重点学习 RAG 的基础流程，而不是追求复杂框架。

## 功能

- 读取本地 Markdown 文档
- 按 Markdown 标题切分文档片段
- 使用简单关键词匹配检索相关片段
- 将检索结果作为上下文发送给模型
- 输出模型回答和引用来源

## 技术栈

- Python 3
- requests
- 硅基流动 API
- 模型：`deepseek-ai/DeepSeek-V4-Pro`
- API 地址：`https://api.siliconflow.cn/v1/chat/completions`

## 项目结构

```text
local-rag-assistant/
  README.md
  requirements.txt
  .env.example
  .gitignore
  data/
    sample_project.md
  src/
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

```powershell
python .\src\main.py
```

按提示输入问题，例如：

```text
这个示例项目有哪些功能？
这个示例项目有什么局限性？
这个示例项目适合用来学习什么？
```

程序会检索 `data/sample_project.md` 中的相关片段，并让模型基于片段回答。

## RAG 流程

```text
用户提问
-> 读取 Markdown 文档
-> 按标题切分文档
-> 关键词匹配相关片段
-> 将片段作为上下文交给模型
-> 输出回答和引用来源
```

## 局限性

- 仅为学习 Demo，不是生产系统。
- 当前只读取一个 Markdown 示例文档。
- 检索方式是简单关键词匹配，不是 Embedding 或向量数据库。
- 匹配效果依赖用户问题和文档词汇是否接近。
- 未实现多轮对话、权限系统、文件上传或 Web 页面。
- 模型回答质量受检索片段质量和模型能力影响。

## 后续改进方向

- 支持读取多个 Markdown 文档。
- 增加更好的关键词清洗和片段排序。
- 增加引用来源的文件名和标题。
- 引入 Embedding 和向量数据库。
- 扩展为简历、项目和岗位 JD 的知识库问答助手。
