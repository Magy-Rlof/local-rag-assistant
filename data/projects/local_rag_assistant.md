# 示例项目：Local RAG Assistant

> 说明：本文档为模拟示例数据，用于说明当前项目能力。

## 项目定位

Local RAG Assistant 是一个本地 RAG Demo，用于演示如何读取 Markdown 文档、生成 Embedding、写入 Qdrant，并基于向量检索结果调用大模型回答问题。

## 核心功能

- 递归读取 data 目录下的 Markdown 文档
- 按标题切分文档片段
- 使用 BAAI/bge-m3 生成文本向量
- 使用 Qdrant 本地模式进行向量检索
- 使用 DeepSeek-V4-Pro 基于检索片段生成回答
- 返回引用来源和相似度分数

## 技术价值

项目展示了 RAG 的基本工程链路，包括文档加载、切分、Embedding、向量入库、语义检索、上下文拼接和模型回答。

## 局限性

当前项目只支持 Markdown 文档，不包含 Web 页面、文件上传、多用户权限或生产部署。Qdrant 使用本地文件模式，适合学习和 Demo。
