# 仓库轮询架构

## 概述

用 Hermes cron 在 Mac mini 上定时轮询企业 Git 仓库，检测分支新增、删除和 SHA 变化；轮询阶段必须只读，不修改被监控仓库。webhook 不可用时（企业内网仓库无法 POST 到本地 Mac mini），优先用 `git ls-remote` 轮询。

## 轮询脚本

路径：`~/.hermes/scripts/repo_poll.py`
状态文件：`~/.hermes/scripts/repo_poll_state.json`

脚本功能：
1. `git ls-remote` 获取远程仓库所有分支和 SHA
2. 对比上次记录的状态（JSON 文件）
3. 输出变更报告（JSON 格式）：
   - new_branches: 新出现的分支
   - changed_branches: SHA 变化的分支（有新提交）
   - deleted_branches: 被删除的分支

## Cron 配置

轮询 cron（bd6bcab46430）：
- 频率：每 30 分钟
- 推送通道：飞书
- 职责：检测变更 → 分析 diff → 准备一次性 cron 提示词 → 推送给用户确认

执行模型：
```
轮询 cron（轻量，几秒完成）
  │ 有变更
  ▼
一次性 cron（独立 session，可能 30-60 分钟）
  git diff → 增量插桩 → 编译烧录 → 测试 → 报告
```

## AT 相关文件路径过滤

只关注以下路径的变更：
```python
AT_RELATED_PATTERNS = [
    r"SDK/onemo/at/src/cm_atcmd_",    # AT 命令层
    r"SDK/onemo/cm_mqtt/",             # MQTT 实现层
    r"SDK/onemo/cm_http/",             # HTTP 实现层
    r"SDK/onemo/cm_tcpip/",            # TCP 实现层
    r"SDK/onemo/coverage/",            # 覆盖率框架
    r"SDK/onemo/at/inc/",              # 头文件
]
```

## 仓库信息

仓库地址需配置在轮询脚本 `REPO_URL` 中；切换监控仓库时必须：
1. 先用 `git ls-remote <repo_url>` 做只读访问验证。
2. 更新脚本中的 `REPO_URL` 和 cron prompt 中的仓库描述。
3. 备份并重置 `~/.hermes/scripts/repo_poll_state.json`，避免把旧仓库分支误报为新仓库的新增/删除。
4. 首次成功访问新仓库时只建立基线；若访问失败，飞书报告错误，不做后续分析。

示例监控目标：
- `ssh://git@code-cmiot.rdcloud.4c.hq.cmcc:8022/osc/CMIOT/fuqiang-cmiot.cmcc/ASR-Coverage-test.git`
- `ssh://git@code-cmiot.rdcloud.4c.hq.cmcc:8022/osc/CMIOT/lte/ml302a/ml302a_std.git`

## 只读安全约束

- 轮询 cron 只允许执行 `git ls-remote`、必要的只读 `git show`/`git log` 分析和本地状态文件读写。
- 禁止对被监控仓库执行 `git push`、创建/删除分支、提交、强制更新或任何远程写操作。
- 如果新仓库返回 `fatal: Could not read from remote repository`、`Connection closed` 或权限错误，报告给用户并保持等待下一轮；不要把错误持久化为仓库不可用规则。
- 飞书投递要使用具体 target（如 `feishu:oc_...`）；裸 `deliver="feishu"` 可能解析失败。
- 如果用户要求“这个仓库一定不能修改”，切换监控目标时也只能修改本地轮询脚本、cron 配置和本地状态文件；不要克隆、提交或推送到目标仓库。

## 网络与 SSH 访问诊断

企业内网 Git 仓库常见地分离“网页登录权限”和“Git SSH 拉取权限”，并且 Hermes/Mac mini 可能不在灵畿/公司内网。处理访问失败时按以下顺序判断：
1. 先让用户在同一台机器终端执行 `git ls-remote <repo_url>`。若用户终端也失败，优先判断为仓库路径、Git SSH 权限、SSH 公钥绑定或内网/VPN/代理不可达问题，而不是 Hermes 问题。
2. 网页能访问仓库不代表 SSH clone/fetch 可用；网页登录态和 SSH key 权限是两条认证链路。
3. 需要新增 key 时，在 Mac mini 生成专用只读 key（如 `~/.ssh/<repo>_readonly`），只把 `.pub` 公钥添加到仓库 Deploy Key/项目 SSH Key，私钥留本机，不要让用户发送私钥内容。
4. 用专用 key 测试时使用 `GIT_SSH_COMMAND='ssh -i <key> -o IdentitiesOnly=yes -p 8022' git ls-remote <repo_url>`，确保没有误用默认 key。
5. 若 `ssh -vv` 显示在密钥认证前就 `kex_exchange_identification: Connection closed by remote host`，优先排查网络/内网/代理/跳板不可达；添加 SSH key 不能解决网络不可达。
6. 若监控 cron 因网络不可达持续报错，应先暂停 cron，避免每 30 分钟发送失败通知；网络恢复后再 resume 并重建基线。

## Pitfalls

1. 首次运行会把所有分支识别为"新"，这是正常的（初始化基线）
2. git fetch 大仓库会超时，用 `git ls-remote` 做轮询；只有需要分析具体变更时再尝试指定 commit/分支的只读 diff 命令
3. 轮询 cron 的 prompt 必须自包含（一次性 cron 没有上下文）
4. 状态文件是唯一持久化存储，删除后会重新初始化
5. 切换监控仓库必须先备份/重置状态文件，否则旧仓库分支会污染新仓库变更检测
6. 如果当前 Hermes SSH 环境访问不到新仓库，而用户终端可以访问，优先排查 SSH key、账号权限、仓库路径和代理/跳板差异，不要修改远程仓库验证
