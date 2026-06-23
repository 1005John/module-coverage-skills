# HTTP 覆盖率 v6/v7 迭代经验

## 背景
- 目标模块：ML307R HTTP/HTTPS AT。
- v5 基线：`HTTP(53%,50%,234/810)`，已包含 AT 层与 HTTP API 层自定义 COV 桩。
- 依据手册：`/Volumes/DevDrive/test_report_ref/http_httpsusermanual.pdf`。
- v6/v7 引入行为断言：覆盖率新增不能抵消预期响应失败。

## 有效提升路径
| 轮次 | 起点 | 终点 | 新增 | 关键贡献 |
|------|------|------|------|----------|
| v6_short | 234/810 | 260/810 | +26 | WTCP/timeout/fragment/urlencode 边界，datamode prompt，chunked ind，DLFILE matrix |
| v7_short | 260/810 | 271/810 | +11 | 精确长度 header/content datamode，request datamode variants，TERM/DEL 状态边界 |

## 阶段收益
### v6_short
- WTCP CFG Boundaries：`234 → 241`，+7。
- Datamode Prompt Edges：`241 → 259`，+18。
- Chunked Ind Flow：HTTP 总数无新增，但 HTTPAPI 有新增。
- Alt Server Paths：无新增。
- DLFILE Matrix：`259 → 260`，+1。

### v7_short
- HeaderContent precise datamode：`260 → 262`，+2。
- Request datamode variants：`262 → 270`，+8。
- Cached read boundaries：无新增。
- TERM/DEL state edges：`270 → 271`，+1。

## 潜在 bug/需复核行为
- `AT+MHTTPCFG="timeout",0,0,0,0`：手册参数范围含 0，但实际 `+CME ERROR: 50`。
- `MHTTPHEADER` 数据模式 `eof=1/eof=2`：出现只返回 `>`、`+CME ERROR: 3` 或断言与实际不一致。
- `MHTTPCONTENT` 数据模式 `eof=1/eof=2`：部分返回 `+CME ERROR: 3` 或状态序列需复核。
- `MHTTPREQUEST` 无 path 数据模式：手册描述可进入数据输入，但实际部分返回 `+CME ERROR: 3`。

## 结论
- 当前已达 `HTTP(63%,57%,271/810)`，分支接近 60% 目标。
- 纯 AT 用例继续迭代的收益下降；语句覆盖率要冲 80%，更可能需要：
  1. 扩展 `cm_http_client.c` 自定义 COV 插桩；或
  2. 接入厂商 TJ 桩采集；或
  3. 构造更强网络环境触发 socket/SSL/HTTP parser 深层路径。

## 复用建议
- 下一轮优先复现 bug candidates，而不是盲目加 cached/read 边界（v7 已显示无新增）。
- 保留 datamode 精确长度用例，因为这是 v6/v7 最高收益区域。
- 对 `eof=1/eof=2` 的断言要结合手册重新校准，避免把脚本状态污染误判为固件 bug。
