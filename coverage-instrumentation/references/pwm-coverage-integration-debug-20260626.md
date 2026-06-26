# PWM 覆盖率集成调试记录 (2026-06-26)

## 问题

PWM 模块插桩后烧录，AT+COVERAGE? 始终显示 `PWM(0%,0%,0/30)`，执行所有 PWM AT 命令后仍为 0。

## 根因分析（4 层）

### 层 1: CM_COVERAGE_ENABLE 未定义
- instrument.py 生成的 `cm_atcmd_pwm.c` 包含 `#ifdef CM_COVERAGE_ENABLE` 块
- `CM_COVERAGE_ENABLE` 定义在 `cm_atcmd_extern.h`
- 但 `cm_atcmd_pwm.c` 不 include `cm_atcmd_extern.h`
- 结果：所有 COV_* 宏展开为 `((void)0)` — 空操作
- **修复**：在 `cm_atcmd_pwm.c` 开头加 `#define CM_COVERAGE_ENABLE`
- **结果**：仍然 0/30 → 进入层 2

### 层 2: 双重覆盖率系统（关键根因）
- **全局系统** `cm_coverage.c/h`：
  - `cm_cov_hit()` 函数，`#pragma O0` 防优化
  - `cov_pwm_stmt_hits` / `cov_pwm_branch_hits` 全局变量
  - `AT+COVERAGE?` 读的是这些全局变量
- **局部系统**（instrument.py 生成在 `cm_atcmd_pwm.c` 里）：
  - `cm_cov_pwm_hit()` 函数（static）
  - 自己的 `cov_pwm_stmt_hits` / `cov_pwm_branch_hits`（局部变量）
  - 自己的 `cov_pwm_bitmap[]`（static 局部）
- AT 命令执行时，桩写入局部变量；AT+COVERAGE? 读全局变量 → 永远 0

### 层 3: CM_COVERAGE_ENABLE 宏作用域
- 即使修复了层 2，如果宏未定义，桩仍为空操作
- 正确方案：不用自包含实现，直接 include `cm_coverage.h`

### 层 4: COV_TOTAL_STUBS 太小（最终阻塞点）

修复层 2+3 后，AT+COVERAGE? 仍然 0/30。

- `cm_coverage.h` 定义 `#define COV_TOTAL_STUBS 50`
- 但 PWM 桩 ID 是 100-102 (stmt) 和 200-226 (branch)
- `cm_cov_hit()` 开头有 `if (stub_id >= COV_TOTAL_STUBS) return;`
- 所有桩 ID >= 50 → 全部被静默丢弃

**修复**：`#define COV_TOTAL_STUBS 250`（必须 > 最大桩 ID 226）

## 正确修复（4 步，全部必须）

### 步骤 1: 修改 cm_coverage.h
```c
// 原来
#define COV_TOTAL_STUBS   50
// 改为（必须 > 所有模块的最大桩 ID）
#define COV_TOTAL_STUBS   250
```

### 步骤 2: 在被插桩的 .c 文件中 include 全局头文件
```c
// 在 #include 区域加一行
#include "cm_coverage.h"
```

### 步骤 3: 删除 instrument.py 生成的局部桩实现
删除 `cm_atcmd_pwm.c` 中的整个 `#ifdef CM_COVERAGE_ENABLE` 到 `#endif` 块，包括：
- `cm_cov_pwm_hit()` 函数
- `cov_pwm_stmt_hits` / `cov_pwm_branch_hits` 局部变量
- `cov_pwm_bitmap[]` 局部数组
- `COV_STMT` / `COV_BRANCH_T` 宏重定义

只保留 `#include "cm_coverage.h"` 和源码中的 `COV_STMT(id)` / `COV_BRANCH_T(id)` 调用。

### 步骤 4: 不需要 `#define CM_COVERAGE_ENABLE`
因为步骤 3 删除了 `#ifdef` 块，这个宏不再需要。
`cm_coverage.h` 中的 `COV_STMT` 宏是无条件定义的。

## 完整坑链总结

| 层 | 问题 | 现象 | 修复 |
|----|------|------|------|
| 1 | CM_COVERAGE_ENABLE 未定义 | 桩编译为空操作 | define 或 include 头文件 |
| 2 | 双重系统（局部 vs 全局变量） | AT+COVERAGE? 读全局，桩写局部 → 0 | 删除局部桩，用全局 cm_coverage.h |
| 3 | 宏作用域 | 同层 1 | 同层 1 |
| 4 | COV_TOTAL_STUBS 太小 | cm_cov_hit() 静默丢弃 ID >= 50 的桩 | 设为 250+ |

## 教训

1. instrument.py 的"自包含桩实现"模式与全局 cm_coverage.c/h 系统**根本不兼容**
2. instrument.py 应该只生成 `#include "cm_coverage.h"` + COV_* 宏调用，不要生成任何局部桩实现
3. **COV_TOTAL_STUBS 必须 > 最大桩 ID**，否则 cm_cov_hit() 静默丢弃，无任何报错
4. 调试覆盖率 0 的排查顺序：(1) 双重系统？(2) COV_TOTAL_STUBS 够大？(3) 宏是否展开？

## 验证命令

```
AT+COVERAGE=1          # 清零（注意：不清 bitmap，只重置计数器）
AT+MPWMCFG=0,0,1      # 执行一条 PWM 命令
AT+MPWMCTRL=1,1        # 再执行一条
AT+COVERAGE?           # 应显示 PWM 桩数 > 0
```

## PWM 实测覆盖率（2026-06-26）

- 总桩：30 (3 stmt + 27 branch)
- 语句：100% (3/3)
- 分支：85% (23/27)
- 总计：26/30 (87%)
- 未覆盖：ACTION_CMD 路径 (3 个，AT 解析器不派发) + onoff=0 else 路径 (1 个)

## ML307C 编译环境

- SDK 路径：`C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK`
- 编译脚本：`ML307C.bat`
- 编译命令：`cd /d <SDK> && ML307C.bat DC-CN ALL`
- ARM 编译器：`tools\win32\ARM_Compiler_5`
- 产物：`target\ML307C-DC-CN-MBRH1S00\ML307C-DC-CN-MBRH1S00_*_release.zip`
- 编译耗时：~5 分钟（全量）
- 注意：DC ALL 会从 ps.7z 恢复源文件，但 SDK 中没有 ps.7z，所以不会覆盖插桩修改
