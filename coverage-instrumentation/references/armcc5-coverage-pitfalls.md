# ARM Compiler 5 覆盖率插桩 Pitfalls（2026-06-25 PWM 实战）

## 1. armcc 优化掉 static 函数中的 volatile 写入

**现象**：cm_cov_hit() 函数被调用（调试计数器递增），但 volatile 变量（cov_pwm_stmt_hits）始终为 0。

**根因**：armcc -O2 对 static 函数进行激进优化。即使变量声明为 volatile，如果函数是 static 且编译器判断写入无外部可观测效果，仍可能优化掉 increment。

**尝试过的修复（均无效）**：
- `volatile` 关键字 → 无效
- 非 static 函数 → 无效
- `#pragma O0` 保护函数 → 无效
- `__attribute__((optnone))` → 未测试

**最终解决方案**：.h/.c 分离模式
- cm_coverage.h：宏定义 + extern 声明
- cm_coverage.c：cm_cov_hit() 实现（独立编译单元）
- cm_atcmd_pwm.c：`#include "cm_coverage.h"`，使用 COV_STMT 宏

armcc 无法跨编译单元优化，所以 cm_coverage.c 中的 increment 不会被消除。

**关键**：cm_coverage.c 必须被编译 **且** 链接到最终固件。见下方第 2 点。

## 2. 静态库 (.lib) 重建时序

**现象**：cm_coverage.o 存在且包含 cm_cov_hit，但 .axf 固件中不包含该符号。

**根因**：AT 模块被打包成 `onemo-at.lib` 静态库。编译流程：
```
编译 .o 文件 → 打包成 .lib → arelease 生成 release ZIP
```

如果 .lib 在 release ZIP 之后重建，ZIP 里的固件不包含新 .o 的代码。

**验证方法**：
```bash
# 检查 .lib 是否包含目标符号
findstr cm_cov_hit onemo-at.lib
# 检查 .axf 是否包含目标符号
findstr cm_cov_hit *.axf
# 检查时间戳
dir onemo-at.lib  # 必须 < release ZIP 时间戳
```

**修复**：删除旧 .o → 重新编译 → 确认 .lib 重新生成 → 确认 .lib 时间戳 < release ZIP → 重新打包。

## 3. SDK 原生 release ZIP vs 自定义打包

**现象**：自定义 Python 打包的 ZIP 能烧录成功，模块能启动，AT 命令正常，但覆盖率代码不工作。

**根因**：package_firmware.py 创建的 ZIP 内部结构可能与 SDK 的 arelease 工具生成的不同。adownload.exe 需要特定格式。

**解决方案**：始终使用 SDK 原生 release ZIP：
```bash
# SDK 编译后自动生成
SDK\target\ML307C-DC-CN-MBRH1S00\ML307C-DC-CN-MBRH1S00_x.x.x.x_release.zip
```

直接复制这个 ZIP 到测试机烧录，不要用 Python 重新打包。

## 4. ATRESP 双重调用

**现象**：AT+COVERAGE? 返回空（不是 ERROR）。

**根因**：GET_CMD handler 中先调用 `cm_coverage_query(atHandle)` 内部发送 ATRESP，然后又调用 `ATRESP(atHandle, OK, 0, "")`。第二次 ATRESP 覆盖了第一次的输出。

**修复**：将计算内联到 GET_CMD 中，只调用一次 ATRESP：
```c
case TEL_EXT_GET_CMD: {
    char output[128];
    // 计算逻辑直接写在这里
    sprintf(output, "+COVERAGE: ...");
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);
    break;
}
```

## 5. cm_atcmd_def.h handler 注册

**现象**：AT+COVERAGE? 返回空，AT+COVERAGE=1 返回 ERROR。

**根因**：cm_atcmd_def.h 中 AT+COVERAGE 的 handler 全是 NULL：
```c
// 错误
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, NULL, NULL, NULL),
```

**修复**：
```c
// 正确
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, cmCOVERAGE, cmCOVERAGE, cmCOVERAGE),
```

参考 MPWMCTRL 的注册格式。

## 6. 全局变量重复定义

**现象**：cm_atcmd_pwm.c 中写入 `cov_pwm_stmt_hits = 55` 无效，但 cm_atcmd_extern.c 中写入 `= 99` 有效。

**根因**：cm_atcmd_pwm.c 和 cm_coverage.c 都定义了 `volatile unsigned int cov_pwm_stmt_hits = 0;`。链接器创建了两个独立符号，两个文件写入不同的变量。

**修复**：变量只在 cm_coverage.c 中定义一次，其他文件通过 `#include "cm_coverage.h"` 的 extern 声明访问。

## 7. 编译验证 Checklist

每次修改覆盖率代码后，必须验证：

- [ ] cm_coverage.o 存在且时间戳正确
- [ ] cm_atcmd_pwm.o 引用 cm_cov_hit（findstr cm_cov_hit cm_atcmd_pwm.o）
- [ ] onemo-at.lib 包含 cm_cov_hit
- [ ] .axf 包含 cm_cov_hit
- [ ] release ZIP 时间戳晚于 .lib
- [ ] 烧录后 AT+COVERAGE? 显示模块
- [ ] 执行 AT 命令后桩命中数 > 0
