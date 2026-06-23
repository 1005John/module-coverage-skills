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
- references/mqtt-at-commands.md — MQTT AT 命令完整参考
- references/tcp-module-testing.md — TCP 模块实测经验：crash bug、数据模式、access mode 策略
- references/echo-server-deployment.md — TCP/UDP echo server 部署
- references/windows-remote-test-execution.md — Windows 测试机远程运行、COM16 探针
- scripts/probe_com16.py — 固定探测 COM16 并发送 `AT`，期望输出 `b'\r\nOK\r\n'`
- references/http-coverage-v1-results.md — HTTP 首轮测试结果
- coverage-analysis/references/automatic-test-generation.md — 自动测试用例生成

## 覆盖率查询命令

```
AT+COVERAGE=1    # 清零并启用覆盖率统计
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
23. **不关闭已发送数据的连接** — MIPCLOSE 所有 mode (0/1/2) 在数据交换后必 crash，不关闭直接继续测试
24. **串口只回显无 OK** — 模组 crash 后 AT 解析器可能卡死，需彻底断电恢复
25. **Windows 环境变量传递** — cmd /c "set X=1&& python script.py" 注意 && 前无空格
24. **MQTT MQTTPUB 是数据模式** — `AT+MQTTPUB=...` 返回 `>` 后必须发送 payload，再收集 `+MQTTPUB`/`OK`/`+MQTTURC`；不能把 `>` 当普通结束，否则会污染后续 `AT+COVERAGE?`。
25. **MQTT query/test 不强等业务 URC** — `AT+MQTTCONN=?`、`AT+MQTTSUB=<id>` 等查询/测试命令不应等待 conn/suback URC。
26. **生成用例必须真实展开** — flow/example 必须展开为 `at_command` 或 `steps`，边界用例必须真实注入边界值；多条不同 id 但相同命令会误导覆盖率分析。

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

## 验证清单

- [ ] AT+COVERAGE=1 返回 OK
- [ ] generated_tests.yaml 校验通过，每 case 含 expected_result
- [ ] 执行后 AT+COVERAGE? 桩数增加
- [ ] run_result.json 保留原始响应和断言
- [ ] assertion_result.json 区分 pass/fail/xfail/error/env_fail
- [ ] bug_candidates.json 含复现步骤、期望、实际、证据
- [ ] 覆盖率达标或饱和原因明确
