# cm_atcmd_extern.c 修改指南

## 为什么必须修改

`AT+COVERAGE?` 的 GET_CMD 在 `cm_atcmd_extern.c` 中实现。它通过 extern 声明访问各模块的计数器，然后用 sprintf 输出所有模块的覆盖率。

如果只修改模块源码（添加计数器和 bitmap），不修改 `cm_atcmd_extern.c`，`AT+COVERAGE?` 不会显示新模块。

## 修改位置（三处 + 命令注册）

### 1. extern 声明（文件开头 ~42-58 行）

```c
#ifdef CM_COVERAGE_ENABLE
extern volatile unsigned int cov_mqtt_stmt_hits;
extern volatile unsigned int cov_mqtt_branch_hits;
// ... 已有模块 ...
extern volatile unsigned int cov_xxx_stmt_hits;  // 新增
extern volatile unsigned int cov_xxx_branch_hits; // 新增
#endif
```

**⚠️ volatile 必须与模块源码一致**：如果模块源码用 `volatile unsigned int`，extern 也必须用 `volatile unsigned int`。

### 2. 变量声明（GET_CMD case 内）

```c
unsigned long _xxx_stmt = cov_xxx_stmt_hits;
unsigned long _xxx_branch = cov_xxx_branch_hits;
unsigned long _xxx_total = STMT_COUNT + BRANCH_COUNT;
_all_stmt += _xxx_stmt;
_all_branch += _xxx_branch;
_all_total += _xxx_total;
```

### 3. sprintf 格式字符串和参数

```c
sprintf(output, "+COVERAGE: EXT(...) ... XXX(%lu%%,%lu%%,%lu/%lu) ALL(...)",
    (unsigned long)(_xxx_total > 0 ? (_xxx_stmt * 100) / STMT_COUNT : 0),
    (unsigned long)(_xxx_total > 0 ? (_xxx_branch * 100) / BRANCH_COUNT : 0),
    _xxx_stmt + _xxx_branch, _xxx_total,
    ...);
```

### 4. AT 命令注册（cm_atcmd_def.h）

**关键！** 必须在 `cm_atcmd_def.h` 中注册 AT+COVERAGE 命令并链接 handler 函数：

```c
// ❌ 错误：handler 全为 NULL，命令被解析但不执行
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, NULL, NULL, NULL),

// ✅ 正确：链接 cmCOVERAGE handler
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, cmCOVERAGE, cmCOVERAGE, cmCOVERAGE),
```

参数顺序（VSYNTAX 变体）：`name, syntax, params, set_handler, get_handler, test_handler`

## ATRESP 调用规则（关键 Pitfall）

**只调用一次 ATRESP！** 如果在辅助函数中调用 ATRESP 发送数据，然后在 handler 中又调用一次，第二次会覆盖第一次，导致返回空。

```c
// ❌ 错误：两次 ATRESP
static void cm_coverage_query(unsigned int atHandle) {
    sprintf(output, "+COVERAGE: ...", ...);
    ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);  // 第一次
}
case TEL_EXT_GET_CMD: {
    cm_coverage_query(atHandle);
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, "");  // 第二次，覆盖！
    break;
}

// ✅ 正确：内联计算，只调用一次
case TEL_EXT_GET_CMD: {
    char output[128];
    // ... 计算逻辑 ...
    sprintf(output, "+COVERAGE: ...", ...);
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);  // 唯一一次
    break;
}
```

## volatile 关键字（ARM 编译器优化陷阱）

模块源码中的计数器必须声明为 `volatile`，否则 ARM armcc 会优化掉 increment：

```c
// ✅ 正确
volatile unsigned int cov_pwm_stmt_hits = 0;

// ❌ 错误（armcc 优化掉 ++）
unsigned int cov_pwm_stmt_hits = 0;
```

**现象**：AT+COVERAGE? 返回 0/N，执行 AT 命令后仍为 0。
**验证**：添加调试计数器 `volatile unsigned int dbg_count = 0;`，在函数入口 `dbg_count++`。如果 DBG 递增但覆盖率为 0 → volatile 问题。

## cmCOVERAGE 函数声明位置

cmCOVERAGE 的函数声明必须在 `#ifdef` 条件编译块**外面**。如果声明在 `#ifdef VOLTE_ENABLE` 内部，cm_atcmd_def.h 无法引用它，handler 注册会失败。

## 文件编码

Windows 上的 `cm_atcmd_extern.c` 使用 **latin-1** 编码（或 GBK）。
Python 读写时必须指定 `encoding='latin-1'`，否则会报 `UnicodeDecodeError`。

```python
with open(path, 'r', encoding='latin-1') as f:
    content = f.read()
# ... 修改 ...
with open(path, 'w', encoding='latin-1') as f:
    f.write(content)
```

## #ifdef CM_COVERAGE_ENABLE 注意事项

如果覆盖率代码被 `#ifdef CM_COVERAGE_ENABLE` 包裹，编译时必须定义该宏。建议在服务器 Agent 的插桩流程中确认编译命令包含 `-DCM_COVERAGE_ENABLE`，或直接移除条件编译让覆盖率代码始终编译。

## 常见错误

1. **忘记修改 cm_atcmd_extern.c** → AT+COVERAGE? 不显示新模块
2. **使用 utf-8 编码读写** → UnicodeDecodeError: 'gbk' codec can't decode
3. **sprintf 参数数量不匹配** → 编译报错或输出乱码
4. **忘记清理 .o 和 pack_c.via** → 增量编译不重编
5. **ATRESP 双重调用（2026-06-25 实战）** — 如果在辅助函数 cm_coverage_query() 中调用 ATRESP 发送数据，然后在 cmCOVERAGE() 的 GET_CMD 中又调用一次 ATRESP(atHandle, OK, 0, "")，第二次会覆盖第一次导致返回空。**修复**：只在 GET_CMD 中调用一次 ATRESP。辅助函数只负责填充 output buffer，不调用 ATRESP。或将计算逻辑直接内联到 GET_CMD 中。
6. **handler 全为 NULL（2026-06-25 实战）** — cm_atcmd_def.h 中 AT+COVERAGE 注册时 handler 全为 NULL，命令被解析但不执行。必须链接 cmCOVERAGE 函数。
7. **cmCOVERAGE 声明在 #ifdef 块内（2026-06-25 实战）** — 如果在 `#ifdef VOLTE_ENABLE` 内，cm_atcmd_def.h 无法引用。必须移到 #ifdef 外面。
8. **#ifdef CM_COVERAGE_ENABLE 未定义** → 所有覆盖率代码被编译掉。建议移除条件编译，让覆盖率代码始终编译。
9. **volatile 缺失** → ARM armcc 优化掉 increment，覆盖率始终为 0。模块源码和 extern 声明都必须用 `volatile unsigned int`
10. **变量重复定义（2026-06-25 实战）** — cm_coverage.c 和 cm_atcmd_pwm.c 都定义了 `cov_pwm_stmt_hits`，链接器创建两个不同符号。cm_cov_hit() 修改的是 cm_coverage.c 的版本，extern 引用的是另一个 → 覆盖率始终为 0。**修复**：只在 cm_coverage.c 中定义变量，cm_atcmd_pwm.c 只 include 头文件。
11. **cm_coverage.o 未加入链接列表（2026-06-25 实战）** — 编译成功但链接时遗漏。检查 `onemo-at_pk_objliblist.txt` 是否包含 cm_coverage.o。

## 验证步骤

1. 修改 cm_atcmd_extern.c（三处）
2. 修改 cm_atcmd_def.h（命令注册）
3. 清理缓存：`del /q obj_dir\cm_atcmd_extern.*`
4. 清理 pack_c.via：`del /q obj_dir\pack_c.via`
5. 编译：`cd /d SDK && cmd /c ML307R.bat DC`
6. 烧录并验证：
   - `AT+COVERAGE?` 应返回 `+COVERAGE: XXX(0%,0%,0/N) ALL(0%,0%,0/N)`
   - `AT+COVERAGE=1` 应返回 OK
   - 执行 AT 命令后再查询，命中数应 > 0
