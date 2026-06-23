# ML307R 覆盖率测试完整流程

## 流程概览

```
PDF手册 → 手册知识库 → 模块模型 → 用例生成 → 插桩 → 编译 → 烧录 → 测试执行 → 分析迭代 → 报告
   ↓           ↓           ↓           ↓         ↓       ↓       ↓           ↓           ↓         ↓
  输入      结构化模型    YAML模型    测试用例   桩映射   固件    模组      结果数据    覆盖率    最终报告
```

## 详细流程

### 阶段 1: 手册知识库建模

**技能**: `at-manual-knowledge-base`

**输入**:
- AT 手册 PDF（如 `MQTT用户手册.pdf`、`HTTP_HTTPS用户手册.pdf`）
- 手册路径：`/Volumes/DevDrive/test_report_ref/`

**输出**:
- `module_model.yaml` — 结构化模块模型
- `manual_expectations.json` — 手册预期响应

**处理内容**:
1. 从 PDF 抽取命令清单（AT+MQTTCONN、AT+MQTTPUB 等）
2. 提取每个命令的：
   - 语法格式
   - 参数类型、范围、默认值
   - 成功响应、错误响应
   - 异步 URC
   - 状态机依赖
3. 生成测试规则：
   - 正向流程
   - 参数边界
   - 状态负向
   - 覆盖率导向

**示例输出** (`module_model.yaml`):
```yaml
module: MQTT
commands:
  - command: AT+MQTTCONN
    syntax: AT+MQTTCONN=<conn_id>,<host>,<port>,<client_id>,<user>,<pass>
    parameters:
      - name: conn_id
        type: integer
        range: [0, 5]
      - name: host
        type: string
        max_length: 128
    responses:
      success: OK
      async: +MQTTURC: "conn",<conn_id>,<code>
    preconditions:
      - PDP_ACTIVE
```

---

### 阶段 2: 插桩与桩级映射

**技能**: `coverage-instrumentation`

**输入**:
- 源文件：`D:\ML307R\SDK\onemo\at\src\cm_atcmd_mqtt.c`
- 桩 ID 范围：MQTT 100-500 (stmt) / 1100-1332 (branch)

**输出**:
- 插桩后的 `.c` 文件
- `coverage_map.json` — 桩 ID → 位置映射

**处理内容**:
1. 正则匹配函数签名
2. 在函数入口、if/else 体、关键执行行插入 `COV_STMT(id)` / `COV_BRANCH_T(id)` / `COV_BRANCH_F(id)`
3. 跳过多行表达式、单行 if、return/goto 后的行
4. 生成桩映射：stub_id → 函数、行号、类型、上下文

**示例输出** (`coverage_map.json`):
```json
{
  "module": "MQTT",
  "source_file": "cm_atcmd_mqtt.c",
  "total_stubs": 635,
  "stubs": {
    "100": {"func": "cm_at_mqtt_connect_cmd", "type": "stmt", "line": 237},
    "1100": {"func": "cm_at_mqtt_connect_cmd", "type": "branch_true", "line": 240}
  }
}
```

**反扫方法**（如果 map 丢失）:
```python
# 从插桩后的源码反扫
python3 rebuild_coverage_map.py
# 输出: coverage_map.mqtt.json (627 桩)
```

---

### 阶段 3: 编译

**技能**: `coverage-build-flash`

**输入**:
- 插桩后的源文件
- SDK 路径：`D:\ML307R\SDK`

**输出**:
- `ML307R-DC-MBRH0S01_*_release.zip` — 固件包

**处理内容**:
1. 清理缓存（`.o`、`.d`、`.pp`、`pack_c.via`）
2. 增量编译：`ML307R.bat DC`（禁止 DC ALL）
3. 验证编译产物（`.o` > 0 字节、`.axf` 存在）

**关键命令**:
```bash
# 清理缓存
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_mqtt.*"
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\pack_c.via"

# 增量编译
ssh 52467@172.20.162.21 "cd /d D:\\ML307R\\SDK && cmd /c ML307R.bat DC"
```

**期望输出**:
```
ML307R-DC-MBRH0S01_3.1.0.XXXXXXXX_release.zip
```

---

### 阶段 4: 烧录

**技能**: `coverage-build-flash`

**输入**:
- 固件包：`ML307R-DC-MBRH0S01_*_release.zip`

**输出**:
- 模组运行新固件

**处理内容**:
1. 发送 `AT+MFORCEDL` 进入下载模式
2. 执行 `adownload.exe -q -a -u -s 115200 -r <firmware.zip>`
3. 等待烧录完成（`aboot download engine stopped successfully`）
4. 物理拔插 USB 恢复 AT 口
5. 验证 AT 口响应 OK

**关键命令**:
```bash
# 发送 AT+MFORCEDL
ssh 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT+MFORCEDL\\r\\n'); import time; time.sleep(2); s.close()\""

# 烧录
ssh 52467@172.20.162.21 "D:\\software\\aboot-tools-...\\adownload.exe -q -a -u -s 115200 -r D:\\ML307R\\SDK\\target\\ML307R-DC-MBRH0S01\\ML307R-DC-MBRH0S01_*_release.zip"

# 验证
ssh 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT\\r\\n'); import time; time.sleep(1); print(s.read_all()); s.close()\""
```

**期望输出**:
```
b'\r\nOK\r\n'
```

---

### 阶段 5: 测试执行

**技能**: `coverage-test-execution`

**输入**:
- `coverage_map.json` — 桩映射
- `module_model.yaml` — 模块模型（可选）
- 测试脚本

**输出**:
- `run_result.json` — 每条 case 的响应和增量
- `coverage_delta.json` — case → stub id 映射
- `uncovered_stubs.json` — 未覆盖桩列表
- `at_execution_log.txt` — 完整 AT 日志

**处理内容**:
1. 清零覆盖率：`AT+COVERAGE=1`
2. 分阶段执行：
   - 阶段1: CFG 测试（不需要连接）
   - 阶段2: 建立连接
   - 阶段3: SUB/PUB/READ/UNSUB
   - 阶段4: DNS 失败（放最后）
3. 每 case 后采集 bitmap：`AT+COVERAGE=2..9`
4. 计算增量：`new_ids = after_ids - before_ids`
5. 连接管理：每次 case 前检查 `AT+MQTTSTATE`

**关键函数**:
```python
def bitmap_snapshot(ser):
    """采集 MQTT bitmap，返回 hit stub id 集合"""
    words = {}
    for cmd_value in range(2, 10):
        resp = at(ser, f'AT+COVERAGE={cmd_value}', 1.5)
        m = re.search(r'\+COVERAGE_DETAIL:\s*MQTT,(\d+),(\d+),([0-9A-Fa-f,]+)', resp)
        if m:
            base = int(m.group(2))
            hex_words = m.group(3).split(',')[:8]
            for off, word in enumerate(hex_words):
                words[base + off] = int(word, 16)
    ids = set()
    for word_index, word in words.items():
        for bit in range(32):
            sid = word_index * 32 + bit
            if word & (1 << bit):
                ids.add(sid)
    return words, ids
```

**高收益 Case 排序**（MQTT 实测）:
| Case | 新增桩 |
|------|--------|
| setup_conn | +53 |
| pub_dm_qos0 | +35 |
| cfg_query_all_cids | +28 |
| cfg_will_matrix | +20 |
| sub_multi | +19 |

---

### 阶段 6: 分析迭代

**技能**: `coverage-analysis`

**输入**:
- `run_result.json`
- `coverage_delta.json`
- `coverage_map.json`

**输出**:
- `coverage_analysis.json` — 分析结果
- `iteration_decision.json` — 下一轮决策
- `generated_tests.yaml` — 下一轮用例

**处理内容**:
1. 统计未覆盖桩，按函数分类
2. 分析断言失败项，生成 bug_candidates
3. 识别高价值命令
4. 生成下一轮用例
5. 判断饱和条件（连续 2 轮新增为 0）

**未覆盖桩分类**:
| 原因 | 判断方法 | 应对策略 |
|------|----------|----------|
| 参数校验未触发 | 桩在 getExtValue 附近 | 补充边界值 |
| 错误处理未触发 | 桩在 CME ERROR 返回前 | 触发错误条件 |
| 连接状态未到达 | 桩在 connected 分支 | 确保连接成功 |
| 异步回调未触发 | 桩在 URC 处理中 | 等待 URC |
| 平台特定路径 | 桩在 platsel/DevInfo | 特定平台配置 |

---

### 阶段 7: 报告生成

**技能**: `coverage-report`

**输入**:
- `coverage_delta.json`
- `uncovered_stubs.json`
- `run_result.json`

**输出**:
- `report.md` — Markdown 报告
- `coverage_report.xlsx` — Excel 报告
- `run_summary.json` — 机器可读摘要

**报告内容**:
1. 覆盖率统计（stmt%/branch%/hit/total）
2. 每轮迭代对比表
3. 高收益 Case 列表
4. 未覆盖热点 Top N
5. 潜在 Bug 列表
6. 饱和判断
7. 下一步建议

---

## 技能与环节对应关系

| 环节 | 技能 | 输入 | 输出 |
|------|------|------|------|
| 手册建模 | `at-manual-knowledge-base` | PDF 手册 | `module_model.yaml` |
| 插桩 | `coverage-instrumentation` | 源文件 | 插桩后 `.c` + `coverage_map.json` |
| 编译 | `coverage-build-flash` | 插桩后源文件 | 固件 zip |
| 烧录 | `coverage-build-flash` | 固件 zip | 模组运行新固件 |
| 测试执行 | `coverage-test-execution` | `coverage_map.json` + 测试脚本 | `run_result.json` + `coverage_delta.json` |
| 分析迭代 | `coverage-analysis` | `run_result.json` + `coverage_map.json` | `coverage_analysis.json` + 下一轮用例 |
| 报告 | `coverage-report` | `coverage_delta.json` + `uncovered_stubs.json` | `report.md` + `.xlsx` |
| 主控协调 | `coverage-pipeline-main` | 所有技能 | 端到端流程 |

---

## 新模块使用指南

### 假设要测试 HTTP 模块

#### 步骤 1: 手册建模

```bash
# 1. 准备手册
ls /Volumes/DevDrive/test_report_ref/HTTP_HTTPS用户手册*.pdf

# 2. 运行手册建模
# 技能: at-manual-knowledge-base
# 输出: module_model.http.yaml
```

#### 步骤 2: 插桩

```bash
# 1. 获取源文件
scp 52467@172.20.162.21:D:/ML307R/SDK/onemo/at/src/cm_atcmd_http.c /tmp/

# 2. 运行插桩脚本
python3 instrument_http_v2.py /tmp/cm_atcmd_http.c /tmp/cm_atcmd_http_instrumented.c

# 3. 上传插桩后的文件
scp /tmp/cm_atcmd_http_instrumented.c 52467@172.20.162.21:D:/ML307R/SDK/onemo/at/src/cm_atcmd_http.c

# 4. 生成 coverage_map
python3 rebuild_coverage_map.py --module HTTP --source cm_atcmd_http.c
# 输出: coverage_map.http.json
```

#### 步骤 3: 编译

```bash
# 清理缓存
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_http.*"
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\pack_c.via"

# 增量编译
ssh 52467@172.20.162.21 "cd /d D:\\ML307R\\SDK && cmd /c ML307R.bat DC"
```

#### 步骤 4: 烧录

```bash
# 发送 AT+MFORCEDL
ssh 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT+MFORCEDL\\r\\n'); import time; time.sleep(2); s.close()\""

# 烧录
ssh 52467@172.20.162.21 "adownload.exe -q -a -u -s 115200 -r <firmware.zip>"

# 验证
ssh 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT\\r\\n'); import time; time.sleep(1); print(s.read_all()); s.close()\""
```

#### 步骤 5: 测试执行

```bash
# 生成测试用例（基于 module_model.http.yaml）
python3 generate_tests.py module_model.http.yaml generated_tests.http.yaml

# 执行测试
python3 run_http_bitmap_v1.py
# 输出: D:\ML307R\at_kb_runs\http-v1-bitmap\
```

#### 步骤 6: 分析迭代

```bash
# 分析结果
python3 analyze_coverage.py D:\ML307R\at_kb_runs\http-v1-bitmap\

# 生成下一轮用例
python3 generate_next_round.py D:\ML307R\at_kb_runs\http-v1-bitmap\coverage_delta.json

# 执行下一轮
python3 run_http_bitmap_v2.py
```

#### 步骤 7: 报告

```bash
# 生成报告
python3 generate_report.py D:\ML307R\at_kb_runs\http-v*-bitmap\
# 输出: http_coverage_report.md + http_coverage_report.xlsx
```

---

## 关键 Pitfalls

1. **DC ALL 会覆盖插桩文件** — 永远用 DC（增量）
2. **数据模式必须专门处理** — `AT+MQTTPUB=...` 返回 `>` 后必须写入 payload
3. **DNS 失败放最后** — 会破坏连接状态
4. **每 case 后采集 bitmap** — 否则无法计算增量
5. **连接管理** — 每次 case 前检查 `AT+MQTTSTATE`，断开则重新连接
6. **coverage_map 必须生成** — 否则只能做粗粒度分析
7. **bitmap 接口必须验证** — `AT+COVERAGE=2..9` 返回 `ERROR` 说明固件不支持

---

## 文件清单

```
/Volumes/DevDrive/projects/at_knowledge_base/
├── tools/
│   ├── generate_tests.py          # 用例生成器
│   ├── executor.py                # 通用执行器
│   ├── instrument_mqtt_v5.py      # MQTT 插桩脚本
│   ├── instrument_http_v2.py      # HTTP 插桩脚本
│   ├── rebuild_coverage_map.py    # coverage_map 反扫
│   └── run_mqtt_bitmap_v9.py      # MQTT 测试脚本
├── modules/
│   ├── mqtt_module_model.yaml     # MQTT 模块模型
│   └── http_module_model.yaml     # HTTP 模块模型
├── reports/
│   ├── mqtt_coverage_loop_report.md  # MQTT 端到端报告
│   └── mqtt_coverage_runbook.md      # 可复制的 runbook
└── env.yaml                       # 环境配置

D:\ML307R\at_kb_runs\
├── coverage_map.mqtt.json         # MQTT 桩映射
├── coverage_map.http.json         # HTTP 桩映射
├── mqtt-v9-bitmap\                # MQTT 测试结果
│   ├── run_result.json
│   ├── coverage_delta.json
│   ├── uncovered_stubs.json
│   └── report.md
└── http-v1-bitmap\                # HTTP 测试结果
    └── ...
```
