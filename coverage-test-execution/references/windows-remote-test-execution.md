# Windows 测试机远程执行与卡点诊断

## When to Use
- 通过 SSH 在 Windows 测试机上运行 AT 覆盖率脚本。
- `cmd /c cd /d ... && python ...`、inline PowerShell 或重定向表现异常。
- 脚本没有生成结果，日志停在启动早期，需要定位是启动方式、串口还是脚本逻辑。

## 推荐启动方式
优先写一个 `.ps1` 文件上传到 Windows，再用 `powershell -File` 执行；不要把复杂 PowerShell/cmd 重定向塞进 SSH inline 命令。

示例 `C:\Users\52467\run_http_v6.ps1`：

```powershell
$ErrorActionPreference = 'Stop'
$workdir = 'D:\ML307R\SDK'
$outLog = Join-Path $workdir 'http_v6_stdout.log'
$errLog = Join-Path $workdir 'http_v6_stderr.log'
$pidFile = Join-Path $workdir 'http_v6_pid.txt'
Set-Location $workdir
Remove-Item -ErrorAction SilentlyContinue 'http_coverage_v6.json','http_assertion_result_v6.json','http_bug_candidates_v6.json','http_v6_stdout.log','http_v6_stderr.log','http_v6_pid.txt'
$p = Start-Process -FilePath 'python' -ArgumentList @('-u','run_http_coverage_v6.py') -WorkingDirectory $workdir -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
$p.Id | Out-File -Encoding ascii $pidFile
Write-Output "STARTED PID=$($p.Id)"
```

执行：

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\52467\run_http_v6.ps1
```

## 卡点诊断顺序
1. 查 SSH 连通性：优先测试 `172.20.162.21:22`，当前可用用户为 `52467`；旧的 `172.20.162.21:52467` 可能已不通。
2. 查进程：`tasklist /FI "PID eq <pid>" /V`。
3. 查日志：`type D:\ML307R\SDK\http_v6_stdout.log` 和 `http_v6_stderr.log`。
4. 枚举串口：`python -m serial.tools.list_ports -v`，优先识别 `ASR Modem Device (COM16)` / `USB VID:PID=2ECC:3012`。
5. 若日志停在串口前后，只探测 `COM16`：运行 `scripts/probe_com16.py` 或等价脚本，期望输出包含 `b'\r\nOK\r\n'`。
6. 若探针正常，问题在测试脚本或启动方式，不是串口占用。
7. 如果全量脚本太长，先跑 short runner，只执行新增阶段，验证用例和断言输出。

## COM16 探针最小脚本

```python
import serial, time
s = serial.Serial('COM16', 115200, timeout=1)
time.sleep(0.5)
s.write(b'AT\r\n')
time.sleep(0.5)
print(repr(s.read(s.in_waiting or 1)))
s.close()
```

期望输出包含 `b'\r\nOK\r\n'`。

## Pitfalls
- SSH inline 命令里的 `&`, `&&`, `$var`, `>` 很容易被本地 shell、cmd、PowerShell 多层解释，导致工作目录回到 `C:\Users\<user>`。
- Windows 测试机上有多个蓝牙虚拟串口（如 `BTHENUM` 的 COM3/4/5...），不要逐个盲开；COM3 等端口可能打开卡到超时。先用 `python -m serial.tools.list_ports -v` 找 `ASR Modem Device (COM16)` / `USB VID:PID=2ECC:3012`，再只探测 `COM16`。
- `Start-Process` 后台运行时，进程和日志状态要以 PID 文件和 stdout/stderr 文件为准，不要只看 SSH 返回码。
- 日志只停在 `COM16 OPENED` 时，先用 COM 探针验证串口；不要直接认定串口坏。
- 用户要求“继续/不要问我”时，长流程应持续推进，只有明确进展、阻塞或需要决策时再汇报。
