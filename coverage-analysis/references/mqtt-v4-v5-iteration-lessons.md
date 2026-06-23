# MQTT v4/v5 覆盖率迭代经验

## 场景

ML307R MQTT 模块覆盖率闭环：先跑手册生成用例，再分析结果并补充增量 runner。

## 关键结果

- v4：91 条生成用例 + tail 补跑，覆盖率达到 `46%/17% (227/635)`。
- v5：针对数据模式 publish/read 生成 11 条增量用例，覆盖率提升到 `50%/18% (245/635)`，新增 18 桩。
- 高收益点：`AT+MQTTREAD=1,1` 新增 11 桩；`AT+MQTTPUB` zero-length payload 新增 4 桩。

## 工作流教训

1. 用户目标是“覆盖率分析迭代测试脚本持续跑一个完整轮次”时，不能停在“用例执行完成”。必须继续完成：执行 → 结果分析 → 生成下一轮用例/脚本 → 执行增量轮 → 汇总闭环报告。
2. 若长流程前台 SSH 被用户追问或中断，应先确认已落盘结果，再继续从结果目录恢复，不要把中断当作最终状态。
3. 每轮必须落盘机器可读产物：`run_result.json`、`coverage_analysis.json` 或 `coverage_summary.json`、`bug_candidates.json`、`at_execution_log.txt`、人类可读报告。
4. 如果没有 `coverage_map.json`/`AT+COVERAGE=DETAIL`，只能做黑盒收益分析：按命令、状态和新增 hit 数选择下一轮候选；不能声称已完成桩级未覆盖分析。

## MQTT 执行器/用例生成教训

1. `AT+MQTTPUB` 是数据模式命令：命令返回 `>` 后必须发送 payload，再读取 `+MQTTPUB`、`OK` 和后续 `+MQTTURC`。通用单命令 executor 若把 `>` 当结束，会污染后续 `AT+COVERAGE?`。
2. 生成器必须为数据模式用例携带 `data_payload`/`payload_len`，执行器必须原生支持；不要把 publish 用例压成单条普通 AT 命令。
3. flow/example 用例如果没有展开成 `at_command`，执行器只能 `SKIP`；生成器应把 flow 展开成可执行 steps，或执行器支持 `steps`。
4. 边界用例必须真实注入边界变量。若 `topic_length_0/1/256/257` 等多条用例实际 at_command 相同，覆盖率迭代会浪费时间且误导分析。
5. `AT+MQTTCONN` 生成时要补齐 `host,port,client_id,username,password`，不能只生成 `AT+MQTTCONN=<id>,"host"`。
6. `AT+MQTTCONN=?`、`AT+MQTTSUB=<id>` 等 query/test 命令不应强等业务 URC；异步 URC 等待只用于真正触发异步业务的命令。

## 推荐 v6 候选

- `MQTTPUBJSON`：JSON 发布路径、method 空/非空、非法 JSON/长度不匹配。
- cached read：缓存多条消息后执行 `AT+MQTTREAD=1`、`AT+MQTTREAD=1,1/2/N`。
- QoS2 完整链路：验证 `pubrec`/`pubcomp`。
- 多 conn_id：连接 id 0/1/2 分别连接、订阅、发布、断开。
- SSL/MQTTS 如果证书条件满足，再单独作为高成本候选。
