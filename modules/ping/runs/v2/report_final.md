# PING 模块覆盖率测试报告

## 概述

PING 模块（AT+MPING）覆盖率测试。

**实际**：语句覆盖率 100%，分支覆盖率 30%（6/15）
**结论**：AT 命令测试天花板已达

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| 编译服务器 | 192.168.242.120 (Lenovo/123) |
| 固件版本 | ML307C-DC-CN-MBRH1S00_4.0.15.2606261053_release |
| 桩数 | 15 (2 stmt + 13 branch) |
| 函数 | _CMIOT_NetPingRspFunc, cmMPING |

## 插桩修复记录（6 个问题）

### 问题 1-5：同 PWM 模块（见 coverage-instrumentation SKILL.md）

### 问题 6：cm_cov_hit() 只递增全局 PWM 计数器
- **现象**：PING 桩始终 0/15，即使 .o 有 BL cm_cov_hit 调用
- **根因**：cm_cov_hit() 递增 cov_pwm_stmt_hits，extern.c 读 cov_ping_stmt_hits
- **修复**：cm_cov_is_hit() + 本地 cm_cov_ping_hit() 桥接

### 问题 7：.lib 路径不在 obj_onemo_onemo/ 下
- **现象**：删 .o 后重编，.lib 仍用旧 .o
- **根因**：.lib 实际路径是 obj_PMD2NONE/onemo-onemo.lib
- **修复**：删 .lib + .o + .d + .pp + pack_c.via

## 测试结果

| 指标 | 值 |
|------|-----|
| 语句覆盖率 | 100% (2/2) |
| 分支覆盖率 | 30% (4/13) |
| 总计 | 40% (6/15) |

## 未覆盖分支（9 个）

异步回调函数 _CMIOT_NetPingRspFunc 中的分支和 cmMPING 中的深层错误路径。
