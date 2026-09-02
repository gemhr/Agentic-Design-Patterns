# Stage5-Phase6 — Advanced RAG Productionization 全阶段学习 / 面试总结

## 1. 一句话项目定义

Stage5-Phase6 的目标不是简单“给 LocalAgent 加 BM25 和 RRF”，而是：

> 将 LocalAgent 原本 production-reachable 的 Dense + keyword supplement + heuristic rerank 检索路径，演进为具有明确 Retrieval Contract（检索合同）、Corpus / Chunk / Index Provenance（来源证明）、可显式启用的 Dense + BM25 → RRF Hybrid Retrieval（混合检索），并通过 production-target Evaluation（生产目标评估）、逐 Case 回归门禁、扩展数据集和受控优化实验，决定 Hybrid 是否具备成为生产默认策略的资格。

最终结果：

```text
STAGE5_PHASE6_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS
PHASE6_COMPLETE = YES

CURRENT_PRODUCTION_DEFAULT = BASELINE

HYBRID_RRF_STATUS =
PRODUCTION_REACHABLE_EXPERIMENTAL

HYBRID_ELIGIBLE_FOR_DEFAULT_PROMOTION = NO
```

也就是说：

> **Hybrid 被真实实现并接入生产 Runtime，但 Evaluation Evidence（评估证据）不足以支持它成为默认策略，因此生产继续保持 Baseline。**

------

# 2. Phase 开始前的真实 RAG 状态

Phase6 开始前，LocalAgent 并不是纯粹的 Dense Retrieval（稠密检索）。

真实生产路径是：

```text
User Query
    ↓
Coordinated Runtime
    ↓
knowledge_expert
    ↓
RetrievalExecutionService
    ↓
Query Rewrite
    ↓
Dense Retrieval
+
Chroma keyword supplement
    ↓
merge / dedup
    ↓
heuristic rerank
    ↓
RetrievalContextChunk
    ↓
ContextBuilder
    ↓
Model Context
```

所以 Phase6 不是：

```text
Dense
→
Hybrid
```

这么简单。

更准确是：

```text
Dense
+ keyword supplement
+ heuristic rerank

        ↓

正式 Retrieval Contract
+ Provenance
+ Canonical BM25
+ RRF
+ Evaluation Gate
```

------

# 3. 整个 Phase 的演进路线

```text
WP0
Production RAG Audit
真实源码审计
        ↓
WP1
Retrieval Contract & Provenance
数据 / Chunk / Index 身份链
        ↓
WP2
Canonical Hybrid Retrieval
Dense + BM25 → RRF 接入真实 Runtime
        ↓
WP3
Production-target Candidate Evaluation
Hybrid v1 正式实验
        ↓
Aggregate Quality PASS
Per-case Regression FAIL
        ↓
WP4
Expanded Evaluation Dataset
20 → 60 retrieval cases
        ↓
WP5
Hybrid Optimization
Core / Dev / Holdout
Weighted RRF experiment
        ↓
NO_VIABLE_CANDIDATE
        ↓
WP6
Production Baseline Freeze
        ↓
BASELINE remains default
Hybrid remains experimental
```

------

# 4. WP0 — Production RAG Audit

## 核心目标

先回答：

> LocalAgent 当前真正运行的 RAG 到底是什么？

而不是根据历史设计文档猜架构。

源码审计最终确认：

```text
PRODUCTION_REACHABLE_DENSE
WITH_KEYWORD_SUPPLEMENT
AND_HEURISTIC_RERANK
```

并建立真实调用链：

```text
Coordinated Runtime
→ knowledge_expert
→ RetrievalExecutionService
→ retrieval
→ ContextBuilder
→ specialist model
```

### 工程价值

这个 WP 看起来没有“新增功能”，但它解决了一个很关键的问题：

> 后续所有优化必须建立在真实 Production Source Truth（生产源码事实）上。

否则很容易出现：

```text
设计文档说 A
实际代码跑 B
Evaluation 却测 C
```

------

# 5. WP1 — Retrieval Contract & Provenance

这是 Phase6 的基础架构 WP。

核心问题：

> 如果以后同时存在 Dense、BM25、Hybrid，多套 Index 怎么证明来自同一份 Corpus 和 Chunk？

因此建立：

```text
Dataset
↕
Corpus
↕
Source Manifest
↕
Chunk Policy
↕
Chunk Manifest
↕
Index Generation
↕
Embedding Identity
↕
Retrieval Artifact
```

------

## 5.1 Corpus Identity

增加：

```text
corpus_id
```

但明确：

> `corpus_id` 只是诊断标签，不是完整性证明。

真正身份依赖 SHA-256 Manifest。

------

## 5.2 Source Manifest

冻结 source-level identity，例如：

```text
source
content_sha256
```

最终形成：

```text
source_manifest_sha256
```

------

## 5.3 Chunk Policy

冻结：

```text
chunk_schema_version
splitter_ref
chunk_size
chunk_overlap
chunk_content_format_ref
```

得到：

```text
chunk_policy_sha256
```

------

## 5.4 Chunk Manifest

每个 Chunk 记录：

```text
ordinal
document_id
chunk_id
source
section_path
content_hash
```

最终：

```text
chunk_manifest_sha256
```

------

## 5.5 Generation

Index 不再只是：

```text
一个 Chroma collection
```

而成为：

```text
Logical Collection
    ↓
Generation
    ├─ Dense Artifact
    ├─ BM25 Artifact
    └─ Provenance
```

Hybrid 必须确认：

```text
Dense
和
BM25
```

属于同一个 Generation。

------

# 6. WP2 — Canonical Hybrid Retrieval Integration

WP2 才真正完成：

```text
Dense + BM25 → RRF
```

生产接入。

------

## 6.1 Canonical Hybrid Pipeline

最终架构：

```text
Query
  ↓
Rewrite
  ↓
┌────────────────────┐
│                    │
Dense               BM25
│                    │
└─────────┬──────────┘
          ↓
semantic identity dedup
          ↓
RRF
          ↓
top-k
          ↓
materialize Dense authoritative content
          ↓
RetrievalContextChunk
          ↓
ContextBuilder
```

------

## 6.2 为什么不用 BM25 返回内容作为最终 Context Authority

BM25 主要承担：

```text
ranking signal
```

最终文本内容仍通过 Dense Generation 中的 authoritative chunk identity materialize。

这样避免：

```text
Dense artifact content
和
BM25 artifact content
```

产生双事实源。

------

## 6.3 RRF

使用：

```text
RRF_K = 60
```

Dense 与 BM25 分别提供排名，再通过 Reciprocal Rank Fusion（倒数排名融合）组合。

Hybrid v1：

```text
Dense weight = 1.0
BM25 weight = 1.0
```

------

## 6.4 Production Strategy

增加：

```text
BASELINE
HYBRID_RRF
```

但：

```text
default = BASELINE
```

Hybrid 只能显式启用。

这里非常重要：

> “生产可达”不等于“生产默认”。

------

# 7. WP3 — Production-target Evaluation & Candidate Gate

这是整个 Phase 技术价值最高的 WP 之一。

核心问题从：

> Hybrid 能不能运行？

升级为：

> Hybrid 是否值得成为 production default？

------

# 8. Same-generation Paired Experiment

为了让比较可信，Baseline 与 Hybrid 必须固定：

```text
同 Dataset
同 Corpus
同 Generation
同 Embedding
同 Chunk
同 Rewrite
同 Runtime source
同 Settings
```

唯一核心变量：

```text
Retrieval Strategy
```

------

## 8.1 Generation Pin

正式 Experiment 冻结：

```text
generation_id
provenance
source manifest
chunk policy
chunk manifest
embedding identity
physical collection
```

避免：

```text
Baseline 用 Index A
Hybrid 用 Index B
```

却把结果差异算到算法头上。

------

## 8.2 Rewrite Fixture

Query Rewrite 调真实 Model，会产生非确定性。

所以：

```text
真实 rewrite capture
        ↓
freeze fixture
        ↓
Baseline replay
Hybrid replay
```

这样：

```text
Rewrite variance
```

不会污染 Retrieval Strategy comparison。

------

# 9. WP3 最重要 Real Bad Case 之一：

# Dataset ↔ Corpus Lineage 错绑

最初以为 Evaluation Dataset 的 GT 对应：

```text
huawei_wiki_collection
```

结果：

```text
GT exact match = 0 / 23
```

进一步审计发现真正 Corpus：

```text
rag-evaluation-corpus.v1
```

重新按照 canonical splitter 构建：

```text
15 documents
60 chunks
23 / 23 Ground Truth identity match
```

这个问题说明：

> Retrieval Metric 的公式即使完全正确，如果 Dataset Ground Truth 和 Corpus 对不上，整个实验仍然没有意义。

------

# 10. Real Bad Case：

# Serializer Drift ≠ Corpus Drift

历史 manifest SHA 与当前 manifest SHA 不一样。

最初看起来像：

```text
Corpus changed
```

但进一步比较发现：

```text
source content 相同
chunk semantics 相同
GT identity 23/23 相同
```

差异只是 serializer schema：

历史：

```text
{path, sha256}
```

当前：

```text
{source, content_sha256}
```

以及当前 Chunk 增加了：

```text
ordinal
```

所以最终分类：

```text
SERIALIZATION_VERSION_DRIFT
```

而不是：

```text
CORPUS_DRIFT
```

因此 Phase6 最终明确拆开：

```text
Dataset Corpus Lineage
```

与：

```text
Current Generation Provenance
```

两个身份层。

------

# 11. Real Bad Case：

# Retrieval EMPTY 被 Runtime 错误升级成 FAILED

这是整个 Phase 最值得面试讲的 Bad Case。

Retrieval 层已经定义：

```text
EMPTY
```

意思：

> 检索流程正常完成，但没有找到可用知识。

但是上层 AgentRouter 又执行：

```text
EMPTY
→ KnowledgeSourceNotFoundError
→ AGENT_STEP_FAILED
```

导致第一次真实 Baseline Formal Run：

```text
24 attempts
20 success
4 failure
```

其中甚至有正常 retrieval case：

```text
semantic-context-trust
```

所以问题不是 Dataset 特判，而是：

```text
Cross-layer Semantic Mismatch
```

------

## 修复后的 Contract

```text
RetrievalExecutionService
        ↓
EMPTY
        ↓
保持 retrieval_status=EMPTY
        ↓
RAG_DOCUMENT count = 0
        ↓
Trusted RUNTIME_STATE
knowledge_retrieval_status=EMPTY
        ↓
Model Invocation
        ↓
bounded no-evidence response
        ↓
normal completion
```

同时：

```text
EMPTY 后真正发生 Provider failure
```

仍然必须失败。

这里真正解决的是：

> Typed Status（强类型状态）只有在所有层都保留它的语义时才有价值。

------

# 12. WP3 Final Formal Pair

正式实验：

```text
Baseline:
24 / 24 completed
failure = 0

Hybrid:
24 / 24 completed
failure = 0
```

20 个 retrieval/ranking cases 的最终结果：

| Metric   | Baseline | Hybrid   | Delta     |
| -------- | -------- | -------- | --------- |
| Recall@1 | 0.641667 | 0.716667 | +0.075000 |
| Recall@3 | 0.850000 | 0.925000 | +0.075000 |
| Recall@5 | 0.900000 | 0.925000 | +0.025000 |
| MRR      | 0.900000 | 0.900000 | 0         |
| NDCG@3   | 0.862854 | 0.863632 | +0.000779 |
| NDCG@5   | 0.879804 | 0.863632 | -0.016172 |

所以：

```text
QUALITY_GATE = PASS
```

------

# 13. 为什么 Hybrid v1 最终还是 FAIL

因为除了 Aggregate Metric（聚合指标），还冻结了：

```text
Per-case Regression Gate
```

最终：

```text
IMPROVEMENT = 4
UNCHANGED   = 12
REGRESSION  = 4
SEVERE      = 0
```

冻结规则：

```text
ordinary regression <= 2 / 20
```

实际：

```text
4 / 20
```

所以：

```text
PER_CASE_REGRESSION_GATE = FAIL

HYBRID_CANDIDATE_GATE = FAIL
```

------

## 这个设计解决什么问题

防止：

```text
绝大多数 Query 变好
        ↓
平均指标提升
        ↓
部分已经正常工作的用户场景却明显退化
```

因此：

```text
Aggregate Quality
```

回答：

> 整体有没有改善？

而：

```text
Per-case Regression
```

回答：

> 有没有通过牺牲已有用户场景换平均提升？

------

# 14. Real Bad Case：

# Latency Denominator 算错

最初报告：

```text
Baseline 799.292ms
Hybrid   662.292ms
```

实际统计的是：

```text
全部 24 cases
```

但 Gate 冻结要求：

```text
20 comparable retrieval cases
```

Final Gate 重算：

```text
Baseline = 828.600 ms
Hybrid   = 685.300 ms
```

最终结果仍然：

```text
LATENCY_GATE = PASS
```

但这个 Bad Case 说明：

> Metric Contract 不只是公式，还包括 Denominator（分母）、Aggregation Scope（聚合范围）和 Case Eligibility（Case 纳入条件）。

------

# 15. WP4 — Expanded Evaluation Dataset

WP3 最大 Accepted Limitation 是：

```text
retrieval cases = 20
```

每个 Case 权重：

```text
5%
```

因此样本过小，很容易受单 Case 波动影响。

WP4 目标：

```text
20 Frozen Core
+
40 New Retrieval Cases
=
60 Retrieval Cases
```

再保留：

```text
4 no-answer
```

最终 Dataset v2：

```text
60 retrieval/ranking
4 no-answer
64 total
```

Final Gate：

```text
71 GT identities
71 valid
0 invalid

exact duplicates = 0
material near duplicates = 0
candidate-informed GT = NO
```

------

# 16. Slice Taxonomy

60 个 Retrieval Case 增加分析 Slice：

```text
EXACT_KEYWORD                 16
SEMANTIC_PARAPHRASE           8
ABBREVIATION                  3
ENTITY_DISAMBIGUATION        10
NUMERIC_FACT                  7
LOW_SCORE_WEAK_EVIDENCE       4
LONG_CONTEXT_CROSS_SECTION    3
TRUST_BOUNDARY_MEMORY_RAG     9
```

Slice 不影响 Candidate 权重，只用于：

```text
failure analysis
per-slice metrics
regression diagnosis
```

------

# 17. 为什么保留原 20 Case 不修改

原 WP3 20 个 Case 被定义成：

```text
Frozen Core Regression Set
```

不能因为：

```text
Hybrid 在某几个 Case 上 FAIL
```

就去修改：

```text
query
GT
relevance
case meaning
```

否则就是：

```text
修改考试题让 Candidate 通过
```

这是整个 Evaluation 系统的可信边界。

------

# 18. WP5 — Hybrid v2 Optimization

WP5 没有直接使用全部 60 Case 调参。

而是：

```text
CORE = 20
DEV_NEW = 20
HOLDOUT_NEW = 20
```

------

## 三者职责

### Core

```text
Regression Safety
```

确认历史关键能力没有再次损坏。

### Dev

```text
Candidate Selection
```

允许用于调参和选择方案。

### Holdout

```text
Final unseen validation
```

Candidate Freeze 前禁止查看。

这样防止：

```text
Test-set Overfitting
```

------

# 19. WP3 四个 Regression Root Cause

重新分析：

```text
Dense rank
BM25 rank
RRF rank
Top-K
Ground Truth
```

最终：

```text
abbreviation-mcp
→ AMBIGUOUS_MULTI_RELEVANT

multi-owner-disambiguation
→ AMBIGUOUS_MULTI_RELEVANT

semantic-baseline-low-score
→ FUSION_ORDERING_ERROR

semantic-memory-write
→ TOP_K_DISPLACEMENT
```

------

# 20. 为什么第二轮先做 Weighted RRF

没有直接引入：

```text
Cross-Encoder
HyDE
Multi-Query
ColBERT
Graph RAG
```

原因是：

> Regression Evidence 指向 Fusion Ordering 和 Top-K Displacement，因此优先尝试最小成本 Fusion 优化。

搜索空间提前冻结：

```text
Control:
Dense 1.0
BM25 1.0

Variant A:
Dense 1.25
BM25 1.0

Variant B:
Dense 1.0
BM25 1.25
```

------

# 21. Real Bad Case：

# Candidate Search Profile 实际执行错误

ZCode 首轮报告声称跑：

```text
1.25 / 1.0
1.0 / 1.25
```

但 Codex Final Gate 审查源码发现实际跑的是：

```text
1.25 / 0.75
0.75 / 1.25
```

也就是说：

```text
Experiment Contract
!=
Experiment Implementation
```

这是一个真实实验完整性问题。

------

## 修复方式

没有重新设计 Candidate。

只做 Narrow Fix-forward：

```text
修正 Search Space
↓
重新跑原冻结的两个 Variant
↓
不增加 Variant C
↓
不查看 Holdout
```

这保证了：

```text
实验规则没有因为结果而改变
```

------

# 22. 修正后的 Weighted RRF 结果

真实权重：

```text
Dense 1.25 / BM25 1.0
Dense 1.0 / BM25 1.25
```

结果：

```text
六项 Dev metric delta
全部 = 0
```

并且：

```text
VARIANT_RANKING_DISTINCT = NO
```

但：

```text
WEIGHT_PROFILE_APPLICATION_GATE = PASS
```

说明：

> 权重确实进入了 Production RRF Score，只是 1.25 的轻量权重不足以改变最终 Selected Ranking。

------

# 23. RRF 中为什么 Score 变了但 Rank 不一定变

RRF 大致：

```text
score =
weight / (k + rank)
```

当前：

```text
k = 60
```

例如：

```text
rank1 → 1/61
rank2 → 1/62
rank3 → 1/63
```

当候选的 Dense/BM25 排名比较稳定时：

```text
weight 1.0
→
1.25
```

可以改变 score，

但仍不足以：

```text
cross ranking boundary
```

所以：

```text
score changed
≠
rank changed
```

------

# 24. 为什么最终没有 Hybrid v2

因为：

```text
Variant A
没有改善

Variant B
没有改善
```

如果强行把某个方案命名：

```text
Hybrid v2
```

只是：

```text
新的配置名称
```

不是新的有效 Candidate。

所以正确输出：

```text
NO_VIABLE_CANDIDATE = YES
HYBRID_V2_SELECTED = NO
```

------

# 25. 为什么没跑 Holdout / Formal Pair

Candidate 验证正确顺序：

```text
Dev
↓
Candidate Selected
↓
Candidate Freeze
↓
Holdout
↓
Formal Pair
```

但当前：

```text
Dev
↓
NO_VIABLE_CANDIDATE
```

所以：

```text
Holdout 不查看
Formal Pair 不运行
```

反而保证：

```text
HOLDOUT_LEAKAGE_GATE = PASS
```

------

# 26. WP6 — Production Baseline Freeze

WP6 不再做任何算法改动。

只确认真实生产状态：

```text
LOCAL_AGENT_RETRIEVAL_STRATEGY
未设置
↓
RetrievalStrategy.parse()
↓
BASELINE
```

只有显式：

```text
HYBRID_RRF
```

才进入：

```text
Dense + BM25 → RRF
```

并执行完整 Hybrid provenance validation。

Codex Final Gate 最终确认：

```text
DEFAULT_STRATEGY_GATE = PASS
HYBRID_CAPABILITY_GATE = PASS
EVALUATION_AUTHORITY_GATE = PASS
PROVENANCE_FINAL_GATE = PASS
DATASET_V2_FREEZE_GATE = PASS
```

------

# 27. Phase6 最终 Production Architecture

```text
User Query
    ↓
Canonical Coordinated Runtime
    ↓
RetrievalExecutionService
    ↓
Retrieval Strategy
    │
    ├─────────────────────────────┐
    │                             │
BASELINE                      HYBRID_RRF
[DEFAULT]                    [EXPLICIT]
    │                             │
Dense                         Dense
+ keyword supplement          +
+ heuristic rerank            BM25
                              ↓
                              RRF
    │                             │
    └──────────────┬──────────────┘
                   ↓
        RetrievalContextChunk
                   ↓
             ContextBuilder
                   ↓
              Model Context
```

------

# 28. Owner 边界

## LocalAgent

Production Owner：

```text
Retrieval
Corpus
Index
Dense
BM25
RRF
Generation
Provenance
Runtime
ContextBuilder
```

## AgentEvalOps

Evaluation Owner：

```text
Dataset
Experiment orchestration
Metrics
Comparison
Regression Gate
Evidence
Candidate decision
```

非常重要：

> AgentEvalOps 不拥有 Production Retrieval Algorithm。

------

# 29. Phase6 最重要的设计思想

## 29.1 Production Reachable ≠ Production Default

功能能跑，不代表应该默认上线。

------

## 29.2 Aggregate Improvement ≠ Safe Promotion

平均 Recall 提升，也可能伴随局部严重回归。

------

## 29.3 Evaluation 的目标不是证明 Candidate PASS

真正目标：

```text
可信地证明 PASS
或
可信地证明 FAIL
```

------

## 29.4 Dataset 也是工程资产

Dataset 不是：

```text
随手写几个 query
```

而是拥有：

```text
version
identity
GT
Corpus lineage
Core
Slice
Dev/Holdout
immutability
```

的正式工程资产。

------

## 29.5 实验参数也是 Provenance

不只要记录：

```text
dataset SHA
source SHA
generation
```

还必须记录：

```text
Candidate Profile
```

否则实际测试参数和设计参数可能不一致。

------

## 29.6 Typed State 必须跨层保持语义

```text
EMPTY
```

不能因为进入不同 Layer 就偷偷变成：

```text
FAILED
```

这是 Contract-based Architecture（合同驱动架构）的关键。

------

# 30. 真实性与完成边界

## 已真实实现

```text
Production Retrieval Provenance
Generation binding
BM25 artifact
Hybrid RRF
Strategy switch
Production Hybrid Runtime path
Evaluation generation pin
Rewrite fixture
Dataset v2
Core / Dev / Holdout split
Per-case Regression Gate
Candidate Gate
Weighted RRF Candidate profile
```

------

## 已真实测试

Hybrid v1：

```text
Baseline 24/24
Hybrid 24/24
```

WP4：

```text
60 retrieval cases
71/71 GT valid
```

WP5：

```text
真实 Weighted RRF production profile propagation
Dev experiment
Holdout leakage validation
```

WP6 focused validation：

```text
LocalAgent:
82 passed, 1 skipped

AgentEvalOps:
108 passed, 1 warning
```

------

## 未实现 / Future

以下没有实现：

```text
Cross-Encoder
HyDE
Multi-Query Retrieval
ColBERT
Graph RAG
Agentic Retrieval
Query-aware Fusion
online retrieval optimization
large-scale production query dataset
LLM Judge final-answer Gate
distributed index
```

不能在简历或面试中描述为已经完成。

------

# 31. Accepted Limitations

Phase6 最终接受：

1. Corpus / Dataset 为 synthetic project-local workload。
2. Expanded Retrieval Dataset 只有 60 Case。
3. Hybrid v2 只探索 bounded Weighted RRF。
4. 未实验 Cross-Encoder / HyDE / Multi-Query / ColBERT / Graph RAG。
5. 因无 viable Hybrid v2，没有第二轮 formal pair。
6. 没有 LLM Judge final-answer Gate。
7. RRF raw score 没有统一 absolute relevance semantics。

这些均明确不阻塞 Phase6。

------

# 32. Real Bad Cases 总表

## Bad Case 1

Dataset ↔ Corpus 错绑

```text
GT hit = 0/23
```

修复为 canonical evaluation corpus 后：

```text
23/23
```

------

## Bad Case 2

Serializer Drift 被误认为 Corpus Drift

根因：

```text
manifest schema change
```

而不是：

```text
content change
```

------

## Bad Case 3

Retrieval EMPTY → Runtime FAILED

根因：

```text
Cross-layer semantic mismatch
```

------

## Bad Case 4

Latency denominator 错误

```text
24 cases
```

错误用于应该：

```text
20 retrieval cases
```

的 Gate。

------

## Bad Case 5

Aggregate Improvement 掩盖 Per-case Regression

Hybrid：

```text
Recall ↑
```

但：

```text
4/20 regression
```

最终拒绝晋级。

------

## Bad Case 6

Candidate Profile 与真实执行权重不一致

设计：

```text
1.25/1.0
1.0/1.25
```

首轮实际：

```text
1.25/0.75
0.75/1.25
```

Final Gate 发现并 fix-forward。

------

# 33. 名词 / 概念速览

### Hybrid Search（混合检索）

同时利用 Dense semantic retrieval 和 sparse lexical retrieval。

### BM25

经典关键词相关性排序算法，擅长 exact token、identifier、缩写和术语匹配。

### Dense Retrieval（稠密检索）

使用 Embedding 表达 Query/Document 语义相似度。

### RRF

Reciprocal Rank Fusion（倒数排名融合），通过多个检索器的 rank 而非原始 score 融合结果。

### Weighted RRF

为不同 Retrieval Channel 的 RRF contribution 增加权重。

### Provenance

证明一个 Retrieval Artifact 来自什么 Corpus、Chunk Policy、Embedding 和 Generation。

### Generation

同一 logical collection 下的一份不可变 Index Snapshot。

### Ground Truth

Evaluation Dataset 中预先确定的正确结果。

### Corpus Lineage

Dataset Ground Truth 与真实 Corpus 内容之间的身份血缘。

### Generation Pin

正式实验中固定 Index Generation 的凭证。

### Rewrite Fixture

冻结 Query Rewrite 输出，控制 Model Rewrite 非确定性。

### Per-case Regression

逐 Case 比较 Candidate 是否让已有正常行为退化。

### Dev Set

用于 Candidate 调参与选择。

### Holdout Set

Candidate Freeze 前禁止查看的留出验证集。

### Test-set Overfitting

算法反复针对 Evaluation Dataset 调整，导致测试结果无法代表泛化性能。

### Candidate Gate

判断某个 Retrieval Strategy 是否允许晋级生产默认的门禁。

------

# 34. 工程方法类高频问题

## Q1：为什么不直接用 Hybrid 替代 Dense？

因为：

```text
Implementation Complete
≠
Production Qualification
```

必须先通过 Evaluation Gate。

------

## Q2：为什么 RAG Evaluation 不只看 Recall@K？

因为还需要：

```text
MRR
NDCG
per-case regression
reliability
latency
fairness
provenance
```

------

## Q3：为什么需要 Provenance？

否则无法知道：

```text
Baseline 和 Hybrid
```

是不是在比较同一个：

```text
Corpus / Chunk / Embedding / Index
```

------

## Q4：为什么 Hybrid Recall 提高还被拒绝？

因为：

```text
4/20 regression
```

超过：

```text
2/20 frozen regression budget
```

说明局部风险不可接受。

------

## Q5：为什么不看到 FAIL 后把 Gate 改成 4/20？

因为属于：

```text
Post-hoc Threshold Tuning
```

会破坏 Evaluation 的可信度。

------

## Q6：为什么后来扩大 Dataset？

20 Case：

```text
1 case = 5%
```

样本过小。

扩成 60 Case 可以：

```text
增加 Failure Mode Coverage
支持 Slice Analysis
拆分 Dev / Holdout
```

------

## Q7：为什么 Hybrid v2 没产生也算成功？

因为实验目标是：

> 判断优化方向是否值得进入正式验证。

结果：

```text
NO_VIABLE_CANDIDATE
```

也是有效 Evidence。

------

## Q8：为什么没看 Holdout？

因为 Dev 根本没有产生 Candidate。

查看 Holdout只会污染下一轮验证边界。

------

## Q9：为什么不用 Cross-Encoder？

当前 Phase 优先验证：

```text
Dense + BM25 + Fusion
```

最小必要生产化。

Cross-Encoder 增加：

```text
model dependency
latency
deployment complexity
```

且不是当前必须项。

------

## Q10：下一轮如果真要继续提升 Hybrid，你会怎么做？

可以考虑：

```text
Query-aware Fusion
Cross-Encoder Reranking
larger production workload dataset
online failure mining
```

但应该作为新的 Candidate Experiment，而不是修改已经完成的 Phase6。

------

# 35. 高频面试追问

建议重点准备：

1. Dense 和 BM25 分别擅长什么？
2. 为什么用 RRF 而不是直接归一化两边 score？
3. RRF_K 有什么作用？
4. 为什么 Hybrid 可能 Recall 提高但 NDCG 不明显？
5. 什么是 Top-K Displacement？
6. 什么是 Corpus Lineage？
7. Index Generation 为什么需要 immutable？
8. Dataset GT 怎么和 Chunk identity 对齐？
9. 为什么 Query Rewrite 要 Fixture？
10. 为什么 EMPTY 不应该变成 FAILED？
11. Per-case Regression 与 Aggregate Metric 如何配合？
12. 为什么 Dataset 要拆 Core / Dev / Holdout？
13. 如何避免 Retrieval Benchmark Overfitting？
14. 为什么没有 Candidate 时不应该强行跑 Formal Pair？
15. 如何证明 Candidate 参数真的进入生产实现？

------

# 36. 30 秒面试总结

我在 LocalAgent 的 Advanced RAG 阶段没有直接把 Dense 改成 Hybrid，而是先从真实生产源码审计开始，建立了 Corpus、Chunk、Embedding 和 Index Generation 的 Provenance，然后把 BM25 和 Dense 通过 RRF 接入真实 Coordinated Runtime，并保留 Baseline 为默认策略。之后使用同 Dataset、同 Generation、同 Rewrite Fixture 和同 Runtime Source 做 production-target paired evaluation。Hybrid v1 的 Recall@1 和 Recall@3 都提升了 7.5 个百分点，但 20 个 Retrieval Case 中有 4 个逐 Case regression，超过提前冻结的 2/20 门槛，所以没有晋级。我又把 Dataset 扩到 60 个 Retrieval Case，并拆成 Core、Dev 和 Holdout 做 Weighted RRF 优化，但轻量权重调整没有改变最终 Ranking，因此没有强行制造 Hybrid v2。最终生产继续使用 Baseline，Hybrid 保留为显式实验能力。

------

# 37. 2 分钟面试总结

这个阶段主要是把 LocalAgent 的 RAG 从一个能工作的检索模块，升级成一个可以可信评估和安全演进的生产 Retrieval System。

最开始我先审计真实 Production Path，发现原系统其实已经不是单纯 Dense，而是 Dense Retrieval 加 keyword supplement 和 heuristic rerank。之后我没有直接叠 BM25，而是先建立 Retrieval Provenance，把 Source Manifest、Chunk Policy、Chunk Manifest、Embedding Identity 和 Index Generation 串起来，确保后续 Dense 和 BM25 真正来自同一个 Corpus Generation。

在这个基础上，我把 Dense + BM25 → RRF 做成一个显式的 `HYBRID_RRF` Production Strategy，但默认继续保持 Baseline。

真正决定是否切默认是在 Evaluation 阶段。Baseline 和 Hybrid 使用完全相同的 Dataset、Generation、Embedding、Rewrite Fixture 和 Runtime Source，通过真实 Coordinated Runtime 各运行 24 个 Case。实验期间还发现 Dataset 一开始绑定错 Corpus、历史 Manifest 差异实际是 Serializer Drift，以及 Retrieval 层的 EMPTY 被 AgentRouter 错误转成 FAILED 等真实工程问题。

修正以后，Hybrid 的 Recall@1 和 Recall@3 都提升 7.5 个百分点，而且 Retrieval Latency 更低，但逐 Case 检查发现 4/20 个场景回归，而实验前已经冻结最多允许 2/20，所以 Hybrid v1 被 Candidate Gate 拒绝。

考虑到 20 Case 太小，我又把 Dataset 扩展到 60 个 Retrieval Case，并增加 Slice Metadata。第二轮优化时，为了避免测试集过拟合，又拆成 20 Core、20 Dev 和 20 Holdout。根据第一轮 Regression Root Cause，我先尝试成本最低的 Weighted RRF，并提前冻结只允许两个 Weight Variant。过程中 Final Gate 还发现实际脚本运行的 Candidate 权重和 Contract 不一致，修正后重新执行，最终两个轻量加权方案虽然 Weight 确实进入生产 RRF 计算，但 Selected Ranking 和 Dev Metrics 都没有变化，所以我没有查看 Holdout，也没有强行选 Hybrid v2。

最终 Phase6 的结论是：Hybrid RRF 已经是一条真实、可显式启用的生产路径，但现有 Evidence 不支持成为默认策略，因此生产继续保持 Baseline。我认为这一阶段最重要的不只是实现 Hybrid，而是建立了一套从 Retrieval Provenance、Dataset Identity、same-generation Experiment、Per-case Regression 到 Dev/Holdout 的评估驱动优化流程。

------

# 38. 简历上可以重点表达的能力

可以概括为：

```text
Advanced RAG
Hybrid Retrieval
Dense + BM25
RRF
Retrieval Provenance
Index Generation
Evaluation Dataset
Recall@K / MRR / NDCG
Per-case Regression
Production-target Evaluation
Dev / Holdout
Evaluation-driven Optimization
```

但不要写：

```text
Hybrid 已成为生产默认
Cross-Encoder 已上线
HyDE 已实现
Graph RAG 已实现
```

这些不符合真实完成边界。

------

# 39. 推荐学习文档文件名

```text
docs/interview/stage5_phase6_advanced_rag_productionization.md
```

------

# 40. 整个 Phase 最值得记住的一句话

> **Advanced RAG 的难点不是把 Dense、BM25 和 RRF 拼在一起，而是让 Corpus、Chunk、Index、Dataset、Runtime 和 Candidate 形成可追溯的身份链，并通过提前冻结的 Evaluation Gate 决定一个看起来平均指标更好的检索方案是否真的应该进入生产默认路径。**