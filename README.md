# ML307R 覆盖率测试技能集

一套完整的通信模组覆盖率测试技能，支持从 PDF 手册到测试报告的端到端流程。

## 概述

本项目包含 7 个技能，覆盖覆盖率测试的完整流程：

```
PDF手册 → 手册知识库 → 模块模型 → 用例生成 → 插桩 → 编译 → 烧录 → 测试执行 → 分析迭代 → 报告
```

## 技能列表

| 技能 | 说明 | 对应环节 |
|------|------|----------|
| `at-manual-knowledge-base` | 从 AT 手册 PDF 抽取命令、响应、URC、状态机 | 手册建模 |
| `coverage-instrumentation` | 源码自动插桩，生成 coverage_map.json | 插桩 |
| `coverage-build-flash` | 固件编译（增量）和烧录（ASR adownload） | 编译/烧录 |
| `coverage-test-execution` | AT 命令测试执行，bitmap 采集，分阶段策略 | 测试执行 |
| `coverage-analysis` | 覆盖率数据分析，未覆盖桩分类，迭代决策 | 分析迭代 |
| `coverage-report` | 测试报告生成（Markdown/JSON/Excel） | 报告 |
| `coverage-pipeline-main` | 主控协调，端到端流程编排 | 全流程 |

## 快速开始

### 1. 环境准备

- Windows 测试机 SSH 可达（默认 172.20.162.21:22，用户 52467）
- AT 串口 COM16 可用（115200 baud）
- MQTT Broker 可达（8.137.154.246:1883）
- SDK 路径：`D:\ML307R\SDK`

### 2. 安装技能

将技能目录复制到 `~/.hermes/skills/embedded-testing/`：

```bash
cp -r at-manual-knowledge-base ~/.hermes/skills/embedded-testing/
cp -r coverage-analysis ~/.hermes/skills/embedded-testing/
cp -r coverage-build-flash ~/.hermes/skills/embedded-testing/
cp -r coverage-instrumentation ~/.hermes/skills/embedded-testing/
cp -r coverage-pipeline-main ~/.hermes/skills/embedded-testing/
cp -r coverage-report ~/.hermes/skills/embedded-testing/
cp -r coverage-test-execution ~/.hermes/skills/embedded-testing/
```

### 3. 使用流程

#### 新模块测试（以 MQTT 为例）

```bash
# 1. 手册建模
# 技能: at-manual-knowledge-base
# 输入: MQTT用户手册.pdf
# 输出: module_model.yaml

# 2. 插桩
# 技能: coverage-instrumentation
# 输入: cm_atcmd_mqtt.c
# 输出: 插桩后 .c + coverage_map.json

# 3. 编译
# 技能: coverage-build-flash
# 输入: 插桩后源文件
# 输出: 固件 zip

# 4. 烧录
# 技能: coverage-build-flash
# 输入: 固件 zip
# 输出: 模组运行新固件

# 5. 测试执行
# 技能: coverage-test-execution
# 输入: coverage_map.json + 测试脚本
# 输出: run_result.json + coverage_delta.json

# 6. 分析迭代
# 技能: coverage-analysis
# 输入: run_result.json + coverage_map.json
# 输出: 下一轮用例

# 7. 报告
# 技能: coverage-report
# 输入: coverage_delta.json + uncovered_stubs.json
# 输出: report.md + .xlsx
```

## 目录结构

```
ml307r-coverage-skills/
├── README.md                           # 本文件
├── env.yaml                            # 环境配置模板
├── at-manual-knowledge-base/           # 手册建模技能
│   ├── SKILL.md
│   └── references/
├── coverage-instrumentation/           # 插桩技能
│   ├── SKILL.md
│   └── references/
├── coverage-build-flash/               # 编译烧录技能
│   ├── SKILL.md
│   └── references/
├── coverage-test-execution/            # 测试执行技能
│   ├── SKILL.md
│   └── references/
├── coverage-analysis/                  # 分析迭代技能
│   ├── SKILL.md
│   └── references/
├── coverage-report/                    # 报告生成技能
│   └── SKILL.md
├── coverage-pipeline-main/             # 主控协调技能
│   ├── SKILL.md
│   └── references/
├── tools/                              # 工具脚本
│   ├── generate_tests.py               # 用例生成器
│   └── executor.py                     # 通用执行器
├── modules/                            # 模块模型
│   └── mqtt_module_model.yaml
└── reports/                            # 报告模板
    ├── mqtt_coverage_loop_report.md
    ├── mqtt_coverage_runbook.md
    └── coverage_test_full_workflow.md
```

## 关键特性

### Bitmap 精确分析

支持 `AT+COVERAGE=2..9` 输出 MQTT bitmap 分块，精确计算每个 stub 是否命中：

```python
def bitmap_snapshot(ser):
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

### 分阶段执行策略

```
阶段1: CFG 测试（不需要连接）→ ~100 桩
阶段2: 建立连接 → ~53 桩
阶段3: SUB/PUB/READ/UNSUB → ~80 桩
阶段4: DNS 失败（放最后）→ ~3 桩
```

### 数据模式处理

`AT+MQTTPUB=...` 返回 `>` 后必须写入 payload：

```python
def pub_dm(ser, cmd, payload, timeout=8):
    ser.reset_input_buffer()
    ser.write((cmd + '\r\n').encode())
    prompt = read_until(ser, 3, ['>', 'ERROR', '+CME ERROR'])
    resp = prompt
    if '>' in prompt:
        ser.write(payload.encode())
        resp += '\n' + read_until(ser, timeout, ['OK', 'ERROR', '+CME ERROR', '+MQTTURC'])
    return resp
```

## 测试结果

### MQTT 模块（2026-06-23）

| 轮次 | stmt% | branch% | 命中/总数 | 关键改进 |
|------|-------|---------|----------|---------|
| v6 | 32% | 13% | 162/635 | bitmap 采集框架 |
| v7 | 38% | 15% | 191/635 | CFG/query/retrans/encoding |
| v8 | 33% | 11% | 163/635 | 连接保持策略 |
| v9 | 51% | 22% | 261/635 | 分阶段执行 + 全 CFG 矩阵 |

### 高收益 Case

| Case | 新增桩 | 说明 |
|------|--------|------|
| setup_conn | +53 | 建立连接全流程 |
| pub_dm_qos0 | +35 | 数据模式 QoS0 发布 |
| cfg_query_all_cids | +28 | 6 个 conn_id 的 query |
| cfg_will_matrix | +20 | will 遗嘱配置矩阵 |
| sub_multi | +19 | 3 topic 订阅 |

## Pitfalls

1. **DC ALL 会覆盖插桩文件** — 永远用 DC（增量）
2. **数据模式必须专门处理** — `AT+MQTTPUB=...` 返回 `>` 后必须写入 payload
3. **DNS 失败放最后** — 会破坏连接状态
4. **每 case 后采集 bitmap** — 否则无法计算增量
5. **coverage_map 必须生成** — 否则只能做粗粒度分析

## 相关文档

- [完整流程文档](reports/coverage_test_full_workflow.md)
- [MQTT 覆盖率闭环报告](reports/mqtt_coverage_loop_report.md)
- [MQTT 覆盖率 Runbook](reports/mqtt_coverage_runbook.md)

## License

MIT
