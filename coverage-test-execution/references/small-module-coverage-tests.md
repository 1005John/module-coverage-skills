# 小模块覆盖率测试实战（Ping/PWM）

## 概述

小模块（<10KB 源码，<100 桩）可以在单轮迭代中达到高覆盖率。
本参考记录 Ping（40桩）和 PWM（66桩）的完整测试过程和关键发现。

## Ping 模块结果

| 指标 | 值 |
|------|-----|
| 源码 | cm_atcmd_ping.c, 191行 |
| 桩数 | 27 (12 stmt + 15 branch) |
| 覆盖率 | 91%/86% (24/27) |
| 测试用例 | 15 |
| 迭代轮次 | 1 |

### 高收益 case

| Case | 新增桩 | 说明 |
|------|--------|------|
| test_cmd | +4 | AT+MPING=? 测试命令 |
| ping_basic | +18 | 基本 ping 8.8.8.8 |
| invalid_host | +1 | DNS 解析失败路径 |
| get_cmd | +1 | GET 命令（不支持） |

### 关键发现

1. 前两个 case (test_cmd + ping_basic) 就贡献 22 桩 (81%)
2. 边界值测试（timeout/packet_len 越界）不新增覆盖 — 参数校验在框架层 getExtValue
3. 错误场景（invalid_host, get_cmd）各贡献 1 桩 — 独立代码路径

## PWM 模块结果

| 指标 | 值 |
|------|-----|
| 源码 | cm_atcmd_pwm.c, 308行 |
| 桩数 | 66 (43 stmt + 23 branch) |
| 覆盖率 | 62%/82% (46/66) |
| 测试用例 | 34 |
| 迭代轮次 | 1 |

### 高收益 case

| Case | 新增桩 | 说明 |
|------|--------|------|
| data_set_ch0_100_50 | +10 | AT+MPWMDATA=0,100,50 |
| cfg_set_ch0_clk0 | +9 | AT+MPWMCFG=0,0 |
| ctrl_enable_ch0 | +7 | AT+MPWMCTRL=0,1 |
| cfg_get | +4 | AT+MPWMCFG? |
| data_test | +4 | AT+MPWMDATA=? |

### 关键发现

1. 分支覆盖率（82%）远高于语句覆盖率（62%）— 条件编译代码未覆盖
2. 3 个命令（MPWMCFG/MPWMDATA/MPWMCTRL）各自贡献独立桩
3. 负向测试（invalid_channel/clk/period/duty）各贡献 1 桩
4. period > 4000 分支（PWM_32K 时钟选择）未覆盖 — 需要测试 period=5000

## 共同模式

### 单轮高覆盖率策略

小模块不需要多轮迭代。关键策略：
1. 测试命令（AT+CMD=?）— 覆盖 TEST_CMD 分支
2. 查询命令（AT+CMD?）— 覆盖 GET_CMD 分支
3. 正向设置 — 覆盖 SET_CMD 主路径
4. 边界值 — 覆盖参数校验成功路径
5. 负向测试 — 覆盖参数校验失败路径
6. 不支持的命令（AT+CMD?）— 覆盖 GET_CMD 不支持路径

### 参数校验在框架层

getExtValue/getExtString 返回 FALSE 时，错误处理在框架层，不贡献模块桩。
这意味着：
- timeout=0, timeout=61 等越界测试不新增覆盖
- 但 AT+CMD="" 等空值测试可能新增覆盖（hostlen < 1 检查在模块内）

### 条件编译代码

PWM 模块有 `#ifdef ML302A_SUPPORT` 代码块，在 ML307R 平台上不编译。
这些代码的桩不会出现在覆盖率统计中，但会显示在 coverage_map 的桩数中。
结果：桩数（66）> 实际可覆盖桩（46），导致语句覆盖率偏低。

## cm_atcmd_extern.c 修改脚本模板

每次新模块插桩后，需要修改 cm_atcmd_extern.c。以下是 Python 脚本模板：

```python
# patch_extern_xxx.py
# 编码: latin-1 (Windows 源码文件编码)

with open(r'D:\ML307R\SDK\onemo\at\src\cm_atcmd_extern.c', 'r', encoding='latin-1') as f:
    content = f.read()

# 1. extern 声明
content = content.replace(
    'extern volatile unsigned int cov_xxx_branch_hits;\n#endif',
    'extern volatile unsigned int cov_xxx_branch_hits;\nextern volatile unsigned int cov_yyy_stmt_hits;\nextern volatile unsigned int cov_yyy_branch_hits;\n#endif'
)

# 2. 变量声明
content = content.replace(
    '_all_total += _http_api_total + _tcp_total + _xxx_total;',
    'unsigned long _yyy_stmt = cov_yyy_stmt_hits;\n    unsigned long _yyy_branch = cov_yyy_branch_hits;\n    unsigned long _yyy_total = STMT + BRANCH;\n    _all_stmt += _yyy_stmt;\n    _all_branch += _yyy_branch;\n    _all_total += _yyy_total;\n    _all_total += _http_api_total + _tcp_total + _xxx_total;'
)

# 3. sprintf 格式字符串
content = content.replace(
    'ALL(%lu%%,%lu%%,%lu/%lu)",',
    'YYY(%lu%%,%lu%%,%lu/%lu) ALL(%lu%%,%lu%%,%lu/%lu)",'
)

# 4. sprintf 参数
content = content.replace(
    '_xxx_stmt + _xxx_branch, _xxx_total,\n        (unsigned long)(_all_total > 0',
    '_xxx_stmt + _xxx_branch, _xxx_total,\n        (unsigned long)(_yyy_total > 0 ? (_yyy_stmt * 100) / STMT : 0),\n        (unsigned long)(_yyy_total > 0 ? (_yyy_branch * 100) / BRANCH : 0),\n        _yyy_stmt + _yyy_branch, _yyy_total,\n        (unsigned long)(_all_total > 0'
)

with open(r'D:\ML307R\SDK\onemo\at\src\cm_atcmd_extern.c', 'w', encoding='latin-1') as f:
    f.write(content)
```

**注意**: 实际替换时需要根据当前文件内容调整 old_string，不能直接使用模板。
关键点是用 latin-1 编码读写文件，避免 GBK 编码错误。
