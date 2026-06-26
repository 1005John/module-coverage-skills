# Kanban Cron Job 配置模板

## 编译服务器 (192.168.242.120)

```python
cronjob(
    action="create",
    name="kanban-build-worker",
    schedule="1m",
    skills=["coverage-instrumentation", "coverage-build-flash"],
    prompt="""你是编译服务器的 Kanban worker。

第一步: 拉取最新 board
  scp 52467@172.20.162.21:D:/coverage-board.db /tmp/coverage-board.db

第二步: 检查 assigned 给 build-server 的 OPEN 任务
  读取 board_state.json，如果没有任务: 静默退出

第三步: 领取任务并执行
  instrument: 执行 coverage-instrumentation 插桩 + 更新 extern.c + 编译
  reinstrument: 根据反馈重新插桩 + 编译
  build: 清理缓存 + 增量编译

第四步: 交付
  1. copy release.zip C:\\Users\\Lenovo\\fw.zip
  2. scp fw.zip 52467@172.20.162.21:D:/通信模组/at_kb_runs/
  3. SSH 写 build_status.json (status=ready)
  4. 标记任务 COMPLETED

第五步: 推送 board
  scp /tmp/coverage-board.db 52467@172.20.162.21:D:/coverage-board.db"""
)
```

## 测试电脑 (172.20.162.21)

```python
cronjob(
    action="create",
    name="kanban-test-worker",
    schedule="1m",
    skills=["coverage-build-flash", "coverage-test-execution",
            "coverage-analysis", "coverage-report"],
    prompt="""你是测试电脑的 Kanban worker。

第一步: 检查 build_status.json 是否有新固件 (status=ready)

第二步: 如果有新固件或 board 有 assigned 任务
  1. 烧录: scripts/flash_module.py <firmware>
  2. 验证: scripts/probe_com16.py
  3. 测试: scripts/run_tests.py generated_tests.yaml
  4. 分析: scripts/analyze_coverage.py runs/<run_id>
  5. 报告: scripts/generate_report.py runs/<run_id>

第三步: 更新状态
  build_status.json: status=done
  board: 标记 COMPLETED + 覆盖率数据
  如果覆盖率不足: 创建 reinstrument 任务 assignee=build-server"""
)
```
