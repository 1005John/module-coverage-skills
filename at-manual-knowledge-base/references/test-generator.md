# 测试生成器技术参考

工具路径: `/Volumes/DevDrive/projects/at_knowledge_base/tools/generate_tests.py`

## 生成维度

| 维度 | 来源 | 数量级 (MQTT) |
|------|------|--------------|
| positive | 每条命令 × syntax 变体 | 25 |
| negative | commands[].negative_cases | 19 |
| boundary | test_generation_rules.boundary_cases | 39 |
| state_negative | test_generation_rules.negative_precondition_cases | 4 |
| flow | test_generation_rules.positive_cases + flows | 2 |
| example | model.example_generated_tests | 2 |

## 命令变体解析

生成器通过 `parse_syntax_variants()` 识别两种命令类型:

**位置参数命令** (如 AT+MQTTPUB):
- syntax.set 只有一条: `AT+MQTTPUB=<connect_id>,<topic>,<qos>,...`
- 直接按参数列表生成一条正向用例

**key-value 分发命令** (如 AT+MQTTCFG):
- syntax.set 有多条 `AT+CMD="<key>"` 格式
- 检测条件: key_count >= len(set_syntax) * 0.5
- 每个 key 生成独立用例，不拼接

## 可选参数处理

两种模式:
- `expand_optional=False` (默认): 去掉 `[]` 及其内容，用必选参数
- `expand_optional=True` (边界测试): 展开 `[]` 保留内容，填充默认值

嵌套清理用循环:
```python
while '[' in result:
    result = re.sub(r'\[[^\[\]]*\]', '', result)
```

## 已知局限

- topic_length 边界规则实际变异的是 msg_len 而非 topic 字符串长度（模型侧问题）
- 正向用例的 expect 是 pattern 级断言，需要匹配引擎
- 没有自动推断哪些可选参数组合有意义
