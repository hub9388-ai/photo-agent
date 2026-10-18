"""Run the repository's offline suites and publish a countable, sanitized inventory.

No live model smoke scripts are invoked. Run from the repository root:
python scripts/test_report.py --run --retouch-python <retouch-venv-python>
Build frontend/out-demo first. --run requires its dependencies and Chrome.
Without --run, regenerate the inventory from existing local result artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ZONE = timezone(timedelta(hours=8))
MODULES = [
    ('agent', 'Agent 协作与上下文', {
        'tests/test_entrypoints.py': '意图路由、统一入口与分支选择',
        'tests/test_handoff.py': '模块交接、素材选择与非法选择处理',
        'tests/test_end_to_end.py': '合成照片导入、素材到 Post 的完整入口流程',
        'tests/test_asset_recovery.py': '素材焦点恢复、失败后的上下文恢复',
        'tests/test_post_chat.py': '流式回复回退与重试边界',
        'tests/test_plan_followup.py': '规划追问及多轮上下文延续',
        'tests/test_coach_lifecycle.py': '练习任务从分配到完成的历史状态更新',
        'backend/tests/test_agent_services_stage5.py': 'Post / Coach API 请求到 Agent 服务的映射',
    }),
    ('provider', '模型与外部服务接入', {
        'tests/test_runtime.py': '配置读取、凭据缺失和模型客户端初始化',
        'tests/test_provider_adapter.py': '参考链接检索与高德 POI 响应适配',
        'tests/test_qwen_image_config.py': 'Key / URL 选择、歧义配置及不可信目标拦截',
        'backend/tests/test_settings.py': '后端配置读取',
        'backend/tests/test_legacy_imports.py': '既有 Agent 模块导入兼容',
        'backend/tests/test_skills_mcp_stage85.py': '知识加载缺失时降级及 API 暴露边界',
    }),
    ('contract', '输出协议与界面文案', {
        'tests/test_protocol.py': '文本与 JSON 分段、截断恢复与非 JSON 回退',
        'tests/test_cli.py': '中文标题、提示、排序与乱码回归',
        'backend/tests/test_agent_request_contract.py': 'Agent 请求字段与结果保存约定',
        'backend/tests/test_contract_models.py': '契约模型、事件去重与持久化规则',
    }),
    ('api', '后端 API、任务与媒体', {
        'backend/tests/test_api_contract.py': 'OpenAPI 路由与响应契约',
        'backend/tests/test_health.py': '服务健康检查',
        'backend/tests/test_job_system.py': '任务生命周期、事件、重试及结果读取',
        'backend/tests/test_media_upload.py': '上传、媒体读取与错误输入',
        'backend/tests/test_stage6_errors.py': '缺失媒体、非法任务和交接错误的结构化反馈',
    }),
    ('data', '素材、规划与数据存储', {
        'tests/test_storage.py': '档案迁移、路径脱敏、缓存复用和索引进度',
        'backend/tests/test_asset_stage7.py': '素材导入、索引、筛选及流转',
        'backend/tests/test_asset_score_api.py': '素材评分接口',
        'backend/tests/test_plan_stage8.py': '规划澄清、约束传递和任务创建边界',
    }),
    ('ops', '事件日志与部署保护', {
        'tests/test_events.py': '事件输出',
        'tests/test_trace.py': 'JSONL 追踪与用户输入摘要截断',
        'tests/test_demo_deployment.py': '并发预算、限额中间件和部署预检',
    }),
    ('advice', '后期建议转换与原图传递', {
        'backend/tests/test_retouch_advice.py': '方向、范围、跳过项、来源及照片匹配',
        'backend/tests/test_retouch_source.py': '原图无重编码传递、预览回退和路径限制',
        'tests/test_retouch_adjust_draft.py': '草稿版本、实际入参及审计字段隔离',
    }),
    ('retouch', '人物保护、笔刷与修图执行', {
        'tests/test_retouch_portrait.py': '阻止简化拆层、选区确认、原图及选区外像素保护',
        'tests/test_retouch_brush.py': '涂抹 / 套索 / 擦除语义与透明缺口拦截',
        'tests/test_retouch_live.py': '离线模拟模型请求、超时、事务失败及图像传输适配',
        'tests/test_retouch_output_limits.py': '上传与内部生成结果的不同大小限制',
    }),
    ('eval', 'Agent 执行语义评测判定器', {
        'evaluations/001-shadow-direction/test_evaluate.py': '反向参数、伪解释、擅自替代及非法调用识别',
    }),
    ('browser', '浏览器产品流程', {
        'frontend/tests/product-demo.spec.ts': '分析、修图、素材、学习、规划、导出与异常反馈',
    }),
]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def worker(kind, out):
    rows = []
    class Result(unittest.TextTestResult):
        def record(self, test, status):
            rows.append({'id': test.id(), 'status': status})
        def addSuccess(self, test):
            super().addSuccess(test)
            self.record(test, 'passed')
        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.record(test, 'failed')
        def addError(self, test, err):
            super().addError(test, err)
            self.record(test, 'error')
        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            self.record(test, 'skipped')
    location, pattern = ('tests', 'test_retouch*.py') if kind == 'retouch' else (
        'evaluations/001-shadow-direction', 'test_evaluate.py')
    suite = unittest.defaultTestLoader.discover(str(ROOT / location), pattern=pattern)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    write_json(out / f'{kind}-results.json', {
        'suite': kind, 'tests_run': result.testsRun, 'successful': result.wasSuccessful(), 'cases': rows})
    return 0 if result.wasSuccessful() else 1


def run_suites(out, retouch_python):
    out.mkdir(parents=True, exist_ok=True)
    def run(name, command, cwd=ROOT, env=None, expected=0):
        print(f'Running {name}...', flush=True)
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, encoding='utf8', errors='replace')
        (out / f'{name}.log').write_text(result.stdout + result.stderr, encoding='utf8')
        if result.returncode != expected:
            raise RuntimeError(f'{name}: exit {result.returncode}; inspect {out / (name + ".log")}')
        return result
    run('main', [sys.executable, '-m', 'pytest', '-q', f'--junitxml={out / "main-results.xml"}'])
    run('retouch', [str(retouch_python), str(Path(__file__).resolve()), '--worker', 'retouch', '--artifacts', str(out)])
    run('evaluator', [sys.executable, str(Path(__file__).resolve()), '--worker', 'evaluator', '--artifacts', str(out)])
    browser_env = {**os.environ, 'NO_PROXY': '127.0.0.1,localhost', 'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'ALL_PROXY': '',
                   'PLAYWRIGHT_JSON_OUTPUT_FILE': str(out / 'browser-results.json')}
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise RuntimeError('npm is required for the browser suite')
    run('browser', [npm, 'run', 'test:demo', '--', '--reporter=json'], ROOT / 'frontend', browser_env)
    supplements = []
    for filename in ['check_analysis_presentation.cjs', 'check_post_advice_ui.cjs', 'check_retouch_brush_ui.cjs']:
        run(filename, ['node', 'scripts/' + filename])
        supplements.append({'script': 'scripts/' + filename, 'status': 'passed'})
    run('pixels', [str(retouch_python), 'scripts/check_retouch_minimal.py', 'core'])
    supplements.append({'script': 'scripts/check_retouch_minimal.py core', 'status': 'passed'})
    base = 'evaluations/001-shadow-direction/'
    run('historical-replay', [sys.executable, base + 'evaluate.py', '--output', str(out / 'historical-evaluation.json')], expected=1)
    run('synthetic-replay', [sys.executable, base + 'evaluate.py', '--trace', base + 'fixtures/synthetic_pass.json',
                             '--output', str(out / 'synthetic-evaluation.json')])
    run('converter', [sys.executable, base + 'check_converter.py'])
    converter = json.loads((ROOT / base / 'reports/converter-result.json').read_text(encoding='utf8'))['report']
    write_json(out / 'converter-evaluation.json', converter)
    write_json(out / 'supplementary-results.json', supplements)


def generate(out):
    file_map = {path: (key, title, description) for key, title, files in MODULES for path, description in files.items()}
    rows = []
    junit = ET.parse(out / 'main-results.xml').getroot()
    main_cases = list(junit.iter('testcase'))
    main_subtests = sum(int(s.get('tests', '0')) for s in junit.iter('testsuite')) - len(main_cases)
    for item in main_cases:
        classname = item.get('classname', '')
        files = [p for p in file_map if p.endswith('.py') and classname.startswith(p[:-3].replace('/', '.'))]
        if len(files) != 1:
            raise ValueError(f'Unmapped or ambiguous case: {classname}')
        status = 'passed'
        for tag, value in [('failure', 'failed'), ('error', 'error'), ('skipped', 'skipped')]:
            if item.find(tag) is not None:
                status = value
        rows.append({'file': files[0], 'id': classname + '::' + item.get('name', ''), 'status': status, 'suite': 'main'})
    for kind in ['retouch', 'evaluator']:
        data = json.loads((out / f'{kind}-results.json').read_text(encoding='utf8'))
        if len(data['cases']) != data['tests_run']:
            raise ValueError(f'{kind}: incomplete results; inspect worker log')
        for case in data['cases']:
            name = case['id'].split('.')[0]
            path = f'tests/{name}.py' if kind == 'retouch' else 'evaluations/001-shadow-direction/test_evaluate.py'
            rows.append({'file': path, 'id': case['id'], 'status': case['status'], 'suite': kind})
    browser = json.loads((out / 'browser-results.json').read_text(encoding='utf8'))
    if browser.get('errors'):
        raise ValueError('Browser runner errors: inspect its local report')
    def visit(suite):
        for spec in suite.get('specs', []):
            for test in spec['tests']:
                status = {'expected': 'passed', 'skipped': 'skipped', 'flaky': 'flaky'}.get(test['status'], 'failed')
                rows.append({'file': 'frontend/tests/product-demo.spec.ts', 'id': spec['title'], 'status': status, 'suite': 'browser'})
        for child in suite.get('suites', []):
            visit(child)
    for suite in browser['suites']:
        visit(suite)
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, encoding='utf8').splitlines()
    actual_files = {p for p in tracked if ((p.startswith(('tests/', 'backend/tests/', 'evaluations/')) and Path(p).name.startswith('test_') and p.endswith('.py'))
                                         or (p.startswith('frontend/tests/') and p.endswith('.spec.ts')))}
    if actual_files != set(file_map):
        raise ValueError(f'Inventory map drift: unclassified={actual_files - set(file_map)}, missing={set(file_map) - actual_files}')
    if {row['file'] for row in rows} != actual_files:
        raise ValueError('Some test files have no runtime result')
    identities = [(r['suite'], r['file'], r['id']) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate runtime test identities')
    for row in rows:
        row['module'] = file_map[row['file']][0]
    counts = Counter(row['status'] for row in rows)
    modules = [{'id': key, 'name': title, 'cases': sum(r['module'] == key for r in rows),
                'passed': sum(r['module'] == key and r['status'] == 'passed' for r in rows)} for key, title, _ in MODULES]
    supplement_path = out / 'supplementary-results.json'
    supplements = json.loads(supplement_path.read_text(encoding='utf8')) if supplement_path.exists() else []
    evaluations = {}
    for name in ['historical', 'synthetic', 'converter']:
        path = out / f'{name}-evaluation.json'
        if path.exists():
            report = json.loads(path.read_text(encoding='utf8'))
            evaluations[name] = {k: report[k] for k in ['trace_kind', 'tool_execution_status', 'semantic_contract_passed', 'failed_checks']}
            evaluations[name]['check_count'] = len(report['checks'])
    result_paths = [out / name for name in ['main-results.xml', 'retouch-results.json', 'evaluator-results.json', 'browser-results.json']]
    source_times = {p.name: datetime.fromtimestamp(p.stat().st_mtime, ZONE).isoformat(timespec='seconds') for p in result_paths}
    snapshot = {'verified_date': datetime.fromtimestamp(max(p.stat().st_mtime for p in result_paths), ZONE).date().isoformat(),
                'timezone': 'Asia/Shanghai', 'generated_at': datetime.now(ZONE).isoformat(timespec='seconds'),
                'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'scope': 'Repository-owned automated tests; parameterized items count separately; subtests and scripts excluded from case total.',
                'total': len(rows), 'status_counts': dict(counts), 'main_subtests_excluded': main_subtests,
                'test_files': len(actual_files), 'result_times': source_times, 'modules': modules,
                'evidence_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in result_paths},
                'test_source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(actual_files)},
                'supplementary_script_runs': supplements, 'evaluation_replays': evaluations, 'cases': rows}
    target = ROOT / 'docs/testing'
    write_json(target / 'results.json', snapshot)
    lines = ['# 全量测试用例索引', '', f'验证日期：{snapshot["verified_date"]}（Asia/Shanghai）。', '',
             f'共 **{len(rows)} 条自动化用例**，覆盖 **{len(modules)} 个模块、{len(actual_files)} 个测试文件**。',
             f'结果：{dict(counts)}；另有 {main_subtests} 个子场景，不重复计入总数。', '',
             '统计来源为运行报告，不是函数名或 assert 数量。[阅读测试方法与结论](README.md)；[机器可读快照](results.json)。', '',
             '| 模块 | 用例数 | 通过 |', '| --- | ---: | ---: |']
    lines += [f'| {m["name"]} | {m["cases"]} | {m["passed"]} |' for m in modules]
    for key, title, files in MODULES:
        lines += ['', f'## {title}', '']
        for path, purpose in files.items():
            cases = [r for r in rows if r['file'] == path]
            lines += [f'### [{Path(path).name}](../../{path})', '', purpose + '。', '',
                      f'本次 {len(cases)} 条；' + '、'.join(f'{s} {n}' for s, n in Counter(c['status'] for c in cases).items()) + '。', '',
                      '<details>', '<summary>展开全部用例名称与结果</summary>', '']
            lines += [f'- `{c["id"]}` — {c["status"]}' for c in cases]
            lines += ['', '</details>', '']
    target.mkdir(parents=True, exist_ok=True)
    (target / 'case-inventory.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    print(json.dumps({'total': len(rows), 'status_counts': dict(counts), 'test_files': len(actual_files), 'modules': modules}, ensure_ascii=False, indent=2))
    return 0 if all(r['status'] == 'passed' for r in rows) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--retouch-python', type=Path, default=ROOT / '.test_artifacts/retouch-runtime/Scripts/python.exe')
    parser.add_argument('--artifacts', type=Path, default=ROOT / '.test_artifacts/test-inventory')
    parser.add_argument('--worker', choices=['retouch', 'evaluator'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.artifacts.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.worker:
        return worker(args.worker, out)
    if args.run:
        run_suites(out, args.retouch_python.resolve())
    return generate(out)


if __name__ == '__main__':
    raise SystemExit(main())
