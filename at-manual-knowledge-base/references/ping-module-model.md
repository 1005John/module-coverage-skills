# Ping 模块模型 (AT+MPING)

## 手册来源
- TCP_IP用户手册.pdf 第 57-59, 73 页
- section: 3.18 AT+MPING PING服务器

## 命令定义

### 测试命令
- `AT+MPING=?`
- 响应: `+MPING: ,(1-60),(1-65535),(1-1400),(1-15)` + OK

### 设置命令
- `AT+MPING=<host>[,<timeout>[,<ping_num>[,<packet_len>[,<cid>]]]]`
- 参数:
  - host: string, 1-255 字节, 域名或 IP
  - timeout: int, 1-60, 默认 10, 单位秒
  - ping_num: int, 1-65535, 默认 4
  - packet_len: int, 1-1400, 默认 16, 单位字节
  - cid: int, 1-15, PDP 上下文索引号

### URC
- 单包: `+MPING: <result>,<ip>,<packet_len>,<time>,<ttl>`
- 统计: `+MPING: "statistics",<sent>,<lost>,<rtt_min>,<rtt_max>,<rtt_avg>`

### result 码
- 0: 成功
- 1: DNS 解析失败
- 2: DNS 解析超时
- 3: 响应错误
- 4: 响应超时
- 5: 其他错误

## 源码结构
- 文件: cm_atcmd_ping.c (191 行)
- 函数: cmMPING, _CMIOT_NetPingRspFunc
- 桩: 40 (27 stmt + 13 branch)
- COV_BRANCH_START: 30

## 测试结果 (v1)
- 覆盖率: 91%/86% (24/27)
- 15 个测试用例
- 高收益: test_cmd(+4), ping_basic(+18)
