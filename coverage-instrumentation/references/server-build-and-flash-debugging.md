# 服务器编译 + 测试机烧录调试记录 (2026-06-25)

## 调试时间线

### 阶段 1：AT+COVERAGE? 返回 ERROR
- cm_atcmd_def.h 中 AT+COVERAGE handler 全为 NULL → 命令不执行
- 修复：`utlDEFINE_EXTENDED_VSYNTAX_AT_COMMAND(MAT_COVERAGE, "+COVERAGE", NULL, cmCOVERAGE, cmCOVERAGE, cmCOVERAGE)`

### 阶段 2：AT+COVERAGE? 返回空（不是 ERROR）
- ATRESP 被调用两次：cm_coverage_query() 辅助函数中一次，cmCOVERAGE() GET_CMD 中一次
- 第二次空 ATRESP 覆盖第一次数据
- 修复：将计算逻辑内联到 GET_CMD，只调用一次 ATRESP

### 阶段 3：覆盖率始终 0/N
- 经历了多种尝试：
  1. static 函数 + volatile → 仍为 0（armcc 内联后优化掉 increment）
  2. 非 static + volatile → 仍为 0
  3. #pragma O0 → 仍为 0
  4. .h/.c 分离模式 → 仍为 0
- 根因发现：**变量重复定义**
  - cm_coverage.c 定义 `volatile unsigned int cov_pwm_stmt_hits = 0;`
  - cm_atcmd_pwm.c 也定义了同名变量
  - 链接器当作两个不同变量，extern 引用指向不同的实例
- 修复：cm_atcmd_pwm.c 只通过 cm_coverage.h 的 extern 声明访问，不定义变量

### 阶段 4：修复后仍为 0
- cm_coverage.o 已在 objliblist.txt 中，但 .axf 不包含 cm_cov_hit
- 根因：**onemo-at.lib 在 release ZIP 打包之后才重建**
  - .lib 更新时间：19:12
  - release ZIP 创建时间：19:11
- 修复：`ML307R.bat DC ALL` 全量重建，确保 .lib 在打包之前完成

### 阶段 5：全量重建后仍为 0
- .axf 确认包含 cm_cov_hit ✅
- 但 SSH 环境下 adownload.exe 烧录一直卡住
- 实际上固件没有被成功烧入测试机

## 关键教训

### 1. .lib 打包时序验证
```bash
# 检查 .lib 时间戳
dir onemo-at.lib
# 检查 release ZIP 时间戳
dir target\ML307C-DC-CN-MBRH1S00\*.zip
# .lib 必须早于 ZIP
```

### 2. .axf 符号验证
```bash
findstr cm_cov_hit *.axf
# 有输出 = 链接正确
# 无输出 = .lib 未包含 cm_coverage.o
```

### 3. SSH 环境下 USB 工具限制
adownload.exe 需要直接 USB 访问，通过 SSH 执行会卡住。解决方案：
- 用户手动在测试机上执行烧录命令
- 或使用远程桌面工具

### 4. 终极验证方法（当覆盖率始终为 0 时）
1. 在 cm_atcmd_pwm.c 中硬编码 `cov_pwm_stmt_hits = 99;`
2. 编译 → 烧录 → AT+COVERAGE?
3. 显示 99 → extern 链接正确，问题在 cm_cov_hit()
4. 显示 0 → 链接有问题，检查变量重复定义

## 测试机环境
- 主机：172.20.162.21 (Windows)
- 用户：52467
- 串口：COM16 (AT 口, 115200)
- 烧录工具：D:\software\aboot-tools-2023.04.03\...\adownload.exe
- Python：3.11.6 + pyserial 3.5
