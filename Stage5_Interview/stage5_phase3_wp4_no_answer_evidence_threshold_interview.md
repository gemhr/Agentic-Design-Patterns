好，我们正式做 **Stage5-Phase3-WP4：No-Answer Evidence Threshold** 的学习 / 面试总结。

这一个 WP 很值得认真吃透。它最后没有产出 threshold，也没有跑 EVAL，但工程价值反而很高：你完整经历了一次从 **“我想加一个拒答阈值”** 到 **“先证明数据、检索结果、实验输入、校准过程都可信，最后让真实数据否掉这个假设”** 的生产级 Evaluation 流程。

Codex 最终确认：真实 Evidence 冻结成功；CAL 14 cases 上完整枚举 `19 × 27 = 513` 个 threshold configuration；`FA==0` 的配置有 141 个，`TA>FAb` 的配置有 140 个，但两者交集为 0。因此 `WP4_CANDIDATE = REJECT_NO_FEASIBLE_POLICY`。没有 `LockedPolicyV2`，所以没有资格运行 untouched EVAL。110_codex_real_calibration_review.mdMD

------

# 一、工程总结：这个 WP 到底做了什么

一句话概括：

> **建立了一个可审计、不可偷看 EVAL、不可伪造 provenance 的 No-Answer threshold calibration pipeline，并最终证明当前 RRF top1 + margin policy family 不满足业务硬约束。**

完整链路是：

```
Dataset Authority
      ↓
Synthetic Retrieval Substrate
      ↓
Real RRF Retrieval
      ↓
Strict Evidence v2
      ↓
Evidence Authority Freeze
      ↓
CAL-only Signal Derivation
      ↓
Deterministic Threshold Grid
      ↓
Feasibility Check
      ↓
NO_FEASIBLE_POLICY
```

最重要的是：这个 WP 并不是简单实现一个：

```
if score < 0.3:
    abstain()
```

实际做的是把“这个 score 有没有资格用来决定拒答”逐层证明清楚。

------

# 二、这个 WP 最核心的几个工程思想

| 核心思想                       | 你这次真正做的事情                                           |
| ------------------------------ | ------------------------------------------------------------ |
| Ground Truth Authority         | 不为了满足想要的 case 分布伪造 conflict / misleading 标注    |
| Reality → Contract             | 先确认真实 corpus/cache/runtime，再冻结 Evidence contract    |
| Hash ≠ Authority               | hash 只能证明内容没变，不能证明内容本来就是对的              |
| Evidence Authority             | Gate 必须从 raw evidence 自己重新验证，不能信 caller 提交的“validated proof” |
| Derivation Authority           | Calibration lock 必须由 Gate / canonical calibration 从 raw evidence重新推导 |
| Label-blind retrieval          | Ground Truth 不能控制哪些 query 被 retrieval                 |
| Exact projection               | Evaluation adapter 只能验证并无损投影 runtime provenance，不能偷偷修复 |
| Version isolation              | v2 新字段不能静默污染 historical v1 schema                   |
| Calibration / Evaluation split | CAL 可以看标签调 policy；EVAL 必须 untouched                 |
| Negative experiment result     | 找不到 feasible threshold 是有效结论，不是实现失败           |

------

# 三、你应该记住的术语

**No-Answer Policy（拒答策略）**
根据当前 evidence 是否足够，决定 `ANSWER` 还是 `ABSTAIN` 的策略。

**Evidence Threshold（证据阈值）**
用 retrieval signal，例如 top1 score 和 top1-top2 margin，机械决定 evidence 是否够强的阈值。

**Calibration（校准）**
只使用 CAL split 的 Ground Truth 选择 policy 参数。

**Evaluation（评估）**
在 policy 完全冻结之后，使用 untouched EVAL split 测试泛化表现。

**False Answer / FA（错误回答）**
Ground Truth 应该拒答，但 policy 选择了 ANSWER。

**False Abstain / FAb（错误拒答）**
Ground Truth 可以回答，但 policy 选择了 ABSTAIN。

**True Answer / TA（正确回答）**
应该回答，也确实 ANSWER。

**True Abstain / TAb（正确拒答）**
应该拒答，也确实 ABSTAIN。

**Feasible Policy（可行策略）**
满足硬性业务约束的 threshold 配置；WP4 冻结条件是 `FA == 0 && TA > FAb`。

**RRF（Reciprocal Rank Fusion，倒数排名融合）**
按照多个 retrieval channel 的 rank 进行融合；本实验使用 `Σ1/(60+rank)`。

**Top1 Score（第一名融合分数）**
排名第一 candidate 的 RRF score。

**Top1-Top2 Margin（前两名分差）**
第一名与第二名 evidence score 的差，用于表达第一名是否明显领先。

**Provenance（来源链 / 可追溯信息）**
证明 evidence 的 rank、score、channel、artifact、run 等事实来自哪个真实 runtime execution。

**Authority（事实权威来源）**
某个事实究竟由哪个组件拥有并定义，而不是“谁手上碰巧有一份值”。

**Canonical Digest（规范化摘要）**
把结构化对象按固定序列化规则计算出的 digest，用于稳定身份绑定，而非单纯文件字节 hash。

**LockedPolicy（冻结策略）**
Calibration 完成以后被冻结、绑定 Dataset/Evidence/Substrate 的 policy；之后 EVAL 只能使用它。

**Fail Closed（失败关闭）**
一旦 Authority / provenance / contract 不可信，不猜、不修、不继续实验，直接 BLOCK。

**Label-Blind（标签盲）**
生成 retrieval evidence 时不能让 Ground Truth 标签影响 retrieval population、顺序或输出。

**Schema Version Isolation（Schema 版本隔离）**
v1、v2 的字段集合和语义必须真正隔离，不能新增 v2 字段后让历史 v1 也悄悄接受。

------

# 四、这个 WP 最值得面试讲的“踩坑链”

这是 WP4 的精华。面试官如果问“你做 Agent Eval 时遇到过什么复杂问题”，不要只讲最后阈值失败，应该讲这条演化链。

1. **Dataset annotation authority 出问题。**
   最开始希望覆盖 `CONFLICT / MISLEADING`，但真实 15-doc corpus 根本没有可信 conflict。于是没有为了满足实验设计硬造标签，而是 rebaseline Dataset。这里的原则是：**Ground Truth Authority > benchmark distribution。**
2. **CAL/EVAL semantic leakage。**
   即使 case ID 不同，如果两个 split 本质上考察同一种 reasoning pattern，也可能泄漏。后来重新替换 case，确保 split 的语义隔离。
3. **Validated proof 可以被 caller 伪造。**
   早期 Gate 接受一个“已经验证过”的对象，但这个对象可以由调用方自行构造。
   修复：**Gate 必须拥有 raw evidence validation。**
4. **即使 raw evidence 是真的，Calibration lock 仍然可以伪造。**
   Caller 可以拿伪造 signal 校准出一个 self-consistent lock。
   修复：Gate 从 raw evidence 自己重新生成 CAL signals，再执行 canonical calibration，并和 supplied lock exact compare。
5. **WP4 synthetic Dataset 却绑定了 WP2 SciFact cache。**
   hash 本身都是合法的，但它们属于另一个 corpus。
   这证明：**identity 正确不等于 experiment substrate 正确。**
6. **READY cache metadata 可以自证。**
   artifact 自己说“我的 identity 是 X”，validator 又拿 artifact 自己的 metadata 去验证 X，这不是 Authority。
   修复：expected facts 必须来自 artifact 外部 frozen contract。
7. **file SHA 正确，不代表 manifest semantics 正确。**
   修改 manifest，再重新算 SHA，也能得到“完整性通过”。
   修复：validator 必须机械 recompute semantic manifest。
8. **Index-time semantics 与 query-time semantics 可能漂移。**
   cache 是用 frozen embedding model 建的，但 warm-load 时 query adapter 如果允许不同 model/prompt，结果仍然失真。
   修复：cache identity 必须同时约束 indexing 和 querying semantics。
9. **Producer 看 Ground Truth 决定 retrieval population。**
   一个 DIAGNOSTIC case 可以因为 split 标签而直接不被 retrieval。
   这是典型实验泄漏。
   修复：producer runtime path 只能看 `case_id + query`。
10. **Evaluation adapter 帮 runtime “修正”结果。**
    runtime 给 `[rank2, rank1]`，producer 排序成 `[rank1,rank2]`，最终 Evidence 看起来更漂亮，但那已经不是 runtime 原始事实。
    修复原则：**validate + project，不 repair。**
11. **v2 新增 channel ranks 却污染 v1。**
    共享 DTO 增加 optional 字段后，historical v1 也能接受以前属于 unknown-field 的字段。
    修复：真正拆分 V1/V2 DTO。
12. **最终实验假设自己失败。**
    全部基础设施通过以后，真实 CAL 数据仍然证明没有 feasible threshold。
    这不是“最后一步翻车”，而是整个 Eval 系统终于开始发挥它真正的作用：**阻止一个看起来合理但实际上不成立的方案进入 production。**

------

# 五、最终 Calibration 为什么失败

这部分面试时一定要会手算逻辑。

当前 policy：

```
ANSWER iff

top1 >= min_top1

AND

margin >= min_margin
```

其中：

```
top1 = RRF 第一名 score
margin = top1 - top2
```

硬约束：

```
FA == 0
TA > FAb
```

真实 CAL 里出现了一个非常麻烦的现象。

最高 ANSWERABLE 的：

```
top1 = 0.03278688524590164
```

而三个 negative case 同样：

```
0.03278688524590164
```

包括：

```
cal-misleading-context-dedup-provenance
cal-misleading-marker-network
cal-weak-output-retry-delay
```

Codex fresh 复核也确认了这个 exact overlap。110_codex_real_calibration_review.mdMD

所以只用 top1，显然无法分开。

你可能会问：

> 那 margin 不是还能救吗？

这正是为什么实验不是只口头分析，而是穷举整个二维 grid。

```
Top1 thresholds = 19
Margin thresholds = 27

19 × 27 = 513
```

最终：

```
FA_ZERO_CONFIGS = 141
TA_GT_FAB_CONFIGS = 140

intersection = 0
```

也就是说：

```
存在很多能做到 FA=0 的 threshold；
存在很多能做到 TA>FAb 的 threshold；

但没有任何一个同时做到两件事。
```

因此：

```
FEASIBLE_CONFIG_COUNT = 0
```

这个结论比“best accuracy 是多少”更重要。

------

# 六、为什么没有继续跑 EVAL

这是非常经典的面试题。

面试官可能会问：

> Calibration 都失败了，为什么不还是在 EVAL 上跑一下看看？

你的回答应该是：

> 因为我们的实验协议要求 EVAL 只能消费 calibration 后冻结的 LockedPolicy。Calibration 没有找到 feasible policy，所以不存在合法 LockedPolicy。如果这时候为了看看效果而人工挑一个 threshold 去跑 EVAL，相当于改变了实验协议，而且容易让 EVAL 变成新的调参集。为了保持 untouched evaluation，我们直接停止。

这个回答很加分。

因为它说明你理解：

```
Evaluation 不是“最后再跑一遍测试集”。

Evaluation 是：
对已经被冻结的决策做一次未参与调参的检验。
```

没有 frozen decision，就没有资格谈 untouched evaluation。

------

# 七、面试问题：设计类

| 问题                                  | 推荐回答核心                                                 |
| ------------------------------------- | ------------------------------------------------------------ |
| 为什么不用固定经验阈值，比如 0.3？    | RRF score不是概率，尺度取决于 rank/fusion configuration，不能假设跨系统校准；阈值必须在冻结 substrate 上做 empirical calibration。 |
| 为什么不能直接用 Dense cosine score？ | 当前实验的 retrieval decision owner 是 RRF evidence；Dense、BM25、RRF 分数尺度不同，也都不是天然 calibrated probability。 |
| 为什么用 top1 + margin？              | top1表达最强 evidence 强度，margin表达第一名相对第二名的区分度；是一个简单、可解释的二维 policy family。 |
| 为什么 `FA==0`？                      | 这是 frozen business constraint，不是算法自然规律；当前实验把错误回答视为必须归零的硬风险。 |
| 为什么还要求 `TA>FAb`？               | 防止 trivial policy：“所有请求全部 ABSTAIN”，它虽然能 FA=0，但没有实用价值。 |
| 为什么 calibration grid 不随机搜索？  | 参数只有两个，候选边界来自 observed signals；确定性 grid 能完整复现、审计和冻结。 |
| 为什么用 observed values + midpoint？ | 对 threshold classifier，prediction 只会在 signal 穿过某个 observed value 时变化；midpoint可以代表相邻区间，无需连续暴力搜索。 |
| 为什么需要 sentinel？                 | 覆盖“低于所有值”和“高于所有值”的边界 policy，例如全部回答、全部拒答。 |

------

# 八、面试问题：Authority 类

这个 WP 最能和普通“写 Eval 脚本”的候选人拉开差距。

### Q：为什么 hash 不等于 Authority？

答：

> Hash 只能证明“我现在看到的内容和计算 hash 时的内容一致”，不能证明内容本身是谁产生的、是否符合真实 runtime semantics。比如一个伪造 manifest 重新计算 SHA 后仍然 hash-valid。因此 validator 需要从外部 frozen facts 重建 expected semantics，而不是让 artifact 自己证明自己。

### Q：为什么 Gate 自己要重新 calibration？

答：

> 因为如果 Gate 只验证一个 caller 提供的 LockedPolicy 是否内部自洽，caller 可以用伪造 calibration signals 得到一个完全自洽的 lock。所以 Gate 必须从 raw evidence 自己派生 signals，再运行 canonical calibration，最后比较 expected lock 和 supplied lock。

### Q：为什么 Evaluation producer 不能排序？

答：

> Producer 的职责是 observation，而不是 repair。如果 runtime 输出顺序错误，producer帮它排序以后，evidence就不再代表真实 runtime行为，evaluation系统反而把 production bug 隐藏了。

------

# 九、面试问题：实验设计类

### “如果没有 feasible threshold，你下一步会怎么做？”

不要回答：

> 我会继续调 threshold。

正确逻辑是：

> 当前二维 policy family 已经被完整枚举证明不可行，所以继续调同一组 threshold 没有意义。如果业务仍然要求零 False Answer，我会把下一步定义成新的 experiment，例如增加更有区分度的 evidence signal、修改 retrieval substrate、引入 reranker-derived evidence，或者重新审视 acceptance constraint。但这些都必须新建实验版本，不能修改当前已冻结结果。

这能体现一个很重要的能力：

**知道什么时候应该停止调参。**

------

# 十、如果让你设计下一版，你有哪些方向

这里只作为面试思考，不代表当前 WP 自动继续。

比如可以研究：

```
Policy family v2:
top1
+ margin
+ source agreement
+ lexical/dense agreement
+ evidence consistency

或者：

RRF
→ CE rerank
→ calibrated answerability score
```

但你一定要补一句：

> 这属于新的 experiment，而不是当前 WP4 的 bug fix。WP4 已经证明当前 frozen policy family 不可行。

否则面试官容易觉得你没有实验版本意识。

------

# 十一、这个 WP 的 Truthful Implementation Boundary

这部分你以后写简历、面试都必须守住。

**你可以说：**

> 我实现并验证了一套 evaluation-only No-Answer threshold calibration pipeline，基于冻结的 Dense+BM25 RRF retrieval evidence，具备 Dataset/Evidence provenance、strict schema、version isolation、label-blind evidence collection、deterministic calibration、CAL/EVAL isolation 和 fail-closed acceptance semantics。

也可以说：

> 在真实 28-case retrieval evidence 上，完成 14-case calibration，穷举 513 个 top1/margin threshold 配置，证明当前 policy family 无法同时满足 zero false-answer 与最低 answer utility constraint，因此 candidate 被 `REJECT_NO_FEASIBLE_POLICY`。

**不能说：**

> 我已经上线了 production abstention。

没有。

不能说：

> No-Answer threshold 最终是 X。

没有 threshold。

不能说：

> EVAL 表现多少。

没有运行 EVAL。

不能说：

> Gate v3 最终 REJECT。

没有 `GateOutcome.REJECT`。

准确状态是：

```
WP4_CANDIDATE = REJECT_NO_FEASIBLE_POLICY
GATE_V3_FINAL_QUALITY = NOT_RUN
REAL_EVALUATION = NOT_RUN
```

Codex 对这个边界也做了明确区分。110_codex_real_calibration_review.mdMD

------

# 十二、简历怎么写

比较稳妥的一版：

> **Built an evaluation-only no-answer calibration pipeline for RAG retrieval, with strict evidence provenance, versioned schemas, leakage-safe CAL/EVAL isolation, and deterministic threshold search; validated 28 real retrieval cases and demonstrated that the initial RRF top-score/margin policy family had no feasible operating point under a zero-false-answer constraint.**

中文理解：

> 搭建 RAG 拒答策略评估与校准链路，覆盖 evidence provenance、schema versioning、CAL/EVAL 防泄漏及 deterministic threshold search；基于真实 28-case retrieval evidence 验证初始 RRF top-score/margin 策略在零错误回答约束下不存在可行工作点。

这比“调了一个阈值”有含金量得多。

------

# 十三、建议你真正记住的 6 句话

1. **Ground Truth 用来评价输出，不应该控制输出是否被采集。**
2. **Hash proves integrity, not authority.**
3. **Evaluator 可以验证 Runtime，但不能偷偷修 Runtime。**
4. **Calibration 决定 policy，Evaluation 只能验证已经冻结的 policy。**
5. **没有 LockedPolicy，就没有 untouched Evaluation。**
6. **一个可信的 REJECT，比一个通过作弊调出来的 PASS 更有价值。**

最后这句话其实就是整个 WP4。

------

# 十四、推荐学习文档文件名

```
stage5_phase3_wp4_no_answer_evidence_threshold_interview.md
```

建议放在你之前 WP2/WP3 interview notes 同级位置。

这份 WP 的最终结论可以浓缩成一句面试金句：

> **我做的不是找一个能过测试的阈值，而是建立一条足够可信的实验链路，让系统有能力证明这个阈值策略本身不成立。**