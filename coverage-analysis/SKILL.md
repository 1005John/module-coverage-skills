---
name: coverage-analysis
description: "覆盖率数据分析与用例迭代技能，支持未覆盖桩分析、用例优化、自动迭代"
triggers:
  - "覆盖率分析"
  - "迭代"
  - "coverage analysis"
  - "未覆盖桩"
---

# 覆盖率分析与迭代

## When to Use
- 测试执行完毕，需要分析覆盖率结果
- 需要生成下一轮测试用例
- 需要判断是否已饱和

## 前置必读
- references/automatic-test-generation.md — 完全自动测试用例生成与迭代设计
- references/behavior-assertions-and-bug-candidates.md — 行为断言与潜在 bug 输出规则
- references/mqtt-coverage-iteration-lessons.md — MQTT 覆盖率闭环实战：数据模式、map 重建、DETAIL 不支持时的分析边界
- coverage-pipeline-main/references/end-to-end-module-coverage-workflow.md — 新模块端到端覆盖率测试实战流程
- references/http-coverage-v6-v7-lessons.md — HTTP v6/v7 覆盖率迭代经验：datamode 高收益、cached/read 饱和、潜在 bug 列表
- references/mqtt-v4-v5-iteration-lessons.md — MQTT v4/v5 迭代经验：不要停在用例执行，必须完成分析→生成增量→再执行闭环；MQTTPUB 数据模式和 cached read 高收益

## 输入

| 文件 | 说明 |
|------|------|
| coverage_map.json | 桩级映射：stub_id → 文件、行号、函数、条件、命令/参数提示 |
| module_model.yaml | 命令模型：参数约束、状态机、URC、破坏性等级 |
| run_result.json | 每条命令的真实响应、OK/ERROR、耗时、URC、环境状态、断言结果 |
| coverage_delta.json | 每个 case 新增命中桩集合，以及每个桩首次命中的 case |
| assertion_result.json | 预期结果与实际结果对比，区分 pass/fail/error/env_fail |
| bug_candidates.json | 潜在 bug：复现步骤、期望、实际、证据、严重级别 |
| coverage_detail.json | 兼容旧格式：每条用例执行后的覆盖率变化 |
| AT+COVERAGE? 输出 | 总体覆盖率数字；若无桩级明细，只能做粗粒度收益分析 |
| AT+COVERAGE=2..9 输出 | MQTT bitmap 分块，用于精确计算每个 stub 是否命中 |

## Bitmap 分析流程

### 1. 采集 Bitmap

```python
def bitmap_snapshot(ser):
    """采集 MQTT bitmap，返回 hit stub id 集合"""
    words = {}
    for cmd_value in range(2, 10):
        resp = at(ser, f'AT+COVERAGE={cmd_value}', 1.5)
        m = re.search(r'\+COVERAGE_DETAIL:\s*MQTT,(\d+),(\d+),([0-9A-Fa-f,]+)', resp)
        if m:
            base = int(m.group(2))
            hex_words = m.group(3).split(',')[:8]
            for off, word in enumerate(hex_words):
                words[base + off] = int(word, 16)
    ids = set()
    for word_index, word in words.items():
        for bit in range(32):
            sid = word_index * 32 + bit
            if word & (1 << bit):
                ids.add(sid)
    return words, ids
```

### 2. 计算 Case 增量

```python
def case_delta(before_ids, after_ids):
    """计算新增命中桩"""
    return sorted(after_ids - before_ids)
```

### 3. 生成 coverage_delta.json

```python
def generate_delta(results, coverage_map):
    """从 results 生成 coverage_delta.json"""
    case_to_new = {r['id']: r['new_stub_ids'] for r in results}
    first_hit = {}
    for r in results:
        for sid in r['new_stub_ids']:
            first_hit.setdefault(str(sid), r['id'])
    
    # 最终未覆盖桩
    final_ids = set(results[-1]['after_summary']['hit_ids'])
    map_ids = {int(k) for k in coverage_map['stubs'].keys()}
    uncovered = []
    for sid in sorted(map_ids - final_ids):
        uncovered.append({'id': sid, **coverage_map['stubs'][str(sid)]})
    
    return {
        'case_to_new_stub_ids': case_to_new,
        'stub_first_hit_case': first_hit,
        'uncovered_count': len(uncovered),
        'uncovered_stubs': uncovered,
    }
```

### 4. 未覆盖桩分类

```python
def classify_uncovered(uncovered_stubs):
    """按函数分类未覆盖桩"""
    from collections import defaultdict
    by_func = defaultdict(lambda: {'total': 0, 'stmt': 0, 'branch': 0, 'examples': []})
    for u in uncovered_stubs:
        f = u.get('func') or 'UNKNOWN'
        by_func[f]['total'] += 1
        by_func[f]['stmt' if u.get('type') == 'stmt' else 'branch'] += 1
        if len(by_func[f]['examples']) < 5:
            by_func[f]['examples'].append(u)
    return dict(sorted(by_func.items(), key=lambda kv: kv[1]['total'], reverse=True))
```

## 分析维度

### 1. 未覆盖桩分类
| 原因 | 判断方法 | 应对策略 |
|------|----------|----------|
| 参数校验未触发 | 桩在 getExtValue 附近 | 补充边界值/无效参数 |
| 错误处理未触发 | 桩在 CME ERROR 返回前 | 触发各种错误条件 |
| 连接状态未到达 | 桩在 connected 分支 | 确保连接成功后再操作 |
| 异步回调未触发 | 桩在 URC 处理中 | 等待 URC 并验证 |
| 平台特定路径 | 桩在 platsel/DevInfo | 需要特定平台配置 |
| 网络依赖 | 桩在 send/recv | 需要网络连接 |
| 多实例路径 | 桩在 conn_id>0 | 测试多个 conn_id |
| 编码模式路径 | 桩在 encoding 处理 | 切换 encoding 参数 |
| 不可达代码 | 桩在 dead code | 标记为不可达，不影响覆盖率 |

### 2. 高价值命令识别
- 单条命令触发最多新桩的命令优先执行
- 错误路径命令往往比成功路径覆盖更多分支
- 多参数命令（如 MQTTCFG）比简单命令覆盖更多

### 3. 饱和判断
- 连续 2 轮新增命中 = 0 → 饱和
- 未覆盖桩全部属于"不可达"或"平台特定" → 饱和
- 剩余未覆盖桩需要硬件/网络条件无法满足 → 条件饱和
- **AT 命令覆盖率有天花板** — HTTP 在 ~59% 饱和（195 桩在参数校验/深层错误处理中，难以通过 AT 触发）。手册驱动测试可将天花板提高 5-10%，但无法突破。突破需要：(1) 直接调用底层 API 而非 AT 命令，或 (2) 将核心层 TJ 桩也计入覆盖率

## 迭代流程

```
1. 读取 module_model.yaml + coverage_map.json
2. 读取本轮 run_result.json + coverage_delta.json + assertion_result.json
3. 统计未覆盖桩，按源码上下文和执行状态分类
4. 分析断言失败项，生成 bug_candidates.json
5. 生成候选用例池 testcase_pool.json
6. 用收益调度器选择下一轮 generated_tests.yaml
7. 真实执行下一轮增量用例，记录覆盖率变化
8. 重新分析增量结果，判断饱和条件
9. 饱和 → 输出报告；未饱和 → 回到测试执行
```

**不要在“用例执行完成”后停下。** 用户要求覆盖率分析迭代时，交付物必须是至少一个完整闭环：执行 → 分析 → 生成下一轮 → 再执行 → 汇总增量。只跑完第一批 generated_tests.yaml 不算完成。

### 自动生成策略
- 规则生成：边界值、非法值、缺参、多参、重复创建/删除、未初始化状态。
- 状态机生成：根据 pre_state/post_state 自动组合 create→cfg→request→read→del。
- 源码导向生成：根据未覆盖桩附近条件推断参数，例如 `id >= MAX`、`state != CONNECTED`、`strlen(x)==0`。
- 收益学习：记录每个 case 新增的 stub_id，优先复用历史高收益模板。
- 行为判定：每个 case 必须声明 expected_result，实际不符合时生成 bug_candidates.json。
- LLM 辅助：仅用于解释复杂代码路径和补充候选，最终仍由约束校验和真实执行结果验证。

## 输出

| 文件 | 说明 |
|------|------|
| iteration_plan.md | 下一轮用例计划和目标桩 |
| generated_tests.yaml | 下一轮实际执行用例，执行器唯一输入 |
| testcase_pool.json | 候选用例池，含来源、成本、风险、预期目标 |
| coverage_analysis.json | 分析结果（含未覆盖原因分类） |
| coverage_delta.json | case_id ↔ 新增 stub_id 的双向映射 |
| assertion_result.json | case_id ↔ 预期/实际/断言状态的映射 |
| bug_candidates.json | 断言失败转化出的潜在 bug 列表 |
| iteration_decision.json | 调度器选择/丢弃候选用例的依据 |

## 常见 Pitfalls

1. **不要只关注 OK 命令** — ERROR 命令也触发覆盖率桩
2. **conn_id 选择比参数全排列更重要** — 用 conn_id=1 而非 0
3. **每个阶段独立** — 配置→连接→操作→断开，不要跨阶段复用
4. **DNS 失败测试放最后** — 会破坏连接状态
5. **HTTP 的覆盖率计数器可能显示 >100%** — 因为每次触发都累加，用 ALL 的 bitmap 统计为准

## 验证清单

- [ ] coverage_map.json 存在，且每个未覆盖桩能定位到源码行/函数/条件
- [ ] module_model.yaml 存在，命令参数、状态机、URC timeout 明确
- [ ] coverage_delta.json 存在，能说明每个 case 新增了哪些 stub_id
- [ ] 未覆盖桩分类有具体原因（非空）
- [ ] generated_tests.yaml 针对高价值区域，且可被执行器直接消费
- [ ] iteration_decision.json 有选择依据，不只写“LLM 建议”
- [ ] 饱和判断有依据（连续 N 轮无新增或剩余桩条件不可达）
