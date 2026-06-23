# 新模块覆盖率插桩完整流程

以 HTTP 模块为蓝本，通用化的新模块覆盖率插桩步骤。

## 第一步：分析源码

1. 找到 AT 命令分发文件（如 `cm_atcmd_http.c`）
2. 从 `cm_atcmd_def.h` 提取已注册的命令函数名
3. 从 `cm_atcmd_mat.h` 提取 MAT 枚举值
4. 确认核心层是否已有 TJ 桩（厂商预埋）

## 第二步：分配桩 ID

| 模块 | 语句桩 ID | 分支桩 ID |
|------|-----------|-----------|
| EXT | 0-53 | 1100+ |
| MQTT | 100-500 | 1100-1332 |
| HTTP | 200-437 | 2000-2211 |
| 新模块 N | 500-799 | 3000-3299 |

避免 ID 重叠！新模块从已有最大值之后分配。

## 第三步：写自动插桩脚本

参考 `instrument_http_v2.py`，核心逻辑：
1. 正则匹配函数签名 → 函数体 { }
2. 入口桩：函数体第一个可执行行（跳过声明）
3. 分支桩：if/else 的 { 之后
4. 语句桩：赋值/调用/流程控制行
5. 过滤：单行 if body、多行表达式、unreachable

**关键过滤函数（必须有）：**
- `is_single_line_if_body()` — 前一行 if/else 无 {
- `is_multiline_continuation()` — 前一行以 , || && 结尾
- `ends_with_open_brace_or_paren()` — 前一行以 ( 或 , 结尾
- `is_return_or_goto()` — 包括 CM_RETURN 宏

## 第四步：更新配置

1. `cm_coverage.h` — COV_TOTAL_STUBS 必须 >= 最大桩 ID + 1
2. `cm_atcmd_extern.c` — 同步更新其本地的 COV_TOTAL_STUBS（重要！该文件有独立实现）
3. `cm_atcmd_extern.c` — 添加 extern 计数器声明 + sprintf 报告
4. `cm_atcmd_extern.c` — output buffer 扩大到 256（原 64 不够）

## 第五步：添加本地 hit 函数

在插桩文件（如 cm_atcmd_http.c）中添加：

```c
/* 覆盖率插桩支持 */
#ifdef CM_COVERAGE_ENABLE
#include "cm_coverage.h"
#undef COV_STMT
#undef COV_BRANCH_T
#undef COV_BRANCH_F

volatile unsigned int cov_xxx_stmt_hits = 0;
volatile unsigned int cov_xxx_branch_hits = 0;

static void cm_cov_xxx_hit(uint16_t stub_id) {
    int already = cm_cov_is_hit(stub_id);
    cm_cov_hit(stub_id);
    if (!already) {
        if (stub_id >= 3000) cov_xxx_branch_hits++;
        else cov_xxx_stmt_hits++;
    }
}

#define COV_STMT(id)        cm_cov_xxx_hit(id)
#define COV_BRANCH_T(id)    cm_cov_xxx_hit(id)
#define COV_BRANCH_F(id)    cm_cov_xxx_hit(id)
#endif
```

**关键：`cm_cov_is_hit()` 检查首次命中** — 否则计数器显示 >100%

## 第六步：编译验证

1. 清理缓存：`del /q obj_PMD2NONE\obj_onemo_*\obj_onemo_at\cm_atcmd_xxx.*`
2. 增量编译：`ML307R.bat DC`
3. 检查 .o 文件存在且 > 0
4. 检查 release.zip 生成

## 第七步：烧录验证

1. 烧录新固件
2. `AT+COVERAGE=1` 启用
3. 执行几条 AT 命令
4. `AT+COVERAGE?` 检查新模块桩数 > 0

## 常见错误清单

| 错误 | 原因 | 修复 |
|------|------|------|
| #111 unreachable | COV 在 return/break/CM_RETURN 后 | 删除该桩 |
| #127 expected statement | COV 在单行 if body 前 | 用 if+{ } 或跳过 |
| #165 too few arguments | COV 在函数参数列表中 | 跳过该行 |
| #167 type void incompatible | COV 在多行函数调用中间 | 跳过该行 |
| L6218E Undefined symbol | 变量 static 但被 extern | 去掉 static |
| 覆盖率显示 >100% | 计数器每次触发都+1 | 用 cm_cov_is_hit() |
| AT+COVERAGE? 返回 ERROR | output buffer 溢出 | 扩大到 256 |
| 覆盖率始终 0% | COV_TOTAL_STUBS 太小 | 增大到覆盖最大 ID |
