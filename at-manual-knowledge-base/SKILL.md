---
name: at-manual-knowledge-base
description: "从蜂窝通信模组 AT/用户/开发指导手册抽取指令、响应、URC、状态机和流程，生成可用于测试用例、覆盖率挖掘和手册变更 diff 的结构化知识库模型"
triggers:
  - "AT 手册知识库"
  - "从手册生成测试用例"
  - "AT 指令抽取"
  - "module_model"
  - "manual_expectations"
  - "MQTT/HTTP/FTP/TCP 手册建模"
  - "generate_tests"
  - "从模型生成用例"
  - "executor"
  - "AT 测试执行"
  - "覆盖率迭代"
---

# AT 手册知识库建模技能

## When to Use

- 用户提供蜂窝通信模组的软件 AT 手册、扩展手册、用户手册、开发指导手册，需要抽取指令、响应、URC、流程和状态依赖。
- 用户要为 MQTT、HTTP/HTTPS、FTP、TCP/IP、SSL、GNSS、SMS 等功能生成 `module_model.<module>.yaml` 或 `manual_expectations.<module>.json`。
- 用户要基于手册变更、代码变更或覆盖率未命中分支生成新的 AT 测试用例。
- 用户强调测试用例必须依据 AT 手册校验预期响应，而不是只追求覆盖率。

## 核心原则

1. 不要只做全文向量库；向量检索只能辅助语义查找，不能作为测试生成的唯一依据。
2. 主要产物必须是结构化 AT 规范模型：命令、参数、响应、URC、状态机、流程、前置条件、清理步骤、来源追溯。
3. 协议类命令必须显式建模状态依赖，例如 `AT+MQTTPUB` 必须先满足 `MQTT_CONNECTED`。
4. 每个测试用例必须带 `basis/source_refs`，能追溯到手册文件、页码、章节或原文片段。
5. 行为断言失败必须输出潜在 bug，不能因为覆盖率提升就算通过。

## 输入资料

常见输入路径示例：

```text
/Volumes/DevDrive/test_report_ref/
  4g_series.pdf
  4gseries扩展.pdf
  MQTT用户手册.pdf
  MQTT开发指导手册_V1.1.4.pdf
  HTTP_HTTPS用户手册_V6.1.3.pdf
  FTP用户手册_V3.1.2.pdf
  TCP_IP用户手册.pdf
```

处理前先确认目标目录实际文件名，不能假设固定版本号。

## 推荐输出结构

```text
at_knowledge_base/
  documents/
    raw/
    extracted/
  modules/
    mqtt.yaml
    http.yaml
    ftp.yaml
    tcpip.yaml
  flows/
    mqtt_non_ssl_publish.yaml
    mqtt_cached_read.yaml
    mqtt_ssl_publish.yaml
  generated/
    manual_expectations.mqtt.json
    generated_tests.mqtt.yaml
  reports/
    manual_diff_report.md
    extraction_quality_report.md
  kb.sqlite
  vector_index/
```

如果用户只要求案例或规划，可先输出到当前手册目录下，例如：

```text
/Volumes/DevDrive/test_report_ref/at_knowledge_base_plan.md
/Volumes/DevDrive/test_report_ref/mqtt_module_model.example.yaml
```

## 标准工作流

### 1. 发现手册文件

使用文件搜索列出目录中的 PDF、DOCX、HTML、JSON、XLSX：

```bash
find <manual_dir> -maxdepth 2 -type f
```

优先识别：

- 基础 AT 手册：网络注册、PDP、SIM、错误码、`AT+CMEE`。
- 扩展 AT 手册：平台扩展命令、低功耗、拨号、PDP 辅助命令。
- 协议用户手册：MQTT、HTTP/HTTPS、FTP、TCP/IP 等命令定义。
- 开发指导手册：完整业务流程、注意事项、平台差异。
- 既有测试报告：历史用例、失败现象、环境配置。

### 2. 抽取文本和命令清单

优先使用 PyMuPDF 抽取 PDF：

```bash
python3 - <<'PY'
import fitz, re, json, os
path = '<manual.pdf>'
doc = fitz.open(path)
cmd_re = re.compile(r'AT\\+[-A-Z0-9_]+|AT\\^[-A-Z0-9_]+|AT&[A-Z0-9]+|AT\\\\[A-Z0-9]+')
cmds = {}
for i, page in enumerate(doc):
    text = page.get_text('text') or ''
    for m in cmd_re.finditer(text):
        cmds.setdefault(m.group(0).rstrip('.,;:'), i + 1)
print(json.dumps({'file': os.path.basename(path), 'pages': len(doc), 'commands': sorted(cmds.items(), key=lambda x: (x[1], x[0]))}, ensure_ascii=False, indent=2))
PY
```

如果 PDF 抽取乱码或为空：

- 尝试 `pdftotext`。
- 尝试 OCR。
- 如果是 CID 编码损坏，标记为手册质量问题，要求重新获取可抽取版本，不要编造内容。

### 3. 按目录页和章节页抽命令段落

先从目录获得章节页码，再按页码抽取命令定义页。每条命令至少抽取：

- 命令名称和功能描述。
- 测试/查询/设置/执行命令语法。
- 参数名称、类型、范围、默认值、平台差异。
- 成功响应、错误响应。
- 异步 URC。
- 示例。
- Note/Important/Pitfall。
- 来源文件、页码、章节。

### 4. 建立模块状态机

协议类模块必须先建状态机，再生成用例。

通用网络状态：

```text
BOOT
  -> SIM_READY
  -> NETWORK_REGISTERED
  -> PDP_CONFIGURED
  -> PDP_ACTIVE
```

示例：MQTT 状态机

```text
MQTT_IDLE
  -> MQTT_CONFIGURED
  -> MQTT_CONNECTING
  -> MQTT_CONNECTED
  -> MQTT_SUBSCRIBED
  -> MQTT_DISCONNECTED
```

示例：HTTP/HTTPS 状态机

```text
HTTP_IDLE
  -> HTTP_CREATED
  -> HTTP_CONFIGURED
  -> HTTP_REQUESTING
  -> HTTP_RESPONSE_READY
  -> HTTP_READING
  -> HTTP_CLOSED
```

示例：FTP 状态机

```text
FTP_IDLE
  -> FTP_CONFIGURED
  -> FTP_CONNECTED
  -> FTP_AUTHENTICATED
  -> FTP_DIR_SELECTED
  -> FTP_TRANSFERRING
  -> FTP_DISCONNECTED
```

示例：TCP/IP 状态机

```text
TCPIP_IDLE
  -> IP_CONFIGURED
  -> SOCKET_OPENING
  -> SOCKET_CONNECTED
  -> SOCKET_SENDING
  -> SOCKET_READING
  -> SOCKET_CLOSED
```

### 5. 生成模块模型

每个模块模型建议包含：

```yaml
module: MQTT
version: draft-0.1
source_documents: []
resources: []
state_machine: {}
common_setup_flows: {}
commands: []
urcs: []
flows: []
test_generation_rules: []
coverage_mapping_hints: []
example_generated_tests: []
```

每条命令建议包含：

```yaml
command: AT+XXX
summary: 功能说明
kind: set|query|execute|test|set_data_mode
source_refs: []
preconditions: []
syntax: {}
parameters: []
responses:
  success: []
  error: []
urcs: []
postconditions: []
negative_cases: []
```

### 6. 生成测试规则

测试生成规则必须覆盖四类：

1. 正向流程：按手册示例生成完整 setup → action → cleanup。
2. 参数边界：枚举、最小值、最大值、越界、空值、超长。
3. 状态负向：缺少前置条件、重复初始化、断开后调用、busy 状态调用。
4. 覆盖率导向：结合 `coverage_map.json` 或源码函数/分支 hint 生成候选变异。

用例结构建议：

```yaml
id: MQTT_PUB_QOS1_POSITIVE
module: MQTT
purpose: 验证已连接状态下 QoS=1 发布消息返回同步成功并收到 puback。
setup_flow: mqtt_connected_plain
steps:
  - send: AT+MQTTPUB=0,"world",1,0,0,4,"3242"
    expect:
      - pattern: +MQTTPUB: 0,<mid>,<length>
      - pattern: OK
      - pattern: '+MQTTURC: "puback",0,<mid>,0'
        async: true
        timeout_ms: 60000
cleanup_flow: mqtt_cleanup_disconnect
basis:
  command: AT+MQTTPUB
  source_refs:
    - document: mqtt_user_manual
      page: 26
coverage_targets:
  - file_hint: cm_atcmd_mqtt.c
    branch_hint: qos == 1 puback path
```

## 各模块建模重点

### MQTT

核心资源：`connect_id`。

重点命令：

- `AT+MQTTCFG`
- `AT+MQTTCONN`
- `AT+MQTTSUB`
- `AT+MQTTUNSUB`
- `AT+MQTTPUB`
- `AT+MQTTREAD`
- `AT+MQTTSTATE`
- `AT+MQTTDISC`
- `+MQTTURC`

重点流程：

- 非加密连接、订阅、QoS0/1/2 发布、断开。
- 缓存模式：`cached=1`、等待 `pubnmi`、`MQTTREAD`。
- MQTTS：`ssl=1`、证书/SSL 上下文前置、8883 连接。

关键断言：

- `AT+MQTTCONN` 的 `OK` 不是最终成功，必须等待 `+MQTTURC: "conn",<id>,0`。
- `AT+MQTTPUB` 的 QoS 不同，URC 期望不同。
- `AT+MQTTDISC` 连接未建立时应返回 `+CME ERROR`。

### HTTP/HTTPS

核心资源：HTTP 会话 id 或 handle。

重点命令：

- `AT+MHTTPCREATE`
- `AT+MHTTPCFG`
- `AT+MHTTPREQUEST`
- `AT+MHTTPREAD`
- `AT+MHTTPHEADER`
- `AT+MHTTPCONTENT`
- `AT+MHTTPDLFILE`
- `AT+MHTTPDEL`
- `AT+MHTTPTERM`

重点流程：

- create → cfg → request → read → delete/term。
- GET/POST/PUT/DELETE。
- HTTPS + SSL 证书配置。
- 下载到文件。

重点负向：

- 未 create 直接 request。
- 未 response ready 直接 read。
- request 过程中重复 request。
- 非法 URL、超长 header/body、超时。

### FTP

核心资源：FTP session、远端目录、本地文件。

重点命令：

- `AT+MFTPCFG`
- `AT+MFTPCONN`
- `AT+MFTPSTATE`
- `AT+MFTPPWD`
- `AT+MFTPCWD`
- `AT+MFTPLIST`
- `AT+MFTPRETR`
- `AT+MFTPSTOR`
- `AT+MFTPAPPE`
- `AT+MFTPDEL`
- `AT+MFTPRN`
- `AT+MFTPMKD`
- `AT+MFTPDISC`

重点流程：

- 连接登录 → PWD/CWD/LIST → 上传/下载/追加 → 删除/重命名/建目录 → 断开。

重点负向：

- 未连接传输。
- 错误账号。
- 非法路径。
- 本地文件不存在。
- 远端文件不存在。
- 传输中断网。

### TCP/IP

核心资源：socket id、server id、remote endpoint。

重点命令：

- `AT+MIPCFG`
- `AT+MIPOPEN`
- `AT+MIPSEND`
- `AT+MIPRD`
- `AT+MIPCLOSE`
- `AT+MIPSTATE`
- `AT+MIPLISTEN`
- `AT+MIPSRVCFG`
- `AT+MIPSENDTO`
- `AT+MDNSGIP`
- `AT+MPING`
- `AT+MNTP`

重点流程：

- TCP client open/send/read/close。
- UDP sendto/read。
- server listen/accept/send/close。
- DNS、Ping、NTP。

重点负向：

- 非法 socket id。
- 未打开直接发送。
- 重复打开。
- 远端关闭。
- 超长 payload。
- DNS 失败。

## 与覆盖率流程结合

将模块模型接入覆盖率测试流水线时，生成器应使用：

- `module_model.<module>.yaml`：命令、状态机、流程、参数边界。
- `coverage_map.json`：未覆盖桩、函数、分支条件、附近源码。
- `coverage_delta.json`：每条用例带来的新增覆盖。
- `assertion_result.json`：行为断言是否符合手册。

生成下一轮用例时：

```text
未覆盖分支
  -> 识别关联命令/参数/状态
  -> 查询 module_model
  -> 生成候选正向/负向/边界/状态变异用例
  -> 执行真实 AT
  -> 比对手册期望
  -> 记录覆盖率增量和潜在 bug
```

## 验证清单

- [ ] 已列出目标目录中的实际手册文件。
- [ ] 已从手册抽取命令清单，并记录命令首次出现页码。
- [ ] 每条命令至少包含语法、参数、成功响应、错误响应、来源页码。
- [ ] 协议状态机已建模，不能孤立生成依赖前置条件的命令。
- [ ] 每个流程有 setup、steps、cleanup。
- [ ] 异步 URC 有触发命令、pattern、timeout。
- [ ] 参数范围、枚举、默认值、平台差异已记录。
- [ ] 负向用例明确是参数负向还是状态负向。
- [ ] `module_model.<module>.yaml` 可被 YAML 解析器加载。
- [ ] 生成的测试用例包含 `basis/source_refs`。
- [ ] 行为断言失败能输出潜在 bug，而不是被覆盖率新增抵消。
- [ ] key-value 分发命令已按 key 独立生成用例，没有拼成单条巨型命令。
- [ ] 边界测试的可选参数已展开，边界值正确注入到 at_command 中。
- [ ] 无残留 `[]` 括号（生成后 grep 检查）。
- [ ] connect_id 默认用 1 不用 0。

## Pitfalls

- 不要把 `OK` 当成所有命令的最终成功。MQTT、FTP、HTTP、TCP 都可能依赖后续 URC 或状态查询。
- 不要忽略 setup/cleanup。连接类协议如果不释放资源，后续用例会被污染。
- 不要把手册示例里的公网服务器、账号、密码硬编码为通用测试配置，应替换为 `${MQTT_HOST}`、`${FTP_USER}` 等环境变量。
- 不要把平台差异丢掉。不同模块的 id 范围、长度限制、SSL 支持、缓存能力可能不同。
- 不要伪造手册内容。抽取失败时应报告 OCR/CID/扫描质量问题。
- 不要只生成正向用例。覆盖率挖掘的价值通常来自非法参数、错误状态、超时、重复操作、资源满等异常路径。
- 不要只输出 Markdown。最终应有机器可读 YAML/JSON，供执行器消费。
- 不要把 key-value 分发命令（如 AT+MQTTCFG）当单条位置参数命令生成。AT+MQTTCFG="key",connect_id,value 的每个 key 是独立变体，必须逐 key 生成用例，不能把所有参数拼成一条巨型命令。
- 不要忽略可选参数的嵌套 `[]` 清理。模板 `AT+CMD=<p1>[,<p2>[,<p3>]]` 有嵌套可选参数，必须用循环 `while '[' in result` 处理，单次 `re.sub` 会遗留残余 `]`。
- 边界测试必须展开可选参数。正向/负向用例可省略可选参数用默认值，但边界测试需要注入边界值到可选参数中，必须先展开 `[` `]` 再替换。
- connect_id 默认用 1 不用 0。实测 conn_id=0 经常返回 URC code=1（重连中），无法成功连接。

## 7. 从模型生成可执行测试用例

模型建好后，用生成器自动产出可执行用例：

```bash
python3 /Volumes/DevDrive/projects/at_knowledge_base/tools/generate_tests.py \
    <module_model.yaml> [generated_tests.yaml]
```

生成器自动处理：
- 每条命令按 syntax 变体展开正向用例
- key-value 分发命令（如 AT+MQTTCFG）每个 key 独立用例
- 命令级负向用例（negative_cases）
- 参数边界值用例（boundary_cases）
- 状态负向用例（negative_precondition_cases）
- 流程级用例（flows + positive_cases.generate_from_flow）

输出格式：`generated_tests.yaml`，含 meta（统计）和 tests（用例列表）。

详细说明见 `references/test-generator.md`。

## 8. 执行器：驱动真实 AT 测试

生成器产出 `generated_tests.yaml` 后，用执行器驱动串口执行:

```bash
python3 /Volumes/DevDrive/projects/at_knowledge_base/tools/executor.py \
    generated_tests.yaml --config env.yaml [--run-id v1]
```

执行器职责:
- 读取 generated_tests.yaml，替换 `${MQTT_HOST}` 等环境变量
- 按 category 排序执行 (flow → positive → boundary → negative → state_neg)
- 通过串口发送 AT 命令，收集响应
- 匹配 expect pattern (同步 OK/ERROR + 异步 URC)
- 每条用例后查询 `AT+COVERAGE?` 记录增量
- 输出 run_result.json、assertion_result.json、bug_candidates.json 等

详细说明见 `references/executor.md`。

## 9. 覆盖率迭代闭环

执行完第一轮后，分析结果决定是否迭代:

```text
coverage_summary.json + assertion_result.json
    │
    ├─ 覆盖率未达标 (目标 80%/60%)
    │     ├─ 分析未覆盖桩 → 查 module_model → 补充用例
    │     ├─ 追加到 generated_tests.yaml
    │     └─ 重新执行
    │
    ├─ 覆盖率饱和 (连续 N 轮无新增)
    │     └─ 输出最终报告，结束迭代
    │
    └─ 有 bug_candidates
          └─ 输出潜在 bug 列表，人工确认
```

## 完整流程图

```
PDF手册 → [步骤1-4] → module_model.yaml → [步骤7] → generated_tests.yaml
                                                         │
                                                    [步骤8] executor
                                                         │
                                                    串口执行 + 覆盖率
                                                         │
                                                    [步骤9] 分析迭代
                                                         │
                                                    未饱和 → 补充用例 → 再执行
                                                    已饱和 → 生成报告 → 结束
```

## 已有样例和工具

```text
# 规划文档
/Volumes/DevDrive/test_report_ref/at_knowledge_base_plan.md

# MQTT 模型样例
/Volumes/DevDrive/test_report_ref/mqtt_module_model.example.yaml

# 生成器工具
/Volumes/DevDrive/projects/at_knowledge_base/tools/generate_tests.py

# 执行器工具
/Volumes/DevDrive/projects/at_knowledge_base/tools/executor.py

# 环境配置模板
/Volumes/DevDrive/projects/at_knowledge_base/env.yaml

# 生成器输出样例
/Volumes/DevDrive/projects/at_knowledge_base/generated_tests.yaml
```

如果这些路径不存在，先在当前手册目录重新生成，不要依赖旧文件。