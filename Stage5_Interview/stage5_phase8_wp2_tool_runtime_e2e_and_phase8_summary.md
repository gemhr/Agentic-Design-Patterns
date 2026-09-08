# Stage5-Phase8-WP2 + Phase8 整体学习/面试总结

## 1. 本 WP 解决了什么问题

WP1 / WP1N 已经解决：

```text
自然语言
↓
DeepSeek Native Function Calling
↓
Tool Selection
↓
Argument Construction
↓
Typed Validation
```

但到这里仍然只能说明：

> Agent “理论上会调用 Tool”。

还不能证明：

> 一个普通用户真的只输入业务语言，就可以安全地调用真实 Tool、产生真实副作用，并与 Governance / HITL / Execution 完整闭环。

所以 WP2 的目标不是再增加 Tool Framework，而是构造一个：

```text
安全
简单
可真实执行
可人工验证
有读写副作用层级
```

的小型 Tool Portfolio。

最终选用了：

```text
workspace_read_file
workspace_write_file
complex_workflow_simulator
```

分别覆盖：

```text
Read-only
Controlled Idempotent Write
High-risk Non-idempotent + HITL
```

这样就能验证 Phase8 的完整能力梯度。

WP2 的核心意义：

> **把“Tool Calling 能力”从模型协议层能力，提升成真正的 Runtime Production Path。**

------

# 2. Phase8 最终真实架构

最终主链：

```text
User Natural-language Intent
        ↓
AgentRouter
        ↓
Selected Model Adapter
        ↓
Capability Detection
        ↓
DeepSeek Native Tool Selection
        ↓
NativeToolCall
        ↓
ToolRegistry
        ↓
ToolAdapter.build_invocation()
        ↓
Typed Validation
        ↓
Immutable ToolInvocation
        ↓
ToolAdapter.spec_for()
        ↓
ToolGovernanceService
        ↓
ALLOW / DENY / APPROVAL_REQUIRED
        ↓
ToolApprovalController
        ↓
Execution Claim / CAS
        ↓
ToolExecutionService
        ↓
Tool Result
        ↓
role=tool + tool_call_id
        ↓
DeepSeek Final Continuation
```

如果当前 Model 不支持 Native Function Calling：

```text
Capability Detection
↓
Non-native existing safe Tool path
```

而不是强行发送 `tools`。

这意味着 Phase8 最终真正实现了：

> **Model 负责理解和表达业务意图，Runtime 负责把意图变成可信执行。**

------

# 3. WP2 Tool Portfolio 为什么这样选

## 3.1 workspace_read_file

用于证明：

```text
Natural-language
→ Tool Selection
→ READ_ONLY
→ LOW
→ ALLOW
→ real execution
```

这是最低风险 Tool。

业务参数只有：

```text
path
```

例如：

```text
project_note.txt
```

用户不需要知道：

```text
Demo Root
Absolute Path
Risk
Authorization
Tool Policy
```

------

## 3.2 workspace_write_file

用于证明：

```text
Tool 产生真实 Side Effect
```

但又尽量控制风险。

设计成：

```text
set / overwrite exact content
```

而不是：

```text
append
```

因为：

```text
write(path="a.txt", content="hello")
```

无论执行一次还是两次：

```text
最终状态相同
```

所以它天然具备：

```text
IDEMPOTENT
```

语义。

最终 Runtime Facts：

```text
LOCAL_STATE_MUTATION
+
IDEMPOTENT
+
MEDIUM
+
ALLOW
```

------

## 3.3 为什么不实现 delete_file

没有必要。

因为 Phase8 已经有：

```text
complex_workflow_simulator
```

覆盖：

```text
HIGH
APPROVAL_REQUIRED
NON-IDEMPOTENT
HITL
```

如果再增加：

```text
workspace_delete_file
```

反而引入真实 destructive filesystem side-effect。

收益很低，风险更高。

这是典型的：

> **用最小 Portfolio 覆盖最大工程语义。**

------

# 4. Restricted Demo Workspace 为什么必要

如果直接设计：

```text
read_file(path)
write_file(path)
```

并允许读取任意：

```text
C:\
D:\
用户目录
Repo
系统目录
UNC
```

那 Agent 只要 Tool Selection 或参数生成错误，就可能产生：

```text
Arbitrary Filesystem Access
```

因此 WP2 固定了：

```text
D:\PythonProject\Local_Agent\data\demo_workspace
```

作为：

```text
Restricted Demo Root
```

File Tool 只能访问该目录内部。

------

# 5. Workspace Path Security

这是 WP2 最重要的安全知识点之一。

不能简单写：

```python
if ".." in path:
    reject
```

因为：

```text
Path Traversal
```

远不止这一种形式。

最终核心思想：

```text
root = resolve(demo_workspace)

candidate = resolve(root / user_relative_path)

candidate 必须仍位于 root 内
```

即：

> **Canonicalization First, Authorization Second.**

中文可以理解：

> 先把路径解析成真正指向的位置，再判断它是否属于允许的根目录。

------

# 6. 为什么仅检查 `..` 不够

例如：

```text
a/../../outside.txt
```

显然可以逃逸。

还有：

```text
absolute path
C:\Windows\...
```

以及：

```text
UNC
\\server\share
```

Windows 还有：

```text
drive-relative path
device path
extended path
junction
symlink
```

所以必须基于：

```text
resolved path containment
```

而不是字符串过滤。

------

# 7. Symlink / Junction Escape

例如：

```text
demo_workspace/
  external_link/
```

表面上：

```text
external_link/a.txt
```

仍在 Workspace 路径下。

但如果：

```text
external_link
→ C:\outside
```

那么真实目标已经逃出 Root。

所以最终检查：

```text
resolve(candidate)
```

之后再次做 Root containment。

WP2 deterministic tests 真实覆盖了 resolved link escape。

------

# 8. 为什么这不是 Sandbox

当前能力只能称为：

```text
Restricted Filesystem Boundary
```

不能叫：

```text
Generic Sandbox
```

因为没有实现：

```text
Container isolation
Process isolation
Syscall isolation
Network isolation
CPU / Memory isolation
Generic ACL
```

它解决的是：

> **Demo Tool 不能越过固定文件根目录。**

而不是：

> **运行任意不可信代码。**

因此 Final Gate 正确把：

```text
fixed Demo Root containment is not a generic sandbox
```

作为 Accepted Limitation。

------

# 9. Read Tool Runtime Facts

`workspace_read_file`：

```text
Side Effect:
NONE

Idempotency:
READ_ONLY

Risk:
LOW

Decision:
ALLOW
```

这些不是 Model 生成的。

模型只提出：

```text
我要读取 project_note.txt
```

随后：

```text
ToolAdapter
+
ToolPolicyCatalog
+
ToolGovernanceService
```

计算真正的 Runtime Facts。

------

# 10. Write Tool Runtime Facts

`workspace_write_file`：

```text
Side Effect:
LOCAL_STATE_MUTATION

Idempotency:
IDEMPOTENT

Risk:
MEDIUM

Decision:
ALLOW
```

为什么 overwrite 可以算 idempotent？

因为：

```text
F(F(state, input), input)
=
F(state, input)
```

例如：

```text
把 result.txt 设置成 "phase8 demo passed"
```

执行两遍：

最终仍然是：

```text
phase8 demo passed
```

------

# 11. Append 为什么不同

如果设计：

```text
append("hello")
```

执行一次：

```text
hello
```

重试：

```text
hellohello
```

所以：

```text
append
```

天然更接近：

```text
NON_IDEMPOTENT
```

如果未来需要 Append：

应该重新评估：

```text
Retry semantics
Idempotency key
Risk
Approval
```

而不是复用 overwrite 的 policy。

------

# 12. Tool Schema 为什么保持极小

Read Schema：

```text
path
```

Write Schema：

```text
path
content
```

没有：

```text
workspace_root
risk
approval
side_effect
idempotency
timeout
execution_claim
```

原因仍然是：

> **Function Schema 是 Model Intent Contract，而不是 Runtime Control Contract。**

------

# 13. Tool Portfolio 与 Tool Discovery 的关系

最终 Registry 中可能同时存在：

```text
list_files
workspace_read_file
workspace_write_file
get_system_status
complex_workflow_simulator
```

这就产生一个实际问题：

> Tool 越多，Description 越重要。

比如：

```text
list_files
```

和：

```text
workspace_read_file
```

必须让 Model 清楚：

```text
一个用于列出目录
一个用于读取具体文件
```

不能只靠 Tool Name 猜。

Final Gate 甚至修复了一处：

```text
workspace description test
```

原来的断言属于恒真断言，后来改成真正检查它与 `list_files` 的语义区分。

------

# 14. Real Read E2E

真实用户输入：

```text
读取 demo workspace 里的 project_note.txt，
告诉我里面记录了什么。
```

用户没有写：

```text
workspace_read_file
```

也没有写：

```json
{"path":"project_note.txt"}
```

真实路径：

```text
User
↓
DeepSeek
↓
workspace_read_file
↓
path = project_note.txt
↓
LOW / ALLOW
↓
TOOL_STARTED
↓
TOOL_COMPLETED
↓
Native Tool Result
↓
Final Answer
↓
RUN_COMPLETED
```

并且使用：

```text
deepseek-v4-flash
```

真实生产 FastAPI / Coordinated Runtime。

------

# 15. Real Write E2E

用户自然语言：

```text
把 “phase8 demo passed”
写入 demo workspace 的 result.txt
```

最终：

```text
Selected Tool:
workspace_write_file

Governance:
MEDIUM / ALLOW

Tool Execution:
PASS

Actual File:
result.txt

Actual Content:
phase8 demo passed
```

这证明：

> Tool Calling 已经不只是“模型返回了正确函数名”，而是真的产生了受治理的本地副作用。

------

# 16. Real HITL E2E

这是 Phase8 最重要的闭环。

用户表达：

```text
对 demo-resource 中 item-1 做一次增加 1 的真实模拟操作，
如果需要审批就按系统规则处理。
```

用户没有：

```text
complex_workflow_simulator
NON_IDEMPOTENT_SIMULATION
operation_id
完整 JSON
```

模型最终选择：

```text
complex_workflow_simulator
```

Runtime：

```text
ToolAdapter
↓
HIGH
↓
APPROVAL_REQUIRED
↓
WAITING_FOR_APPROVAL
```

------

# 17. Approve Path

真实：

```text
WAITING_FOR_APPROVAL
↓
HTTP APPROVE
↓
ToolApprovalController
↓
CAS / Execution Claim
↓
ToolExecutionService
↓
Execution Count = 1
↓
RUN_COMPLETED
```

这证明：

```text
Model Selection
```

和：

```text
Human Authorization
```

是两个完全独立的 Authority。

------

# 18. Reject Path

真实：

```text
WAITING_FOR_APPROVAL
↓
HTTP REJECT
↓
Execution Count = 0
```

也就是说：

> Model 即使已经选择 Tool 并构造好参数，人类仍然可以阻止真正 Side Effect。

这就是 HITL 的真正意义。

------

# 19. Phase8 最终解决的核心问题

最开始：

```text
User
↓
自己知道 Tool
↓
自己知道 enum
↓
自己构造 JSON
↓
Runtime execute
```

最终：

```text
User
↓
只表达业务 Intent
↓
Model:
Tool Selection
Argument Proposal
↓
Runtime:
Validation
Governance
Approval
Execution
```

因此：

> **User 不再充当 Tool Router。**

这就是 Phase8 Final Gate 判定 PASS 的核心标准。

------

# 20. Phase8 最终 Owner Map

| Responsibility           | Owner                             |
| ------------------------ | --------------------------------- |
| User Intent              | User                              |
| Semantic Tool Selection  | Model                             |
| Argument Proposal        | Model                             |
| Native Function Protocol | DeepSeek Provider Layer           |
| Tool Registry            | ToolRegistry                      |
| Tool Binding             | ToolRegistration                  |
| Typed Validation         | ToolAdapter                       |
| Side-effect Fact         | ToolAdapter.spec_for()            |
| Idempotency Fact         | ToolAdapter.spec_for()            |
| Risk / Governance        | ToolGovernanceService             |
| Human Approval           | ToolApprovalController            |
| Execution Claim          | Runtime                           |
| Tool Execution           | ToolExecutionService              |
| Runtime Identity         | Local Runtime                     |
| Provider Correlation ID  | Provider                          |
| Workspace Boundary       | Workspace Adapter / path resolver |

------

# 21. 为什么这个 Owner Map 很重要

Agent 系统最容易出现的问题就是：

```text
一个 Model 输出
```

同时被当成：

```text
Intent
+
Validation
+
Authorization
+
Risk Decision
+
Execution
```

这样所有安全边界都混在一起。

Phase8 最终拆成：

```text
Semantic Authority
≠
Validation Authority
≠
Governance Authority
≠
Approval Authority
≠
Execution Authority
```

这就是一个可信 Agent Runtime 和 Demo Agent 最大的区别之一。

------

# 22. Truth / Completion Boundary

## 已真实实现

```text
Natural-language Tool Use
DeepSeek Native Function Calling
Capability-aware routing
Typed ToolInvocation
Bounded Repair
Validation-before-Governance
Restricted Workspace Read
Restricted Workspace Write
Governance Integration
HITL Integration
Native Tool Result Continuation
```

------

## 已真实 E2E

### Read

```text
REAL_READ_TOOL_E2E = PASS
```

### Write

```text
REAL_WRITE_TOOL_E2E = PASS
```

### HITL Approve

```text
PASS
Execution = exactly once
```

### HITL Reject

```text
PASS
Execution = zero
```

------

## 最终 Regression

Targeted：

```text
246 passed
12 subtests passed
```

Full:

```text
3231 passed
12 failed
```

12 个失败全部是既有 baseline：

```text
Phase8 新增失败 = 0
```

------

# 23. Accepted Limitations

Phase8 最终接受：

```text
DeepSeek-only Native Function Calling

Thinking Tool Calling disabled

Native Tool Streaming disabled

0/1 Tool Call only

Demo Workspace ≠ Generic Sandbox

Approval 无 Authentication / RBAC

没有 Durable Pause / Resume
```

这些不会阻碍：

```text
Local Tool Use
```

主目标。

------

# 24. Real Bad Case 1 — Arbitrary Filesystem Access

### Truth Source

```text
HYPOTHETICAL_BAD_CASE
+
DETERMINISTIC_SECURITY_TEST
```

没有证据表明生产中真的发生过越权读取。

它是主动设计的威胁场景。

### Trigger

Model 生成：

```text
..\..\outside.txt
```

或：

```text
C:\Windows\system.ini
```

### Risk

如果直接：

```python
open(root / user_path)
```

可能访问 Root 外部。

### Root Cause

把 Model output 直接当可信路径。

### Fix

```text
resolved path
+
root containment
```

### Regression

Traversal / Absolute / UNC / Link escape tests。

### Knowledge Point

> Path canonicalization 必须先于 authorization。

------

# 25. Real Bad Case 2 — Symlink / Junction Escape

### Truth Source

```text
DETERMINISTIC_SECURITY_TEST
```

### Trigger

Root 内路径实际上指向 Root 外。

### Risk

字符串看起来合法，但真实访问越界。

### Root Cause

只校验 lexical path，不校验 resolved target。

### Fix

对 resolved candidate 做 containment。

### Knowledge Point

> Filesystem authorization 应基于最终 resolved object，而不是用户输入字符串。

------

# 26. Final Gate Discovery — 过期架构文档

### Truth Source

```text
CODEX_FINAL_GATE_DISCOVERY
```

Final Gate 发现 architecture document 仍描述：

```text
无 approval endpoint
```

但实际 Phase7 已经具备：

```text
run-scoped controller
HTTP approval command
fail-closed approval semantics
```

### Risk

Documentation drift（文档漂移）。

开发人员后续可能根据错误架构文档做错误决策。

### Fix

Final Gate 修正文档。

### Knowledge Point

> Architecture Documentation 也需要和 Runtime Truth 一起接受 Gate。

------

# 27. Final Gate Discovery — 恒真测试

### Truth Source

```text
CODEX_FINAL_GATE_DISCOVERY
```

Workspace description 的一个测试原本属于：

```text
永远成立
```

的断言。

实际上并没有验证：

```text
workspace_read_file
```

和：

```text
list_files
```

描述是否真的可区分。

### Fix

改成真正检查二者语义区分。

### Knowledge Point

> Green Test 不等于有效 Test。

------

# 28. 名词 / 概念速览

### Tool Portfolio（工具组合）

为 Agent 提供的一组具有不同能力与风险等级的 Tool。

### Restricted Workspace（受限工作区）

Tool 只能在固定 Root 内访问数据。

### Path Traversal（路径穿越）

利用 `..` 等方式逃离允许目录。

### Canonicalization（规范化）

将路径转换成真实、标准的位置表示。

### Root Containment（根目录包含校验）

确保最终路径仍属于允许的 Root。

### Symlink（符号链接）

路径指向另一个文件或目录的链接。

### Junction（目录联接）

Windows 的目录重解析机制之一。

### Idempotent Write（幂等写）

相同输入重复执行不会改变最终结果。

### Arbitrary Filesystem Access（任意文件系统访问）

可以访问 Runtime 未授权的任意磁盘位置。

### Exactly-once Execution（恰好一次执行）

在特定 invocation 语义下保证 Side Effect 不被重复执行。

### Zero-execution Reject（拒绝零执行）

Approval 被拒绝时副作用执行次数必须为 0。

### Production-path E2E（生产路径端到端）

不是直接调用函数，而是通过真实 Runtime 主入口完成测试。

------

# 29. 工程方法类问答

## Q1：为什么 Phase8 还要做 WP2？

因为 Tool Selection 单测通过不能证明 Runtime 能真实安全执行 Tool。

------

## Q2：为什么用文件 Tool 做 Demo？

文件读写简单、结果可人工验证，同时可以覆盖 READ_ONLY 和 STATE_MUTATION 两种语义。

------

## Q3：为什么固定 Demo Root？

限制 Model 参数错误造成的 blast radius（影响范围）。

------

## Q4：为什么不允许 arbitrary path？

Agent 的 Model output 本身是不可信输入。

------

## Q5：为什么 overwrite 是 idempotent？

相同 path + content 重复执行最终状态相同。

------

## Q6：为什么不实现 append？

append 的重复执行会重复追加数据，重试语义复杂。

------

## Q7：为什么 Read 是 LOW？

它没有修改状态，并且访问范围被限制在 Demo Root。

------

## Q8：为什么 Write 是 MEDIUM 但可以 ALLOW？

它有本地状态副作用，但范围受限而且是幂等 overwrite；最终结果由现有 Governance policy 决定。

------

## Q9：为什么 Simulator 继续负责 HIGH 场景？

已有高风险 Tool 已经完整覆盖 HITL，没有必要为了 Demo 再制造真实 destructive Tool。

------

## Q10：为什么 Workspace 不叫 Sandbox？

它只限制文件路径，没有隔离进程、系统调用、网络和资源。

------

# 30. 高频面试追问 + 简答

## 1. Agent 为什么不能直接拥有任意文件访问？

因为 Model output 不可信，错误选择或 Prompt Injection 都可能扩大影响范围。

------

## 2. 你们怎么防目录穿越？

Resolve 最终路径后检查它是否仍在固定 Root 内。

------

## 3. 只判断 `..` 不够吗？

不够，Absolute path、UNC、symlink/junction 都可能绕过。

------

## 4. 怎么防 symlink escape？

对最终 resolved target 再做 Root containment。

------

## 5. Write Tool 为什么没有审批？

当前 Policy 对受限且幂等的本地 overwrite 判为 MEDIUM / ALLOW；审批仍由 Governance 决定，不由 Tool 自己决定。

------

## 6. 那 Model 可以说“这是 LOW Risk”吗？

可以说，但 Runtime 不信。

------

## 7. Tool 的 Risk 从哪来？

来自 Adapter spec 和 Governance policy。

------

## 8. 为什么不把 Approval 放进 Tool arguments？

Approval 是 Runtime Authority，不是业务参数。

------

## 9. 用户自然语言怎么变成 path？

由 DeepSeek Function Calling 生成 `path`，之后 Runtime validation。

------

## 10. Model 输出绝对路径怎么办？

ToolAdapter / Workspace path validation fail closed。

------

## 11. Model 选错 Tool 怎么办？

Provider selection 不是 Authority；错误 Tool 仍然需要经过 Registry、Validation 和 Governance，但当前小型 Portfolio 主要依赖清晰 metadata 降低错误率。

------

## 12. Tool 多起来以后怎么办？

Tool 数量足够大时再考虑 Tool Retrieval / Tool RAG，目前没有规模问题。

------

## 13. 为什么现在还不需要 Tool RAG？

Registry Tool 数量很小，直接传入 Tool definitions 更简单稳定。

------

## 14. Approve 为什么是 exactly-once？

Approval 后仍通过 execution claim 和既有 ToolExecutionService 的 invocation identity 执行，而不是 Approval 回调直接调用 Tool。

------

## 15. Reject 怎么保证零执行？

Reject 状态不会获得 execution claim，所以 ToolExecutionService 不运行。

------

## 16. Approval 是不是模型的一部分？

不是，它是独立 Human Authorization Boundary。

------

## 17. Function Calling 本身安全吗？

不安全，它只是结构化表达 Model intent。

------

## 18. Phase8 最大的安全设计是什么？

把 Model Intent 与 Runtime Authority 分开。

------

## 19. 为什么 Native Function Calling 后仍保留 Governance？

因为选择 Tool 和允许执行 Tool 是完全不同的问题。

------

## 20. 你们有没有真正跑外部模型？

有，Read / Write / HITL E2E 使用真实 `deepseek-v4-flash`。

------

## 21. E2E 是直接 Python 调 Tool 吗？

不是，走真实 FastAPI / Coordinated Runtime / Governance / ToolExecutionService。

------

## 22. 为什么 E2E 这一点重要？

直接函数测试只能证明 Tool 能执行，不能证明 Runtime orchestration 是正确的。

------

## 23. Phase8 最大的 Accepted Limitation 是什么？

Native 目前 DeepSeek-only、0/1 Tool Call，并且 workspace 只是 fixed-root containment，不是通用 Sandbox。

------

## 24. 为什么不顺手做多 Tool？

当前目标是先把单 Tool 的 selection、安全和执行链跑通，multi-tool 会引入 orchestration、并发和部分失败语义。

------

## 25. 为什么下一个 Phase 适合 MCP？

因为 Local Tool 的 Registry、Adapter、Validation、Governance 和 Execution 已经稳定，MCP 可以作为新的 Tool Provider 接入。

------

# 31. MCP Readiness 怎么理解

Final Gate：

```text
MCP_READINESS = READY_WITH_LIMITATIONS
```

不是说：

```text
已经支持 MCP
```

而是：

> 当前 Tool Runtime 已经稳定到不需要为了 MCP 再重写 Tool Execution 核心。

未来 MCP 更可能是：

```text
MCP Server
↓
MCP Tool Metadata
↓
MCP Adapter / Registration
↓
Existing ToolRegistry
↓
ToolInvocation
↓
Governance
↓
Execution
```

而不是：

```text
MCP
↓
第二套完全独立 Runtime
```

------

# 32. 30 秒面试总结

> Phase8 的目标是解决用户必须自己知道 Tool 名和 JSON 的问题。WP1 和 WP1N 完成了 Tool metadata、DeepSeek Native Function Calling、参数校验和 capability-aware routing，WP2 又增加了固定 Demo Workspace 下的 read/write Tool，并通过真实 DeepSeek 和 Coordinated Runtime 做端到端验证。文件 Tool 使用 resolved-path root containment 防止 traversal、absolute path 和 symlink escape；write 使用 overwrite 语义保证幂等。高风险场景继续复用 simulator，通过真实 HITL 验证 Approve 后 exactly-once execution、Reject 后 zero execution。最终 Phase8 Gate PASS，Model 负责语义 Tool Selection，但 Risk、Approval 和 Execution 始终由 deterministic Runtime 控制。

------

# 33. 2 分钟面试总结

> Phase7 完成 Tool Governance 和 HITL 后，我们发现用户实际调用 Tool 时仍然需要自己写 Tool name、execution enum 和完整 JSON，所以 Phase8 的目标是让用户只表达自然语言业务意图。
>
> WP1 先增强 Tool 的 LLM-facing metadata 和参数构造，WP1N 在确定只支持 DeepSeek 后迁移到了 Provider-native Function Calling，并保留 ToolAdapter typed validation、Governance 和 HITL 作为 Runtime Authority。Native 迁移过程中还增加了 capability-aware routing，避免不支持 tools 的 Engine 静默吞参数或失败。
>
> WP2 的重点是做真实生产路径闭环。我们新增了 `workspace_read_file` 和 `workspace_write_file`，都只能访问固定的 `data/demo_workspace`。路径安全不是简单检查 `..`，而是把 Root 和候选路径 resolve 后做 containment，因此 traversal、absolute、UNC 和 symlink/junction escape 都会 fail closed。Write Tool 使用 set/overwrite 语义，同一个 path + content 重复执行最终状态相同，所以 Adapter 将其定义为 idempotent local mutation。
>
> 然后使用真实 `deepseek-v4-flash`、FastAPI 和 Coordinated Runtime 分别验证了 Read 和 Write：用户只说“读这个文件”或者“把这句话写进去”，模型通过 Native Tool Call 选择 Tool 和参数，随后 Runtime 负责 Validation、Governance 和 Execution。
>
> 高风险场景没有再造 destructive file Tool，而是复用 `complex_workflow_simulator`。自然语言会被模型选成 simulator，但 Runtime 判为 HIGH / APPROVAL_REQUIRED；Approve 通过已有 HTTP approval command 和 execution claim 后只执行一次，Reject 则执行次数为 0。
>
> 所以 Phase8 最终形成的边界是：Model 负责 semantic selection 和 argument proposal，Runtime 负责 validation、risk、authorization、approval、idempotency 和 execution。Final Gate PASS，没有新增全量回归失败，MCP readiness 被判断为 READY_WITH_LIMITATIONS，意味着下一阶段可以把 MCP Tool 作为新的 Tool Provider 接入，而不是重做 Tool Runtime。

------

# 34. 最值得记住的六句话

### 1

> **User 不应该充当 Tool Router。**

### 2

> **Model Intent 不等于 Runtime Authority。**

### 3

> **Function Calling 解决“如何表达调用”，Governance 解决“是否允许调用”。**

### 4

> **Filesystem Authorization 必须基于 resolved path，而不是原始字符串。**

### 5

> **Tool E2E 要证明的不是函数能运行，而是整个 Runtime Production Path 能正确运行。**

### 6

> **MCP 应该接入现有 Tool Runtime，而不是重新制造第二套 Tool Runtime。**

------

# 35. 推荐面试材料文件名

```text
docs/interview/stage5_phase8_wp2_tool_runtime_e2e_and_phase8_summary.md
```