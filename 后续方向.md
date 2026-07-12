# 一、执行口径

后续按照你定义的 **阶段 0 → 阶段 7** 顺序推进，不跳阶段，不新增第三个大型项目。

这里将你所说的“第一阶段”解释为编号中的 **阶段 1：Python、后端和大模型基础**。不过，在正式进入阶段 1 前，必须先用约 3～5 天完成阶段 0 的基线整理，否则后续项目改造很难证明“改造前后有什么变化”。

当前官方岗位要求也支持这条路线：

- 腾讯近期 Agent 岗位明确要求扎实的 Python、`asyncio`（异步 I/O）和并发处理能力。
- 字节跳动 Agent 后端岗位强调 Python、FastAPI 等 Web 框架及微服务工程能力。
- 腾讯另一个 Agent 平台岗位直接提到评测体系、测试 Harness（执行支架）、Trace/Replay（追踪/回放）和 Bad Case（失败案例）分析平台经验。

因此，你现在最缺的不是继续学习更多 Agent 模式，而是把已有 Agent 能力建立在可靠的 Python、后端和运行时基础上。citeturn133397search1turn133397search2turn133397search3

---

# 二、长期学习进度表

下面的完成度是根据你目前“理论理解、工程实现、面试表达”三方面综合估算，不代表简单的课程观看比例。

| 阶段                       | 核心目标                                         |              当前状态 |    预计学习周期 | 阶段结束标志                                                |
| -------------------------- | ------------------------------------------------ | --------------------: | --------------: | ----------------------------------------------------------- |
| 阶段 0：项目基线           | 固化现状、边界和初始指标                         |      部分完成，约 25% |         3～5 天 | 架构图、时序图、模块清单、指标基线、PandaProbe 改造边界完成 |
| 阶段 1：基础工程           | 补齐 Python、后端、SQL、异步任务和大模型推理基础 |      部分完成，约 35% |         6～7 周 | 能独立实现和解释可靠的异步 FastAPI 服务及任务链路           |
| 阶段 2：Harness 与 Runtime | 建立统一 Agent 执行内核                          |      部分完成，约 20% |         4～5 周 | LocalAgent 具备 RunContext、状态机、预算、取消、重试和追踪  |
| 阶段 3：Tool、Skill、安全  | 建立标准化能力加载与受控执行体系                 |      部分完成，约 25% |         4～5 周 | Tool Registry、Skill、MCP、审批和 Sandbox 主链路完成        |
| 阶段 4：高级 RAG 与 Memory | 从“能检索”升级到“可评估、可治理”                 |      部分完成，约 35% |         3～4 周 | 混合检索、重排、引用、权限过滤和记忆策略完成                |
| 阶段 5：Evaluation         | 建成 AgentEvalOps 第一版                         | 理论约 25%，工程约 0% |         4～5 周 | Regression Report 和 Release Gate 完成                      |
| 阶段 6：生产化与系统设计   | 掌握可靠任务、分布式恢复和部署                   |  尚未系统开始，约 10% |         3～4 周 | 能完成五类重点系统设计题并解释可靠性方案                    |
| 阶段 7：算法与面试         | 将知识转化为稳定面试表现                         |      部分完成，约 20% | 4～6 周集中训练 | 项目深挖、编码、系统设计和模拟面试通过                      |

按照每周约 12～15 小时计算，完整路线大约需要 **28～34 周**。但不是学完全部内容才投递：

- **第一条试投递线**：完成阶段 0～2，LocalAgent Runtime 核心链路成型。
- **主要投递线**：完成阶段 0～5，两个项目形成完整差异化。
- **稳定面试线**：完成阶段 6～7，并进行多轮模拟面试。

阶段 7 在正式顺序上放在最后；已有 LeetCode（力扣）训练可以每周少量保温，但当前不单独展开新知识。

---

# 三、当前能力盘点

## 1. 已完成能力

这里的“已完成”指已经具备系统认知或可运行实现，不代表全部达到生产级。

| 能力                     | 当前证据                                                | 结论               |
| ------------------------ | ------------------------------------------------------- | ------------------ |
| Agent 设计模式           | 已系统完成四部分模式学习                                | 已完成，不再从头讲 |
| 多 Agent 基础编排        | Router、Planner、专业 Agent、并行和 Reflection 已有实践 | 已完成基础层       |
| Tool Use（工具使用）     | 已有文件、Excel、CSV 和系统工具                         | 已完成基础层       |
| 基础 RAG（检索增强生成） | Chroma、Embedding、文档解析和知识库                     | 已完成基础链路     |
| 基础 Memory（记忆）      | SQLite、FTS5、滚动摘要和会话检索                        | 已完成基础链路     |
| 本地与远程模型接入       | llama.cpp、GGUF、OpenAI 兼容 API                        | 已完成             |
| Agent 模型档位           | fast、balanced、deep                                    | 已完成雏形         |
| 基础可观测事件           | 已有 `[[ORCH]]` 编排事件                                | 已完成雏形         |
| 自动化与质量保障能力     | 数据处理、测试工具、问题定位经验                        | 已具备明显职业优势 |
| Evaluation 概念体系      | 指标、Bad Case、回归和发布门禁已有系统认知              | 理论基础已完成     |

## 2. 部分完成能力

| 能力                     | 已具备                                         | 主要缺口                                                 |
| ------------------------ | ---------------------------------------------- | -------------------------------------------------------- |
| `asyncio`（异步 I/O）    | AsyncClient、Semaphore（信号量）、并发调用实践 | TaskGroup、取消传播、超时嵌套、资源清理和异常组          |
| Python 工程能力          | 能写实际工具和后端代码                         | 类型抽象、异常分层、测试隔离、并发边界                   |
| FastAPI                  | 已有后端和流式接口                             | 生命周期、依赖边界、中间件、错误契约、断连取消、生产部署 |
| SQL                      | SQLite 实践较多                                | 索引设计、事务异常、隔离级别、迁移和并发写入             |
| Redis                    | 理论上知道用途                                 | 数据结构、缓存策略、分布式状态和消息语义                 |
| Celery（分布式任务队列） | PandaProbe 中已有现成能力                      | 自己解释 Worker、Broker、ACK、重试和幂等                 |
| 大模型基础               | 能使用模型、Embedding 和量化模型               | Attention、Prefill/Decode、KV Cache、Batch 的内部原理    |
| Runtime                  | 已有 Router、Planner、Profile 和事件           | 缺少统一执行循环、上下文、状态机和生命周期               |
| Guardrails（安全护栏）   | 已学模式                                       | 尚未形成统一策略和强制执行层                             |
| MCP（模型上下文协议）    | 已系统学习概念                                 | 尚未形成生产接入、权限与错误处理实践                     |
| RAG / Memory 评估        | 已了解部分指标                                 | 未建立自动化评测集和完整优化闭环                         |
| 项目面试表达             | 功能丰富                                       | 缺少量化指标、决策权衡和故障案例故事                     |

## 3. 尚未开始或尚未形成体系的能力

主要包括：

- 正式的 Agent Harness（智能体执行支架）和 Agent Runtime（智能体运行时）。
- Checkpoint（检查点）、Resume（恢复）、Durable Execution（持久化执行）。
- 端到端 Idempotency（幂等性）设计。
- Agent Skill（智能体技能）规范及加载体系。
- A2A（智能体间协议）工程实践。
- Sandbox（沙箱）和进程、文件、网络隔离。
- AgentEvalOps 的实际开发。
- PostgreSQL、Redis、Celery 组成的完整生产后端实践。
- Docker 化、自动化测试流水线和正式数据库迁移。
- 生产级系统设计题的结构化回答。
- 双项目的完整面试证据链。

---

# 四、阶段 0：进入第一阶段前的基线任务

阶段 0 不做大规模重构，只记录现状。

## 必须产出

### LocalAgent

1. 当前组件架构图。
2. 一次用户请求的执行时序图。
3. 模块边界表：
   - 前端
   - API
   - Router
   - Planner
   - Agent
   - Tool
   - RAG
   - Memory
   - Model Adapter
   - Event / Logging
4. 当前状态保存位置：
   - 内存状态
   - SQLite
   - Chroma
   - 文件
5. 当前错误分类：
   - 模型错误
   - 工具错误
   - 检索错误
   - 路由错误
   - 解析错误
   - 超时错误
   - 用户取消
6. 至少记录 10～20 个代表性请求的基础数据：
   - 总耗时
   - 首 Token 时间
   - 模型调用次数
   - 工具调用次数
   - 检索次数
   - 成功或失败
   - 最终错误类型

### AgentEvalOps

只分析 PandaProbe 原有能力，不开始大规模开发：

1. 原项目模块图。
2. Trace、Span、Session、Evaluation Run 等现有数据模型关系。
3. Redis 和 Celery 的使用位置。
4. 原有 API、Worker、数据库和 Dashboard 边界。
5. “PandaProbe 原有能力”和“我的新增能力”对照表。
6. 明确第一版不做的功能。

阶段 0 完成后，后续每次改造才能回答：

> 原系统是什么状态？我解决了什么问题？通过什么指标证明改造有效？

---

# 五、阶段 1 详细学习安排

默认安排为 **7 周，每周 12～15 小时**。不建议压缩成纯理论速成，因为阶段 1 是后续 Runtime、Evaluation 和系统设计的地基。

## 第 1 周：`asyncio` 与结构化并发

### 必须掌握

- Event Loop（事件循环）
- Coroutine（协程）
- Task（任务）
- Future（未来结果）
- `await` 的暂停和恢复
- `create_task`
- `gather`
- TaskGroup（任务组）
- Semaphore
- Timeout（超时）
- Cancellation（取消）
- 异步生成器
- 异步上下文管理器
- 阻塞 I/O 对事件循环的影响

### 核心学习重点

不是背 API，而是回答：

1. 协程对象什么时候真正开始执行？
2. Task 和 Coroutine 有什么区别？
3. `gather` 中一个任务失败后，其他任务会怎样？
4. TaskGroup 为什么属于 Structured Concurrency（结构化并发）？
5. 请求断开后，底层模型和工具任务怎样被取消？
6. 为什么不能随便吞掉 `CancelledError`？
7. 超时为什么本质上通常依赖取消实现？

Python 当前官方文档说明：TaskGroup 中一个任务异常时会取消同组其他任务，并最终通过 ExceptionGroup（异常组）汇总异常；协程处理取消时应通过 `try/finally` 清理资源，并通常继续传播 `CancelledError`。citeturn182900view0

### 实践任务

在 LocalAgent 内建立一个隔离的并发实验模块，不直接重构主流程：

- 模拟三个 Agent 并行执行。
- 限制最大并发数。
- 任一关键任务失败时取消其他任务。
- 支持整体超时。
- 支持外部用户取消。
- 确保 HTTP 客户端正常关闭。
- 记录每个 Task 的开始、结束、取消和异常。

### 验收

能够现场写出一个带以下能力的异步执行器：

- 并发限制
- 整体超时
- 单任务异常
- 取消传播
- 资源清理
- 单元测试

---

## 第 2 周：Python 工程能力、线程进程和测试

### 必须掌握

- 类型标注
- `dataclass`
- `Enum`
- `Protocol`
- 泛型的基础使用
- 领域异常与基础设施异常
- `pytest`
- Fixture（测试夹具）
- Mock（模拟对象）
- Monkeypatch（运行时替换）
- 参数化测试
- 日志捕获
- 线程与进程
- I/O 密集与 CPU 密集
- GIL（全局解释器锁）

### 需要理解

- `TypedDict`、Pydantic Model 和普通类的边界。
- `Protocol` 与抽象基类的区别。
- 线程池适合什么任务。
- 进程池为什么有序列化和启动成本。
- 为什么异步不等于并行。
- 为什么 Mock 需要替换“被调用模块所引用的名字”。

pytest 官方文档强调 Fixture 用于提供可靠且一致的测试上下文，Monkeypatch 可安全替换属性、环境变量和字典项，并会在测试结束后恢复。citeturn256885search0turn256885search18

### 实践任务

建立统一异常模型，例如概念上区分：

- `UserInputError`
- `ModelInvocationError`
- `ToolExecutionError`
- `RetrievalError`
- `InfrastructureError`
- `TimeoutError`
- `CancelledRunError`

同时为阶段 1 第 1 周的异步执行器补充：

- 成功测试
- 超时测试
- 取消测试
- 部分失败测试
- 并发上限测试
- Mock 模型客户端测试

---

## 第 3 周：HTTP、SSE、WebSocket 与 FastAPI

### 必须掌握

- HTTP 方法语义
- 状态码
- Header
- 请求和响应生命周期
- REST（表述性状态转移）
- SSE（服务器发送事件）
- 客户端断开检测
- FastAPI 依赖注入
- Lifespan（生命周期）
- Middleware（中间件）
- 统一错误响应
- Request ID（请求标识）
- Trace ID（追踪标识）
- 同步函数与异步函数边界

FastAPI 对普通 `def` 路由和依赖会通过外部线程池执行，而直接调用的普通工具函数不会自动进入线程池；因此“路由写成 async”并不能自动解决内部阻塞问题。citeturn546143view1

### 需要理解

- SSE 与 WebSocket 的选择。
- 反向代理缓冲对流式输出的影响。
- 客户端断开后继续生成的资源浪费。
- 为什么 API 层不能直接承担全部业务编排。
- FastAPI `BackgroundTasks` 与分布式任务队列的边界。

FastAPI 官方建议小型、同进程的后台操作使用 `BackgroundTasks`；重计算或需要跨进程、跨服务器执行的任务更适合 Celery 等任务系统。citeturn546143view0

### LocalAgent 落地

本周只改后端基础设施，不进入完整 Runtime：

- 统一 API 错误结构。
- 增加 Request ID / Trace ID。
- 整理应用启动和关闭逻辑。
- 检查模型客户端、数据库和资源是否在 Lifespan 中正确初始化和释放。
- 补充 SSE 断连与异常测试。
- 检查同步阻塞调用是否运行在事件循环线程。

FastAPI 异步接口可以通过 HTTPX 的异步客户端进行完整测试。citeturn546143view2

---

## 第 4 周：SQL、索引、事务、迁移与 Redis

### SQL 必须掌握

- 主键、唯一键和外键
- B-Tree（B 树）索引
- 联合索引
- 最左前缀
- 覆盖索引
- 部分索引
- 查询计划
- 事务
- 原子性
- 隔离级别
- 乐观并发控制
- 数据库迁移
- 连接池
- N+1 查询

### Redis 必须掌握

- String、Hash、Set、Sorted Set
- TTL（生存时间）
- 缓存穿透、击穿和雪崩
- 分布式锁的基本风险
- Pub/Sub（发布订阅）
- Streams（流）
- 缓存一致性
- 幂等键
- 任务状态缓存

PostgreSQL 当前默认隔离级别是 Read Committed（读已提交）；索引可以提升查询性能，但错误或过多的索引会增加写入和维护成本。citeturn256885search1turn256885search13turn256885search19

Redis Pub/Sub 是 At-most-once（至多一次）语义，消费者断开或处理失败后消息可能永久丢失；需要持久化、消费追踪或重放时，应考虑 Redis Streams。citeturn546143view4turn893694search11

### 实践任务

不要求阶段 1 就把 LocalAgent 全量迁移到 PostgreSQL。

需要完成：

- 为 Session、Message 或 Run 选择一张表分析现有索引。
- 写出至少三个真实查询及对应索引理由。
- 使用查询计划验证索引是否生效。
- 编写一次数据库迁移。
- 用 Redis 实现一个有 TTL 的缓存实验。
- 用 Redis 实现一个简单幂等键实验。
- 解释为什么不能使用 Pub/Sub 承担必须可靠送达的关键任务事件。

---

## 第 5 周：Celery、消息队列、可靠性与 Docker

### 必须掌握

- Producer（生产者）
- Broker（消息代理）
- Worker（工作进程）
- Result Backend（结果后端）
- ACK（确认）
- Retry（重试）
- Backoff（退避）
- Idempotency
- 软超时和硬超时
- 任务状态
- Worker 崩溃
- 重复执行
- 长短任务隔离
- 限流和熔断
- Dockerfile
- Docker Compose
- 健康检查
- 环境变量与 Secret（机密信息）
- CI/CD（持续集成与持续交付）基础

Celery 官方文档明确指出任务应尽量设计为幂等；启用 `acks_late` 后，Worker 在执行过程中崩溃可能导致任务再次执行，因此不能把消息队列理解为“天然只执行一次”。外部 I/O 也应单独设置超时，而不是只依赖强制终止任务。citeturn546143view3

### 家庭环境的 AgentEvalOps 落地

本周不新增 Evaluation 功能，只理解 PandaProbe 已有基础设施：

- 找到 Celery App 的初始化位置。
- 找到 Broker 和 Result Backend 配置。
- 追踪一个 Evaluation Run 如何进入 Worker。
- 找到任务重试、超时和状态更新逻辑。
- 判断任务是否具有幂等性。
- 为一条现有任务链补充 Smoke Test（冒烟测试）或架构说明。

### 公司环境的 LocalAgent 落地

- 建立一个最小异步任务示例。
- 明确哪些任务留在 API 进程，哪些未来需要 Worker。
- 完成开发环境 Docker Compose。
- CI 至少执行：
  - 静态检查
  - 类型检查
  - 单元测试
  - 镜像构建检查

---

## 第 6 周：大模型基础与推理链路

### 必须掌握

- Transformer（变换器）
- Self-Attention（自注意力）
- Query、Key、Value
- Tokenization（分词）
- Embedding（向量表示）
- Context Window（上下文窗口）
- Prefill（预填充）
- Decode（逐 Token 解码）
- KV Cache（键值缓存）
- Batch（批处理）
- Structured Output（结构化输出）
- Function Calling（函数调用）
- Quantization（量化）
- 模型选择与降级

### 需要理解

- Prompt Cache（提示缓存）
- Continuous Batching（连续批处理）
- SFT（监督微调）
- LoRA（低秩适配）
- DPO（直接偏好优化）
- RLHF（基于人类反馈的强化学习）

阶段 1 不要求自行训练模型，也不要求推导完整矩阵公式，但必须能解释：

1. Attention 为什么能建立 Token 间依赖？
2. Prompt 越长，Prefill 为什么越慢？
3. 输出越长，Decode 为什么成为主要耗时？
4. KV Cache 为什么能减少重复计算？
5. KV Cache 为什么会快速消耗显存？
6. 量化为什么可能降低内存，却不一定降低延迟？
7. Function Calling 为什么仍然需要参数验证？
8. Structured Output 为什么不能代替业务规则校验？

KV Cache 通过保存历史 Attention 的 Key 和 Value 避免每次生成重新计算，但主要用于推理；对 KV Cache 或模型进行量化可以降低内存占用，同时可能带来精度或延迟权衡。citeturn244311search0turn244311search7turn244311search19

### 实践任务

使用 LocalAgent 已有本地和远程模型完成一份对比实验：

| 维度             | 本地模型 | 远程模型 |
| ---------------- | -------- | -------- |
| 首 Token 延迟    | 记录     | 记录     |
| 总生成时间       | 记录     | 记录     |
| 输入 Token       | 记录     | 记录     |
| 输出 Token       | 记录     | 记录     |
| 结构化输出成功率 | 记录     | 记录     |
| 工具参数正确率   | 记录     | 记录     |
| 并发能力         | 记录     | 记录     |
| 失败与降级行为   | 记录     | 记录     |

重点不是追求模型榜单，而是形成 Model Routing（模型路由）和 Fallback（降级）设计依据。

---

## 第 7 周：整合、复盘与阶段验收

本周不继续增加新知识，完成以下工作：

1. 整理前六周代码。
2. 删除仅为演示而产生的重复实现。
3. 补测试和文档。
4. 进行一次故障注入。
5. 完成阶段 1 面试题。
6. 录制或自行演练一次 30～45 分钟技术讲解。
7. 输出阶段 1 复盘：
   - 学到了什么
   - 项目改了什么
   - 哪些指标变化
   - 哪些问题推迟到阶段 2

---

# 六、阶段 1 的掌握级别

## 必须掌握

- `asyncio`、TaskGroup、Semaphore、超时和取消。
- 线程、进程、GIL 及任务类型选择。
- 类型标注、异常分层、pytest 和 Mock。
- HTTP、SSE、FastAPI 生命周期和阻塞边界。
- SQL 索引、事务、隔离级别和迁移。
- Redis 缓存、幂等键、Pub/Sub 与 Streams 差异。
- Celery 的任务、ACK、重试、超时和重复执行。
- Docker 与基本 CI。
- Transformer 推理链路、KV Cache、量化、结构化输出和函数调用。

## 需要理解

- WebSocket 的适用场景。
- 数据库锁和较复杂的事务异常。
- 消息队列的投递语义。
- 多进程 Worker 调度。
- Prompt Cache、Batch 和推理吞吐量。
- SFT、LoRA、DPO、RLHF 的目标和差异。

## 加分项

- Python `Protocol` 和泛型设计较成熟。
- 能通过事件循环延迟定位阻塞代码。
- 能完成简单负载测试和性能剖析。
- 能解释 Celery Worker 崩溃后的实际任务行为。
- 能从模型吞吐、延迟、显存、效果和成本五个维度选择模型。

---

# 七、阶段 1 结束时应产出的代码

## LocalAgent，公司环境

1. **异步执行实验模块**
   - 并发限制
   - 超时
   - 取消
   - 异常聚合
   - 资源清理

2. **统一错误体系**
   - 领域错误
   - 基础设施错误
   - API 错误响应
   - 错误码

3. **基础可观测改造**
   - Request ID
   - Trace ID
   - 结构化日志
   - 关键耗时字段

4. **SSE 可靠性测试**
   - 正常完成
   - 模型异常
   - 工具异常
   - 客户端断开
   - 整体超时

5. **数据库工程样例**
   - 一次正式迁移
   - 索引设计
   - 查询计划分析
   - 事务测试

6. **Redis 样例**
   - TTL 缓存
   - 幂等键
   - 缓存失效

7. **测试体系**
   - 单元测试
   - 异步测试
   - Mock 模型
   - Mock 工具
   - 关键异常路径测试

8. **开发部署配置**
   - Dockerfile
   - Docker Compose
   - 环境变量模板
   - 基础 CI 配置

## AgentEvalOps，家庭环境

1. PandaProbe 启动并可稳定运行。
2. Redis、Celery、数据库和 API 链路梳理完成。
3. 一条现有 Celery 任务的调用链分析。
4. 一条现有任务的异常、重试和重复执行分析。
5. 最小 Smoke Test。
6. 不新增 Dataset、Evaluator、Regression 等阶段 5 功能。

两个环境不互相复制代码，只保持架构术语和抽象 Schema 一致。

---

# 八、阶段 1 结束时应产出的文档

至少需要以下文档：

1. `architecture-baseline.md`
   - LocalAgent 当前架构和模块边界。

2. `execution-sequence.md`
   - 一次请求的完整执行时序。

3. `pandaprobe-boundary.md`
   - 原项目能力与个人新增能力边界。

4. `asyncio-engineering-notes.md`
   - Task、TaskGroup、取消、超时和阻塞问题。

5. `error-taxonomy-v1.md`
   - 统一错误分类、错误码及是否可重试。

6. `backend-decisions.md`
   - SSE/WebSocket、API/Worker、SQLite/PostgreSQL、Pub/Sub/Streams 等关键选择。

7. `database-index-report.md`
   - 查询、索引、查询计划和事务分析。

8. `llm-inference-notes.md`
   - Prefill、Decode、KV Cache、量化和模型降级。

9. `model-selection-matrix.md`
   - 本地模型和远程模型的选型依据。

10. `stage-1-review.md`
   - 本阶段改造、指标、遗留问题和进入阶段 2 的条件。

---

# 九、阶段 1 结束时必须能回答的面试问题

不要求背定义，需要结合 LocalAgent 或 PandaProbe 回答。

## Python 与并发

1. Coroutine、Task 和 Future 有什么区别？
2. `create_task`、`gather` 和 TaskGroup 如何选择？
3. TaskGroup 中一个子任务失败会发生什么？
4. Python 异步取消是如何传播的？
5. 为什么不能吞掉 `CancelledError`？
6. 如何限制大模型接口的最大并发？
7. 异步程序中调用同步阻塞库会发生什么？
8. 线程、进程和协程分别适合什么任务？
9. GIL 会不会导致 `asyncio` 没有意义？
10. 如何测试超时、重试和取消？

## FastAPI 与后端

11. FastAPI 中 `def` 和 `async def` 的区别是什么？
12. SSE 和 WebSocket 如何选择？
13. 用户关闭页面后，如何停止模型生成？
14. 为什么不能把长任务直接放在 API 进程？
15. FastAPI BackgroundTasks 与 Celery 有什么区别？
16. 如何设计统一错误码和错误响应？
17. 如何优雅关闭 HTTP 客户端、数据库和后台任务？

## 数据库与消息任务

18. 什么情况下索引不会生效？
19. 联合索引字段顺序如何确定？
20. Read Committed 会产生什么问题？
21. 如何避免重复任务导致重复写入？
22. Celery 的 `acks_late` 解决了什么，又引入了什么？
23. Retry 和消息重新投递有什么区别？
24. Redis Pub/Sub 为什么不能用于关键任务？
25. Redis Streams 和传统消息队列有什么差异？

## 大模型基础

26. Transformer 的 Attention 在计算什么？
27. Prefill 和 Decode 有什么区别？
28. KV Cache 为什么提高生成效率？
29. 长上下文为什么会增加内存和延迟？
30. 量化为什么可能节省内存但不一定更快？
31. Structured Output 是否能保证业务数据正确？
32. Function Calling 的工具参数为什么必须再次校验？
33. 本地 7B 模型和远程大模型如何做路由与降级？
34. SFT、LoRA、DPO 和 RLHF 分别解决什么问题？

---

# 十、阶段 1 最终验收标准

只有同时满足以下标准，才进入阶段 2。

## 知识验收

- 不看资料解释完整异步调用链。
- 能画出 FastAPI 请求、SSE 输出、模型调用和取消传播时序。
- 能解释 Redis Pub/Sub、Streams 和 Celery 的可靠性区别。
- 能解释大模型一次请求从 Tokenization 到 Decode 的过程。

## 编码验收

- 45～60 分钟内实现一个受并发限制、支持超时取消的异步任务执行器。
- 所有外部 I/O 都有明确超时。
- 没有无人管理的后台 Task。
- 取消后资源能正常释放。
- 关键异常路径有自动化测试。

## 后端验收

- FastAPI 服务能通过一条命令启动。
- SSE 正常、异常、超时和断连测试通过。
- 数据库迁移可执行和回滚。
- 能通过查询计划说明索引作用。
- 重复提交同一幂等请求不会产生重复结果。
- Docker 环境可复现。
- CI 能执行测试和基础检查。

## 项目表达验收

能够用 3～5 分钟回答：

> LocalAgent 原来的异步和后端设计有什么问题？你进行了哪些改造？为什么这么改？如何验证改造有效？还有哪些能力将在 Runtime 阶段完成？

满足这些条件后，阶段 2 将正式进入 **Agent Harness、RunContext、AgentState、Agent Loop、State Machine、Budget、Retry、Checkpoint 和 Replay**，不会提前在阶段 1 中混入完整 Runtime 重构。