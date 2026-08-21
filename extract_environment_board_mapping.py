#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
环境版型配置提取脚本

用途
====
扫描 REMOTE_ROOT 下的环境文件夹：

    IP目录
    ├─ 用例执行列表_5G.xls
    └─ 环境基本信息.xls

只有存在“用例执行列表_5G.xls”的文件夹才视为有效环境候选。

读取：
    环境基本信息.xls
    -> Sheet: 单板配置
    -> A列 + J列
    -> 从第4行扫描到 Sheet 实际最后一行

不再使用“J列遇到空行就停止”的旧逻辑，因为中间可能存在：
    - 合并行
    - UE备注行
    - 正常空行
    - 隔几行后继续出现有效配置

正式业务 Target：
    enb0 / enb1 / enb2 / ...

规则：
    enb0             -> BBH
    其他 enb数字      -> BBL

enb_toolX：
    只写入 XLSX 供人工检查；
    不进入正式 JSON 映射。

版型识别规则（大小写不敏感，按优先级）：
    8021_37V200 -> 37
    6138_l      -> 38L
    6182_d      -> 82
    6186        -> 86
    6185        -> 85
    8011        -> 11
    6188        -> 88
    8021        -> 21

特别注意：
    8021_37V200 必须优先于普通 8021，
    保证 37 不会被误判为 21。

输出
====
1. environment_board_mapping.xlsx
   - 汇总
   - 环境版型映射
   - 异常环境

2. environment_board_mapping.json

JSON 正式查询结构：

{
  "environments": {
    "10.150.x.x": {
      "enb0": {
        "group": "BBH",
        "board": "86",
        "raw": "6186G4_h",
        "source_row": 4
      },
      "enb1": {
        "group": "BBL",
        "board": "37",
        "raw": "8021_37V200_xxx",
        "source_row": 5
      }
    }
  },
  "issues": [...]
}

冲突策略
========
同一 IP、同一 enbX 如果重复出现：

1. 多条都识别成同一版型：
   - JSON 保留第一条；
   - XLSX 后续行标记 DUPLICATE_SAME。

2. 识别成不同版型：
   - 认为配置冲突；
   - 该 enbX 不写入 JSON 正式映射；
   - XLSX 标记 CONFLICT；
   - issues 记录 DUPLICATE_CONFLICT。

并发
====
- REMOTE_ROOT 只扫描一次。
- 每个 IP 环境使用 ThreadPoolExecutor 并发读取。
- 每个环境内部按顺序读取两个小 xls。
- 所有线程只负责“读取 + 解析”，不并发写最终 XLSX/JSON。
- 最终汇总后单线程一次性写 XLSX / JSON，避免文件锁和数据竞争。
- 每 30 秒输出一次等待心跳。
- faulthandler 每 120 秒打印线程堆栈，方便定位 UNC/SMB 阻塞。

依赖
====
    pip install xlrd xlsxwriter
"""

from __future__ import annotations

import faulthandler
import ipaddress
import json
import os
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import xlrd
except ImportError as exc:
    raise SystemExit(
        "缺少依赖 xlrd，请先执行：pip install xlrd xlsxwriter"
    ) from exc

try:
    import xlsxwriter
except ImportError as exc:
    raise SystemExit(
        "缺少依赖 xlsxwriter，请先执行：pip install xlrd xlsxwriter"
    ) from exc


# ============================================================
# 一、配置
# ============================================================

REMOTE_ROOT = Path(
    r"\\7.213.207.64\opt\data1\UCI\workspace\UCI_Script\26B\TestCase_26B"
)

EXECUTION_XLS_NAME = "用例执行列表_5G.xls"
ENV_INFO_XLS_NAME = "环境基本信息.xls"
BOARD_SHEET_NAME = "单板配置"

# 默认全量扫描所有环境。
RUN_ALL_IPS = True

# RUN_ALL_IPS=False 时，只处理这里的 IP。
TARGET_IPS: list[str] = [
    # "10.150.102.133",
]

# 输出到脚本所在目录。
OUTPUT_DIR = Path(__file__).parent

OUTPUT_XLSX = OUTPUT_DIR / "environment_board_mapping.xlsx"
OUTPUT_JSON = OUTPUT_DIR / "environment_board_mapping.json"

# ------------------------------------------------------------
# 并发参数
# ------------------------------------------------------------

# 1500 套左右的环境主要是 UNC 小文件 I/O。
# 推荐 8~16。若远程文件服务器压力较大可改成 8。
MAX_WORKERS = 12

# 没有任务完成时，每多少秒打印一次心跳。
HEARTBEAT_SECONDS = 30

# 心跳时最多显示多少个仍在等待的 IP。
WAITING_SAMPLE_COUNT = 8

# faulthandler 堆栈输出周期。
FAULT_DUMP_SECONDS = 120

# ------------------------------------------------------------
# 表格位置
# ------------------------------------------------------------

# Excel 第4行 -> xlrd 0-based = 3
START_ROW_INDEX = 3

# A列 -> 0
COL_A = 0

# J列 -> 9
COL_J = 9


# ============================================================
# 二、版型识别规则
# ============================================================

# 顺序就是优先级。
# 特别注意 8021_37V200 必须在普通 8021 前面。
BOARD_RULES: list[tuple[str, str]] = [
    ("8021_37v200", "37"),
    ("6138_l", "38L"),
    ("6182_d", "82"),
    ("6186", "86"),
    ("6185", "85"),
    ("8011", "11"),
    ("6188", "88"),
    ("8021", "21"),
]

ENB_PATTERN = re.compile(
    r"^enb(\d+)$",
    flags=re.IGNORECASE,
)

ENB_TOOL_PATTERN = re.compile(
    r"^enb_tool(\d+)$",
    flags=re.IGNORECASE,
)


# ============================================================
# 三、日志
# ============================================================

_PRINT_LOCK = threading.Lock()


def log(message: str) -> None:
    with _PRINT_LOCK:
        print(
            f"[{datetime.now():%H:%M:%S}] {message}",
            flush=True,
        )


# ============================================================
# 四、数据结构
# ============================================================

@dataclass
class MappingRow:
    ip: str
    target: str
    group: str
    raw_j: str
    board: str
    record_type: str
    status: str
    source_row: int
    source_file: str


@dataclass
class Issue:
    ip: str
    code: str
    target: str
    raw_j: str
    source_row: int
    detail: str
    source_file: str


@dataclass
class EnvironmentResult:
    ip: str

    # 是否存在 用例执行列表_5G.xls
    is_valid_environment: bool

    # 正式 JSON 映射：
    # enbX -> {group, board, raw, source_row}
    mappings: dict[str, dict[str, Any]]

    rows: list[MappingRow]
    issues: list[Issue]


# ============================================================
# 五、基础函数
# ============================================================

def cell_text(value: Any) -> str:
    """
    xlrd 单元格值转为干净文本。
    """

    if value is None:
        return ""

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    return str(value).strip()


def normalize_target(value: str) -> str:
    return value.strip().lower()


def recognize_board(raw_value: str) -> str | None:
    """
    根据 J 列原始值识别具体版型。
    """

    text = raw_value.strip().lower()

    if not text:
        return None

    for keyword, board in BOARD_RULES:
        if keyword in text:
            return board

    return None


def get_group(target: str) -> str:
    """
    enb0 -> BBH
    其他 enb数字 -> BBL
    """

    return "BBH" if target == "enb0" else "BBL"


def ip_sort_key(value: str) -> tuple:
    """
    IP 优先按真实数字排序；
    非标准 IP 名称退回字符串排序。
    """

    try:
        ip = ipaddress.ip_address(value)
        return (0, int(ip))
    except ValueError:
        return (1, value.lower())


def target_sort_key(target: str) -> tuple:
    match = ENB_PATTERN.fullmatch(target)

    if match:
        return (0, int(match.group(1)))

    match = ENB_TOOL_PATTERN.fullmatch(target)

    if match:
        return (1, int(match.group(1)))

    return (2, target.lower())


def read_file_bytes(path: Path) -> bytes:
    """
    不先 is_file()/exists()，直接 open。
    对 UNC 路径减少一次 SMB round-trip。
    """

    with open(path, "rb") as file:
        return file.read()


def open_xls_from_bytes(
    raw: bytes,
    source_path: Path,
):
    try:
        return xlrd.open_workbook(
            file_contents=raw,
            on_demand=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"xls 解析失败：{source_path}：{exc}"
        ) from exc


def get_board_sheet(workbook):
    """
    优先精确名称；
    再允许工作表名称前后有空格。
    """

    try:
        return workbook.sheet_by_name(
            BOARD_SHEET_NAME
        )
    except xlrd.biffh.XLRDError:
        pass

    for index in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(index)

        if sheet.name.strip() == BOARD_SHEET_NAME:
            return sheet

    raise KeyError(
        f"找不到 Sheet：{BOARD_SHEET_NAME}"
    )


# ============================================================
# 六、处理单个 IP
# ============================================================

def process_ip(ip_dir: Path) -> EnvironmentResult:
    ip = ip_dir.name

    execution_xls = (
        ip_dir
        / EXECUTION_XLS_NAME
    )

    env_info_xls = (
        ip_dir
        / ENV_INFO_XLS_NAME
    )

    # --------------------------------------------------------
    # 1. 只有存在执行表才认为是有效环境
    #
    # 不先 exists/is_file，直接尝试 open。
    # --------------------------------------------------------

    try:
        with open(execution_xls, "rb"):
            pass

    except FileNotFoundError:
        # 不是有效环境，静默跳过。
        return EnvironmentResult(
            ip=ip,
            is_valid_environment=False,
            mappings={},
            rows=[],
            issues=[],
        )

    except OSError as exc:
        # 路径存在性无法可靠判断，保留异常。
        issue = Issue(
            ip=ip,
            code="EXECUTION_LIST_READ_ERROR",
            target="",
            raw_j="",
            source_row=0,
            detail=str(exc),
            source_file=str(execution_xls),
        )

        return EnvironmentResult(
            ip=ip,
            is_valid_environment=True,
            mappings={},
            rows=[],
            issues=[issue],
        )

    # --------------------------------------------------------
    # 2. 读取 环境基本信息.xls
    # --------------------------------------------------------

    try:
        env_raw = read_file_bytes(
            env_info_xls
        )

    except FileNotFoundError:
        issue = Issue(
            ip=ip,
            code="MISSING_ENV_INFO",
            target="",
            raw_j="",
            source_row=0,
            detail=(
                f"有效环境存在 {EXECUTION_XLS_NAME}，"
                f"但缺少 {ENV_INFO_XLS_NAME}"
            ),
            source_file=str(env_info_xls),
        )

        return EnvironmentResult(
            ip=ip,
            is_valid_environment=True,
            mappings={},
            rows=[],
            issues=[issue],
        )

    except OSError as exc:
        issue = Issue(
            ip=ip,
            code="ENV_INFO_READ_ERROR",
            target="",
            raw_j="",
            source_row=0,
            detail=str(exc),
            source_file=str(env_info_xls),
        )

        return EnvironmentResult(
            ip=ip,
            is_valid_environment=True,
            mappings={},
            rows=[],
            issues=[issue],
        )

    # --------------------------------------------------------
    # 3. 解析 xls
    # --------------------------------------------------------

    try:
        workbook = open_xls_from_bytes(
            env_raw,
            env_info_xls,
        )
    except Exception as exc:
        issue = Issue(
            ip=ip,
            code="ENV_INFO_PARSE_ERROR",
            target="",
            raw_j="",
            source_row=0,
            detail=str(exc),
            source_file=str(env_info_xls),
        )

        return EnvironmentResult(
            ip=ip,
            is_valid_environment=True,
            mappings={},
            rows=[],
            issues=[issue],
        )

    try:
        try:
            sheet = get_board_sheet(
                workbook
            )
        except KeyError as exc:
            issue = Issue(
                ip=ip,
                code="MISSING_BOARD_SHEET",
                target="",
                raw_j="",
                source_row=0,
                detail=str(exc),
                source_file=str(env_info_xls),
            )

            return EnvironmentResult(
                ip=ip,
                is_valid_environment=True,
                mappings={},
                rows=[],
                issues=[issue],
            )

        rows: list[MappingRow] = []
        issues: list[Issue] = []

        # 只对正式 enbX 记录参与冲突分析。
        candidate_rows: dict[
            str,
            list[MappingRow],
        ] = defaultdict(list)

        # ----------------------------------------------------
        # 扫描第4行到实际最后一行。
        # 不因中间空行结束。
        # ----------------------------------------------------

        for row_index in range(
            START_ROW_INDEX,
            sheet.nrows,
        ):
            excel_row = row_index + 1

            a_value = cell_text(
                sheet.cell_value(
                    row_index,
                    COL_A,
                )
            )

            j_value = cell_text(
                sheet.cell_value(
                    row_index,
                    COL_J,
                )
            )

            target = normalize_target(
                a_value
            )

            if not target:
                continue

            enb_match = ENB_PATTERN.fullmatch(
                target
            )

            tool_match = ENB_TOOL_PATTERN.fullmatch(
                target
            )

            # 非 enbX / enb_toolX 行完全忽略。
            if not enb_match and not tool_match:
                continue

            board = recognize_board(
                j_value
            )

            # =================================================
            # TOOL：仅供 XLSX 人工查看
            # =================================================

            if tool_match:
                status = (
                    "IGNORE_TOOL"
                    if board
                    else "IGNORE_TOOL_UNRECOGNIZED"
                )

                rows.append(
                    MappingRow(
                        ip=ip,
                        target=target,
                        group="",
                        raw_j=j_value,
                        board=board or "",
                        record_type="TOOL",
                        status=status,
                        source_row=excel_row,
                        source_file=str(
                            env_info_xls
                        ),
                    )
                )

                continue

            # =================================================
            # 正式 enbX
            # =================================================

            group = get_group(
                target
            )

            if not j_value:
                row = MappingRow(
                    ip=ip,
                    target=target,
                    group=group,
                    raw_j="",
                    board="",
                    record_type="ENB",
                    status="MISSING_J",
                    source_row=excel_row,
                    source_file=str(
                        env_info_xls
                    ),
                )

                rows.append(row)

                issues.append(
                    Issue(
                        ip=ip,
                        code="MISSING_J",
                        target=target,
                        raw_j="",
                        source_row=excel_row,
                        detail=(
                            "A列为有效 enbX，"
                            "但 J 列为空"
                        ),
                        source_file=str(
                            env_info_xls
                        ),
                    )
                )

                continue

            if board is None:
                row = MappingRow(
                    ip=ip,
                    target=target,
                    group=group,
                    raw_j=j_value,
                    board="",
                    record_type="ENB",
                    status="UNRECOGNIZED_BOARD",
                    source_row=excel_row,
                    source_file=str(
                        env_info_xls
                    ),
                )

                rows.append(row)

                issues.append(
                    Issue(
                        ip=ip,
                        code="UNRECOGNIZED_BOARD",
                        target=target,
                        raw_j=j_value,
                        source_row=excel_row,
                        detail=(
                            "J列不包含任何已知版型关键字"
                        ),
                        source_file=str(
                            env_info_xls
                        ),
                    )
                )

                continue

            row = MappingRow(
                ip=ip,
                target=target,
                group=group,
                raw_j=j_value,
                board=board,
                record_type="ENB",
                status="OK",
                source_row=excel_row,
                source_file=str(
                    env_info_xls
                ),
            )

            rows.append(row)

            candidate_rows[
                target
            ].append(row)

        # ----------------------------------------------------
        # 4. 重复 / 冲突分析
        # ----------------------------------------------------

        mappings: dict[
            str,
            dict[str, Any],
        ] = {}

        for target, target_rows in (
            candidate_rows.items()
        ):
            unique_boards = {
                row.board
                for row in target_rows
            }

            # 同一个 target 多条，但全部是相同版型
            if len(unique_boards) == 1:
                first = target_rows[0]

                mappings[target] = {
                    "group": first.group,
                    "board": first.board,
                    "raw": first.raw_j,
                    "source_row": (
                        first.source_row
                    ),
                }

                for duplicate in target_rows[
                    1:
                ]:
                    duplicate.status = (
                        "DUPLICATE_SAME"
                    )

                continue

            # 同一个 target 识别成多个不同版型 -> 冲突
            boards_text = ", ".join(
                sorted(unique_boards)
            )

            for row in target_rows:
                row.status = "CONFLICT"

            issues.append(
                Issue(
                    ip=ip,
                    code="DUPLICATE_CONFLICT",
                    target=target,
                    raw_j=" | ".join(
                        row.raw_j
                        for row in target_rows
                    ),
                    source_row=(
                        target_rows[0]
                        .source_row
                    ),
                    detail=(
                        f"同一 {target} "
                        f"识别出多个版型："
                        f"{boards_text}"
                    ),
                    source_file=str(
                        env_info_xls
                    ),
                )
            )

        # ----------------------------------------------------
        # 5. 一个正式映射都没有，增加环境级异常
        # ----------------------------------------------------

        if not mappings:
            issues.append(
                Issue(
                    ip=ip,
                    code="NO_VALID_ENB_MAPPING",
                    target="",
                    raw_j="",
                    source_row=0,
                    detail=(
                        "环境基本信息.xls 中未得到"
                        "任何可用于 JSON 的有效 enbX 版型映射"
                    ),
                    source_file=str(
                        env_info_xls
                    ),
                )
            )

        return EnvironmentResult(
            ip=ip,
            is_valid_environment=True,
            mappings=mappings,
            rows=rows,
            issues=issues,
        )

    finally:
        workbook.release_resources()


# ============================================================
# 七、扫描 IP 目录
# ============================================================

def select_ip_dirs() -> list[Path]:
    log(
        f"[SCAN] REMOTE_ROOT={REMOTE_ROOT}"
    )

    if not RUN_ALL_IPS:
        result = [
            REMOTE_ROOT / ip
            for ip in TARGET_IPS
        ]

        log(
            f"[SCAN] 指定模式，目标IP={len(result)}"
        )

        return result

    result: list[Path] = []

    start = time.perf_counter()

    try:
        with os.scandir(
            str(REMOTE_ROOT)
        ) as iterator:

            for entry in iterator:
                try:
                    if not entry.is_dir(
                        follow_symlinks=False
                    ):
                        continue
                except OSError as exc:
                    log(
                        f"[SCAN WARN] "
                        f"无法判断目录："
                        f"{entry.name}：{exc}"
                    )
                    continue

                result.append(
                    Path(entry.path)
                )

    except OSError as exc:
        raise RuntimeError(
            f"无法扫描 REMOTE_ROOT："
            f"{REMOTE_ROOT}：{exc}"
        ) from exc

    result.sort(
        key=lambda path:
        ip_sort_key(path.name)
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    log(
        f"[SCAN] 根目录扫描完成，"
        f"子目录={len(result)}，"
        f"耗时={elapsed:.2f}s"
    )

    return result


# ============================================================
# 八、并发提取
# ============================================================

def extract_all(
    ip_dirs: list[Path],
) -> list[EnvironmentResult]:

    if not ip_dirs:
        return []

    worker_count = min(
        max(1, MAX_WORKERS),
        len(ip_dirs),
    )

    log(
        f"[CONCURRENCY] workers={worker_count}"
    )

    results: list[
        EnvironmentResult
    ] = []

    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="env-board",
    ) as executor:

        future_map = {
            executor.submit(
                process_ip,
                ip_dir,
            ): ip_dir
            for ip_dir in ip_dirs
        }

        pending = set(
            future_map.keys()
        )

        completed = 0
        valid_count = 0

        while pending:
            done, pending = wait(
                pending,
                timeout=HEARTBEAT_SECONDS,
                return_when=FIRST_COMPLETED,
            )

            if not done:
                log(
                    f"[WAIT] "
                    f"已完成={completed}/{len(ip_dirs)}，"
                    f"仍等待={len(pending)}"
                )

                shown = 0

                for future in list(pending):
                    if (
                        shown
                        >= WAITING_SAMPLE_COUNT
                    ):
                        break

                    ip_dir = future_map[
                        future
                    ]

                    log(
                        f"    [WAITING] "
                        f"{ip_dir.name}"
                    )

                    shown += 1

                continue

            for future in done:
                ip_dir = future_map[
                    future
                ]

                try:
                    result = future.result()

                except Exception as exc:
                    result = EnvironmentResult(
                        ip=ip_dir.name,
                        is_valid_environment=True,
                        mappings={},
                        rows=[],
                        issues=[
                            Issue(
                                ip=ip_dir.name,
                                code=(
                                    "UNHANDLED_ERROR"
                                ),
                                target="",
                                raw_j="",
                                source_row=0,
                                detail=str(exc),
                                source_file="",
                            )
                        ],
                    )

                    log(
                        f"[ERROR] "
                        f"IP={ip_dir.name}："
                        f"{exc}"
                    )

                results.append(
                    result
                )

                if (
                    result
                    .is_valid_environment
                ):
                    valid_count += 1

                completed += 1

                if (
                    completed % 100 == 0
                    or completed
                    == len(ip_dirs)
                ):
                    log(
                        f"[PROGRESS] "
                        f"{completed}/{len(ip_dirs)}，"
                        f"有效环境={valid_count}"
                    )

    results.sort(
        key=lambda item:
        ip_sort_key(item.ip)
    )

    return results


# ============================================================
# 九、JSON
# ============================================================

def build_json_data(
    results: list[EnvironmentResult],
) -> dict[str, Any]:

    environments: dict[
        str,
        dict[str, Any],
    ] = {}

    issues: list[
        dict[str, Any]
    ] = []

    valid_environment_count = 0

    for result in results:
        if not result.is_valid_environment:
            continue

        valid_environment_count += 1

        if result.mappings:
            ordered_mapping = dict(
                sorted(
                    result.mappings.items(),
                    key=lambda item:
                    target_sort_key(
                        item[0]
                    ),
                )
            )

            environments[
                result.ip
            ] = ordered_mapping

        for issue in result.issues:
            issues.append(
                asdict(issue)
            )

    return {
        "meta": {
            "generated_at": (
                datetime.now()
                .astimezone()
                .isoformat(
                    timespec="seconds"
                )
            ),
            "remote_root": str(
                REMOTE_ROOT
            ),
            "execution_xls": (
                EXECUTION_XLS_NAME
            ),
            "environment_xls": (
                ENV_INFO_XLS_NAME
            ),
            "sheet": BOARD_SHEET_NAME,
            "valid_environment_count": (
                valid_environment_count
            ),
            "mapped_environment_count": (
                len(environments)
            ),
            "board_rules": [
                {
                    "keyword": keyword,
                    "board": board,
                }
                for keyword, board
                in BOARD_RULES
            ],
            "group_rule": {
                "enb0": "BBH",
                "other_enb": "BBL",
            },
        },
        "environments": environments,
        "issues": issues,
    }


def write_json(
    data: dict[str, Any],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


# ============================================================
# 十、XLSX
# ============================================================

def write_xlsx(
    results: list[EnvironmentResult],
    json_data: dict[str, Any],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    workbook = (
        xlsxwriter.Workbook(
            str(OUTPUT_XLSX)
        )
    )

    # --------------------------------------------------------
    # 格式
    # --------------------------------------------------------

    title_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 14,
            "align": "left",
            "valign": "vcenter",
        }
    )

    header_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )

    text_fmt = workbook.add_format(
        {
            "border": 1,
            "valign": "top",
        }
    )

    center_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
            "valign": "top",
        }
    )

    ok_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
            "bg_color": "#E2F0D9",
        }
    )

    warn_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
            "bg_color": "#FFF2CC",
        }
    )

    error_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
            "bg_color": "#F4CCCC",
        }
    )

    tool_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
            "bg_color": "#E7E6E6",
        }
    )

    number_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
        }
    )

    # ========================================================
    # Sheet 1：汇总
    # ========================================================

    summary = workbook.add_worksheet(
        "汇总"
    )

    summary.write(
        "A1",
        "环境版型提取汇总",
        title_fmt,
    )

    all_subdirs = len(results)

    valid_results = [
        item
        for item in results
        if item.is_valid_environment
    ]

    mapped_results = [
        item
        for item in valid_results
        if item.mappings
    ]

    all_rows = [
        row
        for item in valid_results
        for row in item.rows
    ]

    all_issues = [
        issue
        for item in valid_results
        for issue in item.issues
    ]

    enb_rows = [
        row
        for row in all_rows
        if row.record_type == "ENB"
    ]

    tool_rows = [
        row
        for row in all_rows
        if row.record_type == "TOOL"
    ]

    summary_rows = [
        ["项目", "数量 / 值"],
        ["REMOTE_ROOT", str(REMOTE_ROOT)],
        ["扫描子目录数", all_subdirs],
        ["有效环境数（存在执行表）", len(valid_results)],
        ["成功得到正式映射的环境数", len(mapped_results)],
        ["正式 ENB 记录数", len(enb_rows)],
        ["TOOL 记录数", len(tool_rows)],
        ["异常记录数", len(all_issues)],
        ["JSON 输出", str(OUTPUT_JSON)],
        ["XLSX 输出", str(OUTPUT_XLSX)],
        ["生成时间", json_data["meta"]["generated_at"]],
    ]

    for row_index, values in enumerate(
        summary_rows
    ):
        for col_index, value in enumerate(
            values
        ):
            fmt = (
                header_fmt
                if row_index == 0
                else text_fmt
            )

            summary.write(
                row_index + 2,
                col_index,
                value,
                fmt,
            )

    summary.set_column(
        "A:A",
        28,
    )
    summary.set_column(
        "B:B",
        100,
    )
    summary.freeze_panes(
        3,
        0,
    )

    # ========================================================
    # Sheet 2：环境版型映射
    # ========================================================

    mapping_sheet = workbook.add_worksheet(
        "环境版型映射"
    )

    mapping_headers = [
        "IP",
        "Target",
        "分组",
        "原始J值",
        "识别版型",
        "类型",
        "状态",
        "源Excel行",
        "环境信息表",
    ]

    for col, header in enumerate(
        mapping_headers
    ):
        mapping_sheet.write(
            0,
            col,
            header,
            header_fmt,
        )

    all_rows.sort(
        key=lambda row: (
            ip_sort_key(row.ip),
            target_sort_key(
                row.target
            ),
            row.source_row,
        )
    )

    for row_index, row in enumerate(
        all_rows,
        start=1,
    ):
        values = [
            row.ip,
            row.target,
            row.group,
            row.raw_j,
            row.board,
            row.record_type,
            row.status,
            row.source_row,
            row.source_file,
        ]

        for col_index, value in enumerate(
            values
        ):
            if col_index == 6:
                if row.status == "OK":
                    fmt = ok_fmt
                elif row.status in (
                    "DUPLICATE_SAME",
                ):
                    fmt = warn_fmt
                elif row.status.startswith(
                    "IGNORE_TOOL"
                ):
                    fmt = tool_fmt
                else:
                    fmt = error_fmt

            elif col_index in (
                1,
                2,
                4,
                5,
                7,
            ):
                fmt = center_fmt

            else:
                fmt = text_fmt

            mapping_sheet.write(
                row_index,
                col_index,
                value,
                fmt,
            )

    mapping_sheet.freeze_panes(
        1,
        0,
    )

    if all_rows:
        mapping_sheet.autofilter(
            0,
            0,
            len(all_rows),
            len(mapping_headers) - 1,
        )

    mapping_sheet.set_column(
        "A:A",
        18,
    )
    mapping_sheet.set_column(
        "B:B",
        14,
    )
    mapping_sheet.set_column(
        "C:C",
        10,
    )
    mapping_sheet.set_column(
        "D:D",
        34,
    )
    mapping_sheet.set_column(
        "E:E",
        12,
    )
    mapping_sheet.set_column(
        "F:F",
        10,
    )
    mapping_sheet.set_column(
        "G:G",
        24,
    )
    mapping_sheet.set_column(
        "H:H",
        12,
    )
    mapping_sheet.set_column(
        "I:I",
        70,
    )

    # ========================================================
    # Sheet 3：异常环境
    # ========================================================

    issue_sheet = workbook.add_worksheet(
        "异常环境"
    )

    issue_headers = [
        "IP",
        "异常代码",
        "Target",
        "原始J值",
        "源Excel行",
        "说明",
        "环境信息表",
    ]

    for col, header in enumerate(
        issue_headers
    ):
        issue_sheet.write(
            0,
            col,
            header,
            header_fmt,
        )

    all_issues.sort(
        key=lambda issue: (
            ip_sort_key(issue.ip),
            issue.code,
            target_sort_key(
                issue.target
            ),
            issue.source_row,
        )
    )

    for row_index, issue in enumerate(
        all_issues,
        start=1,
    ):
        values = [
            issue.ip,
            issue.code,
            issue.target,
            issue.raw_j,
            issue.source_row,
            issue.detail,
            issue.source_file,
        ]

        for col_index, value in enumerate(
            values
        ):
            fmt = (
                center_fmt
                if col_index in (
                    1,
                    2,
                    4,
                )
                else text_fmt
            )

            issue_sheet.write(
                row_index,
                col_index,
                value,
                fmt,
            )

    issue_sheet.freeze_panes(
        1,
        0,
    )

    if all_issues:
        issue_sheet.autofilter(
            0,
            0,
            len(all_issues),
            len(issue_headers) - 1,
        )

    issue_sheet.set_column(
        "A:A",
        18,
    )
    issue_sheet.set_column(
        "B:B",
        28,
    )
    issue_sheet.set_column(
        "C:C",
        14,
    )
    issue_sheet.set_column(
        "D:D",
        34,
    )
    issue_sheet.set_column(
        "E:E",
        12,
    )
    issue_sheet.set_column(
        "F:F",
        70,
    )
    issue_sheet.set_column(
        "G:G",
        70,
    )

    workbook.close()


# ============================================================
# 十一、主程序
# ============================================================

def main() -> None:
    faulthandler.enable(
        file=sys.stderr
    )

    faulthandler.dump_traceback_later(
        FAULT_DUMP_SECONDS,
        repeat=True,
        file=sys.stderr,
    )

    start = time.perf_counter()

    try:
        log("=" * 90)
        log("环境版型配置提取")
        log("=" * 90)

        ip_dirs = select_ip_dirs()

        if not ip_dirs:
            log("未发现需要扫描的目录。")
            return

        results = extract_all(
            ip_dirs
        )

        valid_results = [
            item
            for item in results
            if item.is_valid_environment
        ]

        json_data = build_json_data(
            results
        )

        log(
            "[OUTPUT] 开始写 JSON..."
        )

        write_json(
            json_data
        )

        log(
            "[OUTPUT] 开始写 XLSX..."
        )

        write_xlsx(
            results,
            json_data,
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        mapped_count = len(
            json_data["environments"]
        )

        issue_count = len(
            json_data["issues"]
        )

        mapping_count = sum(
            len(value)
            for value
            in json_data[
                "environments"
            ].values()
        )

        log("=" * 90)
        log("处理完成")
        log("=" * 90)

        log(
            f"根目录子目录：{len(results)}"
        )
        log(
            f"有效环境：{len(valid_results)}"
        )
        log(
            f"成功映射环境：{mapped_count}"
        )
        log(
            f"正式 enbX 映射数：{mapping_count}"
        )
        log(
            f"异常数：{issue_count}"
        )
        log(
            f"JSON：{OUTPUT_JSON}"
        )
        log(
            f"XLSX：{OUTPUT_XLSX}"
        )
        log(
            f"总耗时：{elapsed:.2f}s"
        )

    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
