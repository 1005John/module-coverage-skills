# ARM Compiler 5 覆盖率插桩 Pitfalls（实战验证）

## 1. 编译器优化导致桩函数不生效（根因 #1）

**现象**：COV_STMT 宏展开为 cm_cov_hit(id) 调用，AT 命令正常执行，但覆盖率计数器始终为 0。

**根因**：armcc 5.05 (-O2) 对 `static` 函数进行跨过程优化。即使变量声明为 `volatile`，
如果函数是 `static` 且没有外部代码读取其结果，编译器可能优化掉函数体中的 increment 操作。

**解决方案**：使用 .h/.c 分离模式，将 cm_cov_hit() 放在独立编译单元中：

```c
/* cm_coverage.h */
#ifndef CM_COVERAGE_H
#define CM_COVERAGE_H
#include <stdint.h>

#define COV_TOTAL_STUBS   50
#define COV_BRANCH_START  200

#define COV_STMT(id)        cm_cov_hit(id)
#define COV_BRANCH_T(id)    cm_cov_hit(id)
#define COV_BRANCH_F(id)    cm_cov_hit(id)

extern volatile unsigned int cov_pwm_stmt_hits;
extern volatile unsigned int cov_pwm_branch_hits;
extern void cm_cov_hit(uint16_t stub_id);

#endif
```

```c
/* cm_coverage.c */
#include "cm_coverage.h"

volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;
static unsigned int cov_bitmap[(COV_TOTAL_STUBS + 31) / 32] = {0};

#pragma O0  /* 必须！armcc 仍然可能优化独立编译单元 */
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

**验证方法**：在 cm_atcmd_xxx.c 中直接写入 `cov_pwm_stmt_hits = 99;`，编译后
AT+COVERAGE? 应显示 99/30。如果仍为 0，说明链接有问题。

## 2. 全局变量重复定义（根因 #2）

**现象**：cm_coverage.c 和 cm_atcmd_pwm.c 都定义了 `volatile unsigned int cov_pwm_stmt_hits = 0;`。
cm_cov_hit() 修改的是 cm_coverage.c 的副本，cm_atcmd_extern.c extern 引用的是另一个副本。

**根因**：C 语言中，同一全局变量在多个翻译单元中定义是未定义行为。armcc 链接器
可能创建两个独立符号。

**修复**：变量只在 cm_coverage.c 中定义一次。其他文件通过 `#include "cm_coverage.h"`
使用 extern 声明访问。

**验证**：在 cm_atcmd_pwm.c 中写入 `cov_pwm_stmt_hits = 55;`，AT+COVERAGE? 应显示 55/30。
如果为 0，说明跨文件变量访问有问题（变量重复定义）。

## 3. AT+COVERAGE? 命令处理

### 3.1 ATRESP 只能调用一次

**错误模式**：
```c
static void cm_coverage_query(unsigned int atHandle) {
    // ... 计算 ...
    ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);  // 第一次
}
case TEL_EXT_GET_CMD:
    cm_coverage_query(atHandle);
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, "");  // 第二次 → 覆盖第一次
```

**正确模式**：将计算内联到 GET_CMD，只调用一次 ATRESP：
```c
case TEL_EXT_GET_CMD: {
    char output[128];
    // ... 计算 ...
    sprintf(output, "+COVERAGE: PWM(%lu%%,%lu%%,%lu/%lu) ALL(...)");
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);
    break;
}
```

### 3.2 cm_atcmd_def.h handler 注册

AT 命令必须在 cm_atcmd_def.h 中注册 handler，否则命令返回 ERROR 或空响应：
```c
// 错误：handler 全是 NULL
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, NULL, NULL, NULL),

// 正确：注册 cmCOVERAGE handler
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, cmCOVERAGE, cmCOVERAGE, cmCOVERAGE),
```

### 3.3 函数声明位置

cmCOVERAGE 函数声明必须在 `#ifdef` 块外部，否则某些编译配置下不可见。

## 4. 编译与链接

### 4.1 .mak 文件不直接列出源文件

armcc 构建系统通过 `onemo-at_pk_objliblist.txt` 列出链接的 .o 文件。
新增 .c 文件（如 cm_coverage.c）编译后，需要手动将其 .o 添加到此列表。

检查方法：
```
findstr cm_coverage <SDK>\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\onemo-at_pk_objliblist.txt
```

### 4.2 强制重新编译

增量编译（DC）时，删除 .o + .d + .pp + pack_c.via 强制重编：
```cmd
del /q obj_onemo_at\cm_atcmd_pwm.o obj_onemo_at\cm_atcmd_pwm.d obj_onemo_at\cm_atcmd_pwm.pp
del /q obj_onemo_at\pack_c.via
```

只删 .d/.pp 不删 .o → gnumake 看 .o 时间戳新于源码就不重编。

### 4.3 源码路径映射

编译系统使用 W: 映射驱动器。`.d` 文件显示实际编译路径：
```
W:\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at/cm_atcmd_pwm.o : W:\onemo\at\src\cm_atcmd_pwm.c
```

确保修改的文件在 W: 映射的目录中。

## 5. 固件打包

**不要用自定义 Python 脚本打包固件 ZIP**。使用 SDK 原生的 `ML302A_package.bat`，
它调用 `arelease` 工具创建 adownload.exe 能识别的格式。

自定义 ZIP（如 package_firmware.py）虽然内部文件相同，但 adownload.exe 可能
无法正确处理（烧录卡住或固件异常）。

原生 release ZIP 路径：
```
SDK\target\<buildver>\<buildver>_<version>_release.zip
```

## 6. 调试技巧

| 问题 | 诊断方法 |
|------|----------|
| 覆盖率始终为 0 | 在 .c 中直接写 `cov_pwm_stmt_hits = 99;` 测试变量链接 |
| AT+COVERAGE? 返回空 | 检查 cm_atcmd_def.h handler 是否为 NULL |
| AT+COVERAGE? 返回 ERROR | 检查 SET_CMD 参数解析 |
| 固件烧录后功能异常 | 用 SDK 原生 release ZIP，不用自定义打包 |
| 编译后修改不生效 | 删除 .o + pack_c.via 重新编译 |
