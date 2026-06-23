# MQTT 覆盖率闭环实战记录

## 背景

ML307R MQTT 模块从生成用例执行到覆盖率分析迭代，目标不是只跑完 `generated_tests.yaml`，而是完成闭环：执行 → 分析 → 生成增量 → 再执行 → 汇总增量。

## 实测结论

- 第一轮 generated tests 执行后覆盖率约 `46%/17% (227/635)`。
- 分析发现通用 executor 对 `AT+MQTTPUB` 的 `>` 数据模式处理不正确：收到 `>` 后必须写 payload，再继续等待 `+MQTTPUB`、`OK`、`+MQTTURC`；不能把 `>` 当最终响应。
- 增量 v5 专门覆盖 publish/read 数据模式后，覆盖率提升到 `50%/18% (245/635)`，新增 18 桩。
- `MQTTREAD=1,1` 单条读取缓存消息收益最高，曾带来 +11 桩。
- `MQTTPUB` zero length payload 可触发额外分支。
- 部分 generated tests 的 flow/example 没有 `at_command`，executor 应跳过并报告，不应静默当 PASS。
- 部分边界用例没有真正注入边界变量，多个 topic_length/host_length case 实际命令相同，需要修 generator。

## coverage_map 与 DETAIL

- 如果 `coverage_map.json` 未落盘，可以从插桩后的 `cm_atcmd_mqtt.c` 反扫 `COV_STMT(id)`、`COV_BRANCH_T(id)`、`COV_BRANCH_F(id)` 重建静态 map。
- 重建 map 要与 `AT+COVERAGE?` 中的模块总桩数核对；本次反扫得到 627，固件显示 635，说明还需检查其他 MQTT 源文件或宏格式。
- `AT+COVERAGE=DETAIL` 需要实测；本次固件返回 `ERROR`，`AT+COVERAGE=2` 返回 `+CME ERROR: 50`，说明没有 hit bitmap 明细。
- 没有 DETAIL 时，不能声称精确知道哪些 stub id 未命中；只能做静态热点 + 每轮总 hit 增量分析。

## 下一轮优先级

1. `MQTTPUBJSON` / JSON method / payload 组合。
2. cached 模式下多条消息 publish 后连续 `MQTTREAD=1,1`。
3. `MQTTPUB` 数据模式 payload 长度边界：0、1、准确长度、短发、超长。
4. 多实例 `conn_id=0/1/2`、重复连接、断开后重连，必须分阶段隔离，避免状态污染。
5. 修 generator：flow/example 展开、边界变量真实替换、数据模式用例带 `data_payload` 字段。

## Workflow Guardrail

用户要求“持续跑一个完整轮次”时，不要因为用例执行完成就停下。必须继续分析结果、生成下一轮、执行增量，并给出真实覆盖率增量。