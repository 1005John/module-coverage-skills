# 部署架构 — 双机分工

## 概述

覆盖率测试流水线运行在两台机器上：

```
┌─────────────────────────────────────────────────────────────────────┐
│  编译服务器 (192.168.242.120, Lenovo/123)                            │
│  ─────────────────────────────────────────────────────────────────  │
│  poll-repo-monitor        Git 轮询仓库变更                           │
│  change-analysis          git diff 分析变更文件                       │
│  coverage-instrumentation 源码插桩 (COV_STMT/COV_BRANCH)             │
│  coverage-build-flash     编译部分 (ML307R.bat DC / ML307C.bat DC-CN)│
│                                                                     │
│  产物: 插桩后源码 + coverage_map.json + release.zip                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ 固件 zip 传输 (scp 两跳: 服务器→Mac→测试机)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  测试电脑 (172.20.162.21, 52467)                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  at-manual-knowledge-base AT 手册 PDF 抽取 → module_model.yaml       │
│  coverage-build-flash     烧录部分 (adownload.exe + COM16)           │
│  coverage-test-execution  AT 命令测试 (串口 COM16, 115200)           │
│  coverage-analysis        覆盖率分析 + 迭代决策                       │
│  coverage-report          报告生成 (MD + Excel)                      │
│                                                                     │
│  工作区: D:\通信模组\at_kb_runs\                                     │
│  手册:   D:\通信模组\手册\                                           │
└─────────────────────────────────────────────────────────────────────┘
```

## 技能分工明细

### 编译服务器负责

| 技能 | 原因 | 产物 |
|------|------|------|
| poll-repo-monitor | Git 轮询，纯网络操作 | 变更通知 |
| change-analysis | git diff 分析，纯 CPU | change_analysis.json |
| coverage-instrumentation | 源码修改，纯文件操作 | 插桩后 .c + coverage_map.json |
| coverage-build-flash (编译) | armcc/gnumake 编译 | .o → .axf → release.zip |

### 测试电脑负责

| 技能 | 原因 | 产物 |
|------|------|------|
| at-manual-knowledge-base | PDF 抽取，产出在测试电脑消费 | module_model.yaml |
| coverage-build-flash (烧录) | 需要 COM16 串口物理连接 | 模组运行新固件 |
| coverage-test-execution | AT 命令收发，必须 COM 口 | run_result.json |
| coverage-analysis | 依赖测试结果数据 | coverage_delta.json |
| coverage-report | 依赖测试结果数据 | report.md + report.xlsx |

### 协作流程 (coverage-pipeline-main)

| 阶段 | 内容 | 执行方 |
|------|------|--------|
| 1. 变更识别 | git diff 分析 | 编译服务器 |
| 2. 插桩 | 源码自动插桩 | 编译服务器 |
| 3. 手册建模 | AT 手册 PDF 抽取 | 测试电脑 |
| 4. 用例生成 | module_model + coverage_map → generated_tests.yaml | 测试电脑 |
| 5a. 编译 | 增量编译 | 编译服务器 |
| 5b. 固件传输 | scp 两跳: 服务器→Mac→测试机 | 中间机(Mac) |
| 5c. 烧录 | adownload.exe + COM16 | 测试电脑 |
| 6. 测试执行 | AT 命令 + 覆盖率采集 | 测试电脑 |
| 7. 分析迭代 | 未覆盖桩分类 + 下一轮用例 | 测试电脑 |
| 8. 报告生成 | MD + Excel + JSON | 测试电脑 |

## 固件传输流程

```
编译服务器                    Mac (中间跳板)              测试电脑
192.168.242.120              localhost                   172.20.162.21

release.zip ──scp──→ /tmp/fw.zip ──scp──→ D:\通信模组\at_kb_runs\
(先 copy 到 C:\Users\Lenovo\fw.zip 再 scp)
```

**为什么需要两跳**: 编译服务器和测试电脑不在同一子网，Mac 作为跳板中转。

## 环境依赖

### 编译服务器

- ARM 编译器 (tools\win32\ARM_Compiler_5)
- Git
- Python 3 (插桩脚本)
- SSH 服务 (端口 22)

### 测试电脑

- Python 3.11+
- pyserial (串口通信)
- pyyaml (配置/用例解析)
- openpyxl (Excel 报告)
- pymupdf (可选，手册 PDF 抽取)
- SSH 服务 (端口 22)
- COM16 串口 (115200 baud)

## Kanban 协调层

两台机器通过 Kanban 共享任务板协调，每 1 分钟通过 scp 同步：

```
编译服务器 192.168.242.120          测试电脑 172.20.162.21
       │                                    │
       │    scp 同步 coverage-board.db       │
       │←──────────────────────────────────→│
       │                                    │
  Cron: kanban-build-worker            Cron: kanban-test-worker
  领取 instrument/reinstrument 任务    领取 flash-test 任务
  执行: 插桩 + 编译 + scp 固件         执行: 烧录 + 测试 + 分析 + 报告
```

任务流转：
1. 测试PC 创建任务 → "插桩 DNS" → assignee: build-server
2. 编译服务器 领取 → 插桩+编译 → 完成 → scp 固件到测试PC
3. 测试PC 检测完成 → 下载固件 → 烧录 → 测试 → 报告
4. 如果覆盖率不足 → 创建新任务 → "重插桩 DNS" → 回到步骤 2

详见: coverage-pipeline-main/references/kanban-coordination-design.md

## 注意事项

1. **编译禁止 DC ALL** — 会从 ps.7z 恢复源文件，覆盖插桩
2. **固件传输用 scp 两跳** — 直接 scp Windows 路径会失败
3. **烧录后可能需拔插 USB** — adownload 完成后模组可能不自动重启
4. **AT+COVERAGE=1 可能返回 ERROR** — 新固件不支持清零，忽略即可
5. **网络模块测试前检查 PDP** — CEREG→CGACT→CGPADDR 确认网络注册
