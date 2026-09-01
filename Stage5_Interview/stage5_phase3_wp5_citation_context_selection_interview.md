好，我们正式做 **Stage5-Phase3-WP5：Citation Context Selection** 的学习 / 面试总结。

这一 WP 的价值非常高，因为它把一个很容易被“经验拍脑袋”的问题，变成了一个可审计、可复现、可解释的离线实验：

> **Retriever 已经给出 ranked candidates 后，到底应该放多少上下文给模型？**

最终不是凭感觉说“Top-3 差不多”，而是在 frozen retrieval、frozen corpus、frozen serializer、真实 pinned tokenizer 下，对 `K=1,2,3,4` 做 deterministic ablation。Codex 最终独立确认全部 Gate PASS，`WP5_STATUS = COMPLETE`。70_codex_real_comparison_review.mdMD

------

# 一、先记住最终结果

正式 benchmark：

| K    | Support Coverage | Chunk Noise | Token Noise | Total Tokens | Avg Tokens |
| ---- | ---------------- | ----------- | ----------- | ------------ | ---------- |
| 1    | 1.0              | 0.0         | 0.0         | 385          | 48.125     |
| 2    | 1.0              | 0.5         | 0.4914      | 757          | 94.625     |
| 3    | 1.0              | 0.6667      | 0.6605      | 1134         | 141.75     |
| 4    | 1.0              | 0.75        | 0.7421      | 1493         | 186.625    |

最关键的结构性事实：

```
8 / 8 eligible cases：
Top-1 candidate 都是 expected support
```

因此：

```
K=1:
Coverage = 1.0
Noise = 0
Tokens = 最低
```

而从 K=2 开始，新增 context 没增加 support coverage，只增加了当前 GroundTruth 定义下的 conservative noise 和 token cost。Codex 独立重算确认 `K1/K2/K3` 都 Pareto dominate `K4`。70_codex_real_comparison_review.mdMD

但注意：

```
BEST_K = NOT_SELECTED
```

这是 WP5 最重要的实验纪律之一。

------

# 二、这个 WP 到底解决了什么问题

最简单的理解：

WP2/WP3 主要研究：

```
怎么把正确 chunk 排得更靠前？
```

WP5 研究：

```
排好以后，究竟给模型多少 chunk？
```

这是两个完全不同的问题。

完整链路：

```
Query
 ↓
Dense + BM25
 ↓
RRF ranked candidates
 ↓
[WP5 从这里开始]
Context Selection
 ↓
Serialized RAG Context
 ↓
Generation
```

WP5 v1 没碰 Generation。

它只回答：

> 在 frozen ranked evidence 已经确定时，不同 Top-K 会如何影响 support preservation、context noise 和 token usage？

------

# 三、为什么 Context Selection 是独立问题

很多初学者会觉得：

> Retriever 都已经 Top-K 了，不就是直接把 Top-K 扔给 LLM 吗？

实际上不一样。

Retrieval 的目标通常是：

> 尽量把 relevant evidence 找回来。

Context Selection 的目标是：

> 在已经找到的 evidence 中，选择最值得占用 prompt budget 的部分。

比如：

```
Rank 1 = 真正 support
Rank 2 = 相关但不是需要的 support
Rank 3 = 旁支信息
Rank 4 = 同主题噪声
```

Retriever 排名不一定“错”。

但如果把 1～4 全放进去：

- retrieval recall 没问题；
- context support coverage 也没问题；
- 但 noise 上升；
- token cost 上升；
- 后续 generation 可能受到额外干扰。

所以：

> **Retrieval Quality ≠ Context Quality。**

这是 WP5 第一条要刻进脑子的结论。

------

# 四、四层事实一定要分开

这是 WP5 最重要的面试知识点之一。

```
Retrieved
Selected
Actually in Context
Actually Cited
```

它们不是一回事。

### 1. Retrieved

Retriever 返回了哪些 chunks。

### 2. Selected

Context selection policy 选择了哪些 chunks。

### 3. Actually in Context

经过 serialization / budget / truncation 后，真正进入模型 prompt 的是什么。

### 4. Actually Cited

模型最终答案真的引用了哪些证据。

在当前 WP5 v1 中，我们可靠评估到了：

```
Retrieved
Selected
Serialized Context
```

但没有进入：

```
Actual answer citation usage
```

所以才必须诚实写：

```
CITATION_CORRECTNESS =
NOT_EVALUATED_IN_WP5_V1

CITATION_COMPLETENESS =
NOT_EVALUATED_IN_WP5_V1
```

Codex 最终也再次确认了这个边界。70_codex_real_comparison_review.mdMD

------

# 五、为什么不能把 Support Coverage 叫 Citation Completeness

假设 Ground Truth 要求：

```
support chunk A
```

而 K=1 选中了 A。

这只能证明：

> 需要的 support 已经进入 context。

不能证明：

> 模型最终引用了 A。

模型可能：

- 完全没引用；
- 引用了错误 chunk；
- 生成 claim 但没有 citation；
- citation ID 和 claim 没绑定。

因此：

```
Context Support Coverage
≠ Citation Completeness
```

Citation Completeness 至少需要：

```
required claim
→ required support
→ generated claim
→ actual citation
```

当前项目还没有完整 claim-level authority，所以 WP5 v1 不冒充 citation evaluation。

这是非常成熟的 evaluation boundary。

------

# 六、WP5 的几个核心术语

### Fixed Top-K

固定选 frozen ranking 中前 K 个有效 candidates。

本 WP：

```
K ∈ {1,2,3,4}
```

唯一实验变量就是 K。

------

### Context Support Coverage

选中的 context 覆盖了多少 GroundTruth required support。

定义：

```
|selected support ∩ expected support|
-------------------------------------
       |expected support|
```

本 WP aggregate：

```
MACRO
```

即每 case coverage 先算，再平均。

------

### Context Noise

被选择进 context、但不属于 GroundTruth expected support 的内容。

这里必须说：

> **conservative noise**

因为“不在 expected_support_fact_ids”并不等于“客观无用”。

只是：

> Dataset 没把它标成 required support。

Codex 也专门强调不能把这些 chunks 说成 objectively irrelevant。70_codex_real_comparison_review.mdMD

------

### Noise by Chunk

```
Σ non-support selected chunks
-----------------------------
Σ selected chunks
```

本 WP：

```
MICRO aggregate
```

------

### Noise by Token

```
Σ non-support block token count
--------------------------------
Σ full serialized context tokens
```

这里一个很细但很专业的设计：

```
separator token
→ 进入 denominator
→ 不进入某个 non-support block numerator
```

也就是说 numerator 与 denominator 并不是简单 partition。

------

### Serialized RAG Context Token Count

用真实 frozen generation-model tokenizer，对 WP5 serializer 生成的 RAG context 文本计 token。

不是：

```
字符数
chunk 数
估算 token
完整 production prompt token
```

------

### Pareto Dominance

如果一个方案：

- coverage 不下降；
- noise 至少一项下降；
- token usage 下降；

那它 Pareto dominate baseline。

本 WP baseline：

```
fixed-top-k.v1 / K=4
```

------

# 七、为什么 K=4 不是 Production Baseline

这个地方很容易面试说错。

WP5 的：

```
K=4
```

只是：

> evaluation comparison baseline。

而生产 LocalAgent 真正的 context path 还有：

```
max_context_chunks = 4
max_context_chars = 2400
max_single_chunk_chars = 1000
production dedup
ContextBuilder global budget
mandatory/preserve-content
rendering
```

所以必须说：

```
K4_IS_PRODUCTION_CONTEXT_EXACT = false
```

不是：

> “我们 production 原来用 Top4，然后实验发现 Top1 更好。”

这句话目前不真实。

正确说法：

> 我们用 K=4 作为 evaluation-side comparison baseline，因为它对应当前 production-ish chunk-count ceiling，但并不等价于完整 production ContextBuilder 行为。

这句话面试里很稳。

------

# 八、为什么 Dedup 也要冻结

一开始实现里说：

> mirrors production dedup

后来 Codex 发现其实不完全一样。

Production 是：

```
" ".join(content.split())
→ normalized content hash
```

WP5 是：

```
SHA256(raw snippet)
```

最后没有为了“看起来 production exact”强行改算法，而是诚实冻结为：

```
WP5_DEDUP_REF =
evaluation-raw-snippet-sha256-dedup.v1

WP5_DEDUP_IS_PRODUCTION_EXACT =
false
```

这件事特别值得面试讲。

因为它体现：

> **实验系统最重要的不是假装和 production 一样，而是准确描述自己和 production 哪里一样、哪里不一样。**

------

# 九、Tokenizer Authority 为什么折腾这么久

这是 WP5 第二个大重点。

Token Usage 如果想成为严肃指标，measurement instrument 也必须冻结。

最开始几个风险：

```
任意 GGUF 都能传进来
tokenizer identity 可以 caller 自报
add_bos / special 依赖 library default
AgentEvalOps env 又没有 llama_cpp
```

这些都会让一个看起来非常精确的：

```
1493 tokens
```

变得没有真正 Authority。

最终冻结：

```
MODEL =
qwen2.5-7b-instruct-q4_k_m.gguf

GGUF SHA256 =
f9988096...

llama_cpp =
0.2.90

TOKENIZATION_MODE =
add_bos=false
special=false
```

而且真实 benchmark 用的是：

```
PINNED_GENERATION_MODEL
```

不是 fixture tokenizer。70_codex_real_comparison_review.mdMD

------

# 十、为什么 add_bos=false

这是一个很适合被面试官追问的细节。

WP5 统计的是：

> serialized RAG context segment 本身的 token cost。

不是完整 prompt sequence。

BOS 是整个 sequence 的 beginning token。

如果每个 RAG context 片段独立 tokenization 时都 `add_bos=true`：

就会人为多算一个序列起始 token。

所以冻结：

```
add_bos=false
special=false
```

而且最重要的不是某个参数“理论上绝对正确”，而是：

> **实验前明确冻结，所有 K 使用完全相同 measurement semantics。**

------

# 十一、为什么不用 DeterministicTokenEstimator

因为 estimator 只能做 proxy。

如果我们声称：

> K1 比 K4 减少了多少 token cost

那么最好使用实际 generation model 对应 tokenizer。

所以：

```
DeterministicTokenEstimator
→ debug / proxy

Pinned GGUF tokenizer
→ formal metric Authority
```

这体现的是：

> **Metric precision 必须匹配你的 claim strength。**

如果只是说“context 大概变短”，估算器够了。

如果要说：

```
385 vs 1493 tokens
```

那最好冻结真实 tokenizer。

------

# 十二、为什么要先做 Single Execution Environment

另一个非常工程化的点。

最开始：

```
AgentEvalOps venv
→ 有 backend deps
→ 没 llama_cpp

LocalAgent venv
→ 有 llama_cpp
→ 缺 AgentEvalOps deps
```

如果我们分别在两个环境测一半，然后说：

> real benchmark path 已经跑通

这是不严谨的。

所以最后专门 provision：

```
一个 single environment
```

同时具备：

```
AgentEvalOps dependencies
+
llama_cpp 0.2.90
+
frozen GGUF
```

然后先跑：

```
1 case × K1
```

execution smoke。

等 smoke Gate PASS 后，才正式跑 K1..4。

这就是：

> **Capability proof before benchmark execution。**

------

# 十三、为什么 benchmark 前花这么多时间 Gate

如果面试官问：

> 这么一个 Top-K 实验，为什么搞这么复杂？

可以这样回答：

> Top-K selector 本身很简单，真正困难的是让最终结果可相信。我需要确保四个 K 使用同一 retrieval population、同一 corpus、同一 serializer、同一 tokenizer、同一 GroundTruth、同一 metric definition，而且 tokenizer 不是 fixture、artifact 没有 plaintext 泄露、比较过程中没有隐式调参。否则“Top1 比 Top4 好”很可能只是实验条件漂移。

这是这个 WP 最核心的工程含金量。

------

# 十四、最终结果为什么这么“整齐”

最终：

```
K1 Coverage = 1
K2 Coverage = 1
K3 Coverage = 1
K4 Coverage = 1
```

而：

```
Noise ↑
Tokens ↑
```

为什么？

Codex mechanical verification 给了非常强的结构事实：

```
8 / 8 eligible cases
Top1 都已经是 expected support
```

所以 K=1 已经覆盖全部 required support。

新增 rank2/rank3/rank4：

并没有增加 required support coverage。

于是：

```
K↑
Coverage 不变
Noise ↑
Token ↑
```

这不是理论规律。

是：

> 当前 frozen Dataset + frozen retrieval evidence 下的 empirical finding。

千万不要泛化为：

> RAG 永远 Top1 最好。

------

# 十五、为什么不能直接选 K=1

这个问题面试官几乎一定会问。

因为当前 WP5 v1 是：

```
deterministic comparison experiment
```

不是：

```
policy selection experiment
```

我们已经看过全部 cases 的结果。

如果现在说：

> 那就选 K1 上线。

那其实就是拿同一个 dataset：

```
看结果
→ 选参数
```

然后没有 untouched evaluation。

这会引入 selection bias。

所以：

> 如果未来真的要把 K 当 production policy 参数选择，应该重新定义实验，用 CAL split 选 K，再用 untouched EVAL split 验证。

因此：

```
K1 Pareto dominates K4
```

不等于：

```
K1 = BEST_K
```

这是一个非常高级的实验意识。

------

# 十六、面试高频题：为什么不能现在选 Winner？

推荐回答：

> 因为 WP5 v1 是 ablation，不是 policy tuning。我们同时观察了 K=1..4 在整个 frozen eligible population 上的表现，因此这些结果只能用于比较。如果现在根据这些结果选 K，就相当于用 evaluation set 做 model selection。真正上线选择应该新建 CAL→lock→untouched EVAL 实验。

这基本是满分回答。

------

# 十七、面试题：为什么 Coverage 用 Macro，而 Noise 用 Micro

### Coverage 用 Macro

希望每个 query/case 权重相同。

```
case1 coverage 1.0
case2 coverage 0.5
```

先 per-case 算，再平均。

避免 support facts 多的 case 权重过大。

------

### Noise 用 Micro

Noise 更像整体 context pollution ratio。

所以：

```
所有 non-support chunks
/
所有 selected chunks
```

或者：

```
所有 non-support tokens
/
所有 context tokens
```

从整体系统成本看更直观。

重点不在“macro 一定优于 micro”，而在：

> **口径 benchmark 前冻结。**

Codex 甚至专门在 implementation Gate 阶段就把 aggregation semantics 锁住，就是为了防止看完真实结果后改统计方式。

------

# 十八、面试题：为什么要同时有 Chunk Noise 和 Token Noise

因为：

```
1 个 chunk
```

不等于：

```
同样的 token cost
```

比如：

```
Chunk A = 50 tokens
Chunk B = 500 tokens
```

按 chunk：

```
都是 1
```

按 token：

差 10 倍。

因此：

### Noise by Chunk

看 selection 数量结构。

### Noise by Token

看真正的 context budget 消耗。

两者一起比只报“平均 chunk 数”更真实。

------

# 十九、面试题：为什么 serializer 也必须冻结

因为 tokenizer 是对：

```
serialized string
```

计数。

例如：

```
[来源: ...]
正文
[引用: C1]
```

和：

```
正文
```

token 数不一样。

所以 Token Usage 不是：

```
chunk plaintext token count
```

而是：

```
serialized RAG block token count
```

因此 serializer 也是 measurement pipeline 的一部分。

只冻结 tokenizer，不冻结 serializer，同样不够。

------

# 二十、WP5 的 Authority Chain

这个最好能脱口而出：

```
WP4 Frozen Retrieval Evidence
       ↓
candidate identity / rank Authority
       ↓
Frozen Controlled Corpus
       ↓
content materialization Authority
       ↓
FixedTopKSelector
       ↓
DERIVED_CONTEXT_SELECTION
       ↓
citation-context-selection.v1
       ↓
Metric evaluator
       ↓
comparison report
```

Tokenizer 旁路：

```
Frozen GGUF bytes
       ↓
SHA256 identity
       ↓
llama_cpp 0.2.90
       ↓
explicit tokenization mode
       ↓
serialized RAG context token count
```

每个事实都有 Owner。

------

# 二十一、这次几个非常好的 Bad Cases

建议以后面试拿来讲。

### 1. Materialized asset 自证

错误模式：

```
artifact:
正文 = X
digest = hash(X)

validator：
digest == hash(X)
PASS
```

问题：

artifact 可以同时伪造正文和 digest。

修复：

```
independent frozen source manifest
```

外部 Authority。

------

### 2. Caller 自定义 tokenizer

错误模式：

```
--tokenizer-path random.gguf
→ hash一下
→ 当作合法identity
```

修复：

```
actual bytes SHA256
==
frozen expected SHA256
```

------

### 3. Library default 参与实验

错误模式：

```
tokenize(text)
```

未来库默认值一变：

benchmark 数字漂。

修复：

```
add_bos=false
special=false
```

explicit contract。

------

### 4. Fixture 测试通过冒充 real benchmark

Fixture tokenizer 很适合 deterministic tests。

但不能证明：

```
真实 GGUF tokenizer
```

能在 AgentEvalOps execution path 中运行。

所以专门做了：

```
real tokenizer smoke
→ single environment smoke
→ real comparison
```

------

# 二十二、Truthful Implementation Boundary

## 你可以说

> 我实现了一套 evaluation-only RAG context-selection benchmark，在冻结 Dense+BM25+RRF retrieval evidence 后，对 fixed Top-K context policies 做 deterministic ablation，并使用真实 pinned generation-model tokenizer评估 support coverage、context noise 和 serialized context token cost。

也可以说：

> 在 8 个具有可信 support GroundTruth 的 eligible cases 上，Top-1 已覆盖全部 expected support；K=2~4 未增加 support coverage，却增加 conservative context noise 和 token cost，因此 K1/K2/K3 在冻结指标下均 Pareto dominate K4。

------

## 不能说

### 不能说：

> Top1 是最佳生产策略。

没有 policy selection。

------

### 不能说：

> Top1 提高 Citation Correctness。

没评。

------

### 不能说：

> Top1 提高 Citation Completeness。

没评。

------

### 不能说：

> Top1 提高生成答案质量。

没有 generation。

------

### 不能说：

> K=4 是 production baseline。

只是 evaluation comparison baseline。

------

# 二十三、简历怎么写

推荐英文版：

> **Built an evaluation-only RAG context-selection benchmark with frozen retrieval evidence, strict provenance, real generation-model tokenizer accounting, and deterministic Top-K ablations. On the validated support-labeled subset, Top-1 preserved 100% support coverage while reducing conservative context noise and serialized context tokens versus larger K settings.**

中文：

> 搭建 RAG 上下文选择离线评估链路，冻结 retrieval evidence、corpus provenance、serializer 与真实 generation-model tokenizer，对 Top-K 策略进行 deterministic ablation；在可信 support 标注样本上，Top-1 保持 100% support coverage，同时显著降低 context noise 和 token cost。

注意最后不要补：

> 因此上线 Top1。

------

# 二十四、如果面试官追问：“那你下一步会做什么？”

可以回答两条路线。

### 路线 A：Production K selection

如果目标是决定真正上线 K：

```
new Dataset split
→ CAL choose K
→ lock
→ untouched EVAL
→ release gate
```

不能直接用现在结果选。

------

### 路线 B：真正 Citation Evaluation

如果目标是 Citation Correctness / Completeness：

必须先建立：

```
claim-level GroundTruth
actual generated citation IDs
claim → citation mapping
citation → chunk support mapping
```

然后才有资格评：

```
Citation Correctness
Citation Completeness
```

必要时才讨论 LLM Judge。

------

# 二十五、你现在应该掌握的 8 句话

建议背下来。

1. **Retrieval quality 和 context quality 是两个不同问题。**
2. **Retrieved、selected、in-context、actually cited 必须分层建模。**
3. **Support coverage 不能冒充 citation completeness。**
4. **Token metric 的 tokenizer、serializer、mode 都属于实验 Authority。**
5. **Artifact 不能自己证明自己的来源。**
6. **Fixture 能证明结构，不能证明真实执行能力。**
7. **Pareto dominance 是比较事实，不等于 policy selection。**
8. **如果要根据 benchmark 结果选择 K，就需要新的 CAL→lock→untouched EVAL 实验。**

------

# 二十六、一个很适合面试的完整回答

如果面试官问：

> “你做过 RAG context optimization 吗？”

你可以这样回答：

> 做过。我的处理方式不是直接调 Top-K，而是先把 retrieval 和 context selection 解耦。我们冻结 Dense+BM25+RRF 的 ranked evidence，然后实现 evaluation-side fixed Top-K selector，只改变 K=1~4。Context support coverage 用人工 support fact authority 机械计算，noise 分 chunk 和 token 两个维度，token cost 使用 pinned generation-model GGUF tokenizer，并冻结 serializer 和 BOS/special-token mode。最终在 8 个可信 eligible cases 上，Top1 已经 100% 覆盖 expected support，而 K 增大只增加 conservative noise 和 serialized token cost。我们只把这个结论记录为 Pareto comparison，没有直接选择生产 K，因为该实验本身不是 policy-selection experiment。

这段已经非常接近大厂 Agent / RAG 工程面试的水平。

------

# 二十七、推荐学习文档文件名

```
stage5_phase3_wp5_citation_context_selection_interview.md
```

最后，把 WP5 浓缩成一句话：

> **WP5 不是证明“Top1 最好”，而是证明在冻结的这组 retrieval evidence 上，增加 context 数量没有增加 required support，却确定性增加了噪声与 token 成本；而是否选择 Top1，是另一个必须重新设计的实验。**

