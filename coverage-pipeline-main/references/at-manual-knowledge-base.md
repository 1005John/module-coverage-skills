# AT 手册知识库建模方法

## When to Use

当用户希望把蜂窝通信模组的软件 AT 手册、扩展手册、用户手册、开发指导手册用于：

- 自动生成 AT 测试用例
- 手册变更 diff 后生成新增/回归测试
- 代码变更后定位相关 AT 命令与流程
- 覆盖率未命中分支反推参数、状态和流程变异
- 将实际 AT 响应与手册期望比对并输出潜在 bug

## 核心原则

不要只做全文向量库或 RAG。应建立“结构化 AT 规范知识库”：

- 原始文档层：保存 PDF/Word/HTML/Markdown 原件。
- 文档切片层：按章节、页码、命令、流程示例切片，保留 source_refs。
- 指令规范层：命令语法、参数、范围、枚举、响应、错误码。
- URC 层：异步上报格式、触发命令、状态含义、超时规则。
- 状态机层：前置状态、成功后状态、失败回滚、资源句柄。
- 流程层：完整业务流程，例如 MQTT 连接→订阅→发布→断开。
- 测试生成层：setup、steps、expect、cleanup、basis、coverage_targets。

向量索引只做语义检索辅助，不能作为测试生成的唯一依据。

## 推荐目录

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
  generated/
    manual_expectations.<module>.json
    generated_tests.<module>.yaml
  reports/
    manual_diff_report.md
    extraction_quality_report.md
  kb.sqlite
  vector_index/
```

## 通用命令模型

```yaml
command: AT+XXX
module: MQTT
kind: set|read|test|execute|urc
summary: 功能说明
syntax: []
parameters: []
preconditions: []
postconditions: []
state_transitions: []
responses:
  success: []
  error: []
urcs: []
examples: []
negative_cases: []
source_refs: []
```

## 测试用例模型

每条生成用例必须带依据和可验证断言：

```yaml
id: MQTT_PUB_WITHOUT_CONN_NEGATIVE
module: MQTT
purpose: 验证未建立连接时发布消息返回错误
setup:
  - ensure_state: MQTT_IDLE
steps:
  - send: AT+MQTTPUB=0,"world",1,0,0,4,"3242"
expect:
  - pattern: +CME ERROR: <err>
cleanup: []
basis:
  command: AT+MQTTPUB
  rule: precondition_missing_MQTT_CONNECTED
  source_refs:
    - document: MQTT用户手册.pdf
      page: 26
coverage_targets:
  - file_hint: cm_atcmd_mqtt.c
    branch_hint: publish_without_connection
```

## 状态机是一等公民

协议类命令不能孤立生成测试。生成器必须根据 `preconditions` 自动补齐 setup flow，或故意破坏前置条件生成负向用例。

通用网络前置状态：

```text
BOOT
  -> SIM_READY
  -> NETWORK_REGISTERED
  -> PDP_CONFIGURED
  -> PDP_ACTIVE
```

MQTT 示例状态机：

```text
MQTT_IDLE
  -> MQTT_CONFIGURED
  -> MQTT_CONNECTING
  -> MQTT_CONNECTED
  -> MQTT_SUBSCRIBED
  -> MQTT_PUBLISHING
  -> MQTT_DISCONNECTED
```

例如 `AT+MQTTPUB` 必须要求 `MQTT_CONNECTED`；正向用例自动补齐 `AT+MQTTCONN`，负向用例可故意未连接直接发布并断言错误。

## MQTT 建模重点

当前手册识别的 MQTT 核心命令：

- `AT+MQTTCFG`：版本、PDP、SSL、keepalive、clean、重传、will、心跳、编码、缓存、重连。
- `AT+MQTTCONN`：创建连接，成功后等待 `+MQTTURC: "conn",<connect_id>,0`。
- `AT+MQTTSUB`：订阅，等待 `suback`。
- `AT+MQTTUNSUB`：取消订阅，等待 `unsuback`。
- `AT+MQTTPUB`：发布，QoS0 无发布结果 URC，QoS1 等待 `puback`，QoS2 等待 `pubrec` 和 `pubcomp`。
- `AT+MQTTREAD`：缓存模式下读取缓存消息。
- `AT+MQTTSTATE`：查询连接状态。
- `AT+MQTTDISC`：断开并释放资源。

推荐 MQTT flow：

- 非加密：`MQTTCFG pingresp` → `MQTTCONN` → `MQTTSUB` → `MQTTPUB QoS0/1/2` → `MQTTDISC`。
- 缓存模式：`MQTTCFG cached=1` → `MQTTCONN` → `MQTTSUB` → 等 `pubnmi` → `MQTTREAD` → `MQTTDISC`。
- MQTTS：先配置 SSL 上下文，再 `MQTTCFG ssl=1` → `MQTTCONN` 8883 → 订阅/发布/断开。

## HTTP/FTP/TCP 建模方向

HTTP/HTTPS：

```text
HTTP_IDLE -> HTTP_CREATED -> HTTP_CONFIGURED -> HTTP_REQUESTING -> HTTP_RESPONSE_READY -> HTTP_READING -> HTTP_CLOSED
```

重点覆盖 create/config/request/read/header/content/download/delete/term，负向覆盖未 create 直接 request、未响应直接 read、非法 URL、超长 header/body、HTTPS SSL 配置缺失。

FTP：

```text
FTP_IDLE -> FTP_CONFIGURED -> FTP_CONNECTED -> FTP_AUTHENTICATED -> FTP_DIR_SELECTED -> FTP_TRANSFERRING -> FTP_DISCONNECTED
```

重点覆盖 conn/state/pwd/cwd/list/retr/stor/appe/del/rn/mkd/disc，以及文件存在性、错误账号、非法路径、未连接传输。

TCP/IP：

```text
TCPIP_IDLE -> IP_CONFIGURED -> SOCKET_OPENING -> SOCKET_CONNECTED -> SOCKET_SENDING -> SOCKET_READING -> SOCKET_CLOSED
```

同时建服务端监听状态机，覆盖 TCP client、UDP、server listen、DNS、Ping、NTP、keepalive、透传/非透传、非法 socket、重复打开、远端关闭。

## 覆盖率闭环

1. 手册抽取生成 `module_model.yaml`。
2. 生成 `generated_tests.yaml`，包含 setup/steps/expect/cleanup/basis。
3. 执行真实 AT 命令并记录同步响应与异步 URC。
4. 比对手册期望，断言失败输出 `bug_candidates.json`。
5. 收集覆盖率和未命中桩。
6. 用 `coverage_map.json` 的文件/函数/分支提示映射回命令、参数、状态。
7. 生成下一轮边界、状态、流程变异用例。

## Pitfalls

- 不要只让 LLM 看手册直接编用例；必须先结构化成命令/参数/响应/状态机。
- 不要只判断 `OK`；MQTT/FTP/TCP/HTTP 很多成功依赖异步 URC 或后续读取。
- 不要忽略 cleanup；协议资源未释放会污染下一条用例。
- 不要把覆盖率提升当作行为通过；实际响应不符合手册仍要输出潜在 bug。
- 不要让向量库承担精确断言、参数边界、版本 diff，这些必须由结构化模型和 sqlite/json/yaml 承担。
- 平台差异要建模为 `platform_overrides`，不要把某一型号范围当成全局规则。

## 验证清单

- [ ] 每条命令有语法、参数、成功响应、错误响应、来源页码。
- [ ] 每个协议至少有一个完整正向 flow。
- [ ] 状态依赖命令有 `preconditions` 和 `cleanup`。
- [ ] 异步 URC 有触发命令、pattern、状态含义。
- [ ] 用例带 `basis.source_refs`，能追溯到手册。
- [ ] 负向用例区分参数边界、缺失前置状态、资源状态冲突。
- [ ] 覆盖率目标只作为补充，行为断言失败必须单独报告。
