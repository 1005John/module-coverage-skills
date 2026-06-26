# ARM Compiler 5 覆盖率桩优化陷阱

## 问题描述

armcc 5.05 的 -O2 优化会**吃掉覆盖率桩的 increment 操作**，即使变量声明为 `volatile`。

## 症状

- AT+COVERAGE? 返回 0/N（桩数正确但命中数始终为 0）
- 调试计数器（DBG=N）正常递增（函数被调用）
- 直接写入变量（`cov_pwm_stmt_hits = 99`）能被 AT+COVERAGE? 读到
- 说明 extern 链接正确，但 cm_cov_hit() 内部的 increment 被优化掉

## 根因分析

armcc 看到以下条件时会优化掉 increment：
1. 函数是 `static`（可以内联）
2. 修改的变量没有被本文件其他代码读取
3. 即使变量是 `volatile`，内联后编译器仍可能认为写操作是 dead code
4. 即使函数非 static + #pragma O0，在某些情况下仍被优化

## 解决方案：.h/.c 分离模式 + #pragma O0

### 架构

```
cm_coverage.h  → 宏定义 + extern 声明
cm_coverage.c  → cm_cov_hit() 实现（独立编译单元）
cm_atcmd_pwm.c → #include "cm_coverage.h"，使用 COV_STMT 宏
```

### cm_coverage.h 模板

```c
#ifndef CM_COVERAGE_H
#define CM_COVERAGE_H

#include <stdint.h>

/* 桩 ID 范围配置 */
#define COV_PWM_TOTAL       40
#define COV_PWM_BRANCH_START 200

/* 宏定义 - 各模块 include 后使用 */
#define COV_STMT(id)      cm_cov_hit(id)
#define COV_BRANCH_T(id)  cm_cov_hit(id)
#define COV_BRANCH_F(id)  cm_cov_hit(id)

/* extern 声明 - 供 cm_atcmd_extern.c 引用 */
extern volatile unsigned int cov_pwm_stmt_hits;
extern volatile unsigned int cov_pwm_branch_hits;

/* 函数声明 */
void cm_cov_hit(unsigned short id);

#endif
```

### cm_coverage.c 模板

```c
#include "cm_coverage.h"

volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;

static unsigned int cov_bitmap[(COV_PWM_TOTAL + 31) / 32] = {0};

#pragma O0
void cm_cov_hit(unsigned short id) {
    unsigned int w = id / 32;
    unsigned int b = id % 32;
    if (!(cov_bitmap[w] & (1u << b))) {
        cov_bitmap[w] |= (1u << b);
        if (id < COV_PWM_BRANCH_START) cov_pwm_stmt_hits++;
        else cov_pwm_branch_hits++;
    }
}
#pragma O2
```

### cm_atcmd_pwm.c 修改

```c
#include "cm_coverage.h"  // 包含宏定义和 extern 声明

// 不要定义 cov_pwm_stmt_hits 等变量！只通过 extern 访问
// 不要定义 cm_cov_hit()！只通过宏调用

RETURNCODE_T cmMPWMCTRL(...) {
    COV_STMT(100);  // 展开为 cm_cov_hit(100)
    // ...
}
```

## 关键约束

1. **禁止重复定义变量** — cm_coverage.c 定义 `cov_pwm_stmt_hits`，cm_atcmd_pwm.c 不能再次定义
2. **cm_coverage.c 必须加入 .mak** — 否则不会被编译进固件
3. **#pragma O0 必须保护 cm_cov_hit** — 即使在独立编译单元中
4. **cm_atcmd_extern.c 的 extern 声明必须与 cm_coverage.h 一致**

## 调试流程

1. AT+COVERAGE? 返回 ERROR → 命令未注册
2. AT+COVERAGE? 返回空 → sprintf/ATRESP 问题
3. AT+COVERAGE? 返回 0/N → 桩未触发
4. 在 cm_coverage.c 中硬编码 `cov_pwm_stmt_hits = 99;` →
   - 显示 99: cm_coverage.c 已编译，问题在 cm_cov_hit()
   - 显示 0: cm_coverage.c 未编译或 extern 链接断裂
5. 检查 cm_atcmd_pwm.c 是否有重复变量定义
6. 检查 .mak 是否包含 cm_coverage.c
