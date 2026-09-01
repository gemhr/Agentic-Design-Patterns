当前使用的模型：**GPT-5.6 Sol**。

RAG（Retrieval-Augmented Generation，检索增强生成）可以先记成一句话：

> **RAG = 在模型生成答案之前，先从外部知识源检索相关信息，再把检索结果作为上下文交给 LLM（大语言模型）生成答案。**

但如果是为了 AI 应用 / Agent 面试，只理解成“向量库 + LLM”远远不够。真正应该掌握的是一条完整的 **数据链路、在线检索链路、质量评估链路和生产化链路**。

------

# 一、RAG 到底解决什么问题

LLM 本身主要有三个天然限制。

第一是 **Knowledge Cutoff（知识截止）**。模型训练结束以后，新产生的信息默认不知道。

第二是 **Private Knowledge（私有知识）**。公司内部文档、代码、产品规范、数据库数据不可能全部进入模型训练集。

第三是 **Hallucination（幻觉）**。LLM 本质上是在预测下一个 Token，它可以生成语言上非常合理但事实错误的内容。

RAG 的核心思想就是：

```text
用户问题
   ↓
检索外部知识
   ↓
找到与问题相关的证据
   ↓
把证据放入 Prompt / Context
   ↓
LLM 基于证据生成答案
```

因此 RAG 本质上不是“让模型记住知识”，而是：

> **在推理时动态给模型提供知识。**

这个区别非常重要。

------

# 二、最经典的 RAG 架构

最基础的 RAG 可以拆成两个阶段：

```text
Offline Pipeline
离线知识构建

Document
   ↓
Parse
   ↓
Chunk
   ↓
Embedding
   ↓
Vector Database


Online Pipeline
在线查询

Query
   ↓
Embedding
   ↓
Retrieval
   ↓
Top-K Chunks
   ↓
Prompt Construction
   ↓
LLM
   ↓
Answer
```

也就是说，RAG 实际上有两条 Pipeline（流水线）。

------

# 三、离线阶段：知识是怎么进入 RAG 的

## 1. Document Loading

首先读取各种数据源，例如：

```text
PDF
Markdown
Word
HTML
代码
数据库
Wiki
API
知识库
```

这个阶段经常叫：

**Ingestion（数据摄取）**

关键词可以记：

```text
Data Ingestion
Document Loader
Knowledge Base
ETL
```

------

# 四、Parsing：文档解析

原始文档通常不能直接拿来检索。

例如 PDF 里面可能存在：

```text
正文
表格
标题
页眉
页脚
图片
代码块
```

所以首先需要 Parsing（解析）。

例如：

```text
PDF
 ↓
Parser
 ↓
Structured Text
```

这里其实是很多生产 RAG 的第一个坑。

如果 PDF Parser 把：

```text
字段 | 类型 | 描述
user_id | int | 用户ID
```

解析成乱序文本，那么后面的 Embedding 再强也没有用。

这类问题常被概括为：

> **Garbage In, Garbage Out。**

即：

> 输入质量差，后面的检索模型救不了。

------

# 五、Chunking：为什么必须切块

假设有一份 100 页 PDF。

不能每次用户提问都把 100 页交给 LLM。

所以通常会进行：

**Chunking（文本分块）**

例如：

```text
Document

↓ Chunking

Chunk 1
Chunk 2
Chunk 3
Chunk 4
...
```

比如：

```text
chunk_size = 1000 tokens
chunk_overlap = 150 tokens
```

Overlap（重叠）是为了防止语义刚好被切断。

例如：

```text
Chunk 1:
Redis 是一个内存数据库，它支持...

Chunk 2:
...持久化机制，包括 RDB 和 AOF。
```

如果完全硬切：

```text
Chunk 1:
Redis 是一个内存数据库，它支持

Chunk 2:
持久化机制，包括 RDB 和 AOF
```

语义会受到影响。

------

# 六、Chunking 是 RAG 的核心工程问题之一

常见 Chunking 策略包括：

```text
Fixed-size Chunking
固定长度切块

Recursive Chunking
递归切块

Semantic Chunking
语义切块

Structure-aware Chunking
结构感知切块

Parent-Child Chunking
父子块切分
```

面试里非常容易被问：

> Chunk 越大是不是越好？

不是。

Chunk 太小：

```text
优点：
定位精确

缺点：
上下文不完整
```

Chunk 太大：

```text
优点：
语义完整

缺点：
噪声更多
检索粒度下降
Token 成本增加
```

所以它本质上是一个：

> **Recall（召回）和 Precision（精确率）的权衡。**

这个以后值得单独学。

------

# 七、Embedding：把文字变成向量

Embedding（向量嵌入）是 Dense Retrieval（稠密检索）的核心。

例如：

```text
"Python 是一种编程语言"
```

经过 Embedding Model：

```text
[0.23, -0.51, 0.78, ...]
```

可能是：

```text
768维
1024维
1536维
3072维
```

用户问题：

```text
Python 有什么特点？
```

同样转成向量：

```text
Query Vector
```

然后比较：

```text
Query Vector
     vs
Document Vectors
```

找相似的文本块。

------

# 八、Vector Database：向量数据库做什么

Vector Database（向量数据库）主要保存：

```text
Embedding Vector
Chunk Text
Metadata
Document ID
Chunk ID
```

然后执行：

```text
Nearest Neighbor Search
最近邻搜索
```

典型相似度包括：

```text
Cosine Similarity
余弦相似度

Dot Product
点积

Euclidean Distance
欧氏距离
```

如果数据规模大，就不会暴力计算所有向量，而是使用：

**ANN（Approximate Nearest Neighbor，近似最近邻）**

常见关键词：

```text
HNSW
IVF
PQ
FAISS
Milvus
Qdrant
Weaviate
Chroma
pgvector
```

这些不用现在一次学完。

------

# 九、Dense Retrieval 不是唯一检索方式

这是你之后非常值得重点掌握的一部分。

经典搜索引擎还有：

**Sparse Retrieval（稀疏检索）**

最典型：

**BM25**

BM25 更像传统关键词搜索。

例如用户搜索：

```text
ModelInvocationRouter
```

Dense Retrieval 可能觉得：

```text
model routing
LLM router
模型选择
```

语义类似。

但 BM25 会非常喜欢精确出现：

```text
ModelInvocationRouter
```

的文档。

所以两者各有优势。

Dense 强在：

```text
语义
同义词
自然语言表达
```

BM25 强在：

```text
关键词
专有名词
错误码
API 名称
类名
精确字符串
```

------

# 十、于是出现 Hybrid Retrieval

Hybrid Retrieval（混合检索）：

```text
             Query
              │
       ┌──────┴──────┐
       ↓             ↓
     Dense          BM25
   Retrieval      Retrieval
       ↓             ↓
Dense Ranking    BM25 Ranking
       └──────┬──────┘
              ↓
            Fusion
              ↓
            Top K
```

这就是现代 RAG 非常常见的一种架构。

你的项目已经涉及这一条路线：

```text
Dense
+
BM25
+
RRF
```

因此以后 RAG 八股里，这部分我们应该重点讲。

------

# 十一、RRF 是干什么的

两种检索器返回的 Score（分数）通常不能直接比较。

例如 Dense：

```text
0.91
0.87
0.83
```

BM25：

```text
15.2
12.6
8.1
```

两个 Score 空间完全不同。

RRF（Reciprocal Rank Fusion，倒数排名融合）干脆不比较原始分数，而是比较排名：

```text
score(d) =
Σ 1 / (k + rank(d))
```

简单理解：

> 一个文档如果同时被多个 Retriever（检索器）排在前面，那么最终排名会更高。

这个以后我们单独深入。

------

# 十二、Retrieval 后通常还有 Reranking

很多 RAG 不是：

```text
Retriever → LLM
```

而是：

```text
Retriever
 ↓
Candidate Documents
 ↓
Reranker
 ↓
Top Documents
 ↓
LLM
```

例如：

```text
Retriever Top 50
        ↓
Reranker
        ↓
Top 5
```

为什么？

Retriever 要追求：

> **不要漏掉正确答案。**

所以倾向于高 Recall。

Reranker（重排序器）则负责：

> **把最相关的内容排到最前面。**

所以更加关注排序质量。

常见：

```text
Cross Encoder
LLM Reranker
Cohere Rerank
BGE Reranker
```

------

# 十三、Retriever 和 Reranker 的职责不要混

这是一个很好的面试回答。

可以把整个搜索系统想成：

```text
100 万条 Chunk
      ↓
Retriever
      ↓
几十条
      ↓
Reranker
      ↓
几条
      ↓
LLM
```

Retriever：

> 快，负责大规模筛选。

Reranker：

> 慢，但准确，负责精排。

这和推荐系统里的：

```text
召回
↓
粗排
↓
精排
```

思想非常类似。

------

# 十四、Context Construction：检索到不等于直接塞给模型

得到 Top-K 以后，还需要：

**Context Construction（上下文构建）**

例如：

```text
System Prompt

User Query

Retrieved Context:
[Document 1]
...

[Document 2]
...

Instructions:
Only answer using provided context.
```

这里有非常多工程问题：

```text
Top-K 应该多少？

Chunk 顺序怎么排？

重复 Chunk 怎么去除？

同一个 Document 是否限制 Chunk 数？

Context 超过 Token Budget 怎么办？

Metadata 是否放进去？

来源如何引用？
```

所以现代 RAG 已经不只是 Retrieval。

------

# 十五、Generation：最终才轮到 LLM

最终：

```text
Query
+
Retrieved Evidence
+
Instructions
```

交给 LLM。

LLM 执行的是：

**Grounded Generation（基于证据生成）**

理想状态：

```text
Knowledge Base:
Redis 支持 RDB 和 AOF。

Question:
Redis 有哪些持久化方式？

Answer:
Redis 主要支持 RDB 和 AOF。
```

这里核心要求叫：

**Groundedness（有据性）**

即答案应该能被检索证据支持。

------

# 十六、一个完整的现代 RAG Pipeline

你可以先把这张图记住：

```text
                    Offline

Documents
   ↓
Parsing
   ↓
Cleaning
   ↓
Chunking
   ↓
Metadata
   ↓
Embedding
   ↓
Index
   ↓
Vector DB / Search Index


                    Online

User Query
     ↓
Query Processing
     ↓
┌───────────────┐
│               │
Dense          BM25
│               │
└───────┬───────┘
        ↓
      Fusion
       RRF
        ↓
 Candidate Set
        ↓
    Reranking
        ↓
 Context Selection
        ↓
 Prompt Construction
        ↓
       LLM
        ↓
      Answer
```

这基本就是我们后面学习 RAG 的主地图。

------

# 十七、Advanced RAG 在基础 RAG 上加了什么

所谓 Advanced RAG（高级检索增强生成）并没有一个严格统一的标准。

通常意味着开始处理基础 RAG 的各种失败情况，例如：

```text
Query Rewrite
Multi Query
Query Expansion
Hybrid Retrieval
Metadata Filtering
Reranking
Parent-Child Retrieval
Context Compression
Semantic Chunking
Adaptive Retrieval
Corrective RAG
Self-RAG
Agentic RAG
GraphRAG
```

你暂时不用一个个学。

后面我们逐层拆。

------

# 十八、RAG 最大的误区：检索成功 ≠ RAG 成功

例如标准答案在知识库中。

Retriever 也找到了。

但最终 LLM 还是回答错了。

可能是：

```text
正确 Chunk 排第 8
但只取 Top 5
```

或者：

```text
Top 5 有大量冲突文档
```

或者：

```text
Prompt 没要求依据知识库
```

或者：

```text
正确 Chunk 被 Token 截断
```

因此 RAG 实际至少有三个质量层级：

```text
Retrieval Quality
检索质量

Context Quality
上下文质量

Generation Quality
生成质量
```

------

# 十九、所以 RAG Evaluation 非常重要

一个成熟的 RAG 系统不能只靠：

> “我问了一下，感觉回答还可以。”

Retrieval 可以单独测。

例如：

### Recall@K

正确文档有没有进入前 K 个结果？

例如：

```text
Ground Truth = Document A

Top 5 =
B
D
A
F
G
```

A 在 Top5：

```text
Recall@5 = 命中
```

------

### MRR

MRR（Mean Reciprocal Rank，平均倒数排名）关心：

> 正确结果出现得够不够靠前。

例如：

```text
A 排名第1 → 1
A 排名第2 → 1/2
A 排名第5 → 1/5
```

------

### NDCG

NDCG（Normalized Discounted Cumulative Gain，归一化折损累计增益）进一步考虑：

> 多个结果的相关程度以及它们的顺序。

例如：

```text
非常相关
比较相关
略微相关
完全不相关
```

可以有不同 relevance score。

这些正好也与你已经做过的 Retrieval / Ranking Evaluation 能力直接关联。

------

# 二十、Generation 也需要评估

除了检索，还可以看：

```text
Faithfulness
忠实性

Groundedness
有据性

Answer Relevance
答案相关性

Correctness
正确性

Citation Accuracy
引用准确率
```

其中一个非常重要的区别：

### Correctness

答案是不是客观正确。

### Faithfulness

答案是不是来自给定 Context。

例如：

Context：

```text
没有提到 Redis。
```

LLM：

```text
Redis 支持 RDB 和 AOF。
```

这句话可能：

```text
Correctness = 高
Faithfulness = 低
```

因为模型靠自己的参数知识回答了。

这个区别经常考。

------

# 二十一、RAG 和 Fine-tuning 最容易混

Fine-tuning（微调）改变：

```text
模型参数
```

RAG 改变：

```text
模型输入上下文
```

简单记：

```text
Fine-tuning
Teach the model how to behave.

RAG
Give the model information to use.
```

微调更适合：

```text
风格
任务行为
格式
领域能力模式
```

RAG 更适合：

```text
动态知识
私有知识
大量文档
需要引用来源
```

当然现实中两者可以同时使用。

------

# 二十二、RAG 和 Memory 也不要混

这个对 Agent 开发尤其重要。

RAG 通常解决：

> **外部知识是什么？**

Memory（记忆）通常解决：

> **这个用户 / Agent 过去发生过什么？**

例如：

```text
公司 Kubernetes 部署规范
→ RAG

用户喜欢 Python
→ Memory

之前任务执行失败原因
→ Agent Runtime / Memory / State
```

工程上两者可能都使用 Vector DB，但：

> **存储技术相同，不代表语义和生命周期相同。**

你的项目里把 RAG 与 Long-term Memory（长期记忆）作为独立能力边界，这是一个非常适合面试讲的设计点。

------

# 二十三、Agentic RAG 为什么越来越重要

普通 RAG：

```text
用户问题
↓
检索一次
↓
回答
```

Agentic RAG（智能体式 RAG）：

```text
User Query
   ↓
Agent
   ↓
判断是否需要检索
   ↓
选择知识源
   ↓
生成检索 Query
   ↓
Retrieval
   ↓
分析结果
   ↓
结果不足？
 ┌───┴───┐
是       否
↓        ↓
再次检索  Answer
```

也就是：

> Retrieval（检索）从固定 Pipeline 的一步，变成 Agent 可以自主调用的 Tool / Capability（工具 / 能力）。

这是 Agent 开发岗位很值得学的方向。

------

# 二十四、真正生产级 RAG 还需要考虑什么

如果只是 Demo：

```text
PDF
→ Chroma
→ similarity_search
→ LLM
```

已经可以跑。

但 Production RAG（生产级 RAG）还会面对：

```text
数据更新
索引版本
Embedding Model 升级
文档删除
权限控制
多租户
重复数据
缓存
超时
失败降级
Observability
Evaluation
知识冲突
索引一致性
增量更新
Prompt Injection
成本
Latency
```

这也是：

> **“会用 LangChain 做 RAG”**

和：

> **“能够设计 RAG 系统”**

之间最大的差异。

------

# 二十五、建议你先建立四层知识体系

这是我们接下来学习 RAG 最合适的顺序：

```text
Level 1 基础原理
├─ Embedding
├─ Vector Search
├─ Chunking
├─ Top-K
├─ Cosine Similarity
└─ Vector DB

Level 2 Retrieval
├─ Dense Retrieval
├─ Sparse Retrieval
├─ BM25
├─ Hybrid Retrieval
├─ RRF
├─ Metadata Filtering
└─ Reranking

Level 3 Advanced RAG
├─ Query Rewrite
├─ Multi Query
├─ Parent-Child
├─ Context Compression
├─ Adaptive Retrieval
├─ Corrective RAG
└─ Agentic RAG

Level 4 Production + Evaluation
├─ Recall@K
├─ MRR
├─ NDCG
├─ Faithfulness
├─ Groundedness
├─ Dataset
├─ Observability
├─ Cache
├─ Index Versioning
└─ Security
```

其中 **Level 1～2 是必须掌握，Level 3 是 Agent 岗位的重要加分项，Level 4 是你真正可以和普通 RAG Demo 拉开差距的地方。**

------

# 二十六、你现在最应该形成的 RAG 心智模型

不要记：

> RAG = Vector DB + LLM。

应该记成：

```text
                RAG

       ┌─────────┴─────────┐

Knowledge Pipeline      Query Pipeline
知识构建                  查询执行

Parsing                Query Processing
Chunking               Retrieval
Embedding              Fusion
Indexing               Reranking
Metadata               Context Building
                       Generation

           ↓

        Evaluation
           ↓
Retrieval / Ranking / Generation

           ↓

       Production
           ↓
Version / Cache / ACL / Observability
Latency / Cost / Failure Handling
```

这基本就是后续所有 RAG 八股的总框架。

------

## 这一轮先记住 10 个关键词

后面你可以去其他地方先简单看看：

**Chunking（分块）**、**Embedding（向量嵌入）**、**Dense Retrieval（稠密检索）**、**Sparse Retrieval（稀疏检索）**、**BM25**、**Hybrid Retrieval（混合检索）**、**RRF（倒数排名融合）**、**Reranker（重排序器）**、**Recall@K（K位召回率）**、**Groundedness（有据性）**。

下一步我建议我们**不要直接冲 Advanced RAG**，而是先从整个系统最底层的 **Embedding → Vector Search → Chunking** 开始。把这三个搞清楚以后，再进入 **BM25 → Hybrid Retrieval → RRF → Reranker**，这部分也是你现有项目最值得重点准备面试追问的区域。

# 八股

## 什么样的问题更适合用 RAG 而非微调，两者在知识更新、行为适配与可追溯性上如何分工？

这个问题非常适合面试，因为它本质上在考你是否理解：

> **RAG（检索增强生成）主要解决“模型需要知道什么”，Fine-tuning（微调）主要解决“模型应该怎么做”。**

这句话可以作为你的第一层回答。

### 什么时候更适合用 RAG

如果问题的核心是 **知识本身会变化、属于私有数据、需要精确引用或追溯来源**，优先考虑 RAG。

典型场景包括：

- 企业内部知识库、产品文档、SOP、API 文档
- 法规、政策、价格、库存等频繁变化的信息
- 大量知识，无法经济地塞进训练集
- 用户需要知道“答案来自哪份文档”
- 不同用户只能访问不同知识
- 文档可能被新增、修改、删除

例如：

> “公司当前生产环境 Kubernetes 发布流程是什么？”

这类问题非常适合 RAG。

因为发布流程以后可能修改，你只需要：

```text
修改文档
↓
重新索引
↓
RAG 检索最新版本
```

而不需要重新训练模型。

### 什么时候更适合微调

Fine-tuning 更适合改变模型的：

> **Behavior（行为）、Style（风格）、Task Pattern（任务模式）和输出习惯。**

例如：

- 固定输出 JSON 格式
- 学习企业客服话术
- 学习特定分类任务
- 学习代码审查风格
- 学习如何把输入转换成某种结构
- 改善特定任务的遵循能力

例如：

```text
输入：
用户的故障描述

输出必须为：
{
  "severity": "...",
  "component": "...",
  "action": "..."
}
```

如果你有大量这样的训练样本，那么 Fine-tuning 就可能比在每个 Prompt 里写一大堆 Few-shot Example（少样本示例）更合适。

### 知识更新：RAG 明显占优

这是最重要的区别之一。

假设企业有：

```text
10 万份技术文档
```

今天修改了一份数据库设计规范。

#### RAG

只需要：

```text
Document Update
↓
Re-index
↓
New Embedding
↓
生效
```

知识更新时间可以做到分钟级甚至秒级。

#### Fine-tuning

如果知识写入模型参数：

```text
收集新数据
↓
构造训练集
↓
训练
↓
评估
↓
部署新模型
```

成本和风险都更高。

而且还存在：

**Catastrophic Forgetting（灾难性遗忘）**

即模型学习新知识时可能影响已有能力。

所以面试里可以直接说：

> 对于高频变化的事实性知识，我通常不会优先使用 Fine-tuning，而是让知识留在外部 Knowledge Base（知识库）里，通过 RAG 动态注入。

### 行为适配：Fine-tuning 通常占优

反过来，如果需求是：

> “让模型长期稳定地按照某种方式做事。”

Fine-tuning 更有优势。

例如：

```text
用户问题
↓
自动识别 Intent
↓
严格生成内部 DSL
```

如果每次都靠：

```text
2000 Token System Prompt
+
20 个 Few-shot Example
```

成本会越来越高。

这时候可以考虑微调，把这类行为“内化”进模型参数。

所以可以简单理解：

```text
知识变化
→ RAG

行为变化
→ Fine-tuning
```

但这是原则，不是绝对规则。

### 可追溯性：RAG 明显更强

这是企业应用非常重要的一点。

假设模型回答：

> 当前系统默认使用 PostgreSQL。

用户可能继续问：

> 你从哪里知道的？

RAG 可以返回：

```text
source:
database_architecture.md

section:
Production Database

chunk_id:
doc_183_chunk_7
```

因此可以实现：

**Citation（引用）**

以及：

**Provenance（来源追踪）**

Fine-tuning 就很难做到。

因为知识被编码进模型权重以后：

```text
Question
↓
Neural Network Parameters
↓
Answer
```

你很难说：

> 这个答案具体来自训练集的第 3819 条数据。

因此如果场景要求：

```text
审计
合规
证据
引用
来源追踪
```

RAG 通常更合适。

### 从三个维度看两者分工

这是面试特别推荐的一张表：

| 维度         | RAG      | Fine-tuning    |
| ------------ | -------- | -------------- |
| 知识更新     | 强       | 弱             |
| 行为适配     | 中       | 强             |
| 可追溯性     | 强       | 弱             |
| 私有知识     | 非常适合 | 可以但维护困难 |
| 高频变化知识 | 非常适合 | 不适合         |
| 输出风格     | 一般     | 非常适合       |
| 固定任务模式 | 一般     | 非常适合       |
| 权限控制     | 容易     | 困难           |
| 知识删除     | 容易     | 很困难         |
| 引用来源     | 容易     | 很困难         |

这里有一个面试很容易加分的点：

> **知识删除能力其实是 RAG 非常重要的优势。**

### 为什么“知识删除”对微调很麻烦

比如某员工已经离职：

```text
Alice 是项目负责人
```

如果它只是 RAG 文档：

```text
删除 / 修改文档
↓
更新索引
```

即可。

如果这个知识被 Fine-tuning 到模型参数里：

> 你很难精准地把这一条知识从权重中删除。

这涉及：

**Machine Unlearning（机器遗忘）**

这是一个很复杂的研究领域。

因此企业知识管理一般不会把频繁变化的事实全部交给微调。

### 一个非常重要的面试误区

面试官可能问：

> RAG 可以完全替代 Fine-tuning 吗？

答案是：

> 不能，因为二者解决的问题并不相同。

比如：

公司希望模型：

1. 知道最新产品价格；
2. 按公司客服标准回答问题。

最合理的架构反而可能是：

```text
Fine-tuned Model
负责行为和回答风格

        +

RAG
负责最新产品知识
```

也就是：

```text
           User Query
                ↓
        Fine-tuned Model
        行为能力 / 风格
                +
              RAG
        最新外部知识
                ↓
             Answer
```

两者可以组合，而不是竞争关系。

### 进一步分工：Knowledge vs Capability

你可以把模型系统理解成两层。

#### Knowledge Layer（知识层）

回答：

> “系统知道什么？”

包括：

```text
企业文档
数据库信息
用户资料
产品信息
法规
代码
```

适合：

> RAG。

#### Capability Layer（能力层）

回答：

> “模型会怎么处理这些信息？”

例如：

```text
分类
总结
推理
格式转换
代码生成
工具选择
回答风格
```

更可能考虑：

> Prompt Engineering（提示工程）、Fine-tuning 或 Agent Workflow。

这其实是比“RAG vs Fine-tuning”更成熟的系统设计思路。

### 一个更真实的例子

假设你做一个企业代码 Agent。

需求包括：

#### 需求 A

> 查询公司当前 Python 编码规范。

这是：

```text
动态企业知识
```

应该：

> RAG。

#### 需求 B

> 模型必须按照公司固定的 Code Review（代码审查）格式输出。

例如：

```text
P0
P1
P2
Known Limitation
```

这是：

```text
Behavior Pattern
```

可以通过：

```text
Prompt
↓
Few-shot
↓
如果规模足够再 Fine-tuning
```

#### 需求 C

> 回答必须说明依据哪份设计文档。

这是：

```text
Traceability
```

适合：

> RAG + Citation。

### RAG 的一个额外优势：Access Control

这是生产环境很重要，但很多八股不会提。

假设公司有两个部门：

```text
HR
Engineering
```

HR 用户只能检索 HR 文档。

Engineering 用户只能检索工程文档。

RAG 可以在 Retrieval 阶段使用：

**Metadata Filtering（元数据过滤）**

例如：

```text
department = engineering
```

于是：

```text
User
↓
ACL
↓
Retriever
↓
Authorized Documents
```

如果知识全部微调进同一个模型：

> 很难保证某些训练知识绝对不会被其他用户问出来。

因此企业私有知识通常更倾向于 RAG。

关键词：

**ACL（访问控制列表）**

**Row-Level Security（行级安全）**

**Tenant Isolation（租户隔离）**

### 但 RAG 也不是没有缺点

面试最好主动说这一点。

RAG 引入了一条完整的检索链路：

```text
Query
↓
Retriever
↓
Index
↓
Reranker
↓
Context
↓
LLM
```

因此多出了很多失败模式：

```text
检索不到
检索错
排序错
Chunk 不完整
Context 太长
Embedding 不匹配
索引过期
```

也就是：

> RAG 的知识更新和可追溯性更好，但代价是增加 Retrieval Complexity（检索复杂度）。

Fine-tuning 则：

```text
Question
↓
Model
↓
Answer
```

在线链路通常更简单。

### 还有一个很经典的问题：延迟

RAG 请求可能要经历：

```text
Query Rewrite
↓
Embedding
↓
Vector Search
↓
BM25
↓
RRF
↓
Reranking
↓
LLM
```

因此 Latency（延迟）通常比单纯调用 Fine-tuned Model 更高。

Fine-tuned Model：

```text
Query
↓
Model Inference
```

链路更短。

所以系统设计时经常需要考虑：

> 是否每个 Query 都需要 Retrieval？

这进一步会引出：

**Adaptive RAG（自适应 RAG）**

### 什么时候两者都不需要

这个面试问题也可能出现。

比如：

> “把用户输入转换成 JSON。”

如果模型本身已经做得很好：

```text
Prompt + Structured Output
```

就够了。

没必要：

```text
Fine-tuning
```

更没必要：

```text
RAG
```

工程上要避免：

> 为了使用技术而使用技术。

### 放到你的项目里怎么讲

你现在的真实项目更偏向这样：

```text
LocalAgent
   │
   ├── RAG
   │    ├── Dense Retrieval
   │    ├── BM25
   │    ├── RRF
   │    └── Ranking / Evaluation
   │
   └── Agent Runtime
```

你的知识主要来自外部知识库，而且还需要独立评估 Retrieval / Ranking，因此走 RAG 是合理的。

这里并不存在：

> “通过微调把知识写进模型参数”

这条主线。

所以面试的时候不要把项目描述成：

> 我们比较了 Fine-tuning，最后 RAG 指标更高。

除非你真的做过对应实验。

更准确的表述应该是：

> 项目的需求主要是动态私有知识检索，同时需要能够独立评估召回和排序质量，因此知识层采用了 RAG，而没有把业务知识固化到模型参数中。

这个回答可信度会更高。

### 30 秒面试答案

你可以这样回答：

> RAG 和微调主要解决不同的问题。RAG 更适合动态、私有、需要追溯来源的知识，因为知识存放在外部知识库中，更新文档和索引就可以生效，也容易做权限控制和 Citation。Fine-tuning 更适合行为适配，比如固定输出格式、任务模式或者领域回答风格，因为它是在改变模型参数。实际生产中通常不是二选一，而是把知识交给 RAG，把稳定的行为模式交给 Prompt 或 Fine-tuning，两者可以组合。

### 如果面试官继续追问

#### Q：为什么不用 Fine-tuning 存公司文档？

你可以答：

> 文档变化频繁，而 Fine-tuning 更新成本高，而且知识难以精确删除、做权限隔离和来源追踪；RAG 可以通过重新索引快速更新，也可以返回具体 Document 和 Chunk 作为证据。

#### Q：那 Fine-tuning 完全不能学习知识吗？

可以。

Fine-tuning 当然可以让模型学习领域知识。

关键不是：

> 能不能。

而是：

> **是否适合作为动态知识管理机制。**

通常不适合。

#### Q：为什么 RAG 更可追溯？

因为 Retrieval 是显式过程：

```text
Query
↓
Document A
Chunk 3
↓
Answer
```

系统可以记录：

```text
document_id
chunk_id
retrieval_score
rank
citation
```

而 Fine-tuning 的知识存在模型参数中，没有天然的 source mapping。

### 推荐你继续深入的关键词

这道题之后建议重点了解：

**Knowledge Grounding（知识落地/基于知识约束）**
**Model Adaptation（模型适配）**
**Catastrophic Forgetting（灾难性遗忘）**
**Machine Unlearning（机器遗忘）**
**Data Provenance（数据来源追踪）**
**Citation（引用）**
**Knowledge Freshness（知识新鲜度）**
**ACL（访问控制列表）**
**Tenant Isolation（租户隔离）**
**Adaptive RAG（自适应 RAG）**

其中面试 ROI 最高的是：

> **Knowledge Freshness + Traceability + Behavior Adaptation + Access Control。**

这四个维度基本就能把“RAG vs Fine-tuning”讲得比普通八股完整很多。

## 文档解析、Chunking、Overlap、元数据和父子块设计如何影响召回与上下文完整性

这个问题非常关键，因为很多 RAG（Retrieval-Augmented Generation，检索增强生成）效果差，问题并不出在 Embedding（向量嵌入）模型，而是出在 **文档解析和 Chunk 设计**。

可以先记住一句话：

> **RAG 的召回上限，很大程度上由文档进入索引前的结构化质量决定；Chunk 决定“能不能找到”，Overlap 和父子块决定“找到以后上下文是否完整”，Metadata 决定“能不能把搜索空间缩到正确范围”。**

### 先看完整链路

文档进入 RAG 一般经历：

```text
Raw Document
    ↓
Parsing
文档解析
    ↓
Structure
结构恢复
    ↓
Chunking
切块
    ↓
Overlap
块间重叠
    ↓
Metadata Enrichment
元数据增强
    ↓
Embedding / Index
向量化与索引
```

在线查询：

```text
Query
  ↓
Metadata Filter
  ↓
Retriever
  ↓
找到 Chunk
  ↓
Parent / Neighbor Expansion
  ↓
构建完整 Context
  ↓
LLM
```

所以这几个设计实际上共同决定两个核心指标：

- **Retrieval Recall（检索召回）**：正确证据有没有被找到。
- **Context Completeness（上下文完整性）**：找到以后，证据够不够完整，LLM 能不能正确理解。

### 文档解析为什么会直接影响召回

Parsing（文档解析）是最容易被低估的一环。

假设原始文档是：

```text
3.2 Timeout

默认请求超时时间为 30 秒。

异常情况：
- Model 调用：60 秒
- Tool 调用：10 秒
```

解析正确：

```text
标题：Timeout
正文：默认请求超时时间为30秒
异常：
Model 60秒
Tool 10秒
```

Embedding 能比较好地表达：

> Timeout + Model + Tool + 时间限制

但 PDF Parser 如果解析成：

```text
3.2 Timeout 30 秒 Model
异常情况默认请求
60 秒 Tool 10 秒
```

语义结构已经被破坏。

即使你使用非常好的 Embedding Model：

> 它也只能对错误文本做 Embedding。

所以一个重要工程原则是：

> **Parsing Error（解析错误）是上游错误，无法简单通过提高 Top-K 或换更强模型解决。**

### Parsing 最重要的是恢复“文档结构”

生产 RAG 不是简单的：

```text
PDF → plain text
```

而应该尽量保留：

```text
Document
 ├── Title
 ├── Section
 │    ├── Subsection
 │    ├── Paragraph
 │    ├── Table
 │    └── Code Block
```

例如 Markdown：

```markdown
# Runtime

## Cancellation

Cancellation 会向子任务传播。

## Timeout

Timeout 不等价于 Cancellation。
```

最好让 Chunk 知道：

```text
document = runtime.md
section = Runtime
subsection = Cancellation
```

而不是只保存：

```text
Cancellation 会向子任务传播。
```

否则检索到以后，LLM 可能根本不知道这段话属于什么上下文。

### 表格是 Parsing 特别容易出问题的地方

例如：

| Component | Timeout |
| --------- | ------- |
| Model     | 60s     |
| Tool      | 10s     |

如果解析成：

```text
Component Timeout Model Tool 60s 10s
```

基本废掉了。

更合理的是转成：

```text
Component: Model
Timeout: 60s

Component: Tool
Timeout: 10s
```

或者保留结构化表格。

面试里可以说：

> 对表格类知识，我会优先保证行列关系不被 Parser 打乱，因为 RAG 检索关注的不只是 Token 是否存在，更重要的是实体和属性之间的语义关系。

这是很好的回答。

### Chunking 本质上是在决定“检索单元”

Chunk（文本块）是 Retriever 真正搜索的对象。

假设整个文档：

```text
Document
 ├── Chunk A
 ├── Chunk B
 ├── Chunk C
 └── Chunk D
```

用户不是在检索 Document，而是在检索这些 Chunk。

所以：

> **Chunk Boundary（块边界）本质上定义了 RAG 的最小知识单位。**

这句话值得记。

### Chunk 太大会发生什么

例如把整个 10 页章节作为一个 Chunk：

```text
Chunk:
Python
FastAPI
PostgreSQL
Redis
Docker
Kubernetes
Observability
...
```

用户问：

> Redis 的持久化机制是什么？

这个 Chunk 可能确实包含答案。

所以：

```text
Recall ↑
```

因为答案不容易被切掉。

但是问题是大量无关信息稀释了语义。

Embedding 表示的是整个 Chunk：

```text
Redis + Python + Docker + Kubernetes + ...
```

因此和：

```text
Redis persistence
```

的向量相似度可能反而下降。

这叫：

**Semantic Dilution（语义稀释）**。

同时送给 LLM 后：

```text
Context Noise ↑
Token Cost ↑
```

### Chunk 太小会发生什么

反过来：

```text
Chunk 1:
Redis 支持

Chunk 2:
RDB 和 AOF 两种

Chunk 3:
主要的持久化机制
```

用户问：

> Redis 支持哪些持久化方式？

Embedding 检索 Chunk 2：

```text
RDB 和 AOF 两种
```

它缺少主体：

> 谁支持？

于是出现：

```text
Retrieval Precision 可能还行
Context Completeness ↓
```

这就是：

**Context Fragmentation（上下文碎片化）**。

### 所以 Chunk Size 是一个典型 Trade-off

可以这样理解：

| Chunk | 优点         | 缺点             |
| ----- | ------------ | ---------------- |
| 小    | 检索粒度精准 | 上下文容易碎     |
| 大    | 上下文完整   | 噪声大、语义稀释 |
| 中等  | 平衡         | 需要实验确定     |

因此面试不要回答：

> 最佳 Chunk Size 是 500 Token。

不存在统一最佳值。

更正确的是：

> Chunk Size 应由文档结构、问题粒度、Embedding Model、Retriever 和下游 Context Budget 共同决定，并通过 Evaluation 数据集验证。

这句话非常重要。

### 固定长度 Chunking

最简单：

```text
每 500 Token 切一次
```

比如：

```text
Chunk 1 = token 1~500
Chunk 2 = token 451~950
```

优点：

- 简单；
- 快；
- 行为稳定；
- 容易控制 Token 数量。

缺点：

> 完全不知道语义边界。

可能把：

```text
函数说明
参数表
异常说明
```

从中间切开。

因此一般属于：

> 好 Baseline（基线），但未必是最终方案。

### Recursive Chunking

Recursive Chunking（递归切块）非常常见。

它尝试按照：

```text
章节
↓
段落
↓
句子
↓
字符
```

逐层切分。

例如优先：

```text
\n\n
```

切段落。

还太大就：

```text
\n
```

再切。

还太大：

```text
.
```

继续切。

优势：

> 尽量尊重自然语言边界。

一般比纯字符截断合理。

### Structure-aware Chunking

Structure-aware Chunking（结构感知切块）对技术文档尤其重要。

例如：

```markdown
## Cancellation

### Propagation

...

### Cleanup

...
```

你可以按照 Header（标题）结构切：

```text
Chunk:
Title: Cancellation
Subsection: Propagation
Content: ...
```

对于：

- Markdown；
- API Docs；
- RFC；
- 技术设计文档；
- 代码文档；

通常非常适合。

你的知识库类型里本来就有 Markdown、PDF、RFC、论文，所以结构感知切分比单纯字符切分更有实际意义。

### Overlap 到底解决什么问题

Overlap（重叠）的核心目的只有一个：

> **降低关键信息恰好落在 Chunk Boundary 上而被割裂的概率。**

例如没有 Overlap：

```text
Chunk A:
Agent 执行超时后首先触发 cancellation

Chunk B:
signal，随后等待子任务执行 cleanup。
```

两个 Chunk 单独看都不完整。

加入 100 Token Overlap：

```text
Chunk A:
...
Agent 执行超时后首先触发 cancellation signal，
随后等待子任务执行 cleanup。

Chunk B:
Agent 执行超时后首先触发 cancellation signal，
随后等待子任务执行 cleanup。
...
```

上下文完整性提高。

### Overlap 并不是越大越好

假设：

```text
chunk_size = 500
overlap = 400
```

那：

```text
Chunk 1 = 1~500
Chunk 2 = 101~600
Chunk 3 = 201~700
```

大量重复。

会造成：

#### Index Bloat（索引膨胀）

同一个内容重复很多份。

#### Retrieval Redundancy（检索结果重复）

Top5：

```text
Chunk 17
Chunk 18
Chunk 16
Chunk 19
Chunk 20
```

实际上可能都是同一段。

#### Context Waste

最终 Prompt 里全是重复文字。

#### Diversity下降

本来 Top5 可以覆盖五条证据，现在五条都来自同一位置。

所以：

> Overlap 是边界保险，不是用来代替合理 Chunking 的。

这个是很好的面试表达。

### Overlap 和 Recall 是什么关系

适当的 Overlap：

```text
Boundary Information Loss ↓
Recall ↑
Context Completeness ↑
```

Overlap 太大：

```text
Duplicate Candidates ↑
Result Diversity ↓
Context Efficiency ↓
```

所以依然是 Trade-off（权衡）。

### Metadata 为什么不是“附属字段”

Metadata（元数据）其实是生产 RAG 非常核心的能力。

一个 Chunk 通常不应该只有：

```json
{
  "text": "..."
}
```

而应该有类似：

```json
{
  "document_id": "...",
  "section": "...",
  "chunk_id": "...",
  "version": "...",
  "source": "...",
  "created_at": "...",
  "tenant_id": "...",
  "permission": "...",
  "language": "..."
}
```

元数据主要有四种作用。

#### 作用一：Metadata Filtering

例如用户问：

> Phase 6 的 RAG 架构是什么？

如果知识库同时存在：

```text
Phase 3
Phase 4
Phase 5
Phase 6
```

纯 Embedding 可能全部召回。

但是：

```text
phase = 6
```

先 Filter：

```text
100000 chunks
↓
Metadata Filter
↓
300 chunks
↓
Vector Search
```

搜索空间大幅缩小。

这通常可以提高：

```text
Precision
```

也可能间接提高有效 Recall。

#### 作用二：处理版本冲突

假设：

```text
architecture_v1.md
architecture_v2.md
```

旧版：

> 默认使用 SQLite。

新版：

> 默认使用 PostgreSQL。

如果都在索引里：

```text
Retriever
↓
SQLite
PostgreSQL
```

两个 Chunk 都可能非常相关。

这时候单纯 Embedding 不知道谁更新。

Metadata 可以保存：

```text
version
effective_date
status = active / deprecated
```

检索时限制：

```text
status = active
```

因此 Metadata 实际参与：

> **Knowledge Authority（知识权威性）管理。**

这是高级 RAG 非常重要的一点。

#### 作用三：权限

例如：

```text
tenant_id = company_A
department = finance
access_level = confidential
```

Retrieval 前：

```text
ACL Filter
↓
Semantic Search
```

避免不该看到的知识进入 Context。

注意：

> **不能先全库检索，再交给 LLM 判断用户有没有权限。**

这是 Security Boundary（安全边界）错误。

#### 作用四：Citation

最终回答：

> 根据 Runtime Contract 3.2 节……

你需要知道：

```text
document_id
title
section
page
source
```

这些信息一般都来自 Metadata。

所以：

> 没有良好 Metadata，Citation 很难可靠。

### 父子块为什么出现

现在来到很经典的矛盾：

> 小 Chunk 有利于准确检索，大 Chunk 有利于完整理解。

怎么办？

于是出现：

**Parent-Child Retrieval（父子块检索）**。

核心思想：

> **小块负责找，大块负责读。**

这句话非常值得直接背下来。

#### Parent-Child 怎么工作

原始文档：

```text
Parent Chunk
整个一个章节，2000 tokens

├── Child 1 300 tokens
├── Child 2 300 tokens
├── Child 3 300 tokens
└── Child 4 300 tokens
```

Embedding：

```text
只对 Child 建索引
```

Query：

```text
用户问题
↓
找到 Child 3
↓
根据 parent_id
↓
加载 Parent Chunk
↓
给 LLM
```

于是：

```text
Retrieval Precision
由小 Child 保证

Context Completeness
由大 Parent 保证
```

这是 Parent-Child 最大的意义。

#### 举个例子

文档：

```text
## Cancellation

Cancellation 在 Runtime 中负责终止执行。

### Propagation
取消信号需要传播到子任务。

### Cleanup
任务收到取消后必须执行资源清理。

### Timeout
Timeout 可以触发 Cancellation，
但二者不是同一个概念。
```

如果用户问：

> Timeout 和 Cancellation 什么关系？

Child 可能只检索：

```text
Timeout 可以触发 Cancellation，
但二者不是同一个概念。
```

这已经很相关。

但如果 LLM 需要进一步解释为什么：

Parent：

```text
整个 Cancellation 章节
```

能提供：

```text
Propagation
Cleanup
Timeout
```

完整语义。

#### 父子块有什么代价

它不是免费午餐。

1. Context 变大

命中一个 Child，却加载一个 2000 Token Parent。

如果 Top5 每个对应不同 Parent：

```text
5 × 2000 = 10000 tokens
```

Context 很快爆掉。

2. Parent 重复

两个 Child：

```text
Child A → Parent X
Child B → Parent X
```

如果不 Dedup（去重）：

```text
Parent X
Parent X
```

重复进入 Context。

3. Noise 增加

Child 非常相关，不代表 Parent 所有内容都相关。

因此工程上还要配合：

```text
Deduplication
Context Budget
Parent Size Control
Context Compression
```

### 还有一种方式：Neighbor Expansion

不一定必须 Parent-Child。

例如检索到：

```text
Chunk 17
```

可以额外加载：

```text
Chunk 16
Chunk 17
Chunk 18
```

这叫：

**Neighbor Expansion（邻块扩展）**。

特别适合连续文档。

优点：

```text
简单
Context 增量可控
```

缺点：

> 邻居不一定是真正语义父节点。

### Parent-Child 和 Overlap 的区别

这个很容易面试问到。

#### Overlap

解决：

> 块边界切断问题。

作用发生在：

```text
Chunk Creation
```

#### Parent-Child

解决：

> 检索粒度和上下文粒度矛盾。

作用发生在：

```text
Retrieval → Context Construction
```

所以：

```text
Overlap
= 切块阶段保证局部连续

Parent-Child
= 检索阶段恢复更完整上下文
```

两者可以同时存在。

### 这几个设计如何分别影响 Recall

可以把它们拆开看。

#### Parsing

```text
错误解析
→ 内容语义损坏
→ Embedding 错误
→ Recall ↓
```

#### Chunk Size

过大：

```text
语义稀释
→ 相似度下降
→ Recall ↓
```

过小：

```text
Query 和证据表达不完整
→ Recall ↓
```

#### Overlap

合理：

```text
减少边界断裂
→ Recall ↑
```

过大：

```text
重复结果
→ 有效 Recall / Diversity ↓
```

#### Metadata

合理过滤：

```text
缩小候选空间
→ Precision ↑
→ 有效 Recall ↑
```

错误过滤：

```text
Ground Truth 被提前过滤掉
→ Recall = 0
```

这点尤其重要。

Metadata Filter 是 Hard Filter（硬过滤），比向量排序更危险。

#### Parent-Child

Child：

```text
提高检索粒度
```

Parent：

```text
提高上下文完整性
```

因此：

> 它并不一定直接提高 Recall@K，而更多解决“检索命中后上下文是否足以回答”的问题。

这是非常值得面试说的一点。

### 一个经典面试陷阱

面试官：

> 父子块能提高 Recall 吗？

不要直接说：

> 能。

更准确的是：

> 父子块通常通过小 Child 提高检索精度，同时通过 Parent 恢复上下文完整性。是否提升 Recall 取决于 Child 的索引和检索设计；Parent Expansion 本身主要改善的是 Context Completeness，而不是 Retriever 的 Recall。

这个回答明显比普通八股强。

### 如何工程化选择 Chunk Size

千万不要：

```text
我觉得 500 Token 差不多。
```

更合理的方法：

建立 Evaluation Dataset（评估数据集）。

例如分别实验：

```text
Chunk Size
256
512
1024
1500
```

Overlap：

```text
0
64
128
256
```

然后比较：

```text
Recall@5
MRR
NDCG
Context Token Count
Answer Accuracy
Latency
```

可能得到：

```text
512 + 128

Recall@5 = 0.89
MRR = 0.74
Context = 3500 tokens
```

而：

```text
1024 + 256

Recall@5 = 0.91
MRR = 0.68
Context = 6200 tokens
```

这时候就要做：

> Quality / Cost / Latency Trade-off。

### 这正好能映射到你的项目经验

你当前项目已经不是“随便建一个 Chroma 索引然后问几道题”的状态，而是已经有独立的 Retrieval / Ranking Evaluation，并且 RAG 路线涉及 Dense、BM25、RRF。

因此如果面试官问：

> 你怎么确定 Chunk 参数？

你最好不要回答：

> 根据经验设置。

更符合你整个项目方向的表达应该是：

> Chunk、Overlap 和 Retrieval 策略都属于可评估配置，我更倾向于固定 Dataset 和索引配置后，通过 Recall@K、MRR、NDCG 以及最终回答质量做对比，而不是只靠人工问答判断。

这和你真实 Evaluation-Driven Optimization（评估驱动优化）的项目叙事是统一的。

### 一个完整的设计思维

你可以把整个过程理解成：

```text
                 Raw Document
                      ↓
              Parsing Quality
                      ↓
               Semantic Units
                      ↓
          ┌───────────┴───────────┐
          ↓                       ↓
     Small Chunks             Metadata
      精确召回                限定范围
          ↓                       ↓
          └───────────┬───────────┘
                      ↓
                  Retrieval
                      ↓
              Child Hit / Top-K
                      ↓
       Parent / Neighbor Expansion
                      ↓
               Complete Context
                      ↓
                     LLM
```

所以一个好的 RAG ingestion 设计实际上是在同时优化：

> **Findability（可检索性） + Completeness（完整性） + Authority（权威性） + Efficiency（效率）。**

### 30 秒面试回答

你可以这样说：

> 文档解析决定进入索引的语义质量，如果标题、表格或者段落关系在解析阶段已经丢失，后续再强的 Embedding 也很难补救。Chunking 决定检索粒度，太大会导致语义稀释，太小又容易造成上下文碎片化；Overlap 主要解决块边界切断问题，但过大会导致索引和检索结果重复。Metadata 可以用于版本、权限、来源以及业务范围过滤，提高有效检索质量。父子块则解决检索粒度和上下文粒度之间的矛盾，用小 Child 做精准召回，再恢复较大的 Parent 给 LLM，从而兼顾检索精度和上下文完整性。

### 面试继续追问

#### Q1：Chunk 越小 Recall 越高吗？

不一定。

过小可能丢失语义主体和关联信息，Query 与 Chunk 的 Embedding 匹配反而下降。

#### Q2：Overlap 为什么不用 50%？

因为 Overlap 越大会带来越多重复 Chunk，导致索引膨胀、Top-K 同质化和 Context 浪费。

#### Q3：Metadata Filter 一定提高检索效果吗？

不一定。

正确 Filter 可以缩小搜索空间，但如果过滤条件错误，Ground Truth 会直接被排除，Recall 直接变成 0。

#### Q4：为什么不直接把 Parent Embedding？

因为大 Parent 容易出现 Semantic Dilution，影响精确检索。

典型父子策略：

> Child 用于 Search，Parent 用于 Read。

#### Q5：父子块和 Reranker 谁解决什么问题？

Reranker：

> 优化候选结果顺序。

Parent-Child：

> 优化检索粒度与最终上下文完整性的矛盾。

不是同一个层面。

### 这一题建议继续深入的关键词

优先级最高：

- **Semantic Chunking（语义切块）**
- **Structure-aware Chunking（结构感知切块）**
- **Parent-Child Retrieval（父子块检索）**
- **Small-to-Big Retrieval（小块检索、大块返回）**
- **Neighbor Expansion（邻块扩展）**
- **Semantic Dilution（语义稀释）**
- **Context Fragmentation（上下文碎片化）**
- **Metadata Filtering（元数据过滤）**
- **Document Hierarchy（文档层级结构）**
- **Context Compression（上下文压缩）**

其中面试最值得真正理解的是：

> **Small-to-Big Retrieval、Metadata Filtering、Semantic Chunking，以及 Chunk Size 如何通过 Evaluation 来确定。**

## 稀疏检索与稠密检索各自擅长什么，Hybrid Search 如何融合两类分数或排名？

这个问题是 RAG 检索部分的核心八股之一。可以先记住一句：

> **Sparse Retrieval（稀疏检索）擅长“字面匹配”，Dense Retrieval（稠密检索）擅长“语义匹配”，Hybrid Search（混合检索）通过融合两路候选，降低单一检索器的盲区。**

### Sparse Retrieval 是什么

Sparse Retrieval（稀疏检索）通常基于词项匹配。

最典型的是：

> **BM25**

它关心的是：

```text
Query 里出现了什么词
↓
Document 里有没有这些词
↓
这些词是否稀有、是否重要
↓
文档中出现频率如何
```

例如用户问：

```text
ModelInvocationRouter timeout
```

某个文档正好包含：

```text
ModelInvocationRouter
```

那么 BM25 通常会非常喜欢这个文档。

------

# 二、为什么叫 Sparse

传统词袋模型可以想象成一个超高维向量：

```text
Python
Redis
Kubernetes
Timeout
ModelInvocationRouter
...
```

假设词表有：

```text
100000 个词
```

一个文档实际上只包含几百个词。

于是它的向量可能是：

```text
[0, 0, 3.2, 0, 0, 0, 5.1, 0, ...]
```

绝大多数维度都是：

```text
0
```

所以叫：

> **Sparse Vector（稀疏向量）**

------

# 三、Sparse Retrieval 最擅长什么

## 1. 精确关键词

比如：

```text
ERR_CONNECTION_RESET
```

或者：

```text
LOCAL_AGENT_LLM_BACKEND
```

这种东西 Dense Model 未必理解得特别好。

BM25：

> 字符串对得上就是强信号。

------

## 2. 类名 / 函数名 / API

例如：

```text
ModelInvocationRouter
AgentState
ContextBuilder
create_merge_request
```

这类技术文档非常适合 BM25。

这也是为什么：

> **代码库、API 文档、日志、错误码场景中特别值得保留 Sparse Retrieval。**

------

## 3. 专有名词

例如：

```text
PostgreSQL
HNSW
RRF
GPT-5.6
RFC 9110
```

Dense Retrieval 有时会因为语义空间泛化得太厉害，把很多相关概念一起找回来。

BM25 会更加精确。

------

## 4. 数字 / ID / 版本号

例如：

```text
HTTP 429
v2.3.1
P1_03
RFC 7231
```

Sparse 通常更可靠。

------

# 四、Sparse Retrieval 的缺点

最大的问题：

> **它不真正理解语义。**

例如 Query：

```text
怎么终止正在执行的任务？
```

文档写的是：

```text
Cancellation propagates to child tasks.
```

可能一个关键词都对不上。

BM25 很可能表现不好。

再比如：

```text
Query:
数据库怎么长期保存数据？
```

Document：

```text
PostgreSQL provides durable persistence.
```

字面匹配不强，但语义高度相关。

这就是 Dense Retrieval 的用武之地。

------

# 五、Dense Retrieval 是什么

Dense Retrieval（稠密检索）通过 Embedding Model：

```text
Text
↓
Embedding
↓
Dense Vector
```

例如：

```text
[0.213, -0.148, 0.726, ...]
```

绝大多数维度都有值，所以叫：

> Dense Vector（稠密向量）

然后根据：

```text
Cosine Similarity
Dot Product
```

计算 Query 和 Chunk 的语义相似度。

------

# 六、Dense Retrieval 最擅长什么

## 1. 同义表达

Query：

```text
任务如何被终止？
```

Document：

```text
Cancellation stops execution.
```

字不同，但意思接近。

Dense 很容易匹配。

------

## 2. 自然语言问题

例如：

```text
为什么 Agent 超时以后子任务还在运行？
```

可能知识库没有一模一样的句子。

Dense 可以找到：

```text
Cancellation propagation
child task lifecycle
timeout cleanup
```

相关内容。

------

## 3. 模糊意图

例如：

```text
怎么避免模型回答过期信息？
```

可能检索到：

```text
knowledge freshness
index version
document update
RAG
```

这种语义泛化正是 Dense 的优势。

------

# 七、Dense Retrieval 的缺点

## 1. Exact Match 不稳定

Query：

```text
P1_03_MVP
```

Dense Embedding 可能不知道它是什么。

它可能把：

```text
P1_02
P1_04
Phase1 MVP
```

都认为挺相似。

BM25 则：

> 就找 P1_03_MVP。

------

## 2. 专有词可能被“语义化过头”

比如：

```text
AgentState
```

Dense 可能返回：

```text
runtime state
session state
task state
agent context
```

理论相关，但你真正要找的是：

```text
AgentState class
```

Sparse 更精准。

------

## 3. Embedding Model 有领域偏差

Embedding 模型如果不熟悉：

```text
内部缩写
公司术语
特殊代码标识符
```

Dense Recall 可能明显下降。

------

# 八、所以 Sparse 和 Dense 不是竞争关系

可以记成：

| 能力       | Sparse / BM25 | Dense      |
| ---------- | ------------- | ---------- |
| 精确关键词 | 强            | 中         |
| 错误码     | 很强          | 弱         |
| 类名 / API | 很强          | 中         |
| 数字 / ID  | 强            | 弱         |
| 同义词     | 弱            | 强         |
| 自然语言   | 中            | 强         |
| 语义泛化   | 弱            | 强         |
| 内部专有词 | 强            | 取决于模型 |
| 模糊问题   | 弱            | 强         |

因此现代 RAG 很常见：

```text
Dense + BM25
```

------

# 九、Hybrid Search 是怎么工作的

典型结构：

```text
                   Query
                     │
           ┌─────────┴─────────┐
           ↓                   ↓
         Dense               BM25
       Retriever           Retriever
           ↓                   ↓
      Dense Top-K          BM25 Top-K
           └─────────┬─────────┘
                     ↓
                   Fusion
                     ↓
                 Final Top-K
```

问题就来了：

> 两路结果怎么融合？

主要分两大类：

### Score Fusion（分数融合）

和：

### Rank Fusion（排名融合）

------

# 十、第一种：直接加分数，可以吗？

假设：

Dense：

```text
Document A = 0.91
Document B = 0.85
Document C = 0.79
```

BM25：

```text
Document A = 13.8
Document D = 11.2
Document C = 7.5
```

你不能简单：

```text
final_score = dense_score + bm25_score
```

因为：

```text
Dense:
0 ~ 1

BM25:
可能 0 ~ 20
甚至更大
```

如果直接加：

> BM25 会把 Dense 完全淹没。

所以 Score Fusion 最关键的问题就是：

> **Score Calibration（分数校准）**

------

# 十一、Score Normalization

一种方法是先 Normalize（归一化）。

比如：

### Min-Max Normalization

```text
normalized =
(score - min)
/
(max - min)
```

都映射到：

```text
0 ~ 1
```

然后：

```text
final_score
=
α × dense_score
+
β × bm25_score
```

例如：

```text
0.6 × dense
+
0.4 × bm25
```

------

# 十二、Weighted Score Fusion

这就是：

**Weighted Score Fusion（加权分数融合）**

公式：

```text
Score(d)
=
α × DenseNormalized(d)
+
(1 - α) × BM25Normalized(d)
```

例如：

```text
α = 0.7
```

意味着：

> 更相信 Dense。

这种方法优势是：

```text
直观
可调
可以针对业务优化
```

但缺点非常明显：

> Normalization 和权重非常敏感。

------

# 十三、为什么 Score Normalization 没那么简单

假设某次查询 Dense：

```text
0.89
0.88
0.87
```

另一次：

```text
0.89
0.50
0.20
```

两次：

```text
Top1 都是 0.89
```

但意义完全不一样。

第一种：

> 三个候选都差不多。

第二种：

> 第一名明显领先。

所以单纯 Min-Max 可能扭曲真实分布。

再加上 BM25：

```text
不同 Query 的 BM25 score 分布也不稳定
```

因此直接做跨 Retriever 分数融合并没有想象中简单。

------

# 十四、于是出现 Rank Fusion

Rank Fusion（排名融合）干脆说：

> 我不相信两个 Retriever 的原始 Score，只相信它们各自给出的排序。

最经典就是：

> **RRF（Reciprocal Rank Fusion，倒数排名融合）**

这正是你项目现在使用的重要策略之一。

------

# 十五、RRF 怎么算

公式：

```text
RRF(d)
=
Σ 1 / (k + rank_i(d))
```

其中：

```text
rank_i(d)
```

表示 Document d 在第 i 个 Retriever 中的排名。

`k` 是平滑常数。

经典例子经常：

```text
k = 60
```

但具体值依实现和实验而定。

------

# 十六、举一个 RRF 例子

Dense：

```text
Rank 1: A
Rank 2: B
Rank 3: C
Rank 4: D
```

BM25：

```text
Rank 1: C
Rank 2: A
Rank 3: E
Rank 4: F
```

A：

```text
Dense Rank = 1
BM25 Rank = 2
```

因此：

```text
A =
1/(k+1)
+
1/(k+2)
```

C：

```text
Dense Rank = 3
BM25 Rank = 1
```

因此：

```text
C =
1/(k+3)
+
1/(k+1)
```

A 和 C 都会得到比较高的最终分数。

为什么？

> 因为两个 Retriever 都认为它们重要。

------

# 十七、RRF 最大优势

## 不需要原始 Score 在同一个尺度

Dense：

```text
0.83
```

BM25：

```text
17.2
```

无所谓。

RRF 只看：

```text
Rank
```

于是天然避开：

> Score Calibration 问题。

这是 RRF 特别适合异构 Retriever 的原因。

------

# 十八、RRF 的第二个优势：鲁棒

假设 Dense 认为：

```text
A Rank 1
```

BM25 也认为：

```text
A Rank 3
```

A 最终通常会非常稳定地进入前排。

也就是说：

> 多个 Retriever 对同一候选达成共识时，RRF 会奖励这种共识。

------

# 十九、RRF 的缺点

面试官很容易追问：

> RRF 这么好，那为什么不用 RRF 解决所有问题？

因为 RRF 会丢掉 Score Magnitude（分数幅度）。

例如：

Dense：

```text
A = 0.99
B = 0.70
```

和：

```text
A = 0.71
B = 0.70
```

在 RRF 看来：

```text
A Rank 1
B Rank 2
```

完全一样。

但实际上：

第一种 A 比 B 强很多。

第二种几乎没差。

RRF 看不到这个信息。

------

# 二十、RRF 还有一个问题：Retriever 质量不等

假设：

```text
Dense 很强
BM25 很差
```

普通 RRF 可能仍然给两者类似的影响力。

于是会出现：

> 弱 Retriever 污染强 Retriever 的结果。

这时候可以考虑：

**Weighted RRF（加权 RRF）**

例如：

```text
Score(d)
=
2.0 / (k + dense_rank)
+
1.0 / (k + bm25_rank)
```

表示：

> Dense 权重更高。

------

# 二十一、Weighted RRF 和 Weighted Score Fusion 不一样

这是个容易混的点。

### Weighted Score Fusion

融合的是：

```text
Dense Score
+
BM25 Score
```

需要解决：

```text
Score Scale
Normalization
Calibration
```

------

### Weighted RRF

融合的是：

```text
Dense Rank
+
BM25 Rank
```

不关心原始 Score。

------

# 二十二、Hybrid Search 还有一种模式：Candidate Union

例如：

```text
Dense Top 50
+
BM25 Top 50
↓
去重
↓
最多 100 个候选
↓
Cross Encoder Reranker
↓
Top 5
```

此时 Hybrid 的作用主要是：

> **扩大 Candidate Recall（候选召回率）。**

最终排序不是交给 RRF，而是：

> 交给 Reranker。

这也是很常见的生产方案。

------

# 二十三、所以现代 RAG 可能有两种典型方案

## 方案 A

```text
Dense
+
BM25
↓
RRF
↓
Top K
↓
LLM
```

优点：

```text
简单
便宜
快速
效果稳定
```

------

## 方案 B

```text
Dense
+
BM25
↓
Candidate Union / RRF
↓
Top 30
↓
Cross Encoder
↓
Top 5
↓
LLM
```

通常质量更强。

代价：

```text
Latency ↑
Compute ↑
Complexity ↑
```

------

# 二十四、一个重要区别：Fusion 和 Reranking

不要混淆。

**Fusion（融合）**解决：

> 多个 Retriever 的结果怎么合并？

例如：

```text
Dense
BM25
↓
RRF
```

------

**Reranking（重排序）**解决：

> 已经召回的一批候选，谁和 Query 真正最相关？

例如：

```text
Candidates
↓
Cross Encoder
↓
重新排序
```

因此：

> RRF 不是 Cross Encoder Reranker 的同义词。

------

# 二十五、为什么 Hybrid Search 经常能提高 Recall

假设 Ground Truth 是文档 A。

Query：

```text
怎么停止后台运行的 Agent？
```

文档写：

```text
Cancellation propagates through the runtime.
```

Dense：

```text
命中 A
```

BM25：

```text
可能不命中
```

------

另一个 Query：

```text
LOCAL_AGENT_LLM_BACKEND
```

Dense：

```text
不一定命中正确配置文档
```

BM25：

```text
精准命中
```

所以：

```text
Dense ∪ BM25
```

覆盖了两种失败模式。

Hybrid 的核心价值不是：

> 两个 Retriever 一定比一个聪明。

而是：

> **两个 Retriever 的 Error Pattern（错误模式）不同。**

这句话非常适合面试。

------

# 二十六、什么时候 Hybrid 反而可能变差

不是 Hybrid 一定更好。

例如：

```text
Dense Recall 已经非常高
BM25 经常返回大量关键词噪声
```

融合以后：

```text
Noise ↑
NDCG ↓
MRR ↓
```

或者：

```text
BM25 高排名垃圾结果
↓
RRF 给了它额外权重
↓
挤掉 Dense 的优质结果
```

所以：

> Hybrid Search 必须通过 Evaluation 验证，而不能只凭架构感觉。

------

# 二十七、你这里特别应该记 Recall@K、MRR、NDCG 的分工

假设我们比较：

```text
Dense Only
BM25 Only
Dense + BM25 + RRF
```

可以看：

### Recall@K

回答：

> Ground Truth 有没有被找到？

主要衡量：

```text
召回覆盖能力
```

------

### MRR

回答：

> 第一个正确答案排得够不够前？

------

### NDCG

回答：

> 多个相关结果的整体排序质量怎么样？

所以可能出现：

```text
Hybrid Recall@10 ↑
但是 NDCG@10 ↓
```

意味着：

> 候选覆盖更多了，但排序质量反而下降。

此时可能需要 Reranker。

------

# 二十八、结合你的真实项目

你的项目当前已经实际走过：

```text
Dense Retrieval
+
BM25
+
RRF
```

并且有 Retrieval / Ranking Evaluation。

因此面试时这是一个非常自然的回答链路：

> 我们没有完全依赖 Dense Retrieval，因为知识库包含大量技术文档，里面有类名、API、专有词等精确匹配需求。Dense 对语义问题比较强，而 BM25 能补充关键词和专有标识符召回，所以使用 Hybrid Retrieval。由于 Dense similarity score 和 BM25 score 不在同一分数空间，直接做加权求和需要额外校准，因此采用 RRF 基于排名进行融合，然后再通过 Recall@K、MRR 和 NDCG 验证融合是否真正带来收益。

这一段特别适合你之后整理成项目面试材料。

------

# 二十九、面试官可能继续问：为什么选择 RRF，而不是分数归一化？

你可以回答：

> Dense 和 BM25 的评分机制不同，而且不同 Query 下 Score Distribution 也会变化。如果直接加权，需要设计 Normalization 和 Calibration。RRF 只依赖各 Retriever 内部的排名，因此对不同 Score Scale 更鲁棒，实现也比较简单，适合作为 Hybrid Retrieval 的稳定基线。当然代价是它丢掉了原始 Score 的置信幅度，如果后续评估发现排序能力不足，可以增加 Weighted RRF 或 Cross-Encoder Reranker。

这是很完整的答案。

------

# 三十、面试官再追：RRF 里的 k 有什么作用？

RRF：

```text
1 / (k + rank)
```

`k` 控制：

> 不同排名之间分数差异有多敏感。

`k` 小：

```text
Rank 1 和 Rank 10
差距比较明显
```

更加偏重头部。

`k` 大：

```text
排名之间差异被压平
```

多个 Retriever 的共识更重要。

你不用在面试里死背：

```text
一定 k = 60
```

更好回答：

> 60 是经典 RRF 中常见的经验参数，但在具体系统里应该通过固定 Evaluation Dataset 做参数验证。

------

# 三十一、还有一种更高级的 Hybrid：Query-dependent Fusion

目前：

```text
Dense 权重 = 固定
BM25 权重 = 固定
```

但实际上 Query 类型不同。

比如 Query：

```text
ERR_49218
```

明显应该：

```text
BM25 Weight ↑
```

Query：

```text
为什么任务取消以后还有子任务没有退出？
```

明显：

```text
Dense Weight ↑
```

于是可以做：

**Query-dependent Routing / Adaptive Fusion（按查询动态融合）**

例如：

```text
Query
↓
Query Classifier
↓
Exact-term Query?
    ↓ yes
BM25 weight ↑

Semantic Query?
    ↓
Dense weight ↑
```

这是 Advanced RAG 的一个方向。

现在知道概念即可。

------

# 三十二、完整心智模型

你可以记这张：

```text
                     Query
                       │
          ┌────────────┴────────────┐
          │                         │
       Sparse                     Dense
      BM25 / TF                  Embedding
          │                         │
    Exact Match                Semantic Match
          │                         │
          └────────────┬────────────┘
                       │
                    Hybrid
                       │
          ┌────────────┴────────────┐
          │                         │
     Score Fusion              Rank Fusion
          │                         │
Normalization                  RRF
+ Weighted Sum             Weighted RRF
          │                         │
          └────────────┬────────────┘
                       ↓
                 Candidate Set
                       ↓
                   Reranker
                       ↓
                    Top K
                       ↓
                     LLM
```

------

# 三十三、30 秒面试答案

> Sparse Retrieval 以 BM25 为代表，擅长关键词、错误码、API、类名和专有名词等精确匹配，但对同义表达和自然语言语义理解较弱。Dense Retrieval 通过 Embedding 做语义匹配，更适合自然语言问题和同义表达，但对特殊标识符和精确字符串可能不稳定。因此实际 RAG 中经常使用 Hybrid Search。融合可以做 Score Fusion，对 Dense 和 BM25 分数归一化以后加权，也可以做 Rank Fusion，例如 RRF，只使用两个 Retriever 的排名，避免不同评分空间的校准问题。Hybrid 是否真正有效还需要通过 Recall@K、MRR、NDCG 等指标验证。

------

# 三十四、建议深入学习的关键词

优先掌握：

- **BM25**
- **TF-IDF**
- **Dense Retrieval**
- **Sparse Retrieval**
- **Hybrid Search**
- **Score Normalization**
- **Score Calibration**
- **Weighted Score Fusion**
- **Rank Fusion**
- **RRF**
- **Weighted RRF**
- **Candidate Union**
- **Cross-Encoder Reranker**
- **Query-dependent Fusion**

其中对你当前项目和面试 ROI 最高的是：

> **BM25 为什么能补 Dense → 为什么不能直接加两类 Score → RRF 如何解决 → RRF 有什么缺陷 → 为什么后面还可能需要 Reranker。**

把这条因果链讲顺，Hybrid Retrieval 这一块基本就过关了。