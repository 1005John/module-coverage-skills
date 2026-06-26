# DNS 模块覆盖率测试结果 (2026-06-26)

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| 编译服务器 | 192.168.242.120 (Lenovo/123) |
| 固件版本 | ML307C-DC-CN-MBRH1S00_4.0.15.2606261507_release |
| 桩数 | 60 (全部在 cm_atcmd_dns.c) |
| 涉及命令 | AT+MDNSCFG, AT+MDNSGIP |

## 迭代记录

| 轮次 | stmt | branch | hit/total | 策略 | 新增 |
|------|------|--------|-----------|------|------|
| v1 | 40% | 27% | 17/60 | 基础 MDNSCFG/GIP（网络未注册） | - |
| v2 | 80% | 34% | 21/60 | priority 错误路径 | +4 |
| v3 | 100% | 41% | 28/60 | **网络注册后** DNS 成功路径 | +7 |
| v4 | 100% | 49% | 32/60 | 全 key set+query+缓存 | +4 |
| v5 | 100% | 49% | 32/60 | 主备切换/缓存/超时/重试 | +0 (饱和) |

## 饱和分析

DNS branch 49% (32/60) 是 AT 命令测试天花板。剩余 28 个 branch 分布：

| 未覆盖区域 | 估计桩数 | 原因 |
|------------|----------|------|
| UDP socket 收发 | ~8 | 需直接操作网络栈 |
| DNS 重试循环内部 | ~6 | AT 层面只看到最终结果 |
| NV 存储读写 | ~4 | ML307C 暂不保存 NV |
| 主/备服务器切换 | ~4 | 内部自动切换，AT 无感知 |
| 缓存管理内部 | ~3 | AT 只控制开关 |
| 其他 | ~3 | 平台特定路径 |

## 关键发现

### 1. 网络注册是 DNS 测试前提

```
+CEREG: 0,0  → AT+MDNSGIP 全部返回 CME ERROR:4
+CEREG: 0,1  → AT+MDNSGIP 正常返回 IP 地址
```

诊断流程：`AT+CPIN?` → `AT+CEREG?` → `AT+CGACT?` → `AT+CGPADDR=1`

### 2. ML307C MDNSCFG 实际支持范围

手册 Note 说"仅支持 priority"，实测固件 4.0.15+：

| key | SET | QUERY |
|-----|-----|-------|
| "priority" | OK | OK (`+MDNSCFG: "priority",N`) |
| "ip" | OK | OK (`+MDNSCFG: "ip","addr1","addr2"`) |
| "ipv6" | OK | OK (`+MDNSCFG: "ipv6","addr1","addr2"`) |
| "cached" | OK | CME ERROR:50 |
| "timeout" | OK | CME ERROR:50 |

### 3. 高收益用例

| 用例 | 新增桩 | 说明 |
|------|--------|------|
| DNS_CFG_PRIORITY_V4 | +6 | priority=0 触发 IPv4 路径 |
| DNS_CFG_PRIORITY_QUERY | +4 | 查询路径 |
| DNS_IP_QUERY | +4 | IPv4 服务器查询 |
| DNS_IPV6_QUERY | +4 | IPv6 服务器查询 |
| DNS_CFG_PRIORITY_BAD | +2 | 越界值错误路径 |

### 4. 潜在 Bug

| 用例 | 期望 | 实际 | 严重程度 |
|------|------|------|----------|
| AT+MDNSCFG="cached" query | +MDNSCFG: | CME ERROR:50 | 低（功能限制） |
| AT+MDNSCFG="timeout" query | +MDNSCFG: | CME ERROR:50 | 低（功能限制） |
| AT+MDNSGIP="" | CME ERROR | OK + 空 URC | 中（空域名应报错） |

## v6: 底层插桩后测试

AT 层 49% 饱和后，对底层 cm_async_dns.c 追加插桩（16 桩：4 stmt + 12 branch）。

### DNS + DNSAPI 合并覆盖率

| 模块 | 语句 | 分支 | 命中/总数 |
|------|------|------|----------|
| DNS (AT层 cm_atcmd_dns.c) | 100% | 41% | 28/60 |
| DNSAPI (底层 cm_async_dns.c) | 50% | 0% | 2/16 |
| **合计** | **96%** | **39%** | **30/76** |

### 关键发现

1. **底层桩分母变大但 branch 未突破** — 从 49%/60桩 降到 39%/76桩。cm_async_dns.c 的 12 个 branch 桩在 AT 命令路径之外（异步调度、类型选择、初始化），通过 AT 命令无法触发。
2. **cm_plat_dns.c 是死代码** — 28 个桩已插但不在 .mak 构建文件中，不参与编译。插桩前需确认文件是否在构建系统中。
3. **DNSAPI stmt 50%** — 2/4 stmt 桩被 AT+MDNSGIP 调用链触发（cm_async_dns_request 入口）。
4. **突破 39% 需要**：直接调用 cm_async_dns_request() 等内部 API，或在更底层的 cm_plat_dns.c（如果恢复编译）插桩。

### 迭代历程总览

| 轮次 | 桩数 | 语句 | 分支 | 关键变化 |
|------|------|------|------|----------|
| v1 | 60 | 40% | 27% | 基础测试（无网络） |
| v2 | 60 | 80% | 34% | priority 错误路径 |
| v3 | 60 | 100% | 41% | 网络注册后成功路径 |
| v4 | 60 | 100% | 49% | 全 key set+query |
| v5 | 60 | 100% | 49% | 主备/缓存/超时（AT 层饱和） |
| v6 | 76 | 96% | 39% | 底层插桩（分母变大） |

## 产出文件

```
D:\通信模组\at_kb_runs\runs\dns_final\
├── report.md
├── report.xlsx
├── run_result.json
├── bug_candidates.json
├── coverage_delta.json
├── iteration_decision.json
└── at_execution_log.txt
```
