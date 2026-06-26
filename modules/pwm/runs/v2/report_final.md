# PWM 模块覆盖率测试报告

## 概述

从零开始完成 PWM 模块（AT+MPWMCFG/AT+MPWMDATA/AT+MPWMCTRL）的覆盖率测试。

**目标**：语句覆盖率 70%，分支覆盖率 50%
**实际**：语句覆盖率 100%，分支覆盖率 85%（26/30）
**结论**：目标达成 ✅

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| 编译服务器 | 192.168.242.120 (Lenovo/123) |
| 固件版本 | ML307C-DC-CN-MBRH1S00_4.0.15.2606260848_release |
| 模块 | ML307C (DC-CN 变体) |
| 源文件 | cm_atcmd_pwm.c |
| 桩数 | 30 (3 stmt + 27 branch) |

## 插桩修复记录

本次插桩踩了 4 个坑，逐一修复后才成功：

### 坑 1：两套覆盖率系统冲突
- **现象**：AT+COVERAGE? 始终显示 0/30
- **原因**：instrument.py 在 cm_atcmd_pwm.c 中生成了独立的 `cm_cov_pwm_hit()` 函数和局部变量，但 AT+COVERAGE? 读的是 cm_coverage.c 中的全局变量
- **修复**：删除 instrument.py 生成的 `#ifdef CM_COVERAGE_ENABLE` 块，改用 `#include "cm_coverage.h"`

### 坑 2：CM_COVERAGE_ENABLE 宏未定义
- **现象**：修复坑 1 后仍显示 0/30
- **原因**：cm_atcmd_pwm.c 不 include cm_atcmd_extern.h（那里定义了 CM_COVERAGE_ENABLE），所以 `#ifdef` 判断为 false
- **修复**：坑 1 的修复已解决（删除 #ifdef 块后不再需要这个宏）

### 坑 3：COV_TOTAL_STUBS 太小
- **现象**：修复坑 1、2 后仍显示 0/30
- **原因**：cm_coverage.h 中 COV_TOTAL_STUBS=50，但桩 ID 从 100 起（stmt）和 200 起（branch），cm_cov_hit() 开头 `if (stub_id >= COV_TOTAL_STUBS) return;` 直接丢弃
- **修复**：改 COV_TOTAL_STUBS 为 250（模板值 2500 更安全）

### 坑 4：COV_TOTAL_STUBS 修改后需全量编译
- **现象**：增量编译后 .o 文件未更新
- **原因**：修改 .h 文件后，构建系统的依赖检查可能不触发重编
- **修复**：使用 `ML307C.bat DC-CN ALL` 全量编译

## 测试用例

| Case | 命令 | 说明 |
|------|------|------|
| CFG query | AT+MPWMCFG? | GET_CMD 路径 |
| CFG test | AT+MPWMCFG=? | TEST_CMD 路径 |
| CFG set ch0 | AT+MPWMCFG=0,0,1 | SET_CMD + 参数解析 |
| CFG set ch1 | AT+MPWMCFG=1,0,1 | 多通道 |
| CFG set clk | AT+MPWMCFG=0,1,0 | clk 参数 |
| CFG default | AT+MPWMCFG=0 | is_default 路径 |
| DATA query | AT+MPWMDATA? | GET_CMD |
| DATA test | AT+MPWMDATA=? | TEST_CMD |
| DATA set | AT+MPWMDATA=0,1000,50 | SET_CMD + 参数 |
| DATA big period | AT+MPWMDATA=0,4001,50 | period>4000 边界 |
| CTRL query | AT+MPWMCTRL? | GET_CMD |
| CTRL test | AT+MPWMCTRL=? | TEST_CMD |
| CTRL on | AT+MPWMCTRL=0,1 | 启用 PWM |
| CTRL off | AT+MPWMCTRL=0,0 | 关闭 PWM |
| ERR bad channel | AT+MPWMCFG=3,0,1 | 无效通道 |
| ERR bad param | AT+MPWMCFG=0,2,1 | 无效参数 |

## 未覆盖分支（4 个）

| 桩 ID | 函数 | 原因 |
|-------|------|------|
| 202 | cmMPWMCFG | ACTION_CMD — AT 解析器不派发 |
| 209 | cmMPWMDATA | ACTION_CMD — AT 解析器不派发 |
| 218 | cmMPWMCTRL | ACTION_CMD — SET_CMD 共享代码块 |
| 226 | cmMPWMCTRL | else (onoff=0) — getExtValue 解析问题 |

## 关键经验

1. **instrument.py 生成文件必须手动修复** — 删除局部桩实现，用 `#include "cm_coverage.h"`
2. **COV_TOTAL_STUBS 必须 > 最大桩 ID** — 编译前 grep 检查
3. **全量编译确认时序** — ZIP 必须在 .axf 之后生成
4. **AT+COVERAGE? 验证** — 烧录后先查桩数，>0 才继续测试

## 产出文件

```
modules/pwm/
├── coverage_map.pwm.json
├── runs/
│   ├── v1/          # 旧版本（53 桩，固件 3.1.0）
│   └── v2/          # 当前版本（30 桩，固件 4.0.15，ML307C）
```
