# TCP 模块覆盖率会话记录 (2026-06-22)

## 概要
对 ML307R TCP/IP 模块 (cm_atcmd_tcpip.c) 进行端到端覆盖率测试。

## 插桩
- AT 层: 300 语句桩 (500-799) + 162 分支桩 (2500-2661) = 462 总桩
- 脚本: instrument_tcp_v3.py (含三大陷阱检测)
- cm_atcmd_extern.c 新增 TCP 报告行，output buffer 扩大到 384

## 编译
- ReliableData.bin 缺失但编译本身成功
- 第三次编译后 release packaging 自行恢复
- 清理必须 .o + .d + .pp + pack_c.via 全删

## 烧录
- adownload 路径: `D:\software\aboot-tools-2023.04.03\...\adownload.exe -q -u -a -s 115200 <zip>`
- 烧录后模块不自动重启，需物理拔插 USB (COM15→COM16)
- adownload 残留进程占用 COM 口，需 taskkill

## AT 命令格式发现
- **MIPSEND**: inline 格式 `AT+MIPSEND=0,5,"HELLO"` 返回 CME ERROR:50，必须用数据模式：`AT+MIPSEND=0,5` → 等 `>` → 发数据
- **MIPCFG**: 双引号和无引号 key 都可以，单引号不行
- **MIPSTATE**: 查询所有返回 6 行连接状态，serial read 必须循环读取
- **MIPTKA get**: 无连接时返回 ERROR

## 测试结果
| 轮次 | OK | Fail | 覆盖率 | 说明 |
|------|-----|------|--------|------|
| v1 | 42 | 51 | TCP(14%,3%,50/462) | YAML 解析 bug，命令被截断 |
| v2 | 74 | 19 | TCP(43%,32%,183/462) | 修复解析后，无网络天花板 |
| v4 | 42 | 6 | TCP(45%,31%,186/462) | echo server + 数据模式 |

## Echo Server
- 地址: 8.137.154.246 (SSH root/OneMo@2024)
- TCP: 9500, UDP: 9501
- 部署: python3 /tmp/echo_server.py (threading, TCP+UDP echo)
- 端口 7777/9000 被 WorkerMan 占用

## 严重 Bug: MIPCLOSE crash
所有 MIPCLOSE 模式 (mode=0/1/2) 在 TCP 数据交换后关闭连接导致模组崩溃重启。
- 复现: MIPOPEN→MIPSEND→收到 URC→MIPCLOSE→crash, 覆盖率归零
- MIPCLOSE 在无数据连接上未测试（模组先卡死需重启）
- workaround: 不关闭连接，用完即弃或等超时
- 连续 3 次触发，100% 复现

## 未覆盖区域 (276/462 = 60%)
- Worker 线程 (__cm_tcpip_worker_thread) 消息处理
- Datamode 回调 (__cm_tcpip_send_datamode_cb)
- 自动发送 (auto_send timer)
- 缓存读取 (__cm_tcpip_cache_output / __cm_tcpip_packet_output)
- 状态转换路径

## 潜在 Bug
1. MIPRD/MIPSACK/MIPMODE/MIPCLOSE 在 idle socket 返回 OK 而非 ERROR
2. MIPCFG="rcvbuf" 设置返回 ERROR（手册说范围 1460-65535，ML307R TCP 滑动窗口配置无效）
