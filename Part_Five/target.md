# AI Agent 面试完整学习路线

## 学习深度说明

```text
深入掌握：
需要理解原理、能够设计，并在 LocalAgent 中实现。

正常掌握：
能够解释核心机制、分析方案，并完成小型 Demo。

概念了解：
知道解决什么问题、与其他技术的关系，面试时能简要说明。
```

------

# 第一阶段：Agent Harness 与运行时

## 1. Agent Harness（智能体运行框架）【深入掌握】

理解模型外部如何统一管理 Agent Loop（智能体循环）、工具、上下文、状态、审批、安全、恢复和评估。最终要能清楚说明 LocalAgent 为什么可以被视为一个初级自研 Harness。

## 2. Agent Runtime（智能体运行时）【深入掌握】

学习一次 Agent 任务从创建、运行、暂停、恢复到结束的完整生命周期，包括 RunContext（运行上下文）、状态机、停止条件和资源预算。

## 3. State Machine（状态机）【深入掌握】

用明确状态描述任务的 `pending、running、waiting、completed、failed、cancelled` 等阶段，避免复杂任务只依靠自然语言和临时变量控制。

## 4. Checkpoint 与 Resume（检查点与恢复）【深入掌握】

让长任务在服务重启、模型超时或等待人工审批后，从最近状态继续运行，而不是从头执行。

------

# 第二阶段：Skill 与 Tool 能力系统

## 5. Skill（技能）体系【深入掌握】

理解 Skill、Tool（工具）、Agent（智能体）和 Prompt（提示词）的区别。学习 Skill Manifest（技能清单）、动态发现、按需加载、版本管理、权限和独立评估。

## 6. Tool Registry（工具注册中心）【深入掌握】

统一管理工具的输入输出 Schema（结构定义）、风险等级、角色权限、路径权限、超时、重试和审计信息。

## 7. Skill 与 Tool 编排【深入掌握】

让 Skill 描述“如何完成一类任务”，Tool 负责执行确定动作，Agent 根据目标选择 Skill 和 Tool，而不是把业务流程全部写死在 Agent 代码中。

## 8. Plugin Marketplace（插件市场）【概念了解】

理解企业 Agent 平台如何安装、启用、禁用、升级和共享 Skill、Tool 与插件，不要求现在实现完整市场。

------

# 第三阶段：Agent 协议体系

## 9. MCP（模型上下文协议）【深入掌握】

从概念学习升级为实际开发：实现 MCP Client（客户端）和 MCP Server（服务端），掌握 Tool、Resource、Prompt、传输方式、权限、超时和错误处理。

## 10. A2A（智能体到智能体协议）【正常掌握】

理解独立 Agent 如何通过 Agent Card（智能体能力卡）、Task（任务）、Message（消息）和 Artifact（产物）进行发现和协作，并完成一个最小通信 Demo。

## 11. AG-UI（智能体用户交互协议）【概念了解】

理解 Agent 后端如何向前端标准化传递运行状态、流式事件、工具调用和人工审批；可以和现有 `[[ORCH]]` 事件进行对比。

## 12. A2UI（智能体到用户界面协议）【概念了解】

理解 Agent 如何输出声明式界面描述，让前端使用可信组件进行渲染，目前不需要在 PyQt6 中完整实现。

------

# 第四阶段：安全执行与持久化任务

## 13. Sandbox（沙箱）【深入掌握】

学习如何使用 Docker（容器技术）或隔离工作区执行模型生成的代码和命令，并限制文件系统、网络、CPU、内存、时间和环境变量。

## 14. Durable Execution（持久化执行）【深入掌握】

掌握长任务的状态持久化、任务恢复、事件日志、任务租约和审批暂停，理解服务重启后任务如何继续。

## 15. Idempotency（幂等性）【深入掌握】

确保工具因重试或恢复被重复调用时，不会重复发送邮件、重复写文件或重复更新数据库。

## 16. Transaction 与 Compensation（事务与补偿）【正常掌握】

理解多步骤任务无法使用单一数据库事务时，如何通过备份、回滚和补偿动作恢复系统状态。

## 17. Human Approval Workflow（人工审批工作流）【正常掌握】

把已经学过的 Human-in-the-Loop（人类在环）落实为可暂停、可保存、可恢复的审批流程。

------

# 第五阶段：生产级后端与基础设施

## 18. FastAPI 高级工程实践【深入掌握】

补充异步请求、依赖注入、中间件、异常处理、鉴权、流式响应、连接池和生产部署，而不只是编写普通接口。

## 19. Async / Concurrency（异步与并发）【深入掌握】

系统理解协程、线程、进程、事件循环、连接池、信号量、超时和取消，并能解释你的 AsyncLLMClient（异步大模型客户端）设计。

## 20. SSE 与 WebSocket【正常掌握】

掌握长任务如何向前端流式返回 Token、Agent 状态和工具事件，以及连接断开后的处理方式。

## 21. Task Queue（任务队列）【正常掌握】

学习如何使用 Celery、Arq 或 Dramatiq 等任务系统处理长任务、重试、定时任务和后台执行。

## 22. PostgreSQL 与 Redis【正常掌握】

PostgreSQL 负责持久状态、任务和评估数据，Redis 负责缓存、任务队列、分布式锁和临时状态。

## 23. Docker 与 Docker Compose【深入掌握】

能够把 LocalAgent 的前端、后端、数据库、模型服务和向量库进行容器化组合部署。

## 24. Kubernetes（容器编排平台）【概念到正常掌握】

掌握 Pod、Deployment、Service、ConfigMap、Secret、扩缩容和健康检查，不需要深入集群运维。

------

# 第六阶段：Observability 与 Evaluation

## 25. OpenTelemetry（开放遥测）【正常掌握】

学习 Trace（链路）、Span（跨度）、Metric（指标）和 Log（日志）的统一模型，把 `[[ORCH]]` 升级为标准化可观测事件。

## 26. Agent Trace 体系【深入掌握】

记录 Router、Planner、RAG、Tool、Agent、审批、异常和最终答案的完整执行链，支持回放和问题定位。

## 27. Evaluation Platform（评估平台）实现【深入掌握】

真正实现测试集管理、Batch Runner（批量执行器）、指标计算、版本对比和评估报告，而不是只停留在概念设计。

## 28. Grader（评分器）体系【深入掌握】

结合规则评分、程序验证、LLM-as-a-Judge（大模型裁判）和人工抽检，不同模块采用不同评估方法。

## 29. Bad Case 与 Regression（坏例与回归）【深入掌握】

把线上失败自动转成测试用例，每次修改 Prompt、Skill、Tool、Router 或 Retrieval 后运行回归测试。

## 30. Regression Gate（回归门禁）【正常掌握】

为关键指标设置发布门槛，例如路由正确率不能明显下降、安全审批遗漏必须为零。

------

# 第七阶段：高级 RAG 与 Memory

## 31. Hybrid Retrieval（混合检索）【深入掌握】

组合 FTS5 / BM25（关键词检索）与 Vector Retrieval（向量检索），解决专有名词、代码、报错和语义问题的不同召回需求。

## 32. Reranker 与 Query Rewrite【正常掌握】

学习候选结果重排、查询改写、多查询召回和检索失败恢复，提高最终上下文质量。

## 33. Chunk 与 Metadata 设计【深入掌握】

掌握不同文档类型的切片策略、父子分块、文档版本、来源、权限和时效信息。

## 34. RAG 权限与时效【正常掌握】

确保用户只能检索有权限的文档，并避免过期知识、敏感内容和恶意文档进入上下文。

## 35. Memory 分类【正常掌握】

理解 Working Memory（工作记忆）、Episodic Memory（情景记忆）、Semantic Memory（语义记忆）和 Procedural Memory（程序性记忆）。

## 36. Memory 生命周期【深入掌握】

学习记忆写入门控、压缩、去重、冲突、更新、遗忘、召回和质量评估，而不是把所有对话永久保存。

## 37. GraphRAG 与 Knowledge Graph（知识图谱）【概念了解】

了解图结构适合实体关系和多跳推理，但现阶段不应替换你已有的 FTS5 与 Chroma 主链路。

------

# 第八阶段：大模型与推理基础

## 38. Transformer 与 Self-Attention（自注意力）【正常掌握】

理解大语言模型的基本结构，以及上下文中的 Token 如何相互关联，不要求手写完整训练框架。

## 39. Tokenization 与 Embedding【深入掌握】

理解 Token、向量表示、相似度、维度和模型加载，能够解释本地 Embedding 模型为什么占用大量内存。

## 40. Context Window 与 KV Cache【正常掌握】

理解上下文长度为什么影响延迟和显存，以及 KV Cache（键值缓存）如何加速自回归生成。

## 41. Temperature、Top-p 与结构化输出【正常掌握】

理解采样参数对稳定性和创造性的影响，以及 Agent 为什么通常需要低随机性和严格 Schema。

## 42. Quantization（量化）与模型服务【正常掌握】

理解 GGUF、INT8、INT4 等量化方法对内存、速度和质量的影响，并掌握基础模型服务方式。

## 43. SFT、LoRA、RLHF、DPO、GRPO【概念了解】

知道监督微调、参数高效微调和偏好优化分别解决什么问题，能够判断什么时候应改 Prompt、RAG 或微调模型。

------

# 第九阶段：计算机与后端基础

## 44. Python 高级基础【深入掌握】

补充类型系统、装饰器、上下文管理器、生成器、异步、数据模型、异常体系、测试和性能分析。

## 45. 操作系统基础【正常掌握】

掌握进程、线程、协程、内存、锁、文件系统和进程间通信，能够分析 Agent 运行和 Sandbox 问题。

## 46. 计算机网络【正常掌握】

掌握 HTTP、TCP、连接复用、代理、TLS、SSE、WebSocket、超时和重试，与你现有的异步请求问题直接相关。

## 47. 数据库基础【正常掌握】

掌握索引、事务、隔离级别、锁、慢查询和数据建模，能够设计任务、Trace、Memory 和评估数据表。

## 48. 分布式系统基础【正常掌握】

理解一致性、可用性、消息重复、分布式锁、幂等、任务队列、服务发现和故障恢复。

## 49. 数据结构与算法【持续掌握】

继续完成 Hot 100（热门算法题集），重点保持数组、链表、树、图、堆、二分、动态规划和并发基础题的熟练度。

------

# 第十阶段：系统设计与项目升级

## 50. Agent System Design（智能体系统设计）【深入掌握】

练习企业知识库 Agent、Coding Agent（编码智能体）、数据分析 Agent、多租户 Agent 平台和 Skill 市场等系统设计题。

## 51. LocalAgent Runtime 重构【项目实践】

统一 AgentConfig、RunContext、AgentMessage、AgentResult、TaskState 和 Budget，形成明确的 Harness 运行层。

## 52. Skill Center（技能中心）【项目实践】

先把 Excel 处理、代码审查或 AW 脚本生成中的一个流程改造成独立 Skill，再逐步扩展注册、加载和评估能力。

## 53. MCP 与 A2A Gateway（协议网关）【项目实践】

实现至少一个 MCP Server、一个 MCP Client 和一个最小 A2A 通信流程。

## 54. Sandbox 与 Durable Task【项目实践】

让代码或文件工具在隔离环境运行，并支持任务暂停、Checkpoint 和恢复。

## 55. Evaluation 与 Observability【项目实践】

把现有 `[[ORCH]]`、测试集和 Bad Case 体系整合成可查询、可对比的评估与监控模块。

## 56. 部署版本【项目实践】

使用 Docker Compose 部署 LocalAgent、数据库、Redis、向量库和模型服务，形成可演示的完整环境。

------

# 第十一阶段：面试表达与准备

## 57. 项目故事整理【深入掌握】

围绕“为什么这样设计、遇到了什么问题、如何定位、如何权衡、指标如何变化”讲项目，而不是只罗列功能。

## 58. 架构图与核心流程图【深入掌握】

准备系统架构图、Agent 请求时序图、Tool 调用图、RAG 流程图和评估闭环图。

## 59. 高频追问题库【深入掌握】

整理 Harness、Skill、MCP、A2A、Sandbox、RAG、Memory、Evaluation、并发和系统设计的追问题。

## 60. Coding 与 System Design 模拟【持续掌握】

保持 Python 编码题训练，同时进行 Agent 系统设计、故障分析和项目深挖模拟。

## 61. 简历与岗位匹配【深入掌握】

根据岗位类型区分 Agent 应用开发、Agent 平台开发、RAG 工程和大模型后端，调整项目重点和关键词。

------

# 推荐的整体学习顺序

```text
Agent Harness / Runtime
→ Skill / Tool 系统
→ MCP
→ Sandbox / Durable Execution
→ 生产级后端
→ Evaluation / Observability
→ 高级 RAG / Memory
→ LLM 基础
→ A2A 与其他协议
→ 系统设计
→ 项目包装和模拟面试。
```

# 最核心的项目实施顺序

```text
第一步：把一个现有业务流程改造成 Skill。

第二步：统一 LocalAgent Runtime 和任务状态。

第三步：实现 MCP Client / Server。

第四步：增加 Sandbox 和 Checkpoint / Resume。

第五步：真正完成评估 Runner 和回归报告。

第六步：容器化部署并准备系统设计与面试材料。
```