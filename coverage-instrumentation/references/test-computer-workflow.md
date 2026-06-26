# 测试电脑工作流（2026-06-25 PWM 实战）

## 架构

```
编译服务器 (192.168.242.120)  ←→  Mac mini (协调)  ←→  测试电脑 (172.20.162.21)
   - 源码监控                    - SSH 调度           - COM16 串口
   - 插桩                        - 文件中转           - 烧录 (adownload.exe)
   - 编译                        - 结果收集           - AT 测试执行
   - 打包                                                       - 覆盖率采集
```

## 测试电脑环境

- Windows 11, SSH 登录: `52467@172.20.162.21`
- Python 3.11.6 + pyserial 3.5
- 串口: COM16 (ASR Modem Device, 115200 baud)
- 烧录工具: `D:\software\aboot-tools-2023.04.03\...\adownload.exe`
- 工作目录: `D:\module_coverage_test\`

## 文件传输流程

```bash
# 1. 从编译服务器拉到 Mac
sshpass -p '123' scp Lenovo@192.168.242.120:'path/to/release.zip' /tmp/artifacts/

# 2. 从 Mac 推到测试电脑
scp /tmp/artifacts/release.zip 52467@172.20.162.21:D:/module_coverage_test/
```

## 烧录流程

```python
import subprocess, time, serial, serial.tools.list_ports

TOOL = r'D:\software\aboot-tools-2023.04.03\...\adownload.exe'
ARTIFACT = r'D:\module_coverage_test\release.zip'

# 进入下载模式
def at(cmd, wait=1.5, timeout=3.0):
    with serial.Serial('COM16', 115200, timeout=timeout) as s:
        s.reset_input_buffer()
        s.write((cmd+'\r\n').encode())
        time.sleep(wait)
        return s.read(8192).decode('utf-8', errors='replace').strip()

if not any('ASR Serial Download Device' in p.description
           for p in serial.tools.list_ports.comports()):
    try: at('AT+MFORCEDL', wait=2.0, timeout=1.0)
    except: pass
    time.sleep(8)

# 烧录
p = subprocess.Popen([TOOL, '-q', '-a', '-u', '-s', '115200', '-r', ARTIFACT],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
# ... 等待 "aboot download engine stopped successfully"
subprocess.run(['taskkill','/f','/im','adownload.exe'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 等待重启
time.sleep(15)
for i in range(20):
    try:
        if 'OK' in at('AT'): break
    except: pass
    time.sleep(5)
```

## 覆盖率测试流程

```python
# 1. 初始状态
print(at('AT+COVERAGE?'))  # 应显示 0/N

# 2. 清零
print(at('AT+COVERAGE=1'))  # 应返回 OK

# 3. 执行 AT 命令
print(at('AT+MPWMCFG?'))
print(at('AT+MPWMCTRL=1,1'))

# 4. 检查覆盖率
print(at('AT+COVERAGE?'))  # 命中数应 > 0
```

## 常见问题

1. **COM16 被锁定** — taskkill /F /IM adownload.exe 和 python.exe
2. **模块卡在下载模式** — 拔插 USB 重置
3. **SSH 命令超时** — 用 `timeout /t N >nul` 代替 Python time.sleep
4. **串口无响应** — 检查模块是否在下载模式（COM15 ASR Serial Download Device）
5. **烧录后覆盖率仍为 0** — 检查 .axf 是否包含 cm_cov_hit 符号（服务器端问题）
