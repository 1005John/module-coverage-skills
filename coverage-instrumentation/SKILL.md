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

## 部署位置

**编译服务器** (192.168.242.120) — 源码修改和编译在同一台机器上完成，避免文件传输。

## 前置必读
- templates/dns-deep-instrumentation-brief.md — **底层文件追加插桩模板**：AT 层饱和后对 API/Client 层插桩的完整流程
- references/cm_coverage_template.md — .h/.c 分离模式说明
- references/separation-model-debugging.md — **2026-06-25 PWM 实战调试记录**：变量重复定义、链接列表遗漏、ATRESP 双重调用等完整调试时间线
- references/templates/cm_coverage.h — 正确的头文件模板
- references/armcc-optimization-trap.md — **ARM Compiler 5 优化陷阱**：桩 increment 被优化掉的根因和 .h/.c 分离模式解决方案
- references/pwm-coverage-integration-debug-20260626.md — **PWM 集成调试**：instrument.py 自包含桩 vs 全局 cm_coverage.c/h 双重系统导致覆盖率始终 0 的完整排查
- references/adding-new-module-checklist.md — **新模块必读**：完整的文件修改清单、两套 cm_cov_hit() 架构、计数器 >100% 修复
- references/armcc5-coverage-pitfalls.md — **ARM Compiler 5 关键坑**：static 函数优化、.lib 重建时序、SDK 原生 ZIP 格式、ATRESP 双重调用、handler 注册、变量重复定义等
- references/test-computer-workflow.md — 测试电脑工作流：文件传输、烧录、覆盖率采集的完整流程
- references/adding-new-module-checklist.md — **新模块必读**：完整的文件修改清单、两套 cm_cov_hit() 架构、计数器 >100% 修复
- references/new-module-instrumentation-workflow.md — 新模块完整流程（HTTP 蓝本通用化）
- references/git-diff-incremental-instrumentation.md — Level 2 增量插桩方案：基于 git diff 分析变更点，只对受影响函数调整桩，无需全量重插
- references/ml302a-module-inventory.md — Windows 服务器 (192.168.242.120) 上 ml302a_dev_asr_144 的模块清单、文件大小、桩 ID 分配建议和插桩优先级
- references/armcc-coverage-pitfalls.md — **必读**：ARM Compiler 5 覆盖率插桩实战 Pitfalls（编译器优化、变量重复定义、ATRESP 调用、编译链接、固件打包）
- references/server-agent-workflow.md — 中心服务器 Agent 开发流程、产物目录、测试电脑操作、SSH 连接信息
- references/h-c-separation-model.md — **armcc 防优化方案**：.h/.c 分离模式 + #pragma O0，解决 armcc -O2 优化掉桩函数体的问题
- references/cm_atcmd_extern_modification.md — cm_atcmd_extern.c 的 AT+COVERAGE? handler 修改指南
- references/server-agent-output-contract.md — 服务器 Agent 插桩产出规范：模块源码模板、cm_atcmd_extern.c 三处修改、manifest.json、coverage_map 完整字段、instrument.py 当前缺失项
- references/server-agent-test-workflow.md — 服务器→测试电脑完整工作流：产物传输、烧录流程、AT+COVERAGE? 验证、常见问题
- references/cm_atcmd_extern_modification.md — cm_atcmd_extern.c 修改指南：三处修改 + 命令注册 + ATRESP 规则 + 编码
- references/multi-module-coverage-fix-20260626.md — **多模块覆盖率修复**：cm_cov_is_hit() + 本地 hit 函数 + #undef/#define 完整记录

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

## .h/.c 分离模式（推荐，防止编译器优化）

**背景**：armcc 5.05 (-O2) 会优化掉 static 函数中的 volatile 写操作。即使用 `#pragma O0`
保护 static 函数，increment 仍可能被优化掉。

**解决方案**：将 cm_cov_hit() 放在独立的 cm_coverage.c 中编译，通过 cm_coverage.h 提供宏和声明。

```c
/* cm_coverage.h */
#define COV_TOTAL_STUBS   250   /* ⚠️ 必须 >= 最大桩 ID + 1！原来 50 导致 ID>=50 的桩被静默丢弃 */
#define COV_BRANCH_START  200
#define COV_STMT(id)        cm_cov_hit(id)
#define COV_BRANCH_T(id)    cm_cov_hit(id)
#define COV_BRANCH_F(id)    cm_cov_hit(id)
extern volatile unsigned int cov_pwm_stmt_hits;
extern volatile unsigned int cov_pwm_branch_hits;
extern void cm_cov_hit(uint16_t stub_id);
```

```c
/* cm_coverage.c — 独立编译单元，编译器无法跨单元优化 */
#include "cm_coverage.h"
volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;
static unsigned int cov_bitmap[(COV_TOTAL_STUBS + 31) / 32] = {0};
#pragma O0
void cm_cov_hit(uint16_t stub_id) { /* bitmap 去重 + 计数 */ }
#pragma O2
```

**关键约束**：
- 变量只在 cm_coverage.c 中定义一次，其他文件用 extern
- cm_coverage.o 必须加入 `onemo-at_pk_objliblist.txt` 链接列表
- 详见 `references/armcc-coverage-pitfalls.md`

## 新模块插桩完整清单（关键！）

每次新模块插桩时，必须同时修改两个文件，否则 `AT+COVERAGE?` 不会显示新模块：

### 文件 1: 模块源码 (如 cm_atcmd_pwm.c)

只加一行 include，不定义任何局部变量或函数：
```c
#include "cm_coverage.h"
```

然后在函数入口、if/else 体、关键执行行插入 COV_STMT/COV_BRANCH_T/COV_BRANCH_F 宏调用。

**❌ 不要**在模块 .c 文件中定义自己的 hit 函数、bitmap、计数器变量。全局 cm_coverage.c/h 已经提供了所有基础设施。详见 references/pwm-coverage-integration-debug-20260626.md（4 层坑链）。

### 文件 2: cm_coverage.h（检查 COV_TOTAL_STUBS）

```c
#define COV_TOTAL_STUBS   250   /* ⚠️ 必须 > 所有模块的最大桩 ID！否则静默丢弃 */
```

每次新模块插桩后，检查最大桩 ID 是否超过 COV_TOTAL_STUBS。超过则修改此值并重编 cm_coverage.c。

### 文件 3: cm_atcmd_extern.c（必须！）

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

- [ ] cm_coverage.h 的 COV_TOTAL_STUBS >= 最大桩 ID + 1（每加新模块必须检查！）
- [ ] 模块源码有 `#include "cm_coverage.h"`（不是自包含桩实现）
- [ ] 模块源码没有定义自己的 hit 函数、bitmap、计数器（用全局的）
- [ ] cm_atcmd_extern.c 有 extern 声明
- [ ] cm_atcmd_extern.c 的 GET_CMD 有变量声明
- [ ] cm_atcmd_extern.c 的 sprintf 有新模块输出
- [ ] 编译后 AT+COVERAGE? 显示新模块
- [ ] 执行几条 AT 命令后新模块桩数 > 0
- [ ] 无双重系统（局部 vs 全局变量冲突）

### ⚠️ 关键 Pitfall: stmt 和 branch 桩 ID 不能重叠（PWM 实战验证）

`cm_cov_hit()` 函数通过 `COV_BRANCH_START` 阈值区分 stmt 和 branch：
```c
if (id < COV_BRANCH_START) cov_stmt_hits++;
else cov_branch_hits++;
```

如果一个模块中 COV_STMT(30) 和 COV_BRANCH_T(30) 同时存在（不同函数中），ID 30 会被错误地计入 branch（因为 30 >= COV_BRANCH_START=30）。这会导致：
- stmt 覆盖率偏低（桩被计入 branch）
- cm_atcmd_extern.c 中的分母计算错误
- coverage_map.json 中的桩类型与实际不一致

**解决方案**：
1. 插桩时确保 COV_STMT 的 ID < COV_BRANCH_START，COV_BRANCH_T/F 的 ID >= COV_BRANCH_START
2. 每个函数的桩 ID 范围必须不重叠
3. 插桩完成后用以下脚本检查 ID 重叠：
```python
import re
with open(source_file) as f:
    content = f.read()
stmt_ids = set(int(m) for m in re.findall(r'COV_STMT\((\d+)\)', content))
branch_ids = set()
for m in re.findall(r'COV_BRANCH_[TF]\((\d+)\)', content):
    branch_ids.add(int(m))
overlap = stmt_ids & branch_ids
if overlap:
    print(f"ERROR: stmt 和 branch 桩 ID 重叠: {sorted(overlap)}")
    print("这些 ID 会被 cm_cov_hit() 错误分类")
```

### ⚠️ 关键 Pitfall: cm_atcmd_extern.c 中的分母必须匹配实际桩数

AT+COVERAGE? 的 sprintf 中，语句覆盖率计算为 `(_xxx_stmt * 100) / STMT_COUNT`。STMT_COUNT 必须等于实际的 COV_STMT 桩数（即 < COV_BRANCH_START 的唯一 ID 数量），不是总桩数。

PWM 实战中的 bug：
- 旧值: `_pwm_total = 43 + 23 = 66`, `(_pwm_stmt * 100) / 43` — 错误（43 是包含 branch ID 的 COV_STMT 宏调用数）
- 新值: `_pwm_total = 30 + 23 = 53`, `(_pwm_stmt * 100) / 30` — 正确（30 是 < COV_BRANCH_START 的唯一 stmt ID 数）

**验证方法**：插桩后统计 `< COV_BRANCH_START` 的唯一 COV_STMT ID 数量，用这个值作为 cm_atcmd_extern.c 中的 STMT_COUNT 分母。

### ⚠️ 关键 Pitfall: volatile 关键字不能省略（ARM 编译器优化陷阱）

模块源码中的覆盖率计数器**必须声明为 volatile**：

```c
// ✅ 正确
volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;

// ❌ 错误（ARM armcc 会优化掉 increment）
unsigned int cov_pwm_stmt_hits = 0;
unsigned int cov_pwm_branch_hits = 0;
```

**现象**：AT+COVERAGE? 返回 0/N，但函数确实被调用了（可用调试计数器验证）。

**原因**：ARM Compiler 5 (armcc) 看到 `static void cm_cov_xxx_hit()` 函数修改的全局变量没有 volatile，且没有被本文件其他函数读取 → 编译器将 increment 操作视为 dead code 并优化掉。函数调用本身保留（所以调试计数器正常），但函数体内的 `cov_xxx_stmt_hits++` 被消除。

**修复（三层防护，全部需要）**：

1. **volatile 变量声明**：模块源码和 cm_atcmd_extern.c 中都必须用 `volatile unsigned int`
2. **函数不能是 static**：`static` 函数被 armcc 内联后，increment 可能被优化掉
3. **函数必须禁用优化**：用 `__attribute__((optnone))` 或 `#pragma O0`

```c
// ✅ 正确写法
volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;

__attribute__((optnone)) void cm_cov_pwm_hit(unsigned short id) {
    if (id >= COV_PWM_TOTAL) return;
    unsigned int w = id / 32;
    unsigned int b = id % 32;
    if (!(cov_pwm_bitmap[w] & (1u << b))) {
        cov_pwm_bitmap[w] |= (1u << b);
        if (id < COV_PWM_BRANCH_START) cov_pwm_branch_hits++;
        else cov_pwm_stmt_hits++;
    }
}
```

**调试方法**：在函数中添加一个独立的调试计数器，不依赖 COV 宏：
```c
volatile unsigned int pwm_debug_call_count = 0;
// 在函数入口添加
pwm_debug_call_count++;
```
在 `AT+COVERAGE?` 的输出中添加 `DBG=%lu` 参数显示该计数器值。

**验证**：AT+COVERAGE? 应显示 `DBG=N`（N > 0 表示函数被调用了 N 次）。

**诊断流程**（当覆盖率始终为 0 时）：
1. 在 cmCOVERAGE GET_CMD 中直接写 `cov_pwm_stmt_hits = 99;` → 如果 AT+COVERAGE? 显示 99 → extern 链接正确
2. 添加 DBG 计数器 → 如果 DBG 递增但覆盖率为 0 → 编译器优化问题
3. 确认函数非 static + `__attribute__((optnone))` → 重新编译验证

## 常见 Pitfall

1. **只改模块源码，不改 cm_atcmd_extern.c** → AT+COVERAGE? 不显示新模块
2. **extern 声明在 #ifdef 块外** → 编译通过但链接失败
3. **sprintf 格式字符串和参数数量不匹配** → 编译报错或输出乱码
4. **忘记清理 .o 和 pack_c.via** → 增量编译不重编，修改不生效
5. **COV_BRANCH_START 设置错误导致 stmt/branch 混淆** → 如果 COV_STMT 的 ID 范围和 COV_BRANCH 的 ID 范围有重叠（如 COV_STMT(50) 和 COV_BRANCH_T(50)），`cm_cov_xxx_hit()` 函数中 `if (id < COV_BRANCH_START)` 的判断会出错。COV_STMT(50) 会被计为 branch。**解决**：COV_BRANCH_START 必须大于所有 COV_STMT 的最大 ID。推荐 COV_STMT 用 ID 0-99，COV_BRANCH 用 ID 100+，COV_BRANCH_START=100。
6. **cm_atcmd_extern.c 中的分母硬编码** → sprintf 中 `(_dns_stmt * 100) / 99` 的 99 是 stmt 桩数，`(_dns_branch * 100) / 49` 的 49 是 branch 桩数。这些数字必须与插桩后的源码中实际的 stmt/branch 桩数一致。每次修改插桩后都要验证这些数字。
7. **coverage_map.json 中 stmt/branch 分类错误** → 插桩时 COV_STMT 和 COV_BRANCH 可能共用同一个 ID（如 ID 50 同时出现在 COV_STMT(50) 和 COV_BRANCH_T(50) 中）。coverage_map.json 中应该按 COV 宏类型分类，不是按 ID 范围。COV_STMT(50) 是 stmt，COV_BRANCH_T(50) 是 branch_true。
5. **cm_atcmd_extern.c 的桩被计入所有模块** → AT+COVERAGE? 返回的桩数 > coverage_map 中的桩数。这些桩（ID 1,3,5,6,53,55 等）属于 AT+MADC、AT+MLPMCFG 等命令，不是目标模块的桩。分析覆盖率时需要排除这些桩。
6. **ML302A_SUPPORT 条件编译代码** → ML307R 平台不编译这些代码，coverage_map 中存在但固件中未编译的桩无法覆盖
7. **static + volatile 不够** → armcc 会内联 static 函数后优化掉 volatile increment。需要非 static + `__attribute__((optnone))`。详见 references/armcc-optimization-pitfalls.md
8. **ATRESP 双重调用** → 辅助函数中调用 ATRESP 后 handler 又调用一次，第二次覆盖第一次导致返回空。必须只在 handler 中调用一次 ATRESP
9. **cm_atcmd_def.h handler 为 NULL** → AT 命令注册时 handler 全为 NULL，命令被解析但不执行。必须链接 cmCOVERAGE 函数
10. **cmCOVERAGE 声明在 #ifdef 块内** → 如果在 `#ifdef VOLTE_ENABLE` 内，cm_atcmd_def.h 无法引用。必须移到 #ifdef 外面

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

## 常见 Pitfall

### .h/.c 分离模式（推荐，防编译器优化）

当 armcc 对 static 函数的 increment 进行激进优化时（即使 volatile + #pragma O0 也无法阻止），必须使用 .h/.c 分离模式：

**cm_coverage.h** — 宏定义 + extern 声明：
```c
#ifndef CM_COVERAGE_H
#define CM_COVERAGE_H
#include <stdint.h>
#define COV_TOTAL_STUBS   250   /* ⚠️ 必须 >= 最大桩 ID + 1 */
#define COV_BRANCH_START  200
#define COV_STMT(id)        cm_cov_hit(id)
#define COV_BRANCH_T(id)    cm_cov_hit(id)
#define COV_BRANCH_F(id)    cm_cov_hit(id)
extern volatile unsigned int cov_pwm_stmt_hits;
extern volatile unsigned int cov_pwm_branch_hits;
extern void cm_cov_hit(uint16_t stub_id);
#endif
```

**cm_coverage.c** — 独立编译单元 + #pragma O0：
```c
#include "cm_coverage.h"
volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;
static unsigned int cov_bitmap[(COV_TOTAL_STUBS + 31) / 32] = {0};
#pragma O0
void cm_cov_hit(uint16_t stub_id) {
    unsigned int w = stub_id / 32;
    unsigned int b = stub_id % 32;
    if (!(cov_bitmap[w] & (1u << b))) {
        cov_bitmap[w] |= (1u << b);
        if (stub_id < COV_BRANCH_START) cov_pwm_stmt_hits++;
        else cov_pwm_branch_hits++;
    }
}
#pragma O2
#endif
```

**cm_atcmd_pwm.c** — 只 include，不定义变量：
```c
#include "cm_coverage.h"
// 使用 COV_STMT(100); COV_BRANCH_T(200); 等宏
// ❌ 不要再定义 cov_pwm_stmt_hits 等变量！
```

**⚠️ 变量重复定义陷阱**：如果 cm_coverage.c 和 cm_atcmd_pwm.c 都定义了 `volatile unsigned int cov_pwm_stmt_hits = 0;`，链接器会创建两个不同的符号。cm_cov_hit() 修改的是 cm_coverage.c 的版本，cm_atcmd_extern.c extern 引用的可能是 cm_atcmd_pwm.c 的版本 → 覆盖率始终为 0。

**验证方法**：在 cm_atcmd_pwm.c 中直接写 `cov_pwm_stmt_hits = 99;`，然后 AT+COVERAGE? 检查。显示 99 → 链接正确；仍为 0 → 有重复定义。

**⚠️ instrument.py 不要生成自包含桩实现（2026-06-26 实战）**：instrument.py 生成的 `#ifdef CM_COVERAGE_ENABLE` 块包含了完整的自包含桩实现（`cm_cov_pwm_hit()` + 局部 `cov_pwm_stmt_hits` + 局部 `cov_pwm_bitmap`）。这导致：
1. 局部变量与全局 `cm_coverage.c` 的变量冲突（同名不同地址）
2. `AT+COVERAGE?` 读的是全局变量，桩写的是局部变量 → 永远 0/N
3. 如果模块 .c 文件不 include `cm_atcmd_extern.h`（那里定义 `CM_COVERAGE_ENABLE`），宏展开为 `((void)0)` → 桩为空操作

**正确做法**：instrument.py 应该只在模块 .c 文件头部生成 `#include "cm_coverage.h"`，使用全局的 `COV_STMT`/`COV_BRANCH_T` 宏和 `cm_cov_hit()` 函数。不要生成任何局部的桩实现代码。cm_coverage.h 已经定义了所有需要的宏和 extern 声明。

**⚠️ .mak 链接列表**：cm_coverage.o 必须在 `onemo-at_pk_objliblist.txt` 中。检查：`findstr cm_coverage onemo-at_pk_objliblist.txt`

详见 `references/separation-model-debugging.md`。

### 其他 Pitfall

1. **多行字符串拼接中间插入桩** — armcc 将相邻字符串字面量自动拼接（`"abc"\n"def"` = `"abcdef"`）。如果插桩脚本在两个字符串行之间插入 COV_STMT，编译报 `#18: expected a ")"`。**检测方法**：前一行以 `"` 结尾且不是 COV_ 行时，跳过插入。参见 `references/multiline-detection.md`。
2. **多行函数调用参数中间插入桩** — `OSATimerStart(timer, time, 0, callback, id)` 跨多行时，中间行以 `,` 结尾但以可执行参数开头，脚本误判为独立语句。**检测方法**：前一行以 `,` 或 `(` 结尾时，跳过插入。
3. **cm_atcmd_extern.c 有自己的 cm_cov_hit()** — 与 cm_coverage.c 的不同！新模块调用 cm_cov_hit() 会调用 extern.c 的版本。两处的 COV_TOTAL_STUBS 必须一致
3. **计数器 >100%** — 模块本地计数器不能无条件递增。必须用独立 bitmap 判断首次命中才 +1。详见 references/adding-new-module-checklist.md
4. **AT+COVERAGE? 不显示新模块** — 需要在 cm_atcmd_extern.c 中添加 extern 声明 + sprintf 格式
5. **sprintf 溢出 crash** — AT+COVERAGE? 的 output buffer 只有 64 字节，每加模块需扩大到 256+
6. **AT+COVERAGE? 返回空（不是 ERROR）** — cm_atcmd_def.h 中 handler 全为 NULL，或 ATRESP 被调用两次（辅助函数一次 + handler 一次，第二次覆盖第一次）。详见 references/cm_atcmd_extern_modification.md
7. **AT+COVERAGE? 返回 0/N 且执行 AT 命令后仍为 0** — 计数器变量缺少 volatile 关键字，ARM armcc 优化掉了 increment 操作。用调试计数器验证：如果 DBG 递增但覆盖率为 0 → volatile 问题
8. **AT+COVERAGE=1 返回 ERROR** — SET_CMD handler 未正确注册或参数解析问题。检查 cm_atcmd_def.h 中 cmCOVERAGE 是否链接到 set_handler 位置
5. **函数签名跨多行** — 参数行看起来像可执行语句，需先找函数体 { 再开始
6. **#include "cm_coverage.h" 后必须 #undef + #define** — 如果模块用本地 hit 函数
7. **COV_TOTAL_STUBS 必须 >= 最大桩 ID + 1** — 否则 cm_cov_hit() 静默丢弃
8. **插桩文件上传后必须删 .o 和 pack_c.via** — 否则增量编译不重编
9. **DC ALL 会从 ps.7z 恢复源文件** — 插桩后只能用 DC（增量）
10. **CM_RETURN/break/return 后的 COV_STMT** — 编译器报 unreachable error
11. **插桩脚本输出文件大小必须大于原始文件** — TCP 实战中 v1 脚本 bug 导致输出 16KB（原始 51KB），应为 70KB+
## 常见 Pitfalls

13. **⚠️ 编译前必须运行 update_extern.py** — instrument.py 只生成模块源码中的桩实现，不更新 cm_atcmd_extern.c。如果跳过 update_extern.py 直接编译，AT+COVERAGE? 返回 ERROR。正确顺序：instrument.py → update_extern.py → 编译。
14. **⚠️ 多行函数调用中间插入 COV_STMT 导致编译错误** — 自动插桩脚本必须检测续行。armcc 报 `#167: argument of type "void" incompatible` 和 `#165: too few arguments`。触发条件：前一行以 `,` 或 `(` 结尾（OSATimerStart、OSATimerCreate 等多行调用）。**修复**：在插入语句桩前，向回扫描 output buffer 找到前一个非空行，若以 `,` 或 `(` 结尾则跳过插入
17. **⚠️ 多行字符串拼接中间插入 COV_STMT 导致编译错误** — 自动插桩脚本必须检测续行。armcc 报 `#167: argument of type "void" incompatible` 和 `#165: too few arguments`。触发条件：前一行以 `,` 或 `(` 结尾（OSATimerStart、OSATimerCreate 等多行调用）。**修复**：在插入语句桩前，向回扫描 output buffer 找到前一个非空行，若以 `,` 或 `(` 结尾则跳过插入
18. **⚠️ 多行字符串拼接中间插入 COV_STMT 导致编译错误** — armcc 报 `#18: expected a ")"`。触发条件：cm_printf 等函数的多个字符串字面量拼接，前一行以 `"` 结尾。**修复**：同上，前一个非空行以 `"` 结尾（且不是 COV_ 行）时跳过插入
19. **⚠️ 只删 .d/.pp 不删 .o 导致编译系统跳过重编** — gnumake 看 .o 存在且时间戳新于源码就不重编。清理时必须 `.o` + `.d` + `.pp` + `pack_c.via` 一起删
20. **⚠️ ReliableData.bin 缺失导致 release zip 打包失败** — 编译本身成功（.o 和 .axf 都生成），但 release packaging 阶段报 `open raw image "rd" failed`。详见 references/reliabledata-bin-fix.md
21. **⚠️ ATRESP 双重调用导致 AT+COVERAGE? 返回空** — 如果在 cm_coverage_query() 辅助函数中调用 ATRESP 发送数据，然后在 cmCOVERAGE() 的 GET_CMD 中又调用一次 ATRESP(atHandle, OK, 0, "")，第二次会覆盖第一次，导致返回空。**修复**：只在 GET_CMD 中调用一次 ATRESP，辅助函数只负责填充 buffer，不要调用 ATRESP。或将计算逻辑内联到 GET_CMD 中。
22. **⚠️ AT 命令注册时 handler 为 NULL 导致命令无响应** — `cm_atcmd_def.h` 中 `utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, NULL, NULL, NULL)` 的后四个参数是 handler 函数指针。全为 NULL 时命令被解析但不执行任何操作（不是 ERROR，而是空响应或静默成功）。**修复**：至少设置 GET_CMD handler：`utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, cmCOVERAGE, cmCOVERAGE, cmCOVERAGE)`
23. **⚠️ #ifdef CM_COVERAGE_ENABLE 条件编译陷阱** — 如果覆盖率代码被 `#ifdef CM_COVERAGE_ENABLE` 包裹但编译时未定义该宏，所有桩代码和 AT+COVERAGE? handler 都会被编译掉。**修复**：确认编译命令中包含 `-DCM_COVERAGE_ENABLE`，或直接移除条件编译让覆盖率代码始终编译。
24. **⚠️ update_extern.py 生成的代码位置** — update_extern.py 在 `#include` 行之后插入覆盖率基础设施代码。如果 cm_atcmd_extern.c 已有其他 `#ifdef CM_COVERAGE_ENABLE` 块，脚本可能插入到错误位置导致重复定义。**验证**：插入后检查文件中是否只有一个 `extern volatile unsigned int cov_xxx_stmt_hits` 声明。
25. **⚠️ 重复定义全局变量导致 extern 链接断裂（2026-06-25 实战）** — cm_coverage.c 定义 `volatile unsigned int cov_pwm_stmt_hits = 0;` 后，cm_atcmd_pwm.c **不能再定义同名变量**。否则链接器当作两个不同变量：cm_cov_hit() 修改 cm_coverage.c 的版本，cm_atcmd_extern.c extern 引用 cm_atcmd_pwm.c 的版本。AT+COVERAGE? 始终显示 0。**修复**：cm_atcmd_pwm.c 只通过 `#include "cm_coverage.h"` 中的 extern 声明访问，不定义变量。
26. **⚠️ cm_coverage.c 未加入 .mak 编译列表** — 文件存在于 `onemo/at/src/` 目录但不会自动编译。必须在 .mak 中显式添加。**验证**：检查 `obj_PMD2NONE/obj_onemo_onemo/obj_onemo_at/` 下是否有 cm_coverage.o。如果没有，说明未加入构建。
27. **⚠️ 编译系统路径映射验证** — .d 文件中的 `W:\` 路径可能映射到 SDK 内部目录而非修改的 repos 目录。修改源码后必须用 `findstr` 验证编译用的文件是否包含修改内容。**终极验证**：在源码中硬编码一个已知值（如 `cov_pwm_stmt_hits = 99;`），编译后通过 AT 命令读取确认。

## ⚠️ 多模块覆盖率架构（PING 2026-06-26 实战验证）

当有多个模块（PWM + PING + ...）同时插桩时，**不能只用全局 `cm_cov_hit()`**。原因：

`cm_cov_hit()` 只递增 `cov_pwm_stmt_hits` / `cov_pwm_branch_hits`。AT+COVERAGE? 读的是 per-module 计数器（`cov_ping_stmt_hits` 等），但桩写的是全局 PWM 计数器 → PING 始终 0/N。

**正确架构**：全局 bitmap + 本地 hit 函数 + 本地计数器

### Step 1: cm_coverage.c 添加 `cm_cov_is_hit()`

```c
// 在 cm_coverage.c 中，#pragma O2 之前添加：
int cm_cov_is_hit(uint16_t stub_id) {
    unsigned int w;
    unsigned int b;
    if (stub_id >= COV_TOTAL_STUBS) return 0;
    w = stub_id / 32;
    b = stub_id % 32;
    return (cov_bitmap[w] & (1u << b)) ? 1 : 0;
}
```

cm_coverage.h 添加声明：
```c
extern int cm_cov_is_hit(uint16_t stub_id);
```

### Step 2: 模块 .c 用本地 hit 函数

```c
#define CM_COVERAGE_ENABLE
#include "cm_coverage.h"
#undef COV_STMT
#undef COV_BRANCH_T
#undef COV_BRANCH_F

volatile unsigned int cov_xxx_stmt_hits = 0;
volatile unsigned int cov_xxx_branch_hits = 0;

static void cm_cov_xxx_hit(uint16_t stub_id) {
    int already = cm_cov_is_hit(stub_id);
    cm_cov_hit(stub_id);           // 注册到全局 bitmap
    if (!already) {                 // 首次命中才计数
        if (stub_id >= COV_BRANCH_START) cov_xxx_branch_hits++;
        else cov_xxx_stmt_hits++;
    }
}

#define COV_STMT(id)        cm_cov_xxx_hit(id)
#define COV_BRANCH_T(id)    cm_cov_xxx_hit(id)
#define COV_BRANCH_F(id)    cm_cov_xxx_hit(id)
```

### Step 3: cm_atcmd_extern.c 添加 extern + sprintf

（已在上方"新模块必须更新 cm_atcmd_extern.c"章节详述）

### 为什么不能只用全局 cm_cov_hit()

- `cm_cov_hit()` 内部用 `cov_pwm_stmt_hits` / `cov_pwm_branch_hits`，不区分模块
- 多模块共享相同桩 ID 范围（如 stmt 100-199, branch 200+）时无法区分
- AT+COVERAGE? 读 per-module 计数器，但桩写全局计数器 → 除第一个模块外全部 0

### 快速诊断

AT+COVERAGE? 显示 PWM 有命中但 PING 为 0？→ 大概率是 PING 没用本地 hit 函数。

## ⚠️ 新模块三步漏一不可（PING 2026-06-26 实战）

新模块插桩后如果 AT+COVERAGE? 显示 0/N，按以下顺序排查：

### Step 1: CM_COVERAGE_ENABLE 必须在模块 .c 中定义

`cm_coverage.h` 的宏被 `#ifdef CM_COVERAGE_ENABLE` 包裹。如果模块 .c 文件不定义该宏，所有 COV_* 宏编译为 `((void)0)`。

**修复**：在模块 .c 文件的 `#include "cm_coverage.h"` 之前加：
```c
#define CM_COVERAGE_ENABLE
```

**验证**：`findstr CM_COVERAGE_ENABLE cm_atcmd_xxx.c` 应有输出。

### Step 2: 模块必须定义 cov_xxx_stmt_hits / cov_xxx_branch_hits 变量

`cm_atcmd_extern.c` 声明了 `extern volatile unsigned int cov_xxx_stmt_hits;`。如果模块 .c 文件没有定义这些变量，链接器报：
```
Error: L6218E: Undefined symbol cov_xxx_stmt_hits (referred from cm_atcmd_extern.o)
```

**修复**：在模块 .c 文件中（`#include "cm_coverage.h"` 之后）添加：
```c
volatile unsigned int cov_xxx_stmt_hits = 0;
volatile unsigned int cov_xxx_branch_hits = 0;
```

### Step 3: cm_atcmd_extern.c 必须有 extern + sprintf

（已在上方"新模块必须更新 cm_atcmd_extern.c"章节详述）

### 快速诊断脚本

当 AT+COVERAGE? 显示 0/N 时，用以下脚本在服务器上快速排查：

```python
import re

def check_module(module_c, extern_c, module_name):
    with open(module_c, 'r', encoding='latin-1') as f:
        src = f.read()
    with open(extern_c, 'r', encoding='latin-1') as f:
        ext = f.read()

    issues = []
    # Check 1: CM_COVERAGE_ENABLE
    if 'CM_COVERAGE_ENABLE' not in src:
        issues.append('❌ 缺少 #define CM_COVERAGE_ENABLE')
    # Check 2: cov_xxx variables defined
    if f'cov_{module_name}_stmt_hits' not in src:
        issues.append(f'❌ 缺少 cov_{module_name}_stmt_hits 定义')
    # Check 3: extern in cm_atcmd_extern.c
    if f'cov_{module_name}_stmt_hits' not in ext:
        issues.append(f'❌ cm_atcmd_extern.c 缺少 extern 声明')
    # Check 4: sprintf format
    if module_name.upper() not in ext:
        issues.append(f'❌ cm_atcmd_extern.c sprintf 缺少 {module_name.upper()} 格式')

    if not issues:
        print(f'✅ {module_name} 模块检查通过')
    else:
        print(f'❌ {module_name} 模块问题：')
        for i in issues:
            print(f'  {i}')

# 使用示例
check_module(
    r'C:\...\SDK\onemo\at\src\cm_atcmd_ping.c',
    r'C:\...\SDK\onemo\at\src\cm_atcmd_extern.c',
    'ping'
)
```

## ⚠️ 死代码文件不在构建系统中（DNS 2026-06-26 实战）

插桩前必须确认目标文件参与编译。有些 .c 文件存在于 SDK 目录中但不在 .mak 构建列表中，属于死代码。

**DNS 实战**：`cm_plat_dns.c` 插桩了 28 个桩（12 stmt + 16 branch），但该文件不在构建系统的 .mak 中，桩永远不会被编译执行。

**验证方法**：
1. 检查 .mak 文件中是否包含目标源文件：`findstr /i "cm_xxx" *.mak`
2. 检查 obj 目录下是否有对应的 .o 文件：`dir /s obj_PMD2NONE\*cm_xxx*.o`
3. 如果 .o 不存在且 .mak 中没有该文件 → 死代码，插桩无效

**预防**：插桩前先确认文件在构建列表中，再分配桩 ID。

## 验证清单

- [ ] 插桩文件编译通过（0 error, 0 warning）
- [ ] 模块 .c 有 `#define CM_COVERAGE_ENABLE`
- [ ] 模块 .c 有 `volatile unsigned int cov_xxx_stmt_hits = 0;` 定义
- [ ] cm_atcmd_extern.c 有 extern 声明
- [ ] cm_atcmd_extern.c 的 sprintf 有新模块格式
- [ ] AT+COVERAGE? 显示正确的总桩数（EXT+MQTT+HTTP+...）
- [ ] 执行几条 AT 命令后新模块桩数 > 0
- [ ] coverage_map.json 生成且桩数与实际一致
- [ ] 无 unreachable / expected a statement / too few arguments 错误
- [ ] 无 L6218E Undefined symbol 链接错误