# TCP 模块测试实测经验 (2026-06-22)

## 覆盖率里程碑

| 轮次 | 覆盖率 | 命中桩 | 说明 |
|------|--------|--------|------|
| v1 (无网络) | TCP(43%,32%,183/462) | +126 | 纯 AT 命令天花板 |
| v4 (有连接) | TCP(45%,31%,186/462) | +3 | MIPOPEN + MIPSTATE |
| v6 (多模式) | TCP(35%,22%,142/462) | +136 | mode=0 全量，crash 前 |
| v9 mode=0 | TCP(38%,26%,159/462) | +159 | 单连接不关闭，完整数据交换 |

插桩: 300 stmt + 162 branch = 462 总桩 (ID: stmt 500-799, branch 2500-2661)

## MIPSEND 数据模式

内联格式 `AT+MIPSEND=0,5,"HELLO"` 返回 CME ERROR:50。必须用数据模式：

```
AT+MIPSEND=0,5          ← 不带 data
>                        ← 模组提示符
HELLO                    ← 原始数据（精确长度）
+MIPSEND: 0,5            ← 成功
+MIPURC: "rtcp",0,5,48454C4C4F  ← echo (hex)
```

## Crash Bug (100% 复现)

### MIPCLOSE 有数据连接
MIPOPEN → MIPSEND → MIPRCV → MIPCLOSE (mode=0/1/2) → **模组重启**
- 6/6 复现，覆盖率归零
- idle 连接的 MIPCLOSE 安全

### MIPMODE 切换
MIPOPEN mode=0 → MIPSEND → MIPMODE=0,1 → **模组重启**

### MIPOPEN mode 冲突
有 mode=0 活跃连接 → MIPOPEN mode=1 (不同 cid) → **模组重启**

## 测试策略

```
每种 access_mode 独立流程:
1. 重启模组
2. MIPOPEN mode=N (不关闭之前连接)
3. 全量数据/配置/查询测试
4. 记录覆盖率
5. 需测其他 mode → 回到步骤 1
```

## YAML 解析陷阱

1. `tests:` 不是 `cases:`
2. `cmd: 'AT+MIPCFG=\"cid\",0,1'` — strip 先 `'` 再 `"`
3. `status_in: ["OK"]` — 带方括号，判断用 `in`

## 新增 Bug (v9 迭代)

### MIPRD/MIPSACK/MIPMODE/MIPCLOSE on idle socket → OK (应为 ERROR)
未连接的 socket 执行这些命令返回 OK 而非 ERROR，手册预期应为错误响应。

### MIPCFG rcvbuf 设置 → ERROR
`AT+MIPCFG="rcvbuf",0,4096` 返回 ERROR，手册说范围 1460-65535。

### MIPTKA set on already-connected → CME ERROR:552
已连接 socket 再次设置 MIPTKA 返回 552 (already connected)。

### AT 解析器卡死
模组 crash 后可能进入回显但不执行状态（AT→回显 AT，无 OK）。需要彻底断电恢复。

## 覆盖率未覆盖区域分析 (mode=0, 159/462)

**已覆盖**: MIPCFG 全 key set/query/边界, MIPTKA test, MIPSTATE query, MIPSEND data mode, MIPRD, MIPSACK, MIPOPEN TCP, SSL config, autofree, error paths

**未覆盖 (需 mode=1/2 或 crash 路径)**:
- cache_stream 读取 (__cm_tcpip_cache_output)
- cache_package 读取 (__cm_tcpip_packet_output)
- MIPMODE 切换路径
- MIPCLOSE 正常/立即/abort 关闭
- Worker 线程 CM_TCPIP_CLOSE_IND
- Datamode 回调 (__cm_tcpip_send_datamode_cb)
- 自动发送 (auto_send timer)

## Echo Server

- 地址: 8.137.154.246:9500 (TCP) / 9501 (UDP)
- SSH: root / OneMo@2024
- 脚本: /tmp/echo_server.py (threading, TCP+UDP)
- 重启: `kill $(cat /tmp/echo_server.pid 2>/dev/null); kill <pid> 2>/dev/null; nohup python3 /tmp/echo_server.py > /tmp/echo_server.log 2>&1 &`
- 端口 7777/9000 已被 WorkerMan 占用
