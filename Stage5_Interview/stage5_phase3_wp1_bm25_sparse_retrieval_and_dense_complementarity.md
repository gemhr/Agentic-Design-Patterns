当前模型：GPT-5.6 Sol。

# Stage5-Phase3-WP1 学习总结

## BM25 Sparse Retrieval Foundation（BM25 稀疏检索基础）

本 WP 已经真实完成，并且最重要的价值不是“BM25 分数高不高”，而是：

> **我们终于建立了一个与 Dense 完全独立的 Sparse Retrieval Channel，并通过 300 条 SciFact Query 实际证明：BM25 虽然整体指标低于当前 Dense-led Pipeline，但确实能救回一部分 Dense 完全召不回来的 Case，因此下一步 Dense + BM25 + RRF 有了真实实验依据。**

最终状态：

```
STAGE5_PHASE3_WP1_BM25 = PASS
```

Dense + BM25 Fusion、RRF、CrossEncoder 均未开始。10_bm25_sparse_retrieval_foundation.mdMD

------

# 一、这个 WP 实际解决了什么

WP1 之前，我们只有：

```
Current Retrieval Pipeline
=
Dense
+
$contains keyword supplement
+
heuristic rerank
```

虽然存在 lexical supplement，但它只是：

```
Chroma $contains
+
fixed score 0.55
```

并不是 BM25。

WP1 之后新增：

```
Bm25SparseIndex
```

作为独立 Sparse Index Owner，只负责：

```
build
load
top-k sparse retrieval
```

不负责：

```
Dense
RRF
CrossEncoder
Selection
Generation
Evaluation
```

这保证了 BM25 是一个真正独立、可单独测量的 Retrieval Channel。10_bm25_sparse_retrieval_foundation.mdMD

------

# 二、BM25 为什么和原来的 Keyword Supplement 不一样

原来的：

```
$contains("term")
```

本质上更接近：

> 文档里有没有这个字符串。

而 BM25 会综合：

```
TF
+
IDF
+
Document Length Normalization
```

也就是不仅考虑：

> 这个词有没有出现。

还考虑：

> 出现多少次、这个词有多稀有、这篇文档有多长。

本 WP 固定的公式是：

```
idf(t) =
log(
    1 +
    (N - df(t) + 0.5)
    /
    (df(t) + 0.5)
)
```

以及：

```
score(q,d) =
Σ idf(t) *
tf(t,d) * (k1 + 1)
/
(
    tf(t,d)
    +
    k1 * (1 - b + b * dl / avgdl)
)
```

参数：

```
k1 = 1.2
b  = 0.75
```

而且是在 Benchmark 之前冻结，没有看完 SciFact 成绩后再调参。10_bm25_sparse_retrieval_foundation.mdMD

------

# 三、BM25 中三个最重要的变量

## 1. TF（Term Frequency，词频）

一个词在 Document 中出现得越多：

```
tf ↑
→ relevance 往往 ↑
```

但 BM25 不是线性增加。

不会：

```
出现 10 次
=
出现 1 次的 10 倍价值
```

而是具有饱和效应。

这也是：

```
k1
```

控制的重要部分。

------

## 2. IDF（Inverse Document Frequency，逆文档频率）

如果一个词：

```
几乎所有 Document 都有
```

它没有什么区分度。

例如：

```
the
system
data
```

而：

```
TNFAIP3
Albendazole
CTCF
```

这种稀有词的检索价值通常更高。

所以：

```
df 越小
→ IDF 越高
```

BM25 特别擅长：

```
专有名词
API 名
错误码
类名
函数名
缩写
数字标识
```

这正是以后 Hybrid Retrieval 要保留 Sparse Channel 的一个主要原因。

------

## 3. Document Length Normalization（文档长度归一化）

如果不考虑文档长度：

一篇很长的 Document：

```
因为内容很多
→ 很容易自然出现 Query Term
```

可能获得不合理优势。

BM25 使用：

```
dl / avgdl
```

对这种现象做修正。

其中：

```
b = 0.75
```

控制长度归一化强度。

------

# 四、k1 和 b 分别控制什么

## k1

主要控制：

```
TF saturation
```

也就是一个 Term 重复出现时，额外出现一次还能增加多少分。

简单理解：

```
k1 越大
→ 更看重重复词频

k1 越小
→ TF 更快饱和
```

本项目：

```
k1 = 1.2
```

------

## b

控制：

```
Document Length Normalization
```

简单理解：

```
b = 0
→ 完全忽略文档长度

b = 1
→ 完整执行长度归一化
```

本项目：

```
b = 0.75
```

这一组是常见 BM25 默认附近参数，但面试中重点不是背数值，而是说明：

> 参数是在 Benchmark 之前冻结的，没有为了 SciFact Test Set 调成更漂亮的数字。

------

# 五、Tokenizer 为什么也是 Retrieval Contract

这个 WP 一个容易被忽视但很重要的点是：

> BM25 公式相同，不代表检索结果一定相同。

因为：

```
Text
↓
Tokenizer
↓
Terms
↓
TF / DF / IDF
↓
BM25 Score
```

Tokenizer 直接决定 Index 里到底有哪些词。

本次冻结：

```
bm25-unicode-lexical-tokenizer.v1
```

流程：

```
Unicode NFKC
↓
casefold()
↓
deterministic regex lexical tokenization
```

并保留 ASCII 技术标识符内部的一些连接符，比如：

```
_
.
@
/
+
:
#
-
```

10_bm25_sparse_retrieval_foundation.mdMD

这对于代码、API、错误码类知识库尤其重要。

------

# 六、为什么 Tokenizer 也必须版本化

假设今天：

```
OutputGate
```

被切成：

```
outputgate
```

明天改成：

```
output
gate
```

BM25 的：

```
TF
DF
IDF
posting list
```

全部可能变化。

所以 Sparse Index Identity 不只是：

```
Corpus
+
k1
+
b
```

还必须包含：

```
Tokenizer Version
```

这也是为什么当前 BM25 Cache Key 包含：

```
algorithm ref
tokenizer ref
k1
b
manifest
corpus identity
```

而 Embedding 不进入 Sparse Cache Key。10_bm25_sparse_retrieval_foundation.mdMD

------

# 七、Sparse Index 和 Dense Index 为什么要分开

现在已经形成：

```
Same 9548 Chunks
        │
        ├──────────────┐
        │              │
        v              v
Dense Vector Index   BM25 Sparse Index
        │              │
Embedding-dependent  Lexical-dependent
```

Dense Index 依赖：

```
Embedding Model
Embedding Dimension
Embedding Config
```

BM25 Index 依赖：

```
Tokenizer
BM25 Formula
k1
b
```

所以两个 Cache Identity 必须独立。

例如：

```
Embedding model changed
```

应该：

```
Dense Cache invalid
BM25 Cache still valid
```

而：

```
Tokenizer changed
```

应该：

```
BM25 Cache invalid
Dense Cache unaffected
```

这就是典型的：

> **按真正语义依赖拆分 Cache Ownership。**

------

# 八、为什么 BM25 不使用 Dense 的 `minimum_score=0.55`

这是这个 WP 一个非常重要的工程边界。

Dense score 和 BM25 score：

```
不是同一个概率
也不是同一个量纲
```

如果写：

```
if bm25_score >= 0.55:
    ...
```

这个 `0.55` 没有任何理论依据。

因此本 WP BM25-only 是：

```
BM25 raw ranking
↓
Top 8
↓
Document Projection
↓
Evaluation
```

没有：

```
Dense minimum_score
heuristic rerank
$contains supplement
```

10_bm25_sparse_retrieval_foundation.mdMD

也正因为 Score 不可直接比较，下一步融合才选择：

```
RRF
```

而不是直接：

```
0.5 * dense_score
+
0.5 * bm25_score
```

------

# 九、为什么 `retrieved_items == ranked_items`

因为本 WP 只评价 BM25 本身。

流程：

```
BM25
↓
Raw ranked candidates
```

没有额外：

```
Reranker
```

所以：

```
retrieved_items
=
ranked_items
```

这是刻意设计，不是功能没做完。

否则如果加入 Heuristic Rerank：

```
BM25
+
Heuristic
```

最后就无法判断：

> 分数到底来自 BM25，还是来自现有 Reranker。

------

# 十、SciFact 最终结果

BM25 真实跑了：

```
300 / 300 queries
```

结果：

| Metric   | BM25   |
| -------- | ------ |
| Recall@1 | 0.5036 |
| Recall@3 | 0.6500 |
| Recall@5 | 0.7064 |
| MRR      | 0.6001 |
| NDCG@3   | 0.5955 |
| NDCG@5   | 0.6195 |

10_bm25_sparse_retrieval_foundation.mdMD

而 Current Pipeline 是：

```
Recall@1 = 0.5451
Recall@3 = 0.7307
Recall@5 = 0.7763

MRR      = 0.6632

NDCG@3   = 0.6617
NDCG@5   = 0.6811
```

所以：

```
BM25 overall
<
Current Dense-led Pipeline
```

但这并不意味着 BM25 没价值。

------

# 十一、这次真正最重要的结果：Complementarity

真正决定我们下一步是否值得做 Hybrid 的，是这个表：

| K    | Both Hit | Current-only Hit | BM25-only Hit | Both Miss |
| ---- | -------- | ---------------- | ------------- | --------- |
| @1   | 132      | 42               | 24            | 102       |
| @3   | 180      | 42               | 21            | 57        |
| @5   | 199      | 36               | 19            | 46        |

10_bm25_sparse_retrieval_foundation.mdMD

重点：

```
Current miss + BM25 hit @5 = 19
```

也就是：

> 当前 Pipeline Top5 召不回来的 Query 中，有 19 个被 BM25 找回。

------

# 十二、Dense Miss Rescue 更能说明问题

前一个 WP 已经发现：

```
Dense retrieval miss = 60
```

也就是 Relevant Document 连 Candidate Set 都没进去。

这次 BM25：

```
60 个 Dense miss
↓
救回 19 个
```

10_bm25_sparse_retrieval_foundation.mdMD

约：

```
31.7%
```

的 Dense Miss 被 BM25 Candidate Channel 找回。

这就是我们下一 WP 做：

```
Dense + BM25 + RRF
```

最直接的实验依据。

注意，这里不是说：

> Hybrid 一定提升 31.7%。

只是说明：

> **两个 Retrieval Channel 的错误集合并不完全重叠。**

这就是 Complementarity（互补性）。

------

# 十三、为什么“BM25 总体更差但仍然值得保留”

假设：

```
Dense hit 80%
BM25 hit 70%
```

很多人会直接决定：

> BM25 更差，删掉。

这是错误的评价方式。

真正应该看：

```
Dense miss 的 Case
BM25 能不能找回来
```

如果：

```
Dense misses A/B/C
BM25 hits A/B
```

那 BM25 就有 Hybrid 价值。

本次真实数据正是如此：

```
BM25 aggregate lower
+
BM25 rescues 19 current top5 misses
```

因此：

> BM25 的价值不是替代 Dense，而是提供不同的 Retrieval Error Distribution。

------

# 十四、一个很好的真实 BM25 Win

qid `94`：

```
Albendazole is used to treat lymphatic filariasis.
```

Current Pipeline：

```
Top5 miss
Dense retrieval miss
```

BM25：

```
relevant doc rank 1
```

10_bm25_sparse_retrieval_foundation.mdMD

这非常符合 Sparse Retrieval 的典型优势：

```
Albendazole
lymphatic filariasis
```

具有很强词法区分度。

------

# 十五、Dense 也有 BM25 救不了的优势

qid `54`：

```
AMP-activated protein kinase (AMPK) activation increases inflammation-related fibrosis in the lungs.
```

Current：

```
relevant doc rank 1
```

BM25：

```
top5 miss
```

10_bm25_sparse_retrieval_foundation.mdMD

这就是为什么我们不能：

```
BM25 替换 Dense
```

正确方向是：

```
Dense
+
BM25
```

两者各自覆盖不同 Query。

------

# 十六、还有 46 个 Both-Miss

Top5：

```
Current miss
+
BM25 miss
=
46
```

10_bm25_sparse_retrieval_foundation.mdMD

这也提醒我们：

> Hybrid 并不是万能的。

以后即便 RRF 把两个 Channel 合起来，仍然可能存在：

```
两边都召不回来
```

这些 Case 可能需要：

```
better embedding
query expansion
better tokenizer
larger candidate pool
query rewrite
```

但都不是现在 WP1 的 scope。

------

# 十七、BM25 延迟表现

SciFact：

```
mean = 19.89 ms
P50  = 14 ms
P95  = 96 ms
```

BM25 Index Cold Build：

```
3.281 s
```

10_bm25_sparse_retrieval_foundation.mdMD

相比 Dense：

```
Dense index build
≈ 90 min
```

Sparse Index 构建成本明显低很多。

原因是：

```
BM25
→ tokenize
→ term statistics
→ inverted postings
```

没有：

```
9548 × neural model inference
```

------

# 十八、Synthetic Dataset 的意义也再次体现出来

Synthetic BM25：

```
Recall@1 = 0.8667
Recall@3 = 0.9583
Recall@5 = 0.9583
MRR      = 1.0
NDCG@3   = 0.9606
```

10_bm25_sparse_retrieval_foundation.mdMD

它甚至比 Current Pipeline 的部分 synthetic 指标更好。

但不能因此说：

> BM25 比 Dense 更强。

因为 synthetic corpus 有大量：

```
类名
字段名
API path
术语
错误码
```

天然适合 lexical retrieval。

所以两套 Dataset 的角色进一步清晰：

```
Synthetic
→ Contract / lexical diagnostic / smoke

BEIR SciFact
→ Primary public retrieval benchmark
```

------

# 十九、本 WP 涉及名词 / 概念速览

1. **Sparse Retrieval（稀疏检索）**：基于词项统计而不是神经网络向量进行检索。
2. **BM25**：基于 TF、IDF 和 Document Length Normalization 的经典概率相关性排序算法。
3. **TF（词频）**：Term 在某个 Document 中出现的次数。
4. **DF（文档频率）**：包含某 Term 的 Document 数量。
5. **IDF（逆文档频率）**：衡量 Term 在整个 Corpus 中的区分度。
6. **Document Length Normalization（文档长度归一化）**：降低长文档因为自然包含更多词而获得的不公平优势。
7. **k1**：控制 TF Saturation 的 BM25 参数。
8. **b**：控制 Document Length Normalization 强度的 BM25 参数。
9. **Tokenizer（分词器）**：把原始文本转换为 BM25 使用的 Term Sequence。
10. **NFKC**：Unicode Normalization Form KC，用于统一一些等价字符表示。
11. **casefold**：比简单 lowercase 更适合 Unicode 的大小写规范化操作。
12. **Inverted Index（倒排索引）**：从 Term 映射到包含该 Term 的 Document/Chunk。
13. **Posting List（倒排列表）**：某个 Term 对应的 Document/Chunk 及其词频信息集合。
14. **Sparse Index Cache（稀疏索引缓存）**：持久化 BM25 Index，避免重复 tokenize 和 build。
15. **Complementarity（互补性）**：两个 Retrieval Channel 失败 Case 不完全重合，因此组合后可能获得更高覆盖率。
16. **Dense Miss Rescue**：Dense 没有召回 Relevant Item，但 Sparse Channel 成功召回。
17. **Both Hit**：Dense 和 BM25 都成功召回。
18. **Both Miss**：两个 Channel 都没有召回 Relevant Item。
19. **Raw Ranking（原始排序）**：没有额外 Reranker 干预的 BM25 直接排序结果。
20. **Candidate Budget（候选预算）**：每个 Retrieval Channel 最多返回的候选数量，本 WP 固定为 8。

------

# 二十、工程构建方法类提问

## Q1：什么时候适合引入 BM25？

当 Corpus 中包含较多：

```
专有名词
错误码
类名
函数名
字段
缩写
数字
精确产品名
```

Dense 可能因为 Semantic Approximation 丢失词面信号，而 BM25 通常很有补充价值。

------

## Q2：为什么不能直接把 Dense Score 和 BM25 Score 相加？

因为两边 Score 的来源和尺度完全不同：

```
Dense
→ vector similarity

BM25
→ lexical statistical relevance
```

例如：

```
Dense 0.82
BM25 12.6
```

没有理由认为：

```
0.82 + 12.6
```

有任何统一语义。

因此通常需要：

```
Rank-based Fusion
```

例如下一 WP 的 RRF。

------

## Q3：为什么 BM25 Candidate Limit 也固定为 8？

为了使：

```
Current Channel
vs
BM25 Channel
```

拥有相同的 per-channel candidate budget。

否则：

```
Dense top8
vs
BM25 top100
```

再说 BM25 Recall 高：

是不公平的。

------

## Q4：为什么不调 k1 / b 来提高 SciFact 分数？

因为 SciFact Test Set 已经是我们的 Benchmark。

如果：

```
看 Test Result
→ 调 k1/b
→ 再测 Test
```

实际上是在：

```
test-set overfitting
```

所以本 WP 在 Benchmark 前冻结：

```
k1=1.2
b=0.75
```

------

## Q5：为什么不做 stemming？

因为本 WP 的主要目标是建立：

```
Minimal Deterministic BM25 Channel
```

而不是一次把 Analyzer 调到极致。

如果同时：

```
BM25
+
stemming
+
stopwords
+
synonym
+
query expansion
```

即使指标提高，也不知道哪项贡献最大。

------

# 二十一、本 WP 的 Bad Case 总结

## Bad Case 1：Dense 完全漏召回，但 BM25 Rank 1 命中

**真实性：真实。**

Case：

```
qid=94
```

Current：

```
Dense retrieval miss
```

BM25：

```
rank 1
```

说明：

```
Dense Semantic Retrieval
```

并不能替代所有：

```
Lexical Retrieval
```

知识点：

```
Hybrid Retrieval 的理论基础不是“算法越多越好”
而是不同 Retrieval Channel 的 Error Distribution 不同。
```

------

## Bad Case 2：Dense Rank 1，而 BM25 Top5 Miss

**真实性：真实。**

Case：

```
qid=54
```

说明：

BM25 本身也无法替代 Dense。

所以：

```
BM25-only
```

不是最终架构。

------

## Bad Case 3：Current 与 BM25 都 Miss

**真实性：真实。**

Case：

```
qid=1
```

Top5 Both-Miss 总计：

```
46
```

说明：

Hybrid 只能利用已有 Channel 的互补性。

如果：

```
所有 Channel 都没有 Relevant Candidate
```

RRF 也无能为力。

------

# 二十二、30 秒面试版本

> 在 RAG 优化阶段，我先单独实现了一个 BM25 Sparse Retrieval Channel，没有直接和 Dense 做融合。BM25 使用固定的 Lucene-style IDF、k1=1.2、b=0.75，并使用版本化的确定性 Unicode Tokenizer，在和 Dense 完全相同的 9548 个 Chunk 上构建独立 Sparse Index。SciFact 300 Query 上 BM25 的总体 Recall、MRR、NDCG 低于当前 Dense Pipeline，但 Complementarity Analysis 发现当前 Dense 的 60 个 Retrieval Miss 中有 19 个被 BM25 找回。因此 BM25 的价值不是替代 Dense，而是提供不同的错误分布，这为下一步 Dense + BM25 + RRF 提供了真实实验依据。

------

# 二十三、2 分钟面试版本

> 在 Advanced RAG 阶段，我没有直接上 Hybrid Retrieval，而是先把 BM25 独立出来做单变量实验。
>
> 原系统其实已经有一个 Chroma $contains 的关键词补充通道，但它只是字符串包含匹配并给固定启发式分数，并不是 BM25。所以我在 LocalAgent 中新增了独立 `Bm25SparseIndex`，只负责 Sparse Index 的 Build、Load 和 Top-K Retrieval。
>
> BM25 使用固定的 Lucene-style IDF，k1=1.2、b=0.75；Tokenizer 使用 Unicode NFKC、casefold 和确定性 lexical tokenization。算法、Tokenizer 和参数都在 Benchmark 前冻结，避免对 SciFact Test Set 做调参。
>
> 为保证公平，BM25 和 Dense 使用完全相同的 9548 个 Chunk、同一 SciFact qrels、同一 Document Projection，并且 per-channel Candidate Budget 都固定为 8。BM25-only 不应用 Dense 的 0.55 Score Threshold，也不走原来的 Heuristic Reranker，因为两种 Score 不同量纲，我希望先测出 BM25 自身能力。
>
> 最终 SciFact 300 Query 上，BM25 的 Recall@5 大约 0.706，低于当前 Pipeline 的 0.776；MRR 和 NDCG 也略低。但是 Case-level Complementarity Analysis 发现，在当前 Dense Pipeline 的 60 个完全漏召回 Query 中，有 19 个能被 BM25 找回来，同时 Dense 也能找回不少 BM25 Miss。
>
> 因此实验结论不是“BM25 比 Dense 更好”，而是两个 Retrieval Channel 的错误集合具有明显互补性。这正是下一阶段用 RRF 做 Rank Fusion 的工程依据。

------

# 二十四、高频面试追问 + 参考回答

### Q1：为什么不直接使用 Elasticsearch BM25？

因为这个阶段的目标是把 Sparse Retrieval 集成进现有 LocalAgent Runtime，并保持离线、轻量和可控。为 SciFact Benchmark 单独引入 Elasticsearch/Java 会增加部署和测试复杂度，而当前只需要一个确定性 BM25 Channel 来进行相同 Pipeline 的 Before/After Comparison，所以采用了最小内部实现。

### Q2：自己实现 BM25 不怕公式错吗？

所以我没有只做 E2E，而是对 BM25 Core 做了人工可核算的小语料测试，包括 TF、多词频、IDF、长度归一化、重复 Query Token、Tie-break、finite score 等，然后才跑真实 SciFact Benchmark。10_bm25_sparse_retrieval_foundation.mdMD

### Q3：为什么重复 Query Token 要重复贡献？

当前冻结 Contract 明确定义：

```
query duplicate token
→ repeated contribution
```

这是本实现的确定性语义。关键不是说这是唯一正确实现，而是这个行为必须明确、版本化、可测试，避免以后 Tokenizer 或 Query Processing 静默改变 Benchmark。

### Q4：为什么 BM25 的 MRR 比 Recall@1 高？

Recall@1 只看第一名窗口中相关文档覆盖情况；MRR 看第一个 relevant item 的 Reciprocal Rank，所以 relevant item 出现在第 2、第 3 等位置仍然能贡献：

```
1/2
1/3
...
```

因此两者不是同一指标。

### Q5：BM25 整体更差，为什么还要 RRF？

因为 aggregate score 不足以判断 Hybrid 价值。真实数据证明 BM25 在 Current Top5 Miss 中独立找回了 19 个 Case，这说明 Sparse 和 Dense 的错误集合不同。RRF 的目标就是利用这种 complementary ranking signal。

### Q6：为什么 RRF 比 Score Normalization 更自然？

Dense 和 BM25 Score 没有统一量纲。RRF 直接基于：

```
rank
```

而不是原始 score，因此无需假设：

```
Dense 0.8
和
BM25 8.0
```

应该如何映射到同一个概率尺度。

### Q7：为什么本 WP 不加 Rerank？

因为我们要单独知道 BM25 能做什么。如果 BM25 后面再加现有 heuristic rerank，就无法把 Case Improvement 归因给 BM25 本身。Cross-Encoder 也是后续独立 WP。

### Q8：BM25 Cache 为什么不依赖 Embedding？

因为 BM25 Index 完全基于 Term Statistics，不使用 Embedding Model。Embedding 发生变化，只应该让 Dense Index Cache 失效，不应重建 Sparse Index。

### Q9：CJK 按单字切是不是很差？

它是当前最小 deterministic tokenizer 的已知限制，文档也明确没有把它称为 production-quality Chinese analyzer。10_bm25_sparse_retrieval_foundation.mdMD 当前 Primary Benchmark 是英文 SciFact，中文 synthetic 主要承担 Smoke/Contract 检查。如果未来专门优化中文 Sparse Retrieval，应该独立 version analyzer，而不是在这次 Benchmark 后偷偷修改 Tokenizer。

### Q10：19 个 Rescue 能直接说明 RRF 一定提升吗？

不能。

它只能证明：

```
有 fusion potential
```

而不能证明：

```
fusion result 一定提高
```

因为融合后还涉及：

```
rank conflict
duplicate candidate
RRF constant
final candidate budget
```

所以必须在下一 WP 真实执行 RRF 后再看指标。

------

# 二十五、一个需要记住的真实性边界

WP1 已经证明：

```
BM25 and Dense are complementary
```

但只能在：

```
BEIR_SCIFACT_LOCALAGENT_ADAPTED
+
当前冻结配置
```

条件下这么说。

不能升级成：

> BM25 能修复 31.7% 的生产 RAG Dense Miss。

生产 Corpus、Query Distribution 和 Analyzer 都没有验证。

准确表达是：

> 在当前 SciFact 公开 Benchmark 的 60 个 Current Dense Retrieval Miss 中，BM25 top8 Candidate Channel 找回了 19 个。

10_bm25_sparse_retrieval_foundation.mdMD

------

# 二十六、关于文档里那个 Chunk Digest 差异

这一点值得你知道，但目前不影响 WP1 PASS。

旧 WP0B 文档记录：

```
8CC45BD...
```

当前 READY Cache canonical digest：

```
6f3f2d3c...
```

文档没有把两者说成同一个 SHA，而是明确称为“摘要语义漂移”，并通过：

```
(document_id,
 chunk_id,
 benchmark_document_id,
 content_hash)
```

逐项 exact equality 证明 BM25 与 Dense 使用的是同一批 Chunk。10_bm25_sparse_retrieval_foundation.mdMD

因此当前：

```
CONTRACT_CORRECTNESS = OK
```

但以后有机会应该尽量统一：

```
Manifest File Hash
```

和：

```
Canonical Chunk Identity Digest
```

的命名，避免面试或文档里出现两个 SHA 时造成误解。

不要为了这个现在回头修改历史 Baseline。

------

# 二十七、本 WP 推荐面试材料文件名

```
docs/interview_materials/
stage5_phase3_wp1_bm25_sparse_retrieval_and_dense_complementarity.md
```

------

# 二十八、这个 WP 最值得你记住的一句话

> **Hybrid Retrieval 的理由不是“Dense 和 BM25 都很流行”，而是先分别测量两个 Channel，证明它们的 Error Set 不完全重合，再通过 Fusion 利用这种互补性。**

你现在已经有了完整证据链：

```
Current Dense Miss = 60
        ↓
BM25 rescues 19
        ↓
BM25 aggregate still lower
        ↓
Two channels are complementary
        ↓
WP2 RRF has empirical justification
```

本 WP 学习完成。

下一步按照当前路线是：

```
Stage5-Phase3-WP2
Dense + BM25 + RRF
```

但按照我们的长期约定，这里先停，不自动进入 WP2。