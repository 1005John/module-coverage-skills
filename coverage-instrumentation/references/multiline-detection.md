# 插桩脚本多行检测规则

在对 C 源码自动插入 COV_STMT/COV_BRANCH 宏时，必须跳过以下多行结构，否则编译报错。

## 规则 1: 多行字符串拼接

C 语言相邻字符串字面量自动拼接：
```c
cm_printf(atHandle, "\r\n+MIPCFG: \"cid\",(0-5),(1-15)\r\n"
                    "+MIPCFG: \"encoding\",(0-5),(0-2),(0-1)\r\n"
                    "+MIPCFG: \"ssl\",(0-5),(0-1),(0-5)\r\n");
```

**错误插入**（编译报 `#18: expected a ")"`）：
```c
cm_printf(atHandle, "\r\n+MIPCFG: \"cid\",(0-5),(1-15)\r\n"
                    COV_STMT(581); /* 错误！ */
                    "+MIPCFG: \"encoding\",(0-5),(0-2),(0-1)\r\n"
```

**检测**：前一行以 `"` 结尾（且不是 COV_ 行）时，当前行是字符串续行，跳过。

## 规则 2: 多行函数调用参数

```c
OSATimerStart(socket_info->cm_auto_send.auto_send_timer,
              socket_info->cm_auto_send.auto_send_time * 200,
              0, __cm_tcpip_auto_send_msg, connect_id);
```

**错误插入**（编译报 `#167: argument of type "void"`）：
```c
OSATimerStart(socket_info->cm_auto_send.auto_send_timer,
              socket_info->cm_auto_send.auto_send_time * 200,
              COV_STMT(515); /* 错误！ */
              0, __cm_tcpip_auto_send_msg, connect_id);
```

**检测**：前一行以 `,` 或 `(` 结尾时，当前行是函数参数续行，跳过。

## 规则 3: 单行 if/else body

```c
if (x > 0) return -1;  /* 无花括号 */
```

**错误插入**：
```c
if (x > 0) COV_STMT(100); return -1; /* COV_STMT 变成 if body */
```

**检测**：前一行是 `if/else if/else` 且无 `{` 时，跳过。

## 实现模板

```python
def should_skip_insertion(lines, current_idx):
    """检查当前行是否不应插入桩"""
    # 找前一个非空行
    for j in range(current_idx - 1, max(0, current_idx - 5), -1):
        prev = lines[j].strip()
        if not prev:
            continue
        # 规则 1: 字符串续行
        if prev.endswith('"') and not prev.startswith('COV_'):
            return True
        # 规则 2: 函数参数续行
        if prev.endswith(',') or prev.endswith('('):
            return True
        # 规则 3: 单行 if body
        if re.match(r'^(if|else\s+if|else)\s*(\(.*\))?\s*$', prev):
            return True
        break
    return False
```
