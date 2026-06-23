# TCP 模块 (cm_atcmd_tcpip.c) 测试笔记

## AT 命令清单 (9 个)

| 命令 | 函数 | 用途 |
|------|------|------|
| AT+MIPCFG | cmMIPCFG | 配置 cid/encoding/timeout/sndbuf/rcvbuf/autofree/ackmode/ssl |
| AT+MIPTKA | cmMIPTKA | TCP 保活参数 |
| AT+MIPOPEN | cmMIPOPEN | 打开 TCP/UDP 连接 |
| AT+MIPCLOSE | cmMIPCLOSE | 关闭连接 |
| AT+MIPSEND | cmMIPSEND | 发送数据（数据模式） |
| AT+MIPRD | cmMIPRD | 读取缓存数据 |
| AT+MIPMODE | cmMIPMODE | 访问模式 (0=auto/1=cache_stream/2=cache_package/3=transparent) |
| AT+MIPSTATE | cmMIPSTATE | 查询连接状态 |
| AT+MIPSACK | cmMIPSACK | 查询发送确认统计 |

## 关键行为发现

### MIPSEND 必须用数据模式
```python
# 错误 — CME ERROR: 50
s.write(b'AT+MIPSEND=0,5,"HELLO"\r\n')

# 正确 — 数据模式
s.write(b'AT+MIPSEND=0,5\r\n')
time.sleep(1.5)
# 等待 > 提示
if '>' in s.read(s.in_waiting).decode():
    s.write(b'HELLO')  # 不加 \r\n，精确 5 字节
    time.sleep(5)
    # 期望: +MIPSEND: 0,5 + OK + +MIPURC: "ack",0,5 + +MIPURC: "rtcp",0,5,<hex>
```

### MIPOPEN 需要网络
```python
# 连接 echo server
s.write(b'AT+MIPOPEN=0,"TCP","8.137.154.246",9500,30,0\r\n')
# 等待 8-10 秒
# 期望: OK + +MIPOPEN: 0,0 (成功) 或 +MIPOPEN: 0,-1 (失败)
```

### MIPSTATE 返回多行
```python
# AT+MIPSTATE (查询所有) 返回 6 行 + OK
# 必须用循环读取，不能固定 sleep
def at_loop(ser, cmd, timeout=8):
    ser.reset_input_buffer()
    ser.write((cmd + '\r\n').encode())
    r = ''
    end = time.time() + timeout
    while time.time() < end:
        n = ser.in_waiting
        if n > 0:
            r += ser.read(n).decode('utf-8', errors='replace')
            if 'OK' in r or 'ERROR' in r:
                break
        time.sleep(0.2)
    return r
```

### MIPTKA 设置时机
- 必须在 INITIAL 状态（未连接）时设置
- 已连接时设置返回 CME ERROR: 552

### MIPCFG rcvbuf 在 ML307R 上无效
- TCP 接收缓存为滑动窗口大小（默认 64240），配置无效
- UDP 配置有效，范围 1460-65535

### MIPCLOSE 模式
- mode=0: 优雅关闭
- mode=1: 立即关闭
- mode=2/3: 其他关闭方式
- 在 CONNECTING 状态关闭返回 CM_PROGRESS_ERROR

## Echo Server

- 地址: 8.137.154.246
- TCP: 端口 9500
- UDP: 端口 9501
- 部署: Python threading echo server (见 /tmp/tcp_coverage/echo_server.py)
- 部署命令: `sshpass -p 'xxx' ssh root@8.137.154.246 "nohup python3 /tmp/echo_server.py > /tmp/echo_server.log 2>&1 &"`

## 覆盖率实测数据 (2026-06-22)

| 轮次 | 用例 | OK/Fail | 覆盖率 | 命中/总桩 | 说明 |
|------|------|---------|--------|-----------|------|
| v1 | 93 | 42/51 | 14%,3% | 50/462 | YAML 解析 bug，命令被截断 |
| v2 | 93 | 74/19 | 43%,32% | 183/462 | 修复解析，+echo server |
| v4 | 48 | 42/6 | 45%,31% | 186/462 | 稳定版，含 TCP+UDP 连接 |

### 未覆盖区域 (60%)
- Worker 线程 (CM_TCPIP_OPEN_IND/RECV_IND/CLOSE_IND/AUTO_SEND_IND/DATAMODE_REQ_IND)
- Datamode 回调 (__cm_tcpip_send_datamode_cb)
- 缓存输出 (__cm_tcpip_cache_output / __cm_tcpip_packet_output)
- 自动发送 (auto_send timer)
- 连接状态转换深层路径

### 潜在 Bug
- MIPRD/MIPSACK/MIPMODE/MIPCLOSE 在 idle socket 返回 OK 而非 ERROR
- MIPCFG="rcvbuf" 设置返回 ERROR（手册注释：TCP 配置无效）

## 文件位置

- 插桩脚本: /tmp/tcp_coverage/instrument_tcp_v3.py
- 测试执行器: /tmp/tcp_coverage/run_tcp_v4.py
- 桩映射: /tmp/tcp_coverage/coverage_map.json
- 手册预期: /tmp/tcp_coverage/manual_expectations.tcpip.json
- 测试用例: /tmp/tcp_coverage/generated_tests.yaml
- 模块配置: /tmp/tcp_coverage/module_config.tcpip_at.yaml
- AT 手册: /Volumes/DevDrive/test_report_ref/TCP_IP用户手册.pdf
