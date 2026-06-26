# Ping 模块覆盖率测试完整 Walkthrough

## 概述

Ping 模块（AT+MPING）是验证端到端流程的理想选择：
- 源码仅 191 行（cm_atcmd_ping.c）
- 命令简单：`AT+MPING=<host>[,<timeout>[,<ping_num>[,<packet_len>[,<cid>]]]]`
- 不需要特殊硬件，只需网络连接
- 无状态依赖（不需要先建立连接）

## 最终成果

- 桩数：27（12 stmt + 15 branch）
- 覆盖率：91%/86% (24/27)
- 用例数：15
- 目标达成：70%/50% ✅

## 完整流程

### Step 1: 手册建模

**输入**：`/Volumes/DevDrive/test_report_ref/TCP_IP用户手册.pdf` 第 57-59 页

**提取内容**：
- 测试命令：`AT+MPING=?` → `+MPING: ,(1-60),(1-65535),(1-1400),(1-15)`
- 设置命令：`AT+MPING=<host>[,<timeout>[,<ping_num>[,<packet_len>[,<cid>]]]]`
- 参数范围：host(1-255字节), timeout(1-60), ping_num(1-65535), packet_len(1-1400), cid(1-15)
- URC 单包：`+MPING: <result>,<ip>,<packet_len>,<time>,<ttl>`
- URC 统计：`+MPING: "statistics",<sent>,<lost>,<rtt_min>,<rtt_max>,<rtt_avg>`
- result 值：0=成功, 1=DNS失败, 2=DNS超时, 3=响应错误, 4=响应超时, 5=其他错误

**输出**：`modules/ping/module_model.ping.yaml`

### Step 2: 插桩

**输入**：`cm_atcmd_ping.c` (191 行)

**插桩位置**：
- 函数入口（`_CMIOT_NetPingRspFunc` 和 `cmMPING`）
- switch case 入口（PING_ONCE, PING_TOTAL, PING_ERROR, GET_CMD, SET_CMD, TEST_CMD, default）
- 参数解析前（host, timeout, ping_num, packet_len, cid）
- 关键调用前（getExtString, getExtValue, cm_ping_handle_mping）
- 错误分支（getExtString 失败, hostlen 越界, 参数解析失败, cm_ping_handle_mping 失败）

**桩 ID 分配**：
- stmt: 0-11（12 个）
- branch: 30-44（15 个）

**输出**：`modules/ping/coverage_map.ping.json`

### Step 3: 修改 cm_atcmd_extern.c（关键！）

**必须做**，否则 `AT+COVERAGE?` 不显示 PING 模块。

**修改内容**：

1. extern 声明（约 40-55 行）：
```c
extern volatile unsigned int cov_ping_stmt_hits;
extern volatile unsigned int cov_ping_branch_hits;
```

2. GET_CMD handler 变量：
```c
unsigned long _ping_stmt = cov_ping_stmt_hits;
unsigned long _ping_branch = cov_ping_branch_hits;
unsigned long _ping_total = 12 + 15;
_all_stmt += ... + _ping_stmt;
_all_branch += ... + _ping_branch;
_all_total += ... + _ping_total;
```

3. sprintf 格式：
```c
PING(%lu%%,%lu%%,%lu/%lu)
```
参数：`(_ping_total > 0 ? (_ping_stmt * 100) / 12 : 0), (_ping_total > 0 ? (_ping_branch * 100) / 15 : 0), _ping_stmt + _ping_branch, _ping_total`

**编码**：用 `latin-1` 读写，不用 `utf-8` 或 `gbk`。

**验证**：烧录后 `AT+COVERAGE?` 应显示 `PING(0%,0%,0/27)`。

### Step 4: 编译

```bash
# 清理缓存
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_ping.*"
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_extern.*"
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\pack_c.via"

# 增量编译
ssh 52467@172.20.162.21 "cd /d D:\\ML307R\\SDK && cmd /c ML307R.bat DC"
```

**期望输出**：`ML307R-DC-MBRH0S01_3.1.0.XXXXXXXX_release.zip`

### Step 5: 烧录

```bash
# 进入下载模式
ssh 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT+MFORCEDL\\r\\n'); import time; time.sleep(2); s.close()\""

# 烧录
ssh 52467@172.20.162.21 "adownload.exe -q -a -u -s 115200 -r <firmware.zip>"

# 物理拔插 USB

# 验证
ssh 52467@172.20.162.21 "python -c \"import serial, time; s=serial.Serial('COM16', 115200, timeout=2); s.write(b'AT\\r\\n'); time.sleep(1); print(s.read_all()); s.close()\""
```

### Step 6: 测试执行

15 个用例覆盖：
- 正向：test_cmd (+4), ping_basic (+18)
- 参数变体：ping_single, ping_multiple, timeout_min/max, packet_len_min/max
- 负向：invalid_host (+1), empty_host, timeout/packet_len 越界
- GET 命令：get_cmd (+1)

**高收益 case**：
- `ping_basic` (+18)：一次 ping 覆盖了回调函数的 3 个分支（PING_ONCE, PING_TOTAL, PING_ERROR）和大部分 SET_CMD 路径
- `test_cmd` (+4)：覆盖 TEST_CMD 分支和函数入口

### Step 7: 结果

| 指标 | 目标 | 实际 |
|------|------|------|
| 语句覆盖率 | 70% | 91% |
| 分支覆盖率 | 50% | 86% |
| 桩数 | - | 27 |
| 用例数 | - | 15 |

## 关键教训

1. **cm_atcmd_extern.c 必须修改**：这是最容易遗漏的步骤。不修改的话，`AT+COVERAGE?` 不显示新模块，所有覆盖率都是 0。
2. **编码用 latin-1**：cm_atcmd_extern.c 在 Windows 上可能是 GBK 编码，Python 脚本用 `latin-1` 最安全。
3. **Ping 模块覆盖率提升快**：前两个 case 就贡献 22 桩 (81%)，因为模块逻辑简单。
4. **边界值测试未新增覆盖**：参数解析逻辑已通过基本 ping 覆盖，边界值走的是同一段代码。
5. **错误场景有独立路径**：invalid_host 和 get_cmd 各贡献 1 桩，说明错误处理是独立的代码路径。
