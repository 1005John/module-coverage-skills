# PWM 模块模型 (AT+MPWMCFG/AT+MPWMDATA/AT+MPWMCTRL)

## 手册来源
- 4gseries扩展.pdf 第 74-75 页
- section: 4.20 AT+MPWMDATA, 4.21 AT+MPWMCTRL

## 命令定义

### AT+MPWMCFG (时钟配置)
- 测试: `AT+MPWMCFG=?`
- 查询: `AT+MPWMCFG?` → `+MPWMCNF: <channel>,<clk>`
- 设置: `AT+MPWMCFG=<channel>[,<clk>]`
  - channel: 0-1
  - clk: 0-1
  - 默认查询当前配置

### AT+MPWMDATA (数据配置)
- 测试: `AT+MPWMDATA=?` → `+MPWMDATA: (0-1),(10-10000),(0-100)`
- 查询: `AT+MPWMDATA?` → `+MPWMDATA: <ch>,<period>,<duty>`
- 设置: `AT+MPWMDATA=<channel>,<period>,<duty>`
  - channel: 0-1
  - period: 1-10000, 单位 us
  - duty: 0-100, 单位百分比
- 查询指定通道: `AT+MPWMDATA=<channel>`

### AT+MPWMCTRL (控制)
- 测试: `AT+MPWMCTRL=?` → `+MPWMCTRL: (0-1),(0-1)`
- 设置: `AT+MPWMCTRL=<channel>,<onoff>`
  - channel: 0-1
  - onoff: 0=关闭, 1=启动

## 源码结构
- 文件: cm_atcmd_pwm.c (308 行)
- 函数: cmMPWMCFG, cmMPWMDATA, cmMPWMCTRL
- 桩: 53 (30 stmt + 23 branch)
- COV_BRANCH_START: 30

## 测试结果 (v1)
- 覆盖率: 90%/82% (46/53)
- 34 个测试用例
- 高收益: cfg_get(+4), cfg_set_ch0_clk0(+9), data_set_ch0_100_50(+10), ctrl_enable_ch0(+7)
- 关键: period > 4000 触发 PWM_32K, period <= 4000 触发 PWM_13M

## Pitfalls
- ML302A_SUPPORT 条件编译代码在 ML307R 平台不编译
- cm_pwm_enable 失败路径需要硬件配合
- cmd_atcmd_extern.c 中的分母必须匹配实际桩数
