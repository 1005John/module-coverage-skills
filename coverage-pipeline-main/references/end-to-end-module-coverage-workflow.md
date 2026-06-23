# 新模块覆盖率测试端到端工作流

## When to Use
- 需要让另一个 Agent/模型独立完成新 AT 模块的覆盖率测试。
- 需要从插桩、编译、烧录、测试生成、执行、分析、缺陷识别、迭代到报告闭环。
- 适用于 ML307R/同类通信模组的 AT 命令模块，例如 HTTP/MQTT/TCP/SSL 等。

## 总原则
1. 禁止修改业务逻辑，只允许插桩、构建配置、测试脚本、模型文件、报告变化。
2. 覆盖率必须来自真实 `AT+COVERAGE?`，不得伪造或用估算替代。
3. 用例必须有预期结果来源，优先来自 AT 手册；覆盖率新增不能抵消行为失败。
4. 每轮必须记录新增覆盖、断言失败、潜在 bug、饱和原因，方便其他 Agent 接续。
5. 编译使用增量 `DC`，禁止 `DC ALL`，否则 `ps.7z` 会恢复源码覆盖插桩。

## 目录与产物约定

| 文件 | 说明 |
|------|------|
| `module_config.<module>.yaml` | 模块源码、桩 ID 范围、编译对象、AT 手册路径 |
| `module_model.<module>.yaml` | 命令模型：语法、参数、状态机、URC、timeout、破坏性等级 |
| `manual_expectations.<module>.json` | 从 AT 手册抽取的响应、URC、错误码、页码/章节来源 |
| `coverage_map.json` | 桩 ID 到源码行/函数/条件/命令提示的映射 |
| `generated_tests.yaml` | 数据驱动用例；正式执行器唯一输入 |
| `run_<module>_coverage_vN.py` | 兼容模式脚本；允许实验，但最终需沉淀回 YAML/模型 |
| `run_result.json` | 原始 AT 响应、URC、耗时、环境状态 |
| `coverage_delta.json` | 每条 case 新增覆盖；无桩级明细时标记 `coarse_delta_only=true` |
| `assertion_result.json` | 预期/实际对比，状态为 pass/fail/xfail/error/env_fail |
| `bug_candidates.json` | 潜在 bug：复现步骤、期望、实际、证据、严重级别 |
| `run_summary.md` | 交接报告，必须可让另一个 Agent 继续 |
| `coverage_report.xlsx` | 可选 Excel 报告 |

## 阶段 0：准备与资料收集

1. 确认测试机、串口、SDK 路径、编译命令、烧录工具。
2. 收集 AT 手册 PDF，并验证可抽取：

```bash
pdftotext -layout <manual.pdf> /tmp/<module>_manual.txt
```

3. 从手册抽取：命令列表、语法、参数范围、Possible Returns、URC、错误码、示例。
4. 已知手册位置：
   - HTTP/HTTPS：`/Volumes/DevDrive/test_report_ref/http_httpsusermanual.pdf`
   - TCP/IP：`/Volumes/DevDrive/test_report_ref/TCP_IP用户手册.pdf`
   - 通用 AT：`/Volumes/DevDrive/test_report_ref/4g_series.pdf`
   - 扩展 AT：`/Volumes/DevDrive/test_report_ref/4gseries扩展.pdf`

## 阶段 1：变更识别与模块边界

输出 `change_analysis.json`：

```json
{
  "module": "http",
  "at_layer": "onemo/at/src/cm_atcmd_http.c",
  "api_layer": "onemo/cm_http/src/cm_http_api.c",
  "client_layer": "onemo/cm_http/src/cm_http_client.c",
  "at_commands": ["MHTTPCFG", "MHTTPCREATE", "MHTTPREQUEST"],
  "manuals": ["http_httpsusermanual.pdf"]
}
```

检查点：
- AT 分发层是否有明确 `cmiotXXX` 处理函数。
- 是否有底层 API 层可沿 TJ 桩插 COV。
- 是否有更深 client/platform 层；若只含 TJ 桩，不会自动计入 `AT+COVERAGE?`。

## 阶段 2：插桩

### 2.1 AT 层插桩
- 对 `cm_atcmd_<module>.c` 插入 `COV_STMT(id)`、`COV_BRANCH_T/F(id)`。
- 每个模块使用独立 bitmap 和计数器，例如 `cm_cov_http_hit()`。
- 在 `cm_atcmd_extern.c` 的 `AT+COVERAGE?` 输出中添加模块统计。

### 2.2 API 层插桩
- 对 `cm_<module>_api.c` 可沿厂商 TJ 点插入 COV。
- `.mak` 必须加：

```makefile
$(BUILD_ROOT)/onemo/coverage/inc
-DCM_COVERAGE_ENABLE
```

- 修改 `.mak` 后删除对应 `pack_c.via` 和 `.o`。

### 2.3 coverage_map.json 必填字段

```json
{
  "id": 203,
  "kind": "branch_true",
  "file": "cm_atcmd_http.c",
  "line": 412,
  "function": "cmiotHTTPCFG",
  "condition": "httpid > HTTP_MAX",
  "nearby_source": "if (httpid > HTTP_MAX) ...",
  "command_hint": "MHTTPCFG",
  "param_hints": ["httpid"],
  "category_hint": "parameter_validation"
}
```

## 阶段 3：编译

在 Windows 测试机：

```cmd
cd /d D:\ML307R\SDK
ML307R.bat DC
```

必须清理：

```cmd
del /q D:\ML307R\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at\cm_atcmd_<module>.*
del /q D:\ML307R\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_<module>\*.*
del /q D:\ML307R\SDK\tavor\Arbel\obj_PMD2NONE\inc\cm_coverage.h
```

验证：
- 编译 0 error。
- `.o` 文件更新时间更新且 >0 字节。
- release zip 生成。
- 若编译太快，检查是否没触发重编。

## 阶段 4：烧录固件

流程：
1. AT 口发送 `AT+MFORCEDL` 或检测 ASR 下载设备。
2. 用 `adownload.exe` 烧录 release zip。
3. 等 AT 口恢复。
4. 验证：

```text
AT                -> OK
AT+MSWVER         -> 版本符合预期
AT+COVERAGE=1     -> OK
AT+COVERAGE?      -> 包含新模块统计，total 正确
```

烧录失败必须停止，不得冒充成功。

## 阶段 5：生成测试用例与脚本

### 5.1 预期结果来源
优先级：
1. 模块 AT 手册：语法、响应、URC、错误码。
2. 通用 AT 手册：OK/ERROR/CME/CMS 规则。
3. 源码推断：标记 `source=source_code_inferred`。
4. 历史稳定结果：标记 `source=observed_baseline`。
5. LLM 推断：只能标记 `source=llm_hypothesis`，不得直接作为 bug 判定依据。

### 5.2 用例生成策略
- 手册全命令：测试命令、读取命令、设置命令、执行命令。
- 参数边界：最小、最大、最小-1、最大+1、非法枚举、空字符串、超长字符串。
- 状态机：未创建→操作、创建→配置→请求→读取→删除、删除后操作。
- 异步 URC：等待完整 URC，不用固定 sleep 代替。
- 错误路径：DNS 失败、连接超时、缓存不足、SSL 错误、非法状态。
- 数据模式：`>` 提示、Ctrl+Z 结束、ESC 取消、长度精确匹配。

### 5.3 generated_tests.yaml 关键字段

```yaml
cases:
  - id: http_request_datamode_post
    goal: trigger_request_datamode_cb
    target_stubs: []
    category: datamode
    expected_result:
      status_in: [OK, OTHER]
      prompt: true
      urc_contains: ['+MHTTPURC']
      source: /Volumes/DevDrive/test_report_ref/http_httpsusermanual.pdf
    steps:
      - cmd: 'AT+MHTTPREQUEST=0,2,12'
        send_after_prompt: 'abc=123&x=9'
        end: ctrl_z
        timeout_sec: 20
        coverage_after: true
```

## 阶段 6：测试执行

执行器要求：
- 打开串口后立即写启动日志。
- 每条 case 保存原始 AT 响应，不能只保存 OK/ERROR。
- 异步命令用 `wait_urc`，等待 `+MHTTPURC` / 模块 URC。
- 每阶段后查询 `AT+COVERAGE?`。
- 同时输出覆盖率和断言结果。

Windows 远程运行建议：
- 避免复杂 `cmd /c cd /d ... & ...`，SSH 下容易工作目录错乱。
- 优先上传 `.ps1` 文件，用 `Set-Location` 固定目录后执行。
- 对长流程用 `python -u`，日志实时 flush。

示例：

```powershell
Set-Location D:\ML307R\SDK
python -u .\run_http_coverage_vN.py *> http_vN.log
```

## 阶段 7：覆盖率分析

每轮必须记录：

| 字段 | 说明 |
|------|------|
| 起始覆盖率 | 本轮开始 `AT+COVERAGE?` |
| 结束覆盖率 | 本轮结束 `AT+COVERAGE?` |
| 新增桩 | final_hit - start_hit |
| 阶段增量 | 每个 phase 后的 hit 差值 |
| 零增量阶段 | 说明饱和或用例无效 |
| HTTPAPI/API 层变化 | 判断是否触发底层路径 |

HTTP 实战 v5-v7：

| 轮次 | 覆盖率 | 命中桩 | 新增 | 说明 |
|------|--------|--------|------|------|
| v5 | 53%,50% | 234/810 | +3 | 手册驱动 13 阶段，含 HTTP API 桩 |
| v6_short | 60%,54% | 260/810 | +26 | WTCP、datamode、chunked、DLFILE matrix |
| v7_short | 63%,57% | 271/810 | +11 | 精确 datamode、request datamode、状态边界 |

经验：
- datamode 是 HTTP 后期最大增量来源。
- cached read 边界在 v7 已零增量，后续价值低。
- alt server 路径对 HTTP 总桩无新增，除非服务器行为能触发新错误码。

## 阶段 8：缺陷识别

断言状态：
- `pass`：实际符合预期。
- `fail`：环境正常但实际不符合预期，写入 `bug_candidates.json`。
- `xfail`：已知限制或条件饱和。
- `error`：用例定义错误。
- `env_fail`：串口、网络、SIM、烧录等环境问题。

`bug_candidates.json` 必须包含：

```json
{
  "case_id": "C006",
  "severity": "medium",
  "status": "needs_manual_confirm",
  "steps": ["AT+MHTTPCFG=\"timeout\",0,0,0,0"],
  "expected": {"status": "OK", "source": "http_httpsusermanual.pdf"},
  "actual": {"status": "ERROR", "resp": "+CME ERROR: 50"},
  "evidence": {"log": "http_v6.log", "manual_section": "MHTTPCFG timeout"}
}
```

HTTP 实战发现：
- `timeout=0,0,0` 与手册预期可能不一致。
- `MHTTPHEADER/MHTTPCONTENT` 数据模式 `eof=1/eof=2` 存在行为异常或断言需复核。
- 缺陷必须可复现，不能仅凭覆盖率结果定性。

## 阶段 9：用例与脚本自迭代

迭代规则：
1. 选择新增最多的阶段继续细化。
2. 零增量阶段降权或停止。
3. 断言失败分两类：固件候选 bug、用例/预期错误。
4. 每轮保留脚本和 JSON，不覆盖旧结果。
5. 当连续 2 轮新增为 0 或剩余路径需新插桩/新硬件时判定饱和。

HTTP 实战迭代路径：
- v1-v2：基础命令与计数器修复。
- v3-v4：HTTPCFG 深度参数、多段 header/content、DLFILE。
- v5：手册驱动，加入 API 层桩。
- v6_short：datamode/WTCP/chunked/DLFILE，新增 +26。
- v7_short：精确长度 datamode/request datamode，新增 +11。

## 阶段 10：报告生成

报告必须包含：
1. 项目背景与环境。
2. 插桩方案：文件、ID 范围、计数器架构。
3. 编译/烧录步骤与验证结果。
4. 每轮覆盖率表：覆盖率、命中桩、新增桩、命令数、潜在 bug 数。
5. 阶段增量表。
6. 未覆盖区域和原因分类。
7. 潜在 bug 列表：复现、期望、实际、证据。
8. 已知 pitfalls。
9. 下一步建议：继续 AT 层、扩展底层插桩、TJ 采集、接受饱和。
10. 文件清单和可继续执行命令。

## 新模块验收清单

- [ ] AT 手册已抽取，`manual_expectations.<module>.json` 可追溯。
- [ ] 插桩文件编译通过，未修改业务逻辑。
- [ ] `AT+COVERAGE?` 显示模块 total 正确，计数器不超过 100%。
- [ ] 固件已真实烧录，AT 口验证 OK。
- [ ] 测试用例包含 expected_result 和 expectation_source。
- [ ] 每轮结果包含覆盖率、断言、bug_candidates。
- [ ] 至少两轮迭代后给出饱和/继续依据。
- [ ] 报告能让另一个 Agent 独立继续。
