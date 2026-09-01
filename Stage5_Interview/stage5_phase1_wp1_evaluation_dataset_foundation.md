进入：

# Stage5-Phase1-WP1 学习 / 面试总结

本 WP 的核心价值：

> 从“记录 Agent 执行发生了什么”（WP2 Artifact）进一步演进到“定义什么样的执行结果算好”（Evaluation Dataset + Ground Truth）。

WP2 解决：

```text
事实采集问题
```

WP1 解决：

```text
评价标准问题
```

两者组合后，才具备真正 Evaluation Framework 的基础。

------

# 1. 一句话项目定义（面试版）

> 我设计了一套 Evaluation Dataset Foundation，通过统一的 EvaluationCase、Dataset 和 Ground Truth Schema，将用户输入、期望结果和检索/生成评价标准结构化，为后续 Recall@K、MRR、NDCG 和 LLM Judge 等评估器提供统一输入。

------

# 2. 为什么需要 Evaluation Dataset？

很多 Agent 项目做到：

```text
用户问题
    |
    |
Agent回答
```

然后人工判断：

> 感觉回答变好了。

这是不可复现的。

生产环境需要回答：

- 这次改 Prompt 后有没有提升？
- 换 Embedding 模型后 Recall 有没有下降？
- 新 Retriever 是否影响旧 Case？
- 哪些 Bad Case 被修复？

因此需要：

```text
固定测试输入
+
固定评价标准
+
重复执行
+
指标比较
```

也就是 Evaluation Dataset。

------

# 3. EvaluationCase 为什么不是 TestCase？

这是面试容易问的问题。

很多系统会直接：

```text
TestCase
```

但 Agent Evaluation 和传统测试不同。

------

传统测试：

```text
input
 ↓
expected output
```

例如：

```python
assert result == "xxx"
```

------

Agent Evaluation：

输出通常不是唯一答案。

例如：

问题：

> 什么是 CDT？

可能：

回答 A：

> CDT 是通信领域的数据传输机制...

回答 B：

> CDT 在 LTE 中表示...

两个都可能正确。

因此不能只比较：

```text
string equality
```

------

EvaluationCase：

更多是：

```text
input
+
evaluation criteria
```

而不是：

```text
input
+
exact output
```

------

# 4. EvaluationCase 设计

当前：

```text
EvaluationCase

case_id

name

input

expected_output

ground_truth

metadata
```



------

## 为什么没有 run_id？

因为：

Case ≠ Execution。

关系：

正确：

```text
EvaluationCase
        |
        |
        +---- Run 1
        |
        +---- Run 2
        |
        +---- Run 3
```

错误：

```text
EvaluationCase
        |
        Artifact
```

------

原因：

未来需要比较：

例如：

同一个 Case：

模型：

```text
Qwen
```

vs

```text
DeepSeek
```

Retriever：

```text
BM25
```

vs

```text
Vector
```

Embedding：

```text
Model A
```

vs

```text
Model B
```

如果 Case 绑定 Artifact，就无法比较。

------

# 5. Ground Truth 是本 WP 最核心设计

Ground Truth：

不是简单：

```json
{
"answer":"xxx"
}
```

而是根据 Evaluation 类型拆分。

当前：

```text
GroundTruth

 ├── retrieval
 |
 ├── ranking
 |
 └── generation
```



------

# 6. Retrieval Ground Truth

服务：

```text
Recall@K
MRR
```

例如：

问题：

> CDT字段在哪里定义？

人工标注：

```json
{
"relevant_chunks":[
 {
  "document_id":"cdt.md",
  "chunk_id":"10"
 }
]
}
```

------

之后：

Artifact：

```text
retrieved_items:

[
 chunk1,
 chunk10,
 chunk20
]
```

计算：

命中：

```text
chunk10
```

得到 Recall。

------

# 7. Ranking Ground Truth

服务：

```text
NDCG
```

区别：

Recall：

只关心：

> 找到了没有。

Ranking：

关心：

> 排序是否合理。

------

例如：

人工：

```text
chunk A:
3分

chunk B:
2分

chunk C:
1分
```

表示：

A 最重要。

如果系统：

```
C
B
A
```

虽然都找到了。

但是排序差。

------

所以：

WP1 保留：

```text
graded_relevance
```

而不是简单 boolean。



------

# 8. Generation Ground Truth

服务：

```text
LLM Judge
```

例如：

Case：

问题：

> 什么是RAG？

参考答案：

```text
RAG combines retrieval and generation...
```

未来 Judge：

输入：

```text
Question

Agent Answer

Reference Answer

Retrieved Context
```

评价：

- correctness；
- completeness；
- faithfulness。

------

当前 WP1 只预留：

```text
reference_answer
```

没有实现 Judge。

这是正确边界。



------

# 9. 为什么 Retrieval 和 Ranking 不强制一致？

这是一个架构取舍。

可能有人认为：

```text
ranking.grades
必须来自
retrieval.relevant_chunks
```

但不一定。

例如：

人工评价：

| Chunk | relevance |
| ----- | --------- |
| A     | 3         |
| B     | 2         |
| C     | 1         |

其中：

C：

可能不是严格 relevant。

但它可以用于：

NDCG 排序评价。

因此：

当前设计：

```text
retrieval GT
ranking GT
```

独立。



------

# 10. 为什么选择 JSON + Pydantic？

面试回答：

> 当前 Dataset 属于评估资产，不是在线业务数据，因此采用版本化 JSON + Pydantic Schema 校验，而不是引入数据库。这样方便 Git 管理、Code Review 和离线回归，同时避免提前引入数据生命周期管理复杂度。

------

## 如果追问：

以后数据量很大怎么办？

回答：

> 当前设计通过 dataset_schema_version 保留演进空间。未来如果出现多人标注、大规模查询或者在线评估需求，可以演进到 Dataset Service 或数据库存储，但不会影响 EvaluationCase 抽象。

------

# 11. 为什么需要 Schema Version？

因为 Evaluation Dataset 会变化。

例如：

v1:

```json
{
reference_answer:"xxx"
}
```

未来：

v2:

```json
{
reference_answer:{
 answer:"xxx",
 sources:[]
}
}
```

如果没有版本：

旧 Dataset 无法解析。

所以：

```text
evaluation-dataset.v1
```

是必要的。



------

# 12. 和 WP2 Artifact 的完整关系

现在：

```text
              Evaluation Dataset

                    |
                    |
              EvaluationCase

                    |
                    |
             Agent Execution

                    |
                    |
              RAG Artifact

                    |
                    |
             Evaluator

                    |
                    |
             Metric Result
```

------

未来：

Recall：

```text
Dataset GroundTruth
        +
Artifact retrieved_items
        ↓
Recall@K
```

MRR：

```text
Dataset GroundTruth
        +
Artifact ranked_items
        ↓
MRR
```

NDCG：

```text
graded relevance
        +
ranked_items
        ↓
NDCG
```

LLM Judge：

```text
reference_answer
        +
Agent answer
        +
context
        ↓
Judge score
```

------

# 13. 面试高频问题

## Q1：你的 Evaluation Dataset 怎么设计？

回答：

> 我把 Dataset 分成三个层次：Dataset 是一组评估任务集合；EvaluationCase 描述一次可重复执行的问题；Ground Truth 描述不同评估维度的标准，包括 retrieval relevance、ranking relevance 和 generation reference answer。这样可以支持不同 evaluator 独立消费。

------

## Q2：为什么不用人工直接看结果？

回答：

> 人工评估无法覆盖大量回归场景，而且不同人员标准不一致。通过 Dataset 固化输入，通过 Ground Truth 固化评价标准，可以支持模型、Prompt、Retriever 版本之间的量化比较。

------

## Q3：Ground Truth 怎么生成？

当前真实状态：

还未实现标注平台。

正确回答：

> 当前阶段采用人工构造或已有知识库专家标注 Dataset，重点是建立统一 Schema。后续如果规模扩大，可以增加标注流程和质量校验机制。

------

# 14. 本 WP 面试材料推荐文件名

建议：

```text
docs/interview_materials/stage5_phase1_wp1_evaluation_dataset_foundation.md
```

结构：

```text
1. 一句话项目定义

2. 为什么需要 Evaluation Dataset

3. EvaluationCase 设计

4. Ground Truth 设计

5. Retrieval/Ranking/Generation 三类评价关系

6. Dataset Schema Version

7. JSON + Pydantic 选型

8. 与 RAG Artifact 的数据流

9. Trade-off

10. 后续 Evaluator 演进
```

------

# 本 WP 学习完成

当前状态：

```text
Stage5-Phase1-WP1
Evaluation Dataset Foundation

PASS + 学习完成
```

下一步：

进入：

```text
Stage5-Phase1-WP2
Retrieval Evaluator
```

实现：

- Recall@K；
- MRR。

按照当前工作流：

等级：

```text
M
```

执行：

```text
AgentEvalOps
→ ZCode / DeepSeek
```

等待进入下一步。