# 行为断言与潜在 Bug 输出

## When to Use
- 自动覆盖率测试已经能执行用例，但需要判断每条用例的实际行为是否符合预期。
- 测试结果不能只看覆盖率，需要把预期不符项作为潜在 bug 输出。

## 核心规则
1. 覆盖率命中只说明代码路径被执行，不代表行为正确。
2. 每条自动生成用例必须包含 `expected_result`，描述期望 OK/ERROR、URC、响应关键字、状态变化、是否允许重启等。
3. 执行器必须同时输出覆盖率结果和行为断言结果。
4. 覆盖率新增但断言失败时，结论仍是潜在 bug，不能算测试通过。
5. 环境失败必须和用例失败分开：串口占用、无网络、烧录失败、模块无响应等标为 `env_fail`。

## 推荐输出文件

| 文件 | 说明 |
|------|------|
| `assertion_result.json` | 每条 case 的预期/实际对比，状态为 pass/fail/xfail/error/env_fail |
| `bug_candidates.json` | 断言失败形成的潜在 bug，包含复现步骤、期望、实际、证据、严重级别 |

## 判定状态
- `pass`：实际结果符合 `expected_result`。
- `fail`：环境正常，但实际结果不符合预期；必须进入 `bug_candidates.json`。
- `xfail`：已知限制或条件饱和导致的不符合预期，不计新 bug，但需说明原因。
- `error`：用例定义错误，例如缺失 `expected_result` 或 schema 不合法。
- `env_fail`：环境不可用，例如串口、网络、SIM、烧录、模块无响应。

## bug_candidates.json 最小字段

```json
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
```

## Pitfalls
- 不要把 OK/ERROR 统计等同于通过/失败；有些 ERROR 是预期错误路径，有些 OK 反而是参数校验 bug。
- 不要让覆盖率新增掩盖行为失败；覆盖率和断言是两个独立维度。
- 不要把环境失败写成产品 bug；先确认 AT 口、网络、SIM、烧录状态。
- 异步命令必须检查 URC 和 timeout，不能只看立即返回 OK。
