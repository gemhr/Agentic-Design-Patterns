当前模型：GPT-5.6 Sol。

# Stage5-Phase1-WP3 — NDCG Ranking Evaluator 学习 / 面试总结

推荐文件名：

```
docs/interview_materials/stage5_phase1_wp3_ndcg_ranking_evaluator.md
```

------

# 1. 本 WP 解决了什么问题

在前一个 WP 中，已经实现：

```
Recall@K
→ 相关内容有没有被召回

MRR
→ 第一条相关结果排得够不够靠前
```

但这两个指标无法完整评价：

> 当多个 Chunk 都相关、但相关程度不同时，整个排序质量到底怎么样？

因此本 WP 引入 NDCG@K（Normalized Discounted Cumulative Gain，归一化折损累计增益），使用 `RankingGroundTruth.graded_relevance` 与真实 RAG Artifact 中的 `ranked_items[].rank` 评价多等级相关性下的整体排序质量。30_zcode_ndcg_evaluator.mdMD

现在 Retrieval Evaluation 已经形成：

```
                     Retrieval Evaluation

                    ┌──────────────────┐
                    │   Ground Truth   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Real Artifact   │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
      Recall@K              MRR              NDCG@K
          │                  │                  │
      召回覆盖率        第一相关结果排名      整体排序质量
```

------

# 2. 为什么 Recall@K 和 MRR 还不够

假设 Ground Truth 是：

```
A relevance=3   高度相关
B relevance=2   相关
C relevance=1   弱相关
```

系统一：

```
A
B
C
```

系统二：

```
C
B
A
```

如果看：

```
Recall@3
```

两个系统都是：

```
1.0
```

因为相关内容全部找到了。

但显然系统一更好，因为最有价值的内容排在最前面。

MRR 也只能重点反映：

> 第一条 relevant result 排在什么位置。

它无法充分反映整个 Top-K 内：

```
高相关
中相关
弱相关
```

之间的排序质量。

因此需要 NDCG。

------

# 3. NDCG 核心思想

NDCG 可以理解成：

> 越相关的内容越应该排在前面；如果高相关内容排得越靠后，就给予越大的排名折损。

本 WP 使用标准指数 Gain（增益）：

```
gain(rel) = 2^rel - 1
```

例如：

```
rel=0 → gain=0
rel=1 → gain=1
rel=2 → gain=3
rel=3 → gain=7
```

所以 relevance=3 的内容比 relevance=1 的内容价值明显更高。30_zcode_ndcg_evaluator.mdMD

------

# 4. DCG、IDCG、NDCG

## DCG

DCG（Discounted Cumulative Gain，折损累计增益）：

```
DCG@K =
Σ (2^rel - 1) / log2(rank + 1)
```

同时考虑：

```
相关程度
+
排名位置
```

例如一个 relevance=3 的 Chunk：

```
rank=1
```

贡献很高。

如果它：

```
rank=10
```

贡献就被明显折损。

------

## IDCG

IDCG（Ideal Discounted Cumulative Gain，理想折损累计增益）表示：

> 如果所有 Ground Truth 都按照最理想的 relevance 从高到低排列，理论上最高能得到多少 DCG。

例如：

```
A=3
B=2
C=1
```

理想排序就是：

```
A
B
C
```

------

## NDCG

最终：

```
NDCG@K = DCG@K / IDCG@K
```

因此：

```
0 <= NDCG <= 1
```

完美排序：

```
NDCG = 1
```

当前实现的结果对象也对 `[0, 1]` 范围进行了验证。30_zcode_ndcg_evaluator.mdMD

------

# 5. 为什么需要 Graded Relevance

Recall 更适合：

```
Relevant
Not Relevant
```

即 Binary Relevance（二元相关性）。

但真实 RAG 中，经常出现：

```
Chunk A
→ 直接包含问题答案

Chunk B
→ 提供关键背景信息

Chunk C
→ 只有部分关系

Chunk D
→ 完全无关
```

因此本项目 Ground Truth 支持：

```
0 / 1 / 2 / 3...
```

这样的 Graded Relevance（分级相关性）。

NDCG 正是针对这种情况设计的。

------

# 6. 为什么 Evaluator 必须使用真实 `rank`

本 WP 明确规定：

```
RagEvaluationArtifactV1.ranked_items[].rank
```

是最终 Ranking 的事实来源。30_zcode_ndcg_evaluator.mdMD

Evaluator 不能：

```
读取 score
↓
重新排序
↓
计算 NDCG
```

因为这样评价的已经不是系统真实产生的排序。

正确关系应该是：

```
Runtime / Reranker
        ↓
产生 Ranking Fact
        ↓
保存 Artifact
        ↓
Evaluator
        ↓
Measure
```

核心原则：

> Evaluator 应该测量系统行为，而不是重新实现或修改被评价系统的行为。

------

# 7. 为什么 NDCG 不使用 Retrieval Rank fallback

WP2 的 MRR 在没有 `ranked_items` 时允许：

```
retrieved_items.retrieval_rank
```

作为明确标注 provenance 的 fallback。

但本 WP NDCG 不这么做。

如果：

```
ranked_items=[]
```

则：

```
NDCG=0
```

即使还有 `retrieved_items`。30_zcode_ndcg_evaluator.mdMD

原因是这里明确评价：

> Final Ranking Quality。

如果没有最终 Ranking 事实，就不能偷偷把：

```
Retrieval Rank
```

当成：

```
Final Ranking
```

否则虽然“算出了指标”，但指标语义已经改变。

这是非常重要的 Evaluation 工程原则：

> **宁愿明确缺失，也不要为了得到一个数字而偷换 Metric 的含义。**

------

# 8. Identity Matching 为什么重要

Ground Truth 和 Artifact 必须知道：

> 两边描述的是不是同一个 Chunk。

正常身份：

```
(document_id, chunk_id)
```

例如：

```
("docA", "chunk1")
```

WP1 允许：

```
document_id=None
```

因此可能出现：

```
(None, "chunk1")
```

当前规则是：

如果 Artifact 里只有：

```
docA/chunk1
```

则可以唯一匹配。

但如果同时存在：

```
docA/chunk1
docB/chunk1
```

Ground Truth 又只有：

```
(None, chunk1)
```

则无法知道应该对应哪个。

此时：

```
Fail Closed
```

而不是随机选一个。30_zcode_ndcg_evaluator.mdMD

------

# 9. 本 WP 的真实 Bad Case

本次 Review 找到了一个真实的 Correctness Gap（正确性缺口）。

Ground Truth：

```
(None, chunk1)       relevance=3
(docA, chunk1)       relevance=2
```

Artifact：

```
docA/chunk1 rank=1
```

修复前，两条 GT 都可能解析到：

```
docA/chunk1
```

于是一个 Artifact item 被计算两次 Gain。

可能出现：

```
DCG 被虚高
甚至
DCG > IDCG
```

最终导致错误的 NDCG。

这个问题在第一次实现的 Handoff 中被记录为 Known Limitation，Review 后被升级为必须修复的 correctness issue。30_zcode_ndcg_evaluator.mdMD

------

# 10. 为什么最终选择 Fail Closed

没有选择：

```
merge 两条 Ground Truth
```

也没有：

```
max(relevance)
```

更没有：

```
随机取一个
```

最终实现：

```
两个不同 Ground Truth Identity
             ↓
解析到了同一个 Artifact Identity
             ↓
          ValueError
```

原因：

Evaluator 无权自行决定：

> “Dataset 里这两个 Ground Truth 其实应该算一个。”

那属于 Dataset 作者或 Schema 的语义。

Evaluator 应该：

```
发现无法确定
→ 明确拒绝计算
```

修复后新增 4 个 Regression Test（回归测试），原有测试全部保持通过：

```
NDCG focused:
23 passed

Full unit suite:
735 passed
```

31_zcode_ndcg_identity_fix.mdMD

------

# 11. Recall@K、MRR、NDCG 怎么一起看

这三个指标不是互相替代，而是互补。

| 指标     | 核心问题                     | 更适合诊断                 |
| -------- | ---------------------------- | -------------------------- |
| Recall@K | 相关内容找没找到             | Retriever 召回能力         |
| MRR      | 第一条相关结果靠不靠前       | 首个正确结果排序           |
| NDCG@K   | 高相关内容整体有没有排在前面 | Reranker / Ranking Quality |

例如：

```
Recall@10 ↑
MRR ↓
NDCG ↓
```

可能意味着：

> Retriever 找到了更多相关内容，但引入了大量噪声，高价值内容反而被挤到了后面。

而：

```
Recall@10 基本不变
MRR ↑
NDCG ↑
```

通常说明：

> 召回覆盖率没有明显变化，但 Ranking / Reranking 明显改善。

因此实际优化 RAG 时不能只盯一个指标。

------

# 12. 本 WP 的真实性边界

## 已真实实现

```
NDCG@K
Graded Relevance
DCG / IDCG
rank-based evaluation
optional document identity resolution
identity ambiguity fail closed
identity overlap fail closed
```

## 已真实测试

```
Perfect Ranking
Reverse Ranking
Partial Hit
No Hit
Empty Ranking
Zero Relevance
K Boundary
Rank Field Precedence
Duplicate Artifact Identity
Optional document_id
Ambiguous Identity
Overlapping GT Identity
```

最终 NDCG focused tests：

```
23 passed
```

全量 Unit：

```
735 passed
```

31_zcode_ndcg_identity_fix.mdMD

## 尚未实现

不能在面试中描述为完成：

```
LLM Judge
Evaluation Runner
Dataset Batch Evaluation
Mean NDCG Aggregation
真实 RAG Baseline
RAG 自动优化闭环
Dashboard
```

31_zcode_ndcg_identity_fix.mdMD

------

# 13. 本 WP 名词 / 概念速览

- **NDCG@K**：衡量 Top-K 结果中高相关内容是否被整体排在前面的归一化排序指标。
- **DCG**：同时考虑相关性收益和排名位置折损后的累计排序得分。
- **IDCG**：Ground Truth 按最理想顺序排列时能够获得的最大 DCG。
- **Gain**：把 relevance 转换成排序价值的函数，本 WP 使用 `2^rel - 1`。
- **Discount**：随着结果排名变低而降低该结果贡献的机制。
- **Graded Relevance**：使用多个等级描述结果相关程度，而非只有相关/不相关。
- **Binary Relevance**：只把结果划分为 Relevant 和 Irrelevant 两种状态。
- **Ranking**：按照相关程度或其他标准对候选结果进行排序。
- **Reranking**：在初始召回后，使用更精细的方法重新排列候选结果。
- **Rank**：某个结果在最终排序中的位置。
- **Top-K**：只观察排名前 K 个结果的评价范围。
- **Metric**：用于量化系统某个质量维度的指标。
- **Ground Truth**：用于判断系统结果是否正确或优秀的预先标注标准。
- **Artifact**：真实系统执行后留下的、供 Evaluation 消费的结构化证据。
- **Identity Matching**：判断 Ground Truth 和实际结果是否描述同一个对象。
- **Identity Resolution**：根据现有标识信息解析一个评价对象实际对应哪个结果。
- **Ambiguity**：现有身份信息不足以唯一确定目标对象的状态。
- **Fail Closed**：无法确定结果时拒绝继续，而不是猜测。
- **Duplicate Identity**：同一个逻辑对象在系统结果中被重复记录。
- **Pure Function**：只依赖输入计算输出、不访问或修改外部状态的函数。
- **Evaluator**：根据实际执行证据和 Ground Truth 计算评价指标的组件。
- **Regression Test**：确保已经修复的问题以后不会重新出现的测试。
- **Provenance**：描述一个数据或评价结果来源和产生过程的信息。
- **Correctness Gap**：正常路径工作但某些合法输入会产生错误结果的实现缺陷。

------

# 14. 工程构建方法类提问

这部分重点不是背本项目代码，而是训练设计和取舍能力。

1. 一个 RAG 系统为什么不能只使用 Recall@K，还需要 MRR、NDCG 等指标？
2. 什么场景更适合 MRR，什么场景更适合 NDCG？
3. 如何设计 Ground Truth，才能同时支撑 Retrieval Evaluation 和 Ranking Evaluation？
4. relevance 应该使用二分类还是多等级标注？依据是什么？
5. Graded Relevance 使用 0～3、0～5 或其他范围时应该考虑哪些因素？
6. Evaluation 为什么应该消费真实运行 Artifact，而不是为了评价重新执行 Retrieval？
7. 当 Metric 需要的数据缺失时，应该返回 0、跳过、fallback 还是失败？怎么决策？
8. 如何区分“系统质量确实是 0”和“这个指标根本无法计算”？
9. Ground Truth Identity 信息不足时，什么时候适合模糊匹配，什么时候必须 fail closed？
10. Dataset Schema 应该偏宽松还是偏严格？怎样平衡标注体验与指标正确性？
11. 系统结果里出现 Duplicate Item 时，排名指标应该如何处理？
12. 两个 Ground Truth 条目解析到同一个实际结果时，应该合并、取 max relevance 还是拒绝？
13. 为什么 Metric 计算通常适合实现成 Pure Function？
14. Dataset Load、Agent Execute、Artifact Capture、Evaluator、Aggregation 为什么通常要分层？
15. Recall 上升但 NDCG 下降时，应该怎样判断一次 Retrieval 改动是否值得上线？
16. 构建 Evaluation Framework 时，为什么通常应该先解决 Artifact、Dataset、Ground Truth，再开始写大量 Metric？
17. Offline Evaluation 很好，线上效果为什么仍然可能下降？
18. 怎样防止 Evaluator 自己的 Bug 导致团队误判一个 RAG 版本已经提升？
19. Evaluation Metric 的输入 Contract 应该由被评价系统还是 Evaluation 平台定义？
20. 什么情况下应该继续维护几个简单 Evaluator，什么情况下才值得引入 Metric Registry / Evaluator Framework？

------

# 15. 30 秒面试版本

> 在 AgentEvalOps 的 RAG Evaluation 中，我除了实现 Recall@K 和 MRR，还增加了 NDCG@K 来评价多等级相关性的整体排序质量。Ground Truth 使用 graded relevance，Evaluator 直接消费 LocalAgent 真实执行 Artifact 中的最终 `rank`，不会根据 score 自己重新排序。实现过程中还发现过一个 Identity Resolution 的问题：optional document identity 和精确 identity 可能同时映射到同一个 Chunk，导致 Gain 重复计算。我最终采用 fail-closed 策略，并增加回归测试保证指标不会因为身份歧义被错误放大。

------

# 16. 2 分钟面试版本

> 在 RAG Evaluation 里，我没有只用 Recall@K，因为 Recall 只能告诉我相关内容有没有进入 Top-K，却无法反映不同相关程度内容的整体排序质量。前面我已经实现了 Recall@K 和 MRR，MRR 更关注第一条 relevant result 的位置，这一阶段又增加了 NDCG@K，用于评价 graded relevance 场景。
>
> Dataset 里会给 Chunk 标注不同 relevance，比如 0、1、2、3。NDCG 先根据 `2^rel-1` 计算 Gain，再根据 rank 做 logarithmic discount，得到 DCG，然后跟 Ground Truth 理想排序对应的 IDCG 做归一化。因此高相关 Chunk 如果被排到很后面，指标会受到明显惩罚。
>
> 工程上我有一个比较重要的约束：Evaluator 不重新执行 Retrieval，也不按照 score 重新排序，而是直接读取 LocalAgent 真实 RAG Artifact 中的 `ranked_items[].rank`，因为 Evaluation 应该测量系统真实行为，而不能重新生成被评价对象。
>
> 实现过程中还发现了一个 Identity Correctness 问题。Ground Truth 支持 optional `document_id`，所以 `(None, chunk1)` 和 `(docA, chunk1)` 有可能同时解析到同一个 `docA/chunk1`，导致一个 Artifact item 重复贡献 Gain。这个问题如果静默处理甚至可能导致 DCG 大于 IDCG。我没有在 Evaluator 中擅自 merge relevance 或取最大值，而是采用 fail-closed 策略，把这种情况作为输入歧义拒绝计算。修复后 NDCG focused tests 23 个全部通过，全量 unit tests 735 个通过。
>
> 现在 Retrieval Evaluation 已经分别用 Recall@K 衡量召回覆盖，用 MRR 衡量第一条相关结果位置，用 NDCG 衡量整体多等级排序质量；下一步才会进入 Generation Evaluation，比如 LLM Judge。31_zcode_ndcg_identity_fix.mdMD

------

# 17. 本 WP 高频追问与参考回答

## Q1：为什么已经有 Recall@K 和 MRR，还要实现 NDCG？

**回答：**

> Recall@K 主要评价是否召回，MRR 主要关注第一条相关结果的位置，但真实 RAG 中多个 Chunk 的相关程度并不完全相同。NDCG 支持 graded relevance，可以评价整个 Top-K 中高相关结果是不是整体排在更前面，所以更适合评价 Reranker 和最终 Ranking Quality。

------

## Q2：MRR 和 NDCG 最大的区别是什么？

**回答：**

> MRR 重点看第一条 relevant result，所以对第一条正确结果非常敏感，但后续相关结果基本不影响指标。NDCG 会考虑 Top-K 内多个结果及其不同 relevance，因此更适合评价整体排序质量。

------

## Q3：你的 NDCG 为什么使用 `2^rel - 1`？

**回答：**

> 这是常见的指数 Gain 设计，它会让高 relevance 内容获得更大的收益差异。例如 relevance 3 的收益明显高于 relevance 1，更符合“高度相关结果应该优先排到前面”的 Ranking 评价目标。

------

## Q4：为什么还需要 IDCG，直接看 DCG 不行吗？

**回答：**

> 不同 Case 的 relevant item 数量和 relevance 分布可能不同，所以原始 DCG 不适合直接横向比较。IDCG 表示这个 Case 理论上的最佳排序分数，通过 `DCG / IDCG` 归一化后，NDCG 落在 0 到 1 范围内，不同 Case 之间更容易比较。

------

## Q5：NDCG=1 是什么意思？

**回答：**

> 表示在当前 K 范围内，系统结果达到了 Ground Truth 对应的理想排序，也就是高 relevance 内容已经按照最优顺序排列。

------

## Q6：为什么不根据 Artifact 里的 score 再排序以后计算 NDCG？

**回答：**

> 因为 Evaluator 的职责是测量真实系统行为，而不是重新实现 Ranking。如果我根据 score 再排序，评价的就是 Evaluator 构造出来的排序，而不是 Runtime 实际给模型使用的排序，所以我直接以 Artifact 中的最终 `rank` 作为事实来源。

------

## Q7：如果 `ranked_items` 没有数据，为什么不 fallback 到 retrieval rank？

**回答：**

> 因为这一指标明确评价最终 Ranking Quality。Retrieval Rank 和 Final Ranking 不是同一个语义，如果直接 fallback，虽然能得到数字，但指标含义已经变化。我更倾向于保留明确的评价语义，而不是为了“算出来”而偷换事实。

------

## Q8：Ground Truth 的 relevance 是怎么来的？

**回答：**

> 当前阶段 Ground Truth Schema 已经支持 graded relevance，但还没有建设自动标注平台，主要由人工或领域知识定义 relevance。后续如果 Dataset 规模扩大，需要进一步建设标注规范、多人一致性和标注质量校验。

这句话需要保留，因为目前确实没有完成大规模自动标注体系。

------

## Q9：为什么 `document_id=None` 会有问题？

**回答：**

> 因为 `chunk_id` 不一定在整个知识库全局唯一。如果只有 `chunk1`，Artifact 又同时存在 `docA/chunk1` 和 `docB/chunk1`，Evaluator 就无法判断 Ground Truth 指的是哪一个。因此这种情况不能猜测，需要进行 ambiguity detection。

------

## Q10：遇到 Identity Ambiguity 为什么选择 Fail Closed？

**回答：**

> 因为 Ground Truth 是评价标准，Evaluator 不应该自行补充业务语义。如果它无法唯一确定 Ground Truth 对应哪个实际对象，自动选一个可能直接污染 Metric。所以我宁愿让本次评价明确失败，再要求 Dataset 消歧。

------

## Q11：你们这次实际遇到过什么 NDCG Bad Case？

**回答：**

> Review 时发现 Ground Truth 可以同时存在 `(None, chunk1)` 和 `(docA, chunk1)`，而 Artifact 里只有 `docA/chunk1` 时，两条 Ground Truth 会解析到同一个结果，导致同一 Chunk 重复贡献 Gain。最终我们增加 Artifact Identity ownership 检查，不同 GT identity 如果解析到同一个实际 item 就 fail closed，并增加了 4 个 Regression Test。31_zcode_ndcg_identity_fix.mdMD

------

## Q12：为什么不把两个 Ground Truth 的 relevance 合并或者取最大值？

**回答：**

> 因为那相当于 Evaluator 在修改 Dataset 的语义。Dataset 明确声明了两个不同 Ground Truth identity，Evaluator 无法证明它们实际上应该合并，所以不能擅自用 max 或 merge，而应该暴露数据歧义。

------

## Q13：Recall 提升但 NDCG 下降意味着什么？

**回答：**

> 通常说明 Retriever 找到了更多相关内容，但排序质量变差，或者新增结果带来了较多噪声，把高价值 Chunk 挤到了后面。所以不能仅凭 Recall 上升就判断整个 RAG 优化成功，还需要结合 MRR、NDCG，最终再结合 Generation Evaluation 判断。

------

## Q14：为什么把这些指标实现成 Pure Function？

**回答：**

> Metric Calculation 本身只需要 Ground Truth 和 Artifact，不应该负责加载 Dataset、执行 Agent 或访问数据库。Pure Function 更容易测试、复用，也能防止 Evaluation orchestration 和指标算法互相耦合。

------

## Q15：你现在能不能说已经做完完整的 RAG Evaluation？

**回答：**

> 还不能。目前已经完成 Evaluation Dataset、RAG Artifact Bridge，以及 Retrieval 侧的 Recall@K、MRR、NDCG。Generation Evaluation 的 LLM Judge、Dataset Batch Runner、真实 Baseline 和自动优化闭环还没有完成，所以我会把当前阶段准确描述成 Retrieval Evaluation 能力已经建立，而不是完整 Evaluation 平台已经完成。31_zcode_ndcg_identity_fix.mdMD

------

# 18. 本 WP 学习完成状态

```
Stage5-Phase1-WP3
NDCG Ranking Evaluator

Implementation                 PASS
Identity Correctness Fix       PASS
Focused Tests                  23 PASS
Full Unit Tests                735 PASS
Learning / Interview Summary   COMPLETE
```

下一阶段仍然是：

```
Stage5-Phase1-WP4
Generation Evaluator
→ LLM Judge
```