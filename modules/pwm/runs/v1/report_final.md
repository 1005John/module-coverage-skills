# PWM 模块覆盖率测试报告

## 概述

从零开始完成 PWM 模块（AT+MPWMCFG/AT+MPWMDATA/AT+MPWMCTRL）的覆盖率测试。

**目标**：语句覆盖率 70%，分支覆盖率 50%
**实际**：语句覆盖率 62%，分支覆盖率 82%
**结论**：分支达标 ✅，语句未达标 ❌（差 8%）

## 环境

| 项目 | 值 |
|------|-----|
| 测试机 | 172.20.162.21:22 (用户 52467) |
| AT 串口 | COM16, 115200 |
| 固件版本 | 3.1.0.2606231105_release |
| 源文件 | cm_atcmd_pwm.c (308 行) |
| 桩数 | 66 (43 stmt + 23 branch) |

## 测试用例

| Case | 新增桩 | 说明 |
|------|--------|------|
| cfg_test | +0 | AT+MPWMCFG=? |
| cfg_get | +4 | AT+MPWMCFG? |
| cfg_set_ch0_clk0 | +9 | AT+MPWMCFG=0,0 |
| cfg_set_ch0_default | +1 | AT+MPWMCFG=0 |
| data_test | +4 | AT+MPWMDATA=? |
| data_get | +4 | AT+MPWMDATA? |
| data_set_ch0_100_50 | +10 | AT+MPWMDATA=0,100,50 |
| data_get_ch0 | +1 | AT+MPWMDATA=0 |
| ctrl_get | +1 | AT+MPWMCTRL? |
| ctrl_enable_ch0 | +7 | AT+MPWMCTRL=0,1 |
| cfg_invalid_channel | +1 | AT+MPWMCFG=2,0 |
| cfg_invalid_clk | +1 | AT+MPWMCFG=0,2 |
| data_invalid_channel | +1 | AT+MPWMDATA=2,100,50 |
| data_invalid_period_0 | +1 | AT+MPWMDATA=0,0,50 |
| data_invalid_duty_101 | +1 | AT+MPWMDATA=0,100,101 |

## 未覆盖桩分析

剩余 20 个桩未覆盖，可能原因：
1. **ML302A_SUPPORT 条件编译**：部分代码在 ML302A 平台下才编译
2. **cm_pwm_enable 失败路径**：需要硬件 PWM 模块返回错误
3. **period > 4000 分支**：需要测试 period > 4000 的场景

## 关键发现

1. **覆盖率提升快**：前几个 case 就贡献了大部分桩
2. **分支覆盖率高**：82% 说明主要分支都已覆盖
3. **语句覆盖率低**：62% 可能是条件编译代码未覆盖
4. **负向测试有效**：invalid_channel/clk/period/duty 各贡献 1 桩

## 产出文件

```
/Volumes/DevDrive/projects/at_knowledge_base/modules/pwm/
├── coverage_map.pwm.json
├── runs/v1/
│   ├── run_result.json
│   ├── at_execution_log.txt
│   └── report_final.md
```

## 后续方向

1. **测试 period > 4000 场景**：触发 PWM_32K 时钟选择
2. **测试 cm_pwm_enable 失败**：需要硬件配合
3. **检查条件编译代码**：ML302A_SUPPORT 相关代码
