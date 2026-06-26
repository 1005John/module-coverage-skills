# .h/.c 分离模式调试记录（2026-06-25 PWM 实战）

## 问题背景

在 ML307C 模块上实现 AT+COVERAGE? 覆盖率查询功能。经历了 ~15 次固件迭代调试。

## 调试时间线

### 阶段 1：AT 命令注册（3 次迭代）

| 问题 | 现象 | 修复 |
|------|------|------|
| cm_atcmd_def.h handler 全为 NULL | AT+COVERAGE? 返回空（不报 ERROR） | 链接 cmCOVERAGE 到 handler |
| cmCOVERAGE 声明在 #ifdef VOLTE_ENABLE 内 | 编译通过但 handler 不工作 | 移到 #ifdef 外面 |
| cm_printf 不发送响应 | AT+COVERAGE? 返回空 | 改用 ATRESP + output buffer |

### 阶段 2：ATRESP 双重调用（1 次迭代）

```c
// ❌ 错误：两次 ATRESP
static void cm_coverage_query(unsigned int atHandle) {
    sprintf(output, "+COVERAGE: ...");
    ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);  // 第一次
}
case TEL_EXT_GET_CMD: {
    cm_coverage_query(atHandle);
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, "");  // 第二次覆盖！
}
```

修复：内联计算，只调用一次 ATRESP。

### 阶段 3：编译器优化（5 次迭代）

**现象**：AT+COVERAGE? 返回 0/30，执行 AT 命令后仍为 0。DBG 调试计数器正常递增。

**尝试过的方案**：
1. `volatile` 关键字 → 无效
2. `static` 改为非 static → 无效
3. `#pragma O0` 保护函数 → 无效
4. .h/.c 分离模式（独立编译单元）→ 仍然无效！

**根因**：变量重复定义。cm_coverage.c 和 cm_atcmd_pwm.c 都定义了 `volatile unsigned int cov_pwm_stmt_hits = 0;`。链接器创建了两个不同符号。

**验证方法**：在 cm_atcmd_pwm.c 中直接写 `cov_pwm_stmt_hits = 99;`，AT+COVERAGE? 显示 99/30 → 确认 extern 链接正确，问题在跨文件变量。

**最终修复**：从 cm_atcmd_pwm.c 移除变量定义，只在 cm_coverage.c 中定义。

### 阶段 4：cm_coverage.o 未链接（2 次迭代）

**现象**：cm_coverage.c 已编译（cm_coverage.o 存在），但固件中无效果。

**根因**：cm_coverage.o 不在链接列表 `onemo-at_pk_objliblist.txt` 中。

**验证**：`findstr cm_coverage onemo-at_pk_objliblist.txt`

**修复**：手动添加到列表。

## 最终架构

```
cm_coverage.h     → 宏定义 + extern 声明
cm_coverage.c     → cm_cov_hit() 实现（#pragma O0）
cm_atcmd_pwm.c    → #include "cm_coverage.h"，使用 COV_STMT 宏
cm_atcmd_extern.c → extern 引用计数器，ATRESP 输出
cm_atcmd_def.h    → cmCOVERAGE handler 注册
```

## 关键验证清单

1. `findstr COV_STMT cm_atcmd_pwm.c` — 源码有桩
2. `findstr cm_cov_hit cm_atcmd_pwm.o` — .o 引用了 cm_cov_hit
3. `findstr cm_coverage onemo-at_pk_objliblist.txt` — 在链接列表中
4. `dir cm_coverage.o` — .o 存在且时间戳新于源码
5. `findstr cov_pwm cm_atcmd_pwm.c` — 应为空（无重复定义）
6. 固件测试：AT+COVERAGE? 显示模块名和桩数

## 调试技巧

- **诊断固件**：在 cm_atcmd_extern.c 中直接写 `cov_pwm_stmt_hits = 99;`，验证 extern 链接
- **DBG 计数器**：在 AT handler 中加 `volatile unsigned int dbg = 0; dbg++;` 并在 sprintf 中输出，验证函数被调用
- **二分法**：区分"变量链接问题"和"函数执行问题"
