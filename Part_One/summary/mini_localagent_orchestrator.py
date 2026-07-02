#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Mini LocalAgent Orchestrator

目标：把第一章七种 Agentic Design Patterns 串成一个小型综合 demo：
1. Routing
2. Planning
3. Tool Use
4. Reflection
5. Parallelization
6. Prompt Chaining
7. Multi-Agent Collaboration

放置建议：
D:\PythonProject\Agentic-Design-Patterns\Part_One\summary\mini_localagent_orchestrator.py

依赖：
- common/llm_client.py 中的 AsyncLLMClient
- 标准库，无额外第三方依赖
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


# ============================================================
# 处理项目内模块导入
# ============================================================
# 当前文件路径：
# Part_One/summary/mini_localagent_orchestrator.py
#
# parents[2] 对应项目根目录：
# Agentic-Design-Patterns/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.llm_client import AsyncLLMClient  # noqa: E402


TaskType = Literal["knowledge", "code_review", "file_summary"]


# ============================================================
# 数据结构
# ============================================================

@dataclass
class RouteResult:
    """Router 的结构化输出。"""

    task_type: TaskType
    need_tool: bool
    need_parallel: bool
    confidence: float
    reason: str


@dataclass
class PlanStep:
    """Planner 输出的单个步骤。"""

    name: str
    pattern: str
    detail: str


@dataclass
class PlanResult:
    """Planner 的结构化输出。"""

    steps: list[PlanStep]
    parallel_jobs: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ToolResult:
    """工具调用结果。"""

    tool_name: str
    ok: bool
    content: str


@dataclass
class AgentResult:
    """并行 Agent 的输出。"""

    agent_name: str
    focus: str
    content: str


@dataclass
class OrchestratorState:
    """整个编排过程中的状态。"""

    user_task: str
    route: RouteResult | None = None
    plan: PlanResult | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    draft_answer: str = ""
    reflection: str = ""
    final_answer: str = ""


# ============================================================
# 通用工具函数
# ============================================================

def extract_json(raw: str) -> dict[str, Any]:
    """
    从模型输出中尽量提取 JSON。

    为什么要单独写：
    - 小 demo 里不引入复杂 parser；
    - 真实模型偶尔会包一层 ```json；
    - Router / Planner 这种结构化环节要尽量稳。
    """

    text = raw.strip()

    # 去掉 Markdown 代码块
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 兜底：截取第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return json.loads(text[start : end + 1])

    raise ValueError(f"无法解析 JSON，原始输出：{raw[:500]}")


def shorten(text: str, limit: int = 6000) -> str:
    """限制上下文长度，避免小 demo 一次性塞太多内容。"""

    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n...[内容过长，已截断]"


def extract_code_from_task(user_task: str) -> str:
    """
    从用户任务中提取 Python 代码。

    支持：
    1. ```python ... ``` 代码块；
    2. 没有代码块时，直接把任务作为代码片段兜底。
    """

    pattern = r"```(?:python|py)?\s*(.*?)```"
    match = re.search(pattern, user_task, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return user_task.strip()


def format_trace(state: OrchestratorState) -> str:
    """把编排轨迹打印出来，方便学习七种模式如何串联。"""

    lines: list[str] = []
    lines.append("\n" + "=" * 72)
    lines.append("Mini LocalAgent Orchestrator Trace")
    lines.append("=" * 72)

    if state.route:
        lines.append("\n[1. Routing]")
        lines.append(
            f"task_type={state.route.task_type}, "
            f"need_tool={state.route.need_tool}, "
            f"need_parallel={state.route.need_parallel}, "
            f"confidence={state.route.confidence}"
        )
        lines.append(f"reason={state.route.reason}")

    if state.plan:
        lines.append("\n[2. Planning + 6. Prompt Chaining]")
        for idx, step in enumerate(state.plan.steps, start=1):
            lines.append(f"{idx}. [{step.pattern}] {step.name} - {step.detail}")

    if state.tool_results:
        lines.append("\n[3. Tool Use]")
        for result in state.tool_results:
            status = "OK" if result.ok else "FAILED"
            lines.append(f"- {result.tool_name}: {status}")
            lines.append(textwrap.indent(shorten(result.content, 800), "  "))

    if state.agent_results:
        lines.append("\n[4. Parallelization + 7. Multi-Agent Collaboration]")
        for result in state.agent_results:
            lines.append(f"- {result.agent_name} / {result.focus}")
            lines.append(textwrap.indent(shorten(result.content, 800), "  "))

    if state.reflection:
        lines.append("\n[5. Reflection]")
        lines.append(textwrap.indent(shorten(state.reflection, 1200), "  "))

    lines.append("\n" + "=" * 72)
    lines.append("Final Answer")
    lines.append("=" * 72)
    lines.append(state.final_answer)

    return "\n".join(lines)


# ============================================================
# Tool Use：本地工具层
# ============================================================

class LocalToolRegistry:
    """
    小型工具注册表。

    当前只做两个工具：
    1. read_text_file：读取简单文本文件；
    2. python_static_review：对 Python 代码做轻量静态检查。

    注意：工具层不要依赖 LLM，它应该是确定性、可测试、可替换的。
    """

    async def run(self, tool_name: str, **kwargs: Any) -> ToolResult:
        if tool_name == "read_text_file":
            return await asyncio.to_thread(self.read_text_file, **kwargs)

        if tool_name == "python_static_review":
            return await asyncio.to_thread(self.python_static_review, **kwargs)

        return ToolResult(
            tool_name=tool_name,
            ok=False,
            content=f"未知工具：{tool_name}",
        )

    @staticmethod
    def read_text_file(path: str) -> ToolResult:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return ToolResult(
                tool_name="read_text_file",
                ok=False,
                content=f"文件不存在：{file_path}",
            )

        if not file_path.is_file():
            return ToolResult(
                tool_name="read_text_file",
                ok=False,
                content=f"路径不是文件：{file_path}",
            )

        encodings = ["utf-8", "utf-8-sig", "gbk"]
        last_error: Exception | None = None

        for encoding in encodings:
            try:
                content = file_path.read_text(encoding=encoding)
                return ToolResult(
                    tool_name="read_text_file",
                    ok=True,
                    content=(
                        f"path={file_path}\n"
                        f"encoding={encoding}\n"
                        f"chars={len(content)}\n\n"
                        f"{shorten(content, 8000)}"
                    ),
                )
            except UnicodeDecodeError as exc:
                last_error = exc

        return ToolResult(
            tool_name="read_text_file",
            ok=False,
            content=f"读取失败，尝试编码 {encodings} 后仍无法解码：{last_error}",
        )

    @staticmethod
    def python_static_review(code: str) -> ToolResult:
        """
        轻量 Python 静态检查工具。

        这不是替代 ruff/mypy，而是为了让 Tool Use 模式在 demo 中可见：
        LLM 负责语义审查，工具负责确定性扫描。
        """

        code = code.strip()
        if not code:
            return ToolResult(
                tool_name="python_static_review",
                ok=False,
                content="没有提供 Python 代码。",
            )

        report: list[str] = []
        report.append(f"代码字符数：{len(code)}")
        report.append(f"代码行数：{len(code.splitlines())}")

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return ToolResult(
                tool_name="python_static_review",
                ok=False,
                content=(
                    "发现语法错误：\n"
                    f"line={exc.lineno}, offset={exc.offset}, msg={exc.msg}\n"
                    f"text={exc.text}"
                ),
            )

        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        async_functions = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]

        report.append(f"函数数量：{len(functions)}")
        report.append(f"异步函数数量：{len(async_functions)}")
        report.append(f"类数量：{len(classes)}")
        report.append(f"import 数量：{len(imports)}")
        report.append(f"print 调用数量：{len(prints)}")

        warnings: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    warnings.append(f"line {node.lineno}: 使用了 bare except，建议指定异常类型。")
                elif isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
                    warnings.append(f"line {node.lineno}: 捕获范围较宽：{node.type.id}。")

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 可变默认参数
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        warnings.append(
                            f"line {node.lineno}: 函数 {node.name} 使用可变默认参数，建议改为 None。"
                        )

                # 过长函数
                if node.end_lineno and node.end_lineno - node.lineno + 1 > 60:
                    warnings.append(
                        f"line {node.lineno}: 函数 {node.name} 超过 60 行，建议拆分。"
                    )

                # 类型标注
                if node.returns is None:
                    warnings.append(
                        f"line {node.lineno}: 函数 {node.name} 缺少返回值类型标注。"
                    )

            if isinstance(node, ast.Call):
                func_name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
                if func_name == "eval":
                    warnings.append(f"line {node.lineno}: 使用 eval，存在安全风险。")
                if func_name == "exec":
                    warnings.append(f"line {node.lineno}: 使用 exec，存在安全风险。")

        if warnings:
            report.append("\n潜在问题：")
            report.extend(f"- {warning}" for warning in warnings[:20])
        else:
            report.append("\n未发现明显静态扫描问题。")

        return ToolResult(
            tool_name="python_static_review",
            ok=True,
            content="\n".join(report),
        )


# ============================================================
# Mini Orchestrator：七种模式串联
# ============================================================

class MiniLocalAgentOrchestrator:
    """
    一个小型 Agent 编排器。

    这个类不是为了炫技，而是为了把七种模式放到一个清晰主线中：

    用户任务
      -> Routing
      -> Planning
      -> Tool Use
      -> Parallelization / Multi-Agent Collaboration
      -> Draft Answer
      -> Reflection
      -> Final Answer
    """

    def __init__(self, llm: AsyncLLMClient, max_parallel: int = 3) -> None:
        self.llm = llm
        self.tools = LocalToolRegistry()
        self.semaphore = asyncio.Semaphore(max_parallel)

    async def run(
        self,
        user_task: str,
        *,
        code_file: str | None = None,
        text_file: str | None = None,
    ) -> OrchestratorState:
        state = OrchestratorState(user_task=user_task)

        # 1. Routing
        state.route = await self.route(user_task, code_file=code_file, text_file=text_file)

        # 2. Planning
        state.plan = await self.plan(user_task, state.route)

        # 3. Tool Use
        state.tool_results = await self.call_tools(
            user_task=user_task,
            route=state.route,
            code_file=code_file,
            text_file=text_file,
        )

        # 4. Parallelization + 7. Multi-Agent Collaboration
        state.agent_results = await self.run_parallel_agents(
            user_task=user_task,
            route=state.route,
            plan=state.plan,
            tool_results=state.tool_results,
        )

        # 6. Prompt Chaining：前面的 route/plan/tool/agents 输出被串到后面的 draft prompt
        state.draft_answer = await self.generate_draft(state)

        # 5. Reflection：输出前自我检查和修正
        state.reflection, state.final_answer = await self.reflect_and_revise(state)

        return state

    async def route(
        self,
        user_task: str,
        *,
        code_file: str | None,
        text_file: str | None,
    ) -> RouteResult:
        """Routing：判断任务类型。"""

        # 命令行显式参数优先，避免路由模型误判。
        if code_file:
            return RouteResult(
                task_type="code_review",
                need_tool=True,
                need_parallel=True,
                confidence=1.0,
                reason="用户通过 --code-file 明确提供了 Python 代码文件。",
            )

        if text_file:
            return RouteResult(
                task_type="file_summary",
                need_tool=True,
                need_parallel=True,
                confidence=1.0,
                reason="用户通过 --text-file 明确提供了文本文件。",
            )

        system_prompt = """
你是 Mini LocalAgent 的 Router。
你只负责把用户任务路由到三类之一：
1. knowledge：普通知识解释
2. code_review：Python 代码审查
3. file_summary：简单文本文件总结

必须只输出 JSON，不要输出解释性正文。
JSON 格式：
{
  "task_type": "knowledge | code_review | file_summary",
  "need_tool": true/false,
  "need_parallel": true/false,
  "confidence": 0.0-1.0,
  "reason": "简短原因"
}
""".strip()

        user_prompt = f"用户任务：\n{user_task}"

        try:
            raw = await self.llm.chat(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=500,
            )
            data = extract_json(raw)
            return RouteResult(
                task_type=data.get("task_type", "knowledge"),
                need_tool=bool(data.get("need_tool", False)),
                need_parallel=bool(data.get("need_parallel", True)),
                confidence=float(data.get("confidence", 0.6)),
                reason=str(data.get("reason", "模型路由结果。")),
            )
        except Exception as exc:
            # 兜底路由：demo 要能继续跑，而不是 Router 挂了全局失败。
            lowered = user_task.lower()
            if "```" in user_task or "def " in user_task or "class " in user_task or "代码" in user_task:
                task_type: TaskType = "code_review"
                need_tool = True
            elif ".txt" in lowered or "总结文件" in user_task or "文本文件" in user_task:
                task_type = "file_summary"
                need_tool = True
            else:
                task_type = "knowledge"
                need_tool = False

            return RouteResult(
                task_type=task_type,
                need_tool=need_tool,
                need_parallel=True,
                confidence=0.4,
                reason=f"Router LLM 调用失败，使用规则兜底：{exc}",
            )

    async def plan(self, user_task: str, route: RouteResult) -> PlanResult:
        """Planning：根据路由结果生成执行计划。"""

        system_prompt = """
你是 Mini LocalAgent 的 Planner。
你要根据 Router 的结果，生成一个非常小但清晰的执行计划。

要求：
1. 计划必须体现 Agentic Design Patterns；
2. 不要生成太多步骤，4-6 步即可；
3. parallel_jobs 表示可以并行运行的分析 Agent；
4. 必须只输出 JSON。

JSON 格式：
{
  "steps": [
    {"name": "步骤名", "pattern": "Routing/Planning/Tool Use/...", "detail": "做什么"}
  ],
  "parallel_jobs": [
    {"agent_name": "xxx", "focus": "xxx"}
  ]
}
""".strip()

        user_prompt = f"""
用户任务：
{user_task}

Router 输出：
{json.dumps(route.__dict__, ensure_ascii=False, indent=2)}
""".strip()

        try:
            raw = await self.llm.chat(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=1000,
            )
            data = extract_json(raw)
            steps = [
                PlanStep(
                    name=str(item.get("name", "未命名步骤")),
                    pattern=str(item.get("pattern", "Planning")),
                    detail=str(item.get("detail", "")),
                )
                for item in data.get("steps", [])
            ]
            parallel_jobs = [
                {
                    "agent_name": str(item.get("agent_name", "GeneralAgent")),
                    "focus": str(item.get("focus", "综合分析")),
                }
                for item in data.get("parallel_jobs", [])
            ]

            if steps:
                return PlanResult(steps=steps, parallel_jobs=parallel_jobs)
        except Exception:
            pass

        # Planner 兜底，保证 demo 稳定。
        if route.task_type == "knowledge":
            jobs = [
                {"agent_name": "ConceptAgent", "focus": "解释核心概念"},
                {"agent_name": "EngineeringAgent", "focus": "说明工程落地方式"},
                {"agent_name": "InterviewAgent", "focus": "补充面试表达和追问点"},
            ]
        elif route.task_type == "code_review":
            jobs = [
                {"agent_name": "CorrectnessAgent", "focus": "检查正确性和异常风险"},
                {"agent_name": "MaintainabilityAgent", "focus": "检查可读性、结构和可维护性"},
                {"agent_name": "InterviewAgent", "focus": "提炼面试中可讲的改进点"},
            ]
        else:
            jobs = [
                {"agent_name": "SummaryAgent", "focus": "总结核心内容"},
                {"agent_name": "StructureAgent", "focus": "梳理文章结构"},
                {"agent_name": "ActionAgent", "focus": "提炼行动项或结论"},
            ]

        return PlanResult(
            steps=[
                PlanStep("确认任务类型", "Routing", "根据用户输入判断走知识解释、代码审查或文件总结。"),
                PlanStep("生成执行计划", "Planning", "把任务拆成工具调用、并行分析和最终回答。"),
                PlanStep("调用必要工具", "Tool Use", "代码审查调用静态扫描；文件总结调用文件读取工具。"),
                PlanStep("并行分析", "Parallelization + Multi-Agent Collaboration", "多个专职 Agent 从不同角度分析。"),
                PlanStep("生成并反思答案", "Prompt Chaining + Reflection", "把前面结果串起来生成初稿，再检查和修正。"),
            ],
            parallel_jobs=jobs,
        )

    async def call_tools(
        self,
        *,
        user_task: str,
        route: RouteResult,
        code_file: str | None,
        text_file: str | None,
    ) -> list[ToolResult]:
        """Tool Use：根据任务类型调用本地工具。"""

        results: list[ToolResult] = []

        if route.task_type == "code_review":
            if code_file:
                read_result = await self.tools.run("read_text_file", path=code_file)
                results.append(read_result)
                code = read_result.content if read_result.ok else ""
            else:
                code = extract_code_from_task(user_task)

            static_result = await self.tools.run("python_static_review", code=code)
            results.append(static_result)

        elif route.task_type == "file_summary":
            path = text_file or self.extract_path_from_task(user_task)
            if path:
                results.append(await self.tools.run("read_text_file", path=path))
            else:
                results.append(
                    ToolResult(
                        tool_name="read_text_file",
                        ok=False,
                        content="未能从任务中识别文件路径。建议使用 --text-file 显式传入。",
                    )
                )

        return results

    @staticmethod
    def extract_path_from_task(user_task: str) -> str | None:
        """从自然语言中粗略提取 txt 路径。"""

        # 支持 Windows 路径和普通相对路径
        candidates = re.findall(r"[A-Za-z]:\\[^\n\r\"']+?\.txt|[^\s\"']+\.txt", user_task)
        if candidates:
            return candidates[0].strip()
        return None

    async def run_parallel_agents(
        self,
        *,
        user_task: str,
        route: RouteResult,
        plan: PlanResult,
        tool_results: list[ToolResult],
    ) -> list[AgentResult]:
        """
        Parallelization + Multi-Agent Collaboration。

        多个 Agent 并行分析同一个任务，但关注点不同。
        """

        jobs = plan.parallel_jobs
        if not jobs:
            jobs = [{"agent_name": "GeneralAgent", "focus": "综合分析"}]

        async def run_one(job: dict[str, str]) -> AgentResult:
            async with self.semaphore:
                agent_name = job.get("agent_name", "GeneralAgent")
                focus = job.get("focus", "综合分析")

                system_prompt = f"""
你是 {agent_name}，Mini LocalAgent 中的一个专职分析 Agent。
你的关注点是：{focus}

要求：
1. 只围绕自己的关注点输出；
2. 不要重复其它 Agent 可能会说的大段通用内容；
3. 输出中文；
4. 结论要短而具体。
""".strip()

                tool_context = "\n\n".join(
                    f"[{item.tool_name} / ok={item.ok}]\n{shorten(item.content, 3000)}"
                    for item in tool_results
                ) or "无工具结果。"

                user_prompt = f"""
用户任务：
{user_task}

任务类型：{route.task_type}

工具结果：
{tool_context}
""".strip()

                try:
                    content = await self.llm.chat(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.1,
                        max_tokens=900,
                    )
                except Exception as exc:
                    content = f"该 Agent 调用失败：{exc}"

                return AgentResult(
                    agent_name=agent_name,
                    focus=focus,
                    content=content.strip(),
                )

        return list(await asyncio.gather(*(run_one(job) for job in jobs)))

    async def generate_draft(self, state: OrchestratorState) -> str:
        """Prompt Chaining：汇总前面所有环节，生成初稿。"""

        system_prompt = """
你是 Mini LocalAgent 的 AnswerComposer。
你要根据 Router、Planner、Tool、多个 Agent 的结果，生成一版中文初稿。

要求：
1. 直接回答用户任务；
2. 结构清晰，但不要过度冗长；
3. 如果工具失败，要明确说明；
4. 不要编造工具中没有的信息；
5. 代码审查任务要给出问题、原因、建议；
6. 文件总结任务要基于读到的文件内容。
""".strip()

        user_prompt = self.build_state_prompt(state)

        return await self.llm.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=1800,
        )

    async def reflect_and_revise(self, state: OrchestratorState) -> tuple[str, str]:
        """Reflection：检查初稿并输出最终稿。"""

        system_prompt = """
你是 Mini LocalAgent 的 ReflectionAgent。
你负责在最终输出前审查初稿。

检查维度：
1. 是否回答了用户原始任务；
2. 是否遗漏 Router/Planner/Tool/Agent 里的重要信息；
3. 是否有不确定却说死的内容；
4. 是否有明显废话；
5. 文件总结是否忠于文件内容；
6. 代码审查是否给出可执行修改建议。

输出格式：
先输出【Reflection】部分，列出你发现的问题。
再输出【Revised Answer】部分，给出修订后的最终答案。
""".strip()

        user_prompt = f"""
用户任务：
{state.user_task}

当前初稿：
{state.draft_answer}

完整状态：
{self.build_state_prompt(state)}
""".strip()

        raw = await self.llm.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=2200,
        )

        reflection = raw.strip()
        marker = "【Revised Answer】"
        if marker in reflection:
            final_answer = reflection.split(marker, maxsplit=1)[1].strip()
        else:
            final_answer = state.draft_answer.strip()

        return reflection, final_answer

    @staticmethod
    def build_state_prompt(state: OrchestratorState) -> str:
        route_data = state.route.__dict__ if state.route else {}
        plan_data = {
            "steps": [step.__dict__ for step in state.plan.steps],
            "parallel_jobs": state.plan.parallel_jobs,
        } if state.plan else {}

        tool_data = [item.__dict__ for item in state.tool_results]
        agent_data = [item.__dict__ for item in state.agent_results]

        return f"""
用户任务：
{state.user_task}

Router 输出：
{json.dumps(route_data, ensure_ascii=False, indent=2)}

Planner 输出：
{json.dumps(plan_data, ensure_ascii=False, indent=2)}

Tool 输出：
{json.dumps(tool_data, ensure_ascii=False, indent=2)}

Parallel Agents 输出：
{json.dumps(agent_data, ensure_ascii=False, indent=2)}
""".strip()


# ============================================================
# CLI 入口
# ============================================================

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mini LocalAgent Orchestrator：串联第一章七种 Agent 模式的小型综合 demo。"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="",
        help="用户任务。比如：解释 Agent Routing 是什么。",
    )
    parser.add_argument(
        "--code-file",
        type=str,
        default=None,
        help="需要审查的 Python 代码文件路径。",
    )
    parser.add_argument(
        "--text-file",
        type=str,
        default=None,
        help="需要总结的 txt 文本文件路径。",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=3,
        help="并行 Agent 最大并发数，默认 3。",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="只输出最终答案，不打印中间编排轨迹。",
    )
    return parser


async def async_main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    user_task = args.task.strip()

    if not user_task:
        print("请输入任务。示例：解释 Agent Routing 是什么 / 审查这段 Python 代码 / 总结某个 txt 文件")
        user_task = input(">>> ").strip()

    if not user_task and not args.code_file and not args.text_file:
        raise SystemExit("任务为空，已退出。")

    # 显式文件参数会帮助 Router 降低误判概率。
    if args.code_file and not user_task:
        user_task = "请审查这个 Python 代码文件。"
    if args.text_file and not user_task:
        user_task = "请总结这个文本文件。"

    async with AsyncLLMClient() as llm:
        orchestrator = MiniLocalAgentOrchestrator(
            llm=llm,
            max_parallel=args.max_parallel,
        )
        state = await orchestrator.run(
            user_task=user_task,
            code_file=args.code_file,
            text_file=args.text_file,
        )

    if args.no_trace:
        print(state.final_answer)
    else:
        print(format_trace(state))


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
