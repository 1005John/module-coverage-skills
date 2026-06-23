---
name: coverage-pipeline-main
description: "自治式通信模组覆盖率测试流水线主控技能，协调插桩、编译、测试、迭代、报告全流程"
triggers:
  - "覆盖率测试"
  - "coverage pipeline"
  - "自动测试"
  - "模块覆盖率"
---

# 覆盖率测试流水线主控

## When to Use
- 需要对 AT 命令源码进行覆盖率插桩、编译、烧录、测试、迭代
- 用户要求"自动跑覆盖率"或"插桩+测试"某个模块
- 目标模块有明确的 AT 命令（MQTT/HTTP/TCP 等）

## 前置必读
加载本技能后，必须依次读取以下文件：
- references/end-to-end-module-coverage-workflow.md — 新模块端到端覆盖率测试实战流程（插桩→编译→烧录→测试→缺陷→报告）
- references/quick-start.md — 6 步快速开始流程
- references/script-inventory.md — 脚本清单和路径
- references/mqtt-testing-lessons.md — 12 轮迭代经验
- references/tcp-coverage-iteration-lessons.md — TCP 模块迭代经验（crash bug、数据模式、单连接策略）
- references/config-templates.md — env.yaml 和 module_config 模板
- coverage-analysis/references/automatic-test-generation.md — 完全自动测试用例生成与迭代设计
- references/at-manual-knowledge-base.md — AT 手册结构化知识库建模方法（命令/参数/响应/URC/状态机/流程/测试生成）

## 阶段流程

```
1. 变更识别 → 2. 插桩与桩级映射 → 3. 模块模型 → 4. 用例生成 → 5. 编译下载 → 6. 测试执行 → 7. 分析迭代 → 8. 报告生成
```

### 阶段 1：变更识别
- 拉取最新代码和文档
- 对比 git diff，识别变更文件、函数、分支条件
- 输出 change_analysis.json

### 阶段 2：插桩与桩级映射
- 技能：coverage-instrumentation
- 在测试工作区生成插桩源码
- 输出 `coverage_map.json`，必须包含 stub_id、文件、行号、函数、分支条件、附近源码、命令/参数提示
- 若当前固件只能返回 hit/total，需评估增加 bitmap/命中 ID 查询能力，否则只能做粗粒度迭代

### 阶段 3：模块模型
- 从 AT 手册、源码解析和历史测试经验生成 `module_model.yaml`
- 描述命令格式、参数类型、有效/无效范围、状态机、URC、timeout、破坏性等级
- HTTP/MQTT 等模块必须先有模型，再生成自动用例

### 阶段 4：用例生成
- 技能：coverage-analysis
- 根据 `module_model.yaml` + `coverage_map.json` + 历史 `coverage_delta.json` 生成候选池
- 输出 `testcase_pool.json`、`iteration_decision.json`、`generated_tests.yaml`
- `generated_tests.yaml` 是测试执行器唯一输入，禁止每轮手写新 vN 脚本作为主路径

### 阶段 5：编译下载
- 技能：coverage-build-flash
- 增量编译（禁止 DC ALL）
- 烧录到模组
- 验证 AT 口可用

### 阶段 6：测试执行
- 技能：coverage-test-execution
- 执行 `generated_tests.yaml` 中的 AT 命令用例
- 查询覆盖率和桩级命中明细
- 按 `expected_result` 判定行为结果
- 输出 `at_execution_log.txt`、`run_result.json`、`assertion_result.json`、`bug_candidates.json`、`coverage_summary.json`、`coverage_delta.json`

### 阶段 7：分析迭代
- 技能：coverage-analysis
- 分析未覆盖桩、每个 case 的新增收益和断言失败项
- 自动生成下一轮 `generated_tests.yaml`
- 断言失败生成 `bug_candidates.json`，覆盖率新增不能抵消行为失败
- 连续 2 轮新增命中为 0 → 覆盖率饱和，停止覆盖率迭代；若仍有 bug candidates，继续输出缺陷报告

### 阶段 8：报告生成
- 技能：coverage-report
- 输出 `run_summary.md`、`coverage_report.xlsx`、机器可读 JSON
- 报告必须包含每轮覆盖率表、阶段增量表、潜在 bug 表、未覆盖原因、饱和判断和下一步建议

## 关键约束

1. **禁止修改业务代码**，只允许插桩、测试模型、用例、执行脚本和报告
2. **插桩默认存放在 Windows 测试工作区**，不提交仓库
3. **编译禁止使用 ML307R.bat DC ALL**（会从 ps.7z 归档恢复源码覆盖插桩）
4. **覆盖率数据必须来自真实 AT 返回**，不得伪造
5. **烧录失败不得冒充成功**
6. **自动模式必须数据驱动**：执行器消费 `generated_tests.yaml`，不得把每轮新增用例继续写死在 vN 脚本中
7. **桩级明细优先**：没有命中 ID/bitmap 时必须标记 coarse_delta_only，不能假装知道具体命中桩
8. **行为断言优先级不低于覆盖率**：新增覆盖但预期不符时必须报潜在 bug，不能算测试通过

## 验收标准

| 指标 | 目标值 |
|------|--------|
| 语句覆盖率 | >= 75% |
| 分支覆盖率 | >= 55% |
| 输出格式 | JSON + MD + Excel |
| 可复制性 | 另一个 Agent 按报告可独立继续 |

## 桩 ID 分配表（截至 2026-06-22）

| 模块 | 语句桩 ID | 分支桩 ID | 已用桩数 |
|------|-----------|-----------|----------|
| EXT (cm_atcmd_extern.c) | 0-53 | 1100+ | ~60 |
| MQTT (cm_atcmd_mqtt.c) | 100-500 | 1100-1332 | 635 |
| HTTP (cm_atcmd_http.c) | 200-437 | 2000-2211 | 450 |
| TCP (cm_atcmd_tcpip.c) | 500-799 | 2500-2661 | 462 |
| 新模块 | 按需分配 | 避免重叠 | - |

注意：HTTP API 层 (cm_http_api.c) 有独立计数器，360 桩，不在上述 ID 范围内。

## 编译与打包的分离（关键 Pitfall）

编译和 release zip 打包是**两个独立步骤**：
- **编译** (gnumake + armcc) 生成 `.o` → `.axf` → 各分区 `.bin`
- **打包** (releasepackage 工具) 将 `.bin` + `ReliableData.bin` 打成 release zip

**ReliableData.bin 缺失时**：
- 编译成功（.o 和 .axf 正常生成）
- 打包失败（"open raw image rd failed"）
- **但 .axf 已经可以用了**

解决方案：
1. 从 ps.7z 或之前的 release zip 中提取 ReliableData.bin
2. 运行 `generate_reliabledata.pl`（需要 Perl + 正确的 .gki 文件）
3. 或者接受编译成功、手动处理打包

**验证编译是否成功**：检查 `.o` 文件存在且 > 0 字节，不看 release zip 是否生成。

## TCP 模块已知 Crash Bug (固件 3.1.0.2606221536_release)

| Bug | 操作 | 结果 | Workaround |
|-----|------|------|------------|
| MIPCLOSE crash | MIPOPEN→MIPSEND→MIPCLOSE (mode=0/1/2) | 模组重启 | 不关闭有数据的连接 |
| MIPMODE crash | MIPMODE=0,1 在已连接 socket | 模组重启 | MIPOPEN 时直接指定 mode |
| MIPOPEN mode 冲突 | 有 mode=0 连接时开 mode=1/2 | 模组重启 | 每种 mode 独立重启测试 |

**影响**：TCP 覆盖率测试不能在同一会话中测试多种 access_mode。每种 mode 需要重启模组后独立测试。
**其他模块（MQTT/HTTP）的 close 命令需验证是否存在同样问题。**

## 常见 Pitfalls

1. **DC ALL 会覆盖插桩文件** — 永远用 DC（增量），手动删 .o 触发重编
2. **cm_coverage.c 的 COV_TOTAL_STUBS 必须 >= 最大桩 ID+1** — HTTP 分支桩到 2211，必须设 2500
3. **cm_atcmd_extern.c 有本地 cm_cov_hit()** — 不是用 cm_coverage.c 的，其 COV_TOTAL_STUBS 也需同步更新
4. **AT+COVERAGE? 的 output buffer 只有 64 字节** — 新增模块后需扩大到 256
5. **HTTP 覆盖率计数器在 cm_atcmd_http.c 中定义** — 需 extern 声明 + 在 sprintf 中报告
6. **单行 if/else 无花括号** — 插桩脚本不能在 body 前插 COV_STMT
7. **CM_RETURN/break 后的 COV_STMT** — 编译器报 unreachable error
8. **ReliableData.bin 缺失** — DC ALL 后 bin 目录被清空，需从 SDK 根目录复制或重跑 DC 自愈
9. **TCP MIPCLOSE 所有模式在数据交换后 crash** — mode=0/1/2 均导致模组重启。不关闭有数据的连接。详见 references/tcp-module-crash-bugs.md
10. **TCP MIPMODE 0→1 切换 crash** — 在已连接 socket 上切 cache_stream 导致 crash。需在 MIPOPEN 时直接指定 access_mode
11. **MIPSEND 必须用数据模式** — 不带 data 参数发 `AT+MIPSEND=0,5`，等 `>` 提示后发送。内联格式报 CME ERROR: 50
9. **MIPCLOSE crash (TCP)** — 所有 MIPCLOSE 模式 (0/1/2) 在数据交换后关闭连接导致模组崩溃。workaround: 不关闭连接或等超时。其他模块的 close 命令需验证
10. **MIPSEND 必须用数据模式** — inline 格式 `AT+MIPSEND=0,5,"DATA"` 返回 CME ERROR:50。正确: `AT+MIPSEND=0,5` → 等 `>` 提示 → 发送原始数据
11. **长串口响应需循环读取** — MIPSTATE 查询所有返回 6 行，单次 read() 可能丢数据。用 while 循环 + in_waiting + OK/ERROR 判断终止
12. **YAML 测试用例引号处理** — `cmd: 'AT+MIPCFG="key",0,1'` 外层单引号内层双引号，解析器需 `.strip("'").strip('"')`

## 验证清单

- [ ] env.yaml 字段完整（validate_env.py 通过）
- [ ] AT 手册已抽取，manual_expectations.<module>.json 可追溯
- [ ] 插桩后文件编译通过（0 error）
- [ ] 烧录后 AT 口响应 OK
- [ ] AT+COVERAGE? 显示正确的总桩数且计数器不超过 100%
- [ ] 测试脚本执行完毕（无串口卡死）
- [ ] 每轮结果包含覆盖率、断言、bug_candidates
- [ ] 覆盖率达标或饱和原因明确
- [ ] 报告包含每轮覆盖率表、阶段增量表、潜在 bug 表和下一步建议

## MQTT 覆盖率测试完整流程（2026-06-23 验证）

### 最终成果

MQTT 635 桩，覆盖率 51%/22% (261/635)

### 分阶段执行策略

```
阶段1: CFG 测试（不需要连接）→ ~100 桩
阶段2: 建立连接 → ~53 桩
阶段3: SUB/PUB/READ/UNSUB → ~80 桩
阶段4: DNS 失败（放最后）→ ~3 桩
```

### Bitmap 采集

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

### 高收益 Case 排序

| Case | 新增桩 | 说明 |
|------|--------|------|
| setup_conn | +53 | 建立连接全流程 |
| pub_dm_qos0 | +35 | 数据模式 QoS0 发布 |
| cfg_query_all_cids | +28 | 6 个 conn_id 的 query |
| cfg_will_matrix | +20 | will 遗嘱配置矩阵 |
| sub_multi | +19 | 3 topic 订阅 |
| cfg_platform_devinfo | +16 | 平台认证配置 |
| pubjson | +15 | JSON 发布 |
| cfg_reconn_matrix | +13 | 重连配置矩阵 |
| unsub_one | +11 | 取消订阅 |
| cfg_encoding_matrix | +10 | 编码配置矩阵 |

### 未覆盖热点（366 桩剩余）

| 函数 | 未覆盖 | 说明 |
|------|--------|------|
| subscribe_cmd | 45 | 多 topic/qos 组合 |
| connect_cmd | 44 | 多 conn_id/重复连接 |
| publish_cmd_combine | 37 | inline/datamode 边界 |
| datamode_cb | 30 | 数据模式回调 |
| cfg_platform_devinfo | 29 | devinfo 设置 |

### 连接管理

- 每次 case 前检查 `AT+MQTTSTATE=<cid>`
- 断开则重新连接
- CFG 测试不需要连接，应优先执行
- DNS 失败放最后，会破坏连接状态

### 数据模式处理

`AT+MQTTPUB=...` 返回 `>` 后必须写入 payload，再继续读取 `+MQTTPUB`/`OK`/`+MQTTURC`。通用 executor 不支持此模式，需要专门的 `pub_dm()` 函数。
