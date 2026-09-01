当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase6-WP2 学习 / 面试总结

## Canonical Hybrid Retrieval Integration（标准生产混合检索集成）

本 WP 推荐学习文档名：

```text
docs/interview/stage5_phase6_wp2_canonical_hybrid_retrieval_integration.md
```

这个命名最贴合真实完成边界：WP1 解决的是 `Production Retrieval Contract & Provenance`，WP2 才真正把 Hybrid Retrieval（混合检索）接入 canonical runtime，但此时 **Hybrid 还不是默认策略**。

------

# 1. 本 WP 解决了什么问题

WP1 结束后，我们已经能证明：

```text
Dense Index
和
BM25 Index

来自：
同一 corpus
同一 chunk policy
同一 ordered chunk manifest
同一 generation
```

但这只能说明：

> **两个索引可以安全融合。**

还不能说明：

> **生产请求真的会执行 Dense + BM25 → RRF。**

WP2 解决的就是第二个问题。

它把已经通过 provenance 校验的 Dense 和 BM25 接入 LocalAgent 的 canonical production runtime：

```text
User Request
      ↓
knowledge_expert
      ↓
RetrievalExecutionService
      ↓
Dense Retrieval
+
BM25 Retrieval
      ↓
RRF Fusion
      ↓
Context / Citation
      ↓
Model
```

最终状态已经从 WP1 的：

```text
HYBRID_PRODUCTION_PRECONDITIONS_READY = YES
HYBRID_PRODUCTION_REACHABLE = NO
```

推进为：

```text
HYBRID_PRODUCTION_REACHABLE = YES
HYBRID_PRODUCTION_DEFAULT = NO
```

也就是说 Hybrid 已经是真实生产可达能力，但是否替代现有 Baseline 仍然要等 WP3 的 Evaluation 证据。Final Gate 最终为 `PASS_WITH_ACCEPTED_LIMITATIONS`，P0/P1/P2 均归零。

------

# 2. 当前真实生产架构

WP2 完成后的 canonical Hybrid 路径可以概括为：

```text
server.py::lifespan
        ↓
读取 active generation
        ↓
验证 Dense / BM25 provenance
        ↓
generation-specific VectorDBManager
+
application-scoped Bm25SparseIndex
        ↓
AgentRouter
        ↓
RetrievalExecutionService
        ↓
HybridKnowledgeRetrievalAdapter
        ↓
Query Rewrite
        ↓
Dense rewritten/original retrieval
        ↓
merge → ONE Dense channel
        │
        ├─────────┐
        ↓         ↓
     Dense      BM25
      top8       top8
        │         │
        └────┬────┘
             ↓
     HybridRrfRetriever
             ↓
        RRF fused rank
             ↓
       top rag_top_k
             ↓
Dense-authoritative materialization
             ↓
RetrievalContextChunk
             ↓
ContextItem(RAG_DOCUMENT)
             ↓
ContextBuilder
             ↓
Model Context
```

这条链路已经被 Final Gate 从 `server.py::lifespan()` 一直重新追踪到 `ContextBuilder`，确认是真实 canonical production path，而不是单独测试脚本里的 Hybrid。

------

# 3. 为什么 Hybrid 不直接修改原来的 Baseline Adapter

原来的生产路径是：

```text
RuntimeKnowledgeRetrievalAdapter
```

它负责：

```text
Dense
+
Chroma keyword supplement
+
heuristic rerank
```

WP2 没有在这个类里面不断加：

```text
if strategy == HYBRID:
    ...
else:
    ...
```

而是新增独立的：

```text
HybridKnowledgeRetrievalAdapter
```

然后在 Composition Root（组合根）阶段根据 strategy 选择。

因此形成：

```text
BASELINE
→ RuntimeKnowledgeRetrievalAdapter

HYBRID_RRF
→ HybridKnowledgeRetrievalAdapter
```

这个设计的核心价值是 **Strategy Isolation（策略隔离）**。

如果所有行为都塞进一个 adapter：

```text
rewrite
dense
keyword
bm25
rrf
heuristic rerank
filter
```

以后每改 Hybrid 都容易意外影响 Baseline。

而现在 Final Gate 已经确认 Baseline 仍保持原来的：

```text
Dense
+ Chroma $contains
→ merge
→ heuristic rerank
→ rag_min_score
```

并且不会执行 BM25 或 RRF。

------

# 4. rewritten query 和 original query 为什么只算一个 Dense Channel

这是 WP2 一个很值得面试讲的设计点。

生产系统本来就会执行：

```text
rewritten query
+
original query
```

如果把它们直接当作两个 RRF channel，再加 BM25：

```text
Dense rewritten
Dense original
BM25
```

那就变成三通道 RRF。

但 query rewrite 本质是：

> 对同一种 Dense retrieval modality（检索模态）做 Query Expansion（查询扩展）。

它并不是新的 retrieval modality。

因此 WP2 冻结：

```text
Dense(rewritten)
+
Dense(original)
      ↓
merge / dedup
      ↓
continuous rank
      ↓
ONE Dense Channel
```

然后再：

```text
Dense Channel
+
BM25 Channel
→ RRF
```

这样既保持原生产 Query Rewrite 行为，又不把“查询改写”错误建模成第三种检索算法。

Final Gate 也验证：

- rewrite 不同 → 两次 Dense；
- rewrite 相同或 degradation → 一次 Dense；
- 最后 merge 成一个连续 `1..N` 的 Dense channel。

------

# 5. 为什么 Hybrid 下禁用 Chroma Keyword Supplement

Baseline 原本还有：

```text
Chroma $contains
```

做 keyword supplement。

如果 Hybrid 继续保留，就变成：

```text
Dense
+
Chroma keyword
+
BM25
```

这里会产生一个问题：

> Chroma keyword 和 BM25 都属于 lexical / sparse-ish retrieval，但两者排序语义完全不同。

这样 RRF 到底是在融合两路，还是三路？

而当前 `HybridRrfRetriever` 本身就是固定双通道：

```text
Dense
+
BM25
```

所以 WP2 最终明确：

```text
BASELINE:
Dense + Chroma keyword

HYBRID_RRF:
Dense + BM25
```

Hybrid adapter 的 `should_keyword_retrieve()` 恒为 False。

这样 production Hybrid 的定义非常清晰：

> **Dense = semantic retrieval，BM25 = lexical retrieval，RRF = rank fusion。**

------

# 6. RRF 为什么不能直接复用 rag_min_score

这是 Scout 阶段发现的一个非常好的真实 Bad Case。

Baseline 使用：

```text
rag_min_score ≈ 0.55
```

Dense relevance score 通常是 `[0,1]` 范围。

但 RRF 使用：

```text
score =
Σ 1 / (k + rank)
```

当前：

```text
RRF_K = 60
```

双通道最佳情况大约只有：

```text
2 / 61 ≈ 0.0328
```

如果直接继续执行：

```text
score >= 0.55
```

那么：

```text
0.0328 < 0.55
```

所有 Hybrid candidate 都会被过滤掉。

因此 WP2 明确区分：

```text
BASELINE
→ score-based filtering

HYBRID_RRF
→ rank-based selection
```

Hybrid 最终：

```text
RRF fused rank
→ top rag_top_k
```

不对 raw RRF score 使用 absolute relevance threshold。

Final Gate 专门验证了合法的低 RRF score 不会再被 `rag_min_score` 删除。

这是面试中很好的回答：

> **不同 ranking algorithm 的 score space 不一定可比较，所以不要机械复用同一个 threshold。**

------

# 7. Candidate Budget 如何设计

当前 Hybrid 的预算被冻结为：

| 阶段                 | Budget                    |
| -------------------- | ------------------------- |
| Dense 每次 query     | 8                         |
| merged Dense channel | 8                         |
| BM25                 | 8                         |
| RRF 每 channel       | 8                         |
| RRF union            | 16                        |
| RRF fused output     | 8                         |
| 最终 context         | `rag_top_k`，当前一般 3/4 |

这里有一个 Final Gate 真正发现的 P1。

原来的 Router 仍然使用：

```text
max(rag_top_k * 2, 8)
```

如果：

```text
rag_top_k = 8
```

就会得到：

```text
16
```

这已经违反 Hybrid 固定 channel budget 8。

Final Gate 最终在 Router 构造和 invocation 两处都做了 Hybrid cap。

这个 Bad Case 很适合说明：

> **已有通用预算公式不一定自动满足新策略的局部 invariant。**

------

# 8. 为什么 Dense 和 BM25 选择串行执行

理论上：

```text
Dense Search
BM25 Search
```

可以并发。

但 WP2 最终选择：

```text
SERIAL
```

原因不是不会写并发，而是工程取舍。

当前事实是：

```text
Dense
→ blocking executor
→ VectorDBManager lock

BM25
→ immutable in-memory index
→ no disk I/O
→ execution very cheap
```

如果为了 BM25 那一点 latency 做并发，需要同时引入：

```text
two blocking tasks
parallel cancellation
parallel timeout
budget atomicity
error aggregation
```

系统复杂度明显提升。

因此：

> **当短任务的并发收益不足以抵消 cancellation / timeout / observability contract 的复杂度时，串行是合理设计。**

这比回答“并发一定快，所以应该并发”更成熟。

------

# 9. BM25 Index 为什么必须 Application-scoped

WP1 startup 已经加载并验证了：

```text
ProductionBm25Artifact
```

如果 WP2 query 时再：

```text
open bm25_index.json
→ load
→ search
```

等于同一 artifact 被反复加载。

WP2 最终把：

```text
Bm25SparseIndex
```

作为 application-scoped immutable dependency 保存。

所以生命周期是：

```text
startup
↓
load + validate once
↓
ApplicationRuntimeServices
↓
Hybrid adapter
↓
request 1
request 2
request 3
...
```

请求阶段只做：

```text
index.search()
```

不做磁盘 load。

Final Gate 已经确认 Router/query path 不访问 artifact path，也不 per-request reload。

这涉及一个通用原则：

> **Validated dependency 应该尽可能被直接复用，而不是验证完丢弃，然后消费阶段重新加载。**

------

# 10. BM25-only winner 为什么还要去 Dense Lookup

假设 RRF 的结果：

```text
Dense Top8
BM25 Top8
```

里面某个 chunk：

```text
只在 BM25 Top8
不在 Dense Top8
```

但它经过 RRF 后仍可能进入 fused ranking。

这叫：

```text
BM25-only winner
```

BM25 artifact 中虽然有：

```text
document_id
chunk_id
text
source
content_hash
```

但 citation 需要的 metadata 可能还有：

```text
page
title
section
canonical URI
display name
```

如果直接拿 BM25 metadata 补：

```text
page = ?
title = ?
```

就是在**编造事实**。

所以 WP2 的设计是：

```text
BM25-only fused identity
(document_id, chunk_id)
        ↓
active Dense generation
        ↓
exact lookup
        ↓
verify document_id + chunk_id
        ↓
获得完整正文 + SourceMetadata
```

然后 citation 仍然使用 Dense/Chroma 作为 authority。

Final Gate 还发现首次实现使用了 Chroma private `_collection` API，随后 fix-forward 为公开 `vector_store.get()`。

这体现了两个设计原则：

```text
Ranking Authority
≠
Metadata Authority
```

以及：

```text
不要为了省一次 lookup 而伪造 citation metadata
```

------

# 11. 为什么 RRF 继续复用 RERANK Stage

从概念上说：

```text
RRF = Fusion
```

并不是：

```text
Rerank
```

所以最“漂亮”的设计可能是新增：

```text
RetrievalStage.FUSE
```

但这样会影响：

```text
stage enum
events
metrics
timeouts
error contract
tests
docs
```

WP2 最终没有为了术语纯洁性扩大公共 Contract，而是：

```text
RERANK
```

作为 execution slot。

但 observability 里明确：

```text
strategy = HYBRID_RRF
algorithm = RRF
score_kind = RRF_SCORE
```

即：

> **执行槽位可以复用，但语义不能撒谎。**

这是一个很好的工程取舍：

```text
Internal Execution Slot Reuse
≠
Semantic Misrepresentation
```

------

# 12. Hybrid Failure Semantics

WP2 对 Hybrid 的要求比 Baseline heuristic rerank 更严格。

Baseline 某些 rerank failure 可以：

```text
degrade
→ 保留原 ranking
```

但 Hybrid 不允许：

```text
BM25 failure
→ Dense only

RRF failure
→ baseline heuristic

Hybrid unavailable
→ baseline
```

因为配置明确写的是：

```text
HYBRID_RRF
```

所以 required channel failure 必须：

```text
FAIL CLOSED
```

当前包括：

```text
HYBRID_DENSE_CHANNEL_EMPTY
BM25_SEARCH_FAILED
HYBRID_BM25_CHANNEL_EMPTY
HYBRID_CHANNEL_MISSING
RRF_FUSION_FAILED
HYBRID_STRATEGY_UNAVAILABLE
```

Final Gate 确认没有 single-channel RRF、heuristic fallback 或 silent Baseline substitution。

------

# 13. Degraded Hybrid 的真实 Bad Case

Scout 发现：

```text
strategy = HYBRID_RRF
knowledge_base_required = false
Hybrid dependencies unavailable
```

应用虽然 degraded 启动，但因为已有 Dense manager 和 baseline service，理论上请求仍可能：

```text
偷偷跑 Baseline
```

这很危险。

因为：

```text
配置显示 Hybrid
实际运行 Baseline
```

Evaluation attribution、日志、故障定位都会失真。

WP2 最终改成：

```text
application:
可以 degraded READY

knowledge retrieval:
HYBRID_STRATEGY_UNAVAILABLE
→ fail closed
```

即：

> **Application Availability 和 Feature Availability 是两个不同层面的概念。**

应用能启动，不代表某个 feature 必须偷偷换实现继续工作。

------

# 14. Budget Accounting 为什么增加 bm25_queries / rrf_fusions

以前主要有：

```text
vector_queries
keyword_queries
```

最简单的偷懒方案是：

```text
BM25
→ keyword_queries
```

但这会造成观测语义错误。

Chroma `$contains` keyword search 和 BM25 是两个不同的 retrieval mechanism。

所以 WP2 增加：

```text
bm25_queries
rrf_fusions
```

例如 rewrite 改写成功：

```text
vector_queries = 2
bm25_queries = 1
rrf_fusions = 1
keyword_queries = 0
```

Dense 如果已经空：

```text
bm25_queries = 0
rrf_fusions = 0
```

因为这些 operation 根本没执行。

Final Gate 已确认 Budget、events、evaluation snapshot 都遵循真实 execution accounting。

核心原则：

> **Observability 首先要 truthfully describe what actually happened，而不是强行塞进旧字段。**

------

# 15. Evaluation Artifact v2 如何描述 Hybrid

WP2 完成以后，Artifact 的三个集合终于具有非常清楚的含义：

```text
retrieved_items
→ pre-fusion evidence

ranked_items
→ post-RRF fused ranking

selected_items
→ actual final context
```

例如一个 chunk 同时被 Dense 和 BM25 找到，在：

```text
retrieved_items
```

中可以出现两条 evidence：

```text
Dense:
VECTOR_NORMALIZED_RELEVANCE

BM25:
BM25_RAW_SCORE
```

这是合法的。

但：

```text
ranked_items
```

只能有一条最终 fused identity：

```text
RRF
RRF_SCORE
```

并且可以保存：

```text
dense_channel_rank
bm25_channel_rank
rrf_fused_rank
```

AgentEvalOps 再基于 fused `(document_id, chunk_id)` ranking 计算 Recall@K、MRR、NDCG。

这里可以总结：

> **Retrieval evidence 和 Final ranking 是两种不同的数据模型，不应该强行做一对一映射。**

------

# 16. 真实性与完成边界

### 已真实实现

当前已经真实存在：

```text
Production Dense Channel
Production BM25 Channel
Production RRF Fusion
Hybrid rank-only selection
Hybrid fail-closed
degraded Hybrid protection
BM25 application-scoped lifecycle
BM25-only Dense materialization
Hybrid budget accounting
Hybrid observability
Hybrid Evaluation Artifact v2
AgentEvalOps Hybrid v2 consumer
```

Final Gate 全部给出 PASS。

### 已真实测试

Final Gate 重点回归：

```text
LocalAgent relevant:
205 passed
3 historical failures

Final Gate remediation:
36 passed

AgentEvalOps:
100 passed
1 warning
```

`compileall` 与 `git diff --check` 也通过。

### 尚未完成

仍然没有证明：

```text
HYBRID_RRF
质量一定优于 BASELINE
```

也没有：

```text
HYBRID_PRODUCTION_DEFAULT = YES
```

所以简历或面试不能说：

> “我们已经把 Hybrid 设置为了生产默认检索策略。”

正确说法：

> “Hybrid 已经 production-reachable，默认仍保留 Baseline，下一阶段通过 production-target evaluation 决定是否切换。”

------

# 17. Real Bad Cases

## Real Bad Case 1：RRF score 被 Dense threshold 全部过滤

触发：

```text
RRF score ≈ 0.03
rag_min_score = 0.55
```

风险：

```text
Hybrid 永远 EMPTY
```

根因：

把不同 score space 当成统一 relevance space。

修复：

```text
Hybrid:
rank-only selection

Baseline:
score-based filtering
```

关键词：

```text
Score Space
Rank Fusion
Strategy-specific Filtering
```

------

## Real Bad Case 2：degraded Hybrid 偷跑 Baseline

触发：

```text
HYBRID_RRF configured
Hybrid dependencies unavailable
knowledge_base_required=false
```

风险：

系统配置与真实行为不一致。

根因：

Application degraded readiness 和 Retrieval Strategy availability 没有完全隔离。

修复：

```text
application may start
but Hybrid request fails closed
```

关键词：

```text
Fail Closed
Strategy Attribution
Feature Availability
Graceful Degradation
```

------

## Real Bad Case 3：Hybrid candidate budget 超过 8

Final Gate 发现：

```text
candidate_k = max(rag_top_k * 2, 8)
```

在 `rag_top_k=5..8` 时会得到 10~16。

风险：

违反 RRF frozen channel budget。

修复：

Hybrid-specific cap = 8。

这是 Final Gate 的 P1 fix-forward。

------

## Real Bad Case 4：使用 Chroma private API 做 BM25-only lookup

初始代码：

```text
_collection.get()
```

风险：

代码依赖 Chroma 内部实现细节。

修复：

```text
vector_store.get()
```

并保留 lock + identity validation。

关键词：

```text
Encapsulation
Public API Boundary
Dependency Stability
```

------

## Real Bad Case 5：Fusion lookup 错误落入 generic internal error

BM25-only materialization 本质属于 fusion mapping。

如果 lookup 出错却变成 generic error：

```text
无法知道是 RRF/mapping failure
```

Final Gate 修复为：

```text
RRF_FUSION_FAILED
```

体现：

> Error taxonomy 应表达失败发生在哪个业务阶段，而不是只表达底层抛了什么异常。

------

## Real Bad Case 6：先 materialize 8 个，再只用 3/4 个

原链路：

```text
RRF fused 8
→ materialize 8
→ Context 最后 top 3
```

风险：

```text
额外 Dense lookup
额外 document_reads
额外 latency
```

Final Gate 调整：

```text
RRF fused
→ top rag_top_k
→ materialize
```

这也是 P1 fix-forward。

------

# 18. 名词 / 概念速览

| 名词                           | 一句话理解                                                   |
| ------------------------------ | ------------------------------------------------------------ |
| Hybrid Retrieval（混合检索）   | 将语义检索和词法检索结合起来提高召回与排序质量。             |
| Dense Retrieval（稠密检索）    | 使用 Embedding 向量相似度寻找语义相关内容。                  |
| Sparse Retrieval（稀疏检索）   | 根据词项匹配及词频等统计信息完成检索，BM25 是典型实现。      |
| BM25                           | 基于 TF、IDF 和文档长度归一化的经典词法排序算法。            |
| RRF（倒数排名融合）            | 通过多个 ranking 中的名次而非 raw score 来完成融合。         |
| Query Rewrite（查询改写）      | 将用户问题改写为更适合检索的表达。                           |
| Query Expansion（查询扩展）    | 使用多个表达对同一个检索空间进行召回。                       |
| Retrieval Channel（检索通道）  | 一种独立 ranking 来源，例如 Dense 或 BM25。                  |
| Rank Fusion（排名融合）        | 将多个独立 ranking 合成为统一排序。                          |
| Score Space（分数空间）        | 某种算法产生的分数尺度和语义。                               |
| Fail Closed                    | 依赖条件无法满足时拒绝继续，而不是偷偷换行为。               |
| Application-scoped             | 对象在整个应用生命周期内创建一次并复用。                     |
| Materialization（物化）        | 将 ranking identity 转换为完整正文与 metadata。              |
| Strategy Isolation（策略隔离） | 不同检索策略通过独立 implementation path 减少互相影响。      |
| Error Taxonomy（错误分类体系） | 用稳定业务语义分类失败，而不是暴露底层异常。                 |
| Production Reachable           | 能够从真实 canonical runtime 被正常执行到，而非仅存在脚本或测试。 |

------

# 19. 工程构建方法类面试题

## Q1：为什么不直接把 BM25 加到现有 adapter？

因为当前 Baseline 已经有稳定行为：

```text
Dense + keyword + heuristic rerank
```

直接修改容易让 Hybrid 的：

```text
BM25
RRF
failure semantics
filter semantics
```

污染 Baseline。

所以选择：

```text
construction-time strategy selection
+
independent Hybrid adapter
```

把回归面限制住。

------

## Q2：为什么 rewritten 和 original 不作为两个 RRF channel？

因为它们只是同一 Dense modality 的 query expansion。

如果拆开：

```text
Dense rewritten
Dense original
BM25
```

会人为增加 Dense 的投票权，还需要把固定双通道 RRF 改成三通道。

因此先 merge 为统一 Dense ranking 更符合 retrieval modality 的语义。

------

## Q3：为什么不用加权 Dense score + BM25 score？

因为两个 raw score 不在同一个 score space。

Dense 可能是：

```text
0~1 relevance
```

BM25 可能是：

```text
几分、十几分
```

直接线性加权必须先做 calibration / normalization。

RRF 只使用 rank，因此对异构检索分数更鲁棒。

------

## Q4：为什么 RRF 没有 absolute score threshold？

因为 RRF score 的主要意义是相对 ranking，而不是 calibrated relevance probability。

所以目前 Hybrid 使用：

```text
rank-based top-k
```

而不是人为把：

```text
0.03
```

解释成“3%相关度”。

------

## Q5：为什么 required channel 为空也失败，而不是另一边继续？

因为 production strategy 明确叫：

```text
HYBRID_RRF
```

如果 BM25 empty 后继续 Dense-only：

```text
configured Hybrid
actual Dense
```

策略 attribution 失真。

所以当前 contract 选择 strict Hybrid：

```text
both channels required
```

------

## Q6：为什么 BM25-only result 要回 Chroma lookup？

因为 BM25 是 ranking authority，但不是完整 citation metadata authority。

完整 citation metadata 已经存在 Dense/Chroma generation 中。

通过 stable identity：

```text
(document_id, chunk_id)
```

回查，比在 BM25 里复制一套 metadata 更不容易 drift。

------

## Q7：为什么不新增 FUSE stage？

因为它会扩大：

```text
event contract
metrics
timeout
enum
docs
tests
```

当前 `RERANK` execution slot 已足够承载 fusion。

但必须在 observability 中明确：

```text
RRF_SCORE
RRF_FUSED
HYBRID_RRF
```

不能假装是普通 rerank。

------

# 20. 高频追问

面试官很可能继续追：

```text
为什么选 BM25 而不是纯 keyword search？
为什么选 RRF 而不是 weighted score fusion？
BM25 和 Dense 分别擅长什么查询？
Query Rewrite 对 BM25 为什么只执行 rewritten 一次？
Hybrid latency 会增加多少？
为什么没有并发 Dense/BM25？
如果一个 channel empty 为什么不 degrade？
RRF_K=60 是怎么来的？
BM25-only Dense lookup 会不会增加 latency？
如何保证 RRF 的 document identity 一致？
Hybrid Evaluation 怎样区分 retrieved/ranked/selected？
如何避免 Hybrid 上线后影响旧 Baseline？
为什么 Hybrid 现在还不是默认策略？
```

其中最后一个回答一定要保持真实：

> 因为工程可运行不等于质量上一定更优，所以先让 Hybrid production reachable，再通过 WP3 在同一 canonical runtime 上进行 Baseline vs Hybrid 的 Evaluation，最后再决定默认策略。

------

# 21. 30 秒总结

> 我在完成 Hybrid RAG 的索引一致性和 provenance contract 后，把 Dense + BM25 → RRF 正式接入了 LocalAgent 的 canonical runtime。实现上没有直接修改原 Baseline adapter，而是通过独立 Hybrid adapter 隔离策略；rewritten 和 original query 的 Dense 结果先 merge 成一个 Dense channel，再和 BM25 top-8 通过已有 HybridRrfRetriever 做 RRF。因为 RRF raw score 和 Dense relevance 不在同一个分数空间，Hybrid 不再使用 rag_min_score，而是按 fused rank 取最终 top-k。同时对 BM25/空通道/RRF failure 全部 fail closed，禁止偷偷回退 Baseline。当前 Hybrid 已 production-reachable，但默认仍是 Baseline，要等下一阶段 Evaluation 决定是否切换。

------

# 22. 2 分钟总结

> 在上一阶段，我先解决了 Dense 和 BM25 的 provenance 和 generation 一致性问题，确保只有同一 corpus、同一 chunk policy 和同一个 generation 的索引才能融合。在这个 WP 里，我才把 Hybrid Retrieval 真正接进生产 Runtime。
>
> 我没有直接扩展原来的 RuntimeKnowledgeRetrievalAdapter，而是增加独立的 Hybrid adapter，由 server 的 composition root 根据启动策略选择。这样原来的 Baseline 仍然保持 Dense + Chroma keyword supplement + heuristic rerank，不会被 Hybrid 行为污染。
>
> Hybrid 查询时仍保留现有 query rewrite。rewritten 和 original 会分别执行 Dense search，但它们属于同一种检索 modality，所以先 merge、去重并重新编号成一个 Dense channel；另一个 channel 是 BM25，而且 Hybrid 下彻底禁用原来的 Chroma keyword supplement。两边各取最多 8 个候选，再复用已有的 HybridRrfRetriever 做 RRF。
>
> 这里发现过一个重要问题：RRF score 最大只有大约 0.03，而原来 Dense 的 rag_min_score 是 0.55，如果直接复用 filter，Hybrid 会全部变成 EMPTY。所以我把 Hybrid 改成 rank-based top-k selection，Baseline 才继续使用 score threshold。
>
> Hybrid 的 required channel 全部采用 fail-closed。Dense empty、BM25 empty、BM25 exception 或 RRF failure 都不会偷偷变成单通道检索，也不会 fallback 到 Baseline。即使 knowledge_base_required=false 允许应用 degraded 启动，如果配置的是 HYBRID_RRF 而依赖不可用，请求也会明确返回 HYBRID_STRATEGY_UNAVAILABLE。
>
> BM25 index 在 startup 阶段只加载一次并 application-scoped 复用。对于只被 BM25 找到、但最终进入 RRF Top-K 的 chunk，我没有拿 BM25 的有限 metadata 编造 citation，而是通过 document_id 和 chunk_id 回 active Dense generation 精确获取完整 SourceMetadata。
>
> Evaluation 侧则把 retrieved、ranked、selected 三层数据分开：Dense/BM25 是 pre-fusion evidence，ranked_items 是 RRF fused ranking，selected_items 是实际进入 context 的内容。AgentEvalOps 继续基于 fused document_id/chunk_id 计算 Recall@K、MRR 和 NDCG。
>
> Final Gate 最后还修复了 Hybrid candidate budget 超限、使用 Chroma private API、fusion exception 分类以及 materialize 太多 fused candidates 等几个 P1。最终 Hybrid 已经 production-reachable，但仍不是默认策略；下一阶段会用 production-target Evaluation 决定它是否真的优于 Baseline。

------

# 23. 推荐继续深入学习的关键词

这一 WP 面试价值最高的关键词建议优先掌握：

```text
Hybrid Retrieval
Dense vs Sparse Retrieval
BM25
Reciprocal Rank Fusion
Rank Fusion vs Reranking
Score Calibration
Query Rewrite / Query Expansion
Fail-closed Strategy
Strategy Isolation
Application-scoped Dependency
Materialization
Citation Provenance
Retrieval Budget
Production Reachability
Evaluation Attribution
```

如果只选最重要的 7 个：

```text
BM25
RRF
Hybrid Retrieval
Score Space
Fail Closed
Strategy Isolation
Retrieval Evaluation
```

------

# 24. 推荐学习文档名

最终建议：

```text
docs/interview/stage5_phase6_wp2_canonical_hybrid_retrieval_integration.md
```

这个文件名能够准确表达真实完成边界：

```text
WP1
→ Hybrid 可以安全融合

WP2
→ Hybrid 已真正接入 canonical runtime

WP3
→ 验证 Hybrid 是否真的优于 Baseline
```

因此目前面试中可以明确说 **“Hybrid RAG 已实现并 production-reachable”**，但还不能说 **“Hybrid 已被证明优于 Baseline”** 或 **“已经成为默认生产策略”**。