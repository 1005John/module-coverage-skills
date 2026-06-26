# Windows 服务器部署状态 (192.168.242.120)

## 服务器信息

- 主机名: DESKTOP-L1PPLTV
- IP: 192.168.242.120
- 用户: Lenovo / 密码: 123
- OS: Win11 26200 AMD64
- SSH 端口: 22 (标准)
- 连接命令: `sshpass -p '123' ssh -o StrictHostKeyChecking=no Lenovo@192.168.242.120`

## Hermes Agent

- 已安装: v0.17.0
- Provider: custom:xiaomi (mimo-v2.5-pro)
- Endpoint: https://token-plan-cn.xiaomimimo.com/v1
- 测试命令: `hermes chat -q "你好" --provider custom:xiaomi`

## module_coverage_agent 目录结构

```
C:\Users\Lenovo\Desktop\module_coverage_agent\
├── config/
│   └── config.yaml              # 仓库配置
├── scripts/
│   ├── poll_repo.py             # 仓库轮询脚本
│   ├── change_analysis.py       # 变更分析脚本（已实现完整功能）
│   └── tag_parser.py            # 标签解析脚本
├── repos/
│   ├── ml302a_std/              # 标准仓库克隆
│   │   └── .git/                # 238 个分支, 166 个 tags
│   └── ml302a_dev_asr_144/      # 开发分支仓库克隆
│       └── SDK/                 # 完整 SDK 目录
├── state/
│   └── repo_poll_state.json     # 轮询状态持久化
└── logs/
    └── agent.log                # 运行日志
```

## config.yaml 内容

```yaml
repo:
  url: "ssh://git@code-cmiot.rdcloud.4c.hq.cmcc:8022/osc/CMIOT/lte/ml302a/ml302a_std.git"
  ssh_key: "C:\\Users\\Lenovo\\.ssh\\id_ed25519"
  local_repo: "C:\\Users\\Lenovo\\Desktop\\module_coverage_agent\\repos\\ml302a_dev_asr_144"
  monitor_branches:
    - "dev_asr_144"
poll:
  interval_minutes: 30
state:
  file: "state/repo_poll_state.json"
log:
  file: "logs/agent.log"
  level: "INFO"
```

## change_analysis.py 已实现功能

- git diff --name-status 分析
- 模块识别: MQTT/HTTP/TCP/FTP/SSL/DNS/PING/PWM/OTHER
- 变更类型分类: trivial/boundary/structural/new_func/delete_func/cross_layer
- 受影响函数识别（基于正则匹配函数签名）
- 支持 --local-repo 本地模式和 --repo-url 远程模式
- 输出 JSON 或人类可读报告

## 需求文档

```
C:\Users\Lenovo\Desktop\module_coverage_docs\
├── module_coverage_server_agent_design.md      # 设计文档 (7560 bytes)
└── module_coverage_server_agent_requirements.md # 需求文档 (10440 bytes)
```

## 首次轮询结果 (2026-06-24)

- 监控 238 个分支
- 发现 166 个 tags
- 首次运行所有分支被识别为"新"（正常，初始化基线）

## 已完成 vs 待完成

### 已完成
- [x] Hermes Agent 安装和配置
- [x] 仓库克隆 (ml302a_std, ml302a_dev_asr_144)
- [x] 仓库轮询脚本
- [x] 变更分析脚本 (change_analysis.py)
- [x] 需求文档和设计文档
- [x] 首次轮询基线建立

### 待完成
- [ ] 增量插桩脚本
- [ ] cm_atcmd_extern.c 自动维护脚本
- [ ] 固件编译脚本
- [ ] artifact 打包和发布
- [ ] 与 Mac mini 上 Hermes cron 的集成
- [ ] 飞书通知集成
- [ ] 实际端到端插桩+编译+测试验证

## Pitfalls

1. 该服务器上没有 D:\ML307R 目录 — SDK 在 module_coverage_agent/repos/ml302a_dev_asr_144/SDK/ 下
2. SSH 用密码认证 (Lenovo/123)，不是 key
3. Windows 命令中 `head`/`tail` 不可用，用 PowerShell 的 `Select-Object -First N`
4. Windows 路径用反斜杠，Python 脚本中需注意转义
