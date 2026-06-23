#!/usr/bin/env python3
"""generate_tests.py - 从 module_model.yaml 生成可执行测试用例

用法:
    python3 generate_tests.py <module_model.yaml> [output.yaml]

输入: module_model.yaml (at-manual-knowledge-base 技能产出的结构化模型)
输出: generated_tests.yaml (执行器可消费的测试用例列表)

生成维度:
    1. positive   - 每条命令至少一个正向用例 (按 syntax 变体展开)
    2. negative   - 命令级负向用例 (precondition missing, invalid params)
    3. boundary   - 参数边界值用例
    4. state_neg  - 状态负向用例 (缺前置状态)
    5. flow       - 流程级用例 (setup → steps → cleanup)
"""

import yaml
import sys
import re
import copy
from pathlib import Path
from collections import defaultdict


def load_model(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def build_flow_map(model: dict) -> dict:
    fmap = {}
    for flow in model.get('flows', []):
        fmap[flow['id']] = flow
    for name, flow in model.get('common_setup_flows', {}).items():
        fmap[name] = flow
    return fmap


def build_command_map(model: dict) -> dict:
    cmap = {}
    for cmd in model.get('commands', []):
        name = cmd['command'].replace('AT+', '')
        cmap[name] = cmd
        cmap[cmd['command']] = cmd
    return cmap


def default_param_value(param: dict) -> str:
    name = param.get('name', '')
    ptype = param.get('type', 'string')

    if 'default' in param:
        return str(param['default'])
    if 'allowed' in param:
        vals = param['allowed']
        if name == 'connect_id' and 1 in vals:
            return '1'
        return str(vals[0])
    if name == 'connect_id':
        return '1'

    if ptype == 'integer':
        r = param.get('range', param.get('typical_range'))
        if r:
            lo, hi = r[0], r[1]
            return str(min((lo + hi) // 2, 256))
        return '0'

    if ptype == 'string':
        if 'topic' in name.lower():
            return '"test/topic"'
        if 'host' in name.lower():
            return '"${MQTT_HOST}"'
        if 'client' in name.lower():
            return '"${MQTT_CLIENT_ID}"'
        if 'user' in name.lower():
            return '"${MQTT_USER}"'
        if 'pass' in name.lower() or 'passwd' in name.lower():
            return '"${MQTT_PASSWORD}"'
        if 'message' in name.lower() or 'msg' in name.lower():
            return '"test"'
        return '"test"'

    return '0'


def parse_syntax_variants(cmd: dict) -> list:
    """解析命令的语法变体，返回 [{variant_name, param_names, syntax_template}, ...]

    对于 key-value 分发命令 (如 AT+MQTTCFG)，每个 key 是独立变体。
    对于位置参数命令 (如 AT+MQTTPUB)，每个 syntax 条目是一个变体。
    """
    syntax = cmd.get('syntax', {})
    cmd_name = cmd['command']
    params = cmd.get('parameters', [])
    variants = []

    # 判断是否为 key-value 分发命令
    # 特征: 第一个参数是 key/枚举字符串，不同 key 有不同后续参数
    is_key_dispatch = False
    if params and params[0].get('name') in ('key', 'type', 'mode', 'action'):
        is_key_dispatch = True
    # 额外检测: syntax.set 中有多条以 AT+CMD="<string>" 开头的格式
    set_syntax = syntax.get('set', [])
    if not set_syntax and 'execute' in syntax:
        set_syntax = syntax.get('execute', [])
    if not set_syntax:
        # query/test 类
        for key in ('query', 'test', 'query_cache', 'read_count', 'execute'):
            if key in syntax:
                for s in syntax[key]:
                    variants.append({
                        'name': key,
                        'template': s,
                        'params_in_template': extract_template_params(s),
                    })
        return variants

    # 检查 set 语法中的字符串 key 模式
    key_pattern = re.compile(rf'^{re.escape(cmd_name)}="(\w+)"')
    key_count = 0
    for s in set_syntax:
        if key_pattern.match(s):
            key_count += 1

    if key_count > 1 and key_count >= len(set_syntax) * 0.5:
        # key-value 分发: 每个 key 独立变体
        for s in set_syntax:
            m = key_pattern.match(s)
            if m:
                key_name = m.group(1)
                variants.append({
                    'name': f'key_{key_name}',
                    'template': s,
                    'params_in_template': extract_template_params(s),
                    'key': key_name,
                })
            else:
                variants.append({
                    'name': 'default',
                    'template': s,
                    'params_in_template': extract_template_params(s),
                })
    else:
        # 位置参数命令: 每个 syntax 条目一个变体
        for key in syntax:
            entries = syntax[key] if isinstance(syntax[key], list) else [syntax[key]]
            for s in entries:
                if isinstance(s, str):
                    variants.append({
                        'name': key,
                        'template': s,
                        'params_in_template': extract_template_params(s),
                    })

    # 如果没提取到变体，至少有一个默认
    if not variants:
        variants.append({
            'name': 'default',
            'template': f'{cmd_name}=<params>',
            'params_in_template': [p['name'] for p in params if p.get('direction') != 'response'],
        })

    return variants


def extract_template_params(template: str) -> list:
    """从语法模板提取参数名列表，如 AT+CMD=<p1>,<p2>[,<p3>] → ['p1', 'p2', 'p3']"""
    # 去掉 AT+CMD= 前缀
    eq_idx = template.find('=')
    if eq_idx < 0:
        return []
    param_part = template[eq_idx + 1:]
    # 提取 <name> 或 [,<name>] 中的名字
    names = re.findall(r'<(\w+)>', param_part)
    return names


def build_at_command_from_variant(variant: dict, cmd_name: str, all_params: list, expand_optional: bool = False) -> str:
    """根据变体模板和参数默认值构建 AT 命令字符串

    expand_optional=False(默认): 可选参数不传，使用命令默认值
    expand_optional=True: 可选参数展开并填充默认值（用于边界测试）
    """
    template = variant['template']
    template_param_names = variant['params_in_template']

    param_defs = {}
    for p in all_params:
        param_defs[p['name']] = p

    result = template
    for pname in template_param_names:
        pdef = param_defs.get(pname)
        if pdef:
            val = default_param_value(pdef)
        else:
            val = '0'
        result = result.replace(f'<{pname}>', val)

    if expand_optional:
        # 展开可选参数: 去掉 [] 但保留内容
        result = result.replace('[', '').replace(']', '')
        result = re.sub(r',+', ',', result)
    else:
        # 去掉可选参数
        while '[' in result:
            result = re.sub(r'\[[^\[\]]*\]', '', result)
        result = re.sub(r',+', ',', result)
        result = result.rstrip(',')

    return result


def get_input_params_for_variant(variant: dict, all_params: list) -> list:
    """获取变体涉及的输入参数定义"""
    template_names = variant['params_in_template']
    param_defs = {p['name']: p for p in all_params}
    result = []
    for name in template_names:
        pdef = param_defs.get(name)
        if pdef and pdef.get('direction') != 'response':
            result.append(pdef)
    return result


def generate_positive_tests(cmd: dict) -> list:
    """为一条命令的所有语法变体生成正向测试用例"""
    tests = []
    cmd_name = cmd['command']
    cmd_short = cmd_name.replace('AT+', '')
    kind = cmd.get('kind', 'set')
    responses = cmd.get('responses', {})
    success_patterns = responses.get('success', [])
    source_refs = cmd.get('source_refs', [])
    all_params = cmd.get('parameters', [])
    preconditions = cmd.get('preconditions', [])

    # 解析变体
    variants = parse_syntax_variants(cmd)

    for i, variant in enumerate(variants):
        var_name = variant['name']

        # 构建 AT 命令
        at_cmd = build_at_command_from_variant(variant, cmd_name, all_params)

        # 构建 test id
        if var_name == 'default':
            test_id = f'{cmd_short}_{kind.upper()}_POSITIVE'
        else:
            test_id = f'{cmd_short}_{var_name.upper()}_POSITIVE'

        # 构建 expect
        expect = build_expect_from_responses(responses, var_name)

        # 前置状态
        setup_require = None
        for pc in preconditions:
            if isinstance(pc, str):
                if pc.startswith('MQTT_') or pc in ('PDP_ACTIVE', 'SIM_READY', 'NETWORK_REGISTERED'):
                    setup_require = pc
                    break

        test = {
            'id': test_id,
            'category': 'positive',
            'purpose': f'正向: {cmd_name} {var_name}',
            'at_command': at_cmd,
            'expect': expect,
        }
        if setup_require:
            test['preconditions'] = [setup_require]
        if source_refs:
            test['basis'] = {'command': cmd_name, 'source_refs': source_refs}
        test['coverage_targets'] = [{
            'file_hint': 'cm_atcmd_mqtt.c',
            'branch_hint': f'{cmd_short} {var_name} path',
        }]

        tests.append(test)

    # set_query 类型: 也生成查询变体
    if kind == 'set_query':
        query_id = f'{cmd_short}_QUERY_POSITIVE'
        # 用第一个 connect_id 参数作为查询参数
        connect_p = next((p for p in all_params if p['name'] == 'connect_id'), None)
        if connect_p:
            at_cmd = f'{cmd_name}={default_param_value(connect_p)}'
            expect = [{'pattern': f'+{cmd_short}: '}, {'pattern': 'OK'}]
            test = {
                'id': query_id,
                'category': 'positive',
                'purpose': f'正向: 查询 {cmd_name}',
                'at_command': at_cmd,
                'expect': expect,
            }
            if source_refs:
                test['basis'] = {'command': cmd_name, 'source_refs': source_refs}
            tests.append(test)

    return tests


def build_expect_from_responses(responses: dict, variant_name: str = '') -> list:
    """从响应定义构建 expect 列表"""
    expect = []

    # 选择合适的响应组
    if variant_name and variant_name in responses:
        patterns = responses[variant_name]
    elif 'success' in responses:
        patterns = responses['success']
    else:
        return [{'pattern': 'OK'}]

    for pat in patterns:
        if isinstance(pat, dict):
            if pat.get('none'):
                continue
            entry = {'pattern': pat['pattern']}
            if pat.get('async'):
                entry['async'] = True
                entry['timeout_ms'] = pat.get('timeout_ms', 60000)
            expect.append(entry)
        elif isinstance(pat, str):
            expect.append({'pattern': pat})

    return expect if expect else [{'pattern': 'OK'}]


def generate_negative_tests(cmd: dict) -> list:
    tests = []
    cmd_name = cmd['command']
    cmd_short = cmd_name.replace('AT+', '')
    all_params = cmd.get('parameters', [])
    input_params = [p for p in all_params if p.get('direction') != 'response']
    source_refs = cmd.get('source_refs', [])

    # 解析变体以获取正确的命令格式
    variants = parse_syntax_variants(cmd)
    # 用第一个非 key 变体或 key 变体作为基础
    base_variant = variants[0] if variants else None

    for nc in cmd.get('negative_cases', []):
        nc_id = nc.get('id', f'{cmd_short}_negative')
        mutation = nc.get('mutation', '')
        precond_missing = nc.get('precondition_missing', nc.get('precondition', ''))
        send_cmd = nc.get('send', '')
        expect = nc.get('expect', [])
        expect_error = nc.get('expect_error', False)

        if not send_cmd:
            send_cmd = build_negative_cmd(cmd, variants, input_params, mutation)
            if not send_cmd:
                continue

        built_expect = []
        if expect:
            for e in expect:
                if isinstance(e, dict) and 'pattern' in e:
                    built_expect.append({'pattern': e['pattern']})
                elif isinstance(e, str):
                    built_expect.append({'pattern': e})
        elif expect_error:
            built_expect = [{'pattern': '+CME ERROR'}]

        if not built_expect:
            built_expect = [{'pattern': '+CME ERROR'}]

        test = {
            'id': nc_id,
            'category': 'negative',
            'purpose': f'负向: {nc_id.replace("_", " ")}',
            'at_command': send_cmd,
            'expect': built_expect,
        }

        if precond_missing:
            if isinstance(precond_missing, str):
                test['preconditions_missing'] = [precond_missing]
            else:
                test['preconditions_missing'] = precond_missing

        if source_refs:
            test['basis'] = {'command': cmd_name, 'source_refs': source_refs}

        tests.append(test)

    return tests


def build_negative_cmd(cmd: dict, variants: list, input_params: list, mutation: str) -> str:
    """根据变异类型构建负向命令"""
    cmd_name = cmd['command']
    cmd_short = cmd_name.replace('AT+', '')

    # 对于 key-value 分发命令，找到相关 key 变体
    # 对于位置参数命令，用第一个变体
    target_variant = None
    for v in variants:
        if 'key' in v and mutation:
            # 尝试匹配 mutation 和 key
            if v['key'].lower() in mutation.lower():
                target_variant = v
                break
    if not target_variant:
        target_variant = variants[0] if variants else None

    if not target_variant:
        return ''

    # 如果有 send 字段直接用
    # 否则用变体模板替换变异参数
    template = target_variant['template']
    template_params = target_variant['params_in_template']
    param_defs = {p['name']: p for p in input_params}

    # 解析 mutation
    mutation_param = None
    mutation_value = None
    for pname in template_params:
        if pname in mutation:
            mutation_param = pname
            # 提取值
            m = re.search(r'=(.+)', mutation)
            if m:
                mutation_value = m.group(1)
            break

    result = template
    for pname in template_params:
        pdef = param_defs.get(pname)
        if pname == mutation_param and mutation_value:
            val = mutation_value
        elif pdef:
            val = default_param_value(pdef)
        else:
            val = '0'
        result = result.replace(f'<{pname}>', val)

    while '[' in result:
        result = re.sub(r'\[[^\[\]]*\]', '', result)
    result = re.sub(r',+', ',', result)
    result = result.rstrip(',')
    return result


def generate_boundary_tests(rules: dict, cmd_map: dict) -> list:
    tests = []
    for bc in rules.get('boundary_cases', []):
        cmd_name = bc.get('command', '')
        param_name = bc.get('parameter', '')
        values = bc.get('values', [])

        cmd_def = cmd_map.get(cmd_name) or cmd_map.get(cmd_name.replace('AT+', ''))
        if not cmd_def:
            continue

        # 找到参数定义
        param_def = None
        for p in cmd_def.get('parameters', []):
            if p['name'] == param_name:
                param_def = p
                break

        # 找到包含该参数的变体
        variants = parse_syntax_variants(cmd_def)
        target_variant = None
        for v in variants:
            if param_name in v['params_in_template']:
                target_variant = v
                break
        if not target_variant:
            target_variant = variants[0] if variants else None

        if not target_variant:
            continue

        for val in values:
            expect_error = False
            if param_def:
                r = param_def.get('range', param_def.get('typical_range'))
                allowed = param_def.get('allowed')
                if r and (val < r[0] or val > r[1]):
                    expect_error = True
                if allowed and val not in allowed:
                    expect_error = True

            # 构建命令: 替换变体模板中的目标参数
            template = target_variant['template']
            template_params = target_variant['params_in_template']
            param_defs = {p['name']: p for p in cmd_def.get('parameters', [])}

            result = template
            for pname in template_params:
                if pname == param_name:
                    result = result.replace(f'<{pname}>', str(val))
                else:
                    pdef = param_defs.get(pname)
                    if pdef:
                        result = result.replace(f'<{pname}>', default_param_value(pdef))
                    else:
                        result = result.replace(f'<{pname}>', '0')

            # 展开可选参数（边界测试需要传所有参数）
            result = result.replace('[', '').replace(']', '')
            result = re.sub(r',+', ',', result)
            result = result.rstrip(',')

            test_id = f'{cmd_name.replace("AT+", "")}_{param_name}_{val}'
            if val < 0:
                test_id = f'{cmd_name.replace("AT+", "")}_{param_name}_neg{abs(val)}'

            expect = [{'pattern': '+CME ERROR'}] if expect_error else [{'pattern': 'OK'}]

            test = {
                'id': test_id,
                'category': 'boundary',
                'purpose': f'边界: {cmd_name} {param_name}={val} {"应报错" if expect_error else "应成功"}',
                'at_command': result,
                'expect': expect,
                'basis': {
                    'command': cmd_name,
                    'rule': f'boundary_{param_name}={val}',
                },
            }
            tests.append(test)

    return tests


def generate_state_negative_tests(rules: dict) -> list:
    tests = []
    for nc in rules.get('negative_precondition_cases', []):
        test_id = nc.get('id', 'state_neg_unknown')
        send_cmd = nc.get('send', '')
        expect = nc.get('expect', [])
        missing_state = nc.get('missing_state', '')
        setup_flow = nc.get('setup_flow', '')

        built_expect = []
        for e in expect:
            if isinstance(e, dict) and 'pattern' in e:
                built_expect.append({'pattern': e['pattern']})
        if not built_expect:
            built_expect = [{'pattern': '+CME ERROR'}]

        test = {
            'id': test_id,
            'category': 'state_negative',
            'purpose': f'状态负向: {test_id.replace("_", " ")}',
            'at_command': send_cmd,
            'expect': built_expect,
        }

        if missing_state:
            test['preconditions_missing'] = [missing_state]
        if setup_flow:
            test['setup_flow'] = setup_flow

        tests.append(test)

    return tests


def generate_flow_tests(rules: dict, flow_map: dict) -> list:
    tests = []
    for pc in rules.get('positive_cases', []):
        flow_ref = pc.get('generate_from_flow', '')
        if not flow_ref:
            continue

        flow = flow_map.get(flow_ref)
        if not flow:
            continue

        test_id = pc.get('id', f'flow_{flow_ref}')
        test = {
            'id': test_id.upper(),
            'category': 'flow',
            'purpose': f'流程: {flow.get("title", flow_ref)}',
            'flow_ref': flow_ref,
            'source_refs': flow.get('source_refs', []),
        }

        if 'setup' in flow:
            test['setup'] = expand_flow_steps(flow['setup'])
        if 'steps' in flow:
            test['steps'] = expand_flow_steps(flow['steps'])
        if 'cleanup' in flow:
            test['cleanup'] = expand_flow_steps(flow['cleanup'])
        if flow.get('preconditions'):
            test['preconditions'] = flow['preconditions']

        tests.append(test)

    return tests


def expand_flow_steps(steps: list) -> list:
    result = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        expanded = {}
        if 'send' in step:
            expanded['send'] = step['send']
        if 'expect' in step:
            expanded['expect'] = []
            for e in step['expect']:
                if isinstance(e, dict):
                    entry = {'pattern': e['pattern']}
                    if e.get('async'):
                        entry['async'] = True
                        entry['timeout_ms'] = e.get('timeout_ms', 60000)
                    expanded['expect'].append(entry)
        if 'wait_for' in step:
            expanded['wait_for'] = []
            for w in step['wait_for']:
                if isinstance(w, dict):
                    entry = {'pattern': w['pattern']}
                    entry['timeout_ms'] = w.get('timeout_ms', 120000)
                    expanded['wait_for'].append(entry)
        if 'expect_no_urc' in step:
            expanded['expect_no_urc'] = step['expect_no_urc']
        if 'id' in step:
            expanded['step_id'] = step['id']
        if expanded:
            result.append(expanded)
    return result


def generate_from_example_tests(model: dict) -> list:
    tests = []
    for egt in model.get('example_generated_tests', []):
        test = copy.deepcopy(egt)
        test['source'] = 'model_example'
        if 'category' not in test:
            test['category'] = 'example'
        tests.append(test)
    return tests


def generate_tests(model_path: str) -> dict:
    model = load_model(model_path)
    module_name = model.get('module', 'UNKNOWN')
    version = model.get('version', 'draft')

    flow_map = build_flow_map(model)
    cmd_map = build_command_map(model)
    rules = model.get('test_generation_rules', {})

    all_tests = []
    stats = defaultdict(int)

    # 1. 正向用例
    for cmd in model.get('commands', []):
        tests = generate_positive_tests(cmd)
        all_tests.extend(tests)
        stats['positive'] += len(tests)

    # 2. 命令级负向用例
    for cmd in model.get('commands', []):
        tests = generate_negative_tests(cmd)
        all_tests.extend(tests)
        stats['negative'] += len(tests)

    # 3. 边界用例
    tests = generate_boundary_tests(rules, cmd_map)
    all_tests.extend(tests)
    stats['boundary'] += len(tests)

    # 4. 状态负向用例
    tests = generate_state_negative_tests(rules)
    all_tests.extend(tests)
    stats['state_negative'] += len(tests)

    # 5. 流程用例
    tests = generate_flow_tests(rules, flow_map)
    all_tests.extend(tests)
    stats['flow'] += len(tests)

    # 6. 模型样例用例
    tests = generate_from_example_tests(model)
    all_tests.extend(tests)
    stats['example'] += len(tests)

    # 去重
    seen = set()
    deduped = []
    for t in all_tests:
        tid = t.get('id', '')
        if tid not in seen:
            seen.add(tid)
            deduped.append(t)
        else:
            stats['deduplicated'] += 1

    output = {
        'meta': {
            'module': module_name,
            'model_version': version,
            'source_model': str(model_path),
            'total_tests': len(deduped),
            'generation_stats': dict(stats),
        },
        'tests': deduped,
    }

    return output


def main():
    if len(sys.argv) < 2:
        print('用法: python3 generate_tests.py <module_model.yaml> [output.yaml]')
        sys.exit(1)

    model_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    result = generate_tests(model_path)

    meta = result['meta']
    stats = meta['generation_stats']
    print(f'模块: {meta["module"]}')
    print(f'总计: {meta["total_tests"]} 条用例')
    print(f'  正向:     {stats.get("positive", 0)}')
    print(f'  负向:     {stats.get("negative", 0)}')
    print(f'  边界:     {stats.get("boundary", 0)}')
    print(f'  状态负向: {stats.get("state_negative", 0)}')
    print(f'  流程:     {stats.get("flow", 0)}')
    print(f'  样例:     {stats.get("example", 0)}')
    if stats.get('deduplicated'):
        print(f'  去重:     {stats["deduplicated"]}')

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(result, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)
        print(f'\n已输出: {output_path}')
    else:
        print('\n--- YAML 输出 ---')
        yaml.dump(result, sys.stdout, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)


if __name__ == '__main__':
    main()
