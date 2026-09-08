当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase3 — Advanced RAG 学习 / 面试总结

Phase3 的核心不是“堆更多 RAG 技术”，而是建立了一套 **Evaluation-Driven Optimization（评估驱动优化）** 方法：

```text
先建立可信 Baseline
        ↓
Sparse / Dense 多路召回
        ↓
RRF 融合
        ↓
Cross-Encoder 重排
        ↓
No-Answer / Abstention 实验
        ↓
Context Selection 优化
        ↓
用冻结数据、真实 Benchmark 和独立 Gate 判断：
哪些方案值得保留，哪些应该 REJECT
```

最终状态：

```text
Stage5-Phase3 = COMPLETE

WP0   RAG Evaluation Environment & Quality Baseline ✅
WP0B  Public Retrieval Benchmark Foundation ✅
WP0/0B Closeout & Persistent Cache ✅
WP1   BM25 Sparse Retrieval ✅
WP2   Dense + BM25 + RRF ✅
WP3   Cross-Encoder Reranking ✅
WP4   No-Answer Evidence Threshold ✅
       └─ REJECT_NO_FEASIBLE_POLICY
WP5   Citation / Context Selection ✅
       └─ Fixed Top-K comparison complete
          BEST_K = NOT_SELECTED
```

------

# 一、Phase3 最重要的工程主线

你可以把整个 Phase3 理解成五层。

```text
                    RAG Quality Optimization
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
     Recall               Ranking              Context
       │                    │                    │
 Dense / BM25             RRF / CE          Top-K Selection
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                      Evaluation Authority
                            │
                 Dataset / GroundTruth / Cache
                            │
                     Reproducible Benchmark
```

Phase3 实际解决了三个典型 RAG 问题：

1. **能不能找到正确知识？**
   - Dense Retrieval
   - BM25
   - Hybrid Retrieval
2. **找回来以后能不能把正确知识排得更靠前？**
   - RRF
   - Cross-Encoder
3. **排好以后到底应该给 LLM 多少上下文？**
   - Context Selection
   - Noise / Token Budget

另外还研究了：

> **“证据不足时是否应该拒答？”**

这就是 WP4 No-Answer Threshold。

------

# 二、WP0 — RAG Evaluation Environment & Quality Baseline

Phase3 没有一上来就做 BM25/RRF。

第一件事是建立一个固定、可复现的评估环境。

核心内容：

```text
Synthetic Evaluation Corpus
Dataset / Suite / Ground Truth
Recall@K
MRR
NDCG
Qwen3-Embedding-0.6B
```

Embedding 固定为：

```text
Qwen3-Embedding-0.6B
dimension = 1024
normalize = true
```

### 为什么必须先建立 Baseline？

如果没有 baseline：

```text
“我加了 BM25 感觉更好了”
“我加了 Cross-Encoder 感觉更准了”
```

都没有意义。

真正的优化必须是：

```text
Baseline
   ↓
Change one variable
   ↓
Benchmark
   ↓
Before / After
```

这就是 Phase3 最重要的方法论：

> **Optimization without evaluation is guessing.**

------

# 三、WP0B — Public Retrieval Benchmark Foundation

只用自己构造的 Synthetic Dataset 有一个明显问题：

> 数据可能过于适合自己的系统。

所以又加入了真实公开 Benchmark：

```text
BEIR SciFact
```

规模：

```text
5183 documents
300 test queries
document-level qrels
```

但 LocalAgent 的 RAG 是：

```text
Document
  ↓
Chunk
  ↓
Chunk Retrieval
```

而 SciFact GroundTruth 是 document-level。

所以中间做了：

```text
Retrieved Chunk
     ↓
document_id
     ↓
Chunk → Document Projection
     ↓
与 qrels 比较
```

这是非常典型的真实 RAG Evaluation 问题：

> **Production retrieval unit 和 Benchmark relevance unit 经常不是一个粒度。**

------

# 四、Persistent Dense Cache 为什么重要

Dense Index 的 cold build 大约：

```text
~90 min
```

Warm reuse：

```text
~22 sec
```

如果每次做一个实验都重新 embedding：

```text
BM25
RRF
Cross Encoder
Threshold
Context Selection
```

整个 Phase3 会非常慢。

因此把：

```text
Corpus
Embedding Model
Splitter
Embedding Config
```

绑定成 cache identity。

然后要求：

```text
同样输入
→ 同样 cache
→ benchmark reproduction exact equal
```

这体现的是非常重要的工程思想：

> **实验基础设施首先要保证可复现，其次才是快。**

------

# 五、WP1 — BM25 Sparse Retrieval

这是 Phase3 第一个真正的 retrieval optimization。

## Dense 和 BM25 的核心区别

Dense Retrieval：

```text
Query
 ↓
Embedding
 ↓
Vector Similarity
```

擅长：

```text
语义相似
同义表达
自然语言问题
```

例如：

```text
Query:
“系统如何处理请求失败？”

Document:
“Invocation errors are retried...”
```

字面词不同，Dense 仍可能召回。

------

BM25：

```text
Query Tokens
   ↓
Term Frequency
Inverse Document Frequency
Document Length Normalization
```

擅长：

```text
精确名词
类名
函数名
错误码
产品名
技术术语
ID
```

例如：

```text
ToolExecutionService
CAS
HTTP 409
operation_id
```

这就是为什么 Agent / 后端知识库特别适合：

```text
Dense + Sparse
```

而不是 Dense-only。

------

# 六、BM25 的真正价值：Complementarity

WP1 的价值不只是：

> “我实现了 BM25。”

真正需要理解的是：

> **Dense 和 BM25 会救回彼此漏掉的 Query。**

存在三类 Query：

```text
Dense wins
BM25 wins
Both succeed
```

这就给 WP2 的 Hybrid Retrieval 提供了实验依据。

如果两个 channel 返回的结果几乎完全相同：

> 做 Hybrid 其实没有多少价值。

Hybrid Retrieval 成立的基础就是：

```text
retrieval complementarity
```

------

# 七、WP2 — Dense + BM25 + RRF

这是 Phase3 最核心的 Advanced RAG 能力之一。

整体：

```text
              Query
                │
       ┌────────┴────────┐
       ↓                 ↓
 Dense Retrieval      BM25 Retrieval
    Top8                Top8
       │                 │
       └────────┬────────┘
                ↓
        RRF Rank Fusion
                ↓
             Top8
```

------

# 八、为什么不用直接融合 Dense Score 和 BM25 Score？

因为两个分数不在同一量纲。

例如：

```text
Dense cosine:
0.72
0.68
0.61

BM25:
13.4
8.7
6.2
```

不能简单：

```text
0.72 + 13.4
```

也不能轻易说：

```text
0.7 × Dense + 0.3 × BM25
```

因为还要做 score normalization / calibration。

所以用了：

# RRF — Reciprocal Rank Fusion（倒数排名融合）

公式：

```text
RRF(d) = Σ 1 / (k + rank_i(d))
```

Phase3：

```text
k = 60
rank 从 1 开始
```

核心思想：

> 不关心原始 score，只关心一个 document/chunk 在每个 channel 中排名多高。

所以非常适合：

```text
Dense
+
BM25
```

这种异构 retrieval channel。

------

# 九、RRF 的实验结果应该怎么讲

SciFact：

### Current route

```text
R@1     0.5451
R@3     0.7307
R@5     0.7763
MRR     0.6632
NDCG@3  0.6617
NDCG@5  0.6811
```

### RRF

```text
R@1     0.5567 ↑
R@3     0.7084 ↓
R@5     0.7878 ↑
MRR     0.6669 ↑
NDCG@3  0.6552 ↓
NDCG@5  0.6888 ↑
```

因此正确结论是：

> RRF 在 R@1、R@5、MRR、NDCG@5 上取得改善，但在 R@3 和 NDCG@3 上存在 regression。

不能说：

> RRF 全面击败 Dense。

这是一个很好的面试案例：

> **真实优化通常不是所有指标同时上涨。**

------

# 十、为什么 RRF 现在没有直接切 Production Default

这也是你刚才问过的重点。

因为 Phase3 是：

```text
Evaluation-Driven Optimization
```

不是：

```text
Production Migration
```

而且 RRF 并不是所有指标胜出。

所以当前：

```text
Dense + BM25 + RRF
= 已实现
= 已 benchmark
= 项目具备能力

LocalAgent Production Default
= 尚未切换
```

如果未来要 productionize：

最合理的是做一个很小的：

```text
RRF Productionization
```

然后补：

```text
真实业务 query regression
latency
fallback
failure handling
resource cost
```

不需要重新开发 Hybrid Retrieval。

------

# 十一、WP3 — Cross-Encoder Reranking

RRF 解决：

```text
多路 retrieval 的 rank fusion
```

但它仍然没有真正理解：

```text
Query 与 Document 的联合语义关系
```

Cross-Encoder 则不同。

Bi-Encoder / Dense：

```text
Query → vector
Document → vector

similarity(query_vector, doc_vector)
```

Cross-Encoder：

```text
[Query, Document]
       ↓
 Transformer
       ↓
 relevance score
```

所以通常排序精度更高。

代价：

```text
昂贵
慢
不能全库跑
```

典型架构：

```text
Retriever
 ↓
Top N
 ↓
Cross-Encoder
 ↓
Top K
```

这就是：

> **Retrieve broadly, rerank precisely.**

------

# 十二、Phase3 使用的 Cross-Encoder

模型：

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

路径：

```text
Dense + BM25
      ↓
     RRF
      ↓
    Top8
      ↓
Cross-Encoder
      ↓
Reordered Top8
```

注意：

Cross-Encoder：

```text
没有新增 candidate
没有删除 candidate
```

只是：

```text
permutation / reranking
```

------

# 十三、Cross-Encoder 实验结果

SciFact：

```text
RRF:
MRR     0.66689
NDCG3   0.65523
NDCG5   0.68883

RRF + CE:
MRR     0.68194
NDCG3   0.68120
NDCG5   0.70307
```

提升：

```text
MRR     +0.01505
NDCG3   +0.02597
NDCG5   +0.01424
```

Recall 不变。

这正符合 Cross-Encoder 定位：

> 它不负责 recall，主要负责 ranking。

------

# 十四、为什么最后 Cross-Encoder Candidate 仍然 REJECT？

因为 Synthetic hard guardrail 明显下降。

因此必须区分：

```text
Capability Result
vs
Candidate Decision
```

Capability：

```text
Cross-Encoder 能改善 SciFact ranking
✅ PROVED
```

Production candidate：

```text
当前具体 CE candidate
❌ REJECT
```

面试非常值得讲：

> 我不会因为 public benchmark 涨了就直接上线，还需要看我们自己的业务/合成 guardrail。

这是 Evaluation-Driven Optimization 的真正意义。

------

# 十五、WP4 — No-Answer Threshold

这个 WP 探索的是 RAG 中非常重要的问题：

> **什么时候模型应该拒答？**

传统 RAG：

```text
Query
 ↓
Retrieval
 ↓
无论证据好不好
 ↓
LLM Answer
```

风险：

```text
Retrieval evidence很弱
但 LLM仍然强行回答
→ hallucination
```

所以尝试：

```text
Evidence strong
→ ANSWER

Evidence weak
→ ABSTAIN
```

------

# 十六、WP4 使用了什么信号

简单 policy family：

```text
Top1 Score
+
Top1 - Top2 Margin
```

逻辑：

```text
if top1 >= threshold1
and margin >= threshold2
    ANSWER
else
    ABSTAIN
```

这是一种典型：

```text
Evidence-based Abstention
```

------

# 十七、为什么必须 Calibration / Evaluation 分离

Threshold 是一个参数。

如果：

```text
在 Evaluation Set 看结果
 ↓
调整 threshold
 ↓
再在同一 Evaluation Set 报结果
```

就是数据泄漏。

正确：

```text
CAL
 ↓
choose threshold
 ↓
LOCK
 ↓
untouched EVAL
```

这就是：

```text
Calibration → Lock → Evaluation
```

Phase3 对实验纪律要求非常严格。

------

# 十八、WP4 最终为什么 REJECT

共：

```text
19 × 27
=
513 configs
```

要求：

```text
False Answer = 0

AND

True Answer > False Abstain
```

结果：

```text
FA_ZERO_CONFIGS = 141

TA_GT_FAB_CONFIGS = 140

两者 intersection = 0
```

所以：

```text
FEASIBLE_CONFIG_COUNT = 0
```

最终：

```text
CALIBRATION_FAILED_NO_FEASIBLE_POLICY

WP4_CANDIDATE =
REJECT_NO_FEASIBLE_POLICY
```

------

# 十九、为什么 WP4 是一个“成功的失败实验”

因为目标不是：

> 一定找出 threshold。

而是：

> 判断这种简单 threshold policy 是否有效。

实验最后证明：

```text
Top1 + margin
```

不足以可靠区分：

```text
answerable
vs
weak / misleading evidence
```

所以没有偷偷：

```text
调 Dataset
删 hard case
改指标
降低约束
```

去制造一个 PASS。

这是 Phase3 最值得讲的工程故事之一。

------

# 二十、WP5 — Citation / Context Selection Optimization

WP5 研究的是：

> Retriever 已经排好以后，究竟给 LLM 几个 chunk？

```text
RRF Ranked Candidates
       ↓
      Top-K
       ↓
Serialized Context
       ↓
LLM
```

测试：

```text
K = 1,2,3,4
```

------

# 二十一、Context Selection 为什么是独立问题

Retrieval 的目标：

```text
找到 evidence
```

Context Selection 的目标：

```text
在有限 prompt budget 内
留下最有价值 evidence
```

所以：

```text
Retrieval Quality
≠
Context Quality
```

更多 context 可能意味着：

```text
更多 evidence
```

也可能意味着：

```text
更多 noise
更多 token
更多 distractor
```

所以：

> **More context is not always better.**

------

# 二十二、WP5 三个主要指标

## Context Support Coverage

```text
selected required support
/
expected required support
```

看：

> 该保留的证据有没有留下。

------

## Noise by Chunk

```text
selected non-support chunks
/
selected chunks
```

看：

> 选进来了多少非 required support。

------

## Noise by Token

```text
non-support token cost
/
full serialized context token cost
```

因为：

```text
1 chunk ≠ 固定 token 大小
```

所以 token-level noise 比仅统计 chunk 数更贴近真实 LLM cost。

------

# 二十三、为什么 WP5 真正用了 Generation Model Tokenizer

因为如果要说：

```text
385 tokens
vs
1493 tokens
```

就不能用：

```text
字符数估算
rough token estimator
fixture tokenizer
```

正式使用：

```text
qwen2.5-7b-instruct-q4_k_m.gguf

llama_cpp = 0.2.90

add_bos = false
special = false
```

这体现：

> **Measurement Instrument（测量工具）也是实验 Contract 的一部分。**

不仅 Dataset 要冻结：

```text
Tokenizer
Serializer
Tokenization mode
```

都应该冻结。

------

# 二十四、WP5 最终结果

8 个 eligible cases：

| K    | Coverage | Chunk Noise | Token Noise | Tokens |
| ---- | -------- | ----------- | ----------- | ------ |
| 1    | 1.0      | 0           | 0           | 385    |
| 2    | 1.0      | 0.50        | 0.491       | 757    |
| 3    | 1.0      | 0.667       | 0.660       | 1134   |
| 4    | 1.0      | 0.75        | 0.742       | 1493   |

最重要发现：

```text
8 / 8 eligible cases

Top1 candidate
已经是 expected support
```

所以：

```text
K ↑

Coverage 不增加
Noise ↑
Token ↑
```

最终：

```text
K1 Pareto dominates K4
K2 Pareto dominates K4
K3 Pareto dominates K4
```

------

# 二十五、为什么还是不能说“Top1 最好”

因为 WP5 是：

```text
Ablation / Comparison Experiment
```

不是：

```text
Policy Selection Experiment
```

你已经看过全部 K 的结果。

现在如果：

```text
看到 K1 最漂亮
→ 选择 K1
```

相当于：

```text
用 Evaluation Dataset 调参数
```

正确生产选择：

```text
新的 CAL dataset
 ↓
choose K
 ↓
lock K
 ↓
untouched EVAL
```

因此：

```text
K1 Pareto dominates K4
```

不等于：

```text
BEST_K = K1
```

------

# 二十六、为什么 Citation Correctness / Completeness 仍然没测

WP5 测的是：

```text
context 中有没有 support
```

不是：

```text
最终答案是否正确引用 support
```

必须区分：

```text
Retrieved
 ↓
Selected
 ↓
Serialized into Context
 ↓
Actually Used by Model
 ↓
Actually Cited
```

当前只做到中间层。

所以：

```text
Context Support Coverage
≠ Citation Completeness

Selected Support
≠ Citation Correctness
```

Phase3 明确保持：

```text
CITATION_CORRECTNESS =
NOT_EVALUATED

CITATION_COMPLETENESS =
NOT_EVALUATED
```

------

# 二十七、Phase3 形成的完整高级 RAG 思维

现在你已经可以从完整角度理解 RAG：

```text
                     Query
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
          Dense                Sparse
        Embedding               BM25
             │                   │
             └─────────┬─────────┘
                       ↓
                      RRF
                       ↓
                Candidate Ranking
                       ↓
              Cross-Encoder(optional)
                       ↓
               Context Selection
                       ↓
                  Context Budget
                       ↓
                    LLM
                       ↓
                   Answer
```

但是每一层都存在不同的 Evaluation：

```text
Retrieval
→ Recall@K

Ranking
→ MRR / NDCG

Context Selection
→ Support Coverage / Noise / Tokens

Generation
→ Correctness / Faithfulness

Abstention
→ Answer / Reject quality

Citation
→ Correctness / Completeness
```

这是一个很重要的系统性认识：

> **RAG Evaluation 不是一个分数，而是一组分层指标。**

------

# 二十八、Phase3 名词 / 概念速览

| 名词              | 一句话理解                                                   |
| ----------------- | ------------------------------------------------------------ |
| Dense Retrieval   | 用 embedding 语义相似度进行检索。                            |
| Sparse Retrieval  | 基于词项匹配的检索方式。                                     |
| BM25              | 基于 TF、IDF 和文档长度归一化的经典稀疏检索算法。            |
| Hybrid Search     | 同时使用 Dense 与 Sparse Retrieval。                         |
| RRF               | 使用排名而不是原始 score 融合多个 retrieval channel。        |
| Cross-Encoder     | Query 与 Document 联合编码并计算 relevance score 的重排模型。 |
| Recall@K          | 前 K 个结果中覆盖了多少 GroundTruth relevant documents。     |
| MRR               | 正确结果首次出现位置的倒数均值。                             |
| NDCG              | 考虑 relevance 与排名位置的 ranking quality 指标。           |
| Ground Truth      | 用于评价系统结果的权威正确答案。                             |
| Qrels             | Query 与 relevant document 的标准 relevance 标注。           |
| Reranking         | 对已有候选重新排序，而不是重新召回。                         |
| Abstention        | Evidence 不足时主动拒答。                                    |
| Calibration       | 用专用数据选择 threshold / policy 参数。                     |
| Evaluation        | 用未参与调参的数据验证冻结 policy。                          |
| Context Selection | 从 retrieval candidates 中决定哪些进入 LLM context。         |
| Context Noise     | 进入 context 但不属于 required support 的内容。              |
| Token Budget      | LLM 输入允许消耗的 token 预算。                              |
| Pareto Dominance  | 一个方案至少不损失核心收益，并在部分成本指标严格更好。       |
| Provenance        | 结果来自哪个 Dataset、Artifact、Model、Config 的可追溯链路。 |
| Authority         | 某个事实被谁定义和验证，而不只是“有一个 hash”。              |
| Sidecar           | 与主实验结果配套保存 identity / metrics / provenance 的结构化 artifact。 |

------

# 二十九、Phase3 最重要的工程设计方法

## 1. Baseline First

不要：

```text
先优化
→ 再想怎么证明
```

而应该：

```text
先 baseline
→ 再 optimization
```

------

## 2. Change One Variable

比如测试 Cross-Encoder：

```text
Retrieval candidates 固定
RRF 固定
Dataset 固定
只改变 reranking
```

否则无法知道提升来自哪里。

------

## 3. Public Benchmark + Domain/Synthetic Guardrail

Public benchmark：

```text
防止自建 Dataset 自嗨
```

Synthetic/domain：

```text
防止 public benchmark 与业务场景脱节
```

两者都需要。

------

## 4. Negative Result 也是结果

WP4：

```text
No feasible threshold
```

WP3：

```text
Cross-Encoder public提升
但 synthetic regression
```

这些并不是工程失败。

------

## 5. Evaluation 不能 Repair Runtime

如果 runtime 输出错了：

Evaluator 应：

```text
FAIL
```

而不是：

```text
偷偷修正
→ 再评估
```

否则你测的是 evaluator，不是 runtime。

------

# 三十、Phase3 最值得记住的 Bad Cases

### Bad Case 1：只看一个 Benchmark

SciFact 上 CE 提升就直接 production enable。

问题：

```text
domain regression 可能被掩盖
```

最终选择：

```text
candidate REJECT
```

------

### Bad Case 2：为了得到 Threshold 偷改数据

WP4 找不到可行 threshold 后：

```text
删掉 misleading cases
```

会让实验失去意义。

正确：

```text
REJECT policy family
```

------

### Bad Case 3：GroundTruth 控制 Retrieval

例如：

```text
知道正确 doc 是 A
→ retrieval 时特意保证 A 被加入 candidates
```

这叫 evaluation leakage。

GroundTruth：

```text
只能评价 observation
不能控制 observation
```

------

### Bad Case 4：Hash 被误认为 Authority

```text
artifact
正文=A
hash=hash(A)
```

只能证明：

> artifact 内部一致。

不能证明：

> A 是真正的 frozen source。

所以要 independent source authority。

------

### Bad Case 5：Fixture 冒充真实能力

Fixture tokenizer：

```text
tests PASS
```

不能证明：

```text
真实 GGUF tokenizer
在真实 execution environment 可运行
```

所以 WP5 最后专门做 real execution。

------

### Bad Case 6：实验比较直接变 Production Policy

WP5：

```text
K1表现最好
```

不能：

```text
立即生产 K=1
```

因为缺少新的 policy-selection experiment。

------

# 三十一、Phase3 的 Truth / Completion Boundary

现在面试时可以明确说：

### 已真实实现、评估

```text
BM25 Sparse Retrieval
Dense + BM25 Hybrid Retrieval
RRF Rank Fusion
Cross-Encoder Evaluation
No-Answer Threshold Calibration Experiment
Context Selection Benchmark
Real tokenizer token accounting
SciFact public benchmark
Synthetic/domain benchmark
```

### 已证明能力但没有生产启用

```text
Dense + BM25 + RRF
Cross-Encoder Reranking
```

### Candidate 被拒绝

```text
Cross-Encoder 当前具体 candidate
No-Answer top1+margin threshold policy
```

### 尚未选择

```text
Production Context K
```

### 尚未真正评估

```text
Citation Correctness
Citation Completeness
WP5 Generation Quality
```

### Production Default

```text
Phase3 没有自动改变 LocalAgent production retrieval default
```

这部分一定要诚实。

------

# 三十二、面试高频工程问题

### Q1：为什么 Hybrid Search 要同时使用 Dense 和 BM25？

因为 Dense 擅长语义召回，BM25 擅长关键词、专有名词、错误码和标识符；真实知识库中的 query 同时包含两类需求，两者存在互补性。

------

### Q2：为什么选择 RRF，而不是直接加权 Dense/BM25 score？

两路 score 不同量纲，需要额外 normalization/calibration；RRF 只依赖 rank，简单稳定，也更适合不同 retrieval channel 的融合。

------

### Q3：Cross-Encoder 为什么不直接检索全库？

因为它需要 Query 与每个 Document 联合推理，计算复杂度高，所以一般先由 cheap retriever 缩小 candidate set，再对 Top-N rerank。

------

### Q4：为什么 Recall 不变但 MRR/NDCG 提升？

因为 Cross-Encoder 没改变 candidate population，只改变 candidate 的顺序；因此 recall 可不变，而 ranking metrics 提升。

------

### Q5：为什么 RRF 没有直接上线？

因为 benchmark 存在 mixed result，而且 Phase3 的 Owner 是 evaluation-side optimization，不自动拥有 production default change。

------

### Q6：为什么 No-Answer Threshold 实验最后没有 threshold？

因为冻结 calibration search space 中不存在满足安全约束的 feasible policy；继续调数据或规则只为得到 PASS 会造成实验污染。

------

### Q7：为什么 Top1 结果最好却不能直接选 K=1？

因为这次实验属于 ablation/comparison；如果根据同一 evaluation population 选择参数，会产生 selection bias，应重新做 CAL→lock→untouched EVAL。

------

### Q8：为什么要统计 Context Noise？

Retriever 找到 relevant evidence 不意味着所有 Top-K 都应该进入 prompt；多余 context 会增加 token cost，也可能成为 LLM distractor。

------

# 三十三、30 秒面试总结

> Phase3 我主要做了 Advanced RAG 的 evaluation-driven optimization。首先在 Synthetic 和 BEIR SciFact 上建立可复现 retrieval baseline，然后实现 BM25 sparse retrieval，并和 Dense Retrieval 使用 RRF 做 Hybrid Search。RRF 在部分 Recall、MRR 和 NDCG 指标上提升，但不是所有指标都上涨。之后加入 Cross-Encoder reranking，SciFact ranking 有改善，但 domain guardrail 出现 regression，所以没有 production enable。后面又做了 evidence-based no-answer threshold calibration，最终证明简单 top1+margin policy 没有可行 threshold，因此主动 Reject。最后做了 fixed Top-K context-selection benchmark，用真实 generation tokenizer评估 support coverage、context noise 和 token cost。整个阶段的重点是用可信实验决定优化是否值得，而不是为了指标好看强行上线。

------

# 三十四、2 分钟面试总结

> Phase3 是我整个项目的 Advanced RAG 优化阶段，但核心思想不是不断增加模型，而是 Evaluation-Driven Optimization。
>
> 我先固定了 Qwen3-Embedding-0.6B 的 Dense Retrieval baseline，并建立 Synthetic corpus 和 BEIR SciFact 300-query public benchmark，还做了 persistent embedding cache，让大约 90 分钟的 cold build 能在 20 多秒 warm reuse，同时保证 benchmark exact reproduction。
>
> 在 retrieval 上，我增加了独立 BM25 channel。Dense 对语义表达更好，BM25 对技术名词、错误码、类名这类 lexical query 更有优势，所以之后通过 RRF 做 rank-level fusion，避免直接融合不同量纲的 Dense 和 BM25 score。SciFact 上 RRF 的 R@1、R@5、MRR、NDCG@5 有提升，但 R@3、NDCG@3 有 regression，因此没有说它全面优于 baseline。
>
> Ranking 上又验证了 Cross-Encoder。它没有增加 recall candidates，只重新排序，因此 Recall 基本不变，但 MRR 和 NDCG 有改善。不过 Synthetic hard guardrail 下降，所以这个 candidate 最终 Reject，并没有 production enable。
>
> 然后我研究了 RAG 的 abstention，用 top1 evidence score 和 top1-top2 margin 做 calibration。我们穷举 513 个 threshold configuration，但没有一个同时满足安全约束，因此没有为了得到结果而修改数据，而是直接判定这个简单 policy family 不可行。
>
> 最后做 Context Selection，对 Top1 到 Top4 做固定 ablation。8 个可信 support case 中 Top1 已经覆盖全部 required support，继续增加 K 没提高 coverage，反而增加 context noise 和真实 tokenizer token cost。但我没有直接选择 K1 上线，因为这个实验属于 comparison 而不是 policy-selection，需要新的 CAL/EVAL 才能正式选择生产 K。
>
> 所以这阶段我真正建立的是一套从 retrieval、ranking、abstention 到 context selection 的分层 RAG evaluation 方法，而不是简单堆 BM25、RRF 和 reranker。

------

# 三十五、Phase3 面试最值得强调的能力

你以后讲这个阶段，建议把重点排序成：

```text
1. Evaluation-Driven Optimization 思维
2. Dense + BM25 Hybrid Retrieval
3. RRF 原理与 trade-off
4. Cross-Encoder 两阶段检索架构
5. Public Benchmark + Domain Guardrail
6. CAL / EVAL 实验纪律
7. Negative Result / Candidate Reject
8. Context Selection / Token Cost / Noise
9. Provenance / Reproducibility
10. Truthful Production Boundary
```

不要把面试重点放在：

```text
“我写了多少类”
“有多少 digest”
“做了多少 Gate”
```

那些只是保证实验可信的手段。

------

# 三十六、Phase3 最终一句话

> **Stage5-Phase3 把项目从“能做 RAG”推进到了“能够系统地评估、比较并拒绝 RAG 优化方案”：不仅实现了 BM25、Hybrid RRF、Cross-Encoder 和 Context Selection，更重要的是建立了 Baseline、Public Benchmark、Guardrail、Calibration、Provenance 和可复现实验闭环。**

推荐总学习文档文件名：

```text
stage5_phase3_advanced_rag_evaluation_driven_optimization_interview.md
```