# 覆盖率流水线脚本清单

> **待改进**：以下 IP、端口、凭据、工具路径为硬编码值。
> 正式环境应从 env.yaml 读取，不要硬编码。

## 文档包位置
`/Users/john/module-coverage-autotest-docs/`

## 核心文档
- `REQUIREMENTS.md` — 需求和验收标准
- `DESIGN.md` — 架构和阶段设计
- `CHANGELOG.md` — 变更记录
- `env.yaml` — 环境配置模板
- `module_config.mqtt_at.yaml` — MQTT 模块配置模板
- `module_model.<module>.yaml` — 自动用例生成所需的命令、参数、状态机、URC 模型
- `manual_expectations.<module>.json` — 从 AT 手册抽取的响应/URC/错误码预期
- `coverage_map.json` — 桩级映射，连接插桩 ID 与源码语义
- `coverage-pipeline-main/references/end-to-end-module-coverage-workflow.md` — 新模块端到端实战流程

## 工具脚本

### 环境验证
- `scripts/validate_env.py` — 离线验证 env.yaml 字段和烧录命令模板

### 烧录
- `scripts/flash_ml307r_once.py` — 单次自动烧录和 AT 验证

### 自动测试生成（目标新架构）
- `scripts/generate_testcases.py` — 读取 `module_model.yaml`、`coverage_map.json`、历史 `coverage_delta.json`，生成 `testcase_pool.json` 与 `generated_tests.yaml`
- `scripts/run_generated_tests.py` — 通用 YAML 执行器，消费 `generated_tests.yaml`，输出 `run_result.json`、`assertion_result.json`、`bug_candidates.json`、`coverage_delta.json`
- `scripts/analyze_coverage_delta.py` — 分析未覆盖桩和用例收益，输出 `uncovered_analysis.json`、`iteration_decision.json`
- 当前状态：设计已固化，脚本待实现；旧版 vN 脚本仅作为兼容参考

### MQTT 覆盖率测试
- `scripts/run_mqtt_at_coverage_v1.py` — 基础用例集
- ... (v2-v12 略)

### HTTP 覆盖率测试
- `scripts/run_http_coverage_v1.py` — HTTP 全命令基础测试（107 条用例，首次 35% 覆盖率）
- `scripts/instrument_http_v2.py` — HTTP AT 层自动插桩脚本（238 stmt + 212 branch = 450 桩）
- `scripts/fix_counter_all.py` — 修复 HTTP 覆盖率计数器（添加 cm_cov_is_hit + 独立 bitmap）

### TCP 覆盖率测试 (2026-06-22 新增)
- `scripts/instrument_tcp_v3.py` — TCP AT 层自动插桩脚本（300 stmt + 162 branch = 462 桩）
  - 含三大陷阱检测：多行函数调用、多行字符串拼接、单行 if
- `scripts/run_tcp_coverage_v1.py` — TCP 测试执行器（读取 generated_tests.yaml，输出 JSON 结果）
- `scripts/run_tcp_v5c.py` — 第二轮迭代（连接+数据+模式切换，不关闭连接避免 crash）
- 经验总结：`coverage-pipeline-main/references/tcp-coverage-session-notes.md`
- Echo server：8.137.154.246:9500(TCP)/9501(UDP)，部署见 `coverage-test-execution/references/tcp-echo-server-deployment.md`

### 报告生成
- `scripts/generate_excel_report.py` — 从 coverage_detail.json 生成 Excel

## 测试结果
- `runs/20260621_*/` — 各轮次 MQTT 测试结果
- `D:\ML307R\SDK\tcp_coverage_results\20260622_170603\` — TCP 第一轮结果

## ML307R SDK 参考
- Windows 测试机：172.20.162.21 (SSH 端口 22，账号 52467)
- AT 串口：COM16, 115200
- SDK 路径：D:\ML307R\SDK
- 编译命令：`cmd /c ML307R.bat DC`（增量）
- 烧录工具：`D:\software\aboot-tools-2023.04.03\...\adownload.exe`
- MQTT Broker：8.137.154.246:1883
