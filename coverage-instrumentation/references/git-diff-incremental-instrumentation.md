# Level 2: Git Diff 增量插桩方案

## 背景

全量插桩每次从零开始生成所有桩，效率低。实际开发中，版本迭代是增量的——大部分 commit 只改几行代码。
通过分析 git diff，可以只针对变更点调整桩，无需完全重新插桩。

## 目标仓库

```
ssh://git@code-cmiot.rdcloud.4c.hq.cmcc:8022/osc/CMIOT/fuqiang-cmiot.cmcc/ASR-Coverage-test.git
```

- 主开发分支: `OPENCPU-ML307R-FOR-SIF`
- AT 命令源码路径: `SDK/onemo/at/src/cm_atcmd_mqtt.c`, `cm_atcmd_http.c`, `cm_atcmd_tcpip.c` 等
- 底层 API 路径: `SDK/onemo/cm_mqtt/src/cm_mqtt_client.c`, `SDK/onemo/cm_http/src/` 等

## 典型 Commit 类型与桩影响分析

### 类型 1: 纯参数修复（最常见，约 60%）

```
示例: 2da9f95f [MQTT]修复MQTTCFG配置retrans和reconn缺省值为0的BUG
diff: int pkt_timeout = 0; → int pkt_timeout = 20;
```

- 桩影响: **零**。函数结构不变，行号不变，分支条件不变
- 处理: skip

### 类型 2: 条件边界调整（约 20%）

```
示例: 2f1bf130 [MQTT]心跳间隔最小可配置为5s
diff: ping_cycle < 60 → ping_cycle < 5
```

- 桩影响: **零**（桩绑定的是分支位置，不是具体数值）
- 测试用例影响: **大**（边界值需要从 60 改为 5）
- 处理: skip 桩，但更新 generated_tests.yaml 中的边界值

### 类型 3: 结构性重构（约 10%）

```
示例: 6bc18022 [MQTT]平台设备信息多个文件整合为一个
diff: 65 行新增，57 行删除
```

- 桩影响: **大**。行号偏移、分支桩可能失效、新增/删除分支
- 处理: 函数级重插桩，只处理受影响的函数

### 类型 4: 跨层修改（约 10%）

```
示例: 5a5ca4ad [MQTT]mqtts连接失败修复
diff: AT 层 + MQTT client 层 + HTTP 层同时改
```

- 桩影响: 需检查多个文件，每层独立判断
- 处理: 逐文件判断，可能涉及 AT 层 + API 层两套桩

## Level 2 实现方案

### 输入

- `old_commit`: 基准版本（已有完整插桩）
- `new_commit`: 新版本（需要增量调整）
- `coverage_map.json`: 当前桩映射

### 分析流程

```
1. git diff <old> <new> -- <target_files>
2. 解析 diff → 提取每个文件的变更 hunks
3. 对每个 hunk:
   a. 识别所在函数名
   b. 分类变更类型 (trivial / conditional / structural / functional)
   c. 评估对现有桩的影响
4. 对每个受影响函数:
   a. 查 coverage_map.json 中该函数的所有桩
   b. 计算行号偏移（新增行数 - 删除行数）
   c. 判断是否需要重插桩
5. 输出 diff_analysis.json
```

### 输出格式

```json
{
  "old_commit": "abc123",
  "new_commit": "def456",
  "files_changed": [
    {
      "path": "SDK/onemo/at/src/cm_atcmd_mqtt.c",
      "insertions": 5,
      "deletions": 3,
      "functions_affected": [
        {
          "name": "__mqtt_atcmd_cfg_retrans",
          "change_type": "trivial",
          "line_offset": 0,
          "stubs_affected": [],
          "action": "skip"
        },
        {
          "name": "__mqtt_atcmd_publish",
          "change_type": "structural",
          "line_offset": 8,
          "stubs_affected": [150, 151, 152, 1105, 1106],
          "action": "re_instrument",
          "reason": "新增 if 分支，原行号偏移 8 行"
        }
      ]
    }
  ],
  "test_case_impact": [
    {
      "case_id": "MQTT_CFG_PINGREQ_BOUNDARY_LOW",
      "reason": "ping_cycle 最小值从 60 改为 5",
      "field": "expected_boundary",
      "old_value": 60,
      "new_value": 5
    }
  ],
  "recommended_actions": {
    "skip": 15,
    "update_map": 2,
    "re_instrument": 1,
    "update_tests": 3
  }
}
```

### 增量插桩执行

对于需要 re_instrument 的函数:

1. 从 coverage_map.json 中删除该函数的旧桩记录
2. 对该函数重新运行插桩逻辑（函数级模式）
3. 新桩 ID 从当前最大 ID + 1 开始分配
4. 更新 coverage_map.json
5. 如果桩总数变了，更新 cm_atcmd_extern.c 中的分母

### 行号偏移计算

```python
def calc_line_offset(hunks):
    """计算累计行号偏移"""
    offset = 0
    for hunk in hunks:
        added = len([l for l in hunk.new_lines if l.startswith('+')])
        removed = len([l for l in hunk.old_lines if l.startswith('-')])
        offset += added - removed
    return offset
```

对于未变函数，只需将 coverage_map.json 中的 line 值加上前序 hunks 的累计偏移。

## 瓶颈与注意事项

1. **函数边界依赖正则** — 如果 diff 跨越函数边界（代码移动），会误判为两个函数都变了
2. **行号偏移仅适用于简单插入/删除** — 混合插入删除时行号可能有 ±1 偏差
3. **桩 ID 纯累加导致碎片化** — 删除桩的 ID 永远空着，长期会导致 ID 空间不连续
4. **不理解语义** — `if (a && b)` 改成 `if (a || b)` 时桩 ID 不变但含义变了
5. **跨文件 diff 需要逐文件分析** — 不能把不同文件的偏移混在一起

## 实现优先级建议

1. **Phase 1**: diff_analysis 脚本（只输出分析报告，不自动改桩）
2. **Phase 2**: 函数级增量插桩（自动更新 coverage_map.json）
3. **Phase 3**: 测试用例影响分析（自动更新 generated_tests.yaml 边界值）
