---
name: coverage-instrumentation
description: "通信模组源码自动插桩技能，支持按模块生成覆盖率桩并输出 coverage_map.json"
triggers:
  - "插桩"
  - "instrumentation"
  - "覆盖率桩"
  - "COV_STMT"
---

# 覆盖率自动插桩

## When to Use
- 需要对某个 AT 命令源文件（如 cm_atcmd_http.c）插入覆盖率桩
- 用户要求"给 XX 模块插桩"
- 需要生成 coverage_map.json 供后续测试和分析使用

## 前置必读
- references/cm_coverage_template.md — .h/.c 分离模式说明
- references/templates/cm_coverage.h — 正确的头文件模板
- references/adding-new-module-checklist.md — **新模块必读**：完整的文件修改清单、两套 cm_cov_hit() 架构、计数器 >100% 修复
- references/new-module-instrumentation-workflow.md — 新模块完整流程（HTTP 蓝本通用化）

## 输入

| 项目 | 说明 |
|------|------|
| 源文件 | cm_atcmd_*.c（AT 命令分发层） |
| 函数列表 | 从 cm_atcmd_def.h 中提取的命令处理函数名 |
| 桩 ID 范围 | 按模块分配，见下表 |

### 桩 ID 分配表

| 模块 | 语句桩 ID | 分支桩 ID | 已用桩数 |
|------|-----------|-----------|----------|
| EXT (cm_atcmd_extern.c) | 0-53 | 1100+ | ~60 |
| MQTT (cm_atcmd_mqtt.c) | 100-500 | 1100-1332 | 635 |
| HTTP (cm_atcmd_http.c) | 200-437 | 2000-2211 | 450 |
| TCPIP (cm_atcmd_tcpip.c) | 500-799 | 2500-2661 | 462 |
| 新模块 | 按需分配 | 避免重叠 | - |

## 插桩规则

### 语句桩 COV_STMT(id)
插入位置：
- 函数入口（第一个可执行行之前）
- 赋值语句前
- 关键函数调用前
- return/goto/break/continue 前

### 分支桩 COV_BRANCH_T(id) / COV_BRANCH_F(id)
插入位置：
- if/else if 的 { 之后（COV_BRANCH_T）
- else 的 { 之后（COV_BRANCH_F）
- 单行 if（无花括号）：不插分支桩，只插语句桩

### 禁止插入位置（编译会报错）
- 单行 if/else 的 body 前（COV_STMT 变成 if body，原语句变 unconditional）
- 多行表达式中间（前一行以 , || && 结尾）
- 函数参数列表中（前一行以 ( 或 , 结尾）
- return/goto/break/continue/CM_RETURN 之后（unreachable error）
- 多行 sprintf/函数调用的续行中

## 自动插桩脚本

参考脚本：instrument_http_v2.py（在 ml307r-embedded-sdk skill 的 scripts/ 中）

脚本核心逻辑：
1. 正则匹配函数签名 → 找到函数体 { }
2. 入口桩：找到函数体第一个可执行行（跳过声明）
3. 分支桩：扫描 if/else/else if，找 { 后插入
4. 语句桩：扫描赋值/调用/流程控制行
5. 过滤：跳过单行 if body、多行表达式、unreachable

### 关键过滤函数
- is_single_line_if_body() — 前一行是 if/else 且无 {
- is_multiline_continuation() — 前一行以 , || && 结尾
- ends_with_open_brace_or_paren() — 前一行以 ( 或 , 结尾
- is_return_or_goto() — 包括 CM_RETURN 宏
- **检查前一行是否字符串拼接** — 前一行以 `"` 结尾表示多行字符串拼接，不能插桩

### 多行函数调用检测（TCP 实测验证）
插桩脚本必须检测以下多行模式，否则编译报错：
1. **逗号续行** — 前一行以 `,` 结尾（函数参数列表跨行）
2. **括号续行** — 前一行以 `(` 结尾
3. **字符串拼接** — 前一行以 `"` 结尾（C 字符串字面量拼接）

```python
# 在插桩前检查
in_multiline = False
for prev_line in reversed(output_lines):
    prev_s = prev_line.strip()
    if prev_s:
        if prev_s.endswith(',') or prev_s.endswith('('):
            in_multiline = True
        if prev_s.endswith('"') and not prev_s.startswith('COV_'):
            in_multiline = True
        break
```

## 输出

## 输出

| 文件 | 说明 |
|------|------|
| 插桩后的 .c 文件 | 包含 COV_STMT/COV_BRANCH 宏调用 |
| coverage_map.json | 桩 ID → 位置映射 |

### coverage_map.json 格式

```json
{
  "module": "http",
  "source_file": "cm_atcmd_http.c",
  "total_stubs": 450,
  "stmt_range": [200, 437],
  "branch_range": [2000, 2211],
  "stubs": {
    "200": {"func": "cmiotHTTPCFG", "type": "entry", "line": 237},
    "2000": {"func": "cmiotHTTPCFG", "type": "branch_true", "line": 240}
  }
}
```

### 从插桩后的源码反扫 coverage_map

如果 `coverage_map.json` 丢失，可以从插桩后的源码反扫生成：

```python
import json, re, pathlib

def rebuild_coverage_map(source_path, module_name):
    """从插桩后的源码反扫 coverage_map.json"""
    src = pathlib.Path(source_path)
    lines = src.read_text(encoding='utf-8', errors='replace').splitlines()
    
    stubs = {}
    current_func = None
    func_re = re.compile(r'^\s*(?:static\s+)?(?:int|void|uint\w+_t|CMIOT\w+|CmsRetId)\s+([A-Za-z_]\w*)\s*\(')
    cov_re = re.compile(r'\b(COV_STMT|COV_BRANCH_T|COV_BRANCH_F)\s*\(\s*(\d+)\s*\)')
    
    for idx, line in enumerate(lines, 1):
        # 识别函数签名
        mfunc = func_re.match(line)
        if mfunc and not line.strip().startswith(('if', 'for', 'while', 'switch')):
            current_func = mfunc.group(1)
        
        # 识别 COV 宏
        for m in cov_re.finditer(line):
            kind, sid = m.group(1), int(m.group(2))
            stype = {'COV_STMT': 'stmt', 'COV_BRANCH_T': 'branch_true', 'COV_BRANCH_F': 'branch_false'}[kind]
            
            # 获取上下文
            context = ''
            for j in range(idx, min(idx + 5, len(lines))):
                s = lines[j].strip()
                if s and not s.startswith('COV_'):
                    context = s[:240]
                    break
            
            stubs[str(sid)] = {
                'id': sid,
                'func': current_func,
                'type': stype,
                'line': idx,
                'context': context,
            }
    
    stmt = sum(1 for s in stubs.values() if s['type'] == 'stmt')
    branch = len(stubs) - stmt
    
    result = {
        'module': module_name,
        'source_file': str(src),
        'total_stubs': len(stubs),
        'stmt_count': stmt,
        'branch_count': branch,
        'id_min': min(s['id'] for s in stubs.values()) if stubs else None,
        'id_max': max(s['id'] for s in stubs.values()) if stubs else None,
        'stubs': dict(sorted(stubs.items(), key=lambda kv: int(kv[0])))
    }
    
    return result

# 使用示例
# result = rebuild_coverage_map(r'D:\ML307R\SDK\onemo\at\src\cm_atcmd_mqtt.c', 'MQTT')
# json.dump(result, open('coverage_map.mqtt.json', 'w'), indent=2)
```

**注意**：反扫结果可能与固件实际桩数有差异（±10%），因为：
1. 有些桩可能在其他文件（如 `cm_atcmd_extern.c`）
2. 宏展开可能有变体
3. 多行函数调用中的桩可能被跳过

## 新模块插桩完整清单（关键！）

每次新模块插桩时，必须同时修改两个文件，否则 `AT+COVERAGE?` 不会显示新模块：

### 文件 1: 模块源码 (如 cm_atcmd_ping.c)

1. 添加独立计数器和 bitmap：
```c
#ifdef CM_COVERAGE_ENABLE
volatile unsigned int cov_xxx_stmt_hits = 0;
volatile unsigned int cov_xxx_branch_hits = 0;
#define COV_XXX_TOTAL 50
#define COV_XXX_BRANCH_START 30
static unsigned int cov_xxx_bitmap[(COV_XXX_TOTAL + 31) / 32] = {0};

static void cm_cov_xxx_hit(unsigned short id) {
    if (id >= COV_XXX_TOTAL) return;
    unsigned int w = id / 32;
    unsigned int b = id % 32;
    if (!(cov_xxx_bitmap[w] & (1u << b))) {
        cov_xxx_bitmap[w] |= (1u << b);
        if (id < COV_XXX_BRANCH_START) cov_xxx_stmt_hits++;
        else cov_xxx_branch_hits++;
    }
}
#define COV_STMT(id) cm_cov_xxx_hit(id)
#define COV_BRANCH_T(id) cm_cov_xxx_hit(id)
#define COV_BRANCH_F(id) cm_cov_xxx_hit(id)
#else
#define COV_STMT(id) ((void)0)
#define COV_BRANCH_T(id) ((void)0)
#define COV_BRANCH_F(id) ((void)0)
#endif
```

2. 在函数入口、if/else 体、关键执行行插入 COV_STMT/COV_BRANCH_T/COV_BRANCH_F

### 文件 2: cm_atcmd_extern.c（必须！）

在 `#ifdef CM_COVERAGE_ENABLE` 块中添加：

1. **extern 声明**（在其他模块声明之后）：
```c
extern volatile unsigned int cov_xxx_stmt_hits;
extern volatile unsigned int cov_xxx_branch_hits;
```

2. **变量声明**（在 AT+COVERAGE? 的 GET_CMD case 中）：
```c
unsigned long _xxx_stmt = cov_xxx_stmt_hits;
unsigned long _xxx_branch = cov_xxx_branch_hits;
unsigned long _xxx_total = STMT_COUNT + BRANCH_COUNT;
_all_stmt += _xxx_stmt;
_all_branch += _xxx_branch;
_all_total += _xxx_total;
```

3. **sprintf 输出**（修改 AT+COVERAGE? 的格式字符串）：
```c
sprintf(output, "+COVERAGE: EXT(...) MQTT(...) ... XXX(%lu%%,%lu%%,%lu/%lu) ALL(...)",
    (unsigned long)(_xxx_total > 0 ? (_xxx_stmt * 100) / STMT_COUNT : 0),
    (unsigned long)(_xxx_total > 0 ? (_xxx_branch * 100) / BRANCH_COUNT : 0),
    _xxx_stmt + _xxx_branch, _xxx_total,
    ...);
```

### 验证清单

- [ ] 模块源码有独立计数器和 bitmap
- [ ] cm_atcmd_extern.c 有 extern 声明
- [ ] cm_atcmd_extern.c 的 GET_CMD 有变量声明
- [ ] cm_atcmd_extern.c 的 sprintf 有新模块输出
- [ ] 编译后 AT+COVERAGE? 显示新模块
- [ ] 执行几条 AT 命令后新模块桩数 > 0

### 常见 Pitfall

1. **只改模块源码，不改 cm_atcmd_extern.c** → AT+COVERAGE? 不显示新模块
2. **extern 声明在 #ifdef 块外** → 编译通过但链接失败
3. **sprintf 格式字符串和参数数量不匹配** → 编译报错或输出乱码
4. **忘记清理 .o 和 pack_c.via** → 增量编译不重编，修改不生效

## 多层模块插桩架构

当模块有 AT 层 + 底层实现层时，需要两套独立插桩：

```
AT 分发层 (cm_atcmd_xxx.c)     ← 自定义 COV 插桩
    ↓ 调用
底层实现层 (cm_xxx_api.c)      ← 沿 TJ 桩插入 COV
    ↓ 调用
协议/平台层 (cm_xxx_client.c)  ← 已有 TJ 桩（不计入 COV）
```

### 关键原则

1. **每层使用独立的计数器和 bitmap** — 避免跨层计数冲突
2. **底层 .mak 必须加 `-DCM_COVERAGE_ENABLE` 和 include 路径** — 否则 COV 宏展开为空
3. **修改 .mak 后必须删 `pack_c.via`** — 否则增量编译不生效
4. **COV_TOTAL_STUBS 必须 >= 所有层的最大桩 ID + 1**
5. **AT+COVERAGE? 的 output buffer 必须扩大到 256 字节** — 新增模块后原 64 字节会溢出

### 独立计数器模式

每个需要独立报告的模块使用自己的 hit 函数：

```c
// 在模块的 .c 文件中
static unsigned int cov_xxx_bitmap[(4000 + 31) / 32] = {0};
volatile unsigned int cov_xxx_stmt_hits = 0;
volatile unsigned int cov_xxx_branch_hits = 0;

static void cm_cov_xxx_hit(uint16_t stub_id) {
    unsigned int w = stub_id / 32;
    unsigned int b = stub_id % 32;
    if (cov_xxx_bitmap[w] & (1u << b)) return;  // 首次命中才计数
    cov_xxx_bitmap[w] |= (1u << b);
    if (stub_id >= BRANCH_START) cov_xxx_branch_hits++;
    else cov_xxx_stmt_hits++;
}
```

**关键**：必须用独立 bitmap 判断首次命中。如果只靠全局 cm_cov_hit() 的 bitmap，计数器每次触发都会+1（因为全局 bitmap 已经被 cm_cov_hit() 设置了），导致显示 >100%。

## TCP 模块插桩实测数据 (2026-06-22)

| 层 | 文件 | stmt 桩 | branch 桩 | 总计 |
|----|------|---------|-----------|------|
| AT 层 | cm_atcmd_tcpip.c | 300 (500-799) | 162 (2500-2661) | 462 |

cm_atcmd_extern.c 新增 `TCP(%lu%%,%lu%%,%lu/%lu)` 格式，output buffer 扩大到 384 字节。

## 新模块必须更新 cm_atcmd_extern.c（关键 Pitfall）

插桩新模块后，`AT+COVERAGE?` 默认不会显示该模块。必须修改 `cm_atcmd_extern.c` 添加三处：

### 1. extern 声明（文件头部，约 40-55 行）

```c
extern volatile unsigned int cov_newmod_stmt_hits;
extern volatile unsigned int cov_newmod_branch_hits;
```

### 2. GET_CMD handler 中添加变量和总计

在 `case TEL_EXT_GET_CMD:` 中，找到 `_tcp_total` 定义附近，添加：

```c
unsigned long _newmod_stmt = cov_newmod_stmt_hits;
unsigned long _newmod_branch = cov_newmod_branch_hits;
unsigned long _newmod_total = STMT_COUNT + BRANCH_COUNT;
_all_stmt += ... + _newmod_stmt;
_all_branch += ... + _newmod_branch;
_all_total += ... + _newmod_total;
```

### 3. 修改 sprintf 格式字符串

在 `+COVERAGE:` 格式中添加 `NEWMOD(%lu%%,%lu%%,%lu/%lu)`，并在参数列表中添加对应的 3 个计算值。

### 编码注意事项

`cm_atcmd_extern.c` 在 Windows 上可能是 GBK 或 latin-1 编码。Python 修改脚本必须用 `encoding='latin-1'`，不能用 `utf-8` 或 `gbk`（会因特殊字节失败）。

```python
with open(path, 'r', encoding='latin-1') as f:
    content = f.read()
# ... 修改 ...
with open(path, 'w', encoding='latin-1') as f:
    f.write(content)
```

### 验证方法

修改后烧录，执行：
```
AT+COVERAGE=1    # 清零
AT+COVERAGE?     # 应显示 NEWMOD(0%,0%,0/N)
```

如果返回中没有新模块名，说明 extern 声明或 sprintf 未正确修改。

## 自动插桩脚本陷阱 (armcc 特有)

armcc (`--diag_error=warning`) 把以下情况从 warning 升级为 error，必须在插桩脚本中检测并跳过：

### 陷阱 1: 多行函数调用中间插入 COV_STMT
```c
OSATimerStart(socket_info->cm_auto_send.auto_send_timer,
              socket_info->cm_auto_send.auto_send_time * 200,
              COV_STMT(515);   // ← 编译错误！在函数参数中间
              0, __cm_tcpip_auto_send_msg, connect_id);
```
**检测**: 前一个非空行以 `,` 或 `(` 结尾 → 跳过

### 陷阱 2: 多行字符串拼接中间插入 COV_STMT
```c
cm_printf(atHandle, "\r\n+MIPCFG: \"cid\",(0-5),(1-15)\r\n"
                    "+MIPCFG: \"encoding\",(0-5),(0-2),(0-1)\r\n"
                    COV_STMT(581);   // ← 编译错误！在字符串拼接中间
                    "+MIPCFG: \"ssl\",(0-5),(0-1),(0-5)\r\n");
```
**检测**: 前一个非空行以 `"` 结尾（字符串字面量续行）→ 跳过

### 陷阱 3: 插桩脚本丢失代码
过度复杂的花括号追踪逻辑（如 `i = brace_i + 1` 跳转）会导致后续代码丢失。
**验证**: 插桩后文件大小必须 > 原始文件大小。若 < 原始文件，脚本有 bug。
**经验**: 保守策略 — 不跳过任何原始行，只在确定安全的位置前插入新行。

### 推荐的多行检测逻辑
```python
in_multiline = False
if output:
    for prev_line in reversed(output):
        prev_s = prev_line.strip()
        if prev_s:
            if prev_s.endswith(',') or prev_s.endswith('('):
                in_multiline = True
            if prev_s.endswith('"') and not prev_s.startswith('COV_'):
                in_multiline = True
            break
```

## 自动插桩脚本的三大陷阱（TCP 实战验证）

自动插桩脚本必须处理三种多行表达式，否则编译报错：

### 陷阱 A：多行函数调用（逗号续行）
```c
OSATimerStart(timer,
              time * 200,
              0, callback, id);   // ← 这行以 ; 结尾但不是独立语句
```
**检测**: 前一个非空行以 `,` 或 `(` 结尾 → 跳过插桩。

### 陷阱 B：多行字符串拼接
```c
cm_printf(atHandle, "\r\n+MIPCFG: \"cid\",(0-5)\r\n"
                    "+MIPCFG: \"encoding\",(0-5)\r\n"  // ← 字符串续行
                    "+MIPCFG: \"ssl\",(0-5)\r\n");
```
**检测**: 前一个非空行以 `"` 结尾（且不是 COV_ 宏） → 跳过插桩。

### 陷阱 C：单行 if 无花括号
```c
if (x > 0) return -1;  // ← 不能在这行前插 COV_STMT
```
**检测**: 前一行是 `if/else` 且无 `{` → 跳过插桩。

### 推荐的插桩脚本防御逻辑
```python
in_multiline = False
if output:
    for prev_line in reversed(output):
        prev_s = prev_line.strip()
        if prev_s:
            if prev_s.endswith(',') or prev_s.endswith('('):
                in_multiline = True
            if prev_s.endswith('"') and not prev_s.startswith('COV_'):
                in_multiline = True
            break

# 在插入语句桩前检查
if in_multiline:
    continue  # 跳过
```

### 验证插桩正确性
插桩后必须做两项检查：
1. `wc -c` 对比原始和插桩文件，大小应增加 ~30-50%（不是缩小！）
2. 逐行扫描：COV_ 宏前一个非空行不应以 `,`、`(`、`"` 结尾

## 常见 Pitfalls

1. **多行字符串拼接中间插入桩** — armcc 将相邻字符串字面量自动拼接（`"abc"\n"def"` = `"abcdef"`）。如果插桩脚本在两个字符串行之间插入 COV_STMT，编译报 `#18: expected a ")"`。**检测方法**：前一行以 `"` 结尾且不是 COV_ 行时，跳过插入。参见 `references/multiline-detection.md`。
2. **多行函数调用参数中间插入桩** — `OSATimerStart(timer, time, 0, callback, id)` 跨多行时，中间行以 `,` 结尾但以可执行参数开头，脚本误判为独立语句。**检测方法**：前一行以 `,` 或 `(` 结尾时，跳过插入。
3. **cm_atcmd_extern.c 有自己的 cm_cov_hit()** — 与 cm_coverage.c 的不同！新模块调用 cm_cov_hit() 会调用 extern.c 的版本。两处的 COV_TOTAL_STUBS 必须一致
2. **计数器 >100%** — 模块本地计数器不能无条件递增。必须用独立 bitmap 判断首次命中才 +1。详见 references/adding-new-module-checklist.md
3. **AT+COVERAGE? 不显示新模块** — 需要在 cm_atcmd_extern.c 中添加 extern 声明 + sprintf 格式
4. **sprintf 溢出 crash** — AT+COVERAGE? 的 output buffer 只有 64 字节，每加模块需扩大到 256+
5. **函数签名跨多行** — 参数行看起来像可执行语句，需先找函数体 { 再开始
6. **#include "cm_coverage.h" 后必须 #undef + #define** — 如果模块用本地 hit 函数
7. **COV_TOTAL_STUBS 必须 >= 最大桩 ID + 1** — 否则 cm_cov_hit() 静默丢弃
8. **插桩文件上传后必须删 .o 和 pack_c.via** — 否则增量编译不重编
9. **DC ALL 会从 ps.7z 恢复源文件** — 插桩后只能用 DC（增量）
10. **CM_RETURN/break/return 后的 COV_STMT** — 编译器报 unreachable error
11. **插桩脚本输出文件大小必须大于原始文件** — TCP 实战中 v1 脚本 bug 导致输出 16KB（原始 51KB），应为 70KB+
12. **多行字符串拼接中插桩** — 编译报 `expected a ")"` 错误。见上方"三大陷阱"
13. **extern.c 的 output buffer 必须随模块数扩大** — 5 模块需要 384 字节
12. **⚠️ 多行函数调用中间插入 COV_STMT 导致编译错误** — 自动插桩脚本必须检测续行。armcc 报 `#167: argument of type "void" incompatible` 和 `#165: too few arguments`。触发条件：前一行以 `,` 或 `(` 结尾（OSATimerStart、OSATimerCreate 等多行调用）。**修复**：在插入语句桩前，向回扫描 output buffer 找到前一个非空行，若以 `,` 或 `(` 结尾则跳过插入
13. **⚠️ 多行字符串拼接中间插入 COV_STMT 导致编译错误** — armcc 报 `#18: expected a ")"`。触发条件：cm_printf 等函数的多个字符串字面量拼接，前一行以 `"` 结尾。**修复**：同上，前一个非空行以 `"` 结尾（且不是 COV_ 行）时跳过插入
14. **⚠️ 只删 .d/.pp 不删 .o 导致编译系统跳过重编** — gnumake 看 .o 存在且时间戳新于源码就不重编。清理时必须 `.o` + `.d` + `.pp` + `pack_c.via` 一起删
15. **⚠️ ReliableData.bin 缺失导致 release zip 打包失败** — 编译本身成功（.o 和 .axf 都生成），但 release packaging 阶段报 `open raw image "rd" failed`。详见 references/reliabledata-bin-fix.md

## 验证清单

- [ ] 插桩文件编译通过（0 error, 0 warning）
- [ ] AT+COVERAGE? 显示正确的总桩数（EXT+MQTT+HTTP+...）
- [ ] 执行几条 AT 命令后 HTTP 桩数 > 0
- [ ] coverage_map.json 生成且桩数与实际一致
- [ ] 无 unreachable / expected a statement / too few arguments 错误