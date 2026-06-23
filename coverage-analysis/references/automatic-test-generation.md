# 完全自动测试用例生成与迭代设计

## When to Use
- 需要从“手写多轮脚本”升级为“自动生成、执行、分析、再生成”的闭环。
- 目标模块有 AT 命令入口，且已经完成覆盖率插桩。
- 希望另一个 Agent 可按数据文件继续迭代，而不是依赖人工记忆。

## 核心原则
1. 用例生成必须数据化：执行器消费 `generated_tests.yaml`，不要每轮手写 `run_xxx_vN.py`。
2. 自动测试有两个同等目标：覆盖率提升和行为正确性验证；覆盖率命中不代表测试通过。
3. 迭代必须桩级归因：不仅记录新增 hit 数，还要记录“哪些桩由哪条用例命中”。
4. 每条用例必须声明预期结果；实际结果不符合预期时输出潜在 bug，而不是只当作 FAIL 统计。
5. LLM 只做候选解释和补充，不直接决定最终执行；最终执行必须由规则、约束和真实覆盖率反馈驱动。
6. 禁止修改业务代码；只允许插桩文件、测试用例、执行脚本、分析报告变化。
7. 覆盖率数据必须来自真实 `AT+COVERAGE?` 或 bitmap 导出，不得合成。
8. 先做可运行 MVP，再扩展为跨模块系统；不要一开始就重写整条覆盖率流水线。

## MVP 落地顺序
1. 选一个模块先跑通闭环，优先 HTTP：当前已有首轮结果，且状态机比 MQTT 更清晰。
2. 补齐 `coverage_map.json` 的桩级语义字段，至少包含文件、行号、函数、条件、附近源码。
3. 手工整理第一版 `module_model.http.yaml`，先覆盖 create/config/request/read/delete 和错误路径。
4. 把已有 Python 内置用例迁移成 `generated_tests.yaml`，保持执行结果等价。
5. 实现通用 YAML 执行器 `run_generated_tests.py`，先支持 setup/steps/teardown、URC 等待、timeout、coverage_after。
6. 实现 `coverage_delta.json`：有桩级明细则记录 stub_id；没有明细时必须标记 `coarse_delta_only=true`。
7. 最后再实现 `generate_testcases.py` 和收益调度器，逐步替代手写 vN 脚本。

## 预期结果来源

预期结果必须来自可追溯来源，优先级如下：

1. 模块 AT 手册：命令语法、Possible Returns、URC、错误码，是 `expected_result` 的首选依据。HTTP/HTTPS 模块使用 `/Volumes/DevDrive/test_report_ref/http_httpsusermanual.pdf`。
2. 通用 AT 响应规范：例如 `/Volumes/DevDrive/test_report_ref/4g_series.pdf` 中的 `AT Command Response`、`+CME ERROR`、`+CMS ERROR` 章节，可作为基础 OK/ERROR/CME 规则来源。
3. 扩展 AT 手册：例如 `/Volumes/DevDrive/test_report_ref/4gseries扩展.pdf`，可作为 `AT+M...` 扩展命令的语法、响应、参数范围、URC 预期来源。
4. 模块源码：当手册缺失或实现扩展命令时，用源码状态机和错误路径补充预期，但必须标记 `source=source_code_inferred`。
5. 历史稳定结果：只可作为回归基线，不能替代手册；必须标记 `source=observed_baseline`。
6. LLM 推断：只作为候选，必须标记 `source=llm_hypothesis`，不能直接作为缺陷判定依据。

注意：`4g_series.pdf`、`4gseries扩展.pdf`、`http_httpsusermanual.pdf` 均已验证可用 `pdftotext` 抽取文本。`http_httpsusermanual.pdf` 明确包含 `AT+MHTTPCFG/MHTTPCREATE/MHTTPHEADER/MHTTPCONTENT/MHTTPREQUEST/MHTTPREAD/MHTTPDEL/MHTTPTERM/MHTTPDLFILE` 和 `+MHTTPURC`，可直接作为 HTTP 用例 `expected_result` 和 `manual_expectations.http.json` 的首选来源。当前仍缺 MQTT 专用手册，MQTT 的命令级预期需要对应手册或源码补充。

## 必需数据文件

| 文件 | 作用 |
|------|------|
| `manual_expectations.json` | 从 AT 手册抽取的命令语法、Possible Returns、URC、错误码、章节页码 |
| `module_model.yaml` | 模块命令模型：命令、参数、范围、状态机、URC、破坏性等级、默认预期 |
| `coverage_map.json` | 桩级映射：stub_id → 文件、行号、函数、分支条件、附近源码、推断目标 |
| `testcase_pool.json` | 候选用例池：规则生成、源码导向生成、历史高收益模板 |
| `generated_tests.yaml` | 下一轮实际执行用例，执行器唯一输入，必须包含预期结果 |
| `run_result.json` | 每条命令真实响应、状态、耗时、URC、错误码、断言结果 |
| `coverage_delta.json` | 用例与新增桩映射：case_id → new_stub_ids，stub_id → first_hit_case |
| `assertion_result.json` | 用例预期与实际结果对比，区分 pass/fail/error/env_fail |
| `bug_candidates.json` | 潜在 bug 列表：复现步骤、期望、实际、证据、严重级别、是否需人工确认 |
| `uncovered_analysis.json` | 未覆盖桩分类：参数、状态、网络、URC、平台、不可达 |
| `iteration_decision.json` | 下一轮选择依据：目标桩、候选用例、预期收益、风险、成本、行为验证目标 |

## module_model.yaml 最小结构

```yaml
module: http
commands:
  - name: MHTTPCREATE
    format: 'AT+MHTTPCREATE={id}'
    params:
      - name: id
        type: int
        valid: [0, 3]
        invalid: [-1, 4]
    pre_state: []
    post_state: [created]
    async: false
    expected:
      success:
        status: OK
        response_contains: ['OK']
        state_after: created
      invalid_id:
        status: ERROR
        response_contains_any: ['ERROR', '+CME ERROR']
        state_unchanged: true
    destructive: low

  - name: MHTTPREQUEST
    format: 'AT+MHTTPREQUEST={id},{method},{url}'
    params:
      - name: id
        type: int
        valid: [0, 3]
        invalid: [-1, 4]
      - name: method
        type: enum
        values: [GET, POST, PUT, DELETE]
      - name: url
        type: url
        valid_values: ['http://example.com/']
        invalid_values: ['http://invalid.invalid/']
    pre_state: [created, configured]
    post_state: [requested]
    async: true
    urc: '+MHTTPURC'
    timeout_sec: 15
    expected:
      success:
        immediate_status: OK
        urc_contains: ['+MHTTPURC']
        final_status_in: [success, http_status_received]
      invalid_url:
        immediate_status_in: [OK, ERROR]
        final_status_in: [dns_fail, timeout, connect_fail]
        bug_if: ['crash', 'no_response_after_timeout', 'unexpected_success']
    destructive: medium
```

## coverage_map.json 最小结构

```json
{
  "module": "http",
  "stubs": [
    {
      "id": 203,
      "kind": "stmt",
      "file": "cm_atcmd_http.c",
      "line": 412,
      "function": "cm_http_create",
      "condition": null,
      "nearby_source": "if (http_id >= HTTP_MAX_NUM) ...",
      "command_hint": "MHTTPCREATE",
      "param_hints": ["http_id"],
      "category_hint": "parameter_validation"
    }
  ]
}
```

## generated_tests.yaml 最小结构

```yaml
run_id: http_auto_v2
reset_coverage: true
cases:
  - id: http_create_id_max_plus_1
    goal: hit_http_id_upper_bound_error
    target_stubs: [203, 204]
    category: parameter_validation
    cost: low
    risk: low
    expected_result:
      status: ERROR
      response_contains_any: ['ERROR', '+CME ERROR']
      must_not_reset_module: true
      state_unchanged: true
      bug_severity_if_mismatch: medium
    steps:
      - cmd: 'AT+MHTTPCREATE=4'
        expect: ['ERROR', '+CME ERROR']
        timeout_sec: 3
        coverage_after: true

  - id: http_get_success_flow_id_1
    goal: enter_request_success_and_urc_path
    target_stubs: [260, 261, 2005]
    category: stateful_success_flow
    cost: medium
    risk: medium
    expected_result:
      immediate_status: OK
      urc_contains: ['+MHTTPURC']
      response_not_contains: ['+CME ERROR']
      final_state: requested
      bug_severity_if_mismatch: high
    setup:
      - cmd: 'AT+MHTTPCREATE=1'
      - cmd: 'AT+MHTTPCFG="timeout",1,15'
    steps:
      - cmd: 'AT+MHTTPREQUEST=1,GET,"http://example.com/"'
        wait_urc: '+MHTTPURC'
        timeout_sec: 15
        coverage_after: true
    teardown:
      - cmd: 'AT+MHTTPDEL=1'
```

## 自动生成器分层

### 1. 规则生成器
- 从 `module_model.yaml` 生成基础用例：查询、创建、配置、执行、读取、删除。
- 为每个参数生成边界值：最小、最大、最小-1、最大+1、空值、超长字符串、非法枚举。
- 为每条命令生成缺参、多参、类型错误、未初始化状态、重复释放等错误路径。

### 2. 状态机生成器
- 根据 `pre_state/post_state` 自动组合成功流。
- 每个阶段独立：setup → action → coverage query → teardown。
- 对破坏性命令做隔离，DNS 失败、网络断开、重置类用例放到批次末尾。

### 3. 源码导向生成器
- 读取 `coverage_map.json` 中未覆盖桩附近源码。
- 根据条件表达式推断目标输入，例如：
  - `id >= MAX` → 生成 `id=MAX`、`id=MAX+1`
  - `strlen(x) == 0` → 生成空字符串
  - `state != CONNECTED` → 生成未连接操作
  - `platform == ALIYUN` → 生成 `platsel=2 + devinfo + connect`
- 推断失败时生成 `needs_llm_review`，交给 LLM 输出候选，但仍需执行器验证。

### 4. 收益调度器
- 为候选用例计算分数：`score = target_stub_weight + historical_gain - cost - risk - redundancy`。
- 优先执行低成本、高命中潜力、覆盖未触达函数的用例。
- 同类参数全排列只抽样，除非该区域历史新增覆盖高。

### 5. 行为判定器
- 每个 case 执行后同时做覆盖率判定和行为判定。
- 行为判定输入为 `expected_result`、原始响应、URC、错误码、模块状态、是否重启/无响应。
- 断言结果分为：
  - `pass`：实际结果符合预期。
  - `fail`：实际结果不符合预期，且环境正常；生成潜在 bug。
  - `xfail`：已知限制或条件饱和导致的不符合预期，不计新 bug。
  - `error`：用例定义错误，例如预期字段缺失或 schema 不合法。
  - `env_fail`：串口、网络、SIM、烧录、模块无响应等环境失败。
- 任何 `fail` 必须写入 `bug_candidates.json`，包含复现步骤、期望、实际、证据和建议严重级别。

### 6. 饱和判断器
- 连续 2 轮 `new_stub_ids` 为空 → 候选饱和。
- 剩余桩均为 `unreachable/platform_specific/hardware_required` → 条件饱和。
- 同一未覆盖桩尝试超过 3 种策略仍无新增 → 标记 `needs_manual_review`。

## 执行器要求

1. 执行器只读取 `generated_tests.yaml`，不内置模块业务逻辑。
2. 每个 case 必须有 `expected_result`；缺失时标记 `error`，不得当作通过。
3. 每条步骤执行前后可选查询覆盖率，至少每个 case 后必须查询。
4. 异步命令必须支持 `wait_urc` 和独立 timeout。
5. 结果必须保存原始 AT 响应，不只保存 OK/ERROR。
6. 执行器必须同时输出覆盖率结果和断言结果：覆盖率新增但断言失败时，结论仍是潜在 bug。
7. 若 AT 口无响应、串口占用、模块重启，必须中止本轮并标记环境失败，不得把环境失败算作用例失败。

## 潜在 bug 输出

`bug_candidates.json` 最小结构：

```json
{
  "bugs": [
    {
      "case_id": "http_get_success_flow_id_1",
      "severity": "high",
      "status": "needs_manual_confirm",
      "reason": "expected URC +MHTTPURC but timed out while AT port stayed responsive",
      "steps": ["AT+MHTTPCREATE=1", "AT+MHTTPCFG=...", "AT+MHTTPREQUEST=..."],
      "expected": {"immediate_status": "OK", "urc_contains": ["+MHTTPURC"]},
      "actual": {"immediate_status": "OK", "urc": "", "timeout_sec": 15},
      "evidence": {"run_id": "http_auto_v2", "log": "at_execution_log.txt"}
    }
  ]
}
```

判定规则：
- 预期 OK 但返回 ERROR：潜在功能 bug 或前置状态建模错误，先记录 bug，同时标记 `needs_model_review`。
- 预期 ERROR 但返回 OK：高价值潜在 bug，尤其是参数校验、越界、非法状态场景。
- 预期 URC 但超时：若 AT 口仍响应，记录潜在异步/网络处理 bug；若 AT 口不响应，记录环境失败或稳定性 bug。
- 模块重启、串口断开、无响应：优先记录稳定性 bug，并附带最后一条命令。

## 覆盖率增量归因

理想情况下 `AT+COVERAGE?` 应支持 bitmap 或明细导出。若当前固件只能返回 hit/total，则自动化能力会受限：

- 可做：按 case 记录新增 hit 数，做粗粒度收益学习。
- 不足：无法准确知道哪个未覆盖桩被命中，也无法精确反推下一轮目标。
- 建议：新增 `AT+COVERAGEDETAIL?` 或让 `AT+COVERAGE?` 支持分页返回 bitmap/命中 ID 列表。

## 迭代流程

```text
1. 读取 module_model.yaml + coverage_map.json
2. 读取上一轮 run_result.json + coverage_delta.json
3. 生成 uncovered_analysis.json
4. 从规则、状态机、源码导向三类生成 testcase_pool.json
5. 用收益调度器选出 generated_tests.yaml
6. 执行 generated_tests.yaml，产生 run_result.json
7. 计算 coverage_delta.json
8. 达标或饱和则报告，否则回到第 3 步
```

## 验证清单

- [ ] `generated_tests.yaml` 可被执行器直接消费，无需手写新 Python 脚本。
- [ ] 每个 case 有 `goal/category/target_stubs/cost/risk`。
- [ ] 每轮输出 `coverage_delta.json`，能说明新增覆盖来自哪些 case。
- [ ] 未覆盖桩有分类和下一步动作：生成用例、条件饱和、不可达、人工复核。
- [ ] 自动调度有依据，不能只说“LLM 建议”。
- [ ] 环境失败和用例失败分开统计。
