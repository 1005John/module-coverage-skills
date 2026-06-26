---
name: coverage-test-execution
description: "AT 命令测试执行技能，支持 MQTT/HTTP/TCP 等模块的 AT 测试用例生成、执行、覆盖率查询"
triggers:
  - "AT 测试"
  - "执行测试"
  - "coverage test"
  - "AT 命令测试"
---

# AT 命令测试执行

## When to Use
- 固件已烧录，需要执行 AT 命令测试用例
- 需要生成某个模块的测试脚本
- 需要查询当前覆盖率并分析未覆盖桩

## 前置必读
- references/test-pc-workspace-scripts.md — **测试电脑工作区结构与脚本**：probe/flash/run/analyze/report 五个脚本用法、SSH 远程执行注意事项、固件两跳传输
- references/mqtt-at-commands.md — MQTT AT 命令完整参考
- references/tcp-module-testing.md — TCP 模块实测经验：crash bug、数据模式、access mode 策略
- references/echo-server-deployment.md — TCP/UDP echo server 部署
- references/windows-remote-test-execution.md — Windows 测试机远程运行、COM16 探针
- scripts/probe_com16.py — 固定探测 COM16 并发送 `AT`，期望输出 `b'\r\nOK\r\n'`
- references/http-coverage-v1-results.md — HTTP 首轮测试结果
- references/per-module-coverage-iteration.md — **新模块覆盖率迭代测试流程**：命令分组、增量分析、天花板预估
- references/pwm-bug-candidates-20260626.md — **PWM 疑似 Bug**：关闭路径未执行、period 校验缺失、ACTION_CMD 死代码
- references/ping-test-results-20260626.md — **PING 覆盖率测试**：6/15 (40%)，异步回调路径难覆盖，插桩修复 5 坑记录
- references/ping-dns-test-results-20260626.md — **PING+DNS 首轮覆盖率测试**：ALL 52/132，DNS 首轮 27%（网络未注册时）。后续迭代见 dns-coverage-test-results-20260626.md
- references/dns-coverage-test-results-20260626.md — **DNS 覆盖率测试**：5 轮迭代到 49% branch 饱和，网络注册前提，ML307C 实际支持范围，天花板分析
- coverage-analysis/references/automatic-test-generation.md — 自动测试用例生成

## DNS 底层插桩结果

AT 层 49% branch 饱和后，对底层文件追加插桩：

| 层 | 文件 | 桩数 | 状态 |
|----|------|------|------|
| AT 层 | cm_atcmd_dns.c | 60 | ✅ 已编译 |
| API 层 | cm_async_dns.c | 16 (4 stmt + 12 branch) | ✅ 已编译 |
| Client 层 | cm_plat_dns.c | 28 | ⚠️ 死代码（不在 .mak 中） |
| **总计** | | **76 (有效)** | |

cm_async_dns.c 覆盖函数：`__async_dns_entry`, `cm_async_dns_init`, `cm_async_dns_request`, `cm_async_dns_get_type_by_priority`

## 产出文件

```
D:\通信模组\at_kb_runs\runs\dns_v5\
AT+COVERAGE=0    # 禁用
AT+COVERAGE?     # 查询汇总
AT+COVERAGE=2    # MQTT bitmap chunk 0 (words 0-7)
AT+COVERAGE=3    # MQTT bitmap chunk 1 (words 8-15)
...
AT+COVERAGE=9    # MQTT bitmap chunk 7 (words 56-63)
```

**汇总响应格式**：
```
+COVERAGE: EXT(25%,0%,1/4) MQTT(51%,22%,261/635) HTTP(0%,0%,0/810) HTTPAPI(0%,0%,0/360) TCP(0%,0%,0/462) ALL(14%,3%,262/1461)
```

**Bitmap 响应格式**：
```
+COVERAGE_DETAIL: MQTT,<chunk>,<base_word>,<w0>,<w1>,<w2>,<w3>,<w4>,<w5>,<w6>,<w7>
```

每个 word 是 32-bit hex，stub id 命中判断：
```python
word_index = stub_id // 32
bit = stub_id % 32
hit = (words[word_index] & (1 << bit)) != 0
```

**注意**：`AT+COVERAGE=0/1` 保持原语义；`=2..9` 只查询 bitmap，不清零。

## 测试脚本核心函数

### AT 命令发送

```python
def at(ser, cmd, timeout=2):
    """发送 AT 命令，循环读取直到 OK/ERROR"""
    ser.reset_input_buffer()
    ser.write((cmd + '\r\n').encode())
    data = ''
    end = time.time() + timeout
    while time.time() < end:
        if ser.in_waiting:
            data += ser.read(ser.in_waiting).decode('utf-8', errors='replace')
            if 'OK' in data or 'ERROR' in data or '+CME ERROR' in data:
                time.sleep(0.2)
                if ser.in_waiting:
                    data += ser.read(ser.in_waiting).decode('utf-8', errors='replace')
                break
        time.sleep(0.05)
    return data.strip()
```

### URC 等待

```python
def wait_urc(ser, needle, timeout=8):
    """等待异步 URC 出现"""
    end = time.time() + timeout
    data = ''
    while time.time() < end:
        if ser.in_waiting:
            data += ser.read(ser.in_waiting).decode('utf-8', errors='replace')
            if needle in data:
                break
        time.sleep(0.1)
    return data
```

### 数据模式发布

```python
def pub_dm(ser, cmd, payload, timeout=8):
    """数据模式发布：cmd → > → payload → result"""
    ser.reset_input_buffer()
    ser.write((cmd + '\r\n').encode())
    prompt = read_until(ser, 3, ['>', 'ERROR', '+CME ERROR'])
    resp = prompt
    if '>' in prompt:
        ser.write(payload.encode())
        resp += '\n' + read_until(ser, timeout, ['OK', 'ERROR', '+CME ERROR', '+MQTTURC'])
        resp += '\n' + wait_urc(ser, '+MQTTURC', 5)
    return resp
```

### Bitmap 采集

```python
def bitmap_snapshot(ser):
    """采集 MQTT bitmap，返回 hit stub id 集合"""
    words = {}
    for cmd_value in range(2, 10):
        resp = at(ser, f'AT+COVERAGE={cmd_value}', 1.5)
        m = re.search(r'\+COVERAGE_DETAIL:\s*MQTT,(\d+),(\d+),([0-9A-Fa-f,]+)', resp)
        if m:
            base = int(m.group(2))
            hex_words = m.group(3).split(',')[:8]
            for off, word in enumerate(hex_words):
                words[base + off] = int(word, 16)
    # 判断命中
    ids = set()
    for word_index, word in words.items():
        for bit in range(32):
            sid = word_index * 32 + bit
            if word & (1 << bit):
                ids.add(sid)
    return words, ids
```

### 覆盖率快照

```python
def coverage_snapshot(ser):
    """采集汇总 + bitmap"""
    summary = at(ser, 'AT+COVERAGE?', 1.5)
    m = re.search(r'MQTT\((\d+)%,(\d+)%,(\d+)/(\d+)\)', summary)
    sm = {
        'stmt_percent': int(m.group(1)) if m else 0,
        'branch_percent': int(m.group(2)) if m else 0,
        'hit_stubs': int(m.group(3)) if m else 0,
        'total_stubs': int(m.group(4)) if m else 635,
    }
    words, ids = bitmap_snapshot(ser)
    return {'summary': sm, 'words': words, 'hit_ids': sorted(ids)}
```

### Case 执行

```python
def run_case(ser, case_id, action, results):
    """执行单条 case，采集前后 bitmap，计算增量"""
    before = coverage_snapshot(ser)
    log(f'CASE {case_id}')
    response = action(ser)
    after = coverage_snapshot(ser)
    new_ids = sorted(set(after['hit_ids']) - set(before['hit_ids']))
    result = {
        'id': case_id,
        'response': response[:2000],
        'before_summary': before['summary'],
        'after_summary': after['summary'],
        'new_stub_ids': new_ids,
        'new_stub_count': len(new_ids),
    }
    results.append(result)
    log(f'CASE {case_id} NEW {len(new_ids)} hits={after["summary"]["hit_stubs"]}')
    return result
```

## YAML 解析陷阱

自写 YAML 解析器（不依赖 pyyaml）必须处理：
1. **顶层 key 名** — 先检查实际文件（`tests:` vs `cases:`）
2. **单引号包裹双引号** — `cmd: 'AT+MIPCFG=\"cid\",0,1'`，strip 必须先 `'` 再 `"`
3. **status_in 格式** — `status_in: ["OK"]` 带方括号，判断用 `in`

## 模组 Crash Bug 清单 (ML307R 固件 3.1.0.2606221536_release)

**所有 crash 均导致模组重启、覆盖率归零，需物理拔插 USB 恢复。**

### Bug 1: MIPCLOSE 有数据连接 → crash
- **复现**: MIPOPEN → MIPSEND → 收到 URC → MIPCLOSE (mode=0/1/2 任意)
- **严重**: 100% 复现 (6/6)
- **安全**: MIPCLOSE 在无数据 idle 连接上正常

### Bug 2: MIPMODE 0→1 切换 → crash
- **复现**: MIPOPEN mode=0 → MIPSEND → MIPMODE=0,1 → crash

### Bug 3: MIPOPEN mode=1/2 时有活跃 mode=0 连接 → crash
- **复现**: MIPOPEN mode=0 成功 → MIPOPEN mode=1 (不同 connect_id) → crash

### Crash 规则
**任何导致已连接 socket 状态变化的操作都可能 crash：**
- MIPCLOSE (所有 mode)、MIPMODE 切换、开新连接冲突

**安全操作（不改变已连接 socket 状态）：**
- MIPSEND / MIPRD / MIPSACK / MIPSTATE / MIPCFG / MIPTKA
- MIPOPEN + MIPCLOSE on idle 连接、错误路径

### Access Mode 测试策略
每种 access_mode 需独立测试：重启 → MIPOPEN mode=N → 全量测试 → 记录 → 重启测下一个 mode。
mode=0 贡献最多 (~159 hits)，mode=1/2 各需单独测。

## 执行流程

用户要求“跑完整轮次/持续迭代/覆盖率分析迭代”时，不要停在单次用例执行，也不要频繁短等后汇报。必须持续完成：执行当前用例集 → 落盘结果 → 分析覆盖率和失败项 → 生成下一轮增量用例或脚本 → 执行增量轮 → 输出闭环报告。只有明确硬阻塞、需要物理操作或需要设计决策时才停下来。

1. 读取 `generated_tests.yaml`，校验 case schema 和 `expected_result`
2. 重置覆盖率：`AT+COVERAGE=0` → `AT+COVERAGE=1`（或不重置继续累积）
3. 按 case 执行 setup → steps → teardown
4. 每 case 后查询 `AT+COVERAGE?`
5. 按 `expected_result` 判定 pass/fail/xfail/error/env_fail
6. 断言 fail 时生成 `bug_candidates.json`
7. 检测模组 crash（AT 无 OK 响应）时标记环境失败并停止

## 多模块覆盖率架构（2026-06-26 验证）

### 核心规则：必须用 cm_cov_is_hit() + 本地 hit 函数

当固件有多个模块（PWM + PING + ...）时，每个模块必须：
1. `#define CM_COVERAGE_ENABLE` + `#include "cm_coverage.h"`
2. `#undef COV_STMT` / `#undef COV_BRANCH_T` / `#undef COV_BRANCH_F`
3. 定义 per-module 计数器：`volatile unsigned int cov_xxx_stmt_hits = 0;`
4. 定义本地 hit 函数：
```c
static void cm_cov_xxx_hit(uint16_t stub_id) {
    int already = cm_cov_is_hit(stub_id);
    cm_cov_hit(stub_id);
    if (!already) {
        if (stub_id >= BRANCH_START) cov_xxx_branch_hits++;
        else cov_xxx_stmt_hits++;
    }
}
```
5. 重新定义宏：`#define COV_STMT(id) cm_cov_xxx_hit(id)`

**为什么不能只用 cm_cov_hit()**：cm_cov_hit() 只递增全局 cov_pwm_stmt_hits，extern.c 读的是 per-module cov_xxx_stmt_hits → 永远显示 0。

**为什么不能用独立 bitmap**：会导致 >100% 计数（全局 bitmap 已设置，本地 bitmap 也设置，双重计数）。

### 编译前必须删 .lib

`.lib` 路径是 `obj_PMD2NONE/onemo-onemo.lib`（不是 `obj_onemo_onemo/` 下）。
不删 .lib → 链接器用旧 .o → 新桩不生效。

```cmd
del /q SDK\tavor\Arbel\obj_PMD2NONE\onemo-onemo.lib
del /q SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at\cm_atcmd_xxx.*
del /q SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at\pack_c.via
```

### 验证 .o 是否有 cm_cov_hit 调用

```cmd
fromelf -c obj_file.o | findstr cm_cov_hit
```
应看到 `BL cm_cov_hit` 指令。如果没有 → 桩编译为空操作。

## 常见 Pitfalls

1. **串口被占用** — 先 `taskkill /f /im python.exe`
2. **测试脚本必须放 Windows 测试机** — COM16 只在 Windows 可达
3. **SSH 远程执行** — 上传 `.py` 文件，用 `python -u script.py`，避免 inline Python
4. **长脚本必须实时日志** — `python -u` + `flush=True`
5. **卡点诊断** — 先跑最小探针（open COM → AT → OK）
6. **后台启动必须验证真实进度** — Windows `Start-Process`/`start /b` 可能只创建空 stdout/stderr 后立即退出；启动后必须检查 `tasklist`、日志增长、结果目录是否创建。若后台方式假跑，改用前台 SSH 长超时执行，或写 `.ps1` 明确重定向并检查 PID。
7. **at() 超时** — HTTP/TCP/MQTT 网络请求需 10-20s；用循环读取代替固定 sleep
8. **覆盖率不是通过标准** — 每 case 必须有 `expected_result`，不符合报 bug
9. **预期来源可追溯** — 优先引用 AT 手册 PDF
10. **AT 覆盖率天花板** — 纯 AT 命令 ~45-50%，需网络连接突破
11. **MQTTPUB 数据模式必须专门处理** — `AT+MQTTPUB=...` 返回 `>` 后必须写入 payload，再继续读取 `+MQTTPUB`/`OK`/`+MQTTURC`；不能把 `>` 当普通最终响应，否则会污染后续 `AT+COVERAGE?` 查询。
12. **MIPSEND 必须用数据模式** — 内联格式报 CME ERROR:50
13. **AT+MIPSTATE 多行** — 返回 6 行 + OK，用循环读取
14. **MIPCLOSE crash** — 有数据连接关闭必 crash，不关闭已发送数据的连接
15. **MIPMODE 切换 crash** — 不要事后切换 access_mode，MIPOPEN 时直接指定
16. **MIPOPEN mode=1/2 冲突 crash** — 有活跃 mode=0 时开 mode=1/2 会 crash
17. **MIPRD/MIPSACK idle 返回 OK** — 未连接时返回 OK 应为 ERROR，疑似 bug
18. **烧录后不自动重启** — adownload 100% 后需物理拔插 USB
19. **`+++` 退出数据模式** — 可能断开 TCP 连接，仅在确认卡在数据模式时使用
20. **YAML 单引号** — `cmd: 'AT+...'` strip 先单引号再双引号
21. **at() 必须用循环读取** — 固定 sleep 会漏掉多行响应（MIPSTATE 6行、MIPCFG query），用 while 循环读取 + 检查 OK/ERROR
22. **MIPSEND 内联格式无效** — `AT+MIPSEND=0,5,"HELLO"` 报 CME ERROR:50，必须用数据模式（不带 data 参数，等 > 提示后发送）
27. **不关闭已发送数据的连接** — MIPCLOSE 所有 mode (0/1/2) 在数据交换后必 crash，不关闭直接继续测试
28. **烧录脚本不能 taskkill python.exe** — 烧录+测试一体化脚本中 `taskkill /f /im python.exe` 会杀掉正在运行的脚本自身。只杀 adownload.exe。
29. **AT+COVERAGE=0/1 不清 bitmap** — 只重置计数器，bitmap 中已命中的桩不会被清除。如果需要"真正清零"，需要重新烧录固件。这意味着多次测试迭代时，桩计数只增不减。
30. **PWM 覆盖率天花板 87%** — ACTION_CMD 路径 (AT 解析器不派发) 无法通过 AT 命令覆盖，这是 AT 命令测试的固有上限。其他模块也会有类似现象。
24. **串口只回显无 OK** — 模组 crash 后 AT 解析器可能卡死，需彻底断电恢复
25. **Windows 环境变量传递** — cmd /c "set X=1&& python script.py" 注意 && 前无空格
24. **MQTT MQTTPUB 是数据模式** — `AT+MQTTPUB=...` 返回 `>` 后必须发送 payload，再收集 `+MQTTPUB`/`OK`/`+MQTTURC`；不能把 `>` 当普通结束，否则会污染后续 `AT+COVERAGE?`。
25. **MQTT query/test 不强等业务 URC** — `AT+MQTTCONN=?`、`AT+MQTTSUB=<id>` 等查询/测试命令不应等待 conn/suback URC。
26. **生成用例必须真实展开** — flow/example 必须展开为 `at_command` 或 `steps`，边界用例必须真实注入边界值；多条不同 id 但相同命令会误导覆盖率分析。
27. **SSH 环境下 adownload.exe 烧录卡住** — USB 烧录工具 (adownload.exe) 需要直接 USB 设备访问，通过 SSH 执行会永久卡住（无输出、不退出）。解决方案：用户手动在测试机上执行烧录命令，或使用远程桌面。
28. **串口被占用排查** — `PermissionError(13, '拒绝访问')` 表示 COM 口被其他进程占用。先 `taskkill /F /IM python.exe` 和 `taskkill /F /IM adownload.exe`，等待 3 秒后重试。
29. **⚠️ SSH 脚本中不要 taskkill python.exe** — 通过 SSH 运行 Python 测试脚本时，`taskkill /f /im python.exe` 会杀死正在运行的脚本本身。只能 `taskkill /f /im adownload.exe`。经典现象：脚本输出 `[1/6] Cleaning up...` 后直接退出，exit_code=1。
30. **覆盖率始终为 0/N 诊断** — 如果 AT+COVERAGE? 显示正确总桩数（如 PWM(0%,0%,0/30)）但执行 AT 命令后仍为 0，可能是桩写入了局部变量而 AT+COVERAGE? 读的是全局变量。检查模块 .c 文件是 include `cm_coverage.h`（正确）还是自己定义了 `cm_cov_xxx_hit()` 和局部变量（错误）。
31. **⚠️ Windows GBK 编码导致脚本崩溃** — Windows 中文 locale 默认 GBK 编码，无法输出 Unicode 字符（✓✗⚠️→等）。修复：(a) 脚本开头加 `sys.stdout.reconfigure(encoding='utf-8')`，或 (b) 用 ASCII 替代（`[OK]`/`[FAIL]`/`[!]`），或 (c) SSH 执行时设环境变量 `cmd /c "set PYTHONIOENCODING=utf-8 && python script.py"`。三种方法可混用，推荐 (b)+(c) 双保险。
32. **⚠️ AT+COVERAGE? 响应解析 — ALL 格式无百分号** — 新固件(4.0.15+)的 ALL 汇总格式为 `ALL(hit/total)` 而非 `ALL(stmt%,branch%,hit/total)`。正则必须同时匹配两种格式：`(\w+)\((\d+)%,(\d+)%` 匹配模块级，`(\w+)\((\d+)/(\d+)\)` 匹配 ALL。注意 Python raw string 中 `\\\\d+` 是错误的（匹配字面 `\d`），正确写法是 `\\d+`。
33. **AT+COVERAGE=1 在某些固件返回 ERROR** — 新固件可能不支持 `AT+COVERAGE=1` 清零命令。脚本应忽略此错误继续执行（烧录后覆盖率已归零）。如果需要真正清零，需重新烧录。
34. **PING/DNS 模块平台差异** — ML307C 上 `AT+MPING?` 返回 CME ERROR:4（不支持 query）；`AT+MDNSCFG` 仅支持 `"priority"` key，`"ip"`/`"ipv6"`/`"cached"`/`"timeout"` 返回 CME ERROR:4/50。用例生成前先查手册确认平台支持范围。
35. **固件传输两跳** — 固件在编译服务器(192.168.242.120)时，scp 直接用 Windows 路径会失败。正确流程：(1) 编译服务器上 `copy` 到简单路径如 `C:\\Users\\Lenovo\\fw.zip`，(2) scp 到 Mac，(3) scp 到测试电脑。测试机上 AT 手册路径：`D:\\通信模组\\手册`。
36. **DNS/HTTP/MQTT 网络模块必须检查 PDP** — 测试 DNS(MDNSGIP)、HTTP(MHTTPREQUEST)、MQTT(MQTTCONN) 等依赖网络的模块前，必须先检查 `AT+CEREG?`(返回 0,1 或 0,5 表示已注册) 和 `AT+CGACT?`(有活跃 PDP)。`CEREG: 0,0` = 未注册网络，所有 DNS 解析返回 CME ERROR:4。诊断命令：`AT+CPIN?`(SIM READY)→`AT+CEREG?`(注册)→`AT+CGACT?`(PDP)→`AT+CGPADDR=1`(IP)。无网络时只能测试不依赖网络的配置命令(如 MDNSCFG priority)。
37. **generated_tests.yaml 支持 setup 字段** — 测试用例可包含 `setup:` 列表，在 `at_command` 前顺序执行。用于需要先配置再测试的场景（如先 `AT+MDNSCFG="priority",0` 再 `AT+MDNSGIP`）。执行器必须在查询 coverage before 之前执行 setup 命令。
38. **覆盖率报告必须分别显示 stmt% 和 branch%** — 用户明确要求覆盖率概要用表格形式，每模块显示语句覆盖率和分支覆盖率两列。ALL 行因固件输出不带百分号（`ALL(hit/total)`），显示为 `-/-`。格式：`| 模块 | 语句覆盖率 | 分支覆盖率 | 命中/总数 |`。
39. **AT+COVERAGE? 多模块正则陷阱** — Python raw string 中 `r'(\w+)\((\d+)%,(\\\\d+)%'` 是错误的（`\\\\d` = regex 字面 `\d`，匹配反斜杠+d）。正确写法 `r'(\w+)\((\d+)%,(\\d+)%'`（`\\d` = regex `\d` = 数字）。最安全的写法是分两步：先 `re.findall(r'(\w+)\((\d+)%,(\\d+)%', resp)` 提取 name/stmt/branch，再 `re.search(rf'{name}\(\d+%,\d+%,(\d+)/(\d+)\)', resp)` 提取 hit/total。
40. **DNS 覆盖率天花板 ~49% branch** — ML307C 上 DNS 模块通过 AT 命令测试，branch 覆盖率在 49% 饱和（32/60）。剩余 28 个 branch 在 AT 命令无法触达的底层路径：UDP socket 收发、DNS 重试循环内部、NV 存储读写（ML307C 暂不保存 NV）、主/备服务器自动切换逻辑。突破需要在 `cm_dns_api.c` / `cm_dns_client.c` 等底层文件也插桩。**类似天花板**：PWM 87%（ACTION_CMD 死代码）、PING 53%（异步回调）。
41. **ML307C MDNSCFG 实际支持范围（固件 4.0.15+）** — 手册 Note 说"ML307C 仅支持 priority"，但实测固件 4.0.15+ 实际支持所有 key 的 SET 操作（ip/ipv6/cached/timeout/priority 全返回 OK）。QUERY 操作中：`"priority"` 查询正常返回 `+MDNSCFG: "priority",N`；`"ip"` 和 `"ipv6"` 查询正常返回服务器地址；`"cached"` 和 `"timeout"` 查询返回 CME ERROR:50（不支持查询）。**教训**：手册 Note 可能过时，实际支持范围以固件版本为准，需实测验证。

## MQTT 覆盖率迭代最佳实践 (2026-06-23)

v9 达到 51%/22% (261/635)，关键策略：

1. **分阶段执行**：CFG 测试 → 建立连接 → SUB/PUB/READ/UNSUB → DNS 失败（放最后）
2. **CFG 测试不需要连接**：query/reconn/retrans/encoding/platform/will/ssl/pingreq/pingresp/sndbuf 全部在连接前执行
3. **连接后立刻操作**：SUB → PUB → READ → UNSUB，不要等待
4. **数据模式必须专门处理**：`AT+MQTTPUB=...` 返回 `>` 后必须写入 payload
5. **每 case 后采集 bitmap**：`AT+COVERAGE=2..9` 获取 MQTT bitmap，计算 stub id
6. **连接管理**：每次 case 前检查 `AT+MQTTSTATE`，断开则重新连接
7. **DNS 失败放最后**：会破坏连接状态，后续用例全部失败

**高收益 case 排序**（v9 实测）：
- setup_conn: +53
- pub_dm_qos0: +35
- cfg_query_all_cids: +28
- cfg_will_matrix: +20
- sub_multi: +19
- cfg_platform_devinfo: +16
- pubjson: +15

**未覆盖热点**（v9 剩余 366 桩）：
- subscribe_cmd: 45 桩
- connect_cmd: 44 桩
- publish_cmd_combine: 37 桩
- datamode_cb: 30 桩
- cfg_platform_devinfo: 29 桩

42. **⚠️ 底层插桩可能降低覆盖率百分比** — 对底层文件（如 cm_async_dns.c）追加插桩后，分母从 60 增到 76，但新桩的 branch 路径在 AT 命令之外（内部调度、初始化），导致 branch% 从 49% 降到 39%。**教训**：追加底层插桩前评估新桩是否在 AT 命令可达路径中，否则只是增大分母不增加分子。底层桩覆盖率需要直接调用内部 API 或单元测试才能提升。
43. **⚠️ 插桩前确认文件在构建系统中** — cm_plat_dns.c 已插桩 28 桩但不在 .mak 中，属于死代码，不参与编译。插桩前用 `findstr /si "cm_async_dns" *.mak` 确认文件被构建系统包含。
44. **DNS 迭代策略：先网络后配置** — DNS 覆盖率提升顺序：(1) 确认网络注册 CEREG→PDP→IP (2) 配置命令全 key set+query (3) 解析命令多域名 (4) 优先级切换 (5) 缓存 hit/miss (6) 主备切换。v1-v4 从 27% 到 49%，v5 零新增确认饱和。

- [ ] AT+COVERAGE=1 返回 OK
- [ ] generated_tests.yaml 校验通过，每 case 含 expected_result
- [ ] 执行后 AT+COVERAGE? 桩数增加
- [ ] run_result.json 保留原始响应和断言
- [ ] assertion_result.json 区分 pass/fail/xfail/error/env_fail
- [ ] bug_candidates.json 含复现步骤、期望、实际、证据
- [ ] 覆盖率达标或饱和原因明确
