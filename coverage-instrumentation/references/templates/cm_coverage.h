/**
 * @file    cm_coverage.h
 * @brief   覆盖率桩宏定义 — .h/.c 分离模式
 *
 * .h: 宏 + extern 声明
 * .c: 变量定义 + 函数实现
 *
 * volatile 策略：
 *   cov_bitmap      — 非 volatile（memset 清零需要非 volatile 指针）
 *   cov_stmt_hits   — volatile（防编译器优化）
 *   cov_branch_hits — 同上
 *
 * 使用：
 *   1. cm_coverage.c 放在 onemo/coverage/src/
 *   2. 本文件放在 onemo/at/inc/
 *   3. 各 .c 文件 #include "cm_coverage.h"
 *   4. 编译时 -DCM_COVERAGE_ENABLE
 *   5. 模块用本地 hit 函数时 #include 后 #undef + #define
 */
#ifndef CM_COVERAGE_H
#define CM_COVERAGE_H

#include <stdint.h>

#ifdef CM_COVERAGE_ENABLE

#define COV_TOTAL_STUBS   2500
#define COV_BITMAP_WORDS  ((COV_TOTAL_STUBS + 31) / 32)
#define COV_BRANCH_START  1100

#define COV_STMT(id)        cm_cov_hit(id)
#define COV_BRANCH_T(id)    cm_cov_hit(id)
#define COV_BRANCH_F(id)    cm_cov_hit(id)

extern void     cm_cov_hit(uint16_t stub_id);
extern int      cm_cov_is_hit(uint16_t stub_id);
extern void     cm_cov_init(void);
extern void     cm_cov_enable(int enable);
extern uint32_t cm_cov_get_stmt_hits(void);
extern uint32_t cm_cov_get_branch_hits(void);
extern uint32_t cm_cov_get_total_stubs(void);

#else
#define COV_STMT(id)        ((void)0)
#define COV_BRANCH_T(id)    ((void)0)
#define COV_BRANCH_F(id)    ((void)0)
#endif

#endif
