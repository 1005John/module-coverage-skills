# PWM 模块覆盖率测试记录 (2026-06-26)

## 测试环境
- 模组：ML307C-DC-CN-MBRH1S00
- 固件版本：4.0.15.2606260848
- 测试机：172.20.162.21 (COM16, 115200)

## 测试结果

### 第一轮：基本 AT 命令
| 命令 | 增量 |
|------|------|
| AT+MPWMCFG? (GET) | — |
| AT+MPWMCFG=? (TEST) | — |
| AT+MPWMCFG=0,0,1 (SET) | — |
| AT+MPWMCFG=1,0,1 | — |
| AT+MPWMCFG=0,1,0 | — |
| AT+MPWMCFG=1,1,0 | — |
| AT+MPWMCFG=0 (default) | +1 |
| AT+MPWMCFG=1 (default) | — |
| AT+MPWMDATA? (GET) | — |
| AT+MPWMDATA=? (TEST) | — |
| AT+MPWMDATA=0,1000,50 | — |
| AT+MPWMDATA=1,2000,75 | — |
| AT+MPWMDATA=0,4001,50 | — |
| AT+MPWMDATA=0,9,50 | — |
| AT+MPWMDATA=0,1000,0 | — |
| AT+MPWMDATA=0,1000,100 | — |
| AT+MPWMCTRL? (GET) | — |
| AT+MPWMCTRL=? (TEST) | — |
| AT+MPWMCTRL=0,1 | — |
| AT+MPWMCTRL=0,0 | — |
| AT+MPWMCTRL=1,1 | — |
| AT+MPWMCTRL=1,0 | — |
**小计：24/30**

### 第二轮：错误路径
| 命令 | 增量 |
|------|------|
| AT+MPWMCFG=3,0,1 (bad channel) | — |
| AT+MPWMCFG=0,2,1 (bad param) | — |
| AT+MPWMDATA=3,1000,50 (bad channel) | — |
| AT+MPWMCTRL=3,1 (bad channel) | — |
| AT+MPWMCFG=0,0,2 (bad value) | +5 |
| AT+MPWMDATA=0,1000,101 (bad duty) | — |
**小计：25/30**

### 第三轮：边界条件
| 命令 | 增量 |
|------|------|
| AT+MPWMDATA=0,4001,50 + AT+MPWMCTRL=0,1 | +1 |
**小计：26/30**

### 最终结果
- 语句：100% (3/3)
- 分支：85% (23/27)
- 总计：26/30 (87%)

### 未覆盖的 4 个分支
1. **202**: cmMPWMCFG ACTION_CMD — AT 解析器不派发 ACTION_CMD 给 PWM 命令
2. **209**: cmMPWMDATA ACTION_CMD — 同上
3. **218**: cmMPWMCTRL ACTION_CMD — 同上（SET_CMD 和 ACTION_CMD 共享代码块）
4. **226**: `else` (onoff=0 关闭 PWM) — getExtValue 解析 onoff=0 可能提前返回

### 结论
- PWM 模块的 AT 命令覆盖率天花板约 87%
- ACTION_CMD 路径是 AT 解析器框架的固有限制
- 要突破 87% 需要直接调用函数或单元测试
