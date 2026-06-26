# 多模块覆盖率修复记录 (2026-06-26)

## 问题

PWM 模块覆盖率正常（26/30 = 87%），但 PING 模块始终 0/15。

## 排查时间线

1. AT+COVERAGE? 显示 `PING(0%,0%,0/15)` — 桩总数正确但命中为 0
2. 确认 `#define CM_COVERAGE_ENABLE` 在 cm_atcmd_ping.c 中 — OK
3. 确认 `cov_ping_stmt_hits` 变量已定义 — OK
4. 确认 cm_atcmd_extern.c 有 extern + sprintf — OK
5. 预处理器输出 (.ppp) 显示 `cm_cov_hit(100)` 等调用 — 宏展开正确
6. fromelf 反汇编确认 .o 有 `BL cm_cov_hit` 指令 — 编译正确
7. **根因**：`cm_cov_hit()` 只递增 `cov_pwm_stmt_hits` / `cov_pwm_branch_hits`，不递增 `cov_ping_*`。AT+COVERAGE? 读 `cov_ping_stmt_hits`（始终为 0）

## 修复方案

### cm_coverage.c 添加 cm_cov_is_hit()

```c
int cm_cov_is_hit(uint16_t stub_id) {
    unsigned int w, b;
    if (stub_id >= COV_TOTAL_STUBS) return 0;
    w = stub_id / 32;
    b = stub_id % 32;
    return (cov_bitmap[w] & (1u << b)) ? 1 : 0;
}
```

### cm_coverage.h 添加声明

```c
extern int cm_cov_is_hit(uint16_t stub_id);
```

### cm_atcmd_ping.c 使用本地 hit 函数

```c
#define CM_COVERAGE_ENABLE
#include "cm_coverage.h"
#undef COV_STMT
#undef COV_BRANCH_T
#undef COV_BRANCH_F

volatile unsigned int cov_ping_stmt_hits = 0;
volatile unsigned int cov_ping_branch_hits = 0;

static void cm_cov_ping_hit(uint16_t stub_id) {
    int already = cm_cov_is_hit(stub_id);
    cm_cov_hit(stub_id);
    if (!already) {
        if (stub_id >= 200) cov_ping_branch_hits++;
        else cov_ping_stmt_hits++;
    }
}

#define COV_STMT(id)        cm_cov_ping_hit(id)
#define COV_BRANCH_T(id)    cm_cov_ping_hit(id)
#define COV_BRANCH_F(id)    cm_cov_ping_hit(id)
```

## 关键教训

1. **全局 cm_cov_hit() 不能区分模块** — 它用固定的 `cov_pwm_*` 计数器
2. **多模块必须用本地 hit 函数** — 通过 `cm_cov_is_hit()` 检查首次命中
3. **cm_cov_is_hit() 必须加到 cm_coverage.c** — 原文件没有这个函数
4. **#undef + #define 覆盖宏** — 让 COV_* 宏调用本地函数而非全局函数

## 修复后结果

```
PING: 100% 语句, 30% 分支, 6/15 总桩
ALL:  8% 语句, 17% 分支, 12/45 总桩 (PWM 30 + PING 15)
```

PWM 不受影响（仍用全局 cm_cov_hit()，计数器正确）。
