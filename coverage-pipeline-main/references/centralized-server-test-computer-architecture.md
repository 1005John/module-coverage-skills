# 中心服务器 + 测试电脑分层架构

## When to Use

当多个测试工程师分别负责同一型号模组的不同功能模块（MQTT/HTTP/TCP/FTP/SSL 等），且希望工程师电脑尽量轻量时，采用本架构。

核心目标：

- 插桩、桩 ID 分配、coverage_map 和编译集中在中心服务器。
- 各工程师电脑只负责本地模组上的 AT 执行、覆盖率迭代、行为断言、经验总结和报告生成。
- 各工程师环境完全独立，避免 profile、memory、cron、串口配置互相污染。
- 通用能力集中维护，模块经验分层共享，本地经验成熟后再公共化。

## 推荐架构

```text
源码仓库 Repo A
    │
    ▼
中心服务器 Agent
    ├─ 仓库监控 / webhook / cron 轮询
    ├─ git diff 变更识别
    ├─ Level 2 函数级增量插桩
    ├─ coverage_map / stub_id_alloc 维护
    ├─ 固件编译
    └─ artifact 发布
          │
          ▼
产物仓库 / 文件服务器
    ├─ manifest.json
    ├─ firmware/
    ├─ coverage/
    ├─ diff/
    ├─ instrumentation/
    └─ build/
          │
          ▼
测试电脑 Agent
    ├─ 拉取 artifact
    ├─ 烧录或提示人工烧录
    ├─ AT 口验证
    ├─ 执行 generated_tests.yaml
    ├─ 采集覆盖率和行为断言
    ├─ 生成 coverage_delta / bug_candidates
    ├─ 迭代生成下一轮用例
    ├─ 输出 MD/XLSX/JSON 报告
    └─ 沉淀 local skill
```

## 中心服务器 Agent 职责

中心服务器做重活和统一产物：

1. 只读监控源码仓库提交和分支变化。
2. 对 new commit 执行 `git diff old..new`，输出 `change_analysis.json` 和 `affected_functions.json`。
3. 按 trivial / boundary / structural / new_func / delete_func 分类变更。
4. 只对受影响函数做增量插桩，未变函数保留旧桩。
5. 统一维护 `coverage_map.<module>.json`、`stub_id_alloc.yaml` 和 `cm_atcmd_extern.c` 覆盖率汇总。
6. 使用统一构建环境编译，发布固件和元数据。
7. 输出 artifact，供测试电脑拉取。

中心服务器应加载：

```text
coverage-pipeline-main
coverage-instrumentation
coverage-build-flash
coverage-analysis
coverage-report（仅用于构建/发布报告）
```

## 测试电脑 Agent 职责

测试电脑保持轻量，只做本地测试闭环：

1. 拉取中心服务器发布的 artifact。
2. 校验 `manifest.json`，确保 firmware、coverage_map 和 source_commit 匹配。
3. 在本地模组/串口/SIM/网络环境中烧录和执行 AT 测试。
4. 按 `expected_result` 做行为断言，保存原始响应。
5. 生成 `run_result.json`、`assertion_result.json`、`coverage_delta.json`、`bug_candidates.json`。
6. 根据覆盖率和断言结果迭代生成下一轮 `generated_tests.yaml`。
7. 生成 `run_summary.md` 和 `coverage_report.xlsx`。
8. 把模块稳定经验沉淀到 local skill，成熟后 PR 到公共 module base skill。

测试电脑应加载：

```text
coverage-test-execution
coverage-analysis
coverage-report
at-manual-knowledge-base
<module>-coverage-base
<module>-local-lessons
```

## Skill 分层

```text
公共 core skill（中心维护）
  coverage-pipeline-main
  coverage-instrumentation
  coverage-build-flash
  coverage-test-execution
  coverage-analysis
  coverage-report

模块 base skill（团队共享）
  mqtt-coverage-base
  http-coverage-base
  tcp-coverage-base
  ftp-coverage-base

工程师 local skill（本机私有）
  mqtt-local-lessons
  http-local-lessons
  tcp-local-lessons
```

原则：

- core skill 写通用流程和硬约束。
- module base skill 写模块共性经验。
- local skill 写本地环境、临时策略、未公共化经验。
- 测试结果和单次 run 日志不要写入 skill；只把可复用方法、pitfall、验证清单写入 skill。

## Artifact 规范

中心服务器发布的 artifact 至少包含：

```text
artifact/<repo>/<branch>/<source_commit>_<timestamp>/
  manifest.json
  firmware/
    release.zip
    firmware.axf
  coverage/
    coverage_map.<module>.json
    stub_id_alloc.yaml
  diff/
    change_analysis.json
    affected_functions.json
  instrumentation/
    instrumentation_patch.patch
    affected_stub_ids.json
  build/
    build_log.txt
    build_result.json
```

`manifest.json` 必须绑定：

- repo_url
- branch
- source_commit
- source_parent_commit
- build_time
- modules
- firmware 文件路径
- coverage_map 文件路径
- change_analysis 文件路径
- artifact_id

测试电脑必须阻断 firmware 与 coverage_map 不匹配的 artifact。

## Hermes Profile 建议

每个工程师使用自己的 profile，不共用中心 profile：

```bash
hermes profile create coverage-mqtt
hermes profile create coverage-http
hermes profile create coverage-tcp
```

每个 profile 独立维护：

- cron
- memory
- skills
- 本地 workspace
- 串口和网络配置
- 飞书/消息推送

cron 创建的是独立 session，不会自动创建 profile。需要 profile 隔离时必须显式创建并在该 profile 下配置 cron。

## Pitfalls

1. 不要让所有工程师共用一个 Hermes profile：memory、cron、env 和 local skill 会互相污染。
2. 不要在测试电脑上修改中心服务器发布的 `coverage_map`；如发现错误，应回报中心服务器重新发布 artifact。
3. 不要把单次测试日志写入 skill；skill 只保存可复用流程和经验。
4. 不要让中心服务器加载工程师 local skill；否则局部经验可能污染公共插桩/编译策略。
5. 不要把 firmware 和 coverage_map 混用；二者必须来自同一个 manifest/artifact。
6. 不要把网络/串口/设备问题算成产品 bug；应标记为 `env_fail` 或 `crash` 并保留证据。

## 验证清单

- [ ] 中心服务器能只读检测源码仓库提交。
- [ ] 中心服务器能生成 change_analysis 和 coverage_map。
- [ ] 中心服务器能发布包含 manifest 的 artifact。
- [ ] 测试电脑能拉取并校验 artifact。
- [ ] 测试电脑能执行 AT 测试并保存原始响应。
- [ ] 测试电脑能生成 coverage_delta 和 bug_candidates。
- [ ] 报告包含 source_commit、artifact_id、覆盖率、断言失败和未覆盖原因。
- [ ] local skill 与公共 module base skill 的边界清晰。
