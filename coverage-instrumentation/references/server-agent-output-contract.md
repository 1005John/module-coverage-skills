# Server Agent 插桩产出规范

## 背景

中心服务器 Agent 负责插桩和编译，测试电脑 Agent 负责 AT 执行和覆盖率采集。
服务器插桩的产出必须完整，否则测试电脑无法工作。

## 服务器插桩必须产出的文件

每个模块（如 PWM）的 output/<MODULE>/ 目录下必须包含：

```
output/PWM/
├── cm_atcmd_pwm.c          # 插桩后源码（含 cm_cov_pwm_hit 实现 + COV 宏调用）
├── coverage_map.PWM.json   # 桩 ID → 位置映射
├── stub_id_alloc.yaml      # 桩 ID 分配记录
├── manifest.json           # artifact 元数据（source_commit, build_time, modules 等）
├── change_analysis.json    # 变更分析结果
└── *.zip                   # 编译后的固件
```

固件 ZIP 统一放在 `output/FINAL/` 目录。

## 产出 1：插桩后模块源码（FR-004）

插桩后的 cm_atcmd_xxx.c 必须包含两部分：

### Part A：模块级桩实现（文件顶部，#include 之后）

```c
#define COV_PWM_TOTAL        130    // >= 最大桩 ID + 1
#define COV_PWM_BRANCH_START 200    // > 所有 COV_STMT 的最大 ID

volatile unsigned int cov_pwm_stmt_hits = 0;
volatile unsigned int cov_pwm_branch_hits = 0;
static unsigned int cov_pwm_bitmap[(COV_PWM_TOTAL + 31) / 32] = {0};

static void cm_cov_pwm_hit(unsigned short id) {
    if (id >= COV_PWM_TOTAL) return;
    unsigned int w = id / 32;
    unsigned int b = id % 32;
    if (!(cov_pwm_bitmap[w] & (1u << b))) {
        cov_pwm_bitmap[w] |= (1u << b);
        if (id < COV_PWM_BRANCH_START) cov_pwm_stmt_hits++;
        else cov_pwm_branch_hits++;
    }
}

#define COV_STMT(id)      cm_cov_pwm_hit(id)
#define COV_BRANCH_T(id)  cm_cov_pwm_hit(id)
#define COV_BRANCH_F(id)  cm_cov_pwm_hit(id)
```

注意：不要用 `#ifdef CM_COVERAGE_ENABLE` 包裹，确保覆盖率代码始终编译。

### Part B：COV 宏调用（函数体中）

```c
void cmMPWMCFG(...) {
    COV_STMT(100);  /* function entry */
    switch (cmd) {
        case TEL_EXT_GET_CMD:
            COV_BRANCH_T(101);  /* branch */
            ...
```

## 产出 2：cm_atcmd_extern.c 更新（FR-005）

AT+COVERAGE? 命令在 cm_atcmd_extern.c 中实现。新模块插桩后必须修改三处 + 命令注册：

### 位置 1：extern 声明（~40-58 行）
```c
extern volatile unsigned int cov_pwm_stmt_hits;
extern volatile unsigned int cov_pwm_branch_hits;
```

### 位置 2：GET_CMD handler — 只调用一次 ATRESP
```c
case TEL_EXT_GET_CMD: {
    char output[128];
    unsigned long _pwm_stmt = cov_pwm_stmt_hits;
    unsigned long _pwm_branch = cov_pwm_branch_hits;
    unsigned long _pwm_total = 3 + 27;
    sprintf(output, "+COVERAGE: PWM(%lu%%,%lu%%,%lu/%lu) ALL(...)",
        (unsigned long)(_pwm_total > 0 ? (_pwm_stmt * 100) / 3 : 0),
        (unsigned long)(_pwm_total > 0 ? (_pwm_branch * 100) / 27 : 0),
        _pwm_stmt + _pwm_branch, _pwm_total, ...);
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, output);  // 唯一一次！
    break;
}
```

### 位置 3：SET_CMD handler（清零）
```c
case TEL_EXT_SET_CMD: {
    cov_pwm_stmt_hits = 0;
    cov_pwm_branch_hits = 0;
    ret = ATRESP(atHandle, ATCI_RESULT_CODE_OK, 0, "");
    break;
}
```

### 位置 4：cm_atcmd_def.h 命令注册（关键！）
```c
// ❌ 错误：handler 全为 NULL
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, NULL, NULL, NULL),

// ✅ 正确：链接 cmCOVERAGE handler
utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, cmCOVERAGE, cmCOVERAGE, cmCOVERAGE),
```

## 产出 3：coverage_map.json

```json
{
  "module": "PWM",
  "source_commit": "<git sha>",
  "instrumentation_version": "20260625075216",
  "total_stubs": 30,
  "stmt_count": 3,
  "branch_count": 27,
  "branch_start_id": 200,
  "stubs": {
    "100": {"id": 100, "file": "cm_atcmd_pwm.c", "func": "cmMPWMCFG", "type": "stmt", "line": 30, "context": "function entry"},
    "200": {"id": 200, "file": "cm_atcmd_pwm.c", "func": "cmMPWMCFG", "type": "branch", "line": 49, "context": "case TEL_EXT_GET_CMD:"}
  }
}
```

## 产出 4：manifest.json

服务器当前缺失此文件。应包含：
```json
{
  "artifact_id": "ml302a_dev_asr_144_PWM_20260625_081900",
  "repo_url": "ssh://...",
  "branch": "dev_asr_144",
  "source_commit": "f020ddb",
  "build_time": "2026-06-25T08:19:00+08:00",
  "modules": ["PWM"],
  "firmware": {"zip": "ML307C-DC_CN-5.0.0-RC4_inst_f020ddb_2606250819.zip"},
  "coverage_map": "coverage_map.PWM.json",
  "stub_id_alloc": "stub_id_alloc.yaml"
}
```

## 服务器 instrument.py 当前状态（2026-06-25 更新）

1. ✅ 生成模块级 cm_cov_xxx_hit() 实现（FR-004 合规）
2. ✅ update_extern.py 更新 cm_atcmd_extern.c（FR-005 合规）
3. ❌ 不生成 manifest.json
4. ❌ coverage_map 中 source_commit 为空
5. ❌ 不生成 change_analysis.json 到产物目录
6. ⚠️ cm_atcmd_def.h 命令注册需要手动检查

## AT+COVERAGE? 命令参考

- `AT+COVERAGE?` — 查询所有模块覆盖率
- `AT+COVERAGE=1` — 清零所有计数器
- 返回格式：`+COVERAGE: EXT(stmt%,branch%,hit/total) ... ALL(stmt%,branch%,hit/total)`
- 测试电脑验证流程见 references/server-agent-test-workflow.md
