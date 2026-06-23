# 覆盖率流水线快速开始

## 第一步：准备环境

1. 复制文档包到目标电脑
2. 修改 `env.yaml` 中的：
   - `remote_access.host` — Windows 测试机 IP
   - `remote_access.username` — SSH 账号
   - `serial.at_port` — AT 串口
   - `flash.tool.path` — 烧录工具路径
   - `network.mqtt_broker` — MQTT Broker 地址

3. 修改 `module_config.<module>.yaml` 中的：
   - `source.source_files` — 目标模块源码路径
   - `coverage.id_ranges` — 桩 ID 范围

## 第二步：验证环境

```bash
python3 scripts/validate_env.py --config env.yaml
```

输出应显示：
- 工具路径正确
- 命令模板正确
- 参数匹配 download_library.py

## 第三步：烧录固件

```bash
python3 scripts/flash_ml307r_once.py
```

验证：
- flash_ok=True
- at_ok=True
- version_ok=True

## 第四步：执行测试

```bash
python3 scripts/run_mqtt_at_coverage_v1.py
```

查看结果：
- `runs/<run_id>/coverage_summary.json` — 覆盖率摘要
- `runs/<run_id>/coverage_detail.json` — 用例详情
- `runs/<run_id>/run_summary.md` — Markdown 报告

## 第五步：迭代优化

1. 分析 `coverage_detail.json`，找出高价值用例
2. 修改脚本，增加针对性用例
3. 重复执行，直到达标

## 第六步：生成报告

```bash
python3 scripts/generate_excel_report.py
```

输出：`runs/MQTT覆盖率测试详细报告.xlsx`

## 复制到其他电脑

1. 复制整个文档包
2. 修改 `env.yaml` 和 `module_config.yaml`
3. 按照上述步骤执行

## 注意事项

- 禁止使用 `ML307R.bat DC ALL`（会覆盖插桩）
- conn_id=0 不可靠，优先使用 conn_id=1
- 即使命令返回 ERROR，覆盖率桩仍会触发
- 编译失败不得烧录
- 烧录失败不得冒充成功
