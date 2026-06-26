# PING + DNS 覆盖率测试结果 (2026-06-26)

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| 编译服务器 | 192.168.242.120 (Lenovo/123) |
| 固件版本 | ML307C-DC-CN-MBRH1S00_4.0.15.2606261507_release |
| 桩数 | 132 (PWM:57, PING:15, DNS:60) |

## 覆盖率结果

### v1 (首轮 PING+DNS, 23 条用例)

| 模块 | 语句覆盖率 | 分支覆盖率 | 命中/总数 |
|------|-----------|-----------|----------|
| PING | 100% | 53% | 9/15 |
| PWM | 6% | 88% | 26/57 |
| DNS | 40% | 27% | 17/60 |
| ALL | - | - | 52/132 |

### v2 (DNS 迭代, 29 条用例)

| 模块 | 语句覆盖率 | 分支覆盖率 | 命中/总数 |
|------|-----------|-----------|----------|
| DNS | 40% | 34% | 21/60 |

增量仅 +4 桩。瓶颈：AT+MDNSGIP 全部返回 CME ERROR:4。

## 根因：模组未注册网络

```
AT+CPIN?    → +CPIN: READY (SIM 正常)
AT+CEREG?   → +CEREG: 0,0 (未注册网络!)
AT+CGACT?   → OK (无活跃 PDP)
AT+CGACT=1,1 → ERROR (无法激活 PDP)
AT+MDNSGIP  → CME ERROR:4 (DNS 必然失败)
```

**结论**：DNS 成功路径（返回 IP 地址）需要活跃的蜂窝网络。无网络时只能覆盖错误路径。

## ML307C 平台限制

| 命令 | 支持 | 备注 |
|------|------|------|
| AT+MDNSCFG="priority" | ✓ | 唯一支持的 key |
| AT+MDNSCFG="ip" | ✗ CME ERROR:4 | 手册确认 ML307C 不支持 |
| AT+MDNSCFG="ipv6" | ✗ CME ERROR:4 | 同上 |
| AT+MDNSCFG="cached" | ✗ CME ERROR:50 | 手册确认 ML307C 仅支持 priority |
| AT+MDNSCFG="timeout" | ✗ CME ERROR:50 | 同上 |
| AT+MDNSCFG=? | ✓ | 返回 "priority",(0,1) |
| AT+MDNSGIP | ✗ CME ERROR:4 | 无网络，DNS 解析失败 |
| AT+MPING? | ✗ CME ERROR:4 | ML307C 不支持 query |
| AT+MPING=? | ✓ | 返回参数范围 |

## 高收益用例 (v1)

| 用例 | 新增桩 | 类别 |
|------|--------|------|
| MDNSCFG_TEST (=?) | +4 | positive |
| MDNSCFG_IP_QUERY | +8 | positive (错误路径) |
| MDNSCFG_IPV6_QUERY | +4 | positive (错误路径) |
| MDNSCFG_IP_SET | +4 | positive (错误路径) |
| MDNSGIP_TEST (=?) | +4 | positive |
| MPING_BASIC | +6 | positive |

## DNS 覆盖率天花板分析

60 个桩中已覆盖 21 个（35%）。剩余 39 个桩分布推测：
- MDNSGIP 成功返回 IP 路径：~15 桩（需要活跃网络）
- MDNSGIP 多 IP 列表路径：~8 桩（需要 DNS 返回多个 A 记录）
- MDNSGIP IPv4/IPv6 双栈路径：~6 桩（需要优先级切换 + 网络）
- MDNSCFG 未支持 key 的深层路径：~10 桩（平台不支持，不可达）

**无网络时天花板：~35% (21/60)**
**有网络时预期：~65-80%**（取决于 DNS 成功路径覆盖程度）

## 结论

1. DNS 模块必须在有活跃蜂窝网络的环境下测试
2. 测试前先检查 `AT+CEREG?` 确认注册状态
3. ML307C 平台 MDNSCFG 仅支持 "priority"，用例生成需过滤不支持的 key
4. AT+MPING? query 不支持，用例中不应包含 query 变体
