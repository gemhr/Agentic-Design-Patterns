已收到并核验 `42_phase_final_gate_re_review.md`。

根据最终 Gate 结果：

```text
PHASE0_FINAL_GATE = PASS
```

Stage5-Phase0-WP2 正式关闭。

按照之前约定：

> 每完成一个 WP 后必须停下来询问：进行本 WP 的学习/面试总结，还是直接进入下一步？

当前进入学习阶段。

------

# Stage5-Phase0-WP2 学习 / 面试总结

## WP2 一句话项目定义

本 WP 实现了一个：

> **RAG Evaluation Bridge（RAG 评估桥接层）**

将 LocalAgent 一次真实 Retrieval Execution（检索执行）产生的运行事实转换为可持久化的 Evaluation Artifact（评估证据），并由 AgentEvalOps 消费，为后续自动评估指标提供输入。

当前真实完成：

```text
LocalAgent
=
RAG execution fact producer

AgentEvalOps
=
evaluation evidence consumer
```

不是完整 Evaluation Platform。



------

# 1. 为什么需要 WP2？

## 原始问题

之前：

```text
User Query
    |
LocalAgent Runtime
    |
Retrieval
    |
Answer
```

虽然 Runtime 能运行，但缺少：

- 这次检索用了什么 query？
- rewrite 后是什么？
- 检索召回了哪些候选？
- rerank 后顺序如何？
- 最终选择哪些 chunk？
- citation 来自哪里？
- latency 如何？

因此无法回答：

> 为什么这次 RAG 效果不好？

也无法支持：

- Recall@K；
- MRR；
- NDCG；
- Citation Accuracy。

------

# 2. 最大设计原则：事实所有权

这是 WP2 最核心面试点。

## 错误设计

很多系统会：

```
Evaluation Platform
        |
        |
重新调用 Retriever
        |
        |
计算指标
```

问题：

一次执行：

```
线上 Retrieval
```

和：

```
评估 Retrieval
```

可能不是同一次。

导致：

- embedding 不同；
- 数据库状态不同；
- rerank 不同；
- query rewrite 不同。

最终：

评估的不是线上事实。

------

## WP2 设计

采用：

```
LocalAgent
      |
      |
Original Retrieval Execution
      |
      |
Artifact Snapshot
      |
      |
AgentEvalOps
```

即：

> 谁执行，谁产生事实。

------

面试表达：

> 我没有让 Evaluation 平台重新执行 RAG，而是在 Retrieval Runtime 内增加 evaluation sidecar，在原执行链路产生不可变 evidence snapshot，然后由评估平台消费。

这是非常典型的生产级设计。

------

# 3. 为什么不用修改 RetrievalExecutionResult？

这是一个非常好的架构问题。

## 直觉方案

直接增加：

```python
RetrievalExecutionResult:

    retrieved_documents
    ranked_documents
    query
    citations
```

看起来简单。

------

## 问题

Runtime Result 是：

```
Execution Contract
```

而 Evaluation Artifact 是：

```
Evaluation Contract
```

两个生命周期不同。

如果混合：

后果：

```
Runtime
 |
 |
Evaluation fields
 |
 |
Trace
 |
 |
Persistence
```

污染核心执行模型。

------

所以：

最终：

```
RetrievalExecutionResult
        |
        |
unchanged

RetrievalEvaluationSnapshot
        |
        |
evaluation only
```

------

面试关键词：

- Contract Isolation（合同隔离）
- Single Responsibility（单一职责）
- Sidecar Pattern（旁车模式）

------

# 4. 为什么 Artifact 是 RetrievalInvocation，而不是 Run？

这是 WP2 一个非常容易被追问的问题。

错误：

```
Run Artifact
```

例如：

```
Run001
 |
 |
all retrieval merged
```

问题：

一个 Agent Run 可能：

```
Query
 |
Planner
 |
Agent A retrieval
 |
Agent B retrieval
 |
Tool
 |
Agent C retrieval
```

多个 Retrieval。

如果合并：

无法知道：

- 哪次 retrieval 失败；
- 哪次 query rewrite；
- 哪个 agent 调用。

------

正确：

```
Run

 ├── RetrievalInvocation 1
 |
 ├── RetrievalInvocation 2
 |
 └── RetrievalInvocation 3
```

所以：

```
1 Run
→
0..N RetrievalArtifact
```

------

# 5. retrieved / ranked / selected 三层为什么重要？

这是 RAG Evaluation 基础。

很多简单实现：

```
vector search result
       |
       |
selected context
```

直接保存。

问题：

丢失中间过程。

------

WP2：

## retrieved_items

表示：

```
召回阶段
```

回答：

> 系统找到了什么？

用于：

Recall@K。

------

## ranked_items

表示：

```
rerank阶段
```

回答：

> 系统认为哪些更相关？

用于：

MRR/NDCG。

------

## selected_items

表示：

```
最终进入 Context 的内容
```

回答：

> 最终给 LLM 看了什么？

用于：

Groundedness / Citation。

------

关系：

```
selected
   ⊆
ranked
   ⊆
retrieved
```

------

# 6. 为什么不能通过 score 推断 channel？

这是一个典型 Bad Case。

错误：

```python
if score == 0.55:
    channel="keyword"
```

原因：

score 是结果：

```
effect
```

不是原因：

```
cause
```

例如：

```
vector score
=
0.55
```

并不能说明：

来自：

- keyword；
- vector；
- rerank。

正确：

在 retrieval adapter 执行阶段记录：

```
provenance（来源）
```

然后 artifact 保存。

------

# 7. Runtime Status 和 Capture Status 为什么分开？

这是生产系统非常重要的思想。

两个状态：

## Runtime

表示：

> 业务执行怎么样？

例如：

```
SUCCESS
FAILED
TIMEOUT
```

------

## Capture

表示：

> 评估证据保存怎么样？

例如：

```
COMPLETE
PARTIAL
FAILED
```

------

可能：

```
Runtime SUCCESS
Capture FAILED
```

例如：

```
Agent回答成功

但是artifact超过1MB无法保存
```

如果混合：

```
Runtime FAILED
```

就是错误。

------

最终：

```
Execution Truth
+
Evaluation Evidence Truth
```

分离。



------

# 8. 为什么不做 Artifact Store？

这是一个很好的系统设计取舍。

直觉：

建立：

```
artifact table
artifact service
artifact storage
```

长期保存。

------

问题：

WP2 当前目标：

```
让 Evaluation 可以拿到 evidence
```

不是：

```
建设新的数据平台
```

增加 Artifact Store 会引入：

- schema；
- retention；
- migration；
- lifecycle；
- consistency。

------

所以当前：

```
EvidenceRef.metadata
```

足够。

未来如果：

- 大规模 artifact；
- 大文件；
- 多版本；
- 查询需求；

再演进。

------

# 9. AC10 为什么重要？

前面的测试：

Producer：

证明：

```
LocalAgent 正确生成 artifact
```

Consumer：

证明：

```
AgentEvalOps 正确解析保存
```

但是：

缺少：

```
A → B
```

真实链路。

AC10：

验证：

```
LocalAgent
 |
HTTP
 |
AgentEvalOps
 |
PostgreSQL
 |
Reload
```

才证明：

系统闭环。



------

# 面试问题模拟

## Q1：你为什么不用 LangChain/LangSmith 做 Evaluation？

回答：

> 我们的场景更关注自研 Agent Runtime 内部行为，比如 Planner、Tool、Retrieval、Execution 状态，因此需要拿到 Runtime 内真实产生的中间事实。外部 Evaluation 平台通常只能看到输入输出，无法保证 retrieval execution 过程一致，所以设计了 Runtime sidecar capture，把事实导出给 Evaluation 系统。

------

## Q2：为什么 Artifact 不直接存数据库？

回答：

> 当前阶段主要解决 Evaluation 输入标准化问题，而不是建设 Artifact 平台。如果过早引入独立存储，会增加生命周期管理和一致性问题。因此先复用已有 EvidenceRef 机制保存 bounded metadata，未来当 artifact 规模和查询需求增长后再独立演进。

------

## Q3：如果 Retrieval 改了一版，怎么知道历史评估对应哪个版本？

当前真实状态：

> WP2 尚未实现版本归因，这是后续阶段规划。

不要说已经实现。

后续：

```
rag_pipeline_version
embedding_model
retriever_config_hash
kb_snapshot_id
```

属于后续。

------

# 本 WP 推荐面试材料文件名

按照你的规范：

```text
docs/interview_materials/stage5_phase0_wp2_rag_evaluation_bridge.md
```

建议内容：

```
1. 一句话项目定义

2. 为什么需要 Evaluation Artifact

3. 原架构问题

4. Owner Boundary

5. RetrievalInvocation Artifact设计

6. retrieved/ranked/selected 三层模型

7. Runtime/Capture状态分离

8. EvidenceRef持久化方案

9. AC10跨仓验证

10. Trade-off

11. Bad Case

12. 后续演进方向
```

------

# 当前学习节点结束

WP2 已完成学习总结。

下一步根据你的长期规则：

**进行本 WP 的学习/面试总结，还是直接进入下一步？**

（如果选择下一步，将进入 Stage5-Phase1 规划/开发。）