# ML307R MQTT 覆盖率测试闭环报告

## 概述

从零开始完成 MQTT AT 命令层覆盖率测试全流程：插桩 → 编译 → 烧录 → 测试执行 → bitmap 采集 → 分析 → 迭代。

**最终成果**：MQTT 635 桩，覆盖率 51%/22% (261/635)

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| MQTT Broker | 8.137.154.246:1883 |
| 固件版本 | 3.1.0.2606230824_release |
| SDK 路径 | D:\ML307R\SDK |
| 源文件 | D:\ML307R\SDK\onemo\at\src\cm_atcmd_mqtt.c |

## 桩分布

| 函数 | 桩数 | 类型 |
|------|------|------|
| cm_at_mqtt_connect_cmd | 75 | 56 stmt + 19 branch |
| cm_at_mqtt_publish_cmd_combine | 75 | 51 stmt + 24 branch |
| cm_at_mqtt_subscribe_cmd | 66 | 42 stmt + 24 branch |
| __mqtt_atcmd_cfg_platform_devinfo | 42 | 24 stmt + 18 branch |
| __mqtt_atcmd_datamode_cb | 42 | 26 stmt + 16 branch |
| cm_at_mqtt_read_cmd | 36 | 26 stmt + 10 branch |
| 其他 22 个函数 | 299 | - |
| **总计** | **635** | **402 stmt + 233 branch** |

## 迭代历程

| 轮次 | stmt% | branch% | 命中/总数 | 关键改进 |
|------|-------|---------|----------|---------|
| v4 | 46% | 17% | 227/635 | 通用 executor，91 条生成用例 |
| v5 | 50% | 18% | 245/635 | 数据模式 publish/read |
| v6 | 32% | 13% | 162/635 | bitmap 采集框架（清零重跑） |
| v7 | 38% | 15% | 191/635 | CFG/query/retrans/encoding |
| v8 | 33% | 11% | 163/635 | 连接保持策略（清零重跑） |
| **v9** | **51%** | **22%** | **261/635** | **分阶段执行 + 全 CFG 矩阵** |

## v9 高收益 Case

| Case | 新增桩 | 说明 |
|------|--------|------|
| setup_conn | +53 | 建立连接全流程 |
| pub_dm_qos0 | +35 | 数据模式 QoS0 发布 |
| cfg_query_all_cids | +28 | 6 个 conn_id 的 query |
| cfg_will_matrix | +20 | will 遗嘱配置矩阵 |
| sub_multi | +19 | 3 topic 订阅 |
| cfg_platform_devinfo | +16 | 平台认证配置 |
| pubjson | +15 | JSON 发布 |
| cfg_reconn_matrix | +13 | 重连配置矩阵 |
| unsub_one | +11 | 取消订阅 |
| cfg_encoding_matrix | +10 | 编码配置矩阵 |

## 未覆盖热点（366 桩剩余）

| 函数 | 未覆盖 | stmt | branch | 说明 |
|------|--------|------|--------|------|
| cm_at_mqtt_subscribe_cmd | 45 | 26 | 19 | 多 topic/qos 组合 |
| cm_at_mqtt_connect_cmd | 44 | 31 | 13 | 多 conn_id/重复连接 |
| cm_at_mqtt_publish_cmd_combine | 37 | 19 | 18 | inline/datamode 边界 |
| __mqtt_atcmd_datamode_cb | 30 | 18 | 12 | 数据模式回调 |
| __mqtt_atcmd_cfg_platform_devinfo | 29 | 13 | 16 | devinfo 设置 |
| cm_at_mqtt_read_cmd | 26 | 18 | 8 | cached 多条读取 |
| __mqtt_atcmd_cfg_will_payload | 24 | 11 | 13 | will payload 设置 |

## 关键发现

### 1. 分阶段执行是覆盖率提升的关键

```
阶段1: CFG 测试（不需要连接）
  → query/reconn/retrans/encoding/platform/will/ssl/pingreq/pingresp/sndbuf
  → 贡献 ~100 桩

阶段2: 建立连接
  → setup_conn
  → 贡献 ~53 桩

阶段3: SUB/PUB/READ/UNSUB（需要连接）
  → 贡献 ~80 桩

阶段4: DNS 失败（放最后，会破坏连接状态）
  → 贡献 ~3 桩
```

### 2. 数据模式必须专门处理

`AT+MQTTPUB=...` 返回 `>` 后必须写入 payload，再继续读取 `+MQTTPUB`/`OK`/`+MQTTURC`。通用 executor 不支持此模式。

### 3. bitmap 采集是精确分析的基础

`AT+COVERAGE=2..9` 返回 MQTT bitmap 分块，每 chunk 8 个 32-bit word，覆盖 2000 个 stub id。通过 `word_index = stub_id / 32`，`bit = stub_id % 32` 判断命中。

### 4. 连接管理策略

- 每次 case 前检查 `AT+MQTTSTATE=<cid>`
- 断开则重新连接
- CFG 测试不需要连接，应优先执行
- DNS 失败放最后，会破坏连接状态

## 产出文件

```
D:\ML307R\at_kb_runs\
├── coverage_map.mqtt.json          # 627 桩映射（从源码反扫）
├── mqtt-v4\                        # 通用 executor 结果
│   ├── run_result.json
│   ├── assertion_result.json
│   ├── coverage_summary.json
│   └── bug_candidates.json
├── mqtt-v5\                        # 数据模式 publish/read
│   ├── run_result.json
│   └── coverage_analysis.json
├── mqtt-v6-bitmap\                 # bitmap 采集框架
│   ├── coverage_delta.json
│   ├── uncovered_stubs.json
│   └── report.md
├── mqtt-v7-bitmap\                 # CFG/query/retrans/encoding
│   ├── coverage_delta.json
│   └── report.md
├── mqtt-v8-bitmap\                 # 连接保持策略
│   ├── coverage_delta.json
│   └── report.md
└── mqtt-v9-bitmap\                 # 最终结果
    ├── coverage_delta.json
    ├── uncovered_stubs.json
    ├── report.md
    ├── run_result.json
    └── at_execution_log.txt
```

## 固件增强

### AT+COVERAGE=2..9 bitmap 分块输出

**格式**：
```
AT+COVERAGE=2    # chunk 0, words 0-7
AT+COVERAGE=3    # chunk 1, words 8-7
...
AT+COVERAGE=9    # chunk 7, words 56-63
```

**返回**：
```
+COVERAGE_DETAIL: MQTT,<chunk>,<base_word>,<w0>,<w1>,<w2>,<w3>,<w4>,<w5>,<w6>,<w7>
```

**判断命中**：
```python
word_index = stub_id // 32
bit = stub_id % 32
hit = (words[word_index] & (1 << bit)) != 0
```

## 后续方向

1. **继续迭代**：打 subscribe/connect/publish/datamode 路径
2. **平台认证**：`devinfo` 返回 CME ERROR:606，需要深入分析
3. **多 conn_id**：测试 conn_id=0/2/3/4/5 的独立路径
4. **datamode 回调**：payload 超短/准确/超长、ESC 干扰
5. **生成测试报告**：Excel/HTML 格式
