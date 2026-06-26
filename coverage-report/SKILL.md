---
name: coverage-report
description: "覆盖率测试报告生成技能，支持 Markdown/JSON/Excel 多格式输出"
triggers:
  - "覆盖率报告"
  - "coverage report"
  - "生成报告"
---

# 覆盖率报告生成

## When to Use
- 覆盖率测试迭代完毕，需要生成最终报告
- 需要把结果交付给其他 Agent 或人工审查
- 需要 Excel 格式的可视化报告

## 输入

| 文件 | 说明 |
|------|------|
| coverage_detail.json / coverage_map.json | 逐桩详情和源码映射 |
| coverage_summary.json / AT+COVERAGE? 输出 | 总体覆盖率数字 |
| run_result.json / 测试结果 JSON | 每条命令的原始响应、URC、成功/失败 |
| assertion_result.json | 每条用例的预期/实际断言结果 |
| bug_candidates.json | 潜在 bug：复现步骤、期望、实际、证据 |
| 迭代记录 | 每轮覆盖率变化、阶段增量、饱和判断 |

## 输出格式

### 1. run_summary.md
必须包含：
- 项目背景、硬件环境、SDK 路径、固件版本。
- 插桩方案：文件、层级、ID 分配、计数器架构。
- 编译与烧录：命令、验证结果、失败处理。
- 每轮覆盖率表：覆盖率、命中桩、新增桩、命令数、OK/Fail、潜在 bug 数。
- 阶段增量表：每个 phase 后的 hit 变化。
- 未覆盖区域分析：按函数/原因分类。
- 潜在 bug 表：case_id、复现步骤、期望、实际、证据、严重级别、是否需人工确认。
- 用例迭代建议：继续、饱和、需新增插桩或硬件条件。
- 文件清单：脚本、JSON、日志、报告路径。

```markdown
# 覆盖率测试报告

## 概要
- 模块: HTTP (cm_atcmd_http.c + cm_http_api.c)
- 固件版本: 3.1.0.2606220923_release
- 迭代轮次: v1-v7

## 覆盖率迭代
| 轮次 | 覆盖率 | 命中桩 | 新增 | 命令数 | OK/Fail | 潜在 bug | 关键改进 |
|------|--------|--------|------|--------|---------|----------|----------|
| v5 | 53%,50% | 234/810 | +3 | 139 | 105/34 | 未统计 | 手册驱动 + HTTP API 桩 |
| v6_short | 60%,54% | 260/810 | +26 | 45 | 29/16 | 4 | datamode/WTCP/DLFILE |
| v7_short | 63%,57% | 271/810 | +11 | 76 | 69/7 | 4 | 精确 datamode/request datamode |
```

### 2. coverage_detail.json
```json
{
  "module": "http",
  "total_stubs": 450,
  "hit_stubs": 200,
  "coverage_pct": 44.4,
  "stubs": {
    "200": {"hit": true, "func": "cmiotHTTPCFG", "line": 237},
    "201": {"hit": false, "func": "cmiotHTTPCFG", "line": 238}
  }
}
```

### 3. Excel 报告
使用 openpyxl 生成，包含：
- Sheet 1: 概要（覆盖率、测试统计）
- Sheet 2: 逐桩详情（ID、函数、行号、命中状态）
- Sheet 3: 迭代历史（轮次、覆盖率变化）
- 样式：OK 绿色、ERROR 红色、新增黄色

## 报告生成脚本

```python
import json
from datetime import datetime

def generate_summary(coverage_json, test_results, output_path):
    with open(coverage_json) as f:
        cov = json.load(f)
    with open(test_results) as f:
        tests = json.load(f)
    
    total = cov['total_stubs']
    hit = cov['hit_stubs']
    pct = hit / total * 100 if total > 0 else 0
    ok = sum(1 for t in tests['results'] if t['ok'])
    fail = len(tests['results']) - ok
    
    md = f"""# 覆盖率测试报告

## 概要
- 模块: {cov['module']}
- 时间: {datetime.now().isoformat()}

## 覆盖率
- 命中: {hit}/{total} ({pct:.1f}%)

## 测试统计
- 成功: {ok}
- 失败: {fail}
"""
    with open(output_path, 'w') as f:
        f.write(md)
```

## 常见 Pitfalls

1. **HTTP 覆盖率计数器显示 >100%** — cov_http_stmt/branch_hits 每次触发都累加（不是首次命中），导致百分比超 100%。应以 ALL 的 bitmap 统计为准。**待修复**：改为只在首次命中时 +1
2. **Excel 样式需要 openpyxl** — Windows 测试机可能没装，需 pip install
3. **报告路径用绝对路径** — 不要用相对路径（Windows SSH 工作目录不确定）
4. **coverage_detail.json 和 coverage_summary.json 是不同文件** — 前者逐桩，后者汇总
5. **报告生成脚本是骨架代码** — **待完善**：需要完整 openpyxl 实现（OK 绿色/ERROR 红色/新增黄色样式）
6. **⚠️ 覆盖率概要必须分别显示 stmt% 和 branch%** — 用户明确要求覆盖率用表格格式，每模块显示语句覆盖率和分支覆盖率两列。ALL 行因固件输出不带百分号（`ALL(hit/total)`），显示为 `-`。格式：
```markdown
| 模块 | 语句覆盖率 | 分支覆盖率 | 命中/总数 |
|------|-----------|-----------|----------|
| ALL  | -         | -         | 52/132   |
| PING | 100%      | 53%       | 9/15     |
| DNS  | 100%      | 49%       | 32/60    |
```

7. **⚠️ 多模块合并覆盖率报告** — 当一个逻辑模块跨多层插桩（如 DNS AT 层 + DNSAPI 底层），报告中应分别列出每层的 stmt/branch/hit/total，再给出合并合计。合并时 stmt 和 branch 不能简单相加百分比，应按 hit/total 汇总后重算。例：
```markdown
| 模块 | 语句覆盖率 | 分支覆盖率 | 命中/总数 |
|------|-----------|-----------|----------|
| DNS (AT层) | 100% | 41% | 28/60 |
| DNSAPI (底层) | 50% | 0% | 2/16 |
| **DNS 合计** | **96%** | **39%** | **30/76** |
```
8. **⚠️ 迭代历程表必须包含饱和判断** — 迭代表除了每轮覆盖率数据，还需标注饱和原因（如"AT 层天花板"、"底层桩不可达"、"网络依赖"）。帮助用户决定是否继续迭代或接受当前覆盖率。

## 验证清单

- [ ] run_summary.md 存在且格式正确
- [ ] coverage_detail.json 存在且桩数与实际一致
- [ ] Excel 文件可打开且样式正确
- [ ] 报告中的覆盖率数字与 AT+COVERAGE? 一致
- [ ] 报告可被另一个 Agent 读取并继续执行
