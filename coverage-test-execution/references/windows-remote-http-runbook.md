# Windows 远程运行 HTTP 覆盖率脚本 Runbook

## When to Use
- 需要从 Mac/Hermes 远程运行 Windows 测试机上的 `run_http_coverage_v*.py`。
- 需要避免 SSH + `cmd /c` 的工作目录、重定向、`&` 转义问题。
- 脚本需要长时间运行，并且必须保留 stdout/stderr、PID、结果 JSON。

## 推荐启动方式

优先写入并执行 PowerShell 脚本文件，不要把复杂命令直接塞进 `ssh "cmd /c ..."`：

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

从 Mac 上传并执行：

```bash
scp run_http_v6.ps1 52467@172.20.162.21:'C:/Users/52467/run_http_v6.ps1'
ssh 52467@172.20.162.21 "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\52467\\run_http_v6.ps1"
```

## 进度检查

```cmd
type D:\ML307R\SDK\http_v6_pid.txt
tasklist /FI "PID eq <pid>" /V
dir D:\ML307R\SDK\http_v6_stdout.log D:\ML307R\SDK\http_v6_stderr.log D:\ML307R\SDK\http_coverage_v6.json D:\ML307R\SDK\http_assertion_result_v6.json D:\ML307R\SDK\http_bug_candidates_v6.json
type D:\ML307R\SDK\http_v6_stdout.log
type D:\ML307R\SDK\http_v6_stderr.log
```

## 早期卡点诊断

如果日志只出现脚本标题或停在串口阶段，给脚本加启动诊断：

```python
print("OPEN COM16...", flush=True)
s = serial.Serial("COM16", 115200, timeout=1)
print("COM16 OPENED", flush=True)
print("SEND AT...", flush=True)
at_resp = at(s, "AT")
print("AT RESP: {!r}".format(at_resp[:200]), flush=True)
```

同时把早期失败落盘：

```python
with open(r"D:\ML307R\SDK\http_coverage_v6_boot_error.json", "w", encoding="utf-8") as f:
    json.dump({"stage": stage, "detail": str(detail)}, f, indent=2, ensure_ascii=False)
```

## Pitfalls
- `ssh "cmd /c cd /d D:\\ML307R\\SDK && python ..."` 在多层转义下容易失效，`python` 可能回到 `C:\Users\52467` 执行。
- `cmd /c ... & ...` 中的 `&` 会破坏 `cd` 的作用域；复杂命令不要 inline。
- stdout 重定向若不加 `python -u`，长时间无输出时无法判断脚本是否进入早期阶段。
- 旧日志文件可能被卡住的进程占用；先用新日志名或确认旧 PID 已退出。
- 覆盖率脚本早期必须打印并 flush：打开串口前、打开串口后、发送 AT 前、AT 响应后。

## 验证清单
- [ ] PowerShell 返回 `STARTED PID=<pid>`。
- [ ] `http_v6_stdout.log` 至少包含脚本标题和时间。
- [ ] 若未生成结果 JSON，stdout/stderr 或 `http_coverage_v6_boot_error.json` 能定位阶段。
- [ ] 结果文件包含覆盖率、断言结果和潜在 bug 三类输出。
