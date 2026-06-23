# Windows 远程运行 HTTP 覆盖率脚本注意事项

## When to Use
- 通过 SSH 在 Windows 测试机上运行 `D:\ML307R\SDK\run_http_coverage_v*.py`。
- 需要长时间执行 AT 串口测试，并把日志/JSON 结果可靠落盘。

## 背景
远程 `cmd /c cd /d D:\ML307R\SDK && python ...` 在多层 SSH/引号/重定向场景下容易被 `&`、重定向或当前目录解析影响，导致 Python 实际在 `C:\Users\<user>` 下执行，表现为：

- `python: can't open file 'C:\\Users\\52467\\run_http_coverage_v6.py'`
- 日志写到错误目录或日志文件为 0 字节
- 进程存在但没有进入脚本主逻辑

不要把这类现象误判为 HTTP 用例卡住；先确认进程命令行、工作目录、日志路径。

## 推荐运行方式
优先上传一个 `.ps1` 脚本文件，由 PowerShell 明确指定工作目录和日志路径，不要用长 inline 命令拼接。

```powershell
$workdir = 'D:\ML307R\SDK'
Set-Location $workdir
Remove-Item -ErrorAction SilentlyContinue `
  http_coverage_v6.json, `
  http_assertion_result_v6.json, `
  http_bug_candidates_v6.json, `
  http_v6_run.log

$stdout = Join-Path $workdir 'http_v6_run.log'
$stderr = Join-Path $workdir 'http_v6_run.err.log'
$p = Start-Process -FilePath 'python' `
  -ArgumentList @('-u', 'run_http_coverage_v6.py') `
  -WorkingDirectory $workdir `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -PassThru

"PID=$($p.Id)"
```

从 Mac 侧启动：

```bash
scp run_http_v6.ps1 52467@172.20.162.21:'C:/Users/52467/run_http_v6.ps1'
ssh 52467@172.20.162.21 "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\52467\\run_http_v6.ps1"
```

## 诊断清单
1. 查进程是否还在：
   ```cmd
   tasklist /FI "IMAGENAME eq python.exe"
   ```
2. 查命令行和父进程：
   ```cmd
   wmic process where "name='python.exe'" get ProcessId,ParentProcessId,CommandLine,CreationDate
   ```
3. 查日志是否增长：
   ```cmd
   dir D:\ML307R\SDK\http_v6_run*.log
   type D:\ML307R\SDK\http_v6_run.log
   ```
4. 如果进程 CPU 时间长期为 0 且日志 0 字节，优先怀疑启动/工作目录/重定向问题，而不是 AT 用例逻辑。
5. 如果日志已打印到 `AT: OK` 后卡住，再按串口、URC 等待、网络请求 timeout 方向诊断。

## 脚本侧建议
- 长流程脚本使用 `python -u` 或所有关键 `print(..., flush=True)`。
- 在打开串口前后打印明确标记：`before serial open`、`after serial open`、`before AT probe`。
- 结果 JSON 应分阶段增量写入或至少在异常时写 `run_error.json`，避免长跑失败后没有证据。
- 远程运行前先确认没有旧 Python 占用串口；必要时精确 `taskkill /F /PID <pid>`，不要盲目杀所有进程。
