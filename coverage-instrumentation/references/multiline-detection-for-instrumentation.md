# 多行表达式检测：自动插桩的关键过滤

## 问题

armcc 编译器对 COV_STMT 宏插入位置要求严格。插入到多行表达式中间会产生：
- `#167: argument of type "void" incompatible with parameter of type "UINT32"`
- `#165: too few arguments in function call`
- `#18: expected a ")"`

## 触发场景

### 场景 1：多行函数调用
```c
OSATimerStart(socket_info->cm_auto_send.auto_send_timer,
              socket_info->cm_auto_send.auto_send_time * 200,
              0, __cm_tcpip_auto_send_msg, connect_id);
```
如果在 `0, __cm_tcpip_auto_send_msg, connect_id);` 前插入 COV_STMT，编译器会把函数调用拆断。

### 场景 2：多行字符串拼接
```c
cm_printf(atHandle, "\r\n+MIPCFG: \"cid\",(0-5),(1-15)\r\n"
                    "+MIPCFG: \"encoding\",(0-5),(0-2),(0-1)\r\n"
                    "+MIPCFG: \"ssl\",(0-5),(0-1),(0-5)\r\n");
```
如果在 `"+MIPCFG: \"ssl\"...` 前插入 COV_STMT，字符串拼接被打断。

## 检测算法

```python
def is_continuation_line(output_buffer):
    """检查当前位置是否在多行表达式中间"""
    for prev_line in reversed(output_buffer):
        prev_s = prev_line.strip()
        if prev_s:
            # 多行函数调用：前一行以 , 或 ( 结尾
            if prev_s.endswith(',') or prev_s.endswith('('):
                return True
            # 多行字符串拼接：前一行以 " 结尾（非 COV_ 行）
            if prev_s.endswith('"') and not prev_s.startswith('COV_'):
                return True
            break
    return False
```

## 在插桩脚本中的使用

在插入语句桩之前，调用 `is_continuation_line(output)` 判断。如果返回 True，跳过该行不插桩。

```python
# 语句桩插入逻辑
if (found_exec and s.endswith(';') and
    not is_continuation_line(output) and  # ← 关键检查
    not s.startswith('//') and ...):
    # 插入 COV_STMT
```

## 验证方法

插桩完成后，用以下脚本扫描确认无问题：

```python
lines = open(instrumented_file).read().split('\n')
for i, line in enumerate(lines):
    if 'COV_' in line:
        for j in range(i-1, max(0, i-5), -1):
            prev = lines[j].strip()
            if prev:
                if prev.endswith(',') or prev.endswith('('):
                    print(f'PROBLEM: COV at line {i+1} after comma/paren at line {j+1}')
                if prev.endswith('"') and not prev.startswith('COV_'):
                    print(f'PROBLEM: COV at line {i+1} after string literal at line {j+1}')
                break
```
