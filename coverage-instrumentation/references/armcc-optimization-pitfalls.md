# armcc 编译器优化陷阱（实战验证）

## 问题

ARM Compiler 5 (armcc) 会激进优化覆盖率计数器 increment，即使变量声明为 `volatile`。

## 触发条件

1. `static` 函数被 armcc 冽数内联后，编译器可能将 volatile increment 视为 dead code
2. 非 static 函数也可能被优化掉（armcc 的 interprocedural optimization）

## 三层防护

### 1. volatile 变量声明（必要但不充分）
```c
volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;
```

### 2. 函数不能是 static
```c
// ❌ static → armcc 内联后优化掉 increment
static void cm_cov_pwm_hit(unsigned short id) { ... }

// ✅ 非 static → 编译器必须保留函数体
void cm_cov_pwm_hit(unsigned short id) { ... }
```

### 3. 函数必须禁用优化（最可靠）
```c
__attribute__((optnone)) void cm_cov_pwm_hit(unsigned short id) {
    // 函数体
}
```
或：
```c
#pragma O0
void cm_cov_pwm_hit(unsigned short id) {
    // 函数体
}
#pragma O2
```

## 诊断流程

当 AT+COVERAGE? 始终返回 0/N 时：

### Step 1: 验证 extern 链接
在 cmCOVERAGE GET_CMD 中直接写入：
```c
cov_pwm_stmt_hits = 99;
```
编译后 `AT+COVERAGE?` 应显示 99。如果显示 99 → 链接正确。如果显示 0 → extern 链接有问题（变量名不匹配或编译未生效）。

### Step 2: 验证函数调用
添加调试计数器：
```c
volatile unsigned int pwm_debug_call_count = 0;
```
在函数入口 `pwm_debug_call_count++`，在 AT+COVERAGE? 输出中显示 `DBG=%lu`。

- DBG 递增 → 函数被调用
- DBG 为 0 → 函数未被调用（AT 命令注册问题）

### Step 3: 验证 increment
如果 DBG 递增但覆盖率为 0 → 编译器优化掉了 increment → 加 `__attribute__((optnone))`。

## 现象对照表

| 现象 | 原因 | 修复 |
|------|------|------|
| AT+COVERAGE? 返回空 | ATRESP 双重调用 | 内联计算，只调用一次 ATRESP |
| AT+COVERAGE? 静默无响应 | handler 为 NULL | cm_atcmd_def.h 中链接 cmCOVERAGE |
| 直接写入 99 能读回 | extern 链接正确 | — |
| DBG 递增但覆盖率为 0 | 编译器优化 increment | 非 static + optnone |
| DBG 为 0 | 函数未被调用 | 检查 AT 命令注册 |
