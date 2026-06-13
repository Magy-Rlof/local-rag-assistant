# AI 应用开发框架与平台对比

> 说明：本文档用于支持技术解释类问答，帮助区分 Dify、LangChain、LlamaIndex 和手写 RAG 的定位。

## Dify

Dify 是一个面向大模型应用搭建的低代码平台，常用于快速创建聊天助手、知识库问答、工作流和 Agent 原型。

Dify 的优势是上手快、界面化配置多、适合业务验证和原型交付。开发者可以通过界面配置模型供应商、知识库、Prompt、工作流节点和发布方式，不需要从零编写完整后端代码。

Dify 的局限是底层流程被平台封装，灵活性和可控性不如手写代码。遇到复杂检索策略、深度业务系统集成、定制化权限、复杂日志或特殊数据处理时，可能需要额外开发或绕过平台限制。

## LangChain

LangChain 是一个通用的大模型应用编排框架。它提供 LLM、Prompt Template、Retriever、Chain、Agent、Tool、Memory 等抽象，适合把模型调用、检索、工具调用和多步流程组合成应用。

在 RAG 场景中，LangChain 可以封装文档加载、文本切分、Embedding、向量库、Retriever、Prompt 拼接和模型调用。它更像“应用流程编排层”，适合需要工具调用、多步骤推理、对话状态或复杂业务流程的场景。

## LlamaIndex

LlamaIndex 更关注“数据如何被大模型使用”。它围绕 Document、Node、Index、Retriever、Query Engine 等概念组织文档和私有数据，适合以文档索引和知识库问答为核心的 RAG 应用。

在 RAG 场景中，LlamaIndex 对文档解析、节点切分、索引构建、检索策略和回答合成提供了较完整的抽象。它更像“数据索引与查询层”，适合文档问答、知识库检索、资料摘要和私有数据问答。

## 手写 RAG

手写 RAG 是指开发者直接实现文档加载、切分、Embedding、向量入库、向量检索、上下文拼接、Prompt 设计和模型调用。

手写 RAG 的优势是流程透明、可控性高、便于理解底层机制，也方便针对具体业务做定制化优化。缺点是开发成本更高，样板代码更多，需要自己处理错误、评估、日志、上下文长度和检索质量。

## 选择建议

- 快速做业务原型、知识库问答或工作流演示：优先考虑 Dify。
- 需要编排多步骤 LLM 应用、工具调用、Agent 或复杂业务流程：优先考虑 LangChain。
- 主要目标是高质量文档索引、知识库问答和私有数据检索：优先考虑 LlamaIndex。
- 学习 RAG 原理、做高度定制化检索或展示底层工程能力：可以手写 RAG。

## 与 local-rag-assistant 的关系

local-rag-assistant 采用手写 RAG 路线，目的是理解并展示文档加载、切分、Embedding、Qdrant 向量检索、上下文拼接和模型回答的完整链路。

后续如果使用 Dify、LangChain 或 LlamaIndex，local-rag-assistant 的手写经验可以帮助判断框架封装了哪些步骤、哪些地方需要自定义，以及为什么某些回答质量问题要从资料、检索、Prompt 和上下文组装共同排查。
