# PING 模块覆盖率测试结果 (2026-06-26)

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| 编译服务器 | 192.168.242.120 (Lenovo/123) |
| 固件版本 | ML307C-DC-CN-MBRH1S00_4.0.15.2606261053_release |
| 模块 | ML307C (DC-CN 变体) |
| 源文件 | cm_atcmd_ping.c |
| 桩数 | 15 (2 stmt + 13 branch) |
| 函数 | _CMIOT_NetPingRspFunc, cmMPING |

## 最终结果

```
PING: 100% 语句 (2/2), 30% 分支 (4/13), 总计 6/15 (40%)
ALL:  8% 语句, 17% 分支, 12/45 (PWM 26 + PING 6)
```

## 命中的桩 (6/15)

| 桩 ID | 类型 | 函数 | 触发命令 |
|-------|------|------|----------|
| 100 | stmt | _CMIOT_NetPingRspFunc | AT+MPING="www.baidu.com" |
| 101 | stmt | cmMPING | AT+MPING=? |
| 200 | branch | _CMIOT_NetPingRspFunc | AT+MPING="www.baidu.com" |
| 203 | branch | cmMPING (GET_CMD) | AT+MPING=? |
| 204 | branch | cmMPING (SET_CMD) | AT+MPING="www.baidu.com" |
| 212 | branch | cmMPING (default) | AT+MPING="" |

## 未覆盖的桩 (9/15)

| 桩 ID | 推测位置 | 原因 |
|-------|----------|------|
| 201 | _CMIOT_NetPingRspFunc error path | 需要 ping 失败触发回调 |
| 202 | _CMIOT_NetPingRspFunc stats path | 需要多次 ping 统计 |
| 205-211 | cmMPING 内部分支 | 参数解析、边界条件等深层路径 |

## 测试用例

| Case | 命令 | 新增桩 | 说明 |
|------|------|--------|------|
| ping_baidu | AT+MPING="www.baidu.com" | +4 | 基本 ping |
| ping_test | AT+MPING=? | +1 | 测试命令 |
| ping_114 | AT+MPING="114.114.114.114" | +0 | IP ping |
| ping_invalid | AT+MPING="999.999.999.999" | +0 | 无效 IP |
| ping_empty | AT+MPING="" | +1 | 空参数错误路径 |
| ping_localhost | AT+MPING="127.0.0.1" | +0 | 回环 |
| ping_timeout | AT+MPING="192.0.2.1" | +0 | 超时 |
| ping_count_3 | AT+MPING="www.baidu.com",3 | +0 | 多次 ping |
| ping_size_64 | AT+MPING="www.baidu.com",1,64 | +0 | 指定包大小 |
| ping_timeout_1 | AT+MPING="www.baidu.com",1,64,1 | +0 | 指定超时 |

## 关键发现

1. **前两个命令贡献了 5/6 的命中** — ping_baidu (+4) + ping_test (+1)
2. **后续变体命令无增量** — 不同 IP、包大小、超时参数都不触发新桩
3. **异步回调路径难覆盖** — _CMIOT_NetPingRspFunc 的 error/stats 分支需要特定网络条件
4. **覆盖率天花板 40%** — 纯 AT 命令测试无法覆盖异步回调和深层错误处理

## 插桩修复记录

本次 PING 插桩踩了 5 个坑：

1. cm_atcmd_extern.c 缺少 PING 的 extern 声明和 sprintf → 链接错误
2. cm_atcmd_ping.c 缺少 cov_ping_stmt_hits 变量定义 → 链接错误
3. cm_atcmd_ping.c 缺少 #define CM_COVERAGE_ENABLE → 桩编译为空操作
4. cm_coverage.c 缺少 cm_cov_is_hit() → 多模块计数器冲突
5. .lib 路径在 obj_PMD2NONE/ 不在 obj_onemo_onemo/ → 增量编译不重编
