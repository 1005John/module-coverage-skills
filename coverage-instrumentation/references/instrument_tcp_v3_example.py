#!/usr/bin/env python3
"""
TCP 模块 AT 层自动插桩脚本 v3 — 经过实战验证的参考实现
可用于其他模块（SSL/DNS/FTP 等）的插桩模板

使用方法:
1. 修改 SRC/OUT/MAP 路径
2. 修改 STMT_START/STMT_END/BRANCH_START/BRANCH_END
3. 修改 cmd_map 映射
4. 运行: python3 instrument_xxx_v3.py
5. 验证: wc -c 输出文件应大于原始文件
6. 在输出文件头部加入模块独立计数器代码
"""
import re, json

SRC = "cm_atcmd_xxx.c"          # 原始源码
OUT = "cm_atcmd_xxx_instrumented.c"  # 插桩后输出
MAP = "coverage_map.json"       # 桩映射

STMT_START = 500                # 语句桩起始 ID（按模块分配）
STMT_END = 799
BRANCH_START = 2500             # 分支桩起始 ID
BRANCH_END = 2899

def instrument():
    with open(SRC, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    stmt_id = STMT_START
    branch_id = BRANCH_START
    stubs = {}
    output = []
    
    in_func = False
    brace_depth = 0
    func_name = ""
    found_exec = False
    pending_branch = None  # (branch_id, indent, cond_text, func_name)
    
    # AT 命令处理函数 → 命令名映射
    cmd_map = {
        "cmXXX": "XXX",
        # 添加你的模块函数映射
    }
    
    for i, line in enumerate(lines):
        s = line.strip()
        indent = re.match(r'^(\s*)', line).group(1)
        
        # 检测函数定义（RETURNCODE_T / void / int / static void 等）
        m = re.match(r'^(?:static\s+)?(?:RETURNCODE_T|void|int|OSA_STATUS)\s+(\w+)\s*\(', s)
        if m and brace_depth <= 0:
            func_name = m.group(1)
            in_func = True
            brace_depth = 0
            found_exec = False
        
        # 追踪花括号深度
        if in_func:
            brace_depth += s.count('{') - s.count('}')
            if brace_depth <= 0 and '}' in s and i > 0:
                in_func = False
                func_name = ""
        
        # === 在函数体内插桩 ===
        if in_func and brace_depth > 0:
            # 跳过：空行、注释、声明、{、预处理
            if (not s or s.startswith('//') or s.startswith('/*') or s.startswith('*') or
                s.startswith('#') or s.startswith('{') or
                re.match(r'^(int|char|void|const|static|unsigned|UINT|RETURNCODE)', s)):
                output.append(line)
                i += 1  # 不需要，for 循环自动 +1
                continue
            
            # --- 函数入口桩 ---
            if not found_exec and s and not s.startswith('}'):
                found_exec = True
                if stmt_id <= STMT_END:
                    hint = cmd_map.get(func_name, func_name)
                    stubs[str(stmt_id)] = {"kind": "entry", "file": SRC, "line": i+1,
                        "function": func_name, "condition": "", "nearby_source": s[:80],
                        "command_hint": hint, "param_hints": [], "category_hint": "function_entry"}
                    output.append(f"{indent}COV_STMT({stmt_id}); /* entry: {func_name} */\n")
                    stmt_id += 1
            
            # --- 分支桩: if/else if ---
            if re.match(r'^(else\s+)?if\s*\(', s):
                cond_m = re.search(r'\((.+?)\)\s*$', s.rstrip())
                cond_text = cond_m.group(1)[:60] if cond_m else ""
                if '{' in s:
                    # 同行有 {
                    if branch_id <= BRANCH_END:
                        hint = cmd_map.get(func_name, func_name)
                        stubs[str(branch_id)] = {"kind": "branch_true", "file": SRC, "line": i+1,
                            "function": func_name, "condition": cond_text, "nearby_source": s[:80],
                            "command_hint": hint, "param_hints": [], "category_hint": "branch"}
                        output.append(line)
                        output.append(f"{indent}    COV_BRANCH_T({branch_id}); /* branch: {cond_text[:40]} */\n")
                        branch_id += 1
                        continue
                else:
                    pending_branch = (branch_id, indent, cond_text, func_name)
            
            # --- 分支桩: else { ---
            elif re.match(r'^else\s*\{', s):
                if branch_id <= BRANCH_END:
                    hint = cmd_map.get(func_name, func_name)
                    stubs[str(branch_id)] = {"kind": "branch_false", "file": SRC, "line": i+1,
                        "function": func_name, "condition": "else", "nearby_source": s[:80],
                        "command_hint": hint, "param_hints": [], "category_hint": "branch"}
                    output.append(line)
                    output.append(f"{indent}    COV_BRANCH_F({branch_id}); /* branch: else */\n")
                    branch_id += 1
                    continue
            
            elif s == 'else':
                pending_branch = (branch_id, indent, "else", func_name)
            
            # --- pending branch 落地 ---
            elif s == '{' and pending_branch:
                bid, p_indent, cond_text, p_func = pending_branch
                pending_branch = None
                if bid <= BRANCH_END:
                    is_else = (cond_text == "else")
                    kind = "branch_false" if is_else else "branch_true"
                    hint = cmd_map.get(p_func, p_func)
                    stubs[str(bid)] = {"kind": kind, "file": SRC, "line": i+1,
                        "function": p_func, "condition": cond_text, "nearby_source": s[:80],
                        "command_hint": hint, "param_hints": [], "category_hint": "branch"}
                    output.append(line)
                    macro = "COV_BRANCH_F" if is_else else "COV_BRANCH_T"
                    output.append(f"{indent}    {macro}({bid}); /* branch: {cond_text[:40]} */\n")
                    branch_id += 1
                    continue
            
            # --- 语句桩 ---
            # 三大陷阱检测：多行函数调用、多行字符串拼接、单行 if
            in_multiline = False
            if output:
                for prev_line in reversed(output):
                    prev_s = prev_line.strip()
                    if prev_s:
                        if prev_s.endswith(',') or prev_s.endswith('('):
                            in_multiline = True
                        if prev_s.endswith('"') and not prev_s.startswith('COV_'):
                            in_multiline = True
                        break
            
            if (found_exec and s and s.endswith(';') and
                not in_multiline and
                not s.startswith('//') and not s.startswith('/*') and not s.startswith('*') and
                not s.startswith('#') and not s.startswith('{') and not s.startswith('}') and
                not s.startswith('COV_') and not s.startswith('case ') and not s.startswith('default') and
                not re.match(r'^(int|char|void|const|static|unsigned|UINT|RETURNCODE)', s) and
                not any(s.startswith(k) for k in ['return', 'goto', 'break', 'continue', 'CM_RETURN'])):
                
                # 前一行不是 return/break/CM_RETURN
                if output and any(output[-1].strip().startswith(k) for k in ['return', 'goto', 'break', 'continue', 'CM_RETURN']):
                    pass
                elif stmt_id <= STMT_END:
                    hint = cmd_map.get(func_name, func_name)
                    stubs[str(stmt_id)] = {"kind": "stmt", "file": SRC, "line": i+1,
                        "function": func_name, "condition": "", "nearby_source": s[:80],
                        "command_hint": hint, "param_hints": [], "category_hint": "statement"}
                    output.append(f"{indent}COV_STMT({stmt_id}); /* stmt */\n")
                    stmt_id += 1
        
        output.append(line)
    
    # 写出插桩文件
    with open(OUT, 'w', encoding='utf-8') as f:
        f.writelines(output)
    
    # 写 coverage_map.json
    cov_map = {
        "module": SRC.replace("cm_atcmd_", "").replace(".c", ""),
        "source_file": SRC,
        "stmt_range": [STMT_START, stmt_id - 1],
        "branch_range": [BRANCH_START, branch_id - 1],
        "total_stubs": len(stubs),
        "stmt_count": stmt_id - STMT_START,
        "branch_count": branch_id - BRANCH_START,
        "stubs": stubs
    }
    with open(MAP, 'w', encoding='utf-8') as f:
        json.dump(cov_map, f, indent=2, ensure_ascii=False)
    
    return stmt_id - STMT_START, branch_id - BRANCH_START, len(stubs)

if __name__ == "__main__":
    s, b, t = instrument()
    print(f"Instrumentation complete:")
    print(f"  Statement stubs: {s} (IDs {STMT_START}-{STMT_START + s - 1})")
    print(f"  Branch stubs: {b} (IDs {BRANCH_START}-{BRANCH_START + b - 1})")
    print(f"  Total: {t}")
