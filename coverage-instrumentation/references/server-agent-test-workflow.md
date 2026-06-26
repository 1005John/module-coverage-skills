# 服务器 Agent → 测试电脑 完整工作流

## 网络拓扑

```
Mac (192.168.242.xxx)  ←→  构建服务器 (192.168.242.120, Lenovo/123)
Mac (SSH)              ←→  测试电脑 (172.20.162.21, 52467)
构建服务器             ←→  测试电脑 (互通, 延迟 ~2ms)
```

## 产物传输流程

### 1. 从构建服务器拉取产物到 Mac

```bash
sshpass -p '123' scp -o StrictHostKeyChecking=no \
  Lenovo@192.168.242.120:'C:/Users/Lenovo/Desktop/module_coverage_agent/output/FINAL/<firmware>.zip' \
  /tmp/module_coverage_artifacts/

sshpass -p '123' scp -o StrictHostKeyChecking=no \
  Lenovo@192.168.242.120:'C:/Users/Lenovo/Desktop/module_coverage_agent/output/PWM_FR004_final/coverage_map.PWM.json' \
  /tmp/module_coverage_artifacts/
```

### 2. 推送到测试电脑

```bash
scp -o StrictHostKeyChecking=no \
  /tmp/module_coverage_artifacts/<firmware>.zip \
  52467@172.20.162.21:D:/module_coverage_test/
```

## 测试电脑环境

- **串口**: COM16 (ASR Modem Device, 115200 baud)
- **烧录工具**: `D:\software\aboot-tools-2023.04.03\...\adownload.exe`
- **Python**: 3.11.6 + pyserial 3.5
- **测试目录**: `D:\module_coverage_test\`

## 烧录流程

```python
import serial, serial.tools.list_ports, subprocess, time

TOOL = r'D:\software\aboot-tools-2023.04.03\...\adownload.exe'
ARTIFACT = r'D:\module_coverage_test\<firmware>.zip'
AT_PORT = 'COM16'

# 1. 进入下载模式
def has_dl():
    return any('ASR Serial Download Device' in p.description
                for p in serial.tools.list_ports.comports())

if not has_dl():
    with serial.Serial(AT_PORT, 115200, timeout=1) as s:
        s.write(b'AT+MFORCEDL\r\n')
    time.sleep(6)  # 等待进入下载模式

# 2. 等待下载端口
for _ in range(10):
    if has_dl(): break
    time.sleep(3)

# 3. 执行烧录
cmd = [TOOL, '-q', '-a', '-u', '-s', '115200', '-r', ARTIFACT]
subprocess.run(cmd, timeout=300)

# 4. 清理进程
subprocess.run(['taskkill', '/f', '/im', 'adownload.exe'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 5. 等待模块重启
time.sleep(10)
for _ in range(20):
    try:
        with serial.Serial(AT_PORT, 115200, timeout=2) as s:
            s.write(b'AT\r\n'); time.sleep(1)
            if b'OK' in s.read(1024): break
    except: pass
    time.sleep(5)
```

### 烧录关键点

- AT+MFORCEDL 后模块进入下载模式，COM16 消失，COM15 出现（ASR Serial Download Device）
- adownload.exe 使用 USB 端口 COM15 烧录
- 烧录完成后模块自动重启，COM16 恢复
- 烧录耗时约 10-15 秒

## AT+COVERAGE? 验证流程

```python
import serial, time

ser = serial.Serial('COM16', 115200, timeout=3)
ser.reset_input_buffer()

# 1. 查询初始状态
ser.write(b'AT+COVERAGE?\r\n')
time.sleep(2)
print('初始:', ser.read(4096))

# 2. 清零
ser.write(b'AT+COVERAGE=1\r\n')
time.sleep(1.5)
print('清零:', ser.read(4096))

# 3. 执行 PWM 命令
ser.write(b'AT+MPWMCTRL=1,1\r\n')
time.sleep(1.5)
print('PWM:', ser.read(4096))

# 4. 再次查询
ser.write(b'AT+COVERAGE?\r\n')
time.sleep(2)
print('执行后:', ser.read(4096))

ser.close()
```

### 期望输出

```
AT+COVERAGE? => +COVERAGE: PWM(0%,0%,0/30) ALL(0%,0%,0/30)
AT+COVERAGE=1 => OK
AT+MPWMCTRL=1,1 => OK
AT+COVERAGE? => +COVERAGE: PWM(X%,Y%,N/30) ALL(X%,Y%,N/30)  # N>0
```

## 常见问题

| 现象 | 原因 | 修复 |
|------|------|------|
| AT+COVERAGE? 返回 ERROR | AT 命令未注册或 handler 为 NULL | 检查 cm_atcmd_def.h |
| AT+COVERAGE? 返回空 | ATRESP 双重调用 | 只调用一次 ATRESP |
| AT+COVERAGE=1 返回 ERROR | SET_CMD handler 未实现 | 添加 cm_coverage_reset 逻辑 |
| 烧录后版本不变 | 未进入下载模式 | 确认 COM15 出现再烧录 |
| COM16 不存在 | 模块未连接或 USB 松动 | 检查 USB 连接 |
