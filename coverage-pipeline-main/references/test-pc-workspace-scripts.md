# 测试电脑工作区脚本

测试电脑 (172.20.162.21) 需要 5 个本地脚本完成步骤 1/6/7/8/9。
步骤 2-5（插桩、更新 extern.c、清理缓存、编译）在编译服务器上完成。

## 工作目录结构

```
D:\通信模组\at_kb_runs\
├── env.yaml                          # 环境配置
├── generated_tests.<module>.yaml     # 可执行用例（步骤1产出或从仓库拷贝）
├── modules/
│   ├── <module>_module_model.yaml    # 模块模型（步骤1产出）
│   └── coverage_map.<module>.json    # 桩映射（步骤2-5从服务器拷贝）
├── scripts/
│   ├── probe_com16.py                # 探测 AT 串口
│   ├── flash_module.py               # 烧录固件
│   ├── run_tests.py                  # 执行 AT 测试
│   ├── analyze_coverage.py           # 覆盖率分析 + 迭代决策
│   └── generate_report.py            # 生成 MD + Excel 报告
├── artifacts/                        # 固件 zip（从服务器拷贝）
└── runs/
    └── v<N>_<YYYYMMDD>/              # 每轮测试结果
        ├── run_result.json
        ├── assertion_result.json
        ├── coverage_delta.json
        ├── bug_candidates.json
        ├── coverage_summary.json
        ├── iteration_decision.json
        ├── uncovered_analysis.json
        ├── report.md
        ├── report.xlsx
        └── at_execution_log.txt
```

## 脚本接口

### probe_com16.py — 探测 AT 串口
```bash
python scripts/probe_com16.py [--port COM16] [--baud 115200]
# 输出: ✓ COM16 可用 或 ✗ 无法打开
```

### flash_module.py — 烧录固件
```bash
python scripts/flash_module.py <firmware.zip> [--config env.yaml]
# 步骤: AT+MFORCEDL → 等待 COM15 → adownload.exe → 等待重启 → AT 验证
```

### run_tests.py — 执行 AT 测试
```bash
python scripts/run_tests.py generated_tests.<module>.yaml --config env.yaml --run-id v1
# 依赖: pyserial, pyyaml
# 输出: runs/<run_id>/ 下所有 JSON + 日志
```

### analyze_coverage.py — 覆盖率分析
```bash
python scripts/analyze_coverage.py runs/<run_id> [--coverage-map modules/coverage_map.<module>.json]
# 输出: coverage_delta.json, uncovered_analysis.json, iteration_decision.json
```

### generate_report.py — 生成报告
```bash
python scripts/generate_report.py runs/<run_id> [--coverage-map modules/coverage_map.<module>.json]
# 输出: report.md + report.xlsx (需要 openpyxl)
```

## 新测试机部署步骤

1. 安装 Python 3.11+ 和依赖: `pip install pyserial pyyaml openpyxl`
2. 创建工作目录: `mkdir D:\通信模组\at_kb_runs\{scripts,modules,artifacts,runs}`
3. 从仓库拷贝 5 个脚本到 `scripts/`
4. 创建 `env.yaml`（参考 config-templates.md）
5. 运行 `python scripts/probe_com16.py` 验证串口
6. 从服务器拷贝固件 zip 到 `artifacts/`，coverage_map.json 到 `modules/`
7. 运行测试

## 完整工作流命令序列

```bash
# 1. 验证串口
python scripts/probe_com16.py

# 2. 烧录（从服务器拷贝固件后）
python scripts/flash_module.py artifacts/<firmware>.zip

# 3. 执行测试
python scripts/run_tests.py generated_tests.<module>.yaml --run-id v1

# 4. 分析
python scripts/analyze_coverage.py runs/v1 --coverage-map modules/coverage_map.<module>.json

# 5. 报告
python scripts/generate_report.py runs/v1 --coverage-map modules/coverage_map.<module>.json

# 6. 如果未饱和，生成下一轮用例再回到步骤 3
```

## Pitfalls

1. **pyserial 和 pyyaml 是必须的** — 缺少会 ImportError，脚本开头有检测
2. **openpyxl 是可选的** — 缺少只跳过 Excel 生成，不影响其他
3. **coverage_map.json 从服务器拷贝** — 不要在测试机上修改，如发现问题回报服务器
4. **env.yaml 中的烧录工具路径不要硬编码在脚本中** — 从 config 读取
5. **每轮 run_id 用时间戳** — 避免覆盖历史结果
