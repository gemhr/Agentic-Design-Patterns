#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AW 顺序状态解耦 / Normalized 生成脚本

核心目标
========
原始用例按执行表顺序运行时，前一个 Case 对 DSP 全局变量的修改可能遗留给后一个 Case。
现在这些 Case 会进入随机池独立执行，因此需要为每个 Case 生成：

    TestCtrlPara_Normalized.dat

生成逻辑分两步：

Pass 1
------
1. 每个处理单元的 current_state 初始为空。
2. 严格按 用例执行列表_5G.xls 原始顺序扫描。
3. 在每个 Case 的：

       set TestCtrlInfoList {

   下一行插入“前序 Case 中已经写入过非默认值”的受控变量历史状态。
4. 从未在前序 Case 中写入过非默认值的受控变量不主动插入。
5. 原始 AW 中写入默认值的受控 WSym 会被删除，不推进 current_state。
6. current_state 只根据“原始 AW 中写入非默认值的 WSym”推进。
   新增的前置写入和恢复写入绝不参与状态推进。

Pass 2
------
1. 在固定尾部：

       xxx
       }
       set RecoveryList {
       }
       set CaptureList {
       }

   中，RecoveryList 前面的那个 } 之前插入恢复脚本。
2. Pass 1 前置插入的全部已跟踪受控变量都恢复到 DSP JSON 默认值。
3. 当前 Case 自己写入过非默认值的受管变量也恢复。
4. 当前 Case 写入默认值的受管变量已在 Pass 1 删除，因此不会新增恢复写入。
5. 同一个状态项在当前 Case 中写多次非默认值：
   - 原脚本全部保留；
   - 历史状态取最后一次；
   - 恢复只写一次；
   - 恢复模板优先使用该 Case 最后一次真实写入格式。

状态键
======
DSP ID（WSym 第一个参数）参与状态键，多个 DSP 分别跟踪。

DSP_WSym:
    (BBH/BBL, DSP ID, Core ID, Variable, Offset=0)

DSP_WSymOffset:
    (BBH/BBL, DSP ID, Core ID, Variable, Offset)

DSP_WSymAuto:
    (BBH/BBL, DSP ID, Core ID=5, Variable, Offset=0)

board_sensitive 变量还会把 AW target 加入状态键，避免同一 IP 下不同版型
的 BBL 单板互相覆盖状态。

板型
====
    BaseBandBoard -> BBH
    enb0          -> BBH
    其他 enb数字   -> BBL

外部 JSON
=========
environment_board_mapping.json：
    使用 environments[IP][target].board 查询具体版型。
    映射中不存在当前 IP 时，直接跳过该 IP。

dsp_defaults.json：
    common 与 board_sensitive 是同级字段，完全替代旧 default.txt。

common：
    只按 BBH/BBL、DSP ID、Core ID、Variable、Offset 匹配默认值。

board_sensitive：
    先按 IP 和 AW target 查询版型，再从 defaults_by_board 选默认值：
    1. 当前版型存在当前 DSP ID：使用精确值；
    2. 否则使用第一个包含当前 DSP ID 的版型值；
    3. 仍不存在时，使用 defaults_by_board 中第一个版型的第一个值。

受控变量规则
============
DSP 默认值 JSON 承担两个职责：

1. 判断某条 WSym 是否属于受控变量；
2. 提供该受控变量的默认恢复值。

并不要求每个 IP 都必须出现 JSON 中的全部变量。

状态集合按当前处理单元的原始执行顺序动态增长：

- 某个受控变量从未在前序 Case 中写入过非默认值：
  不在当前 Case 开头补写；
- 当前 Case 写入该受控变量的默认值：
  删除该原始 WSym，不推进历史状态，也不在当前 Case 结尾新增恢复写入；
- 当前 Case 第一次写入该受控变量的非默认值：
  保留原始写入，并在当前 Case 结尾恢复默认值；
- 从下一个 Case 开始：
  该变量进入历史状态链，按前序 Case 最后的非默认写入值在开头补写；
- 当前 Case 结束时，所有开头补写过的受控变量和当前 Case 自己写入过
  非默认值的受控变量，都恢复到 DSP JSON 默认值。

前置/恢复脚本始终复用当前 IP 中真实出现过的 WSym 行作为模板，
只替换真正的数据参数。

本脚本会打印详细诊断：
    - WSym 候选行总数
    - 成功解析数
    - 命中受管变量数
    - 未命中 StateKey 样例
    - 解析失败 WSym 样例

异常隔离
========
1. 单个 Case AW 加载失败：记录错误并跳过，其他 Case 按原顺序继续；
   接受后续历史状态可能缺少失败 Case 的影响。
2. 单个 Case 的 Pass 1/Pass 2 已知格式或写入错误：跳过该 Case。
3. 处理单元未知异常：跳过该处理单元，继续同 IP 的其他处理单元。
4. IP 未知异常：跳过该 IP；串行和并发 IP 模式行为一致。
5. 全局 JSON 无法加载、远程根目录无法扫描等启动条件错误仍会终止任务。

UNC / 并发优化
==============
1. RUN_ALL_IPS=False 时，不再枚举远程根目录，也不预先 is_dir()；
   直接构造 TARGET_IPS 路径，后续读取执行表时自然判断是否存在。
2. AW 不再先 is_file() 再 read，避免双重 SMB round-trip。
3. 不再对 UNC Path 调用 resolve()。
4. 多 IP 并行。
5. 单 IP 内 AW 文件读取并行。
6. Pass 1 状态推进严格串行。
7. AW 读取每 30 秒输出一次心跳和等待中的文件。
8. faulthandler 每 60 秒打印所有线程堆栈，方便定位 SMB 阻塞。
"""

from __future__ import annotations

import faulthandler
import json
import os
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import xlrd


# ============================================================
# 一、用户配置
# ============================================================

REMOTE_ROOT = Path(
    r"\\7.213.207.64\opt\data1\UCI\workspace\UCI_Script\26B\TestCase_26B"
)

BOARD_MAPPING_JSON = Path(
    __file__
).parent / "environment_board_mapping.json"

DSP_DEFAULTS_JSON = Path(
    __file__
).parent / "dsp_defaults.json"

# ------------------------------------------------------------
# IP 运行模式
# ------------------------------------------------------------

RUN_ALL_IPS = True # True 对上面的远程目录遍历IP

TARGET_IPS = [
    "10.150.102.133",
    "10.150.102.136",
]


# ============================================================
# 二、执行参数
# ============================================================

EXECUTION_XLS_NAME = "用例执行列表_5G.xls"

# 已存在 Normalized 文件时是否覆盖
OVERWRITE_NORMALIZED = True


# ------------------------------------------------------------
# 并发
# ------------------------------------------------------------

ENABLE_IP_CONCURRENCY = True
ENABLE_AW_READ_CONCURRENCY = True

# 日志中 4*6 的 UNC 并发存在少量长阻塞。
# 先使用更保守的 2*4，稳定后再调大。
MAX_IP_WORKERS = 2
MAX_AW_READ_WORKERS_PER_IP = 4

# AW 并发读取无完成任务时，每多少秒打印一次心跳
AW_READ_HEARTBEAT_SECONDS = 30

# 心跳时最多显示几个仍在等待的 AW
AW_WAITING_SAMPLE_COUNT = 5

# faulthandler 每多少秒打印一次线程堆栈
FAULT_DUMP_SECONDS = 60

# 模板诊断打印多少个样例
DIAGNOSTIC_SAMPLE_COUNT = 20


# ============================================================
# 三、执行表列
# ============================================================

# xlrd 0-based
COL_A_CASE_PATH = 0

# AM = 第 39 列 -> 0-based 38
COL_AM_AW_NAME = 38


# ============================================================
# 四、命令类型 / 正则
# ============================================================

TYPE_WSYM = "DSP_WSym"
TYPE_AUTO = "DSP_WSymAuto"
TYPE_OFFSET = "DSP_WSymOffset"

WSYM_PATTERN = re.compile(
    r"DSP_WSymOffset"
    r"|DSP_WSymOffest"
    r"|DSP_WSymAuto"
    r"|DSP_WSym",
    flags=re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(
    r"[-+]?(?:0[xX][0-9A-Fa-f]+|\d+)"
)

# 只要求 AW 前两个双引号字段合法：
# {"CMD" "enb0" ...
# {"CMD" "BaseBandBoard" ...
AW_FIRST_TWO_FIELDS_PATTERN = re.compile(
    r'^\s*\{\s*"([^"]*)"\s+"([^"]*)"'
)


# ============================================================
# 五、线程安全日志
# ============================================================

_PRINT_LOCK = threading.Lock()


def log(message: str) -> None:
    """
    带时间戳、立即 flush 的线程安全日志。
    """

    with _PRINT_LOCK:
        print(
            f"[{datetime.now():%H:%M:%S}] {message}",
            flush=True,
        )


# ============================================================
# 六、数据结构
# ============================================================

@dataclass(frozen=True)
class DefaultKey:
    section: str
    core_id: int
    variable: str
    offset: int


@dataclass(frozen=True)
class StateKey:
    section: str
    dsp_id: int
    core_id: int
    variable: str
    offset: int
    target: str = ""


@dataclass
class DefaultSpec:
    key: StateKey
    default_value: str
    source: str


@dataclass
class DefaultCatalog:
    common: dict[DefaultKey, dict[int, str]]
    board_sensitive: dict[
        DefaultKey,
        dict[str, dict[int, str]],
    ]


@dataclass
class WriteCommand:
    raw_line: str
    command_type: str
    section: str
    target: str
    dsp_id: int
    core_id: int
    variable: str
    data_token: str
    offset: int
    data_start: int
    data_end: int

    @property
    def key(self) -> StateKey:
        return StateKey(
            section=self.section,
            dsp_id=self.dsp_id,
            core_id=self.core_id,
            variable=self.variable,
            offset=self.offset,
        )

    @property
    def default_key(self) -> DefaultKey:
        return DefaultKey(
            section=self.section,
            core_id=self.core_id,
            variable=self.variable,
            offset=self.offset,
        )

    def replace_data(self, new_value: str) -> str:
        """
        完整保留原始 AW 行，只替换真正写入 Data。
        """
        return (
            self.raw_line[:self.data_start]
            + str(new_value)
            + self.raw_line[self.data_end:]
        )


@dataclass
class CaseSource:
    excel_row: int
    case_root: Path
    source_aw: Path
    output_aw: Path
    axcauto_source: Path | None
    axcauto_output: Path | None
    axcauto_text: str | None
    text: str
    encoding: str
    newline: str
    write_commands: list[WriteCommand]
    wsym_candidate_count: int
    wsym_parse_failed_lines: list[str]


@dataclass
class CasePlan:
    case: CaseSource
    pass1_text: str
    front_lines: list[str]
    recovery_lines: list[str]


@dataclass
class TemplateDiagnostics:
    candidate_count: int
    parsed_count: int
    managed_command_count: int
    managed_unique_key_count: int
    unmatched_key_counts: dict[StateKey, int]
    parse_failed_lines: list[str]


# ============================================================
# 七、基础解析
# ============================================================

def parse_int(value: str) -> int | None:
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return None


def xls_cell_text(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


# ============================================================
# 八、JSON 默认值与版型映射
# ============================================================

def load_json_object(path: Path, label: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"{label}不存在：{path}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"{label}读取失败：{path}：{exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(f"{label}顶层必须是 JSON object：{path}")

    return data


def parse_default_key(
    section: str,
    item: object,
    source: str,
) -> DefaultKey:
    if not isinstance(item, dict):
        raise ValueError(f"{source} 必须是 JSON object")

    normalized_section = section.upper()
    core_id = parse_int(item.get("core"))
    offset = parse_int(item.get("offset"))
    variable = str(item.get("variable", "")).strip()

    if normalized_section not in ("BBH", "BBL"):
        raise ValueError(f"{source} 的分组非法：{section!r}")
    if core_id is None or offset is None or not variable:
        raise ValueError(
            f"{source} 缺少合法的 variable/core/offset"
        )

    return DefaultKey(
        section=normalized_section,
        core_id=core_id,
        variable=variable,
        offset=offset,
    )


def parse_dsp_defaults(
    value: object,
    source: str,
) -> dict[int, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{source} 必须是非空 JSON object")

    result: dict[int, str] = {}

    for raw_dsp_id, raw_default in value.items():
        dsp_id = parse_int(raw_dsp_id)
        default_value = str(raw_default).strip()

        if dsp_id is None or parse_int(default_value) is None:
            raise ValueError(
                f"{source} 包含非法 DSP ID 或默认值："
                f"{raw_dsp_id!r}={raw_default!r}"
            )

        result[dsp_id] = default_value

    return result


def load_default_catalog(path: Path) -> DefaultCatalog:
    data = load_json_object(path, "DSP 默认值 JSON")
    common: dict[DefaultKey, dict[int, str]] = {}
    board_sensitive: dict[
        DefaultKey,
        dict[str, dict[int, str]],
    ] = {}

    common_root = data.get("common", {})
    sensitive_root = data.get("board_sensitive", {})

    if not isinstance(common_root, dict):
        raise ValueError("DSP 默认值 JSON 的 common 必须是 object")
    if not isinstance(sensitive_root, dict):
        raise ValueError(
            "DSP 默认值 JSON 的 board_sensitive 必须是 object"
        )

    for section, items in common_root.items():
        if not isinstance(items, dict):
            raise ValueError(f"common.{section} 必须是 object")

        for name, item in items.items():
            source = f"common.{section}.{name}"
            key = parse_default_key(section, item, source)
            dsp_defaults = parse_dsp_defaults(
                item.get("dsp_defaults"),
                f"{source}.dsp_defaults",
            )

            if key in common or key in board_sensitive:
                raise ValueError(f"DSP 默认值重复定义：{source}")

            common[key] = dsp_defaults

    for section, items in sensitive_root.items():
        if not isinstance(items, dict):
            raise ValueError(f"board_sensitive.{section} 必须是 object")

        for name, item in items.items():
            source = f"board_sensitive.{section}.{name}"
            key = parse_default_key(section, item, source)
            raw_by_board = item.get("defaults_by_board")

            if not isinstance(raw_by_board, dict) or not raw_by_board:
                raise ValueError(
                    f"{source}.defaults_by_board 必须是非空 object"
                )

            defaults_by_board: dict[str, dict[int, str]] = {}

            for board, dsp_values in raw_by_board.items():
                board_name = str(board).strip()
                if not board_name:
                    raise ValueError(f"{source} 包含空版型名称")

                defaults_by_board[board_name] = parse_dsp_defaults(
                    dsp_values,
                    f"{source}.defaults_by_board.{board_name}",
                )

            if key in common or key in board_sensitive:
                raise ValueError(f"DSP 默认值重复定义：{source}")

            board_sensitive[key] = defaults_by_board

    return DefaultCatalog(
        common=common,
        board_sensitive=board_sensitive,
    )


def load_board_mappings(path: Path) -> dict[str, dict[str, str]]:
    data = load_json_object(path, "环境版型映射 JSON")
    environments = data.get("environments")

    if not isinstance(environments, dict):
        raise ValueError(
            "环境版型映射 JSON 缺少 environments object"
        )

    result: dict[str, dict[str, str]] = {}

    for ip_name, targets in environments.items():
        if not isinstance(targets, dict):
            continue

        boards: dict[str, str] = {}

        for target, info in targets.items():
            if not isinstance(info, dict):
                continue

            board = str(info.get("board", "")).strip()
            if board:
                boards[str(target).strip().lower()] = board

        if boards:
            result[str(ip_name).strip()] = boards

    return result


def resolve_default(
    command: WriteCommand,
    catalog: DefaultCatalog,
    boards_by_target: dict[str, str],
) -> DefaultSpec | None:
    key = command.default_key
    common_defaults = catalog.common.get(key)

    if common_defaults is not None:
        default_value = common_defaults.get(command.dsp_id)
        if default_value is None:
            return None

        return DefaultSpec(
            key=command.key,
            default_value=default_value,
            source="common",
        )

    defaults_by_board = catalog.board_sensitive.get(key)
    if defaults_by_board is None:
        return None

    target = command.target.lower()
    board_target = "enb0" if target == "basebandboard" else target
    board = boards_by_target.get(board_target)
    selected_board = None
    default_value = None

    if board is not None:
        exact_defaults = defaults_by_board.get(board)
        if exact_defaults is not None:
            default_value = exact_defaults.get(command.dsp_id)
            if default_value is not None:
                selected_board = board

    if default_value is None:
        for candidate_board, candidate_defaults in defaults_by_board.items():
            candidate_value = candidate_defaults.get(command.dsp_id)
            if candidate_value is not None:
                selected_board = candidate_board
                default_value = candidate_value
                break

    if default_value is None:
        selected_board, first_defaults = next(
            iter(defaults_by_board.items())
        )
        default_value = next(iter(first_defaults.values()))

    state_key = StateKey(
        section=command.section,
        dsp_id=command.dsp_id,
        core_id=command.core_id,
        variable=command.variable,
        offset=command.offset,
        target=board_target,
    )

    return DefaultSpec(
        key=state_key,
        default_value=default_value,
        source=(
            f"board_sensitive target={board_target} "
            f"board={board or 'UNKNOWN'} selected={selected_board}"
        ),
    )


# ============================================================
# 九、AW target -> BBH / BBL
# ============================================================

def get_target_from_aw_line(line: str) -> str | None:
    match = AW_FIRST_TWO_FIELDS_PATTERN.match(line)
    if match is None:
        return None

    target = match.group(2).strip()

    return target or None


def get_section_from_aw_line(line: str) -> str | None:
    raw_target = get_target_from_aw_line(line)
    if raw_target is None:
        return None

    target = raw_target.lower()

    if target in ("basebandboard", "enb0"):
        return "BBH"

    if re.fullmatch(r"enb\d+", target, flags=re.IGNORECASE):
        return "BBL"

    return None


# ============================================================
# 十、WSym 宽松解析
# ============================================================

def normalize_command_type(raw_type: str) -> str:
    value = raw_type.lower()

    if value in (
        "dsp_wsymoffset",
        "dsp_wsymoffest",
    ):
        return TYPE_OFFSET

    if value == "dsp_wsymauto":
        return TYPE_AUTO

    return TYPE_WSYM


def parse_wsym_line(
    line: str,
) -> WriteCommand | None:
    """
    宽松识别 DSP_WSym / Auto / Offset。

    不要求括号严格合法。
    主要依赖：
      1. WSym 家族命令名
      2. 变量名双引号
      3. 变量名前的数字参数
      4. 变量名后的 Data / Offset 数字
    """

    type_match = WSYM_PATTERN.search(line)
    if type_match is None:
        return None

    section = get_section_from_aw_line(line)
    target = get_target_from_aw_line(line)
    if section is None or target is None:
        return None

    command_type = normalize_command_type(
        type_match.group(0)
    )

    first_quote = line.find(
        '"',
        type_match.end(),
    )

    if first_quote < 0:
        return None

    second_quote = line.find(
        '"',
        first_quote + 1,
    )

    if second_quote < 0:
        return None

    variable = (
        line[first_quote + 1:second_quote]
        .strip()
        .strip("\\")
        .strip()
    )

    if not variable:
        return None

    before_variable = line[
        type_match.end():first_quote
    ]

    before_numbers = list(
        NUMBER_PATTERN.finditer(
            before_variable
        )
    )

    if command_type == TYPE_AUTO:
        if len(before_numbers) < 1:
            return None

        dsp_id = parse_int(
            before_numbers[0].group(0)
        )

        # 按约定固定归一到 Core 5
        core_id = 5

    else:
        if len(before_numbers) < 2:
            return None

        dsp_id = parse_int(
            before_numbers[0].group(0)
        )

        core_id = parse_int(
            before_numbers[1].group(0)
        )

    if dsp_id is None or core_id is None:
        return None

    after_start = second_quote + 1
    after_text = line[after_start:]

    after_numbers = list(
        NUMBER_PATTERN.finditer(
            after_text
        )
    )

    if not after_numbers:
        return None

    # 变量名后的第一个数字一定是 Data
    data_match = after_numbers[0]

    data_token = data_match.group(0)
    data_start = after_start + data_match.start()
    data_end = after_start + data_match.end()

    if command_type == TYPE_OFFSET:
        if len(after_numbers) < 2:
            return None

        offset = parse_int(
            after_numbers[1].group(0)
        )

        if offset is None:
            return None
    else:
        offset = 0

    return WriteCommand(
        raw_line=line,
        command_type=command_type,
        section=section,
        target=target,
        dsp_id=dsp_id,
        core_id=core_id,
        variable=variable,
        data_token=data_token,
        offset=offset,
        data_start=data_start,
        data_end=data_end,
    )


def parse_all_wsym(
    text: str,
) -> tuple[
    list[WriteCommand],
    int,
    list[str],
]:
    """
    返回：
      成功解析的 WSym
      WSym 候选行数
      解析失败的 WSym 行
    """

    result: list[WriteCommand] = []
    candidate_count = 0
    failed_lines: list[str] = []

    for line in text.splitlines():
        if WSYM_PATTERN.search(line) is None:
            continue

        candidate_count += 1

        command = parse_wsym_line(line)

        if command is None:
            if len(failed_lines) < DIAGNOSTIC_SAMPLE_COUNT:
                failed_lines.append(line)
            continue

        result.append(command)

    return result, candidate_count, failed_lines


# ============================================================
# 十一、AW 读取 / 写入
# ============================================================

def read_aw_file(
    path: Path,
) -> tuple[str, str, str]:
    """
    只做一次真正的 open/read。
    不在前面 is_file()。
    """

    with open(path, "rb") as file:
        raw = file.read()

    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
        encoding = "utf-8-sig"
    else:
        try:
            text = raw.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = raw.decode("gb18030")
            encoding = "gb18030"

    newline = "\r\n" if "\r\n" in text else "\n"

    return text, encoding, newline


def write_aw_file(
    path: Path,
    text: str,
    encoding: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding=encoding,
        newline="",
    ) as file:
        file.write(text)


# ============================================================
# 十二、AW 插入
# ============================================================

def insert_after_testctrlinfo(
    text: str,
    new_lines: list[str],
    newline: str,
) -> str:
    lines = text.splitlines()

    target_index = None

    for index, line in enumerate(lines):
        if line.strip() == "set TestCtrlInfoList {":
            target_index = index + 1
            break

    if target_index is None:
        raise ValueError(
            "找不到：set TestCtrlInfoList {"
        )

    lines[target_index:target_index] = new_lines

    result = newline.join(lines)

    if text.endswith(("\n", "\r")):
        result += newline

    return result


def insert_before_recovery_tail(
    text: str,
    recovery_lines: list[str],
    newline: str,
) -> str:
    """
    在最后一个 set RecoveryList { 前面的 TestCtrlInfoList 结束 } 之前插入。
    """

    lines = text.splitlines()

    recovery_index = None

    for index in range(
        len(lines) - 1,
        -1,
        -1,
    ):
        if lines[index].strip() == "set RecoveryList {":
            recovery_index = index
            break

    if recovery_index is None:
        raise ValueError(
            "找不到固定尾部：set RecoveryList {"
        )

    close_index = recovery_index - 1

    while (
        close_index >= 0
        and not lines[close_index].strip()
    ):
        close_index -= 1

    if (
        close_index < 0
        or lines[close_index].strip() != "}"
    ):
        raise ValueError(
            "set RecoveryList { 前未找到 TestCtrlInfoList 的结束 }"
        )

    lines[close_index:close_index] = recovery_lines

    result = newline.join(lines)

    if text.endswith(("\n", "\r")):
        result += newline

    return result


# ============================================================
# 十三、执行表
# ============================================================

def load_case_paths(
    ip_dir: Path,
) -> list[tuple[int, Path, str]]:
    execution_xls = ip_dir / EXECUTION_XLS_NAME

    log(
        f"[XLS] IP={ip_dir.name} 开始读取：{execution_xls}"
    )

    start = time.perf_counter()

    # 不先 is_file()，直接读。
    try:
        with open(execution_xls, "rb") as file:
            xls_bytes = file.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"找不到执行表：{execution_xls}"
        ) from exc
    except OSError as exc:
        raise OSError(
            f"执行表读取失败：{execution_xls}：{exc}"
        ) from exc

    elapsed = time.perf_counter() - start

    log(
        f"[XLS] IP={ip_dir.name} 文件读取完成，"
        f"大小={len(xls_bytes)} bytes，耗时={elapsed:.2f}s"
    )

    try:
        workbook = xlrd.open_workbook(
            file_contents=xls_bytes,
            on_demand=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"执行表解析失败：{execution_xls}：{exc}"
        ) from exc

    try:
        sheet = workbook.sheet_by_index(0)

        result: list[
            tuple[int, Path, str]
        ] = []

        for row_index in range(
            1,
            sheet.nrows,
        ):
            a_value = xls_cell_text(
                sheet.cell_value(
                    row_index,
                    COL_A_CASE_PATH,
                )
            )

            if not a_value:
                continue

            if a_value.lower() == "end":
                break

            am_value = ""

            if sheet.ncols > COL_AM_AW_NAME:
                am_value = xls_cell_text(
                    sheet.cell_value(
                        row_index,
                        COL_AM_AW_NAME,
                    )
                )

            case_root = Path(a_value)

            if not case_root.is_absolute():
                case_root = ip_dir / case_root

            result.append(
                (
                    row_index + 1,
                    case_root,
                    am_value,
                )
            )

    finally:
        workbook.release_resources()

    log(
        f"[XLS] IP={ip_dir.name} 解析完成，Case={len(result)}"
    )

    return result


# ============================================================
# 十四、单个 Case 加载
# ============================================================

def load_single_case(
    excel_row: int,
    case_root: Path,
    am_value: str,
) -> CaseSource:
    aw_name = (
        am_value
        if am_value
        else "TestCtrlPara.dat"
    )

    aw_dir = case_root / "TestCtrlPara"

    source_aw = aw_dir / aw_name
    aw_stem = source_aw.stem
    output_aw = aw_dir / (aw_stem + "_Normalized.dat")

    # 不使用 resolve()。
    # 只要源文件名本身就是 Normalized，就禁止。
    if source_aw.name.lower().endswith("_normalized.dat"):
        raise RuntimeError(
            f"执行表第 {excel_row} 行："
            f"禁止把 _Normalized.dat 文件作为原始输入：{source_aw.name}"
        )

    try:
        text, encoding, newline = read_aw_file(
            source_aw
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"执行表第 {excel_row} 行：AW不存在：{source_aw}"
        ) from exc
    except OSError as exc:
        raise OSError(
            f"执行表第 {excel_row} 行：AW读取失败：{source_aw}：{exc}"
        ) from exc

    (
        write_commands,
        candidate_count,
        parse_failed_lines,
    ) = parse_all_wsym(text)

    axcauto_name = "TestCtrlPara_AXCAUTO_6188.dat"
    axcauto_source = aw_dir / axcauto_name
    axcauto_output = aw_dir / "TestCtrlPara_AXCAUTO_6188_Normalized.dat"
    axcauto_text = None

    if axcauto_source.is_file():
        try:
            axcauto_text, _, _ = read_aw_file(axcauto_source)
        except OSError:
            axcauto_text = None
            axcauto_source = None
            axcauto_output = None
    else:
        axcauto_source = None
        axcauto_output = None

    return CaseSource(
        excel_row=excel_row,
        case_root=case_root,
        source_aw=source_aw,
        output_aw=output_aw,
        axcauto_source=axcauto_source,
        axcauto_output=axcauto_output,
        axcauto_text=axcauto_text,
        text=text,
        encoding=encoding,
        newline=newline,
        write_commands=write_commands,
        wsym_candidate_count=candidate_count,
        wsym_parse_failed_lines=parse_failed_lines,
    )


# ============================================================
# 十五、单 IP 并发加载全部 AW
# ============================================================

def load_ip_cases(
    ip_dir: Path,
) -> tuple[list[CaseSource], int]:
    case_rows = load_case_paths(ip_dir)

    if not case_rows:
        return [], 0

    if (
        not ENABLE_AW_READ_CONCURRENCY
        or MAX_AW_READ_WORKERS_PER_IP <= 1
        or len(case_rows) <= 1
    ):
        cases: list[CaseSource] = []
        failed = 0

        for excel_row, case_root, am_value in case_rows:
            try:
                case = load_single_case(
                    excel_row,
                    case_root,
                    am_value,
                )
            except Exception as exc:
                failed += 1
                log(
                    f"[CASE LOAD ERROR] UNIT={ip_dir.name} "
                    f"ExcelRow={excel_row}：{exc}"
                )
                continue

            cases.append(case)

        if failed:
            log(
                f"[CASE LOAD SUMMARY] UNIT={ip_dir.name} "
                f"失败={failed}，继续处理成功加载的 "
                f"{len(cases)} 个 Case；后续历史状态可能不完整"
            )

        return cases, failed

    worker_count = min(
        MAX_AW_READ_WORKERS_PER_IP,
        len(case_rows),
    )

    results: list[
        CaseSource | None
    ] = [None] * len(case_rows)

    errors: list[
        tuple[int, Exception]
    ] = []

    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix=f"aw-{ip_dir.name}",
    ) as executor:

        future_map = {}

        for order, (
            excel_row,
            case_root,
            am_value,
        ) in enumerate(case_rows):

            future = executor.submit(
                load_single_case,
                excel_row,
                case_root,
                am_value,
            )

            future_map[future] = (
                order,
                excel_row,
            )

        pending = set(future_map.keys())
        completed = 0

        while pending:
            done, pending = wait(
                pending,
                timeout=AW_READ_HEARTBEAT_SECONDS,
                return_when=FIRST_COMPLETED,
            )

            if not done:
                log(
                    f"[AW READ WAIT] IP={ip_dir.name} "
                    f"已完成={completed}/{len(case_rows)}，"
                    f"仍等待={len(pending)}"
                )

                shown = 0

                for future in list(pending):
                    if shown >= AW_WAITING_SAMPLE_COUNT:
                        break

                    order, excel_row = future_map[future]

                    _, case_root, am_value = case_rows[order]

                    aw_name = (
                        am_value
                        if am_value
                        else "TestCtrlPara.dat"
                    )

                    waiting_aw = (
                        case_root
                        / "TestCtrlPara"
                        / aw_name
                    )

                    log(
                        f"    [WAITING] ExcelRow={excel_row} "
                        f"AW={waiting_aw}"
                    )

                    shown += 1

                continue

            for future in done:
                order, excel_row = future_map[future]

                try:
                    case = future.result()
                except Exception as exc:
                    errors.append(
                        (excel_row, exc)
                    )
                else:
                    results[order] = case

                completed += 1

                if (
                    completed % 50 == 0
                    or completed == len(case_rows)
                ):
                    log(
                        f"[AW READ] IP={ip_dir.name} "
                        f"{completed}/{len(case_rows)}"
                    )

    errors.sort(
        key=lambda item: item[0]
    )

    for excel_row, exc in errors:
        log(
            f"[CASE LOAD ERROR] UNIT={ip_dir.name} "
            f"ExcelRow={excel_row}：{exc}"
        )

    final_results: list[CaseSource] = []

    for index, case in enumerate(results):
        if case is None:
            excel_row = case_rows[index][0]
            if not any(
                failed_row == excel_row
                for failed_row, _ in errors
            ):
                errors.append(
                    (
                        excel_row,
                        RuntimeError("并发读取后没有结果"),
                    )
                )
                log(
                    f"[CASE LOAD ERROR] UNIT={ip_dir.name} "
                    f"ExcelRow={excel_row}：并发读取后没有结果"
                )
            continue

        final_results.append(case)

    if errors:
        log(
            f"[CASE LOAD SUMMARY] UNIT={ip_dir.name} "
            f"失败={len(errors)}，继续处理成功加载的 "
            f"{len(final_results)} 个 Case；后续历史状态可能不完整"
        )

    return final_results, len(errors)


# ============================================================
# 十六、模板目录 + 诊断
# ============================================================

def build_template_catalog(
    cases: list[CaseSource],
    catalog: DefaultCatalog,
    boards_by_target: dict[str, str],
) -> tuple[
    dict[StateKey, WriteCommand],
    TemplateDiagnostics,
    dict[StateKey, DefaultSpec],
    list[StateKey],
]:
    templates: dict[
        StateKey,
        WriteCommand
    ] = {}

    candidate_count = 0
    parsed_count = 0
    managed_command_count = 0

    unmatched_key_counts: dict[
        StateKey,
        int
    ] = defaultdict(int)

    parse_failed_lines: list[str] = []
    defaults: dict[StateKey, DefaultSpec] = {}
    default_order: list[StateKey] = []

    for case in cases:
        candidate_count += (
            case.wsym_candidate_count
        )

        parsed_count += len(
            case.write_commands
        )

        for line in case.wsym_parse_failed_lines:
            if (
                len(parse_failed_lines)
                < DIAGNOSTIC_SAMPLE_COUNT
            ):
                parse_failed_lines.append(line)

        for command in case.write_commands:
            spec = resolve_default(
                command,
                catalog,
                boards_by_target,
            )

            if spec is None:
                unmatched_key_counts[command.key] += 1
                continue

            key = spec.key

            managed_command_count += 1

            old_spec = defaults.get(key)
            if old_spec is None:
                defaults[key] = spec
                default_order.append(key)
            elif parse_int(old_spec.default_value) != parse_int(
                spec.default_value
            ):
                raise ValueError(
                    "同一状态键解析出不同默认值：\n"
                    f"  key={key}\n"
                    f"  第一次={old_spec.default_value} ({old_spec.source})\n"
                    f"  第二次={spec.default_value} ({spec.source})"
                )

            if key not in templates:
                templates[key] = command

    diagnostics = TemplateDiagnostics(
        candidate_count=candidate_count,
        parsed_count=parsed_count,
        managed_command_count=managed_command_count,
        managed_unique_key_count=len(templates),
        unmatched_key_counts=dict(
            unmatched_key_counts
        ),
        parse_failed_lines=(
            parse_failed_lines
        ),
    )

    return templates, diagnostics, defaults, default_order


def print_template_diagnostics(
    ip_name: str,
    diagnostics: TemplateDiagnostics,
) -> None:
    log(
        f"[DIAG] IP={ip_name} "
        f"WSym候选行={diagnostics.candidate_count}，"
        f"成功解析={diagnostics.parsed_count}，"
        f"命中受管命令={diagnostics.managed_command_count}，"
        f"命中受管唯一Key={diagnostics.managed_unique_key_count}，"
        f"未命中唯一Key={len(diagnostics.unmatched_key_counts)}"
    )

    if diagnostics.parse_failed_lines:
        log(
            f"[DIAG] IP={ip_name} "
            f"WSym解析失败样例 "
            f"(最多 {DIAGNOSTIC_SAMPLE_COUNT} 条)："
        )

        for line in diagnostics.parse_failed_lines:
            log(
                f"    [PARSE FAILED] {line}"
            )

    if diagnostics.unmatched_key_counts:
        log(
            f"[DIAG] IP={ip_name} "
            f"已成功解析但不属于 DSP 默认值 JSON 的 StateKey 样例："
        )

        sorted_items = sorted(
            diagnostics.unmatched_key_counts.items(),
            key=lambda item: (
                -item[1],
                item[0].section,
                item[0].dsp_id,
                item[0].core_id,
                item[0].variable,
                item[0].offset,
            ),
        )

        for key, count in sorted_items[
            :DIAGNOSTIC_SAMPLE_COUNT
        ]:
            log(
                "    [UNMANAGED] "
                f"count={count} "
                f"{key.section} "
                f"dsp={key.dsp_id} "
                f"core={key.core_id} "
                f"offset={key.offset} "
                f"{key.variable}"
            )



def _remove_default_value_lines(
    text: str,
    catalog: DefaultCatalog,
    boards_by_target: dict[str, str],
) -> str:
    lines = text.splitlines()
    new_lines: list[str] = []
    for line in lines:
        command = parse_wsym_line(line)
        if command is not None:
            spec = resolve_default(
                command,
                catalog,
                boards_by_target,
            )
            if spec is not None:
                default_val = spec.default_value
                if parse_int(command.data_token) == parse_int(default_val):
                    continue
        new_lines.append(line)
    newline = "\r\n" if "\r\n" in text else "\n"
    result = newline.join(new_lines)
    if text.endswith(("\n", "\r")):
        result += newline
    return result


# ============================================================
# 十七、Pass 1
# ============================================================

def build_pass1_plans(
    ip_name: str,
    cases: list[CaseSource],
    defaults: dict[StateKey, DefaultSpec],
    default_order: list[StateKey],
    catalog: DefaultCatalog,
    boards_by_target: dict[str, str],
) -> tuple[list[CasePlan], int]:
    """
    按原始执行顺序动态维护受控变量状态。

    关键规则：

    1. DSP 默认值 JSON 只是“受控变量白名单 + 默认恢复值”，
       不是要求每个 IP 必须完整初始化的变量集合。

    2. current_state 初始为空。
       某个受控变量只有在前序原始 Case 中真实出现过以后，
       才进入后续 Case 的继承状态。

    3. 当前 Case 出现某个受控变量：
       - 当前 Case 开头不补这个变量（首次出现时）；
       - 如果写入值等于默认值，删除该 WSym 行，不推进状态；
       - 如果写入值不等于默认值，保留原始 WSym；
       - 当前 Case 结尾恢复 JSON 默认值（仅非默认写入的变量）；
       - 写入值非默认时，该变量进入 current_state，
         供下一个 Case 继承。

    4. 已经进入 current_state 的变量：
       每个后续 Case 开头都显式补写最近一次非默认历史状态。

    5. 当前 Case 结束时恢复：
       - 本 Case 开头补写过的全部受控变量；
       - 本 Case 原始 AW 自己写过且写入值非默认的全部受控变量。

    6. current_state 只由原始 AW 中的 WSym 推进，
       且仅当写入值不等于默认值时才推进。
       写入值等于默认值的 WSym 不推进状态，不继承到下一个 Case。
       新增的前置和恢复脚本绝不参与状态推进。
    """

    # --------------------------------------------------------
    # 动态历史状态。
    #
    # 初始为空，而不是把 JSON 中的全部变量塞进来。
    # 只有原始 AW 真实出现过的受控变量才进入这里。
    # --------------------------------------------------------

    current_state: dict[
        StateKey,
        str,
    ] = {}

    # 最近一次原始 Case 对该状态项的真实写入命令。
    # 后续 Case 前置补写时直接复用它的真实格式。
    current_templates: dict[
        StateKey,
        WriteCommand,
    ] = {}

    plans: list[CasePlan] = []
    pass1_failed = 0

    for case_index, case in enumerate(
        cases,
        start=1,
    ):
        # ====================================================
        # 1. 当前 Case 入口状态
        #
        # 只补“前序 Case 已经出现过”的受控变量。
        # ====================================================

        front_lines: list[str] = []

        front_template_by_key: dict[
            StateKey,
            WriteCommand,
        ] = {}

        for key in default_order:
            if key not in current_state:
                continue

            template = current_templates.get(
                key
            )

            if template is None:
                # 理论上不会出现：
                # current_state 和 current_templates 同步推进。
                log(
                    f"[STATE WARN] IP={ip_name} "
                    f"Case#{case_index} "
                    f"已有状态但没有模板："
                    f"{key.section} "
                    f"dsp={key.dsp_id} "
                    f"core={key.core_id} "
                    f"offset={key.offset} "
                    f"{key.variable}"
                )
                continue

            value = current_state[key]

            # 即使 value == default，也照样写入。
            front_lines.append(
                template.replace_data(
                    value
                )
            )

            front_template_by_key[
                key
            ] = template

        cleaned_text = _remove_default_value_lines(
            case.text,
            catalog,
            boards_by_target,
        )

        try:
            pass1_text = (
                insert_after_testctrlinfo(
                    cleaned_text,
                    front_lines,
                    case.newline,
                )
            )
        except Exception as exc:
            pass1_failed += 1

            log(
                f"[PASS1 ERROR] "
                f"IP={ip_name} "
                f"Case#{case_index} "
                f"ExcelRow={case.excel_row} "
                f"AW={case.source_aw}：{exc}"
            )

            # 当前 Case 虽然不能生成 Normalized，
            # 但原始执行顺序中的状态仍然必须继续推进。
            for command in case.write_commands:
                spec = resolve_default(
                    command,
                    catalog,
                    boards_by_target,
                )

                if spec is None:
                    continue

                key = spec.key

                if parse_int(command.data_token) == parse_int(
                    spec.default_value
                ):
                    continue

                current_state[key] = (
                    command.data_token
                )

                current_templates[key] = (
                    command
                )

            continue

        # ====================================================
        # 2. 当前 Case 自己写过非默认值的受控变量
        #
        # 同一状态项写多次时取最后一次，作为：
        #   - Case 结束后的历史状态；
        #   - 当前 Case 恢复默认值时的优先模板。
        # ====================================================

        case_last_write: dict[
            StateKey,
            WriteCommand,
        ] = {}

        for command in case.write_commands:
            spec = resolve_default(
                command,
                catalog,
                boards_by_target,
            )

            if spec is None:
                continue

            key = spec.key

            if parse_int(command.data_token) == parse_int(
                spec.default_value
            ):
                continue

            case_last_write[
                key
            ] = command

        # ====================================================
        # 3. 构造 Pass2 恢复脚本
        #
        # 恢复集合 =
        #   前置补写的受控变量
        #   ∪
        #   当前 Case 原始 AW 自己写过非默认值的受控变量
        # ====================================================

        recovery_lines: list[str] = []

        for key in default_order:
            if (
                key not in front_template_by_key
                and key not in case_last_write
            ):
                continue

            # 当前 Case 自己写过非默认值时，优先使用本 Case 最后一次
            # 真实 WSym 格式；否则使用入口补写所用模板。
            template = (
                case_last_write.get(key)
                or front_template_by_key.get(key)
                or current_templates.get(key)
            )

            if template is None:
                log(
                    f"[RECOVERY WARN] IP={ip_name} "
                    f"Case#{case_index} "
                    f"无法找到恢复模板："
                    f"{key.section} "
                    f"dsp={key.dsp_id} "
                    f"core={key.core_id} "
                    f"offset={key.offset} "
                    f"{key.variable}"
                )
                continue

            default_value = (
                defaults[key].default_value
            )

            recovery_lines.append(
                template.replace_data(
                    default_value
                )
            )

        plans.append(
            CasePlan(
                case=case,
                pass1_text=pass1_text,
                front_lines=front_lines,
                recovery_lines=(
                    recovery_lines
                ),
            )
        )

        # ====================================================
        # 4. 最后才推进“原始顺序”的历史状态
        #
        # 只看原始 AW 的真实 WSym。
        # 新增的 front/recovery 不参与。
        # ====================================================

        for command in case.write_commands:
            spec = resolve_default(
                command,
                catalog,
                boards_by_target,
            )

            if spec is None:
                continue

            key = spec.key

            if parse_int(command.data_token) == parse_int(
                spec.default_value
            ):
                continue

            current_state[key] = (
                command.data_token
            )

            current_templates[key] = (
                command
            )

    return plans, pass1_failed


# ============================================================
# 十八、Pass 2
# ============================================================

def execute_pass2(
    ip_name: str,
    plans: list[CasePlan],
    catalog: DefaultCatalog,
    boards_by_target: dict[str, str],
) -> tuple[int, int]:
    success = 0
    failed = 0

    for index, plan in enumerate(
        plans,
        start=1,
    ):
        case = plan.case

        try:
            final_text = (
                insert_before_recovery_tail(
                    plan.pass1_text,
                    plan.recovery_lines,
                    case.newline,
                )
            )
        except Exception as exc:
            failed += 1

            log(
                f"[PASS2 ERROR] "
                f"IP={ip_name} "
                f"Plan#{index} "
                f"ExcelRow={case.excel_row} "
                f"AW={case.source_aw}：{exc}"
            )

            continue

        try:
            output_exists = case.output_aw.exists()
        except Exception as exc:
            failed += 1

            log(
                f"[CASE ERROR] IP={ip_name} "
                f"ExcelRow={case.excel_row} "
                f"检查输出路径失败，跳过该 Case：{exc}"
            )
            continue

        if not OVERWRITE_NORMALIZED and output_exists:
            failed += 1

            log(
                f"[SKIP OUTPUT] 已存在：{case.output_aw}"
            )

            continue

        try:
            write_aw_file(
                case.output_aw,
                final_text,
                case.encoding,
            )
        except Exception as exc:
            failed += 1

            log(
                f"[WRITE ERROR] "
                f"IP={ip_name} "
                f"ExcelRow={case.excel_row} "
                f"输出={case.output_aw}：{exc}"
            )

            continue

        if (
            case.axcauto_source is not None
            and case.axcauto_output is not None
            and case.axcauto_text is not None
        ):
            try:
                axcauto_cleaned = _remove_default_value_lines(
                    case.axcauto_text,
                    catalog,
                    boards_by_target,
                )
                axcauto_pass1 = insert_after_testctrlinfo(
                    axcauto_cleaned,
                    plan.front_lines,
                    case.newline,
                )
                axcauto_final = insert_before_recovery_tail(
                    axcauto_pass1,
                    plan.recovery_lines,
                    case.newline,
                )
                write_aw_file(
                    case.axcauto_output,
                    axcauto_final,
                    case.encoding,
                )
            except Exception as exc:
                log(
                    f"[AXCAUTO WRITE WARN] "
                    f"IP={ip_name} "
                    f"ExcelRow={case.excel_row} "
                    f"输出={case.axcauto_output}：{exc}"
                )

        success += 1

    return success, failed


# ============================================================
# 十九、IP 选择
# ============================================================

def select_ip_dirs(
    root: Path,
) -> list[Path]:
    log(
        f"[IP SCAN] 开始选择IP，REMOTE_ROOT={root}"
    )

    # --------------------------------------------------------
    # 指定 IP 模式：
    # 不远程枚举、不 is_dir()。
    # 直接构造路径，后续读取 xls 自然确认。
    # --------------------------------------------------------

    if not RUN_ALL_IPS:
        log(
            "[IP SCAN] 当前模式：只处理 TARGET_IPS；"
            "不预扫描远程目录"
        )

        result = [
            root / ip
            for ip in TARGET_IPS
        ]

        log(
            f"[IP SCAN] 已构造 {len(result)} 个目标 IP 路径"
        )

        return result

    # --------------------------------------------------------
    # 全量模式才枚举 REMOTE_ROOT。
    # --------------------------------------------------------

    log(
        "[IP SCAN] 当前模式：扫描 REMOTE_ROOT 下全部直接子目录"
    )

    selected: list[Path] = []

    scan_start = time.perf_counter()

    try:
        with os.scandir(str(root)) as iterator:
            for entry in iterator:
                try:
                    if not entry.is_dir():
                        continue
                except OSError as exc:
                    log(
                        f"[IP SCAN WARN] "
                        f"无法判断目录 {entry.name}：{exc}"
                    )
                    continue

                selected.append(
                    Path(entry.path)
                )

                if len(selected) % 20 == 0:
                    log(
                        f"[IP SCAN] 已发现 {len(selected)} 个目录..."
                    )

    except OSError as exc:
        elapsed = (
            time.perf_counter()
            - scan_start
        )

        raise RuntimeError(
            f"扫描远程根目录失败，耗时={elapsed:.2f}s："
            f"{root}：{exc}"
        ) from exc

    selected.sort(
        key=lambda path: path.name.lower()
    )

    elapsed = (
        time.perf_counter()
        - scan_start
    )

    log(
        f"[IP SCAN] 全量扫描完成，"
        f"目录数={len(selected)}，耗时={elapsed:.2f}s"
    )

    return selected


# ============================================================
# 二十、IP 子目录执行表发现
# ============================================================

def find_ip_units(
    ip_dir: Path,
) -> list[Path]:
    """
    发现 IP 路径下所有包含执行表的处理单元。

    一个目录只要包含 用例执行列表_5G.xls，就是一个独立的处理单元。
    检查范围：
      1. ip_dir 自身
      2. ip_dir 的直接子目录（不递归）

    每个处理单元完全独立，不存在状态继承。
    """

    units: list[Path] = []

    # 1. IP 根目录自身
    try:
        if (ip_dir / EXECUTION_XLS_NAME).is_file():
            units.append(ip_dir)
    except OSError as exc:
        log(
            f"[IP UNIT WARN] IP={ip_dir.name} "
            f"检查根目录执行表失败：{exc}"
        )

    # 2. 直接子目录（不递归）
    try:
        with os.scandir(str(ip_dir)) as iterator:
            for entry in iterator:
                try:
                    if not entry.is_dir():
                        continue
                except OSError as exc:
                    log(
                        f"[IP UNIT WARN] IP={ip_dir.name} "
                        f"无法判断子目录 {entry.name}：{exc}"
                    )
                    continue

                child_path = Path(entry.path)

                try:
                    if (child_path / EXECUTION_XLS_NAME).is_file():
                        units.append(child_path)
                except OSError as exc:
                    log(
                        f"[IP UNIT WARN] IP={ip_dir.name} "
                        f"检查子目录 {entry.name} 执行表失败：{exc}"
                    )
                    continue
    except OSError as exc:
        log(
            f"[IP UNIT WARN] IP={ip_dir.name} "
            f"扫描子目录失败：{exc}"
        )

    return units


# ============================================================
# 二十一、处理单个 IP
# ============================================================

def process_ip(
    ip_dir: Path,
    catalog: DefaultCatalog,
    board_mappings: dict[str, dict[str, str]],
) -> tuple[int, int]:
    ip_name = ip_dir.name

    log("=" * 90)
    log(f"[IP] {ip_name}")
    log("=" * 90)

    boards_by_target = board_mappings.get(ip_name)
    if boards_by_target is None:
        log(
            f"[SKIP IP] {ip_name}："
            "环境版型映射 JSON 中不存在该 IP"
        )
        return 0, 0

    # --------------------------------------------------------
    # 发现所有包含执行表的处理单元
    # （IP 根目录 + 含执行表的直接子目录）
    # --------------------------------------------------------

    units = find_ip_units(ip_dir)

    if not units:
        log(
            f"[ABORT IP] {ip_name}："
            f"IP根目录及子目录均未找到{EXECUTION_XLS_NAME}"
        )
        return 0, 1

    log(
        f"[IP UNITS] {ip_name} "
        f"发现 {len(units)} 个处理单元"
    )

    # --------------------------------------------------------
    # 对每个处理单元独立执行完整流水线
    # --------------------------------------------------------

    total_success = 0
    total_failed = 0

    for unit_dir in units:
        # 日志中区分 IP 根目录 vs 子目录
        if unit_dir == ip_dir:
            unit_label = ip_name
        else:
            unit_label = f"{ip_name}/{unit_dir.name}"

        log("-" * 70)
        log(f"[UNIT] {unit_label}")
        log("-" * 70)

        try:
            cases, load_failed = load_ip_cases(
                unit_dir
            )
        except Exception as exc:
            log(
                f"[ABORT UNIT] {unit_label}：{exc}"
            )
            total_failed += 1
            continue

        total_failed += load_failed

        log(
            f"[INPUT] UNIT={unit_label} "
            f"成功加载Case={len(cases)}，加载失败={load_failed}"
        )

        if not cases:
            log(
                f"[ABORT UNIT] {unit_label}：执行表没有有效 Case"
            )
            if load_failed == 0:
                total_failed += 1
            continue

        # ------------------------------------------------
        # 只做诊断：
        #
        # DSP 默认值 JSON 中有多少变量，并不要求当前 IP 全部出现。
        # 当前 IP 实际出现几个受控 StateKey，就只处理几个。
        # ------------------------------------------------

        try:
            (
                observed_templates,
                diagnostics,
                defaults,
                default_order,
            ) = build_template_catalog(
                cases,
                catalog,
                boards_by_target,
            )

            log(
                f"[CONTROLLED] UNIT={unit_label} "
                f"JSON逻辑变量="
                f"{len(catalog.common) + len(catalog.board_sensitive)}，"
                f"当前单元实际出现受控Key={len(observed_templates)}"
            )

            print_template_diagnostics(
                unit_label,
                diagnostics,
            )
        except Exception as exc:
            log(
                f"[UNIT ERROR] {unit_label} "
                f"模板和默认值解析失败，跳过该处理单元：{exc}"
            )
            total_failed += 1
            continue

        # ------------------------------------------------
        # Pass 1
        # ------------------------------------------------

        log(
            f"[PASS 1] UNIT={unit_label} "
            "开始按原始顺序动态继承已出现的受控变量..."
        )

        try:
            plans, pass1_failed = (
                build_pass1_plans(
                    ip_name=unit_label,
                    cases=cases,
                    defaults=defaults,
                    default_order=default_order,
                    catalog=catalog,
                    boards_by_target=boards_by_target,
                )
            )
        except Exception as exc:
            log(
                f"[UNIT ERROR] {unit_label} "
                f"Pass 1 未知异常，跳过该处理单元：{exc}"
            )
            total_failed += 1
            continue

        log(
            f"[PASS 1] UNIT={unit_label} "
            f"形成计划={len(plans)}，"
            f"失败Case={pass1_failed}"
        )

        # ------------------------------------------------
        # Pass 2
        # ------------------------------------------------

        log(
            f"[PASS 2] UNIT={unit_label} "
            "开始恢复前置变量和当前Case受控变量到默认值..."
        )

        try:
            success, pass2_failed = execute_pass2(
                unit_label,
                plans,
                catalog,
                boards_by_target,
            )
        except Exception as exc:
            log(
                f"[UNIT ERROR] {unit_label} "
                f"Pass 2 未知异常，跳过该处理单元：{exc}"
            )
            total_failed += 1
            continue

        processing_failed = (
            pass1_failed
            + pass2_failed
        )

        unit_failed = load_failed + processing_failed

        log(
            f"[UNIT DONE] {unit_label}："
            f"成功={success}，失败={unit_failed}"
        )

        total_success += success
        total_failed += processing_failed

    log(
        f"[IP DONE] {ip_name}："
        f"成功={total_success}，失败={total_failed}"
    )

    return total_success, total_failed


# ============================================================
# 二十一、主程序
# ============================================================

def main() -> None:
    # --------------------------------------------------------
    # 远程文件系统阻塞监控：
    # 每 60 秒打印一次所有线程当前堆栈。
    # --------------------------------------------------------

    faulthandler.enable(
        file=sys.stderr
    )

    faulthandler.dump_traceback_later(
        FAULT_DUMP_SECONDS,
        repeat=True,
        file=sys.stderr,
    )

    try:
        log("=" * 90)
        log("AW 顺序状态解耦 / Normalized 生成")
        log("=" * 90)

        # ----------------------------------------------------
        # 默认变量与环境版型
        # ----------------------------------------------------

        catalog = load_default_catalog(
            DSP_DEFAULTS_JSON
        )

        board_mappings = load_board_mappings(
            BOARD_MAPPING_JSON
        )

        common_count = len(catalog.common)
        sensitive_count = len(
            catalog.board_sensitive
        )

        log(
            f"[DEFAULT] common变量={common_count}，"
            f"board_sensitive变量={sensitive_count}"
        )

        log(
            f"[BOARD] 已映射IP={len(board_mappings)}"
        )

        # ----------------------------------------------------
        # IP
        # ----------------------------------------------------

        ip_dirs = select_ip_dirs(
            REMOTE_ROOT
        )

        log(
            f"[IP] 本次处理数量：{len(ip_dirs)}"
        )

        if not ip_dirs:
            log("没有需要处理的 IP。")
            return

        if (
            ENABLE_IP_CONCURRENCY
            and MAX_IP_WORKERS > 1
            and len(ip_dirs) > 1
        ):
            actual_ip_workers = min(
                MAX_IP_WORKERS,
                len(ip_dirs),
            )
        else:
            actual_ip_workers = 1

        if (
            ENABLE_AW_READ_CONCURRENCY
            and MAX_AW_READ_WORKERS_PER_IP > 1
        ):
            actual_aw_workers = (
                MAX_AW_READ_WORKERS_PER_IP
            )
        else:
            actual_aw_workers = 1

        log(
            f"[CONCURRENCY] "
            f"IP workers={actual_ip_workers}，"
            f"AW read workers/IP={actual_aw_workers}"
        )

        log(
            f"[CONCURRENCY] "
            f"理论最大远程 AW 并发≈"
            f"{actual_ip_workers * actual_aw_workers}"
        )

        total_success = 0
        total_failed = 0
        ip_results: dict[
            str,
            tuple[int, int]
        ] = {}

        # ----------------------------------------------------
        # 串行 IP
        # ----------------------------------------------------

        if actual_ip_workers == 1:
            for ip_dir in ip_dirs:
                try:
                    success, failed = process_ip(
                        ip_dir,
                        catalog,
                        board_mappings,
                    )
                except Exception as exc:
                    success = 0
                    failed = 1

                    log(
                        f"[IP ERROR] {ip_dir.name}：{exc}；"
                        "已跳过该 IP，继续处理后续 IP"
                    )

                ip_results[ip_dir.name] = (
                    success,
                    failed,
                )

                total_success += success
                total_failed += failed

        # ----------------------------------------------------
        # 并发 IP
        # ----------------------------------------------------

        else:
            with ThreadPoolExecutor(
                max_workers=actual_ip_workers,
                thread_name_prefix="ip",
            ) as executor:

                future_map = {
                    executor.submit(
                        process_ip,
                        ip_dir,
                        catalog,
                        board_mappings,
                    ): ip_dir
                    for ip_dir in ip_dirs
                }

                completed_ip_count = 0

                for future in as_completed(
                    future_map
                ):
                    ip_dir = future_map[
                        future
                    ]

                    try:
                        success, failed = (
                            future.result()
                        )
                    except Exception as exc:
                        success = 0
                        failed = 1

                        log(
                            f"[IP ERROR] "
                            f"{ip_dir.name}：{exc}"
                        )

                    ip_results[
                        ip_dir.name
                    ] = (
                        success,
                        failed,
                    )

                    total_success += success
                    total_failed += failed

                    completed_ip_count += 1

                    log(
                        f"[IP PROGRESS] "
                        f"{completed_ip_count}/{len(ip_dirs)} "
                        f"完成：{ip_dir.name}，"
                        f"成功={success}，失败={failed}"
                    )

        # ----------------------------------------------------
        # 总结
        # ----------------------------------------------------

        log("=" * 90)
        log("全部处理完成")
        log("=" * 90)

        log(
            f"处理 IP 数量：{len(ip_dirs)}"
        )

        log(
            f"成功生成 Normalized AW：{total_success}"
        )

        log(
            f"失败 / 中止：{total_failed}"
        )

        log("各 IP 结果：")

        for ip_dir in ip_dirs:
            result = ip_results.get(
                ip_dir.name
            )

            if result is None:
                log(
                    f"    {ip_dir.name}: 无结果"
                )
                continue

            success, failed = result

            log(
                f"    {ip_dir.name}: "
                f"成功={success}，失败={failed}"
            )

    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
