# Stage5-Phase3-WP3 学习 / 面试总结

## 一、这个 WP 到底做了什么

一句话概括：

> 我在固定 Dense/BM25/RRF 候选集合的前提下，引入 Cross-Encoder（交叉编码器）做 query-document pair 的精排，并通过真实 SciFact 300、synthetic 24、case-level regression analysis 和预冻结 acceptance gate 判断它是否值得进入候选方案。

最终链路：

```text
Current retrieval ─┐
                   ├─→ RRF top8
BM25 retrieval ────┘
                       ↓
                Cross-Encoder
                       ↓
              same top8 reordered
                       ↓
              DocumentProjection
                       ↓
       Recall / MRR / NDCG / Case Analysis
                       ↓
        Frozen Mechanical Acceptance Gate
```

这里最重要的实验原则是：

```text
Candidate Generation 不变
只改变 Ranking
```

因此可以把指标变化比较干净地归因给 Cross-Encoder。

------

# 二、为什么 RRF 后还需要 Cross-Encoder

RRF（Reciprocal Rank Fusion，倒数排名融合）解决的是：

> 多个 retrieval channel 的排序怎么融合？

它主要利用：

```text
rank
```

而不是深入理解：

```text
Query 与 Chunk 的语义匹配关系
```

例如：

```text
Query:
Does drug X reduce disease Y?

Chunk A:
Drug X was evaluated but had no measurable effect on Y.

Chunk B:
Drug X significantly reduced Y in randomized trials.
```

Dense/BM25/RRF 都可能认为两个文档关键词和语义很接近。

Cross-Encoder 则把：

```text
(query, chunk)
```

作为一个整体输入 Transformer，让模型直接判断二者 relevance。

所以典型两阶段 Retrieval：

```text
第一阶段：
快速召回
Dense / BM25 / Hybrid
        ↓
候选 8～100 条

第二阶段：
昂贵精排
Cross-Encoder
        ↓
最终 TopK
```

这也是为什么本 WP 不让 CE 扫整个 5,000+ corpus，而只 rerank top8。

------

# 三、Bi-Encoder 和 Cross-Encoder 的核心区别

### Bi-Encoder（双编码器）

分别计算：

```text
Query → embedding Q

Document → embedding D
```

然后：

```text
similarity(Q, D)
```

优点是 document embedding 可以提前算好：

```text
Document
   ↓
Embedding
   ↓
Vector DB
```

查询时只编码 query，因此适合大规模召回。

缺点是 Query 和 Document 在编码阶段没有直接 token-level interaction。

------

### Cross-Encoder

输入：

```text
[CLS] Query [SEP] Document [SEP]
```

模型内部可以直接做：

```text
query token ↔ document token
```

交互。

因此排序一般更准确，但：

```text
每一个 query-document pair
都必须单独 inference
```

无法像 Vector Search（向量检索）那样提前把整个 corpus 编码后快速 ANN 查询。

所以：

```text
Bi-Encoder = Recall

Cross-Encoder = Rerank
```

是更常见的组合，而不是二选一。

------

# 四、为什么 WP3 坚持 top8 → top8

这是这个 WP 很值得面试讲的设计点。

我们没有做：

```text
RRF top8
↓
CE
↓
top3
```

也没有做：

```text
RRF top50
↓
CE
↓
top8
```

而是：

```text
RRF top8
↓
CE
↓
same top8
```

唯一允许：

```text
ordering change
```

这样形成一个 Controlled Experiment（受控实验）：

```text
Corpus                  固定
Dataset                 固定
Chunking                固定
Dense cache             固定
BM25                    固定
RRF k=60                固定
Candidate count         固定
Candidate identities    固定
Cross-Encoder model     固定

唯一变量：
Candidate ranking
```

所以如果：

```text
NDCG@3 ↑
MRR ↑
```

我们就有比较强的证据说明：

> 提升来自 Cross-Encoder 的 reranking，而不是因为多召回了文档。

------

# 五、这次真实结果应该怎么理解

SciFact 300：

| Metric   | RRF   | RRF + CE | Delta      |
| -------- | ----- | -------- | ---------- |
| Recall@1 | .5567 | .5567    | 0          |
| Recall@3 | .7084 | .7084    | 0          |
| Recall@5 | .7878 | .7878    | 0          |
| MRR      | .6669 | .6819    | **+.0151** |
| NDCG@3   | .6552 | .6812    | **+.0260** |
| NDCG@5   | .6888 | .7031    | **+.0142** |



最有价值的不是简单说：

> CE 提升了 NDCG。

而是：

> **召回集合整体能力没有改善，但是相关文档在候选集合中的位置改善了。**

这正是 reranker 应该解决的问题。

------

# 六、Recall 不变，为什么 NDCG / MRR 会提高

这是非常典型的面试题。

假设 RRF：

```text
rank1 irrelevant
rank2 relevant
rank3 irrelevant
```

CE：

```text
rank1 relevant
rank2 irrelevant
rank3 irrelevant
```

两者：

```text
Recall@3 = 一样
```

因为相关文档都在 Top3。

但是：

```text
MRR:
1/2 → 1

NDCG:
相关结果越靠前，discount 越小
因此提高
```

这恰好就是本次真实结果表现出的模式。

------

# 七、为什么 Recall@K 不变，但 rescue 又是正的

你的真实结果：

```text
K1 rescue 24 / regression 20
K3 rescue 17 / regression 5
K5 rescue 4 / regression 1
```



看起来：

```text
rescue > regression
```

但 Recall@K delta 却是 0。

不能解释为“TopK 集合没变化”。

正确原因是指标统计粒度不同。

### Rescue / Regression

通常是 query-level binary：

```text
这个 query 的 TopK：
有没有至少一个 relevant document？
```

结果只有：

```text
0 / 1
```

### Recall@K

对于一个 query 有多个 relevant documents 时：

```text
Recall@K
=
TopK 中 relevant 数量
/
总 relevant 数量
```

比如：

Query A 有 1 个 relevant：

```text
miss → hit
Recall:
0 → 1
```

Query B 有 4 个 relevant：

```text
hit → miss
Recall:
0.5 → 0.25
```

query-level hit transition 与 Recall contribution 权重并不相同。

所以 aggregate Recall 完全可能抵消，而 binary rescue count 仍然是正数。

这是一个很好的**指标不可替代性**案例。

------

# 八、为什么要同时看 Aggregate Metrics 和 Case Analysis

如果只看：

```text
NDCG@3:
.655 → .681
```

可能会得出：

> CE 很好。

但真实 case：

```text
improved = 45
degraded = 32
unchanged = 223
```

并且还有：

```text
qid303:
rank5 → rank6

qid1041:
rank3 → rank4
```



所以真正可靠的 evaluation 应该是：

```text
Aggregate
+
Pairwise Comparison
+
Case Analysis
```

三层。

------

# 九、Rescue / Regression 是什么

对于 Baseline 和 Candidate：

```text
Baseline = RRF
Candidate = CE
```

每个 query 分类：

```text
RRF miss → CE hit
= Rescue

RRF hit → CE miss
= Regression

RRF hit → CE hit

RRF miss → CE miss
```

这样可以得到：

```text
net hit change
=
rescue - regression
```

本 WP：

```text
K1 +4
K3 +12
K5 +3
```

说明 CE 在 binary hit 维度总体是净正向的。

------

# 十、Rank Transition 又解决什么问题

Rescue 只能观察：

```text
hit / miss
```

但：

```text
rank1 → rank2
```

仍然：

```text
hit → hit
```

Rescue 捕获不到。

因此还需要：

```text
Rank Transition
```

本次：

```text
improved = 45
degraded = 32
unchanged = 223
```



这与 NDCG/MRR 提升形成了很好的相互印证：

> CE 主要是在已有 hit candidate 内改善 ranking。

------

# 十一、为什么 SciFact 明明明显提升，最后还 REJECT

这是 WP3 最值得面试讲的一点。

因为我们**在看 CE 结果之前就冻结了 Acceptance Gate（验收门槛）**。

其中规定：

```text
Synthetic 24
六项指标均不得下降
```

结果：

```text
MRR:
1.000 → 0.823

NDCG@3:
0.988 → 0.766

NDCG@5:
0.988 → 0.802
```

明显下降。

所以即使：

```text
SciFact NDCG@3
+0.026
```

也必须：

```text
CE_CANDIDATE = REJECT
```

如果看到 SciFact 很漂亮以后再说：

> Synthetic 样本太少，不算了。

那就是典型的：

**Post-hoc Evaluation（事后修改评价规则）**。

会造成 benchmark overfitting。

------

# 十二、但 REJECT 是否说明 Cross-Encoder 没价值？

**完全不是。**

这次真正得到的工程结论应该是：

> `ms-marco-MiniLM-L6-v2` 在 SciFact 300 上证明 Cross-Encoder reranking 有明显价值，提升了 MRR 和 NDCG；但当前预冻结 gate 对 synthetic regression 零容忍，因此该具体 candidate 没有通过 v1 acceptance gate。

这是：

```text
Algorithm capability = PROVEN

Candidate acceptance = REJECT
```

两个不同结论。

一定不要在面试里说：

> Cross-Encoder 实验失败了。

更准确：

> Cross-Encoder 的主 benchmark 明显改善，但这个具体模型/配置没有满足我们预先冻结的完整 release gate。

------

# 十三、为什么 Synthetic 会下降这么多

从结果可以直接观察到：

```text
Recall@3 = 1
Recall@5 = 1
```

但：

```text
MRR ↓
NDCG ↓
```

说明不是相关文档被彻底召回丢失，而是：

> CE 把已经排得非常好的 relevant documents 向后移动了。

Synthetic RRF baseline：

```text
MRR = 1.0
NDCG ≈ .988
```

本身已经接近 perfect ranking。

这属于很典型的：

**Ceiling Effect（天花板效应）**。

Baseline 已经非常高时：

```text
可改善空间 ≈ 0
可退化空间 > 0
```

所以 reranker 更容易产生 regression。

------

# 十四、这个 Gate 本身有什么局限

现在回头看，不能偷偷改 v1 Gate，但可以总结设计经验：

```text
Synthetic 20 truth cases
+
六项 metric
+
任何下降都 REJECT
```

这个 guardrail 非常严格。

它的优点：

> 对 regression 极敏感。

缺点：

> 小样本、高 baseline 时容易一票否决一个在真实 benchmark 上总体更优的 candidate。

下一版 Gate 如果重新设计，合理方法不是“为了这个 CE 放宽”，而是：

```text
先形成新的 gate version

例如：
CE_CANDIDATE_ACCEPTANCE_GATE.v2

然后在任何新 candidate benchmark 之前冻结。
```

这样才不会污染历史实验。

------

# 十五、Latency 怎么讲

真实 CPU：

```text
cold model load ≈ 3.9s

warm inference:
mean ≈ 164 ms/query

CE total:
mean ≈ 180 ms/query

hybrid endpoint:
mean ≈ 360 ms/query
```



这说明 Cross-Encoder 的代价非常明显。

因此生产设计通常不会：

```text
对全部 corpus Cross-Encode
```

而是：

```text
Retrieve TopN
→ Cross-Encode TopN
```

而且 `N` 是一个真实 latency-quality tradeoff。

本 WP 冻结 N<=8，因此 CPU 也可以完成真实评测。

------

# 十六、为什么模型要固定 revision + digest

如果只记录：

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

未来仓库内容变化后，你无法证明两次实验使用的是同一资产。

所以冻结：

```text
model_ref
revision
asset_tree_sha256
```

这属于 **Experiment Reproducibility（实验可复现性）**。

本次真实模型还验证了：

```text
offline
CPU
local_files_only
exact asset digest
```



这是非常不错的面试工程点。

------

# 十七、为什么 Provenance 这么重要

Provenance（来源追踪）解决：

> 这个指标到底是怎么来的？

本 WP 每个 case 都能证明：

```text
Approved model
        ↓
RRF candidate identity
        ↓
pre rank
        ↓
CE score
        ↓
post rank
        ↓
Evaluation metric
```

如果只保存：

```text
NDCG@3 = .681
```

你无法回答：

- 用了哪个 model？
- 哪个 revision？
- 候选有没有变？
- 是不是 cache rebuild？
- 哪个 document 从 rank2 到 rank1？
- 有没有 mixed model result？

所以真正的 Evaluation Platform 不只是“算指标”，而是：

```text
Metric
+
Evidence
+
Provenance
+
Gate
```

------

# 十八、名词 / 概念速览

| 概念                        | 一句话                                                     |
| --------------------------- | ---------------------------------------------------------- |
| Cross-Encoder（交叉编码器） | Query 和 Document 联合进入模型，直接预测 relevance score。 |
| Bi-Encoder（双编码器）      | Query/Document 分别编码成向量，适合大规模快速召回。        |
| Reranking（重排序）         | 不改变候选集合，只重新调整候选顺序。                       |
| RRF                         | 使用多个 channel 的 rank 做倒数排名融合。                  |
| Candidate Set               | 第一阶段 Retrieval 提供给 reranker 的候选集合。            |
| MRR                         | 根据第一个 relevant result 的 rank 评价排序质量。          |
| NDCG                        | 对多个 relevant result 的位置进行折损后的排序质量指标。    |
| Recall@K                    | TopK 中覆盖了多少 relevant documents。                     |
| Rescue                      | Baseline miss、Candidate hit。                             |
| Regression                  | Baseline hit、Candidate miss。                             |
| Rank Transition             | relevant result 排名改善、退化或不变。                     |
| Acceptance Gate             | benchmark 前冻结的候选接受规则。                           |
| Guardrail                   | 即使主指标提高，也不能突破的退化边界。                     |
| Provenance                  | 保存结果由哪个资产、候选和过程产生的证据。                 |
| Asset Digest                | 对模型文件树做 hash，确认实验使用同一模型资产。            |
| Fail Closed                 | 验证不完整时拒绝结果，而不是猜测或继续成功。               |
| Ceiling Effect              | baseline 接近满分时改善空间很小，但退化空间仍然很大。      |
| Benchmark Overfitting       | 根据 benchmark 结果反向修改方案或评价规则。                |

------

# 十九、工程构建类高频面试问题

### 1. 为什么不用 Cross-Encoder 直接检索整个知识库？

因为复杂度约为：

```text
每个 query × corpus documents
```

每个 pair 都需要 Transformer inference。

因此生产级模式通常：

```text
cheap retriever
→ small candidate set
→ expensive reranker
```

------

### 2. 为什么 RRF 和 CE 要分层？

RRF 解决：

```text
heterogeneous retrieval fusion
```

CE 解决：

```text
fine-grained semantic ordering
```

职责不同。

------

### 3. 为什么不扩大 top8 再跑 CE？

因为当前 WP 的实验目标是验证：

> CE reranking 有没有价值。

如果同时把：

```text
8 → 50
```

那么提升可能来自：

```text
candidate recall ↑
```

而不是：

```text
reranker quality ↑
```

变量就混了。

------

### 4. 为什么不用 CE score 和 RRF score 加权？

它们不是天然同尺度：

```text
RRF score
≈ rank-derived

CE score
≈ learned relevance logit
```

直接：

```text
a * RRF + b * CE
```

需要额外 calibration / normalization / tuning。

第一版选择：

```text
RRF 做 candidate generation
CE 完全负责 final ordering
```

实验更干净。

------

### 5. 为什么 technical failure 不 fallback RRF？

Benchmark 场景如果：

```text
CE fail
→ RRF fallback
```

最终 300 queries 会变成：

```text
一部分 CE
+
一部分 RRF
```

形成 mixed population。

这时你不能再说：

> 这是 Cross-Encoder 的 NDCG。

所以 benchmark 应 fail closed。

------

### 6. 为什么模型资产需要 hash？

确保：

```text
experiment A model
==
experiment B model
```

而不是只相信目录名/model name。

------

### 7. 为什么最终 REJECT 还说实验成功？

因为：

```text
工程实验成功
≠
candidate 通过 release gate
```

实验成功意味着：

- 真实模型运行；
- 300/300；
- provenance 完整；
- 指标可信；
- Gate 正常工作。

而 Gate 的职责就是允许：

```text
候选被 REJECT
```

------

# 二十、这次最好的 Bad Case

我最推荐面试时讲：

## “SciFact 主 benchmark 明显改善，但候选仍被 Gate REJECT”

背景：

```text
RRF NDCG@3 = .6552
CE  NDCG@3 = .6812

提升：
+0.026
```

本来已经明显超过：

```text
+0.01 primary threshold
```

而且：

```text
MRR ↑
NDCG@5 ↑
rescue > regression
improved > degraded
```

SciFact 所有 Gate 都 PASS。

但是 Synthetic：

```text
MRR:
1.0 → .823

NDCG@3:
.988 → .766

NDCG@5:
.988 → .802
```

于是：

```text
CE_CANDIDATE = REJECT
```

处理方式：

> 没有为了保住漂亮的 SciFact 指标去修改 gate，也没有马上调参重新跑，而是保留 REJECT，并分析 synthetic baseline 存在明显 ceiling effect，把它记录为下一版 evaluation design 的输入。

这个故事同时包含：

```text
RAG
Evaluation
Regression
Metrics
Experiment Design
Guardrail
Truthfulness
Engineering Tradeoff
```

非常适合面试。

------

# 二十一、1 分钟面试版

> 在 RAG 优化阶段，我先做了 Dense/BM25 的 Hybrid Retrieval，并用 RRF 对两个通道进行 rank fusion。RRF 提升了 Top5 coverage，但 Top3 排序还有退化，所以后面增加了 Cross-Encoder reranking。
>
> 为了控制变量，我固定 RRF top8 candidate set，Cross-Encoder 只能重新排序，不能扩召回或过滤候选。模型使用 pinned revision 和 asset digest 离线加载，并记录每个 query 的 pre/post rank provenance。
>
> 在 SciFact 300 上，300 条全部成功。相对 RRF，NDCG@3 从 0.655 提升到 0.681，MRR 从 0.667 提升到 0.682，NDCG@5 也提升，同时 rescue/regression 和 rank-transition 都是净正向。
>
> 但我们在实验前冻结的 acceptance gate 要求 synthetic regression 为零，而 synthetic 24 上 MRR 和 NDCG 有明显下降，所以最后候选被机械 REJECT。我没有根据结果修改 threshold。这个实验让我把 RAG 优化从单纯看 aggregate metric，进一步做到了 provenance、case-level regression 和 pre-frozen release gate。

------

## WP3 最终真实性边界

可以说：

- Cross-Encoder 真实离线模型已加载；
- SciFact 300/300 真实通过；
- synthetic 24 真实执行；
- SciFact MRR/NDCG 真实改善；
- `CE_CANDIDATE = REJECT`；
- CPU latency 已真实测量；
- production default 没有切换。

不能说：

- Cross-Encoder 已在生产启用；
- CE 全面优于 RRF；
- Recall 得到了提升；
- synthetic regression 已解决；
- 该模型是最优 reranker；
- 当前 latency 是 production SLO。