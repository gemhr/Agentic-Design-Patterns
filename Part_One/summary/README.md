# Mini LocalAgent Orchestrator

这个 demo 用一个小型编排器串联第一章七种 Agentic Design Patterns：

1. Routing
2. Planning
3. Tool Use
4. Reflection
5. Parallelization
6. Prompt Chaining
7. Multi-Agent Collaboration

## 放置路径

建议复制到你的项目：

```text
D:\PythonProject\Agentic-Design-Patterns\Part_One\summary\mini_localagent_orchestrator.py
D:\PythonProject\Agentic-Design-Patterns\Part_One\summary\sample_note.txt
```

它会通过：

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

自动把项目根目录加入 `sys.path`，然后导入：

```python
from common.llm_client import AsyncLLMClient
```

## 环境变量示例

公司内网 Qwen：

```powershell
$env:LLM_PROVIDER="qwen"
$env:LLM_BASE_URL="http://你的内网地址:8001/v1/chat/completions"
$env:LLM_MODEL="你的模型名"
$env:LLM_TRUST_ENV="false"
$env:LLM_MAX_CONNECTIONS="3"
$env:LLM_MAX_KEEPALIVE_CONNECTIONS="0"
```

家里 DeepSeek：

```powershell
$env:LLM_PROVIDER="deepseek"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL="deepseek-chat"
$env:LLM_API_KEY="你的 API Key"
$env:LLM_VERIFY_SSL="true"
$env:LLM_TRUST_ENV="false"
```

## 运行示例

### 1. 普通知识解释

```powershell
uv run python Part_One\summary\mini_localagent_orchestrator.py --task "解释 Agent Routing 是什么，并说明工程里为什么需要它"
```

### 2. Python 代码审查

```powershell
uv run python Part_One\summary\mini_localagent_orchestrator.py --code-file Part_One\C3_Parallelization\demo2.py
```

### 3. 简单文本文件总结

```powershell
uv run python Part_One\summary\mini_localagent_orchestrator.py --text-file Part_One\summary\sample_note.txt
```

### 4. 只看最终答案，不看 Trace

```powershell
uv run python Part_One\summary\mini_localagent_orchestrator.py --task "解释 Reflection 在 Agent 中的作用" --no-trace
```

## 推荐学习方式

先打开 Trace，看每一段输出来自哪个模式：

```text
[1. Routing]
[2. Planning + 6. Prompt Chaining]
[3. Tool Use]
[4. Parallelization + 7. Multi-Agent Collaboration]
[5. Reflection]
Final Answer
```

第一章最终可以浓缩成一句话：

> Agent 工程的核心，是把 Routing、Planning、Tool Use、Reflection、Parallelization、Prompt Chaining、Multi-Agent Collaboration 这些模式，按任务需要组合成稳定的执行链路。
