# Ping 模块覆盖率测试报告

## 概述

从零开始完成 Ping 模块（AT+MPING）的覆盖率测试，完整走完 手册建模→插桩→编译→烧录→测试→报告 全流程。

**目标**：语句覆盖率 70%，分支覆盖率 50%
**实际**：语句覆盖率 91%，分支覆盖率 86%
**结论**：目标达成 ✅

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| 固件版本 | 3.1.0.2606231027_release |
| 源文件 | cm_atcmd_ping.c (191 行) |
| 桩数 | 27 (12 stmt + 15 branch) |

## 流程回顾

### 1. 手册建模

从 `TCP_IP用户手册.pdf` 第 57-59 页提取 AT+MPING 命令：
- 测试命令：`AT+MPING=?`
- 设置命令：`AT+MPING=<host>[,<timeout>[,<ping_num>[,<packet_len>[,<cid>]]]]`
- 参数：host (1-255字节), timeout (1-60), ping_num (1-65535), packet_len (1-1400), cid (1-15)
- URC：`+MPING: <result>,<ip>,<packet_len>,<time>,<ttl>`
- 统计：`+MPING: "statistics",<sent>,<lost>,<rtt_min>,<rtt_max>,<rtt_avg>`

输出：`module_model.ping.yaml`

### 2. 插桩

对 `cm_atcmd_ping.c` 进行插桩：
- 12 个语句桩 (ID 0-11)
- 15 个分支桩 (ID 30-44)
- 总计 27 个桩

输出：`coverage_map.ping.json`

### 3. 编译

- 清理缓存：删除 `.o`、`.d`、`.pp`、`pack_c.via`
- 增量编译：`ML307R.bat DC`
- 产物：`ML307R-DC-MBRH0S01_3.1.0.2606231027_release.zip`

### 4. 烧录

- 发送 `AT+MFORCEDL` 进入下载模式
- 执行 `adownload.exe -q -a -u -s 115200 -r <firmware.zip>`
- 物理拔插 USB 恢复 AT 口
- 验证：`AT` → OK，`AT+MSWVER` → 3.1.0.2606231027_release

### 5. 测试执行

15 个测试用例：

| Case | 新增桩 | 说明 |
|------|--------|------|
| test_cmd | +4 | 测试命令 AT+MPING=? |
| ping_basic | +18 | 基本 ping 8.8.8.8 |
| ping_single | +0 | 单次 ping |
| ping_multiple | +0 | 多次 ping |
| timeout_min | +0 | timeout 最小值 |
| timeout_max | +0 | timeout 最大值 |
| packet_len_min | +0 | packet_len 最小值 |
| packet_len_max | +0 | packet_len 最大值 |
| invalid_host | +1 | 无效主机名 |
| empty_host | +0 | 空主机名 |
| timeout_below_min | +0 | timeout 越界 |
| timeout_above_max | +0 | timeout 越界 |
| packet_len_below_min | +0 | packet_len 越界 |
| packet_len_above_max | +0 | packet_len 越界 |
| get_cmd | +1 | GET 命令（不支持） |

### 6. 覆盖率分析

**最终覆盖率**：91%/86% (24/27)

**未覆盖桩** (3 个)：
- 需要查看 `coverage_map.ping.json` 中 ID 对应的函数和行号

## 关键发现

1. **第一次编译后 PING 覆盖率未生效**：`AT+COVERAGE?` 返回中没有 PING 模块
   - 原因：`cm_atcmd_extern.c` 中没有 Ping 模块的 extern 声明和 sprintf 输出
   - 解决：修改 `cm_atcmd_extern.c` 添加 Ping 模块的覆盖率报告

2. **覆盖率提升快**：前两个 case (test_cmd + ping_basic) 就贡献了 22 桩 (81%)
   - 说明 Ping 模块逻辑简单，主要路径在基本 ping 流程中

3. **边界值测试未新增覆盖**：timeout/packet_len 的边界值测试没有新增桩
   - 说明这些参数的解析逻辑已经通过基本 ping 覆盖

4. **错误场景有新增**：invalid_host 和 get_cmd 各贡献 1 桩
   - 说明错误处理路径是独立的代码路径

## 产出文件

```
/Volumes/DevDrive/projects/at_knowledge_base/modules/ping/
├── module_model.ping.yaml          # 模块模型
├── coverage_map.ping.json          # 桩映射
├── cm_atcmd_ping.c                 # 原始源码
├── cm_atcmd_ping_instrumented.c    # 插桩后源码
└── runs/v1/
    ├── run_result.json             # 测试结果
    ├── at_execution_log.txt        # AT 日志
    └── report.md                   # 报告
```

## 后续方向

1. **继续提升覆盖率**：剩余 3 个桩可能在错误处理的深层路径
2. **添加更多负向用例**：如 cid 越界、host 超长等
3. **与其他模块对比**：Ping 模块 91%/86% 已很高，可与其他模块对比

## 总结

Ping 模块覆盖率测试完整流程验证成功：
- 从 PDF 手册到测试报告的端到端流程
- 插桩、编译、烧录、测试、分析全链路
- 目标覆盖率达成（91% > 70%, 86% > 50%）

此流程可复用于其他模块（HTTP、FTP、SSL 等）。
