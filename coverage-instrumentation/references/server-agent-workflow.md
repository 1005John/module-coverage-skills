# 中心服务器 Agent 开发流程（module_coverage_agent）

## 架构概览

```
服务器 (192.168.242.120)          测试电脑 (172.20.162.21)
┌─────────────────────┐          ┌─────────────────────┐
│ 仓库轮询 (poll_repo.py) │          │ 产物拉取             │
│ 变更分析 (change_analysis.py)│    │ 固件烧录 (adownload.exe)│
│ 插桩 (instrument.py)      │ ──→   │ AT 测试执行           │
│ cm_atcmd_extern.c 更新    │       │ 覆盖率采集            │
│ 编译 (ML307R.bat DC)      │       │ 分析迭代              │
│ 打包 (ML302A_package.bat) │       │ 报告生成              │
│ 飞书通知                   │       │                      │
└─────────────────────┘          └─────────────────────┘
```

## 服务器产物目录

```
module_coverage_agent/
├── config/config.yaml          # 仓库配置
├── scripts/
│   ├── poll_repo.py            # 仓库轮询
│   ├── change_analysis.py      # 变更分析
│   ├── instrument.py           # 插桩脚本（FR-004）
│   ├── update_extern.py        # cm_atcmd_extern.c 更新（FR-005）
│   ├── package_firmware.py     # 固件打包（仅用于 build_info，不用干烧录）
│   └── tag_parser.py           # 标签解析
├── repos/
│   ├── ml302a_std              # 标准仓库
│   └── ml302a_dev_asr_144      # 开发分支仓库
├── output/
│   └── FINAL/                  # 最终固件产物
└── logs/
```

## 测试电脑操作流程

### 1. 拉取产物

从服务器拉取 SDK 原生 release ZIP（不是 package_firmware.py 创建的 ZIP）：
```bash
# 服务器上 release ZIP 路径
C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK\target\ML307C-DC-CN-MBRH1S00\*_release.zip
```

通过 Mac 中转：
```bash
sshpass -p '123' scp Lenovo@192.168.242.120:'<path>' /tmp/
scp /tmp/<file> 52467@172.20.162.21:D:/module_coverage_test/
```

### 2. 烧录固件

```python
import subprocess, serial, time, serial.tools.list_ports

TOOL = r'D:\software\aboot-tools-2023.04.03\...\adownload.exe'
ARTIFACT = r'D:\module_coverage_test\<release>.zip'

# 进入下载模式
# AT+MFORCEDL → 等待 COM15 (ASR Serial Download Device)

# 烧录
p = subprocess.Popen([TOOL, '-q', '-a', '-u', '-s', '115200', '-r', ARTIFACT])
# 等待 "aboot download engine stopped successfully"
```

**关键**：烧录完成后需要 taskkill adownload.exe，否则端口被锁。

### 3. 测试 AT+COVERAGE?

```python
import serial
s = serial.Serial('COM16', 115200, timeout=3)
s.write(b'AT+COVERAGE?\r\n')
time.sleep(2)
print(s.read(4096).decode())
# 期望: +COVERAGE: PWM(x%,x%,n/30) ALL(x%,x%,n/30)
```

## SSH 连接信息

| 主机 | 用户 | 密码 | 用途 |
|------|------|------|------|
| 192.168.242.120 | Lenovo | 123 | 编译服务器 |
| 172.20.162.21 | 52467 | (无密码) | 测试电脑 |

## 关键 Pitfall

1. **烧录用 SDK 原生 release ZIP**，不用 package_firmware.py 创建的 ZIP
2. **烧录后必须 taskkill adownload.exe**，否则 COM 端口被锁
3. **测试电脑 COM 口可能变化** — 模块断电重连后 COM16 可能变为其他端口
4. **SSH 命令超时** — 烧录等长时间操作用 background=true + notify_on_complete
5. **Mac 中转传输** — 两台 Windows 之间通过 Mac scp 中转（都可从 Mac SSH 访问）
