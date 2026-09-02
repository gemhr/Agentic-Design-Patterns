当前使用的模型：**GPT-5.6 Sol**。

下面进入 **Stage5-Phase6-WP5 — Hybrid Retrieval Optimization & Second Experiment** 的学习/面试总结。这一 WP 最值得讲的不是“我又调了一轮 RRF”，而是：**如何在扩大数据集后，用受控 Dev/Holdout 设计继续优化 Hybrid，同时在没有 viable Candidate 时主动停止，而不是为了上线而过拟合测试集。**

# Stage5-Phase6-WP5 — Hybrid Retrieval Optimization & Second Experiment 学习/面试总结

## 1. 本 WP 解决什么问题

WP3 已经证明：

```text
Hybrid v1
Dense + BM25 → RRF
```

虽然整体 Recall 有提升，但：

```text
4 / 20 ordinary regressions
>
2 / 20 frozen regression budget
```

所以不能晋级 production default。

WP4 又把 retrieval/ranking Dataset 从：

```text
20 cases
```

扩充到：

```text
60 cases
```

因此 WP5 的核心问题变成：

> 能不能在不修改 Dataset、不降低 Gate、不查看 Holdout 的前提下，对 Hybrid v1 的真实 regression 做一轮受控优化，并得到一个更安全的 Hybrid v2 Candidate？

最终答案是：

```text
没有。
```

但这并不意味着 WP5 失败。

最终：

```text
WP5_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

NO_VIABLE_CANDIDATE = YES
HYBRID_V2_SELECTED = NO

HYBRID_V2_CANDIDATE_GATE = INCONCLUSIVE

PRODUCTION_DEFAULT_CHANGED = NO
READY_FOR_WP6 = YES
```

也就是说：

> 优化实验本身成功完成，但预声明的轻量 Weighted RRF（加权倒数排名融合）搜索空间没有产生值得进入 Holdout / Formal Pair 的新 Candidate。

------

# 2. 真实架构与实验数据流

## 2.1 Dataset Split

WP4 的 60 个 retrieval/ranking cases 被拆成：

```text
20 CORE
20 DEV_NEW
20 HOLDOUT_NEW
```

其中：

### CORE 20

来自 WP3 的 Frozen Core Regression Set（冻结核心回归集）。

主要作用：

```text
已知 regression 诊断
+
regression safety check
```

### DEV_NEW 20

用于：

```text
Candidate comparison
Candidate selection
```

### HOLDOUT_NEW 20

禁止参与：

```text
调权重
选 Candidate
改算法
```

只有在 Candidate 被正式冻结后，才能进入最终实验。

这种设计的核心是：

> 避免在全部 60 个 Case 上反复调参，然后又拿同一批 Case 证明“优化成功”。

也就是防止：

```text
Test-set Overfitting（测试集过拟合）
```

------

## 2.2 实验链路

本 WP 没有在 AgentEvalOps 里重写 RRF。

真实 Owner 仍然是：

```text
LocalAgent
```

实验路径复用生产实现：

```text
Settings
    ↓
server.py::lifespan()
    ↓
AgentRouter
    ↓
HybridKnowledgeRetrievalAdapter
    ↓
HybridRrfRetriever
    ↓
Dense / BM25
    ↓
Weighted RRF
```

AgentEvalOps 继续只负责：

```text
orchestration
evaluation
evidence
gate
```

因此仍然保持：

```text
LocalAgent = Retrieval Owner
AgentEvalOps = Evaluation Owner
```

------

# 3. WP3 Regression Root Cause Analysis

WP3 的四个真实回归分别重新检查了：

```text
Dense rank
BM25 rank
RRF fused rank
top-k
Ground Truth
```

最终分类如下。

------

## 3.1 abbreviation-mcp

分类：

```text
AMBIGUOUS_MULTI_RELEVANT
```

问题并不是简单的：

```text
BM25 找错了
```

而是存在多个相关 Chunk，Ground Truth 与融合排名之间存在多相关结果竞争。

核心学习：

> 一个 Case 的 metric regression 不一定意味着单个 retrieval channel 明显错误，也可能是多相关文档的排序位置变化。

------

## 3.2 multi-owner-disambiguation

分类：

```text
AMBIGUOUS_MULTI_RELEVANT
```

多个 Owner / Entity（实体）共享相似词汇和语义信号。

因此 Dense 和 BM25 都可能分别产生合理候选，但融合顺序会影响最终 top-k。

------

## 3.3 semantic-baseline-low-score

分类：

```text
FUSION_ORDERING_ERROR
```

这里更接近典型 Hybrid 问题：

```text
Dense 原有合理排序
+
BM25 signal
↓
Fusion 后正确结果位置下降
```

问题主要发生在 Fusion Ordering（融合排序），而不是 Ground Truth 或 Corpus。

------

## 3.4 semantic-memory-write

分类：

```text
TOP_K_DISPLACEMENT
```

正确 Chunk 仍然可能存在于 Candidate Pool（候选池）中，但融合后被其他结果挤出了最终 top-k。

这说明：

> Retrieval Failure 不只有“没召回”，还包括“召回了但没有进入最终 Context”。

------

# 4. 核心方案设计与取舍

## 4.1 为什么这次不继续扩算法范围

可以做的方案很多：

```text
Cross-Encoder
HyDE
Multi-Query
Query Routing
LLM Rerank
ColBERT
```

但 WP5 明确不加入这些方案。

原因：

当前要回答的是：

> 当前 Dense + BM25 + RRF 架构，通过非常小的融合参数调整，能不能解决主要 regression？

所以只设计了一个非常小的 Search Space（搜索空间）：

```text
Control
Dense=1.0
BM25=1.0

Variant A
Dense=1.25
BM25=1.0

Variant B
Dense=1.0
BM25=1.25
```

优点：

```text
实验成本低
归因简单
生产可解释
面试容易说明
避免参数海洋
```

------

## 4.2 为什么要提前冻结搜索空间

不能这样：

```text
1.1
→ 不好

1.2
→ 不好

1.3
→ 不好

1.4
→ 不好

...

一直试到 Dataset 通过
```

那会逐渐变成：

```text
benchmark tuning
```

甚至：

```text
test-set overfitting
```

所以 WP5 先冻结：

```text
Control
+
2 variants
```

再执行。

如果都不行：

```text
NO_VIABLE_CANDIDATE
```

而不是继续无限扩参数。

------

# 5. Real Bad Case — 搜索空间实现和 Contract 不一致

这一 WP 最重要的真实工程问题之一是：

> ZCode 首轮实际执行的权重，与 Prompt 冻结的权重不一致。

我们冻结的是：

```text
Dense 1.25 / BM25 1.0

Dense 1.0 / BM25 1.25
```

但最初真实运行却是：

```text
Dense 1.25 / BM25 0.75

Dense 0.75 / BM25 1.25
```

这导致最初报告出现：

```text
两个 Variant
Dev 六项指标都大幅下降

Core:
4 ordinary regressions
1 severe regression
```

Codex Final Gate 没有直接接受这个结果，而是检查实际 Candidate Profile。

最终确认：

```text
实验实现
!=
冻结的实验 Contract
```

因此进行了 Narrow Fix-forward（窄范围向前修复）。

------

## 为什么这是重要 Bad Case

如果不检查：

可能会错误得出：

> 1.25 的轻量加权严重破坏了 Hybrid。

但实际测试的是：

```text
1.25 vs 0.75
```

已经不是原计划的小幅偏置了。

这说明：

> Evaluation Pipeline 的参数本身也是 Experiment Identity（实验身份）的一部分。

不能只验证：

```text
Dataset SHA
Generation ID
Source SHA
```

还必须验证：

```text
Candidate Profile
```

------

# 6. Fix-forward 后的真实结果

修正后真正执行：

```text
Variant A
Dense 1.25
BM25 1.0

Variant B
Dense 1.0
BM25 1.25
```

结果非常有意思：

```text
六项 Dev delta 全部 = 0.0
```

包括：

```text
Recall@1
Recall@3
Recall@5
MRR
NDCG@3
NDCG@5
```

Core 的：

```text
ordinary regression = 0
severe regression = 0
```

也就是说：

> 轻量权重确实被应用了，但完全没有改变最终 Selected Ranking（选中排序）。

------

# 7. 为什么两个相反的权重会没有任何排名变化

这是一个很重要的 RRF 工程知识点。

RRF（Reciprocal Rank Fusion，倒数排名融合）核心思想类似：

```text
score =
weight / (k + rank)
```

当：

```text
k = 60
```

时，例如：

```text
rank 1
1 / 61

rank 2
1 / 62

rank 3
1 / 63
```

这些值之间本身差异很小。

如果 Dense 和 BM25 的候选排名结构比较稳定，那么：

```text
1.0 → 1.25
```

虽然会改变：

```text
fused score
```

却不一定足以改变：

```text
relative ordering
```

于是就出现：

```text
WEIGHT_PROFILE_APPLICATION_GATE = PASS

但

VARIANT_RANKING_DISTINCT = NO
```

这两个事实并不矛盾。

------

# 8. 为什么不能因为 Delta=0 就选一个 Hybrid v2

例如可以强行说：

```text
Dense 1.25
与 v1 一样

→ 那就选它
```

但没有意义。

因为 Candidate v2 应该至少提供：

```text
更好的质量
或
更低 regression risk
或
更清晰的生产收益
```

如果：

```text
ranking 不变
metric 不变
```

那么它只是：

```text
新的配置名字
```

不是新的有效 Candidate。

所以：

```text
NO_VIABLE_CANDIDATE = YES
```

是正确判断。

------

# 9. 为什么没有继续看 Holdout

这是 WP5 很值得面试讲的一点。

正确流程是：

```text
Dev
↓
选 Candidate
↓
Freeze
↓
Holdout
```

现在 Dev 已经告诉我们：

```text
Variant A 没改善
Variant B 没改善
```

所以没有 Candidate 可 Freeze。

因此：

```text
不查看 Holdout
```

反而是更严格的行为。

如果现在为了“看看会不会 Holdout 反而更好”而打开 Holdout：

```text
Holdout
```

就逐渐变成第二个 Dev Set。

最终：

```text
HOLDOUT_LEAKAGE_GATE = PASS
```



------

# 10. 为什么没有运行正式 44 + 44 Pair

原计划：

```text
Candidate Freeze
        ↓
40 retrieval formal cases
+
4 no-answer
        ↓
Baseline 44
        ↓
Hybrid v2 44
```

但这里缺少第一步：

```text
Candidate Freeze
```

因此：

```text
无 Candidate
→ 无 Formal Pair
```

是正确流程。

不能：

```text
先跑 Holdout/Formal
→ 再看看哪个 Candidate 表现好
```

因为这会让 Formal Dataset 反过来参与 Candidate Selection。

------

# 11. 真实性与完成边界

## 已真实完成

### Dataset Split

```text
CORE = 20
DEV_NEW = 20
HOLDOUT_NEW = 20
```

并有持久化 split manifest。

### Regression Root Cause

4 个 WP3 regression 已完成真实 Rank Evidence 分析。

### Weighted RRF 实验

真实测试了：

```text
Dense 1.25 / BM25 1.0

Dense 1.0 / BM25 1.25
```

### Production Profile Propagation

已确认：

```text
Settings
→ Runtime
→ Adapter
→ HybridRrfRetriever
```

权重真实生效。

### Dev Selection

Holdout 未用于 Candidate selection。

### Fix-forward

发现并修复搜索空间权重实现错误。

------

## 未完成

### Hybrid v2

```text
未产生
```

### Holdout Evaluation

```text
未执行
```

### Formal 44+44 Pair

```text
未执行
```

### Formal Latency Gate

```text
不适用
```

因为没有 Candidate。

------

# 12. Accepted Limitations

最终主要两项：

### 1. 没有正式 44+44 Experiment

原因不是执行失败，而是：

```text
NO_VIABLE_CANDIDATE
```

### 2. Formal Latency Gate 不适用

因为：

```text
Hybrid v2 不存在
```

所以没有 Candidate latency 可以比较。

这些限制不阻塞：

```text
WP5_FINAL_GATE
```



------

# 13. 名词 / 概念速览

### Dev Set（开发集）

用于候选方案选择、参数比较和开发期优化的数据子集。

### Holdout Set（留出集）

在 Candidate 冻结前禁止参与调参，用于检查方案是否具有一定泛化能力。

### Frozen Core Regression Set（冻结核心回归集）

长期保留的已知关键 Case，用于确认新方案没有破坏历史能力。

### Search Space（搜索空间）

实验前允许尝试的算法或参数组合集合。

### Weighted RRF（加权倒数排名融合）

在 RRF 中为不同 Retrieval Channel（检索通道）赋予不同贡献权重。

### Candidate Profile（候选配置）

完整描述一个 Candidate 使用的算法、权重和参数，属于实验身份的一部分。

### Candidate Freeze（候选冻结）

在进入 Holdout / Formal Experiment 前固定算法和参数，之后禁止继续调优。

### Holdout Leakage（留出集泄漏）

通过查看 Holdout 结果来调整算法或参数，使 Holdout 失去独立验证意义。

### Post-selection Tuning（选择后调优）

Candidate 已经选择后根据正式或 Holdout 结果继续修改参数，会破坏实验可信度。

### Ranking Distinctness（排序差异性）

两个 Candidate 是否真正产生不同的最终排序，而不只是内部 score 数值不同。

### NO_VIABLE_CANDIDATE（无可行候选）

当前冻结搜索空间内没有方案满足继续进入正式验证的价值和安全要求。

------

# 14. 工程构建方法类问答

## Q1：为什么要把 Dataset 分成 Dev 和 Holdout？

如果同一 Dataset 同时用于：

```text
调参数
+
证明最终效果
```

最终指标会产生 Selection Bias（选择偏差）。

所以：

```text
Dev
负责选方案

Holdout
负责检查选出的方案
```

------

## Q2：为什么还要保留 Core 20？

因为这 20 个 Case 已经包含真实历史 regression。

它们非常适合回答：

> 新优化有没有把之前已经知道的关键行为再次破坏？

因此：

```text
Core
=
Regression Safety

Dev
=
Candidate Selection

Holdout
=
Generalization Check
```

三者职责不同。

------

## Q3：为什么搜索空间要很小？

因为当前不是训练 ML 模型，而是在做生产 Retrieval Strategy 优化。

过大的搜索空间：

```text
几十个 weight
×
多个 RRF k
×
多个 top-k
```

会导致：

```text
成本增加
实验解释困难
Dataset overfitting 风险增加
```

小搜索空间更容易归因。

------

## Q4：为什么两个 Weighted RRF Variant 最终排名没变化？

权重真实改变了 fused score。

但因为：

```text
候选排名结构
+
RRF k
+
rank gap
```

使得轻量 `1.25` 权重不足以跨越排序边界。

所以：

```text
score changed
!=
rank changed
```

------

## Q5：为什么不继续把权重调成 2、3、5？

因为搜索空间已经冻结。

看到：

```text
1.25 没作用
```

以后再继续增加权重，就属于：

```text
根据 Dataset 结果扩大搜索空间
```

不是原实验。

可以未来开新 Experiment，但不能偷偷扩当前 WP5。

------

## Q6：为什么没有 Candidate 还算 WP PASS？

WP5 的工程目标不是：

> 必须制造出 Hybrid v2。

而是：

> 用受控实验判断当前优化方向是否值得继续进入正式验证。

最终得到：

```text
NO_VIABLE_CANDIDATE
```

本身就是一个有效实验结果。

------

## Q7：什么时候应该停止调参？

至少满足以下之一：

```text
Dev 无改善
新 regression 增加
搜索空间已耗尽
实现复杂度明显高于收益
进一步实验需要重新定义算法
```

这时应该：

```text
停止当前实验
保留证据
开始新的 Candidate design
```

而不是无限调参。

------

## Q8：为什么没看 Holdout 是优点而不是缺点？

因为 Holdout 的价值来自：

```text
未被用于选择
```

如果 Dev 都没有产生 Candidate，查看 Holdout 没有决策价值，只会污染下一轮实验。

------

# 15. 高频面试追问

## 追问 1：Hybrid v1 已经 Recall 更高，为什么还要继续优化？

因为 WP3 发现：

```text
Aggregate Quality ↑
但
Per-case Regression 超 Gate
```

说明 Hybrid v1 的问题不是“完全无效”，而是：

```text
收益和局部风险不平衡
```

因此值得先尝试低成本 Fusion 优化。

------

## 追问 2：为什么先试 Weighted RRF？

因为 WP3 regression root cause 中存在：

```text
FUSION_ORDERING_ERROR
TOP_K_DISPLACEMENT
```

所以最小改动方案就是调整：

```text
Dense/BM25 contribution
```

而不是直接增加更复杂的 reranker。

------

## 追问 3：最后发现 Weighted RRF 没作用说明什么？

说明当前问题不太可能通过：

```text
轻量 channel weighting
```

解决。

下一轮如果继续投入，可能需要：

```text
更强 Fusion Policy
Query-aware Fusion
Reranking
```

但当前阶段考虑时间和收益，没有继续扩大。

------

## 追问 4：你怎么证明权重真的生效了？

Final Gate 沿真实生产链路验证：

```text
Settings
→ lifespan
→ AgentRouter
→ HybridKnowledgeRetrievalAdapter
→ HybridRrfRetriever
```

并用分离通道的确定性测试证明改变权重会改变 fused score。

所以：

```text
VARIANT_RANKING_DISTINCT = NO
```

不是配置没生效。

------

## 追问 5：实验过程中出现错误权重怎么办？

没有删除历史结果。

先保留原证据，然后：

```text
确认 Contract mismatch
→ Fix-forward
→ 只重跑原冻结搜索空间
```

没有增加第三个 Variant，也没有查看 Holdout。

这样避免因为实现错误而破坏实验设计。

------

## 追问 6：为什么正式 Pair 是 INCONCLUSIVE，不是 FAIL？

因为：

```text
Hybrid v2 Candidate
```

根本没有被选出来。

所以不存在可供 Formal Gate 判断：

```text
PASS / FAIL
```

的 Candidate。

因此：

```text
HYBRID_V2_CANDIDATE_GATE = INCONCLUSIVE
```

这里的 INCONCLUSIVE 意味着：

> 没有进入 Candidate-level formal evaluation。

并不代表 WP5 工程结果不可信。

------

# 16. 30 秒面试总结

在第一轮 Hybrid RRF 因逐 Case 回归过多没有晋级以后，我把 Dataset 从 20 条扩到 60 条，并进一步拆成 Core、Dev 和 Holdout，避免直接用整个测试集调参。我分析了原来的四个 regression，发现主要涉及多相关文档竞争、Fusion Ordering 和 Top-K Displacement，因此先选择低成本 Weighted RRF 做第二轮实验，并提前冻结只有两组权重的搜索空间。过程中还发现执行脚本实际用了错误的 1.25/0.75 权重，Final Gate 修正后重新按 1.25/1.0 和 1.0/1.25 执行。最终权重确实生效，但两种方案都没有改变 Dev 排名和六项 Retrieval Metric，因此没有产生 viable Candidate。我没有查看 Holdout，也没有继续扩大参数搜索，而是终止本轮优化并保留 Baseline 作为 production default。

------

# 17. 2 分钟面试总结

WP3 中 Dense+BM25→RRF 的 Hybrid v1 在 Recall@1 和 Recall@3 上都有明显提升，但 20 个 Retrieval Case 中出现了 4 个逐 Case regression，超过提前冻结的 2/20 Gate，所以没有直接上线。

之后我先在 WP4 把 Dataset 扩到了 60 个 Retrieval Case。WP5 为了避免测试集过拟合，又把数据拆成 20 个 Frozen Core、20 个 Dev 和 20 个 Holdout。Core 用于历史 regression safety，Dev 用于 Candidate selection，Holdout 在 Candidate 冻结前完全禁止用于调参。

我对 WP3 的四个 regression 重新查看 Dense、BM25 和 RRF 排名，发现其中两个属于多相关文档竞争，一个是 Fusion Ordering Error，一个是 Top-K Displacement。因此没有立刻引入 Cross-Encoder 或 HyDE，而是先做成本最低、最容易解释的 Weighted RRF，并提前冻结两个候选：Dense 权重 1.25 和 BM25 权重 1.25。

执行过程中还发现了一个真实 Bad Case：最初脚本实际用了 1.25/0.75 和 0.75/1.25，和实验 Contract 不一致。Codex Final Gate 发现后只做窄范围 fix-forward，没有扩大搜索空间，也没有查看 Holdout。

修正以后，Production HybridRrfRetriever 能确认权重确实进入真实融合公式，但两个 Variant 在 Dev 上六项指标 Delta 都是 0，最终 selected ranking 也完全不变。说明当前 1.25 级别的轻量 channel weighting 虽然改变 score，但不足以改变 rank。因此没有产生 Hybrid v2 Candidate。

我最终没有因为项目需要 Hybrid 就继续盲目扩大权重或查看 Holdout，而是输出 `NO_VIABLE_CANDIDATE`，不运行 formal 44+44 experiment，生产默认继续保持 Baseline。我认为这一轮最大的工程价值不是调出了一个更好的参数，而是建立了 Dev/Holdout 防过拟合边界，并知道在证据不支持继续优化时及时停止。

------

# 18. 推荐学习文档文件名

```text
docs/interview/stage5_phase6_wp5_hybrid_retrieval_optimization.md
```

# 19. 本 WP 最值得记住的一句话

> **Evaluation-Driven Optimization（评估驱动优化）的目标不是把 Candidate 调到 PASS，而是在提前冻结的数据、搜索空间和 Holdout 边界下判断某个优化方向是否真的产生增益；如果没有，就应该停止，而不是继续调参直到测试集满意。**

WP5 学习/面试总结完成。

下一步就是 Phase6 最后的 **WP6 — Production Baseline Freeze & Phase6 Final Gate**：不再继续做 RAG 算法实验，只冻结 `BASELINE` 为当前 production default、保留 Hybrid experimental capability，并正式关闭 Phase6。