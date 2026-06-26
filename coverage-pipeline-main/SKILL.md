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

## 部署架构

**详见 DEPLOYMENT.md** — 双机分工架构文档。

编译服务器 (192.168.242.120): 阶段 1-2 (变更识别+插桩) + 阶段 5a (编译)
测试电脑 (172.20.162.21):     阶段 3-4 (建模+用例) + 阶段 5c (烧录) + 阶段 6-8 (测试+分析+报告)
中间跳板 (Mac):               阶段 5b (固件传输)

## 前置必读
加载本技能后，必须依次读取以下文件：
- references/end-to-end-module-coverage-workflow.md — 新模块端到端覆盖率测试实战流程（插桩→编译→烧录→测试→缺陷→报告）
- references/quick-start.md — 6 步快速开始流程
- references/script-inventory.md — 脚本清单和路径
- references/mqtt-testing-lessons.md — 12 轮迭代经验
- references/tcp-coverage-iteration-lessons.md — TCP 模块迭代经验（crash bug、数据模式、单连接策略）
- references/config-templates.md — env.yaml 和 module_config 模板
- references/test-pc-workspace-scripts.md — **测试电脑工作区脚本**：probe/flash/run/analyze/report 五个脚本用法
- coverage-analysis/references/automatic-test-generation.md — 完全自动测试用例生成与迭代设计
- references/at-manual-knowledge-base.md — AT 手册结构化知识库建模方法（命令/参数/响应/URC/状态机/流程/测试生成）
- references/at-manual-knowledge-base.md — AT 手册结构化知识库建模方法（命令/参数/响应/URC/状态机/流程/测试生成）
- references/incremental-instrumentation-design.md — Level 2 增量插桩设计方案（git diff 函数级，轮询检测，仓库架构）
- references/repo-polling-architecture.md — 仓库轮询架构（cron 模型、脚本路径、飞书推送）
- references/centralized-server-test-computer-architecture.md — 多工程师分层架构：中心服务器负责插桩/编译/artifact，测试电脑负责 AT 执行/迭代/经验/报告
- references/windows-server-deployment-state.md — Windows 服务器 192.168.242.120 实际部署状态（目录结构、已部署脚本、credentials、完成清单）
- references/test-machine-flash-workflow.md — 测试机 172.20.162.21 烧录与验证流程
- references/test-pc-workspace-scripts.md — 测试电脑完整工作区脚本（probe/flash/run/analyze/report 5 个脚本的接口和部署步骤）

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
- **增量模式**：当有旧版本 coverage_map.json 且变更为小版本提交时，可用 git diff 增量分析（见 coverage-instrumentation/references/git-diff-incremental-instrumentation.md），只对受影响函数重插桩，其余平移行号

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
9. **持续推进，不要频繁停下汇报**：用户要求"跑完整轮次/持续迭代"时，必须持续完成：执行当前用例集 → 落盘结果 → 分析覆盖率和失败项 → 生成下一轮增量用例或脚本 → 执行增量轮 → 输出闭环报告。只有明确硬阻塞（需要物理操作、需要设计决策、需要用户输入）时才停下来。不要每完成一个子步骤就停下问"接下来做什么"或汇报"完成了"。
10. **Windows 后台执行不可靠**：`Start-Process` / `start /b` 通过 SSH 执行时经常静默失败（创建空 stdout/stderr 后立即退出）。启动后必须检查 `tasklist`、日志增长、结果目录是否创建。若后台方式假跑，改用前台 SSH 长超时执行（`timeout=600`）。

## 验收标准

| 指标 | 目标值 |
|------|--------|
| 语句覆盖率 | >= 75% |
| 分支覆盖率 | >= 55% |
| 输出格式 | JSON + MD + Excel |
| 可复制性 | 另一个 Agent 按报告可独立继续 |

## 桩 ID 分配表（截至 2026-06-23）

| 模块 | 语句桩 ID | 分支桩 ID | 已用桩数 |
|------|-----------|-----------|----------|
| EXT (cm_atcmd_extern.c) | 0-53 | 1100+ | ~60 |
| MQTT (cm_atcmd_mqtt.c) | 100-500 | 1100-1332 | 635 |
| HTTP (cm_atcmd_http.c) | 200-437 | 2000-2211 | 450 |
| TCP (cm_atcmd_tcpip.c) | 500-799 | 2500-2661 | 462 |
| PING (cm_atcmd_ping.c) | 0-11 | 30-44 | 27 |
| PWM (cm_atcmd_pwm.c) | 0-29 | 30-52 | 53 |
| DNS (cm_atcmd_dns.c) | 0-98 | 100-148 | 148 |
| 新模块 | 按需分配 | 避免重叠 | - |

注意：HTTP API 层 (cm_http_api.c) 有独立计数器，360 桩，不在上述 ID 范围内。

## 新模块覆盖率报告集成（关键步骤）

插桩新模块后，`AT+COVERAGE?` 默认不显示该模块。必须修改 `cm_atcmd_extern.c`：

1. **extern 声明**：添加模块的 `cov_xxx_stmt_hits` / `cov_xxx_branch_hits` 声明
2. **GET_CMD 变量**：在 handler 中添加模块变量、更新 `_all_stmt` / `_all_branch` / `_all_total`
3. **sprintf 格式**：添加 `XXX(%lu%%,%lu%%,%lu/%lu)` 和对应参数

**编码**：`cm_atcmd_extern.c` 用 `latin-1` 编码读写，不要用 `utf-8` 或 `gbk`。

**验证**：烧录后 `AT+COVERAGE=1` + `AT+COVERAGE?` 应显示 `NEWMOD(0%,0%,0/N)`。

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

## 测试电脑（远程）工作流

测试电脑通过 SSH 从 Mac 中转获取服务器产物。三机架构：

```
服务器 (192.168.242.120)  →  Mac (orchestrator)  →  测试机 (172.20.162.21)
   插桩+编译                   SSH 编排                 烧录+AT测试
```

### 测试机环境（172.20.162.21, 用户 52467）

- Python 3.11.6 + pyserial 3.5
- 烧录工具：`D:\software\aboot-tools-2023.04.03\...\adownload.exe`
- AT 串口：COM16 (115200)
- 下载口：COM15 (ASR Serial Download Device)
- 工作目录：`D:\module_coverage_test\`
- 历史测试：`D:\ML307R\autocov\runs\`

### 产物传输流程

```bash
# 1. 服务器 → Mac
sshpass -p '123' scp Lenovo@192.168.242.120:'output/FINAL/*.zip' /tmp/artifacts/
sshpass -p '123' scp Lenovo@192.168.242.120:'output/PWM_FR004_final/coverage_map.*.json' /tmp/artifacts/

# 2. Mac → 测试机
scp /tmp/artifacts/* 52467@172.20.162.21:D:/module_coverage_test/
```

### 烧录流程

1. AT+MFORCEDL 进入下载模式
2. 等待 COM15 出现 ASR Serial Download Device
3. adownload.exe -q -a -u -s 115200 -r <firmware.zip>
4. 等待模块重启（~10s）
5. AT 验证 + AT+MSWVER 确认版本

参考脚本：测试机上 `C:\Users\52467\flash_coverage_detail.py`

## ⚠️ 关键 Pitfall: 编译前必须先运行 update_extern.py

**实战教训**：服务器编译了固件但没有先运行 update_extern.py 更新 cm_atcmd_extern.c，导致烧录后 AT+COVERAGE? 返回 ERROR。

**正确顺序**（不可打乱）：
```
1. instrument.py     → 生成插桩源码（含 cm_cov_xxx_hit）
2. update_extern.py  → 更新 cm_atcmd_extern.c（添加模块汇总入口）
3. 编译              → 生成固件 ZIP
4. 打包              → 生成 manifest + 产物目录
```

**验证方法**：编译前检查 cm_atcmd_extern.c 是否包含新模块的 extern 声明：
```bash
grep "cov_pwm_stmt_hits" cm_atcmd_extern.c  # 应有匹配
```

## Kanban 跨机器协调

**设计文档**: references/kanban-coordination-design.md

### 概述

多台机器（编译服务器 + N 台测试电脑）通过 Kanban 共享任务板协调工作。
执行技能不需要改动，Kanban 是协调层，负责"谁做什么、何时交接"。

### Board 共享方式

```
编译服务器 192.168.242.120          测试电脑 172.20.162.21
       │                                    │
       │    scp 同步 coverage-board.db       │
       │←──────────────────────────────────→│
       │                                    │
  Cron 1分钟轮询                       Cron 1分钟轮询
  领取 assigned:build-server 的任务    领取 assigned:test-pc1 的任务
```

### 任务类型

| 任务 | 创建方 | 执行方 | 说明 |
|------|--------|--------|------|
| instrument-{module} | 测试PC | 编译服务器 | 插桩+编译 |
| reinstrument-{module} | 测试PC | 编译服务器 | 根据反馈重插桩 |
| flash-test-{module} | 编译服务器 | 测试PC | 烧录+测试+分析+报告 |

### 任务生命周期

```
OPEN → CLAIMED → COMPLETED (成功)
                → BLOCKED (失败/依赖未满足) → OPEN (解决后重新开放)
```

### Cron Job 模板

**完整模板**: references/kanban-cron-templates.md — 可直接复制使用的 Cron 配置

#### 编译服务器 (build-server)

```python
cronjob(
    name="kanban-build-worker",
    schedule="1m",
    skills=["coverage-instrumentation", "coverage-build-flash"],
    prompt="""
    你是编译服务器的 Kanban worker。执行以下步骤:

    1. 拉取最新 board:
       scp 52467@172.20.162.21:D:/coverage-board.db /tmp/coverage-board.db

    2. 检查 assigned 给 build-server 的 OPEN 任务:
       kanban_list(filter="assignee:build-server, status:open")

    3. 如果有任务:
       a. kanban_claim(task_id)
       b. 读取任务描述，执行:
          - instrument 类型: 执行 coverage-instrumentation 插桩
          - reinstrument 类型: 根据 description 中的反馈重新插桩
          - 任何类型: 编译 (ML307R.bat DC 或 ML307C.bat DC-CN)
       c. scp 固件到测试PC:
          scp fw.zip 52467@172.20.162.21:D:/通信模组/at_kb_runs/
       d. kanban_complete(task_id, result="固件:fw.zip, 桩数:N")
       e. 如果失败: kanban_block(task_id, reason="失败原因")

    4. 推送更新后的 board:
       scp /tmp/coverage-board.db 52467@172.20.162.21:D:/coverage-board.db

    5. 如果没有任务: 静默退出
    """
)
```

#### 测试电脑 (test-pc)

```python
cronjob(
    name="kanban-test-worker",
    schedule="1m",
    skills=["coverage-build-flash", "coverage-test-execution",
            "coverage-analysis", "coverage-report"],
    prompt="""
    你是测试电脑的 Kanban worker。执行以下步骤:

    1. 检查 assigned 给本机的 OPEN 任务:
       kanban_list(filter="assignee:test-pc1, status:open")

    2. 如果有任务:
       a. kanban_claim(task_id)
       b. 读取任务描述中的固件路径
       c. 烧录: scripts/flash_module.py <firmware> --config env.yaml
       d. 验证 AT 口: scripts/probe_com16.py
       e. 执行测试: scripts/run_tests.py generated_tests.yaml --run-id <run_id>
       f. 分析: scripts/analyze_coverage.py runs/<run_id>
       g. 报告: scripts/generate_report.py runs/<run_id>
       h. kanban_complete(task_id, result="覆盖率:stmt%/branch%, 报告路径")
       i. 如果覆盖率不达标: 创建新任务 "reinstrument-{module}" 
          assignee=build-server, desc="需要插桩的具体文件和原因"

    3. 如果没有任务: 检查 build_status.json 是否有新固件
       如果有: 创建任务 "flash-test-{module}" assignee=自己
       如果没有: 静默退出

    4. 如果测试失败(crash等): kanban_block(reason="模组crash, 需要拔插USB")
    """
)
```

### Board 初始化

```bash
# 在测试电脑上执行
hermes kanban init --board coverage-pipeline

# 创建初始任务标签
hermes kanban create "等待编译服务器就绪" --tags setup --assignee build-server
```

### 多 PC 扩展

每新增一台测试电脑:
1. 配置该 PC 的 Kanban tenant (如 test-pc2-ml302a)
2. 配置 Cron job，assignee 改为对应 ID
3. Board 自动通过 scp 同步

### 待决事项

见 references/kanban-coordination-design.md 第 9 节。

1. **DC ALL 会覆盖插桩文件** — 永远用 DC（增量），手动删 .o 触发重编
2. **cm_coverage.c 的 COV_TOTAL_STUBS 必须 >= 最大桩 ID+1** — HTTP 分支桩到 2211，必须设 2500
3. **cm_atcmd_extern.c 有本地 cm_cov_hit()** — 不是用 cm_coverage.c 的，其 COV_TOTAL_STUBS 也需同步更新
4. **AT+COVERAGE? 的 output buffer 只有 64 字节** — 新增模块后需扩大到 256
5. **HTTP 覆盖率计数器在 cm_atcmd_http.c 中定义** — 需 extern 声明 + 在 sprintf 中报告
6. **单行 if/else 无花括号** — 插桩脚本不能在 body 前插 COV_STMT
7. **CM_RETURN/break 后的 COV_STMT** — 编译器报 unreachable error
8. **ReliableData.bin 缺失** — DC ALL 后 bin 目录被清空，需从 SDK 根目录复制或重跑 DC 自愈
9. **TCP MIPCLOSE 所有模式在数据交换后 crash** — mode=0/1/2 均导致模组重启。不关闭有数据的连接
10. **MIPSEND 必须用数据模式** — inline 格式报 CME ERROR:50。正确: `AT+MIPSEND=0,5` → 等 `>` 提示 → 发送原始数据
11. **长串口响应需循环读取** — MIPSTATE 查询所有返回 6 行，单次 read() 可能丢数据
12. **新模块插桩必须同时修改两个文件** — 模块源码 + cm_atcmd_extern.c，否则 AT+COVERAGE? 不显示新模块
13. **COV_BRANCH_START 必须大于所有 COV_STMT 最大 ID** — 否则 COV_STMT(50+) 被计为 branch，导致 stmt/branch 覆盖率混淆。推荐 COV_STMT 用 0-99，COV_BRANCH 用 100+，COV_BRANCH_START=100
14. **cm_atcmd_extern.c 中的分母硬编码** — sprintf 中 `(_xxx_stmt * 100) / N` 的 N 是 stmt 桩数。每次修改插桩后必须验证分母与实际桩数一致
15. **adownload.exe 烧录后占用串口** — 烧录完成后 adownload.exe 可能不退出，需 `taskkill /F /IM adownload.exe`
16. **QCOM_V1.6.exe 占用串口** — 测试机上的 QCOM 工具会占用 COM16，需先关闭

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

### 关键发现

1. **cm_atcmd_extern.c 桩污染**：cm_atcmd_extern.c 中有独立的桩（ID 1,3,5,6,53,55 等），这些桩被计入了所有模块的覆盖率统计。分析覆盖率时需要排除这些桩。

2. **ML302A_SUPPORT 条件编译**：ML307R 平台不编译 ML302A_SUPPORT 代码，coverage_map 中存在但固件中未编译的桩无法覆盖。

3. **硬件依赖路径**：cm_pwm_enable 失败路径等需要硬件配合才能触发的桩无法通过软件测试覆盖。

4. **覆盖率上限分析**：当覆盖率停滞不增时，必须分析上限原因，不要盲目生成更多用例。计算实际覆盖率 = 已覆盖桩 / (总桩数 - 外部桩 - 条件编译桩 - 硬件依赖桩)。

### 连接管理

- 每次 case 前检查 `AT+MQTTSTATE=<cid>`
- 断开则重新连接
- CFG 测试不需要连接，应优先执行
- DNS 失败放最后，会破坏连接状态

### 数据模式处理

`AT+MQTTPUB=...` 返回 `>` 后必须写入 payload，再继续读取 `+MQTTPUB`/`OK`/`+MQTTURC`。通用 executor 不支持此模式，需要专门的 `pub_dm()` 函数。
