# 测试机烧录与验证流程

## 测试机环境

- 主机：172.20.162.21（用户名 52467，无密码）
- Python 3.11.6 + pyserial 3.5
- AT 串口：COM16 (115200 baud)
- 下载口：COM15 (ASR Serial Download Device)
- 烧录工具：`D:\software\aboot-tools-2023.04.03\aboot-tools-2023.04.03\aboot-tools-2023.04.03-win-x86\aboot-tools-2023.04.03-win-x86\adownload.exe`
- 工作目录：`D:\module_coverage_test\`

## 产物传输

```bash
# 服务器 → Mac
sshpass -p '123' scp Lenovo@192.168.242.120:'C:/Users/Lenovo/Desktop/module_coverage_agent/output/FINAL/*.zip' /tmp/artifacts/
sshpass -p '123' scp Lenovo@192.168.242.120:'C:/Users/Lenovo/Desktop/module_coverage_agent/output/PWM_FR004_final/coverage_map.*.json' /tmp/artifacts/
sshpass -p '123' scp Lenovo@192.168.242.120:'C:/Users/Lenovo/Desktop/module_coverage_agent/output/PWM_FR004_final/stub_id_alloc.yaml' /tmp/artifacts/

# Mac → 测试机
scp /tmp/artifacts/* 52467@172.20.162.21:D:/module_coverage_test/
```

## 烧录流程

```python
import serial, time, subprocess, serial.tools.list_ports

TOOL = r'D:\software\aboot-tools-2023.04.03\...\adownload.exe'
ARTIFACT = r'D:\module_coverage_test\<firmware>.zip'
AT_PORT = 'COM16'

# 1. 进入下载模式
with serial.Serial(AT_PORT, 115200, timeout=2) as s:
    s.write(b'AT+MFORCEDL\r\n')
    time.sleep(2)

# 2. 等待 COM15 出现
time.sleep(6)
# 检查 serial.tools.list_ports.comports() 中有 'ASR Serial Download Device'

# 3. 烧录
cmd = [TOOL, '-q', '-a', '-u', '-s', '115200', '-r', ARTIFACT]
# 等待 'aboot download engine stopped successfully'

# 4. 等待重启
time.sleep(10)

# 5. 验证
with serial.Serial(AT_PORT, 115200, timeout=3) as s:
    s.write(b'AT+MSWVER\r\n')  # 检查版本
    s.write(b'AT+COVERAGE?\r\n')  # 检查覆盖率命令是否可用
```

## 验证清单

- [ ] 烧录成功（aboot download engine stopped successfully）
- [ ] 模块重启后 AT 响应 OK
- [ ] AT+MSWVER 显示新版本号
- [ ] AT+COVERAGE? 返回模块覆盖率（非 ERROR）
- [ ] AT+COVERAGE=1 能清零计数器

## 常见问题

- COM16 打不开：模块可能未连接或端口被占用
- AT+COVERAGE? 返回 ERROR：固件编译时未更新 cm_atcmd_extern.c
- 烧录后模块不响应：等待时间不够，重试 AT 命令最多 20 次（每次间隔 5s）
