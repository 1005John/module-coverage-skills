# Kanban 跨机器协作设计文档

## 1. 问题

覆盖率测试流水线分布在多台机器上：

- **编译服务器** (192.168.242.120): 负责插桩 + 编译
- **测试电脑** (172.20.162.21 等，可能多台): 负责烧录 + 测试 + 分析

两方需要**双向信息交换**：

| 方向 | 信息 | 示例 |
|------|------|------|
| 测试PC → 编译服务器 | 需求 | "DNS 底层需要插桩 cm_async_dns.c" |
| 测试PC → 编译服务器 | 反馈 | "覆盖率有问题，COV_TOTAL_STUBS 太小" |
| 编译服务器 → 测试PC | 交付 | "固件已编译: fw.zip, 76桩" |
| 编译服务器 → 测试PC | 说明 | "cm_plat_dns.c 是死代码，不参与编译" |
| 测试PC → 测试PC | 协调 | "我在测 DNS，你先测 MQTT" |

**当前痛点**：所有信息交换依赖人工（用户在两个终端之间传话），无法无人值守。

**目标**：完全自动化，两个 Agent 通过共享任务板自主协调，无需人工干预。

## 2. 方案选型

| 方案 | 双向 | 状态管理 | 多机扩展 | 实现复杂度 | 结论 |
|------|------|----------|----------|------------|------|
| 共享文件 + Cron | 手动 | 手动 | 差 | 中 | 不够 |
| SSH hermes chat -q | 能做 | 无 | 差 | 低 | 单向，无状态 |
| Webhook | 能做 | 无 | 中 | 中 | 需 HTTP 可达 |
| **Kanban** | **原生** | **自动** | **好** | **低** | **✓ 最佳** |

**选择 Kanban**，原因：
1. Hermes 原生支持，不需要额外开发
2. 天然支持多 Agent 协作（assignee、tenant、atomic claim）
3. 内置状态管理（待办→进行中→完成→阻塞）
4. 支持 failure_limit 自动熔断
5. 支持 heartbeat 存活检测

## 3. 定位：跨技能的协调层

### 不是独立技能，是协调层

Kanban **不替代**现有技能，而是作为**协调层**连接它们：

```
┌─────────────────────────────────────────────────────────────┐
│                    Kanban 协调层                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  共享任务板 (SQLite)                                    │  │
│  │  - 任务创建/领取/完成/阻塞                              │  │
│  │  - assignee 路由                                       │  │
│  │  - tenant 隔离                                         │  │
│  │  - heartbeat + failure_limit                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐               │
│         ▼                 ▼                 ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 编译服务器     │  │ 测试电脑 #1   │  │ 测试电脑 #2   │      │
│  │              │  │              │  │              │      │
│  │ coverage-    │  │ coverage-    │  │ coverage-    │      │
│  │ instrumentation │ test-        │  │ test-        │      │
│  │ coverage-    │  │ execution    │  │ execution    │      │
│  │ build-flash  │  │ coverage-    │  │ coverage-    │      │
│  │ (编译部分)    │  │ analysis     │  │ analysis     │      │
│  │              │  │ coverage-    │  │ coverage-    │      │
│  │              │  │ report       │  │ report       │      │
│  │              │  │ coverage-    │  │ coverage-    │      │
│  │              │  │ build-flash  │  │ build-flash  │      │
│  │              │  │ (烧录部分)    │  │ (烧录部分)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 与 coverage-pipeline-main 的关系

`coverage-pipeline-main` 是**单机内的流程编排**（阶段 1-8）。
Kanban 是**跨机器的任务协调**（谁做什么、何时交接）。

```
coverage-pipeline-main (单机视角):
  阶段1 变更识别 → 阶段2 插桩 → ... → 阶段8 报告

Kanban (跨机视角):
  编译服务器: 领取"插桩任务" → 执行阶段1-2 → 提交"固件就绪"
  测试电脑:   领取"测试任务" → 执行阶段5c-8 → 提交"测试完成"
```

## 4. Board Schema

### 任务类型

```yaml
task_types:
  # 编译服务器执行
  instrument:
    title_pattern: "插桩 {module}"
    assignee: build-server
    inputs: [source_files, stub_id_ranges, coverage_map]
    outputs: [instrumented_files, firmware_zip, coverage_map]
    
  reinstrument:
    title_pattern: "重插桩 {module} - {reason}"
    assignee: build-server
    inputs: [feedback_from_test, target_files]
    outputs: [firmware_zip]

  # 测试电脑执行
  flash_and_test:
    title_pattern: "烧录测试 {module}"
    assignee: "{test_pc_id}"
    inputs: [firmware_zip, generated_tests_yaml]
    outputs: [run_result_json, coverage_report]
    
  analyze_and_report:
    title_pattern: "分析报告 {module}"
    assignee: "{test_pc_id}"
    inputs: [run_result_json]
    outputs: [report_md, report_xlsx, iteration_decision]
```

### 任务生命周期

```
         ┌──────────┐
         │  创建     │  (任一方创建)
         │  OPEN     │
         └────┬─────┘
              │
              ▼
         ┌──────────┐
         │  领取     │  (assignee 自动领取)
         │ CLAIMED   │
         └────┬─────┘
              │
         ┌────┴────┐
         ▼         ▼
   ┌──────────┐ ┌──────────┐
   │  完成     │ │  阻塞     │  (依赖未满足 / 失败)
   │ COMPLETED│ │ BLOCKED   │
   └────┬─────┘ └────┬─────┘
        │            │
        ▼            ▼
   ┌──────────┐ ┌──────────┐
   │ 下游领取  │ │ 解除阻塞  │  (问题解决后)
   │ (触发下一步)│ │ → 回到 OPEN │
   └──────────┘ └──────────┘
```

### Board 数据结构

```sql
-- Kanban SQLite schema (Hermes 内置，不需要自建)
tasks:
  id            INTEGER PRIMARY KEY
  title         TEXT     -- "插桩 DNS"
  description   TEXT     -- 详细说明、文件路径、桩ID范围
  status        TEXT     -- open/claimed/completed/blocked/archived
  assignee      TEXT     -- "build-server" / "test-pc1" / "test-pc2"
  tenant        TEXT     -- 隔离命名空间
  tags          TEXT     -- ["ML307C", "dns", "coverage"]
  priority      INTEGER  -- 0=普通, 1=高优
  result        TEXT     -- 完成后的输出（固件路径、覆盖率数据等）
  blocked_by    INTEGER  -- 依赖的 task id
  failure_count INTEGER  -- 连续失败次数
  created_at    DATETIME
  claimed_at    DATETIME
  completed_at  DATETIME
  heartbeat_at  DATETIME
```

## 5. 典型交互流程

### 流程 A：新模块覆盖率测试（首次）

```
TestPC                          Board                          BuildServer
  │                               │                               │
  │  kanban_create("插桩DNS")      │                               │
  │  assignee: build-server  ────→│                               │
  │  desc: AT手册已建模,           │                               │
  │    cm_atcmd_dns.c 需要插桩     │                               │
  │                               │                               │
  │                               │──── assignee领取 ────────────→│
  │                               │                               │
  │                               │    读取任务描述                 │
  │                               │    执行 coverage-instrumentation
  │                               │    执行 coverage-build-flash(编译)
  │                               │                               │
  │                               │←── kanban_complete ───────────│
  │                               │    result: "fw.zip, 76桩,      │
  │                               │      DNSAPI已编译, cm_plat_dns │
  │                               │      是死代码不参与"            │
  │                               │                               │
  │←──── Cron 检测到完成 ─────────│                               │
  │                               │                               │
  │  scp 下载固件                  │                               │
  │  执行 flash_module.py          │                               │
  │  执行 run_tests.py             │                               │
  │  执行 analyze_coverage.py      │                               │
  │                               │                               │
  │  覆盖率: 100%/49%, 已饱和      │                               │
  │  kanban_create("DNS测试完成")   │                               │
  │  result: "report.md,           │                               │
  │    branch 49% 饱和"      ────→│                               │
```

### 流程 B：覆盖率不足，需要重插桩

```
TestPC                          Board                          BuildServer
  │                               │                               │
  │  DNS branch 49% 饱和           │                               │
  │  分析: 需要底层插桩             │                               │
  │                               │                               │
  │  kanban_create("重插桩DNS")    │                               │
  │  assignee: build-server  ────→│                               │
  │  desc: "需要插桩 cm_async_dns.c│                               │
  │    桩ID: 800-899/3200-3299     │                               │
  │    参考: dns_instrumentation   │                               │
  │    _brief.md"                  │                               │
  │                               │                               │
  │                               │──── assignee领取 ────────────→│
  │                               │                               │
  │                               │    读取任务描述                 │
  │                               │    检查文件是否在 .mak 中       │
  │                               │    执行插桩                    │
  │                               │    编译                       │
  │                               │                               │
  │                               │←── kanban_complete ───────────│
  │                               │    result: "fw.zip, 76桩,      │
  │                               │      DNSAPI(4stmt+12branch)"  │
  │                               │                               │
  │←──── Cron 检测到完成 ─────────│                               │
  │                               │                               │
  │  下载 → 烧录 → 测试 → 分析     │                               │
  │  覆盖率: 100%/39%              │                               │
  │  结论: 底层桩 AT 命令不可达      │                               │
  │  kanban_create("DNS最终报告")  │                               │
  │  result: "branch 39%,         │                               │
  │    AT层天花板"            ────→│                               │
```

### 流程 C：编译失败反馈

```
BuildServer                     Board                          TestPC
  │                               │                               │
  │  编译报错: Undefined symbol    │                               │
  │  cov_dns_client_stmt_hits     │                               │
  │                               │                               │
  │  kanban_block(                │                               │
  │    task="重插桩DNS",     ────→│                               │
  │    reason="cm_plat_dns.c      │                               │
  │      不在.mak中,extern声明     │                               │
  │      需要移除"                 │                               │
  │  )                            │                               │
  │                               │                               │
  │                               │──── Cron 检测到阻塞 ─────────→│
  │                               │                               │
  │                               │    读取阻塞原因                 │
  │                               │    创建新任务: "修复extern声明" │
  │                               │    assignee: build-server      │
  │                               │                               │
  │←──── 新任务触发 ──────────────│                               │
  │                               │                               │
  │  修复 extern 声明              │                               │
  │  重新编译                     │                               │
  │  kanban_complete(...)    ────→│                               │
```

## 6. 实现方案

### 6.1 技能结构

```
coverage-pipeline-main/
├── SKILL.md                          # 更新：添加 Kanban 协调章节
└── references/
    ├── kanban-coordination.md        # 新增：本文档（精简版）
    ├── kanban-board-schema.md        # 新增：任务 schema 和生命周期
    ├── kanban-multi-pc-routing.md    # 新增：多测试PC路由策略
    └── ... (现有文件)
```

**不创建独立技能**，原因：
1. Kanban 是协调机制，不是独立功能
2. 放在 coverage-pipeline-main 下作为参考文档，与现有编排逻辑一致
3. 各执行技能（instrumentation、build-flash、test-execution）不需要改动，只需要知道"任务从哪来、结果往哪交"

### 6.2 Cron 配置

每台机器配置一个 Cron job 轮询 board：

```python
# 编译服务器
cronjob(
    name="kanban-build-worker",
    schedule="1m",
    prompt="""
    检查 Kanban board 中 assigned 给 build-server 的 OPEN 任务。
    如果有:
      1. 领取任务 (kanban_claim)
      2. 根据任务类型执行:
         - instrument: 执行 coverage-instrumentation
         - reinstrument: 根据反馈重新插桩
         - build: 执行 coverage-build-flash (编译)
      3. 完成任务 (kanban_complete)，结果包含固件路径和桩数
      4. 如果失败: kanban_block，说明失败原因
    如果没有: 静默退出
    """,
    skills=["coverage-instrumentation", "coverage-build-flash"]
)

# 测试电脑 #1
cronjob(
    name="kanban-test-pc1",
    schedule="1m",
    prompt="""
    检查 Kanban board 中 assigned 给 test-pc1 的 OPEN 任务。
    如果有:
      1. 领取任务
      2. 下载固件 (scp from build server)
      3. 烧录 (flash_module.py)
      4. 执行测试 (run_tests.py)
      5. 分析 (analyze_coverage.py)
      6. 报告 (generate_report.py)
      7. 完成任务，结果包含覆盖率数据和报告路径
      8. 如果覆盖率不足: 创建新任务 "重插桩XXX" assignee=build-server
    如果没有: 静默退出
    """,
    skills=["coverage-build-flash", "coverage-test-execution",
            "coverage-analysis", "coverage-report"]
)
```

### 6.3 Board 路由策略

**单 board 多 tenant 模式：**

```
board: coverage-pipeline.db
├── tenant: build-server        # 编译服务器的任务视图
├── tenant: test-pc1-ml307r     # 测试电脑1 (ML307R)
├── tenant: test-pc2-ml307c     # 测试电脑2 (ML307C)
└── tenant: test-pc3-ml302a     # 测试电脑3 (ML302A)
```

**Board 共享方式：**

| 方式 | 适合 | 延迟 |
|------|------|------|
| NFS/SMB 共享目录 | 同一局域网 | 0 |
| SSH scp 同步 | 跨网络 | 1-5 秒 |
| Git 同步 | 跨网络，可审计 | 10-30 秒 |

推荐：**SSH scp 同步**（与现有固件传输方式一致）。

每个 Cron tick：
1. scp 拉取远端 board → 本地
2. 处理本地任务
3. scp 推送更新后的 board → 远端

## 7. 与现有技能的融合

### 不需要修改执行技能

| 技能 | 是否需要改动 | 说明 |
|------|-------------|------|
| coverage-instrumentation | 否 | 不关心任务从哪来，照常执行 |
| coverage-build-flash | 否 | 编译/烧录逻辑不变 |
| coverage-test-execution | 否 | 测试逻辑不变 |
| coverage-analysis | 否 | 分析逻辑不变 |
| coverage-report | 否 | 报告逻辑不变 |
| at-manual-knowledge-base | 否 | 手册建模不变 |
| **coverage-pipeline-main** | **是** | 添加 Kanban 协调章节 |

### 只改 coverage-pipeline-main

在 SKILL.md 中添加：
1. Kanban 协调概述
2. 任务类型定义
3. Cron 配置模板
4. Board 路由策略
5. 多 PC 扩展指南

## 8. 实施计划

### Phase 1：单机验证（当前）
- 测试电脑创建 Kanban board
- 手动创建任务，验证 lifecycle
- Cron 轮询 + 自动执行

### Phase 2：双机联调
- 编译服务器配置 Kanban worker
- SSH scp 同步 board
- 端到端验证：测试PC创建任务 → 编译服务器执行 → 测试PC收到结果

### Phase 3：多 PC 扩展
- 新增测试电脑配置 tenant
- 验证任务路由和隔离
- 验证 failure_limit 和 heartbeat

## 9. 待决事项

1. **Board 同步频率** — 1 分钟 vs 更短？
2. **固件传输** — 是否走 Kanban 通知 + scp 独立传输？
3. **任务粒度** — 一个模块一个任务 vs 一次迭代一个任务？
4. **人工介入** — 何时需要人工审批（如烧录前确认）？
5. **日志聚合** — 多台 PC 的日志如何汇总查看？
