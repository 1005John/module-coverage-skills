# 测试电脑工作区结构与脚本

## 工作区路径

```
D:\通信模组\at_kb_runs\
├── env.yaml                          # 环境配置
├── generated_tests.<module>.yaml     # 可执行用例
├── modules/
│   ├── <module>_module_model.yaml    # 模块模型（手册抽取）
│   └── coverage_map.<module>.json    # 桩映射（编译服务器生成）
├── scripts/
│   ├── probe_com16.py                # COM16 探针
│   ├── flash_module.py               # 烧录固件
│   ├── run_tests.py                  # 执行 AT 测试
│   ├── analyze_coverage.py           # 覆盖率分析
│   └── generate_report.py            # 生成报告
└── runs/
    └── <run_id>/                     # 每轮测试结果
        ├── run_result.json
        ├── assertion_result.json
        ├── coverage_delta.json
        ├── bug_candidates.json
        ├── coverage_summary.json
        ├── iteration_decision.json
        ├── report.md
        ├── report.xlsx
        └── at_execution_log.txt
```

## 脚本用法

### 探测 COM16
```cmd
python scripts\probe_com16.py
```

### 烧录固件
```cmd
python scripts\flash_module.py <firmware.zip> --config env.yaml
```

### 执行测试
```cmd
python scripts\run_tests.py generated_tests.<module>.yaml --config env.yaml --run-id <run_id>
```

### 分析覆盖率
```cmd
python scripts\analyze_coverage.py runs\<run_id> --coverage-map modules\coverage_map.<module>.json
```

### 生成报告
```cmd
python scripts\generate_report.py runs\<run_id>
```

## SSH 远程执行注意事项

```cmd
cmd /c "set PYTHONIOENCODING=utf-8 && python scripts\run_tests.py ..."
```

- 必须设 `PYTHONIOENCODING=utf-8` 防止 GBK 编码错误
- 脚本中用 `[OK]`/`[FAIL]` 代替 Unicode 符号（✓✗⚠️）
- 长测试用前台 SSH + 大 timeout（600s），不用后台

## 固件传输（编译服务器 → 测试电脑）

两跳传输（编译服务器和测试电脑不在同一子网）：

```bash
# 编译服务器 → Mac
sshpass -p '123' scp Lenovo@192.168.242.120:'C:/Users/Lenovo/fw.zip' /tmp/fw.zip

# Mac → 测试电脑
scp /tmp/fw.zip 52467@172.20.162.21:"D:/通信模组/at_kb_runs/fw.zip"
```

⚠️ scp 直接用 Windows 长路径会失败，需先在编译服务器上 `copy` 到简单路径。
