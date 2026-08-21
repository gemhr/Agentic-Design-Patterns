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
1. 每个 IP 独立从 default.txt 中的默认值初始化 current_state。
2. 严格按 用例执行列表_5G.xls 原始顺序扫描。
3. 在每个 Case 的：

       set TestCtrlInfoList {

   下一行插入“前序 Case 中已经真实出现过”的受控变量历史状态。
4. 从未在前序 Case 中出现过的受控变量不主动插入。
5. 即使已跟踪变量的当前状态 == 默认值，也照样显式写入。
6. current_state 只根据“原始 AW 中的 WSym”推进。
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
2. Pass 1 前置插入的全部已跟踪受控变量都恢复到 default.txt 默认值。
3. 当前 Case 自己修改过的受管变量也恢复。
4. 同一个状态项在当前 Case 中写多次：
   - 原脚本全部保留；
   - 历史状态取最后一次；
   - 恢复只写一次；
   - 恢复模板优先使用该 Case 最后一次真实写入格式。

状态键
======
暂时忽略 DSP ID（WSym 第一个参数）。

DSP_WSym:
    (BBH/BBL, Core ID, Variable, Offset=0)

DSP_WSymOffset:
    (BBH/BBL, Core ID, Variable, Offset)

DSP_WSymAuto:
    (BBH/BBL, Core ID=5, Variable, Offset=0)

板型
====
    BaseBandBoard -> BBH
    enb0          -> BBH
    其他 enb数字   -> BBL

默认值 TXT
==========
例如：

    BBL    DSP_RSym(0,5,"g_lrcDynSpecSwitch",4)             1
    BBH    DSP_RSym(0,1,"g_puschNOrthDmrsMngFrmType",4)     无

“无”表示该变量不参与：
    - 状态跟踪
    - 前置写入
    - 默认恢复

但不会删除原 AW 中已有命令。

DSP_RSym 的 len 用来反推 Offset：

    offset = len - 4

当前 Offset 要求必须是 4 的整数倍。

受控变量规则
============
default.txt 只承担两个职责：

1. 判断某条 WSym 是否属于受控变量；
2. 提供该受控变量的默认恢复值。

并不要求每个 IP 都必须出现 default.txt 中的全部变量。

状态集合按当前 IP 的原始执行顺序动态增长：

- 某个受控变量从未在前序 Case 中出现：
  不在当前 Case 开头补写；
- 当前 Case 第一次真实写到该受控变量：
  保留原始写入，并在当前 Case 结尾恢复默认值；
- 从下一个 Case 开始：
  该变量进入历史状态链，按前序 Case 最后的真实写入值在开头补写；
- 即使历史值等于默认值，也照样显式补写；
- 当前 Case 结束时，所有开头补写过的受控变量和当前 Case 自己写过的受控变量，
  都恢复到 default.txt 默认值。

前置/恢复脚本始终复用当前 IP 中真实出现过的 WSym 行作为模板，
只替换真正的数据参数。

本脚本会打印详细诊断：
    - WSym 候选行总数
    - 成功解析数
    - 命中受管变量数
    - 未命中 StateKey 样例
    - 解析失败 WSym 样例

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

DEFAULT_VALUE_TXT = Path(
    __file__
).parent / "default.txt"

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

RSYM_PATTERN = re.compile(
    r'DSP_RSym\s*'
    r'\(\s*'
    r'([^,]+?)\s*,\s*'
    r'([^,]+?)\s*,\s*'
    r'\\?"([^"]+?)\\?"\s*,\s*'
    r'([^)]+?)'
    r'\s*\)',
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
class StateKey:
    section: str
    core_id: int
    variable: str
    offset: int


@dataclass
class DefaultSpec:
    key: StateKey
    dsp_id: int
    read_length: int
    default_value: str
    source_line: int


@dataclass
class WriteCommand:
    raw_line: str
    command_type: str
    section: str
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
# 八、默认值 TXT
# ============================================================

def parse_default_line(
    line: str,
    line_number: int,
) -> tuple[str, str, str] | None:
    stripped = line.strip()

    if not stripped or stripped.startswith("#"):
        return None

    # 优先按 TAB
    parts = [
        part.strip()
        for part in line.rstrip("\r\n").split("\t")
    ]

    if len(parts) >= 3:
        return (
            parts[0],
            "\t".join(parts[1:-1]).strip(),
            parts[-1],
        )

    # 空格兜底
    match = re.match(
        r"^\s*"
        r"(BBH|BBL)"
        r"\s+"
        r"(DSP_RSym\s*\(.*\))"
        r"\s+"
        r"(\S+)"
        r"\s*$",
        stripped,
        flags=re.IGNORECASE,
    )

    if match is None:
        raise ValueError(
            f"default.txt 第 {line_number} 行格式无法识别：{stripped}"
        )

    return (
        match.group(1),
        match.group(2),
        match.group(3),
    )


def parse_rsym(
    command: str,
) -> tuple[int, int, str, int] | None:
    text = command.replace('\\"', '"')

    match = RSYM_PATTERN.search(text)
    if match is None:
        return None

    dsp_id = parse_int(match.group(1))
    core_id = parse_int(match.group(2))
    variable = match.group(3).strip().strip("\\")
    read_length = parse_int(match.group(4))

    if (
        dsp_id is None
        or core_id is None
        or not variable
        or read_length is None
    ):
        return None

    return dsp_id, core_id, variable, read_length


def load_defaults(
    txt_path: Path,
) -> tuple[dict[StateKey, DefaultSpec], list[StateKey]]:
    if not txt_path.is_file():
        raise FileNotFoundError(
            f"默认值 TXT 不存在：{txt_path}"
        )

    text = txt_path.read_text(
        encoding="utf-8-sig"
    )

    defaults: dict[StateKey, DefaultSpec] = {}
    default_order: list[StateKey] = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        parsed = parse_default_line(
            line,
            line_number,
        )

        if parsed is None:
            continue

        section, rsym_command, default_value = parsed
        section = section.upper()

        if section not in ("BBH", "BBL"):
            raise ValueError(
                f"default.txt 第 {line_number} 行板型非法：{section!r}"
            )

        # “无”完全不参与管理
        if default_value.strip() == "无":
            continue

        rsym = parse_rsym(rsym_command)

        if rsym is None:
            raise ValueError(
                f"default.txt 第 {line_number} 行 DSP_RSym 无法解析："
                f"{rsym_command}"
            )

        dsp_id, core_id, variable, read_length = rsym

        offset = read_length - 4

        if offset < 0:
            raise ValueError(
                f"default.txt 第 {line_number} 行读取长度={read_length}，"
                "无法得到合法 Offset"
            )

        if offset % 4 != 0:
            raise ValueError(
                f"default.txt 第 {line_number} 行 Offset={offset}，"
                "不是 4 的整数倍"
            )

        if parse_int(default_value) is None:
            raise ValueError(
                f"default.txt 第 {line_number} 行默认值不是合法整数："
                f"{default_value!r}"
            )

        key = StateKey(
            section=section,
            core_id=core_id,
            variable=variable,
            offset=offset,
        )

        spec = DefaultSpec(
            key=key,
            dsp_id=dsp_id,
            read_length=read_length,
            default_value=default_value,
            source_line=line_number,
        )

        old = defaults.get(key)

        if old is not None:
            if parse_int(old.default_value) != parse_int(default_value):
                raise ValueError(
                    "default.txt 出现同一状态键不同默认值：\n"
                    f"  key={key}\n"
                    f"  第一次={old.default_value} "
                    f"(line {old.source_line})\n"
                    f"  第二次={default_value} "
                    f"(line {line_number})"
                )
            continue

        defaults[key] = spec
        default_order.append(key)

    return defaults, default_order


# ============================================================
# 九、AW target -> BBH / BBL
# ============================================================

def get_section_from_aw_line(line: str) -> str | None:
    match = AW_FIRST_TWO_FIELDS_PATTERN.match(line)
    if match is None:
        return None

    target = match.group(2).strip().lower()

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
    if section is None:
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
) -> list[CaseSource]:
    case_rows = load_case_paths(ip_dir)

    if not case_rows:
        return []

    if (
        not ENABLE_AW_READ_CONCURRENCY
        or MAX_AW_READ_WORKERS_PER_IP <= 1
        or len(case_rows) <= 1
    ):
        return [
            load_single_case(
                excel_row,
                case_root,
                am_value,
            )
            for (
                excel_row,
                case_root,
                am_value,
            ) in case_rows
        ]

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

    if errors:
        errors.sort(
            key=lambda item: item[0]
        )

        error_lines = []

        for excel_row, exc in errors[:10]:
            error_lines.append(
                f"ExcelRow={excel_row}: {exc}"
            )

        if len(errors) > 10:
            error_lines.append(
                f"...另外还有 {len(errors) - 10} 个错误"
            )

        raise RuntimeError(
            f"IP={ip_dir.name} 共有 {len(errors)} 个 AW 加载失败，"
            "无法安全推进顺序状态：\n"
            + "\n".join(error_lines)
        )

    final_results: list[CaseSource] = []

    for index, case in enumerate(results):
        if case is None:
            raise RuntimeError(
                f"IP={ip_dir.name} 内部错误："
                f"第 {index + 1} 个 Case 并发读取后没有结果"
            )

        final_results.append(case)

    return final_results


# ============================================================
# 十六、模板目录 + 诊断
# ============================================================

def build_template_catalog(
    cases: list[CaseSource],
    defaults: dict[StateKey, DefaultSpec],
) -> tuple[
    dict[StateKey, WriteCommand],
    TemplateDiagnostics,
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
            key = command.key

            if key not in defaults:
                unmatched_key_counts[key] += 1
                continue

            managed_command_count += 1

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

    return templates, diagnostics


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
            f"已成功解析但不属于 default.txt 的 StateKey 样例："
        )

        sorted_items = sorted(
            diagnostics.unmatched_key_counts.items(),
            key=lambda item: (
                -item[1],
                item[0].section,
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
                f"core={key.core_id} "
                f"offset={key.offset} "
                f"{key.variable}"
            )



def _remove_default_value_lines(
    text: str,
    defaults: dict[StateKey, DefaultSpec],
) -> str:
    lines = text.splitlines()
    new_lines: list[str] = []
    for line in lines:
        command = parse_wsym_line(line)
        if command is not None:
            key = command.key
            if key in defaults:
                default_val = defaults[key].default_value
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
) -> tuple[list[CasePlan], int]:
    """
    按原始执行顺序动态维护受控变量状态。

    关键规则：

    1. default.txt 只是“受控变量白名单 + 默认恢复值”，
       不是要求每个 IP 必须完整初始化的变量集合。

    2. current_state 初始为空。
       某个受控变量只有在前序原始 Case 中真实出现过以后，
       才进入后续 Case 的继承状态。

    3. 当前 Case 出现某个受控变量：
       - 当前 Case 开头不补这个变量（首次出现时）；
       - 如果写入值等于默认值，删除该 WSym 行，不推进状态；
       - 如果写入值不等于默认值，保留原始 WSym；
       - 当前 Case 结尾恢复 default.txt 默认值（仅非默认写入的变量）；
       - 写入值非默认时，该变量进入 current_state，
         供下一个 Case 继承。

    4. 已经进入 current_state 的变量：
       每个后续 Case 开头都显式补写历史状态，
       即使历史值等于默认值也照样写。

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
    # 初始为空，而不是把 default.txt 全部塞进来。
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
            case.text, defaults
        )

        try:
            pass1_text = (
                insert_after_testctrlinfo(
                    cleaned_text,
                    front_lines,
                    case.newline,
                )
            )
        except ValueError as exc:
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
                key = command.key

                if key not in defaults:
                    continue

                if parse_int(command.data_token) == parse_int(
                    defaults[key].default_value
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
        # 2. 当前 Case 自己写过的受控变量
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
            key = command.key

            if key not in defaults:
                continue

            if parse_int(command.data_token) == parse_int(
                defaults[key].default_value
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
        #   当前 Case 原始 AW 自己写过的受控变量
        # ====================================================

        recovery_lines: list[str] = []

        for key in default_order:
            if (
                key not in front_template_by_key
                and key not in case_last_write
            ):
                continue

            # 当前 Case 自己写过时，优先使用本 Case 最后一次
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
            key = command.key

            if key not in defaults:
                continue

            if parse_int(command.data_token) == parse_int(
                defaults[key].default_value
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
    defaults: dict[StateKey, DefaultSpec],
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
        except ValueError as exc:
            failed += 1

            log(
                f"[PASS2 ERROR] "
                f"IP={ip_name} "
                f"Plan#{index} "
                f"ExcelRow={case.excel_row} "
                f"AW={case.source_aw}：{exc}"
            )

            continue

        if (
            not OVERWRITE_NORMALIZED
            and case.output_aw.exists()
        ):
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
        except OSError as exc:
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
                    case.axcauto_text, defaults
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
            except (ValueError, OSError) as exc:
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
    defaults: dict[StateKey, DefaultSpec],
    default_order: list[StateKey],
) -> tuple[int, int]:
    ip_name = ip_dir.name

    log("=" * 90)
    log(f"[IP] {ip_name}")
    log("=" * 90)

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
            cases = load_ip_cases(
                unit_dir
            )
        except Exception as exc:
            log(
                f"[ABORT UNIT] {unit_label}：{exc}"
            )
            total_failed += 1
            continue

        log(
            f"[INPUT] UNIT={unit_label} Case数量={len(cases)}"
        )

        if not cases:
            log(
                f"[ABORT UNIT] {unit_label}：执行表没有有效 Case"
            )
            total_failed += 1
            continue

        # ------------------------------------------------
        # 只做诊断：
        #
        # default.txt 中有多少变量，并不要求当前 IP 全部出现。
        # 当前 IP 实际出现几个受控 StateKey，就只处理几个。
        # ------------------------------------------------

        (
            observed_templates,
            diagnostics,
        ) = build_template_catalog(
            cases,
            defaults,
        )

        log(
            f"[CONTROLLED] UNIT={unit_label} "
            f"default.txt受控变量={len(defaults)}，"
            f"当前单元实际出现受控Key={len(observed_templates)}"
        )

        print_template_diagnostics(
            unit_label,
            diagnostics,
        )

        # ------------------------------------------------
        # Pass 1
        # ------------------------------------------------

        log(
            f"[PASS 1] UNIT={unit_label} "
            "开始按原始顺序动态继承已出现的受控变量..."
        )

        plans, pass1_failed = (
            build_pass1_plans(
                ip_name=unit_label,
                cases=cases,
                defaults=defaults,
                default_order=default_order,
            )
        )

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

        success, pass2_failed = execute_pass2(
            unit_label,
            plans,
            defaults,
        )

        unit_failed = (
            pass1_failed
            + pass2_failed
        )

        log(
            f"[UNIT DONE] {unit_label}："
            f"成功={success}，失败={unit_failed}"
        )

        total_success += success
        total_failed += unit_failed

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
        # 默认变量
        # ----------------------------------------------------

        defaults, default_order = (
            load_defaults(
                DEFAULT_VALUE_TXT
            )
        )

        bbh_count = sum(
            1
            for key in defaults
            if key.section == "BBH"
        )

        bbl_count = sum(
            1
            for key in defaults
            if key.section == "BBL"
        )

        log(
            f"[DEFAULT] 有效受管变量：{len(defaults)}"
        )

        log(
            f"[DEFAULT] BBH={bbh_count}，BBL={bbl_count}"
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
                success, failed = process_ip(
                    ip_dir,
                    defaults,
                    default_order,
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
                        defaults,
                        default_order,
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
