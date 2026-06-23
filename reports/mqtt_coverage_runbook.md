# ML307R MQTT 覆盖率测试 Runbook

## 概述

本 runbook 描述从零开始完成 MQTT AT 命令层覆盖率测试的完整流程。其他智能体可按照本 runbook 独立执行。

## 前置条件

- Windows 测试机 SSH 可达（172.20.162.21:22，用户 52467）
- AT 串口 COM16 可用（115200 baud）
- MQTT Broker 可达（8.137.154.246:1883）
- SDK 路径：D:\ML307R\SDK

## 步骤 1：插桩

### 1.1 获取源文件

```bash
# 从 Windows 测试机获取原始源文件
scp -P 22 52467@172.20.162.21:D:/ML307R/SDK/onemo/at/src/cm_atcmd_mqtt.c /tmp/
```

### 1.2 运行插桩脚本

```bash
# 使用自动插桩脚本
python3 /Volumes/DevDrive/projects/at_knowledge_base/tools/instrument_mqtt_v5.py \
    /tmp/cm_atcmd_mqtt.c \
    /tmp/cm_atcmd_mqtt_instrumented.c
```

### 1.3 上传插桩后的文件

```bash
# 上传到 Windows 测试机
scp -P 22 /tmp/cm_atcmd_mqtt_instrumented.c 52467@172.20.162.21:D:/ML307R/SDK/onemo/at/src/cm_atcmd_mqtt.c
```

### 1.4 生成 coverage_map.json

```bash
# 从插桩后的源码反扫生成 coverage_map
python3 /Volumes/DevDrive/projects/at_knowledge_base/tools/rebuild_coverage_map.py
```

**期望输出**：`coverage_map.mqtt.json`，包含 627+ 桩映射。

## 步骤 2：编译

### 2.1 清理缓存

```bash
ssh -p 22 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_mqtt.* && del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\pack_c.via"
```

### 2.2 增量编译

```bash
ssh -p 22 52467@172.20.162.21 "cd /d D:\\ML307R\\SDK && cmd /c ML307R.bat DC"
```

**期望输出**：`ML307R-DC-MBRH0S01_*_release.zip` 生成。

### 2.3 验证编译产物

```bash
ssh -p 22 52467@172.20.162.21 "dir D:\\ML307R\\SDK\\target\\ML307R-DC-MBRH0S01\\*release.zip"
```

## 步骤 3：烧录

### 3.1 发送 AT+MFORCEDL

```bash
ssh -p 22 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT+MFORCEDL\\r\\n'); import time; time.sleep(2); s.close()\""
```

### 3.2 执行 adownload

```bash
ssh -p 22 52467@172.20.162.21 "D:\\software\\aboot-tools-2023.04.03\\...\\adownload.exe -q -a -u -s 115200 -r D:\\ML307R\\SDK\\target\\ML307R-DC-MBRH0S01\\ML307R-DC-MBRH0S01_*_release.zip"
```

**期望输出**：`aboot download engine stopped successfully`

### 3.3 验证 AT 口

```bash
ssh -p 22 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT\\r\\n'); import time; time.sleep(1); print(s.read_all()); s.close()\""
```

**期望输出**：`b'\r\nOK\r\n'`

## 步骤 4：测试执行

### 4.1 上传测试脚本

```bash
scp -P 22 /tmp/run_mqtt_bitmap_v9.py 52467@172.20.162.21:D:/ML307R/at_knowledge_base/
```

### 4.2 执行测试

```bash
ssh -p 22 52467@172.20.162.21 "cd /d D:\\ML307R\\at_knowledge_base && python -u run_mqtt_bitmap_v9.py"
```

**期望输出**：
```
WROTE D:\ML307R\at_kb_runs\mqtt-v9-bitmap
# MQTT bitmap v9 增量分析
- final: {'stmt_percent': 51, 'branch_percent': 22, 'hit_stubs': 261, 'total_stubs': 635}
- bitmap hit: 261/627
- uncovered: 366
```

### 4.3 收集结果

```bash
scp -P 22 52467@172.20.162.21:D:/ML307R/at_kb_runs/mqtt-v9-bitmap/* /tmp/mqtt_results/
```

## 步骤 5：分析

### 5.1 查看覆盖率

```bash
cat /tmp/mqtt_results/report.md
```

### 5.2 查看未覆盖桩

```bash
python3 -c "import json; data=json.load(open('/tmp/mqtt_results/uncovered_stubs.json')); print(f'未覆盖: {len(data)} 桩')"
```

### 5.3 查看高收益 case

```bash
python3 -c "
import json
data = json.load(open('/tmp/mqtt_results/coverage_delta.json'))
for case, stubs in sorted(data['case_to_new_stub_ids'].items(), key=lambda x: -len(x[1])):
    print(f'{case}: +{len(stubs)}')
"
```

## 步骤 6：迭代

### 6.1 生成下一轮用例

根据未覆盖热点，生成新的测试用例：

```python
# 重点打 subscribe/connect/publish/datamode 路径
cases = [
    ('sub_multi_topic', 'AT+MQTTSUB=1,"t1",0,"t2",1,"t3",2'),
    ('pub_dm_qos0', 'AT+MQTTPUB=1,"test/a",0,0,0,5'),
    ('pub_dm_qos1', 'AT+MQTTPUB=1,"test/a",1,0,0,5'),
    ('pub_dm_qos2', 'AT+MQTTPUB=1,"test/a",2,0,0,5'),
    ('pubjson', 'AT+MQTTPUBJSON=1,"test/json",0,0,0,"",13,"{\\"k\\":\\"v\\"}"'),
]
```

### 6.2 执行迭代

重复步骤 4-5，直到覆盖率饱和（连续 2 轮新增为 0）。

## 产出文件

```
D:\ML307R\at_kb_runs\
├── coverage_map.mqtt.json          # 桩映射
├── mqtt-v9-bitmap\                 # 测试结果
│   ├── run_result.json             # 每条 case 的响应和增量
│   ├── coverage_delta.json         # case → stub id 映射
│   ├── uncovered_stubs.json        # 未覆盖桩列表
│   ├── report.md                   # 分析报告
│   └── at_execution_log.txt        # 完整 AT 日志
└── mqtt_coverage_loop_report.md    # 端到端报告
```

## 关键 Pitfalls

1. **DC ALL 会覆盖插桩文件** — 永远用 DC（增量）
2. **数据模式必须专门处理** — `AT+MQTTPUB=...` 返回 `>` 后必须写入 payload
3. **DNS 失败放最后** — 会破坏连接状态
4. **每 case 后采集 bitmap** — 否则无法计算增量
5. **连接管理** — 每次 case 前检查 `AT+MQTTSTATE`，断开则重新连接

## 验收标准

| 指标 | 目标值 | 当前值 |
|------|--------|--------|
| 语句覆盖率 | >= 75% | 51% |
| 分支覆盖率 | >= 55% | 22% |
| 输出格式 | JSON + MD | ✓ |
| 可复制性 | 其他 Agent 可独立继续 | ✓ |

## 后续方向

1. 继续迭代：打 subscribe/connect/publish/datamode 路径
2. 平台认证：`devinfo` 返回 CME ERROR:606，需要深入分析
3. 多 conn_id：测试 conn_id=0/2/3/4/5 的独立路径
4. datamode 回调：payload 超短/准确/超长、ESC 干扰
