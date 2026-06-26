# 添加新模块到覆盖率系统 — 完整 Checklist

当需要对一个新模块（如 HTTP、TCP、SSL）进行覆盖率插桩时，除了插桩源码本身，
还需要修改 cm_atcmd_extern.c 和 cm_coverage.h。遗漏任何一步都会导致覆盖率
不显示或计数错误。

## 必须修改的文件清单

假设新模块名为 `xxx`，桩 ID 范围 STMT=500-699, BRANCH=3000-3199：

| # | 文件 | 修改内容 | 忘记的后果 |
|---|------|----------|-----------|
| 1 | `onemo/at/inc/cm_coverage.h` | `COV_TOTAL_STUBS` 必须 >= 最大桩 ID+1 | 桩被 `cm_cov_hit()` 静默丢弃 |
| 2 | `onemo/at/src/cm_atcmd_extern.c` | 添加 `extern volatile unsigned int cov_xxx_stmt_hits;` | AT+COVERAGE? 不显示新模块 |
| 3 | `onemo/at/src/cm_atcmd_extern.c` | GET_CMD 的 sprintf 添加 `XXX(%lu%%,%lu%%,%lu/%lu)` | 同上 |
| 4 | `onemo/at/src/cm_atcmd_extern.c` | `output` buffer 从 64 扩大到 256 | sprintf 溢出 → 模组 crash |
| 5 | `onemo/at/src/cm_atcmd_extern.c` | `COV_TOTAL_STUBS` 也需 >= 最大桩 ID+1 | 本地 `cm_cov_hit()` 丢弃桩 |
| 6 | `onemo/at/src/cm_atcmd_xxx.c` | `#include "cm_coverage.h"` + `#undef/#define` | 桩调用错误的 hit 函数 |
| 7 | `onemo/at/src/cm_atcmd_xxx.c` | 定义本地计数器 + 独立 bitmap | 计数器显示 >100% |

## 关键架构：两套 cm_cov_hit()

```
cm_coverage.c:     cm_cov_hit()     → 使用全局 bitmap + 全局计数器
cm_atcmd_extern.c: cm_cov_hit()     → 使用本地 bitmap + 本地计数器（覆盖！）
cm_atcmd_xxx.c:    cm_cov_xxx_hit() → 使用独立 bitmap + 独立计数器
```

**cm_atcmd_extern.c 中有它自己的 `cm_cov_hit()` 实现**，与 cm_coverage.c 的不同。
它有自己的 `COV_TOTAL_STUBS`、`cov_bitmap[]`、`cov_stmt_hits`。
这意味着：
- 从 cm_atcmd_xxx.c 调用 `cm_cov_hit(id)` 会调用 extern.c 的版本
- 两个文件的 `COV_TOTAL_STUBS` 必须一致
- 新模块不能直接用 `cm_cov_hit()` 的返回值判断是否首次命中

## 计数器 >100% 的根因与修复

**问题**：如果 cm_atcmd_xxx.c 的 `cm_cov_xxx_hit()` 直接调用 `cm_cov_hit()` 然后
无条件递增 `cov_xxx_stmt_hits`，每次触发都 +1（不是首次命中），导致 >100%。

**修复**：新模块使用独立 bitmap 判断首次命中：

```c
static unsigned int cov_xxx_bitmap[(COV_TOTAL_STUBS + 31) / 32] = {0};
volatile unsigned int cov_xxx_stmt_hits = 0;
volatile unsigned int cov_xxx_branch_hits = 0;

static void cm_cov_xxx_hit(uint16_t stub_id) {
    unsigned int w = stub_id / 32;
    unsigned int b = stub_id % 32;
    if (cov_xxx_bitmap[w] & (1u << b)) return;  /* 已命中，跳过 */
    cov_xxx_bitmap[w] |= (1u << b);
    cm_cov_hit(stub_id);  /* 同时注册到全局 bitmap */
    if (stub_id >= 3000) cov_xxx_branch_hits++;
    else cov_xxx_stmt_hits++;
}
```

## cm_atcmd_extern.c 的 sprintf 修改模板

在 GET_CMD case 中，现有格式：
```
+COVERAGE: EXT(...) MQTT(...) ALL(...)
```

改为：
```
+COVERAGE: EXT(...) MQTT(...) XXX(...) ALL(...)
```

需要：
1. 添加 `extern volatile unsigned int cov_xxx_stmt_hits;`
2. 添加 `extern volatile unsigned int cov_xxx_branch_hits;`
3. 在 `_all_total` 计算后添加 `_xxx_stmt/branch/total` 并加到 `_all_*`
4. sprintf 格式字符串添加 `XXX(%lu%%,%lu%%,%lu/%lu)` 段
5. `output` buffer 扩大到 256（每新增一个模块都需要检查）

## instrument.py 生成文件修复（关键！）

如果使用 `instrument.py` 自动插桩，生成的模块 .c 文件会包含独立的桩实现（`#ifdef CM_COVERAGE_ENABLE` 块）。**必须手动修复**才能与全局覆盖率系统连通：

### 方案 A：使用全局 cm_cov_hit()（简单，适合单模块测试）

1. 删除生成的 `#ifdef CM_COVERAGE_ENABLE ... #endif` 整个块（含 `cm_cov_xxx_hit()` 函数、bitmap、计数器）
2. 在 `#include` 区域添加 `#include "cm_coverage.h"`
3. 确认 `cm_coverage.h` 的 `COV_TOTAL_STUBS` > 模块最大桩 ID
4. 重新编译

### 方案 B：使用独立本地 hit 函数（推荐，适合多模块）

1. 保留 `#include "cm_coverage.h"`
2. 在其后添加 `#undef COV_STMT` / `#undef COV_BRANCH_T` / `#undef COV_BRANCH_F`
3. 定义本地 `cm_cov_xxx_hit()` 函数（含独立 bitmap + `cm_cov_hit()` 调用）
4. 重新 `#define COV_STMT(id) cm_cov_xxx_hit(id)` 等
5. 在 `cm_atcmd_extern.c` 中添加 extern 声明 + sprintf 格式

### COV_TOTAL_STUBS 快速验证

编译前必须检查：
```bash
# 查看实际值
grep COV_TOTAL_STUBS SDK/onemo/at/inc/cm_coverage.h
# 查看模块最大桩 ID
grep -oP 'COV_\w+\(\K\d+' SDK/onemo/at/src/cm_atcmd_xxx.c | sort -n | tail -1
```

如果 COV_TOTAL_STUBS < 最大桩 ID，cm_cov_hit() 会静默丢弃所有桩，AT+COVERAGE? 始终显示 0。

## 常见 Pitfalls

1. **忘记同步 COV_TOTAL_STUBS** — cm_coverage.h 和 cm_atcmd_extern.c 都有，必须都改
2. **忘记删 .o 缓存** — 改 .h 后必须删 obj_PMD2NONE/inc/ 下的缓存副本
3. **独立 bitmap 大小** — `(COV_TOTAL_STUBS + 31) / 32` 个 uint32，不是字节数
4. **cm_atcmd_extern.c 的 output[64]** — 每加一个模块就检查一次，超了就扩大
5. **sprintf 参数数量** — 格式字符串的 %lu 数必须与参数数严格一致
