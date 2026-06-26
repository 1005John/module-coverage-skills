# .h/.c 分离模式覆盖率桩实现

## 背景

armcc 5.05 的 -O2 优化会把同一编译单元中的覆盖率桩函数体完全优化掉，
即使变量声明为 volatile、函数声明为非 static。

## 解决方案

将覆盖率桩实现放在独立的编译单元（cm_coverage.c），用 #pragma O0 保护。

### cm_coverage.h

```c
#ifndef CM_COVERAGE_H
#define CM_COVERAGE_H
#include <stdint.h>

#define COV_TOTAL_STUBS   50        /* >= 最大桩 ID + 1 */
#define COV_BITMAP_WORDS  ((COV_TOTAL_STUBS + 31) / 32)
#define COV_BRANCH_START  200       /* branch 桩起始 ID */

#define COV_STMT(id)        cm_cov_hit(id)
#define COV_BRANCH_T(id)    cm_cov_hit(id)
#define COV_BRANCH_F(id)    cm_cov_hit(id)

extern volatile unsigned int cov_pwm_stmt_hits;
extern volatile unsigned int cov_pwm_branch_hits;
extern void cm_cov_hit(uint16_t stub_id);

#endif
```

### cm_coverage.c

```c
#include "cm_coverage.h"

volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;
static unsigned int cov_bitmap[COV_BITMAP_WORDS] = {0};

#pragma O0
void cm_cov_hit(uint16_t stub_id) {
    unsigned int w, b;
    if (stub_id >= COV_TOTAL_STUBS) return;
    w = stub_id / 32;
    b = stub_id % 32;
    if (!(cov_bitmap[w] & (1u << b))) {
        cov_bitmap[w] |= (1u << b);
        if (stub_id < COV_BRANCH_START) cov_pwm_stmt_hits++;
        else cov_pwm_branch_hits++;
    }
}
#pragma O2
```

### cm_atcmd_xxx.c（模块源码）

```c
#include "cm_coverage.h"
// ... 其他 include ...

RETURNCODE_T cmMPWMCFG(...) {
    COV_STMT(100);  // 函数入口
    // ...
    if (condition) {
        COV_BRANCH_T(200);  // 分支
        // ...
    }
}
```

## 关键 Pitfalls

1. **变量只能定义一次** — `cov_pwm_stmt_hits` 只在 cm_coverage.c 中定义，
   cm_atcmd_xxx.c 通过 cm_coverage.h 的 extern 声明访问。重复定义会导致
   链接器创建两个不同变量，写入一个读不到另一个。

2. **#pragma O0 必须保护 cm_cov_hit** — armcc -O2 会优化掉函数体中的
   volatile 变量写入。#pragma O0 禁用该函数的优化。

3. **cm_atcmd_def.h 必须注册 AT 命令 handler** — 如果 AT+COVERAGE? 返回
   空（不是 ERROR），说明命令已注册但 handler 是 NULL。需要把 cmCOVERAGE
   函数指针填入 utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND 的参数中。

4. **AT+COVERAGE? 的 ATRESP 不能调用两次** — GET_CMD handler 中只能调用
   一次 ATRESP(atHandle, OK, 0, output)。如果在子函数中调用一次再在
   handler 中调用一次，第二次会覆盖第一次的输出。

5. **cm_coverage.o 必须在链接列表中** — 检查
   onemo-at_pk_objliblist.txt 是否包含 cm_coverage.o。

6. **固件打包必须用 SDK 原生 release ZIP** — package_firmware.py 创建的
   ZIP 格式与 adownload.exe 不兼容。必须用 SDK/target/ 下的
   *_release.zip 直接烧录。

## 验证方法

1. 在模块函数中硬编码 `cov_pwm_stmt_hits = 42;`
2. 编译烧录后 AT+COVERAGE? 应显示 42/30
3. 如果显示 0/30，说明变量链接有问题
4. 移除硬编码，用 cm_cov_hit() 测试
5. 如果硬编码=42 有效但 cm_cov_hit 无效，说明函数被优化掉了
