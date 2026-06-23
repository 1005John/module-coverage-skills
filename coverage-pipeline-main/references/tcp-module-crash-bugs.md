# TCP 模块 (cm_atcmd_tcpip.c) 固件 Bug 记录

**固件版本**: 3.1.0.2606221536_release (ML307R)
**发现时间**: 2026-06-22
**测试环境**: AT口 COM16, Echo server 8.137.154.246:9500(TCP)/9501(UDP)

## Bug 1: MIPCLOSE 所有模式在数据交换后 crash

**严重级别**: Critical
**复现率**: 100%

**复现步骤**:
1. `AT+MIPOPEN=0,"TCP","8.137.154.246",9500,30,0` → OK, +MIPOPEN: 0,0
2. `AT+MIPSEND=0,5` (数据模式) → 发送 HELLO → +MIPSEND: 0,5
3. 等待 +MIPURC: "rtcp" echo 回来
4. `AT+MIPCLOSE=0,0` (或 mode=1 或 mode=2) → **模组崩溃重启**

**影响**: 覆盖率归零，需要物理拔插 USB 恢复

**安全操作**: `AT+MIPCLOSE=0,2` (abort) 在 **无数据的 idle 连接** 上安全

**测试策略**: 不关闭有数据的连接，用完即弃

## Bug 2: MIPMODE 0→1 切换 crash

**严重级别**: Critical
**复现率**: 100%

**复现步骤**:
1. `AT+MIPOPEN=0,"TCP","...",9500,30,0` → CONNECTED
2. `AT+MIPMODE=0,1` → **模组崩溃重启**

**安全替代**: 在 MIPOPEN 时直接指定 access_mode：
- `AT+MIPOPEN=0,"TCP","...",9500,30,1` (cache_stream)
- `AT+MIPOPEN=0,"TCP","...",9500,30,2` (cache_package)

## Bug 3: MIPRD/MIPSACK idle 返回 OK

**严重级别**: Medium
**复现步骤**:
1. 模组空闲（无连接）
2. `AT+MIPRD=0` → 返回 OK（应为 ERROR/CM_TCPIP_FIAL）
3. `AT+MIPSACK=0` → 返回 OK（应为 CM_TCPIP_NO_CONN）

**源码分析**: cmMIPRD 在 `state == CM_TCPIP_CONN_INITIAL` 时应返回 CM_TCPIP_FIAL，但 access_mode=0 导致提前 break 返回 0。

## TCP 测试覆盖率现状

| 指标 | 值 | 说明 |
|------|-----|------|
| 语句桩 | 300 | IDs 500-799 |
| 分支桩 | 162 | IDs 2500-2661 |
| 总桩 | 462 | AT 层 cm_atcmd_tcpip.c |
| 已达覆盖率 | ~45%/32% | mode=0 数据交换路径 |
| 未覆盖主要区域 | ~60% | cache_stream/package 深路径、关闭路径、模式切换 |

## 安全测试策略

```
每个 access_mode 需要独立模组重启:
1. mode=0: MIPOPEN ... 30,0 → 数据测试 → 不关闭
2. 重启模组
3. mode=1: MIPOPEN ... 30,1 → 数据测试 → 不关闭
4. 重启模组
5. mode=2: MIPOPEN ... 30,2 → 数据测试 → 不关闭
```

## Echo Server

- 地址: 8.137.154.246
- TCP: 9500
- UDP: 9501
- SSH: root / OneMo@2024
- 部署: `python3 /tmp/echo_server.py` (nohup 后台)
- 验证: `echo "test" | nc -w 3 8.137.154.246 9500`
