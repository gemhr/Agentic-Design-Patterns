当前模型：GPT-5.6 Sol。

# Stage5-Phase3 WP0/WP0B Closeout 学习总结

## BEIR SciFact Persistent Dense Index Cache

本次学习重点不是 RAG 算法本身，而是一个很典型的生产级 Evaluation Infrastructure（评估基础设施）问题：

> **当公开 Benchmark 的向量索引构建一次需要约 90 分钟时，如何把一次性实验资产升级成可验证、可复用、自动失效且不会污染实验公平性的持久化缓存。**

本次最终真实结果是：SciFact 的 5183 个 Document、9548 个 Chunk 使用 `Qwen3-Embedding-0.6B` 完成持久化 Dense Index；Warm Reuse（热复用）实际命中 `CACHE_HIT`，校验约 18 秒，整个 warm command 约 22 秒，并且没有重新 Embedding；随后完整 300 Query 重跑的六项指标与原冻结 Baseline **完全一致**。30_beir_scifact_dense_index_cache_closeout.mdMD

------

# 一、这个 WP 实际解决了什么

修复前：

```
SciFact 5183 docs
    ↓
9548 chunks
    ↓
Qwen Embedding on CPU
    ↓
~90 min
    ↓
pytest temporary Chroma
    ↓
Benchmark
    ↓
temp directory cleanup
    ↓
Index 丢失
```

这意味着后续每做一次：

```
BM25
RRF
Cross-Encoder
No-Answer
Context Selection
```

都可能重复付出约 90 分钟 Dense Index Build 成本。

修复后：

```
SciFact Asset
    ↓
Deterministic Cache Identity
    ↓
Cache validation
    │
    ├─ MISS → Build → Validate → READY → Publish
    │
    └─ HIT  → Reuse
                    ↓
              Existing Chroma
                    ↓
              Benchmark Run
```

核心变化不是：

> Embedding 更快了。

而是：

> **同一 Index Semantic（索引语义）下，Embedding 只做一次。**

这是两个完全不同的优化层级。

------

# 二、最重要的工程设计：Cache Identity

本次生成了确定性的 Cache Identity：

```
b63c0bbd115150da766b84a80331b332010812bbb757a6782df9ae2224ca8f46
```

并使用：

```
beir-scifact-dense-index-cache.v1
```

作为 Cache Schema。30_beir_scifact_dense_index_cache_closeout.mdMD

Cache Key 的设计原则是：

> **只有真正影响向量索引内容的事实才应该进入 Cache Identity。**

例如应该进入：

```
Corpus digest
Chunk manifest digest
Embedding model identity
Embedding dimension
Embedding prompt
Splitter identity
Chunk size
Chunk overlap
```

因为这些变化都会导致：

```
最终写入 Chroma 的 vector / chunk
```

发生变化。

------

# 三、为什么 `candidate_limit=8` 不能放进 Cache Key

这是本 WP 一个很值得面试讲的设计点。

当前：

```
candidate_limit = 8
```

属于 Query-time Configuration（查询时配置）。

它只决定：

```
Query
→ 从现有 Index 取多少结果
```

并不会改变：

```
Document
→ Chunk
→ Embedding
→ Stored Vector
```

因此：

```
candidate_limit 8 → 20
```

不应该导致：

```
重新 Embedding 9548 chunks
```

同理：

```
minimum_score
rerank_top_k
selection top_k
MRR evaluator version
NDCG evaluator version
```

也不应该成为 Dense Index Cache Key。

这背后其实是在区分：

```
Index-time Configuration
```

和：

```
Query-time Configuration
```

这是生产级 RAG 系统非常重要的配置边界。

------

# 四、为什么不能“目录存在就直接复用”

一个非常差的实现是：

```
if cache_dir.exists():
    use_cache()
```

因为目录存在不代表：

```
Index 完整
Index 正确
Index 与当前配置兼容
```

比如：

```
90 分钟 build
↓
70 分钟时进程被杀
↓
目录已经存在
```

下次如果只检查：

```
Path.exists()
```

就可能把一个半成品当正常 Index。

因此本次增加了：

```
BUILDING / READY
```

或者等价的 Completion Contract（完成合同）。

最终原则：

> **Only READY cache is reusable.**

文档确认现在不完整 Cache 会被判为 `CACHE_INCOMPLETE`，Semantic Metadata 不一致则为 `CACHE_INVALID`，只有 READY Cache 才允许加载。30_beir_scifact_dense_index_cache_closeout.mdMD

------

# 五、Fail Closed 为什么重要

Cache 最危险的情况通常不是：

```
Cache miss
```

而是：

```
Cache hit 了一个错误的 Index
```

例如：

Baseline 使用：

```
Qwen3-Embedding-0.6B
```

后来配置切到另一个 Embedding：

```
Model B
```

如果系统仍然复用 Qwen 生成的旧 Chroma：

```
Query Vector from Model B
        ↓
Search
        ↓
Document Vector from Model A
```

即使维度相同：

```
1024 == 1024
```

也完全不能证明两个向量空间兼容。

所以正确策略不是：

```
有 Cache 就尽量用
```

而是：

```
不能证明一致
→ 不允许复用
```

这就是 Fail Closed（失败关闭）。

------

# 六、为什么还需要 Manifest Hash

单独记录：

```
Corpus SHA
```

仍然不够。

因为：

```
相同 Corpus
```

在：

```
不同 Chunker
不同 chunk_size
不同 overlap
```

下会产生完全不同的 Chunk。

所以这里还冻结了：

```
9548 chunk identities
manifest SHA-256 =
8CC45BD6163E958B1C374054E1F59433048446EB896AEE8683F174069F8602BB
```

这样 Cache 的真实逻辑变成：

```
Source identity
+
Transformation identity
+
Embedding identity
=
Index identity
```

而不只是：

```
文件名相同
=
Index 相同
```

------

# 七、Persistent Cache 与普通 Cache 最大的区别

这里的 Cache 不是：

```
为了省几十毫秒
```

而是一个高成本 Artifact Cache（制品缓存）。

它缓存的是：

```
9548 chunk embeddings
+
Chroma index
```

构建成本约：

```
90 minutes
```

所以它更类似：

```
CI Build Artifact
Docker Layer
Compiler Cache
ML Feature Cache
```

而不是：

```
Redis GET cache
```

设计重点也因此不同。

它更关注：

```
Identity
Provenance
Integrity
Invalidation
Reproducibility
Atomic Publication
```

而不是 TTL。

------

# 八、为什么不能简单使用 TTL

比如：

```
Cache 保留七天
```

对于这种 Evaluation Index 并没有多少意义。

七天之后：

```
Corpus 没变
Chunking 没变
Embedding 没变
```

索引依然有效。

反过来：

一小时前如果：

```
Embedding Model 改了
```

那即使 Cache 只存在一小时：

```
也已经失效
```

所以这里适合：

```
Content / Configuration Addressed Cache
```

而不是：

```
Time-based Expiration
```

------

# 九、No-Reembedding Proof 为什么必须实际验证

不能只根据代码阅读说：

> Warm Cache 应该不会重新 Embedding。

本次真正做的是：

```
Cold Build
→ persistent index

Warm Command
→ CACHE_HIT
→ 只 materialize / split / identity / metadata validation
→ 不实例化 VectorDBManager
→ 不调用 ingest
→ embedding_rebuild = NO
```

这个属于：

```
REAL_TEST
```

而不是：

```
架构推断
```

文档明确记录 Warm Reuse 的 `CACHE_HIT` 和 `embedding_rebuild = NO`。30_beir_scifact_dense_index_cache_closeout.mdMD

这就是为什么生产工程里：

> “代码看起来会复用”

和：

> “已经证明真正没有重算”

是两种不同等级的证据。

------

# 十、为什么还要重新跑 300 Query Baseline

这是本次最关键的 Regression Gate（回归门禁）。

我们修改了 Benchmark Infrastructure。

虽然理论上：

```
只改 Cache
不改 Retrieval
```

但如果改错：

```
加载错误 Collection
少了一部分 Chunk
metadata 对不上
Index 污染
```

一样会导致指标改变。

因此必须验证：

```
Before Cache Change
vs
After Cache Change
```

六项结果：

```
Recall@1  = 0.5451111111111111
Recall@3  = 0.7307222222222223
Recall@5  = 0.7763333333333333

MRR       = 0.6631746031746032

NDCG@3    = 0.6616894303340216
NDCG@5    = 0.6810530658917988
```

最终：

```
exact equal
```

30_beir_scifact_dense_index_cache_closeout.mdMD

因此可以比较有把握地说：

> Cache 优化改变了 Benchmark 执行成本，没有改变 Benchmark Retrieval Semantics。

这就是本次最重要的工程证明。

------

# 十一、本 WP 涉及名词 / 概念速览

1. **Index Cache（索引缓存）**：缓存已经构建完成的 Retrieval Index，避免相同数据与配置下重复 Embedding 和建索引。
2. **Cache Identity（缓存身份）**：由影响缓存内容的输入和配置确定，用来判断两个 Cache 是否语义等价。
3. **Cache Key（缓存键）**：Cache Identity 的机器可使用表示，本项目最终是稳定 Hash。
4. **Cache Invalidation（缓存失效）**：当 Corpus、Chunking、Embedding 等 Index Semantic 改变时拒绝复用旧 Cache。
5. **Content-addressed Cache（内容寻址缓存）**：根据内容/配置摘要决定缓存身份，而不是根据创建时间。
6. **Fail Closed（失败关闭）**：无法证明 Cache 正确时拒绝使用，而不是尝试“凑合复用”。
7. **Provenance（来源追踪）**：记录 Index 是由哪个 Dataset、Chunking、Embedding 等条件产生。
8. **Manifest（清单）**：保存所有 Chunk Identity 等确定性资产信息，用于确认 Index 输入是否一致。
9. **READY Marker（就绪标记）**：只有完整完成并通过验证的 Cache 才进入 READY 状态。
10. **Partial Build（部分构建）**：构建过程中断留下的半成品，必须禁止复用。
11. **Atomic Publish（原子发布）**：先构建到临时位置，完整成功后再将其暴露为可用 Cache。
12. **Cold Build（冷构建）**：无有效 Cache，需要实际执行完整 Embedding/Index Build。
13. **Warm Reuse（热复用）**：有效 Cache 已存在，只验证并直接加载。
14. **Index-time Configuration（索引时配置）**：会改变存储向量或 Chunk 的配置，例如 Embedding Model、Chunk Size。
15. **Query-time Configuration（查询时配置）**：只影响搜索过程、不改变 Index 本体的配置，例如 Candidate Limit。
16. **Baseline Reproduction（基线复现）**：在相同冻结条件下重新执行 Benchmark，并验证指标/结果保持一致。
17. **Artifact Cache（制品缓存）**：缓存高成本构建产物，而不是简单缓存请求结果。
18. **Determinism（确定性）**：相同输入与配置应得到相同 Manifest、Cache Identity 和可比较的 Retrieval 结果。

------

# 十二、工程构建方法类提问

## 1. 一个 RAG Index Cache 的 Key 应该怎么设计？

核心原则：

> 从“这个参数变化是否会改变实际 Index 内容”出发。

例如：

```
Embedding Model
→ YES

Chunk Size
→ YES

Corpus SHA
→ YES

candidate_limit
→ NO

rerank_top_k
→ NO
```

不能偷懒直接把完整 Settings Hash 全部作为 Cache Key。

否则任何：

```
report config
timeout
top_k
```

小变化都可能触发昂贵重建。

------

## 2. 为什么不能直接使用 Git Commit SHA 作为 Cache Key？

因为 Git SHA 太粗。

例如：

```
README 修改
→ Git SHA changed
```

但：

```
Dense Index Semantics
```

完全没有变化。

如果这样设计：

```
每次 commit
→ Cache miss
→ 重新 90 分钟
```

等于 Cache 失去了意义。

因此应该通过真正影响 Index Semantic 的字段构建 Cache Identity。

------

## 3. 为什么 Cache Hit 也需要 Validation？

因为：

```
目录存在
```

只能证明文件系统上有东西。

不能证明：

```
模型相同
Corpus 相同
Chunking 相同
Build 完成
Collection 正确
```

所以 Cache Hit 实际应该是：

```
Physical Cache Exists
+
Metadata Valid
+
READY
+
Collection Valid
=
CACHE_HIT
```

------

## 4. 为什么 Query-time 参数和 Index-time 参数要分开？

因为这直接决定：

```
什么变化需要 rebuild
```

例如：

```
candidate_limit 8 → 20
```

只影响：

```
搜索时取多少 Candidate
```

如果因此重建 Embedding Index：

就是典型的无效计算。

这种配置分层同样适用于：

- Vector DB；
- Search Engine；
- Feature Store；
- ML Pipeline。

------

## 5. 为什么 Baseline Infrastructure 修改也需要 Regression Test？

因为 Infrastructure 依然可能改变行为。

例如：

```
Cache 加载了错误 Collection
```

最终：

```
Retrieval Results
```

当然会变化。

所以：

> “我没有修改算法”

不能替代：

> “我证明结果没有变化”。

------

# 十三、这个 WP 可以形成的 Bad Case

## Bad Case：Benchmark 每次都重新构建 Dense Index

**真实性：真实。**

触发条件：

```
BEIR SciFact Benchmark
→ pytest temp Chroma
→ 执行结束后 Index 被清理
```

结果：

```
每次完整 run
→ 重新 Embedding 9548 chunks
→ 约 90 分钟
```

根因不是 Embedding 模型慢这么简单，而是：

```
Prebuilt Directory
```

只有目录复用能力，没有：

```
Cache Identity
READY Contract
Validation
Persistent Lifecycle
```

修复：

```
Deterministic identity
+
persistent index
+
metadata validation
+
READY marker
+
warm reuse
```

结果：

```
Cold Build     ≈ 90 min

Warm validation ≈ 18 s
Warm command    ≈ 22 s
Reembedding     NO
```

并且 Baseline 六项指标 exact equal。30_beir_scifact_dense_index_cache_closeout.mdMD

这是一个非常适合作为面试 **“Evaluation Infrastructure 性能优化”** 的真实案例。

------

# 十四、30 秒面试版本

> 我在做 Agent RAG Evaluation 时发现，BEIR SciFact 有 5183 篇文档、9548 个 Chunk，本地 Qwen Embedding 在 CPU 上完整建一次 Chroma Index 要接近 90 分钟，而且之前 Index 放在 pytest 临时目录，每次 Benchmark 结束都会丢失。后来我把它改造成一个持久化的 Dense Index Cache，Cache Identity 只包含 Corpus、Chunk Manifest、Embedding 和 Chunking 等真正影响 Index Semantic 的配置，并通过 READY Marker 和 Metadata Validation 做 fail-closed 校验。真实验证后 Warm Run 可以直接 Cache Hit，约 22 秒完成准备且不会重新 Embedding，同时重新跑 300 条 SciFact Query，Recall、MRR、NDCG 六项指标和旧 Baseline 完全一致。

------

# 十五、2 分钟面试版本

> 在 Stage5 的 RAG 优化阶段，我引入了 BEIR SciFact 作为公开 Retrieval Benchmark。数据大约有 5183 篇 Document，经过 LocalAgent 现有 Chunker 后生成 9548 个 Chunk，使用本地 Qwen3-Embedding-0.6B 在 CPU 上完整建立 Dense Chroma Index 一次大约需要 90 分钟。
>
> 最开始 Index 是由 Integration Test 建到 pytest 临时目录里的，Benchmark 跑完以后目录会被清理，所以后续做 BM25、RRF、Cross-Encoder 时，每个实验都可能重新支付一次 90 分钟的 Embedding 成本。
>
> 我没有去优化 Embedding 算法，而是把这个问题定位成 Evaluation Infrastructure 的 Artifact Lifecycle 问题，增加了持久化 Dense Index Cache。
>
> Cache Key 没有直接用完整配置或者 Git SHA，而是只包含真正影响 Index 内容的事实，比如 Corpus Digest、Chunk Manifest Digest、Embedding Model、Dimension、Embedding Prompt、Splitter、Chunk Size 和 Overlap。像 Candidate Limit、Minimum Score、Rerank Top-K 这种 Query-time Config 不进入 Cache Key，否则改一个检索参数也会导致整个 Dense Index 重建。
>
> 同时 Cache 不是目录存在就复用，而是需要校验 Metadata、Collection 和 READY Completion Marker。如果构建中途中断或者配置不一致，会 fail closed。
>
> 最后我实际完成了一次 Cold Build，再进行 Warm Reuse，验证 Cache Hit 后没有实例化新的 Embedding Ingest 路径，准备时间从约 90 分钟下降到约 22 秒。之后重新跑完整 300 条 SciFact Query，Recall`@1/3/5`、MRR、NDCG`@3/5` 与原冻结 Baseline 完全一致，证明优化只改变 Evaluation 执行成本，没有改变 Retrieval Semantics。

------

# 十六、高频追问 + 可直接面试参考回答

### Q1：为什么不直接 pickle Embedding 向量？

因为我们的执行目标不是单纯得到 embedding array，而是运行真实 LocalAgent Retrieval Pipeline，实际检索资产是 Chroma Index。缓存 Chroma 可以继续复用现有查询路径，同时保留 Collection Metadata 和 Index 行为，避免再维护第二种只服务 Evaluation 的向量加载路径。

### Q2：为什么不用 Redis？

这个 Cache 是约 162MB 级的持久化向量索引制品，构建成本约 90 分钟，生命周期与 Dataset/Embedding Config 绑定，而不是请求级短期 Cache。使用文件系统 + Chroma Persistence 更符合资产形态，Redis 反而增加依赖和生命周期复杂度。

### Q3：为什么 `candidate_limit` 不进入 Cache Key？

因为它只决定 Query 时从 Index 取多少候选，不改变 Index 中保存的 Chunk 和 Vector。因此修改它只应该重新执行 Evaluation，不应该重新 Embedding 9548 个 Chunk。

### Q4：模型维度相同为什么还不能复用？

因为 Embedding Dimension 只能说明向量结构兼容，不能证明向量空间语义兼容。两个不同模型都可以输出 1024 维，但相同语义在两个空间里的坐标系统完全不同，因此 Embedding Model Identity 必须进入 Cache Identity。

### Q5：Cache 构建到一半进程挂了怎么办？

这种目录不能被当作正常 Cache。我们的设计要求只有完整构建、Metadata 校验完成并写入 READY 状态以后才允许复用；否则识别成 `CACHE_INCOMPLETE`，fail closed。

### Q6：怎么证明缓存优化没有影响结果？

我们使用相同 SciFact Asset、Manifest、Embedding、Chunking、Retrieval Config 和 Document Projection 重跑完整 300 Query，Recall`@1/3/5`、MRR、NDCG`@3/5` 六项指标与冻结 Baseline exact equal。因此这里验证的不只是测试通过，而是行为级 Baseline Reproduction。30_beir_scifact_dense_index_cache_closeout.mdMD

### Q7：90 分钟优化到 22 秒，是不是 240 倍性能提升？

面试里不要这样描述。

这不是：

```
Embedding Algorithm Latency Optimization
```

而是：

```
避免重复计算
```

应该说：

> 对已构建且 Cache Identity 相同的 Benchmark，后续准备阶段从需要重新构建约 90 分钟，变为约 22 秒的 Cache Validation + Reuse。

不要把它包装成 Qwen Embedding 本身快了几百倍。

### Q8：为什么不用 TTL 做失效？

因为这种 Index 的有效性由 Corpus、Chunking 和 Embedding Identity 决定，而不是年龄。即使 Cache 一个月前生成，只要输入和配置没变仍然有效；反之模型刚换一分钟，旧 Cache 就已经不能使用。

### Q9：未来 BM25 能共用这个 Cache 吗？

BM25 不应该共用 Dense Vector Index 本身，但可以使用相同 Corpus/Chunk Identity。未来应形成：

```
Dense Index Cache
+
BM25 Sparse Index
```

两个独立的 Retrieval Channel 资产，再由后续 RRF 做融合。当前这个 WP 没有提前建设完整 Multi-index Registry，避免过度设计。

### Q10：这个优化对生产 RAG 有什么借鉴意义？

核心不是这个 SciFact Cache 本身，而是相同原则可以用于生产 RAG 的 Index Build Pipeline：

```
Source Version
→ Chunk Version
→ Embedding Version
→ Index Version
```

只有真正影响 Index Semantic 的因素变化时才 rebuild，并且必须保留 provenance、validation 和 atomic publication。

------

# 十七、本 WP 最值得记住的面试知识点

这个案例最有价值的不是：

```
“我做了一个缓存。”
```

而是你可以完整解释：

```
发现昂贵重复计算
        ↓
定位资产生命周期问题
        ↓
区分 Index-time / Query-time Config
        ↓
设计 Semantic Cache Identity
        ↓
Fail-closed Validation
        ↓
Partial Build Protection
        ↓
Persistent Artifact Lifecycle
        ↓
Warm Reuse
        ↓
No-Reembedding Proof
        ↓
300-query Baseline Reproduction
```

这已经比较接近一个完整的 **Evaluation Infrastructure Engineering（评估基础设施工程）** 案例，而不是简单的 Python 性能小优化。

------

# 十八、推荐面试材料文件名

```
docs/interview_materials/
stage5_phase3_wp0b_beir_dense_index_cache_and_baseline_reproducibility.md
```

本 WP 的学习/面试总结到这里完成。

下一步按照当前路线就是：

```
Stage5-Phase3-WP1
BM25 Sparse Retrieval Foundation
```

但按照约定，本次学习结束后先停在这里，不自动开始 WP1。