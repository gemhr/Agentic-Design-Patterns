# 一、这个 WP 到底解决了什么

WP1 做完 BM25（Best Matching 25，经典词法检索算法）之后，你实际上有了两个性质不同的检索通道：

```
Current channel
≈ Dense semantic retrieval
+ Chroma lexical supplement
+ candidate merge
+ heuristic rerank

BM25 channel
≈ lexical retrieval
```

问题变成：

> 两个排序体系完全不同的检索器，怎样组合，而不强行比较它们不可比的 score？

WP2 的答案就是 **RRF（Reciprocal Rank Fusion，倒数排名融合）**。

最终链路是：

```
Query
  │
  ├── Current ranked chunks ───┐
  │                            │
  └── BM25 ranked chunks ──────┤
                               ▼
                      HybridRrfRetriever
                               │
                       fused top-8 chunks
                               │
                               ▼
                      DocumentProjection
                               │
                               ▼
                    BEIR document ranking
                               │
                               ▼
                         qrels evaluator
```

这里最值得理解的不是“加了一个 RRF 算法”，而是：

> **把异构检索器组合问题，从 score-space 转换成了 rank-space。**

这才是这个 WP 的核心工程价值。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

# 二、RRF 为什么适合 Dense + BM25

假设两个检索器分别输出：

```
Dense:
A rank1
B rank2
C rank3

BM25:
B rank1
D rank2
A rank3
```

RRF 不关心 Dense 给 A 的 cosine similarity 是 `0.83`，也不关心 BM25 给 B 的 BM25 score 是 `17.2`。

它只关心：

```
A:
Dense rank = 1
BM25 rank = 3

B:
Dense rank = 2
BM25 rank = 1
```

然后计算：

```
score(d) = Σ 1 / (k + rank)
```

你们冻结的是：

```
k = 60
rank starts at 1
channels = 2
```

因此，一个文档同时被两个通道排在较前位置，它就会获得两份贡献；只被一个通道召回，则只有一份贡献。10_dense_bm25_rrf_hybrid_retrieval.mdMD

### 为什么不直接 Dense score + BM25 score？

因为这两个 score **没有共同量纲**。

Dense 可能是：

```
cosine similarity
0.71
0.76
0.83
```

BM25 可能是：

```
8.4
12.7
21.3
```

直接：

```
dense_score + bm25_score
```

在数学上基本没有可靠含义。

当然可以做 score normalization（分数归一化）、calibration（校准）、learned fusion（学习式融合），但都会引入更多超参数、训练数据和稳定性问题。

RRF 的优点就是：

> 不要求两个检索器的分数可比，只要求它们各自能够给出可靠排序。

这是面试中非常重要的一句话。

------

# 三、为什么 `rrf_k=60`

先不要把 `60` 理解成某个“神奇最优参数”。

它本质上是一个 **rank smoothing constant（排名平滑常数）**：

```
1 / (k + rank)
```

当 `k` 较大时：

```
rank1
rank2
rank3
```

之间的贡献差异不会特别激进。

也就是说，RRF 更关注：

> “多个检索器是否一致认为这个候选靠前”

而不是：

> “某一个检索器是不是把它排在第一”。

你们这一 WP 做得正确的一点是：

```
rrf_k = 60
```

在 SciFact 正式评测之前就冻结，并写入 constant + tests。

然后即使看到 Top3 指标下降，也没有改成：

```
k=30
k=20
k=10
```

去刷 benchmark。

否则就会产生典型的 **benchmark overfitting（基准过拟合）**。10_dense_bm25_rrf_hybrid_retrieval.mdMD

面试可以这样回答：

> 我们第一版采用固定 RRF k=60，不在测试集结果出来后调参，因为这一阶段的目的不是寻找 SciFact 最优超参数，而是验证 Hybrid Retrieval 架构本身是否有效。后续如果要调 k，会单独划分 validation set，而不是直接针对最终 benchmark 调整。

这已经非常接近生产评测思路。

------

# 四、为什么 RRF 是 query-time component，而不是新的 Retrieval Owner

你们没有建立：

```
HybridRetrievalService
    ├─ own Dense index
    ├─ own BM25 index
    ├─ own cache
    ├─ own persistence
    └─ own result contract
```

而是：

```
Current Retriever ─┐
                   ├─ HybridRrfRetriever
BM25 Retriever ────┘
```

`HybridRrfRetriever` 只负责：

```
ranked candidates
        ↓
rank fusion
        ↓
ranked candidates
```

这属于非常好的 **Single Responsibility Principle（单一职责原则）**。

它不拥有：

```
index
cache
Retrieval Run
Context Selection
database
Evaluation Domain
```

因此没有产生第二套 Retrieval 生命周期。10_dense_bm25_rrf_hybrid_retrieval.mdMD

这也是系统设计面试里常见的 Owner 问题：

> 为什么不把 Hybrid Retriever 做成一个完整的新 Retriever？

答案不是“代码少”。

真正原因是：

> Hybrid Fusion 本身没有索引生命周期，它只是组合已有 Retriever 的输出。如果让它重新成为 Retriever Owner，就会产生索引、缓存、状态和结果 Contract 的重复所有权。

------

# 五、为什么是在 chunk level 做融合

你们当前流程：

```
Current chunks
+
BM25 chunks
        ↓
      RRF
        ↓
fused chunks
        ↓
DocumentProjection
        ↓
documents
```

而不是：

```
Current documents
+
BM25 documents
        ↓
RRF
```

这是因为 LocalAgent 的真实检索单位是 **chunk（文本块）**。

例如：

```
Document A
 ├─ chunk 1
 ├─ chunk 2
 └─ chunk 3
```

Dense 和 BM25 实际可能分别命中：

```
Dense → A/chunk2
BM25  → A/chunk3
```

如果过早 document dedup，就会丢失：

```
哪个 chunk 被哪个 channel 找到
```

的信息。

所以你们先：

```
(document_id, chunk_id)
```

作为稳定 identity 融合，再由 AgentEvalOps 已有 `DocumentProjection` 完成：

```
chunk ranking
    ↓
document dedup
    ↓
BEIR document ranking
```

这种分层是合理的。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

# 六、为什么 Dedup 和 Tie-break 也是 Contract

很多人实现 RRF 就写：

```
scores[id] += 1 / (k + rank)
```

然后结束。

但生产实现的问题在于：

> 如果两个候选 RRF score 完全相同，谁排前面？

你们冻结了：

```
RRF score descending
→ best channel rank ascending
→ contributing channel count descending
→ stable chunk identity ascending
```

最后那个：

```
stable chunk identity ascending
```

特别重要。

它不是为了提升 Recall，而是为了保证：

**Determinism（确定性）**。

同一输入不应该因为：

```
dict iteration
set iteration
process scheduling
Python implementation detail
```

导致结果顺序变化。

所以你们才有：

```
exact score
inverse ranking
deterministic tie
```

对应单元测试。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

# 七、为什么 malformed ranking 要 fail closed

你们要求单 channel：

```
duplicate → failure
non-contiguous rank → failure
rank not starting at 1 → failure
```

这属于 **Fail Closed（失败关闭）**。

为什么不“自动修复”？

比如输入：

```
rank1
rank3
rank4
```

程序完全可以偷偷改成：

```
rank1
rank2
rank3
```

但是这么做意味着 Fusion 层开始猜测上游语义。

更危险的是 duplicate：

```
chunk A rank1
chunk A rank3
```

到底：

```
取 rank1？
取 rank3？
两个都贡献？
```

任何自动选择都是隐含策略。

所以正确做法是：

> 排名 Contract 不满足时明确失败，而不是让 Fusion 层静默修复上游数据。

------

# 八、Empty 和 Failure 为什么必须区分

这是这一 WP 另一个非常好的工程点。

你们的语义是：

| Current           | BM25    | 行为         |
| ----------------- | ------- | ------------ |
| success           | success | 正常 RRF     |
| success           | empty   | Current-only |
| empty             | success | BM25-only    |
| empty             | empty   | `EMPTY`      |
| technical failure | 任意    | failure      |

这里最关键的是：

```
EMPTY ≠ FAILED
```

Empty 表示：

> 检索器正常工作，只是没有结果。

Failure 表示：

> 我不知道检索结果应该是什么，因为系统执行失败了。

如果：

```
BM25 timeout
```

然后被偷偷转换成：

```
BM25 = []
```

你最终会得到一个看起来正常的 Current-only 结果。

评测系统则会认为：

```
Hybrid retrieval succeeded
```

这是错误的。

因为真正事实应该是：

```
Hybrid retrieval technical failure
```

所以你们明确规定：

```
FAILED
TIMED_OUT
CANCELLED
HTTP failure
parse failure
artifact invalid
```

不能转换为 empty。10_dense_bm25_rrf_hybrid_retrieval.mdMD

这是典型的 Runtime / Evaluation 面试知识点：

> **业务空结果和技术失败不能共享一个状态。**

------

# 九、Candidate Budget 为什么必须冻结

你们的 budget：

```
Current <= 8
BM25 <= 8
union <= 16
RRF output <= 8
```

看起来只是几个数字，实际上它控制了实验公平性。

假设 Current baseline 是：

```
top8
```

然后 Hybrid 突然：

```
Dense top100
BM25 top100
RRF top50
```

即使 Recall 提升了，也无法知道提升到底来自：

```
RRF
```

还是：

```
candidate pool 扩大 12.5 倍
```

所以保持 candidate budget 稳定，是在控制实验变量。

这就是 Evaluation 中的 **Controlled Variable（控制变量）** 思维。

真实 300-query evidence 也确认：

```
max Current = 8
max BM25 = 8
max union = 16
max final = 8
```

说明 Contract 不只是文档描述，而是被真实运行验证过。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

# 十、为什么 RRF 不需要自己的 Cache

RRF 输入：

```
two ranked lists
```

计算：

```
几十次简单加法 + 排序
```

它没有：

```
Embedding
Index Build
Corpus preprocessing
Tokenization index
```

所以你们复用了：

```
Dense cache
BM25 cache
```

而没有创建：

```
RRF cache
```

这是正确的。

真实结果也证明：

```
Dense CACHE_HIT = PASS
REEMBEDDING = NO

BM25 CACHE_HIT = PASS
```

RRF fusion 平均仅约：

```
0.0961 ms
```

几乎可以忽略。10_dense_bm25_rrf_hybrid_retrieval.mdMD

一个很好的面试回答是：

> Cache 应该围绕高成本、可复用的计算建立，而不是因为系统多了一个组件就机械地增加一层 Cache。RRF 本身是极低成本的 query-time pure computation，没有独立 cache 的收益。

------

# 十一、这组指标应该怎样读

最重要的是别说：

> “RRF 全面优于原检索。”

因为事实不是这样。

实际结果是：

| Metric   | Current    | RRF        | 结论   |
| -------- | ---------- | ---------- | ------ |
| Recall@1 | 0.5451     | **0.5567** | ↑      |
| Recall@3 | **0.7307** | 0.7084     | ↓      |
| Recall@5 | 0.7763     | **0.7878** | ↑      |
| MRR      | 0.6632     | **0.6669** | 小幅 ↑ |
| NDCG@3   | **0.6617** | 0.6552     | ↓      |
| NDCG@5   | 0.6811     | **0.6888** | ↑      |

所以正确结论是：

> RRF 确实补充了一部分 BM25 lexical signal，提升了 Top5 的整体覆盖能力，但同时重新排列了部分 Current 原本较强的 Top3 候选，因此产生浅层排名退化。10_dense_bm25_rrf_hybrid_retrieval.mdMD

这比简单说：

```
Recall@5 +1.15%
```

有价值得多。

------

# 十二、Rescue / Regression 分析为什么比 Aggregate Metric 更重要

假设只看：

```
Recall@5
0.7763 → 0.7878
```

你只能知道：

> 平均变好了。

但不知道为什么。

你们进一步做了：

```
Current miss → RRF hit
Current hit → RRF miss
```

Top5：

```
miss → hit = 14
hit → miss = 6

net = +8
```

这直接回答了：

> RRF 到底救回了多少 Current 原本失败的 case，又破坏了多少 Current 原本成功的 case？

这就是 **Regression Analysis（回归分析）** 的价值。10_dense_bm25_rrf_hybrid_retrieval.mdMD

而 Top3：

```
miss → hit = 14
hit → miss = 16
net = -2
```

这正好解释了：

```
Recall@3 下降
NDCG@3 下降
```

------

# 十三、为什么 Top1 net -1，但 Recall@1 反而上升

这是本 WP 非常好的面试追问题。

你们得到：

```
Top1 binary hit net = -1
```

但：

```
Recall@1:
0.5451 → 0.5567
```

看似矛盾。

原因在于两个统计口径不一样。

Binary hit：

```
query 是否命中至少一个 relevant document
```

只得到：

```
0 / 1
```

Recall：

```
retrieved relevant documents
----------------------------
all relevant documents
```

假设 Query A 有：

```
4 个 relevant docs
```

Top1 命中一个：

```
Recall@1 = 1/4
```

Query B 只有：

```
1 个 relevant doc
```

Top1 命中：

```
Recall@1 = 1
```

所以即使：

```
少命中 1 个 query
```

如果 RRF 救回的 query 平均 relevant-set 更小，也可能：

```
mean Recall@1 上升
```

这说明：

> **Metric 本身也是一种 projection，任何单一指标都不能完整描述系统行为。**

------

# 十四、Oracle Union 到底是什么

你们的：

```
DERIVED_DIAGNOSTIC_ONLY
```

处理是正确的。

Top5：

```
Oracle union hit = 254 / 300
= 84.67%
```

它不是某个真实算法。

它表示：

> 如果我有一个“上帝排序器”，只要 relevant document 出现在 Current 或 BM25 的候选集合里，就假设它能把 relevant document 排进 Top5，那么最多能做到多少。

因此 Oracle Union 测的是：

```
candidate generation ceiling
```

而不是：

```
RRF performance
```

你们实际：

```
both-channel Top5 miss = 46
```

意思是至少这些 case：

> Current 和 BM25 都没有把答案带进 candidate pool。

这种问题 RRF 怎么调排序都解决不了。10_dense_bm25_rrf_hybrid_retrieval.mdMD

因此后续优化必须区分：

```
candidate generation failure
```

和：

```
ranking failure
```

这是 RAG（Retrieval-Augmented Generation，检索增强生成）调优非常核心的诊断思想。

------

# 十五、为什么下一步是 Cross-Encoder

RRF 解决的是：

```
两个 Retriever 的 rank 如何融合
```

但它并不真正理解：

```
query 与 chunk 的语义匹配程度
```

例如：

```
Current rank1
BM25 rank1
```

RRF 会认为它非常可靠。

但：

```
两个 Retriever 可能一起错。
```

Cross-Encoder 的价值是重新做：

```
(query, candidate)
        ↓
deep relevance scoring
```

因此完整思路变成：

```
Dense
   \
    \
     RRF → candidate pool → Cross-Encoder → final ranking
    /
BM25
```

简单理解：

```
Dense / BM25
负责 Recall

RRF
负责多路融合

Cross-Encoder
负责 Precision / ranking
```

而你们这一次恰好发现：

```
RRF Top5 improves
Top3 regresses
```

实际上正是一个很合理的 Cross-Encoder 输入状态。

因为：

> Candidate pool 更丰富了，但浅层排序还不够好。

------

# 十六、为什么现在不能直接把 RRF 设成 production default

因为还没有事先冻结：

```
什么叫“足够好”？
```

例如究竟要求：

```
Recall@5 必须提升？
Recall@3 不能下降？
NDCG@3 最多允许下降多少？
Critical Case 一个都不能退化？
总 regression 数必须 < N？
```

这些都没有提前定义。

如果现在看到：

```
Top5 +8
```

然后说：

> 那我们认为 Top5 最重要，所以 ACCEPT。

这是 **post-hoc decision（事后决策）**。

同理，如果因为：

```
Top3 -2
```

就说 Reject，同样也是事后门槛。

所以当前：

```
RRF_IMPLEMENTATION = PASS
RRF_CANDIDATE = NEEDS_REVIEW
```

是最严谨的状态。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

# 十七、本 WP 名词 / 概念速览

| 名词                                        | 一句话理解                                                   |
| ------------------------------------------- | ------------------------------------------------------------ |
| RRF（Reciprocal Rank Fusion，倒数排名融合） | 通过各检索器中的 rank 而不是原始 score 融合多路检索结果。    |
| Hybrid Retrieval（混合检索）                | 同时利用语义检索与词法检索等多种检索信号。                   |
| Dense Retrieval（稠密向量检索）             | 使用 Embedding 向量相似度寻找语义相关内容。                  |
| BM25                                        | 基于词频、逆文档频率和文档长度的经典词法排序算法。           |
| Rank Fusion（排名融合）                     | 将多个已有排序列表组合成一个新的统一排序。                   |
| Candidate Budget（候选预算）                | 限制各阶段允许进入下一阶段的候选数量。                       |
| Deduplication（去重）                       | 将同一稳定实体的重复候选合并。                               |
| Tie-break（平分决胜规则）                   | 主排序分数相同时用于获得稳定次序的规则。                     |
| Determinism（确定性）                       | 相同输入与状态下获得可重复结果。                             |
| Fail Closed（失败关闭）                     | 数据不满足 Contract 时明确失败，而不是猜测或静默修复。       |
| Provenance（来源追踪）                      | 保存一个最终候选由哪些 channel、rank 和 score 演化而来。     |
| Rescue Case（救回案例）                     | Baseline miss、Candidate hit 的真实改善 case。               |
| Regression Case（回归案例）                 | Baseline hit、Candidate miss 的真实退化 case。               |
| Oracle Union（理想并集诊断）                | 假设并集候选能被完美排序时的候选生成理论上限。               |
| Rank Transition（排名迁移）                 | 比较同一 relevant document 在 baseline 与 candidate 中排名如何变化。 |
| Cross-Encoder（交叉编码器）                 | 将 query 和 candidate 一起输入模型进行更精确相关性打分。     |
| Benchmark Overfitting（基准过拟合）         | 根据最终 benchmark 结果反复调参，使指标好看但泛化能力下降。  |

------

# 十八、工程构建类面试题

### Q1：为什么 Dense 和 BM25 不直接把 score 相加？

因为两种 Retriever 的 score 来源、尺度和分布都不同，直接相加缺少数学可比性。可以通过 normalization 或 calibration 做 score fusion，但第一版会增加新的超参数和训练依赖，所以我们采用只依赖排序位置的 RRF。

------

### Q2：为什么不用一个大模型直接把所有候选重新排序？

成本和延迟。

Retriever 的职责是：

```
从大语料快速缩小候选空间
```

Cross-Encoder 或 LLM reranker 更适合：

```
对有限 candidate pool 做高质量排序
```

不能让昂贵模型直接扫描整个 corpus。

------

### Q3：为什么不把 Current 和 BM25 并行调用？

从算法上可以。

但本 WP 的目标是验证：

```
RRF correctness
```

而不是 production latency。

因此使用 sequential execution 更容易控制变量和定位失败。

真实 latency 也明确注明：

```
evaluation HTTP boundary
not production SLO
```

所以不能拿当前约 170ms 直接宣称生产性能。10_dense_bm25_rrf_hybrid_retrieval.mdMD

未来生产化可以变成：

```
        ┌─ Current
Query ──┤
        └─ BM25
           │
           ▼
          RRF
```

这才是 latency optimization。

------

### Q4：为什么 BM25 timeout 时不直接退化成 Dense-only？

可以设计这种生产策略，但要显式建模。

这一 WP 选择：

```
technical failure → evaluation failure
```

是因为评测阶段需要知道：

> Hybrid pipeline 是否真的完整执行。

否则 infrastructure failure 会污染 quality metric。

生产系统则可能采用：

```
BM25 timeout
→ Dense graceful degradation
→ emit degradation telemetry
```

这是另外一个 Contract，不能混进 benchmark。

------

### Q5：RRF 最大缺点是什么？

它只看：

```
rank
```

不看：

```
query-document semantic relevance
```

所以如果两个 Retriever 的 ranking 都有系统性偏差，RRF 无法真正理解哪个 candidate 更正确。

另外它还会丢掉：

```
score confidence
```

信息。

因此 RRF 经常适合作为：

```
candidate fusion
```

而不是最终 relevance model。

------

### Q6：为什么 Top5 好了，Top3 反而变差？

因为 BM25 为 candidate pool 引入了新的 lexical candidates。

其中一些确实是 relevant，因此：

```
Top5 coverage ↑
```

但 RRF 只依赖 rank consensus，部分新候选被提升到了原本 Current 强候选之前，于是：

```
Top3 ordering quality ↓
```

这意味着：

> retrieval diversity 增加了，但 fine-grained ranking 仍然有改善空间。

这正是 Cross-Encoder reranking 的使用场景。

------

# 十九、这个 WP 最值得面试讲的 Bad Case

我最推荐讲 **qid 54**。

真实情况：

```
Current:
relevant doc rank1

RRF:
relevant doc rank3
```

这不是实现 Bug，而是算法 trade-off。10_dense_bm25_rrf_hybrid_retrieval.mdMD

面试里可以说：

> 我们没有只展示 Hybrid Retrieval 的提升案例。真实 SciFact 评测里也观察到 Current 原本 rank1 的 relevant document 被 RRF 降到 rank3。进一步做 aggregate 和 case-level 分析后发现，RRF 在 Top5 是净改善，但 Top3 存在轻微回归。所以我们没有直接把它切成生产默认，而是保留为 candidate，并计划让下一阶段 Cross-Encoder 解决候选融合后的精排问题。

这句话同时展示：

```
Evaluation
Regression Analysis
Truthfulness
Architecture Evolution
Release Decision
```

比说“我实现了 RRF”强很多。

------

# 二十、这个 WP 可以怎样概括成项目经历

面试中的一分钟版本可以压成：

> 在 LocalAgent 的 RAG 检索链路里，我先增加了 BM25 词法召回，然后为了融合原有 Dense-led 检索和 BM25，我实现了一个独立的 query-time RRF 组件。因为 Dense 和 BM25 原始 score 不同尺度，所以没有直接做 score fusion，而是固定 `k=60` 按 rank 融合，并冻结 candidate budget、stable chunk identity、tie-break 和失败语义。之后通过 AgentEvalOps 在 SciFact 300 条 query 上跑真实回归，RRF 的 Recall@5 从 0.7763 提升到 0.7878，同时发现 Recall@3 有下降。我们进一步做了 rescue、regression 和 rank transition 分析，确认 Top5 是净 +8 个 hit，但 Top3 是净 -2，所以没有直接切 production default，而把这些 case-level evidence 留给后续 Cross-Encoder 精排阶段。

这里每一句都有 handoff 里的真实 evidence 支撑。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

# 二十一、真实性边界

这个 WP 当前可以真实说：

**已经实现并真实验证**：固定 RRF、Hybrid evaluation runtime、AgentEvalOps analysis、双 cache reuse、SciFact 300-query、synthetic 24-case、PostgreSQL EvaluationLoop persistence、case-level rescue/regression/oracle/rank-transition。10_dense_bm25_rrf_hybrid_retrieval.mdMD

不能说：

```
已经上线生产
已经证明生产语料一定提升
已经优化生成答案质量
达到 production SLO
达到官方 BEIR leaderboard 水平
Cross-Encoder 已经实现
```

这些 handoff 都明确标记为 `NOT_VERIFIED` 或 `NOT_STARTED`。10_dense_bm25_rrf_hybrid_retrieval.mdMD

------

## 推荐的本 WP 面试材料文件名

```
stage5_phase3_wp2_dense_bm25_rrf_hybrid_retrieval_interview.md
```

这个 WP 的核心不是“会写 RRF 公式”，而是已经形成了一条很完整的工程故事：

**异构 Retriever → 不可比较 score → rank-space fusion → 冻结 Contract → 控制变量评测 → aggregate + case-level diagnosis → 发现 gain/regression trade-off → 不贸然切 production → 把问题交给下一阶段精排解决。**

这条链本身就是很好的 AI Agent / RAG 工程面试素材。

**本 WP 学习到这里可以视为完成。下一步应进入 WP3 Cross-Encoder，但我先停在这里，不提前启动下一 WP。**