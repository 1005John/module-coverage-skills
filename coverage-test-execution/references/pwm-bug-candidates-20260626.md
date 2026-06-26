# PWM 模块疑似 Bug 列表 (2026-06-26)

## Bug #1 [严重] AT+MPWMCTRL=0,0 无法关闭 PWM

**现象**：发送 `AT+MPWMCTRL=0,0` 返回 OK，但 `cm_pwm_disable()` 路径未执行（stub 226 从未命中）。

**复现步骤**：
1. `AT+MPWMDATA=0,1000,50` → 设置 period/duty
2. `AT+MPWMCTRL=0,1` → 开启 PWM
3. `AT+MPWMCTRL=0,0` → 尝试关闭
4. `AT+COVERAGE?` → stub 226 (else/onoff=0) 未命中

**推测根因**：`getExtValue(parameter_values_p, 1, &onoff, 0, 1, 0)` 在 onoff=0 时可能返回 FALSE（参数被 AT 解析器当作"默认值"），导致提前 break。

**影响**：PWM 一旦开启无法通过 AT 命令关闭。

## Bug #2 [轻微] period 范围校验缺失

**现象**：`AT+MPWMDATA=0,10000,50` 返回 OK，如果 period 上限应为 4000 则应拒绝。

**复现**：`AT+MPWMDATA=0,10000,50` → OK（应为 ERROR）

## Bug #3 [设计] ACTION_CMD 是死代码

**现象**：`AT+MPWMCFG`/`AT+MPWMDATA`/`AT+MPWMCTRL`（不带 =）都返回 ERROR。AT 解析器不派发 ACTION_CMD。

**影响**：代码冗余，不影响功能。SET_CMD case fall-through 到 ACTION_CMD 的代码路径实际通过 SET_CMD 入口执行。
