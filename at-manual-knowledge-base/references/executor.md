# AT 测试执行器技术参考

工具路径: `/Volumes/DevDrive/projects/at_knowledge_base/tools/executor.py`

## 架构

```
generated_tests.yaml → executor.py → runs/<run_id>/
                          │
                          ├─ 串口发送 AT 命令
                          ├─ 收集响应 + 等待 URC
                          ├─ 匹配 expect pattern
                          ├─ 查询 AT+COVERAGE?
                          └─ 输出结构化结果
```

## 输出文件

| 文件 | 内容 |
|------|------|
| run_result.json | 每条命令的原始响应、覆盖率、耗时 |
| assertion_result.json | 断言通过/失败详情 |
| coverage_summary.json | 覆盖率汇总、迭代历史、目标达成 |
| bug_candidates.json | 行为不符手册的潜在 bug |
| at_execution_log.txt | 完整 AT 串口日志 (带时间戳) |
| run_summary.md | 人可读 Markdown 报告 |

## Pattern 匹配

expect pattern 用 `<name>` 占位变量值:
- `OK` → 字面匹配
- `+MQTTURC: "conn",<connect_id>,<conn_state>` → URC 匹配
- `+CME ERROR` → 错误前缀匹配

转换逻辑:
```python
# 1. re.escape 转义特殊字符
# 2. 恢复 <name> 占位符
# 3. <name> → [^,\r\n]*  (允许引号)
regex = re.sub(r'<\w+>', r'[^,\\r\\n]*', escaped)
```

关键: 通配符必须允许引号 (`"` 不排除)，因为 MQTTREAD payload 带引号。

## URC 等待策略

```python
send_wait_urc(cmd, urc_pattern, timeout):
    发送命令
    循环 0.5s 间隔读取
    if urc_pattern in collected:
        多等 1s 收集后续数据
        break
    超时后返回已收集数据
```

## 环境变量

用 `${VAR}` 占位，执行时替换:
- `${MQTT_HOST}`, `${MQTT_PORT}` — broker
- `${MQTT_CLIENT_ID}` — 客户端 ID (用 run_id 保证唯一)
- `${MQTT_USER}`, `${MQTT_PASSWORD}` — 认证

## 执行顺序

按 category 排序:
1. flow (流程级, 建立连接)
2. positive (正向验证)
3. boundary (参数边界)
4. negative (负向)
5. state_negative (状态负向)
6. example (样例)

## 部署

```bash
# 1. 复制到 Windows 测试机
scp -r /Volumes/DevDrive/projects/at_knowledge_base/ \
    52467@192.168.3.128:D:/ML307R/at_knowledge_base/

# 2. 安装依赖
pip install pyserial pyyaml

# 3. 执行
cd D:\ML307R\at_knowledge_base
python3 tools/executor.py generated_tests.yaml --config env.yaml
```
