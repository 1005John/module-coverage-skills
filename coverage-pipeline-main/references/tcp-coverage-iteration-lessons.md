# TCP 覆盖率迭代经验 (2026-06-22)

## 迭代路径

| 轮次 | 覆盖率 | 命中桩 | 新增 | 关键操作 |
|------|--------|--------|------|----------|
| v1 (无网络) | 43%,32% | 183/462 | +126 | 纯 AT 命令，YAML 解析修复后 |
| v4 (有 echo) | 45%,31% | 186/462 | +3 | MIPOPEN TCP + MIPSTATE |
| v6 (多模式) | 35%,22% | 142/462 | +136 | mode=0 全量，MIPCLOSE crash 前 |
| v7 (不重置) | 41%,30% | 172/462 | +30 | MIPCFG query 变体 |
| v8 (单连接) | 38%,26% | 159/462 | +159 | mode=0 完整数据交换，不关闭 |
| v9 mode=0 | 38%,26% | 159/462 | +159 | 最终 mode=0 基线 |

## 核心教训

### 1. Crash Bug 是最大阻碍
MIPCLOSE/MIPMODE/MIPOPEN mode 冲突导致模组 crash，覆盖率归零。
**解法**: 单连接、不关闭、每次只测一个 access_mode、重启切换。

### 2. 数据模式是 MIPSEND 唯一方式
内联格式 `AT+MIPSEND=0,5,"HELLO"` 返回 CME ERROR:50。
必须: `AT+MIPSEND=0,5` → `>` → `HELLO`

### 3. 多行响应需要循环读取
MIPSTATE 返回 6 行 + OK，MIPCFG query 返回多行。固定 sleep 会漏。
用 while 循环读取直到超时或收到 OK/ERROR。

### 4. 覆盖率天花板
mode=0 纯 AT 命令测试天花板约 38% (159/462)。
未覆盖区域: cache_stream/package 读取、MIPCLOSE、MIPMODE 切换、worker 线程消息处理。
要突破需要: (1) 修复 crash bug 后测 mode=1/2, (2) API 层插桩。

### 5. Echo Server 必须
TCP 测试必须有可达的 echo server。模组 PDP 激活后可直连公网 TCP 服务。
UDP echo 可用同服务器不同端口。

## 产出文件清单

| 文件 | 路径 |
|------|------|
| 插桩脚本 | /tmp/tcp_coverage/instrument_tcp_v3.py |
| 插桩源码 | /tmp/tcp_coverage/cm_atcmd_tcpip_instrumented.c |
| 桩映射 | /tmp/tcp_coverage/coverage_map.json |
| 手册预期 | /tmp/tcp_coverage/manual_expectations.tcpip.json |
| 测试用例 | /tmp/tcp_coverage/generated_tests.yaml |
| 模块配置 | /tmp/tcp_coverage/module_config.tcpip_at.yaml |
| 执行脚本 v9 | /tmp/tcp_coverage/run_tcp_v9.py |
| 测试结果 | D:\ML307R\SDK\tcp_coverage_results\ |
| 报告 | /tmp/tcp_coverage/run_summary.md |
