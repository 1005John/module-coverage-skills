# Ping/PWM 模块端到端流程实例

## 流程概览

两个小模块（Ping 191行/PWM 308行）完整走完覆盖率测试流程，均在单轮迭代中达到高覆盖率。

## 步骤 1: 手册建模

**Ping**: 从 `TCP_IP用户手册.pdf` 第 57-59 页提取 AT+MPING 命令
**PWM**: 从 `4gseries扩展.pdf` 第 74-75 页提取 AT+MPWMCFG/AT+MPWMDATA/AT+MPWMCTRL 命令

输出: `module_model.<module>.yaml`

## 步骤 2: 插桩

对模块源码添加 COV_STMT/COV_BRANCH_T/COV_BRANCH_F 宏。
同时修改 `cm_atcmd_extern.c` 添加模块的覆盖率报告。

**关键**: 必须同时修改两个文件！

输出: 插桩后 .c + `coverage_map.<module>.json`

## 步骤 3: 编译

```bash
# 清理缓存
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_<module>.*"
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\cm_atcmd_extern.*"
ssh 52467@172.20.162.21 "del /q D:\\ML307R\\SDK\\tavor\\Arbel\\obj_PMD2NONE\\obj_onemo_onemo\\obj_onemo_at\\pack_c.via"

# 编译
ssh 52467@172.20.162.21 "cd /d D:\\ML307R\\SDK && cmd /c ML307R.bat DC"
```

输出: `ML307R-DC-MBRH0S01_*_release.zip`

## 步骤 4: 烧录

```bash
# 进入下载模式
ssh 52467@172.20.162.21 "python -c \"import serial; s=serial.Serial('COM16',115200); s.write(b'AT+MFORCEDL\\r\\n'); import time; time.sleep(2); s.close()\""

# 烧录
ssh 52467@172.20.162.21 "adownload.exe -q -a -u -s 115200 -r <firmware.zip>"

# 验证
ssh 52467@172.20.162.21 "python -c \"import serial, time; s=serial.Serial('COM16', 115200, timeout=2); s.write(b'AT+COVERAGE?\\r\\n'); time.sleep(1); print(s.read_all()); s.close()\""
```

期望: `AT+COVERAGE?` 返回中包含新模块

## 步骤 5: 测试执行

```bash
# 上传测试脚本和 coverage_map
scp /tmp/run_<module>_v1.py 52467@172.20.162.21:D:/ML307R/at_knowledge_base/
scp coverage_map.<module>.json 52467@172.20.162.21:D:/ML307R/at_knowledge_base/

# 执行
ssh 52467@172.20.162.21 "cd /d D:\\ML307R\\at_knowledge_base && python -u run_<module>_v1.py"
```

输出: `D:\ML307R\at_knowledge_base\<module>_runs\v1\`

## 步骤 6: 收集结果

```bash
scp 52467@172.20.162.21:D:/ML307R/at_knowledge_base/<module>_runs/v1/* /local/path/
```

## 结果对比

| 模块 | 桩数 | stmt% | branch% | 用例数 | 迭代 |
|------|------|-------|---------|--------|------|
| Ping | 27 | 91% | 86% | 15 | 1 |
| PWM | 66 | 62% | 82% | 34 | 1 |
| MQTT | 635 | 51% | 22% | 91+ | 9 |
| TCP | 462 | 38% | 26% | - | 8 |

**结论**: 小模块（<100桩）可在单轮迭代中达到 60-90% 覆盖率。
大模块（>400桩）需要多轮迭代，每轮针对性补充用例。
