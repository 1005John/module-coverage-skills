# Level 2 增量插桩设计方案

## 概述

基于 git diff 实现函数级增量插桩，避免每次版本更新都全量重插。

## 触发条件

仓库 A（原始代码仓库）有新 commit 时，通过轮询 cron 检测 SHA 变化，触发增量分析。

## 变更分类（基于 git diff）

| 类型 | 特征 | 插桩处理 | 测试处理 |
|------|------|----------|----------|
| trivial | 赋值/常量/字符串修改，无新分支 | 桩不变 | 用例不变 |
| boundary | if/switch 条件表达式改写 | 桩不变 | 更新边界值和 expected |
| structural | 函数签名变化/新增删除代码块 | 函数级重插桩 | 更新相关用例 |
| new_func | 新增整个函数 | 新增插桩 | 补充新用例 |

## 判定逻辑

```python
def classify_change(diff_hunk):
    """根据 diff hunk 分类变更"""
    added = [l for l in diff_hunk if l.startswith('+')]
    removed = [l for l in diff_hunk if l.startswith('-')]
    
    # 纯赋值/常量修改
    if all(is_value_change(a, r) for a, r in zip(added, removed)):
        return 'trivial'
    
    # 条件表达式修改
    if any('if' in l or 'switch' in l or 'case' in l for l in added + removed):
        return 'boundary'
    
    # 新增函数
    if any(is_function_signature(l) for l in added):
        return 'new_func'
    
    return 'structural'
```

## 增量插桩流程

```
1. git diff old_commit..new_commit -- <at_source_files>
2. 逐 hunk 分类变更
3. 对 structural/new_func 类型：
   a. 定位受影响函数
   b. 删除该函数的旧桩（从 coverage_map 中移除）
   c. 对该函数重新执行插桩逻辑
   d. 新桩 ID = 当前最大 ID + 1（累加分配）
4. 更新 coverage_map.json
5. 如桩数变化，更新 cm_atcmd_extern.c 中的分母
```

## 桩 ID 策略

- 新增桩使用累加 ID（当前最大 ID + 1）
- 删除桩的 ID 不复用（避免混淆历史数据）
- 每个模块维护独立的 ID 计数器
- 跨模块不能有 ID 重叠

## 仓库架构

```
仓库 A（原始代码，不修改）
  SDK/onemo/at/src/cm_atcmd_mqtt.c    ← 干净源码

ASR-Coverage-test（插桩仓库，独立）
  SDK/onemo/at/src/cm_atcmd_mqtt.c    ← 插桩后源码
  coverage/
    maps/coverage_map.mqtt.json
    tests/generated_tests.mqtt.yaml
    results/run_result.vN.json
```

两个仓库完全独立，互不影响。插桩文件通过 git diff + apply patch 方式同步。

## 需要监控的文件路径

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

## 已知约束

1. 仓库太大（442 分支），fetch 超时，只能用 ls-remote 和 git show
2. 企业内网仓库，webhook 不可达本地 Mac mini，用轮询替代
3. 编译在 Windows 测试机上进行（SSH 远程）
4. armcc 编译器对不可达代码报 error（不是 warning）
