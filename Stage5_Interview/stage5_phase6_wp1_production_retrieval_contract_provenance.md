当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase6-WP1 学习 / 面试总结

## Production Retrieval Contract & Provenance

### 1. 本 WP 解决了什么问题

WP1 解决的并不是“如何实现 BM25”或者“如何写 RRF”，因为这两项能力在此前已经存在。

真正的问题是：

> **Dense 和 BM25 即使各自都能正常工作，生产系统凭什么证明它们来自同一份知识库、同一次切块、同一个版本，然后才允许 RRF 对它们进行融合？**

WP0 已经证明，当时的生产 RAG 还是：

```text
Dense Retrieval
+
Chroma keyword supplement
→ heuristic rerank
```

BM25、RRF、Cross-Encoder 虽然存在并有测试，但没有进入生产链路。

更关键的是，当时生产 Chroma marker 只能证明 embedding 配置、dimension 和 chunk schema 等有限信息，无法证明：

```text
corpus 是否相同
source files 是否相同
splitter 是否相同
chunk_size / overlap 是否相同
Dense / BM25 是否来自同一批 chunks
```

因此，如果直接把现有 BM25 接入生产，有可能出现：

```text
Dense Index = Corpus A / Chunk Policy v1
BM25 Index  = Corpus A / Chunk Policy v2

两个索引都各自合法
        ↓
RRF 仍然进行融合
        ↓
融合结果在语义上已经不可信
```

WP1 最终建立了完整的生产级 provenance foundation，使系统在 WP2 进行 Hybrid Retrieval 前，可以先证明 Dense 和 BM25 **确实属于同一个 generation**。Final Gate 最终为 `PASS_WITH_ACCEPTED_LIMITATIONS`，P0/P1/P2 均归零。

------

# 2. 真实架构与数据流

WP1 最重要的架构演进可以理解为：

```text
Knowledge Source Files
        ↓
Canonical Source Enumeration
        ↓
source_manifest_sha256
        ↓
Canonical Chunk Policy
        ↓
split once
        ↓
One Prepared Chunk Set
        │
        ├──────────────┐
        ↓              ↓
Dense Generation    BM25 Artifact
Chroma              BM25 JSON
        │              │
        └──────┬───────┘
               ↓
     RetrievalIndexProvenance
               ↓
 Exact Provenance Validation
               ↓
           active.json
               ↓
        Atomic Publication
               ↓
     Production Startup Validation
```

这里真正的核心不是索引，而是中间的：

```text
RetrievalIndexProvenance
```

它把两个原本可以独立变化的检索索引绑定成一个统一的生产 generation。

最终生产兼容证明的核心是：

```text
source_manifest_sha256
+
chunk_policy_sha256
+
chunk_manifest_sha256
+
generation_id
```

只有全部精确一致，Dense/BM25 才被认为属于同一套可融合数据。

------

## 2.1 Corpus Identity

这里没有把：

```text
目录路径
collection name
文件名
ingest_batch_id
```

直接当成 corpus identity。

因为这些信息只能证明“叫什么”或者“放在哪”，不能证明文件内容相同。

最终采用：

```text
source_manifest_sha256
```

其思想是对：

```text
relative source path
+
source content SHA-256
```

进行 canonical ordering 后统一计算 digest。

因此：

```text
D:\A\kb
```

和：

```text
E:\B\kb
```

只要里面相对文件结构和内容完全一致，就可以得到相同的 corpus proof。

这体现的是：

> **Logical Identity 与 Physical Location 分离。**

------

## 2.2 Chunk Policy Identity

同一批文件并不意味着得到同一批 chunks。

例如：

```text
chunk_size = 1400
overlap = 180
```

和：

```text
chunk_size = 1000
overlap = 100
```

即使 corpus 完全一样，也已经是两个不同的 retrieval space。

所以 WP1 把以下字段统一纳入：

```text
chunk_schema_version
splitter_ref
chunk_size
chunk_overlap
chunk_content_format_ref
```

并计算：

```text
chunk_policy_sha256
```

其中非常值得面试讲的是：

```text
chunk_content_format_ref
```

因为 Dense embedding 的实际文本可能不是单纯正文，而类似：

```text
文档：
章节：
页码：
正文……
```

如果这个 text projection 发生变化，即使 chunk 的起止位置完全不变，Embedding 输入语义也发生了变化。

因此：

> **Chunk identity 不仅由窗口边界决定，还由最终进入 Embedding 的文本表示决定。**

------

## 2.3 Chunk Manifest

生产 build 只允许：

```text
load once
→ split once
```

然后产生统一 prepared chunks。

再从同一个列表同时生成：

```text
Dense
BM25
```

每个 chunk 的 manifest 包含：

```text
ordinal
document_id
chunk_id
source
section_path
content_hash
```

最终得到：

```text
chunk_manifest_sha256
```

这个设计解决的本质问题是：

> 不允许 Dense 和 BM25 分别执行一次 splitter，然后再“希望它们刚好一致”。

------

# 3. Generation 机制

这是 WP1 非常有系统设计价值的一部分。

以前可以理解为只有：

```text
huawei_wiki_collection
```

现在 Hybrid production foundation 引入：

```text
Generation N
```

每一个 generation 都拥有自己的 Dense physical collection，例如：

```text
la_<collection_key>_g_<generation_uuid>
```

而：

```text
LOCAL_AGENT_KB_COLLECTION
```

仍然只是 logical collection name。

也就是说：

```text
Logical Collection
        ↓
Generation 1
Generation 2
Generation 3
```

物理 artifact 与逻辑知识库名称正式解耦。

这让系统可以做到：

```text
Generation A   ACTIVE
        ↓
后台构建 Generation B

B 构建失败
→ A 完全不受影响

B 构建成功
→ validate
→ publication
→ B ACTIVE
```

Final Gate 也特别验证了 staging generation 不会覆盖当前 active Dense collection。

------

# 4. active.json 为什么重要

WP1 使用一个非常简单但有效的：

```text
Publish Pointer
```

也就是：

```text
active.json
```

它不负责证明 artifact 内容正确，只负责回答：

> **当前 production 应该使用哪个 generation？**

因此 Authority 被分开：

```text
active.json
→ location authority

Chroma marker
→ Dense provenance authority

BM25 metadata
→ BM25 provenance authority

retrieval_index_manifest.json
→ shared provenance authority
```

这是一个非常值得面试讲的设计：

> 一个文件不要同时承担 Location、Integrity、Provenance、Lifecycle 等所有职责。

------

## Atomic Publication

发布 active generation 使用：

```text
write temp file
↓
flush
↓
fsync(file)
↓
close
↓
os.replace(temp, active.json)
```

这样避免：

```text
active.json
```

被写到一半时进程崩溃，导致下一次 startup 读取半截 JSON。

没有实现 directory fsync，这是 Final Gate 正式接受的 limitation。

------

# 5. Embedding Model Identity

WP0 曾发现一个真实风险：

```text
model path 相同
dimension 相同
但目录里的模型文件被替换
```

旧 marker 仍可能认为模型兼容。

WP1 最终没有接受这个限制，而是引入：

```text
embedding_asset_tree_sha256
```

规则非常严格：

```text
Embedding Model Root
        ↓
recursive traversal
        ↓
every regular file
        ↓
relative POSIX path
+
content_sha256
        ↓
canonical ordering
        ↓
asset-tree SHA-256
```

不参与 identity 的包括：

```text
mtime
ctime
absolute path
permission
```

也不允许：

```text
symlink
special filesystem node
```

悄悄跳过。

这里可以抽象成一个通用工程原则：

> **配置身份不等于资产身份。**

例如：

```text
model_name = Qwen3-Embedding-0.6B
```

只是配置。

真正强一致的 artifact identity 应尽可能来自：

```text
actual model content
```

------

# 6. Retrieval Strategy Contract

WP1 新增了明确的 strategy：

```text
BASELINE
HYBRID_RRF
```

默认仍然：

```text
BASELINE
```

这也是非常重要的工程设计。

没有因为：

```text
BM25 artifact 存在
```

就自动启用 Hybrid。

也没有：

```text
Hybrid 失败
→ 自动切回 Baseline
```

而是明确：

```text
Strategy 是 Operator Decision
而不是 Failure Side Effect
```

为什么？

如果配置明明写的是：

```text
HYBRID_RRF
```

请求出错后系统偷偷变成：

```text
BASELINE
```

那么：

- 日志 attribution 会失真；
- Evaluation 会失真；
- 故障无法复现；
- 线上真正跑的策略和配置不一致。

因此 WP1 冻结：

> **禁止 silent strategy fallback。**

------

# 7. WP1 为什么没有直接把 Hybrid 接上去

这是一个很好的系统设计拆分问题。

WP1 完成后：

```text
HYBRID_PRODUCTION_PRECONDITIONS_READY = YES

HYBRID_PRODUCTION_REACHABLE = NO
```

这不是“功能只做了一半”。

而是主动把两个不同风险维度拆开：

```text
WP1
Artifact correctness
Provenance
Generation
Persistence
Compatibility

WP2
Runtime query execution
BM25 Search
Candidate Mapping
RRF Fusion
Context Integration
```

如果同时做：

```text
artifact lifecycle
+
runtime fusion
```

那么一旦 Evaluation 出问题，很难判断到底是：

```text
索引版本不一致
```

还是：

```text
RRF / runtime wiring 错误
```

这种拆分的价值叫：

**Failure Domain Isolation（故障域隔离）**。

------

# 8. 真实性与完成边界

### 已真实实现

WP1 已实现：

```text
RetrievalIndexProvenance
source manifest
chunk-policy identity
ordered chunk manifest
generation identity
generation-specific Chroma collection
active.json
atomic publication
embedding asset-tree digest
Chroma marker v2
production BM25 artifact
production chunk Settings
retrieval strategy Settings
startup provenance validation
evaluation artifact v2
AgentEvalOps v1/v2 compatibility
```

Final Gate 对这些 Contract 均给出了 PASS。

### 已真实测试

Focused regression：

```text
LocalAgent
304 passed
1 skipped
12 deselected

AgentEvalOps
192 passed
```

并且进行了 compileall 和 `git diff --check`。

### 尚未实现

当前仍然没有：

```text
Production BM25 Query Execution
Production RRF Fusion
Hybrid Runtime Adapter
Hybrid Context Selection
```

因此：

```text
HYBRID_PRODUCTION_REACHABLE = NO
```

### Accepted Limitations

当前正式接受：

- active descriptor publication 不做 directory fsync；
- build 失败可能留下不可达 orphan Chroma collection；
- orphan generation 手动清理；
- startup 需要完整扫描 embedding model tree；
- Cross-Encoder 不在 WP1/WP2 production scope；
- 部分全仓历史失败仍然存在，但已经证明与 WP1 无关。

------

# 9. Real Bad Case

WP1 有几个非常适合面试讲的真实问题。

## Real Bad Case 1：Production marker 无法证明 Dense/BM25 同源

**来源：源码审计发现。**

触发条件：

```text
Dense 已构建
BM25 独立构建
```

但两者没有共同：

```text
corpus proof
chunk policy proof
generation proof
```

风险：

RRF 可能融合两个不同 chunk space。

根因：

Production provenance 只关注 Dense 自身 embedding compatibility，没有建立跨索引的 shared provenance。

修复：

```text
RetrievalIndexProvenance
+
source_manifest_sha256
+
chunk_policy_sha256
+
chunk_manifest_sha256
+
generation_id
```

知识点：

```text
Provenance
Artifact Compatibility
Generation Contract
Single Source of Truth
```

------

## Real Bad Case 2：Final Gate 发现 validator 打开了错误 Dense collection

这是本 WP 最值得讲的一个实现 Bug。

原问题：

```text
active.json
→ 指向 physical collection A

validator 使用的 manager
→ 可能打开 logical collection B
```

这样：

```text
descriptor 说检查 A
实际检查 B
```

可能破坏整个 generation invariant。

Final Gate 将它修复为：

```text
active descriptor
↓
physical collection locator
↓
open exact collection
↓
validate manager targets same locator
↓
provenance validation
```

Final Gate 将其定为 P1，并在冻结 Contract 内直接修复。

知识点：

```text
TOCTOU-like identity mismatch
Artifact Locator
Authority Boundary
Validation Target
Composition Root
```

------

## Real Bad Case 3：v1 兼容逻辑污染 v2 严格 Contract

AgentEvalOps 为了兼容历史 fixture，支持：

```text
VECTOR
KEYWORD
```

这种 shorthand。

最初 Stage 3 让 v2 也接受了它。

风险：

新 Contract 的 typed enum 被历史兼容逻辑放宽。

Final Gate 修复：

```text
Artifact v1
→ 接受 legacy shorthand

Artifact v2
→ 必须 strict enum
```

这体现了一个很重要的兼容原则：

> **Backward compatibility 应该被版本边界限制，而不是永久污染新协议。**

Final Gate 同样将其定为 P1，并直接修复后重新验证。

------

# 10. 名词 / 概念速览

| 关键词                 | 一句话理解                                                   |
| ---------------------- | ------------------------------------------------------------ |
| Provenance             | 描述一个 artifact 是由什么输入、配置和流程产生的来源证明。   |
| Artifact               | 构建过程产生并被运行时消费的持久化产物，例如 Dense index、BM25 index。 |
| Generation             | 一套彼此兼容的不可变检索 artifact 版本。                     |
| Corpus Identity        | 证明知识语料内容属于哪个版本的身份。                         |
| Source Manifest        | 对输入源文件集合及其内容进行规范化描述。                     |
| Chunk Manifest         | 描述某 generation 中全部 chunks 的有序清单。                 |
| Chunk Policy           | 决定如何把 source 变成 chunks 的参数与算法合同。             |
| Content Fingerprint    | 根据实际内容计算的稳定摘要，而不是靠路径或名称判断身份。     |
| Atomic Publication     | 避免消费者看到半完成状态的一次性发布方式。                   |
| Publish Pointer        | 指向当前 active generation 的小型可切换引用。                |
| Fail Closed            | 不能证明安全或兼容时直接拒绝继续执行。                       |
| Fail Open              | 校验失败仍允许继续，通常只适合非常有限的降级场景。           |
| Compatibility Contract | 判断两个组件或 artifact 能否安全共同工作的规则。             |
| Semantic Identity      | 从业务含义上判断对象是否相同，而不只比较临时 ID。            |
| Physical Locator       | artifact 实际存储的位置，不能替代其语义身份。                |
| RRF                    | 根据不同检索通道中的排名，而不是直接比较异构 raw score 完成融合。 |
| Artifact Attestation   | 对实际 artifact 内容建立更强的身份/完整性证明。              |
| Failure Domain         | 一个故障能够影响到的系统范围。                               |
| Composition Root       | 应用中负责构造和连接核心依赖的统一位置。                     |

------

# 11. 工程构建方法类问题

## Q1：为什么 BM25 和 Dense 不能各自建好索引后直接 RRF？

因为 RRF 默认有一个隐含前提：

> 两个 ranking 的 document/chunk identity 属于同一个语义空间。

如果两个索引来自不同版本 corpus 或不同 chunk policy：

```text
(document_id, chunk_id)
```

即使格式一样，也不一定代表同一个实体。

所以 Hybrid Retrieval 首先是一个：

```text
Data Compatibility Problem
```

其次才是 Ranking Problem。

------

## Q2：为什么不能直接用 collection name 当 corpus identity？

因为：

```text
collection_name = company_kb
```

只能证明名称没变。

里面文件完全可能已经变了。

更合理的是：

```text
relative source path
+
file content digest
```

生成 content-derived fingerprint。

------

## Q3：为什么 chunk_size/overlap 也要进入 provenance？

因为 Retrieval index 的最小检索单位就是 chunk。

改变：

```text
chunk_size
overlap
splitter
```

都会改变 chunk space。

即使 source files 完全没变，两个 index 也已经不再严格兼容。

------

## Q4：为什么一次 build 要 split once？

如果：

```text
Dense Builder
自己 split

BM25 Builder
再 split
```

即使两边使用相同配置，也存在未来 implementation drift 的风险。

更强的设计是：

```text
one prepared chunk set
```

作为 build 的事实源。

Dense 和 BM25 都只消费它。

这是一种：

```text
Single Source of Truth
```

设计。

------

## Q5：为什么不用数据库事务解决 generation 发布？

因为这里是：

```text
单机
本地文件
Chroma + JSON artifact
```

引入复杂 transaction coordinator 成本远高于收益。

使用：

```text
immutable generation
+
atomic publish pointer
```

已经能达到足够好的 crash safety。

这是典型的：

> 用最小机制满足真实一致性需求，而不是机械追求“分布式事务”。

------

## Q6：为什么 Hybrid 失败不自动降级成 Baseline？

因为这会破坏：

```text
Configuration Truth
Observability Truth
Evaluation Attribution
```

配置说：

```text
HYBRID_RRF
```

实际跑：

```text
BASELINE
```

是一种隐式行为漂移。

因此更合理的是：

```text
explicit strategy
+
explicit failure
+
explicit rollback
```

------

## Q7：为什么 v1 可以宽松兼容，v2 要严格？

因为兼容代码如果没有版本边界，会形成：

```text
Legacy behavior forever contaminates new contract
```

正确做法是：

```text
if schema == v1:
    compatibility behavior

if schema == v2:
    strict new contract
```

这叫：

**Version-scoped Compatibility（版本范围兼容）**。

------

# 12. 高频面试追问

## 追问 1：你这个 RAG 的 Hybrid Retrieval 是怎么做的？

现阶段最准确的回答不是直接说：

> 我们生产就是 Dense + BM25 + RRF。

而应该说：

> 我们此前已经实现并评估过 BM25 和 RRF，但生产链最开始还是 Dense + keyword supplement。为了生产化 Hybrid，我没有直接把 BM25 接到请求链路，而是先做了一层 Retrieval Provenance Contract，确保 Dense 和 BM25 必须来自同一 corpus、同一个 chunk policy、同一个 ordered chunk manifest 和 generation，随后才进入 Runtime Integration。

这会明显比只背：

```text
Dense + Sparse → RRF
```

更有工程含量。

------

## 追问 2：RRF 为什么适合 Dense + BM25？

因为 Dense similarity 与 BM25 raw score 的数值空间不同。

直接：

```text
dense_score * a + bm25_score * b
```

需要复杂 score normalization。

RRF 使用：

```text
rank
```

而不是原始 score，因此可以比较稳定地融合异构 retrieval channel。

关键词：

```text
Rank Fusion
Score Calibration
Heterogeneous Retrieval
```

------

## 追问 3：怎么保证两个 index 一致？

可以直接说四层：

```text
source_manifest_sha256
chunk_policy_sha256
chunk_manifest_sha256
generation_id
```

然后补一句：

> 其中 collection name 和路径都只是 locator，不作为 corpus proof。

------

## 追问 4：如何更新知识库而不破坏在线版本？

回答：

```text
immutable generation
→ staging build
→ validation
→ atomic active pointer swap
```

失败时旧 generation 不动。

------

## 追问 5：模型文件被原地替换怎么办？

WP1 使用：

```text
embedding_asset_tree_sha256
```

对模型目录所有 regular file 的相对路径和内容 digest 进行统一 fingerprint。

因此即使：

```text
path 不变
dimension 不变
```

模型资产变化仍然能被发现。

------

## 追问 6：为什么不自动 rebuild？

因为 server startup 应主要负责：

```text
validate
load
serve
```

如果自动：

```text
detect mismatch
→ rebuild
```

就会把 startup 与昂贵、可能失败的数据 mutation 耦合在一起。

所以这里选择：

```text
REBUILD_REQUIRED
```

由显式 build operation 完成。

------

# 13. 30 秒面试总结

> 在 Advanced RAG 生产化过程中，我发现 BM25 和 RRF 虽然已经实现和评估过，但不能直接接入生产，因为原有 Dense Chroma marker 无法证明 Dense 和 BM25 来自同一 corpus 和 chunk version。我先建立了 RetrievalIndexProvenance，通过 source manifest、chunk policy、ordered chunk manifest 和 generation ID 对两个索引进行强一致绑定，并采用 immutable generation 加 active.json 原子发布，保证新索引构建失败不会影响当前生产版本。同时加入 embedding asset tree digest，防止模型目录原地替换造成静默不兼容。WP1 最终完成了 Hybrid 的全部生产前置 Contract，但故意没有接查询链路，BM25/RRF Runtime Integration 留到下一 WP。

------

# 14. 2 分钟面试总结

> 我们之前已经在 Evaluation 阶段实现过 BM25、RRF 和 Cross-Encoder，但源码审计后发现生产链路实际上还是 Dense Retrieval 加 Chroma keyword supplement 和 heuristic rerank。所以 Advanced RAG 生产化的第一步不是直接把 BM25 接进 Runtime，而是解决两个索引之间的数据一致性问题。
>
> 原来的生产 Chroma marker 主要记录 embedding 配置、dimension 和 chunk schema，但是没有记录 corpus fingerprint、splitter、chunk size、overlap 或完整 chunk manifest。如果 Dense 和 BM25 分别基于不同版本的知识库或切块方式构建，两个索引各自都可能合法，但 RRF 融合结果实际上不可信。
>
> 所以我先建立了一套 RetrievalIndexProvenance。输入源文件通过相对路径和内容 SHA-256 形成 source manifest；chunk schema、splitter、size、overlap 以及最终 embedding text format 形成 chunk-policy digest；切块只执行一次，再形成 ordered chunk manifest。Dense 和 BM25 必须同时匹配 source manifest、chunk policy、chunk manifest 和 generation ID，才能被认为属于同一个 retrieval generation。
>
> 持久化上我没有做复杂事务，而是采用 immutable generation。每次 build 创建独立 Chroma collection 和 BM25 artifact，全部验证完成后通过 active.json 使用 temp file、fsync 和 os.replace 原子切换 active generation。失败 build 不会影响旧 generation。
>
> 同时我们发现 embedding model path 和 dimension 还不足以证明模型资产没变化，所以又增加了 embedding asset-tree SHA-256，对本地模型所有 regular files 建立内容 fingerprint。
>
> 在 Final Gate 里还发现过两个真实问题，一个是 validator 曾可能验证 logical collection 而不是 active descriptor 指定的 physical collection，另一个是为了兼容旧 artifact 放宽的 VECTOR/KEYWORD shorthand 意外影响了 v2 strict contract。这两个问题都在冻结架构范围内直接修复并回归。
>
> WP1 最终的状态是 Hybrid production prerequisites 已经完成，但 BM25 和 RRF 还没有进入请求链路。这样下一阶段只需要解决 Runtime Integration，不需要再同时处理 corpus、chunk 和 artifact lifecycle 问题。

------

# 15. 建议继续深入的关键词

这一个 WP 最值得单独学习的关键词是：

```text
Data Provenance
Content-addressable Identity
Immutable Generation
Atomic Publish
Artifact Manifest
Compatibility Contract
Schema Versioning
Fail-closed
Rollback Strategy
Composition Root
RRF
Index Lifecycle
Crash Consistency
TOCTOU
```

面试优先级最高的我建议是：

```text
Provenance
Immutable Generation
Atomic Publish
RRF
Schema Versioning
Fail-closed
Composition Root
```

------

# 16. 推荐学习文档名

按你现在的命名规则，本 WP 我最推荐：

```text
docs/interview/stage5_phase6_wp1_production_retrieval_contract_provenance.md
```

如果想进一步突出 Hybrid RAG，也可以叫：

```text
stage5_phase6_wp1_hybrid_retrieval_provenance_contract.md
```

但**首选第一种**，因为 WP1 真正完成的是 `Production Retrieval Contract + Provenance`，Hybrid Runtime 本身还没有进入 production，文件名不应该让人误以为 Hybrid 已经完成。

WP1 学习总结到这里正式结束。下一步是 **Stage5-Phase6-WP2 — Canonical Hybrid Retrieval Integration**。