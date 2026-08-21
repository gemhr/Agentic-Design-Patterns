# normalize.py 完整业务流程与 Agent 交接说明

## 1. 文档目的

本文说明根目录 `normalize.py` 当前已经实现的业务功能、输入输出契约、状态推进规则、版型和多 DSP 默认值处理、异常行为，以及后续 Agent 接手时需要继续关注的事项。

本文以当前源码实际行为为准，不描述尚未实现的设想。

---

## 2. 业务背景

原始 AW 用例按照 `用例执行列表_5G.xls` 中的固定顺序执行。

前一个 Case 对 DSP 全局变量的写入可能遗留到下一个 Case，因此部分 Case 的真实入口状态依赖前序 Case。现在 Case 会进入随机池独立执行，如果直接使用原 AW，后续 Case 可能缺少它在原执行顺序中应当继承的 DSP 状态。

`normalize.py` 的目标是为每个原始 AW 生成一个 `*_Normalized.dat` 文件，使其具备：

1. 在 Case 开头补齐原执行顺序下应继承的历史状态；
2. 保留当前 Case 的有效非默认写入；
3. 在 Case 结束前把补写和当前 Case 修改过的受管变量恢复到默认值；
4. 让生成后的 Case 尽量可以脱离原执行顺序独立运行。

脚本不会主动修改原始 AW 文件。

---

## 3. 根目录输入文件

### 3.1 `normalize.py`

主处理脚本。

### 3.2 `environment_board_mapping.json`

环境版型映射文件，由 `extract_environment_board_mapping.py` 生成。

正式查询结构如下：

```json
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
  }
}
```

`normalize.py` 实际只读取：

```text
environments[IP][target].board
```

其中：

- `IP` 是远程根目录下 IP 文件夹的名称；
- `target` 是 AW 命令第二个双引号字段，例如 `enb0`、`enb1`；
- AW 中的 `BaseBandBoard` 在查询版型时按 `enb0` 处理。

如果整个 IP 不存在于 `environments` 中，脚本直接跳过该 IP，不计为失败。

### 3.3 `dsp_defaults.json`

DSP 受管变量及默认值配置，完全替代旧的 `default.txt`。

顶层至少支持两个同级字段：

```json
{
  "common": {},
  "board_sensitive": {}
}
```

#### `common`

用于不区分具体版型、只区分 BBH/BBL 和 DSP ID 的变量。

示例：

```json
{
  "common": {
    "BBH": {
      "g_cchSdvFmt1DtxFlag|5|4": {
        "variable": "g_cchSdvFmt1DtxFlag",
        "core": 5,
        "offset": 4,
        "dsp_defaults": {
          "0": "0x0",
          "1": "0x0"
        }
      }
    }
  }
}
```

匹配字段为：

```text
(BBH/BBL, DSP ID, Core ID, Variable, Offset)
```

`dsp_defaults` 中没有当前 DSP ID 时，该 WSym 不会被当作受管命令。

#### `board_sensitive`

用于默认值真实区分具体版型的少量变量。

示例：

```json
{
  "board_sensitive": {
    "BBH": {
      "g_lrcDynSpecSwitch|24|4": {
        "variable": "g_lrcDynSpecSwitch",
        "core": 24,
        "offset": 4,
        "defaults_by_board": {
          "86": {
            "0": "0x1"
          },
          "11": {
            "1": "0x0"
          }
        }
      }
    }
  }
}
```

这类变量除了 DSP ID 外，还按照 AW target 分开跟踪，防止同一 IP 中不同 BBL 单板的状态和默认值互相覆盖。

### 3.4 远程目录

默认远程根目录：

```text
\\7.213.207.64\opt\data1\UCI\workspace\UCI_Script\26B\TestCase_26B
```

根目录下直接子目录默认被视为 IP 目录。

---

## 4. BBH/BBL 与版型识别规则

AW 命令的第二个双引号字段用于识别分组：

```text
BaseBandBoard -> BBH
enb0          -> BBH
其他 enb数字   -> BBL
```

对于 `common` 变量，具体版型不参与默认值选择。

对于 `board_sensitive` 变量，脚本先通过 IP 和 AW target 查询具体版型，再选择默认值。

### 4.1 `board_sensitive` 默认值选择顺序

给定当前版型和当前 DSP ID，按照以下顺序选择：

1. `defaults_by_board` 中存在当前版型，并且该版型包含当前 DSP ID：使用精确默认值；
2. 否则，按 JSON 原始顺序寻找第一个包含当前 DSP ID 的版型，使用该值；
3. 仍找不到时，使用 `defaults_by_board` 中第一个版型的第一个默认值。

示例：

```json
"defaults_by_board": {
  "86": {
    "0": "0x1"
  },
  "11": {
    "1": "0x0"
  }
}
```

当前版型为 `37` 时：

- 当前 DSP ID 是 `1`：选择版型 `11` 的 `0x0`；
- 当前 DSP ID 是 `2`：没有任何版型包含 DSP 2，选择第一个版型 `86` 的第一个值 `0x1`。

如果 IP 存在，但某个 AW target 在版型映射中不存在，`board_sensitive` 会直接进入上述第 2、3 级回退，而不是跳过整个 IP。

---

## 5. 多 DSP 状态模型

DSP ID 已经纳入 `StateKey`，DSP 0、DSP 1 等分别跟踪。

普通受管变量的状态键为：

```text
(section, dsp_id, core_id, variable, offset)
```

版型敏感变量的状态键为：

```text
(section, dsp_id, core_id, variable, offset, target)
```

因此：

- DSP 0 的历史值不会覆盖 DSP 1；
- DSP 0 和 DSP 1 分别生成自己的前置写入和恢复写入；
- `board_sensitive` 中 `enb1` 的状态不会覆盖 `enb2`；
- 脚本不会把 DSP 0 的值自动镜像给 DSP 1；
- 只有原始 AW 中真实出现并被成功解析的 DSP 写入才会进入状态链。

如果原始 AW 同时写 DSP 0 和 DSP 1，两者都会独立处理。向单芯片版型写入额外 DSP 命令所产生的设备侧无效报错，不由本脚本处理。

---

## 6. WSym 解析规则

脚本宽松识别以下命令：

```text
DSP_WSym
DSP_WSymAuto
DSP_WSymOffset
DSP_WSymOffest
```

其中 `DSP_WSymOffest` 是对历史拼写错误的兼容。

### 6.1 命令类型归一化

- `DSP_WSymOffset`、`DSP_WSymOffest` -> `DSP_WSymOffset`；
- `DSP_WSymAuto` -> `DSP_WSymAuto`；
- 其他匹配 -> `DSP_WSym`。

### 6.2 参数解释

`DSP_WSym`：

```text
DSP ID = 变量名前第一个数字
Core ID = 变量名前第二个数字
Data = 变量名后第一个数字
Offset = 0
```

`DSP_WSymOffset`：

```text
DSP ID = 变量名前第一个数字
Core ID = 变量名前第二个数字
Data = 变量名后第一个数字
Offset = 变量名后第二个数字
```

`DSP_WSymAuto`：

```text
DSP ID = 变量名前第一个数字
Core ID = 固定为 5
Data = 变量名后第一个数字
Offset = 0
```

脚本保留完整原始行。生成前置和恢复写入时只替换 Data 所在字符区间，不主动重排参数、修改 target、修改 DSP ID 或格式化整行。

---

## 7. 完整执行流程

### 7.1 启动和配置加载

`main()` 启动后：

1. 启用 `faulthandler`；
2. 每 60 秒打印一次所有线程堆栈，用于定位 UNC/SMB 阻塞；
3. 读取 `dsp_defaults.json`；
4. 读取 `environment_board_mapping.json`；
5. 校验 JSON 的必要结构和默认值是否合法。

非法 JSON、非法 DSP ID、非法整数默认值、重复变量定义等会在进入远程处理前直接终止。

### 7.2 选择 IP

当 `RUN_ALL_IPS=True`：

1. 枚举远程根目录的直接子目录；
2. 每个直接子目录作为一个 IP；
3. 按目录名排序。

当 `RUN_ALL_IPS=False`：

1. 不扫描远程根目录；
2. 直接根据 `TARGET_IPS` 构造路径；
3. 不预先调用 `is_dir()`。

### 7.3 版型映射 Gate

开始处理 IP 时，先查询：

```text
board_mappings[ip_name]
```

不存在时：

```text
[SKIP IP] <IP>：环境版型映射 JSON 中不存在该 IP
```

随后返回 `成功=0，失败=0`，不读取该 IP 的执行表和 AW。

### 7.4 发现处理单元

一个“处理单元”是一个包含 `用例执行列表_5G.xls` 的目录。

每个 IP 下检查：

1. IP 根目录自身；
2. IP 根目录的直接子目录；
3. 不继续递归更深层级。

每个处理单元完全独立：

- 独立读取执行表；
- `current_state` 独立从空状态开始；
- 不从上一个处理单元继承状态。

### 7.5 读取执行表

读取处理单元中的：

```text
用例执行列表_5G.xls
```

只读取第一个 Sheet。

使用列：

```text
A 列  -> Case 路径
AM 列 -> AW 文件名
```

规则：

- 从 Excel 第 2 行开始；
- A 列为空时跳过；
- A 列等于 `end` 时停止；
- A 列为相对路径时，相对于当前处理单元解析；
- AM 列为空时使用 `TestCtrlPara.dat`。

### 7.6 加载 Case AW

源 AW 路径：

```text
<Case路径>/TestCtrlPara/<AM列文件名或TestCtrlPara.dat>
```

输出路径：

```text
<Case路径>/TestCtrlPara/<源文件stem>_Normalized.dat
```

如果执行表把 `_Normalized.dat` 作为输入，脚本拒绝处理，防止重复归一化。

编码读取顺序：

1. UTF-8 BOM -> `utf-8-sig`；
2. UTF-8；
3. UTF-8 解码失败后使用 `gb18030`。

输出沿用主 AW 的编码和换行风格。

### 7.7 单 IP 内并发读取

AW 文件可以并发读取，但读取结果会放回执行表原始位置。

因此：

- 文件 I/O 可以并发；
- 后续状态推进仍严格按照 Excel 顺序串行；
- 单个 AW 加载失败时记录 `[CASE LOAD ERROR]` 并跳过该 Case；
- 其他成功加载的 Case 保持原 Excel 相对顺序继续处理；
- 后续历史状态可能缺少失败 Case 的影响，这是用户明确接受的降级行为；
- 30 秒没有读取任务完成时打印等待心跳和部分等待文件。

### 7.8 建立受管模板和默认值目录

脚本遍历该处理单元的全部原始 WSym：

1. 根据 BBH/BBL、变量、Core、Offset、DSP ID 匹配 JSON；
2. 对 `board_sensitive` 变量解析 target 对应版型和默认值；
3. 为每个实际出现的受管 `StateKey` 保存第一条真实 WSym 作为模板；
4. 记录当前处理单元实际出现的默认值和顺序；
5. 输出 WSym 候选数、解析成功数、受管命令数、未受管 Key 和解析失败样例。

JSON 中存在、但当前处理单元从未出现的变量不会被强行初始化。

---

## 8. Pass 1：生成入口历史状态

### 8.1 初始状态

每个处理单元开始时：

```text
current_state = {}
current_templates = {}
```

不会把 JSON 中所有默认值预先放入状态集合。

### 8.2 当前 Case 的前置写入

进入一个 Case 时，遍历已经进入 `current_state` 的状态项。

在：

```tcl
set TestCtrlInfoList {
```

下一行插入前序 Case 最后一次非默认写入值。

前置命令复用该状态项最近一次原始 WSym 的完整格式，只替换 Data。

### 8.3 原始写入等于默认值

如果当前 Case 的原始受管 WSym 写入值等于解析后的默认值：

1. 从生成文本中删除该原始 WSym；
2. 不因为本次写入新增恢复命令；
3. 不推进 `current_state`；
4. 不更新 `current_templates`。

需要特别注意：如果该变量此前已经进入历史状态，本 Case 开头仍可能存在历史前置写入，尾部也仍会为该前置写入恢复默认值。当前默认值写入本身不会增加第二条恢复。

另外，默认值写入不会清除既有历史状态。后续 Case 仍继承此前最后一次非默认写入。这是当前源码的明确行为。

### 8.4 原始写入不等于默认值

如果当前 Case 写入非默认值：

1. 原始 WSym 保留；
2. 同一状态项在当前 Case 中写多次时，原始行全部保留；
3. 当前 Case 的最终状态取最后一次非默认写入；
4. 恢复模板优先使用当前 Case 最后一次非默认写入的格式；
5. Case 处理完成后，该值进入 `current_state`，供后续 Case 继承。

### 8.5 找不到 `TestCtrlInfoList` 标记

如果找不到：

```tcl
set TestCtrlInfoList {
```

当前 Case 的 Normalized 计划失败，不生成输出。

但为了保证后续 Case 的原执行顺序状态仍正确，脚本仍会根据该 Case 原始 AW 中的非默认受管 WSym 推进 `current_state`。

---

## 9. Pass 2：生成恢复写入并落盘

### 9.1 恢复集合

一个 Case 的恢复集合是：

```text
本 Case 开头补写的全部历史状态
并集
本 Case 原始 AW 自己写入过的全部非默认受管状态
```

同一个 `StateKey` 只恢复一次。

### 9.2 恢复值

每个状态项恢复到为该命令解析出的 JSON 默认值。

恢复模板优先级：

1. 当前 Case 最后一次非默认真实写入；
2. 当前 Case 前置写入使用的历史模板；
3. 当前状态保存的最近真实模板。

### 9.3 插入位置

脚本从文件尾部向前寻找最后一个：

```tcl
set RecoveryList {
```

然后定位它前面的非空 `}`，并在该 `}` 之前插入恢复命令。

也就是说，恢复命令仍插入 `TestCtrlInfoList` 的尾部，而不是写进空的 `RecoveryList`。

### 9.4 输出覆盖

当前配置：

```python
OVERWRITE_NORMALIZED = True
```

因此已经存在的 `_Normalized.dat` 会被覆盖。

如果改为 `False`，目标文件已存在时当前 Case 记为失败并跳过写入。

### 9.5 AXCAUTO 文件

如果同一目录存在：

```text
TestCtrlPara_AXCAUTO_6188.dat
```

脚本还会尝试生成：

```text
TestCtrlPara_AXCAUTO_6188_Normalized.dat
```

处理方式：

1. 使用相同的默认值删除规则清理默认值 WSym；
2. 插入主 AW 计划得到的相同 `front_lines`；
3. 插入主 AW 计划得到的相同 `recovery_lines`；
4. 写入 Normalized 文件。

AXCAUTO 写入失败只记录警告，不影响主 AW 已经成功的计数。

---

## 10. 并发模型

默认并发配置：

```text
IP workers = 2
AW read workers/IP = 4
理论最大远程 AW 并发约为 8
```

并发边界：

- 不同 IP 可以并行执行；
- 同一 IP 内 AW 文件读取可以并行；
- 同一处理单元的 Case 状态推进严格串行；
- `log()` 使用全局锁，避免多线程日志互相穿插；
- 每 60 秒使用 `faulthandler` 输出所有线程堆栈。

---

## 11. 成功、失败与跳过语义

### 11.1 不计失败的跳过

- 当前 IP 不存在于环境版型映射 JSON：整 IP 跳过，返回 `0, 0`。

### 11.2 单 Case 失败

以下情况记录失败并跳过当前 Case，其他 Case 继续：

- 原始 AW 不存在、无法读取或无法解析；
- Pass 1 找不到 `set TestCtrlInfoList {`；
- Pass 2 找不到固定尾部；
- 输出路径无法检查；
- Normalized 文件生成或写入失败。

### 11.3 处理单元失败

以下情况会使处理单元中止或累计失败：

- 找不到执行表；
- 执行表无法读取或解析；
- 执行表没有有效 Case；
- 模板和默认值目录构建出现未知异常；
- Pass 1 出现无法归属到单个 Case 的未知异常；
- Pass 2 出现无法归属到单个 Case 的未知异常。

处理单元失败后继续同一 IP 的其他处理单元。

### 11.4 IP 失败

`process_ip()` 逃出的未知异常会被主调度层捕获，记录 `[IP ERROR]` 后跳过该 IP。串行和并发 IP 模式使用相同语义，不会因为单个 IP 异常退出全部任务。

### 11.5 仍会终止全部任务的全局异常

- `dsp_defaults.json` 缺失、非法或 schema 校验失败；
- `environment_board_mapping.json` 缺失、非法或 schema 校验失败；
- 远程根目录完全无法扫描；
- Python 进程被外部终止等无法恢复的进程级问题。

### 11.6 警告但主 AW 仍算成功

- AXCAUTO 文件读取失败；
- AXCAUTO Normalized 生成失败。

---

## 12. 当前实现边界

以下内容是当前实现的明确边界，后续修改前应先确认业务期望：

1. `common` 中当前 DSP ID 不存在于 `dsp_defaults` 时，该命令视为未受管，不使用其他 DSP 的值回退；
2. 多 DSP 分别跟踪，不自动把某个 DSP 的历史值复制给其他 DSP；
3. 只有原始 AW 真实出现过的受管变量才进入状态链，不全量初始化 JSON 变量；
4. 默认值写入会从输出中删除，但不会清除此前保存的非默认历史状态；
5. `board_sensitive` 缺少当前 target 映射时，会使用 DSP/首项回退，不会跳过 IP；
6. `common` 变量仍按 BBH/BBL 共享逻辑状态，不按具体版型区分；
7. `board_sensitive` 变量按 target 隔离状态；
8. 恢复命令插入 `TestCtrlInfoList` 尾部，不插入 `RecoveryList` 内部；
9. 脚本只扫描 IP 根目录和一层直接子目录中的执行表；
10. AXCAUTO 输出沿用主 AW 的编码和换行配置；
11. 当前没有设备侧执行结果回读，无法判断额外 DSP 写入是否在目标硬件上报无效；
12. 单个 Case 加载失败后仍继续处理，后续 Case 的历史状态可能缺少失败 Case 的写入影响；
13. 当前没有实际 `environment_board_mapping.json` 和 `dsp_defaults.json` 的全量远程执行验证记录。

---

## 13. 当前已完成的本地验证

已执行：

```text
uv run python -m py_compile normalize.py
```

结果：通过。

已使用本地最小行为探针验证：

1. `common` 默认值按 DSP ID 精确匹配；
2. `board_sensitive` 精确版型匹配；
3. 缺少版型时优先选择包含相同 DSP ID 的第一个版型；
4. 完全没有相同 DSP ID 时选择第一个版型的第一个默认值；
5. DSP 0 和 DSP 1 的 `StateKey` 相互独立；
6. `board_sensitive` 的不同 target 状态相互独立；
7. 后续 Case 分别获得 DSP 0、DSP 1 的历史前置写入；
8. 只有默认值写入且没有历史前置状态时，不生成前置和恢复命令，并删除该原始默认值 WSym。
9. 串行和并发 AW 加载模式下，单个 Case 加载失败都会保留其他 Case 并继续处理。

尚未完成：

- 使用真实两个 JSON 的加载验证；
- 使用真实远程执行表和 AW 的端到端生成；
- 在真实单芯片、多芯片板型上执行生成文件；
- 验证设备侧额外 DSP 写入报错确实不影响业务。

---

## 14. 交给下一位 Agent 的说明

如果把当前任务交给下一位 Agent，建议附带以下说明：

### 14.1 当前需求结论

1. `default.txt` 已废弃，由 `dsp_defaults.json` 完全替代；
2. `environment_board_mapping.json` 来自 `extract_environment_board_mapping.py`；
3. `enb0` 和 `BaseBandBoard` 属于 BBH，其他 `enb数字` 属于 BBL；
4. `common` 不区分具体版型；
5. `board_sensitive` 按 IP、target 和版型选择默认值；
6. DSP 0、DSP 1 等必须分别跟踪；
7. 环境映射缺少整个 IP 时直接跳过；
8. 版型默认值缺失时执行“精确版型 -> 相同 DSP ID -> 第一项”回退；
9. 写入默认值的原始受管 WSym 会删除，不因该写入新增恢复；
10. 单个 Case 加载失败时记录并跳过，接受后续状态可能不完整；
11. 处理单元或 IP 的未知异常只跳过对应范围，不得退出全部任务；
12. 不要擅自扩大为架构重构或修改远程生成数据。

### 14.2 下一步首先需要的用户输入

请求用户把以下真实文件放到根目录：

```text
environment_board_mapping.json
dsp_defaults.json
```

如果文件名不同，只修改 `BOARD_MAPPING_JSON` 和 `DSP_DEFAULTS_JSON` 两个配置常量即可。

### 14.3 下一步建议验证顺序

1. 只加载两个真实 JSON，确认 schema、数量和首尾样例；
2. 选择一个明确的 IP 和一个处理单元，不先跑全部远程目录；
3. 找到一个 `common` 多 DSP 变量；
4. 找到一个 `board_sensitive` 精确版型变量；
5. 找到一个需要相同 DSP ID 回退的版型；
6. 找到一个需要首项回退的版型；
7. 各选少量连续 Case，对比原始 AW、历史状态和生成结果；
8. 确认无误后再考虑扩大到全部 IP。

### 14.4 下一位 Agent 必须重点检查的风险

#### 风险 A：默认值写入不清除历史状态

当前代码会删除默认值写入，并保留此前最后一次非默认历史状态。

示例：

```text
Case 1: X = 5
Case 2: X = 0，且 0 是默认值
Case 3: 未写 X
```

当前生成逻辑中，Case 2 的 `X=0` 被删除，Case 3 仍继承 `X=5`。

这是当前已确认并写入说明的行为。后续 Agent 不应自行改动；如果真实业务希望 Case 2 清除历史状态，必须重新向用户确认。

#### 风险 B：`common` 的不同 BBL target 共享状态

当前 `common` 状态键不包含 target。若同一 IP 下 `enb1`、`enb2` 的同一 common 变量实际上属于不同物理状态，现有行为可能互相覆盖。

目前用户只要求 common 按 BBH/BBL，不应未经授权改成全部按 target 隔离。

#### 风险 C：AXCAUTO 复用主 AW 的前置和恢复命令

需要用真实 AXCAUTO 文件确认主 AW 模板行是否可以直接插入 AXCAUTO，以及主 AW 编码是否始终与 AXCAUTO 一致。

#### 风险 D：回退依赖 JSON 顺序

“第一个版型”和“第一个默认值”依赖 JSON object 的原始顺序。Python 会保留 JSON 解析顺序，但重新生成或手工排序 JSON 会改变最终回退值。

#### 风险 E：真实 WSym 格式覆盖度

当前解析器是宽松数字/双引号解析。真实数据中如果出现表达式、宏、非整数 Data 或不同引号结构，可能被记录为解析失败并失去管理。

#### 风险 F：失败 Case 导致后续历史状态不完整

当前策略是单个 Case 加载失败后继续处理其他 Case。因为失败 Case 的 WSym 无法读取，脚本不能把它对 DSP 状态的影响推进到 `current_state`，所以后续 Case 的前置历史状态可能不完整。

这是用户明确接受的可用性优先策略。后续 Agent 不应擅自恢复为“任意 Case 失败则中止整个处理单元”。

### 14.5 下一位 Agent 不应自行做的事情

- 不要修改 `extract_environment_board_mapping.py` 的采集逻辑，除非用户明确要求；
- 不要恢复 `default.txt` 双轨兼容；
- 不要把 DSP 0 的值自动镜像到 DSP 1；
- 不要改变版型回退顺序；
- 不要把缺少 IP 映射改成失败；
- 不要修改原始 AW；
- 不要在未验证单个 IP 前直接运行全部远程目录；
- 不要顺手重构并发、日志、目录发现或 Excel 读取逻辑。

---

## 15. 关键源码入口

```text
配置路径                         BOARD_MAPPING_JSON / DSP_DEFAULTS_JSON
JSON 默认值加载                  load_default_catalog
环境版型映射加载                 load_board_mappings
默认值精确匹配与回退             resolve_default
WSym 单行解析                    parse_wsym_line
Excel Case 路径加载              load_case_paths
单个 Case 加载                   load_single_case
单 IP 并发读取                   load_ip_cases
受管模板和实际默认值目录         build_template_catalog
默认值原始写入删除               _remove_default_value_lines
Pass 1 状态继承与恢复计划        build_pass1_plans
Pass 2 插入和输出                execute_pass2
IP 内处理单元调度                process_ip
总入口                           main
```

---

## 16. 最终业务流程摘要

```text
加载 DSP 默认值 JSON
        |
加载 IP/target/版型映射 JSON
        |
选择 IP
        |
IP 无映射 -> 跳过
        |
发现 IP 根目录及一层子目录中的执行表
        |
每个处理单元独立读取 Excel Case 顺序
        |
并发读取 AW，但恢复原始 Case 顺序
        |
解析 WSym + 匹配 common/board_sensitive 默认值
        |
Pass 1：插入前序非默认历史状态
        |
删除当前 Case 中等于默认值的受管 WSym
        |
记录当前 Case 最后一次非默认写入
        |
Pass 2：恢复前置状态和当前非默认写入到 JSON 默认值
        |
生成 *_Normalized.dat
        |
可选生成 TestCtrlPara_AXCAUTO_6188_Normalized.dat
```
