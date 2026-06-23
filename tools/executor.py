#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""executor.py - 从 generated_tests.yaml 驱动 AT 命令执行，采集覆盖率。

用法:
    python3 executor.py generated_tests.yaml [--config env.yaml] [--run-id v1]

输入:
    generated_tests.yaml  — generate_tests.py 产出的用例列表
    env.yaml              — 串口、broker、覆盖率等环境配置

输出:
    runs/<run_id>/
        run_result.json        — 每条命令的原始响应
        assertion_result.json  — 断言通过/失败
        coverage_summary.json  — 覆盖率汇总
        bug_candidates.json    — 行为不符手册的潜在 bug
        at_execution_log.txt   — 完整 AT 日志
        run_summary.md         — 人可读摘要
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

try:
    import serial
except ImportError:
    print("需要 pyserial: pip install pyserial")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════

def load_config(config_path: str) -> dict:
    """加载 env.yaml 配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_tests(tests_path: str) -> dict:
    """加载 generated_tests.yaml"""
    with open(tests_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ═══════════════════════════════════════════════════════════════
# 串口通信
# ═══════════════════════════════════════════════════════════════

class ATSerial:
    """AT 串口通信封装"""

    def __init__(self, port: str, baud: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None
        self.log_lines = []

    def connect(self):
        self.ser = serial.Serial(
            self.port, self.baud,
            timeout=self.timeout,
            bytesize=8, parity='N', stopbits=1
        )
        time.sleep(0.5)
        self.ser.read_all()  # 清空缓冲区
        self.log(f"已连接 {self.port} @ {self.baud}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        self.log_lines.append(line)

    def send(self, cmd: str, wait: float = 1.0) -> str:
        """发送 AT 命令，等待固定时间后读取响应"""
        self.log(f">>> {cmd}")
        self.ser.write((cmd + "\r\n").encode())
        time.sleep(wait)
        raw = self.ser.read_all()
        resp = raw.decode("utf-8", errors="replace").strip()
        self.log(f"<<< {resp[:300]}")
        return resp

    def send_wait_urc(self, cmd: str, urc_pattern: str, timeout: float = 30.0) -> tuple:
        """发送命令并等待 URC 出现。

        Returns:
            (full_response, urc_found, elapsed)
        """
        self.log(f">>> {cmd} (等待 URC: {urc_pattern[:40]}, 超时 {timeout}s)")
        self.ser.write((cmd + "\r\n").encode())

        collected = ""
        t0 = time.time()
        urc_found = False
        urc_regex = re.compile(pattern_to_regex(urc_pattern)) if urc_pattern else None

        while time.time() - t0 < timeout:
            time.sleep(0.5)
            chunk = self.ser.read_all()
            if chunk:
                collected += chunk.decode("utf-8", errors="replace")
                if urc_regex and urc_regex.search(collected):
                    urc_found = True
                    # 多等 1 秒收集后续数据
                    time.sleep(1.0)
                    remaining = self.ser.read_all()
                    if remaining:
                        collected += remaining.decode("utf-8", errors="replace")
                    break

        elapsed = round(time.time() - t0, 1)
        collected = collected.strip()
        self.log(f"<<< {collected[:300]} (URC={'是' if urc_found else '否'}, {elapsed}s)")
        return collected, urc_found, elapsed


# ═══════════════════════════════════════════════════════════════
# 模式匹配
# ═══════════════════════════════════════════════════════════════

def pattern_to_regex(pattern: str) -> str:
    """将 expect pattern 转换为正则表达式。

    <name> → 匹配任意非逗号/引号内容
    其他字符 → 字面量匹配
    """
    pattern = re.sub(r'\[[^\]]*\]', '', pattern)
    pattern = pattern.replace('...', '<any>')
    # 转义正则特殊字符（但保留 <> 用于替换）
    escaped = re.escape(pattern)
    # 恢复 <name> 占位符
    escaped = escaped.replace(r'\<', '<').replace(r'\>', '>')
    # 将 <name> 替换为通配
    regex = re.sub(r'<\w+>', r'[^,\\r\\n]*', escaped)
    return regex


def match_pattern(pattern: str, response: str) -> bool:
    """检查 response 中是否包含匹配 pattern 的行"""
    regex = pattern_to_regex(pattern)
    for line in response.split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.search(regex, line):
            return True
    return False


# ═══════════════════════════════════════════════════════════════
# 覆盖率采集
# ═══════════════════════════════════════════════════════════════

COV_RE = re.compile(r"MQTT\((\d+)%,(\d+)%,"  r"(\d+)/(\d+)\)")


def parse_coverage(resp: str) -> dict:
    """解析 AT+COVERAGE? 响应"""
    m = COV_RE.search(resp)
    if m:
        return {
            'stmt_percent': int(m.group(1)),
            'branch_percent': int(m.group(2)),
            'hit_stubs': int(m.group(3)),
            'total_stubs': int(m.group(4)),
        }
    # 备用: 尝试解析通用格式
    m2 = re.search(r'(\d+)%.*?(\d+)%.*?(\d+)/(\d+)', resp)
    if m2:
        return {
            'stmt_percent': int(m2.group(1)),
            'branch_percent': int(m2.group(2)),
            'hit_stubs': int(m2.group(3)),
            'total_stubs': int(m2.group(4)),
        }
    return {'stmt_percent': 0, 'branch_percent': 0, 'hit_stubs': 0, 'total_stubs': 0}


def get_coverage(at: ATSerial) -> dict:
    """查询当前覆盖率"""
    resp = at.send("AT+COVERAGE?", 1.0)
    return parse_coverage(resp)


# ═══════════════════════════════════════════════════════════════
# 断言判定
# ═══════════════════════════════════════════════════════════════

def judge_response(response: str, expect: list) -> dict:
    """判定响应是否符合预期。

    Returns:
        {
            'passed': bool,
            'matched': [pattern, ...],
            'missed': [pattern, ...],
            'details': [{pattern, matched, line}, ...]
        }
    """
    if not expect:
        return {'passed': True, 'matched': [], 'missed': [], 'details': []}

    matched = []
    missed = []
    details = []

    for exp in expect:
        if not isinstance(exp, dict):
            continue
        pattern = exp.get('pattern', '')
        is_async = exp.get('async', False)
        # 异步 URC 的判定在 send_wait_urc 中处理，这里只判定同步响应
        if is_async:
            continue

        found = match_pattern(pattern, response)
        if found:
            matched.append(pattern)
        else:
            missed.append(pattern)
        details.append({'pattern': pattern, 'matched': found, 'async': is_async})

    passed = len(missed) == 0
    return {'passed': passed, 'matched': matched, 'missed': missed, 'details': details}


def judge_urc(urc_response: str, expect: list) -> dict:
    """判定异步 URC 是否符合预期"""
    matched = []
    missed = []
    details = []

    for exp in expect:
        if not isinstance(exp, dict):
            continue
        if not exp.get('async'):
            continue
        pattern = exp.get('pattern', '')
        found = match_pattern(pattern, urc_response)
        if found:
            matched.append(pattern)
        else:
            missed.append(pattern)
        details.append({'pattern': pattern, 'matched': found, 'async': True})

    passed = len(missed) == 0
    return {'passed': passed, 'matched': matched, 'missed': missed, 'details': details}


# ═══════════════════════════════════════════════════════════════
# 环境变量替换
# ═══════════════════════════════════════════════════════════════

def substitute_env(cmd: str, env_vars: dict) -> str:
    """替换命令中的 ${VAR} 环境变量"""
    for key, val in env_vars.items():
        cmd = cmd.replace(f'${{{key}}}', str(val))
    return cmd


def normalize_command(cmd: str, env_vars: dict) -> str:
    """补齐生成器产出的可执行 AT 命令。"""
    cmd = substitute_env(cmd, env_vars).strip()
    if re.fullmatch(r'AT\+MQTTCONN=\d+,"[^"]+"', cmd):
        conn_id, host = re.match(r'AT\+MQTTCONN=(\d+),"([^"]+)"', cmd).groups()
        client_id = env_vars.get('MQTT_CLIENT_ID', f'executor_{int(time.time())}')
        port = env_vars.get('MQTT_PORT', '1883')
        user = env_vars.get('MQTT_USER', '')
        password = env_vars.get('MQTT_PASSWORD', '')
        return f'AT+MQTTCONN={conn_id},"{host}",{port},"{client_id}","{user}","{password}"'
    return cmd


# ═══════════════════════════════════════════════════════════════
# 执行器核心
# ═══════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    """单条用例执行结果"""
    id: str
    category: str
    purpose: str
    at_command: str
    status: str  # PASS / FAIL / ERROR / SKIP
    response: str
    sync_assertion: dict = field(default_factory=dict)
    urc_assertion: Optional[dict] = None
    coverage_before: dict = field(default_factory=dict)
    coverage_after: dict = field(default_factory=dict)
    new_hits: int = 0
    elapsed_ms: int = 0
    bug_candidate: Optional[dict] = None


class Executor:
    """测试执行器"""

    def __init__(self, config: dict, tests: dict, run_id: str):
        self.config = config
        self.tests = tests
        self.run_id = run_id

        # 路径
        runs_dir = config.get('paths', {}).get('runs_dir', 'runs')
        self.run_dir = Path(runs_dir) / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # 串口
        serial_cfg = config.get('serial', {})
        self.port = serial_cfg.get('at_port', 'COM16')
        self.baud = serial_cfg.get('baudrate', 115200)

        # 网络
        net = config.get('network', {})
        self.env_vars = {
            'MQTT_HOST': net.get('mqtt_broker', '8.137.154.246'),
            'MQTT_PORT': str(net.get('mqtt_port', 1883)),
            'MQTT_CLIENT_ID': f'executor_{run_id}',
            'MQTT_USER': net.get('mqtt_username', ''),
            'MQTT_PASSWORD': net.get('mqtt_password', ''),
            'MQTTS_HOST': net.get('mqtt_broker', '8.137.154.246'),
            'MQTTS_PORT': str(net.get('mqtt_port', 8883)),
            'MQTT_CLIENT_ID_DUP': f'dup_{run_id}',
        }

        # 覆盖率
        cov_cfg = config.get('coverage', {})
        self.cov_targets = cov_cfg.get('targets', {})
        self.max_iterations = cov_cfg.get('max_iterations', 3)

        # 结果
        self.results: list[TestResult] = []
        self.coverage_history = []
        self.bug_candidates = []

    def run(self):
        """执行所有测试用例"""
        meta = self.tests.get('meta', {})
        test_list = self.tests.get('tests', [])
        total = len(test_list)

        self.log(f"开始执行: {meta.get('module', '?')} 模块, {total} 条用例")
        self.log(f"运行 ID: {self.run_id}")

        at = ATSerial(self.port, self.baud)
        try:
            at.connect()

            # 清理: 断开所有可能的连接
            self._cleanup_all(at)

            # 重置覆盖率
            at.send("AT+COVERAGE=1", 1.0)
            cov = get_coverage(at)
            self.log(f"初始覆盖率: {cov['stmt_percent']}%/{cov['branch_percent']}% "
                     f"({cov['hit_stubs']}/{cov['total_stubs']})")
            self.coverage_history.append({'phase': 'init', **cov})
            prev_hits = cov['hit_stubs']

            # 按 category 排序执行
            category_order = ['flow', 'positive', 'boundary', 'negative', 'state_negative', 'example']
            sorted_tests = sorted(test_list,
                                  key=lambda t: category_order.index(t.get('category', 'example'))
                                  if t.get('category', 'example') in category_order else 99)

            # 执行每条用例
            for i, test in enumerate(sorted_tests):
                result = self._execute_one(at, test, i + 1, total, prev_hits)
                self.results.append(result)
                prev_hits = result.coverage_after.get('hit_stubs', prev_hits)
                self._save_results(at, meta)

                # 检测潜在 bug
                if result.status == 'FAIL' and result.sync_assertion.get('missed'):
                    bug = {
                        'test_id': result.id,
                        'at_command': result.at_command,
                        'expected': result.sync_assertion.get('missed', []),
                        'actual_response': result.response[:500],
                        'category': result.category,
                    }
                    if result.urc_assertion and not result.urc_assertion.get('passed'):
                        bug['urc_missed'] = result.urc_assertion.get('missed', [])
                    self.bug_candidates.append(bug)

            # 最终覆盖率
            final_cov = get_coverage(at)
            self.log(f"最终覆盖率: {final_cov['stmt_percent']}%/{final_cov['branch_percent']}% "
                     f"({final_cov['hit_stubs']}/{final_cov['total_stubs']})")
            self.coverage_history.append({'phase': 'final', **final_cov})

        finally:
            at.close()

        # 保存结果
        self._save_results(at, meta)
        self._print_summary()

    def _execute_one(self, at: ATSerial, test: dict, idx: int, total: int,
                     prev_hits: int) -> TestResult:
        """执行单条用例"""
        test_id = test.get('id', f'T{idx}')
        category = test.get('category', '?')
        purpose = test.get('purpose', '')
        at_cmd = normalize_command(test.get('at_command', ''), self.env_vars)
        if not at_cmd:
            cov = get_coverage(at)
            result = TestResult(
                id=test_id,
                category=category,
                purpose=purpose,
                at_command='',
                status='SKIP',
                response='用例未包含 at_command，可能是未展开的 flow 用例',
                coverage_before=cov,
                coverage_after=cov,
                new_hits=0,
            )
            self.log(f"[{idx}/{total}] {test_id} ({category})")
            self.log("  → SKIP 未展开 at_command")
            return result
        expect = test.get('expect', [])
        preconds = test.get('preconditions', [])
        preconds_missing = test.get('preconditions_missing', [])

        # 替换环境变量
        at_cmd = substitute_env(at_cmd, self.env_vars)

        self.log(f"[{idx}/{total}] {test_id} ({category})")

        # 状态负向: 先确保前置状态不满足
        if preconds_missing:
            for state in preconds_missing:
                if state == 'MQTT_CONNECTED':
                    # 确保未连接
                    for cid in range(6):
                        at.send(f"AT+MQTTDISC={cid}", 0.5)
                elif state == 'MQTT_CACHED_MODE_ENABLED':
                    at.send('AT+MQTTCFG="cached",0,0', 0.5)

        # 查询覆盖率 before
        cov_before = get_coverage(at)

        # 判断是否有异步 URC 需要等待
        has_async = any(isinstance(e, dict) and e.get('async') for e in expect)
        if at_cmd.endswith('=?') or re.fullmatch(r'AT\+MQTTSUB=\d+', at_cmd):
            has_async = False
        async_timeout = 15.0
        urc_pattern = ""
        if has_async:
            for e in expect:
                if isinstance(e, dict) and e.get('async'):
                    urc_pattern = e.get('pattern', '')
                    async_timeout = e.get('timeout_ms', 30000) / 1000.0
                    break

        # 发送命令
        t0 = time.time()
        if has_async and urc_pattern:
            response, urc_found, _ = at.send_wait_urc(at_cmd, urc_pattern, async_timeout)
        else:
            response = at.send(at_cmd, 2.0)
            urc_found = None
        elapsed = int((time.time() - t0) * 1000)

        time.sleep(0.3)

        # 查询覆盖率 after
        cov_after = get_coverage(at)
        new_hits = cov_after['hit_stubs'] - prev_hits

        # 同步断言
        sync_judge = judge_response(response, expect)

        # 异步 URC 断言
        urc_judge = None
        if has_async:
            urc_judge = judge_urc(response, expect)

        # 综合判定
        passed = sync_judge['passed']
        if urc_judge and not urc_judge['passed']:
            passed = False

        # 检查 expect_no_urc
        expect_no_urc = test.get('expect_no_urc', [])
        for no_urc_pattern in expect_no_urc:
            if match_pattern(no_urc_pattern, response):
                passed = False
                sync_judge['missed'].append(f'不应出现: {no_urc_pattern}')

        status = 'PASS' if passed else 'FAIL'

        result = TestResult(
            id=test_id,
            category=category,
            purpose=purpose,
            at_command=at_cmd,
            status=status,
            response=response[:1000],
            sync_assertion=sync_judge,
            urc_assertion=urc_judge,
            coverage_before=cov_before,
            coverage_after=cov_after,
            new_hits=new_hits,
            elapsed_ms=elapsed,
        )

        self.log(f"  → {status} +{new_hits} ({cov_after['stmt_percent']}%/{cov_after['branch_percent']}%)")
        return result

    def _cleanup_all(self, at: ATSerial):
        """清理所有 MQTT 连接"""
        self.log("清理: 断开所有 MQTT 连接")
        for cid in range(6):
            at.send(f"AT+MQTTDISC={cid}", 0.5)
        time.sleep(0.5)

    def _save_results(self, at: ATSerial, meta: dict):
        """保存所有结果到文件"""
        # run_result.json
        run_results = []
        for r in self.results:
            run_results.append({
                'id': r.id,
                'category': r.category,
                'at_command': r.at_command,
                'status': r.status,
                'response': r.response,
                'new_hits': r.new_hits,
                'elapsed_ms': r.elapsed_ms,
                'coverage': r.coverage_after,
            })
        self._json(run_results, 'run_result.json')

        # assertion_result.json
        assertions = []
        for r in self.results:
            assertions.append({
                'id': r.id,
                'category': r.category,
                'passed': r.status == 'PASS',
                'sync': r.sync_assertion,
                'urc': r.urc_assertion,
            })
        self._json(assertions, 'assertion_result.json')

        # coverage_summary.json
        final_cov = self.coverage_history[-1] if self.coverage_history else {}
        cov_summary = {
            'run_id': self.run_id,
            'module': meta.get('module', '?'),
            'model_version': meta.get('model_version', '?'),
            'total_tests': len(self.results),
            'passed': sum(1 for r in self.results if r.status == 'PASS'),
            'failed': sum(1 for r in self.results if r.status == 'FAIL'),
            'coverage': final_cov,
            'coverage_history': self.coverage_history,
            'targets': self.cov_targets,
            'target_met': {
                'stmt': final_cov.get('stmt_percent', 0) >= self.cov_targets.get('module_stmt_percent', 80),
                'branch': final_cov.get('branch_percent', 0) >= self.cov_targets.get('module_branch_percent', 60),
            },
        }
        self._json(cov_summary, 'coverage_summary.json')

        # bug_candidates.json
        self._json(self.bug_candidates, 'bug_candidates.json')

        # at_execution_log.txt
        log_path = self.run_dir / 'at_execution_log.txt'
        log_path.write_text('\n'.join(at.log_lines), encoding='utf-8')

        # run_summary.md
        self._write_summary(meta, final_cov)

        self.log(f"结果已保存到: {self.run_dir}")

    def _write_summary(self, meta: dict, final_cov: dict):
        """生成人可读的 Markdown 摘要"""
        passed = sum(1 for r in self.results if r.status == 'PASS')
        failed = sum(1 for r in self.results if r.status == 'FAIL')
        total = len(self.results)

        lines = [
            f"# MQTT 覆盖率测试报告",
            f"",
            f"## 概要",
            f"- 运行 ID: `{self.run_id}`",
            f"- 模块: {meta.get('module', '?')}",
            f"- 模型版本: {meta.get('model_version', '?')}",
            f"- 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 覆盖率",
            f"| 指标 | 数值 | 目标 | 状态 |",
            f"|------|------|------|------|",
            f"| 语句 | {final_cov.get('stmt_percent', 0)}% | "
            f"{self.cov_targets.get('module_stmt_percent', 80)}% | "
            f"{'✅' if final_cov.get('stmt_percent', 0) >= self.cov_targets.get('module_stmt_percent', 80) else '❌'} |",
            f"| 分支 | {final_cov.get('branch_percent', 0)}% | "
            f"{self.cov_targets.get('module_branch_percent', 60)}% | "
            f"{'✅' if final_cov.get('branch_percent', 0) >= self.cov_targets.get('module_branch_percent', 60) else '❌'} |",
            f"| 命中/总桩 | {final_cov.get('hit_stubs', 0)}/{final_cov.get('total_stubs', 0)} | - | - |",
            f"",
            f"## 用例统计",
            f"| 分类 | 总数 | 通过 | 失败 |",
            f"|------|------|------|------|",
        ]

        cats = {}
        for r in self.results:
            c = r.category
            if c not in cats:
                cats[c] = {'total': 0, 'pass': 0, 'fail': 0}
            cats[c]['total'] += 1
            if r.status == 'PASS':
                cats[c]['pass'] += 1
            else:
                cats[c]['fail'] += 1

        for cat in ['flow', 'positive', 'boundary', 'negative', 'state_negative', 'example']:
            if cat in cats:
                c = cats[cat]
                lines.append(f"| {cat} | {c['total']} | {c['pass']} | {c['fail']} |")
        lines.append(f"| **总计** | **{total}** | **{passed}** | **{failed}** |")

        # 潜在 bug
        if self.bug_candidates:
            lines.extend([
                f"",
                f"## 潜在 Bug ({len(self.bug_candidates)} 个)",
                f"| 用例 | 命令 | 期望 | 实际响应 |",
                f"|------|------|------|----------|",
            ])
            for bug in self.bug_candidates[:20]:
                exp = ', '.join(bug.get('expected', []))[:60]
                act = bug.get('actual_response', '')[:80].replace('\n', ' ')
                lines.append(f"| {bug['test_id']} | `{bug['at_command'][:40]}` | {exp} | {act} |")

        # 覆盖率迭代
        if len(self.coverage_history) > 1:
            lines.extend([
                f"",
                f"## 覆盖率变化",
                f"| 阶段 | 语句% | 分支% | 命中 |",
                f"|------|-------|-------|------|",
            ])
            for ch in self.coverage_history:
                lines.append(f"| {ch.get('phase', '?')} | {ch.get('stmt_percent', 0)}% | "
                             f"{ch.get('branch_percent', 0)}% | {ch.get('hit_stubs', 0)} |")

        # 增量 Top10
        results_with_hits = sorted(self.results, key=lambda r: r.new_hits, reverse=True)
        top_hits = [(r.id, r.new_hits, r.at_command) for r in results_with_hits if r.new_hits > 0][:10]
        if top_hits:
            lines.extend([
                f"",
                f"## 增量命中 Top10",
                f"| 用例 | 新增命中 | 命令 |",
                f"|------|---------|------|",
            ])
            for tid, nh, cmd in top_hits:
                lines.append(f"| {tid} | +{nh} | `{cmd[:50]}` |")

        md = '\n'.join(lines)
        (self.run_dir / 'run_summary.md').write_text(md, encoding='utf-8')

    def _json(self, data, filename: str):
        path = self.run_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _print_summary(self):
        passed = sum(1 for r in self.results if r.status == 'PASS')
        failed = sum(1 for r in self.results if r.status == 'FAIL')
        total = len(self.results)
        final = self.coverage_history[-1] if self.coverage_history else {}

        print(f"\n{'='*60}")
        print(f"  执行完成: {passed}/{total} 通过, {failed} 失败")
        print(f"  覆盖率: {final.get('stmt_percent', 0)}%/{final.get('branch_percent', 0)}%"
              f" ({final.get('hit_stubs', 0)}/{final.get('total_stubs', 0)})")
        if self.bug_candidates:
            print(f"  潜在 Bug: {len(self.bug_candidates)} 个")
        print(f"  结果目录: {self.run_dir}")
        print(f"{'='*60}")

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='AT 命令测试执行器')
    parser.add_argument('tests', help='generated_tests.yaml 路径')
    parser.add_argument('--config', default='env.yaml', help='环境配置文件')
    parser.add_argument('--run-id', default=None, help='运行 ID')
    args = parser.parse_args()

    config = load_config(args.config)
    tests = load_tests(args.tests)

    run_id = args.run_id or datetime.now().strftime(f"%Y%m%d_%H%M%S_{tests['meta']['module']}")

    executor = Executor(config, tests, run_id)
    executor.run()


if __name__ == '__main__':
    main()
