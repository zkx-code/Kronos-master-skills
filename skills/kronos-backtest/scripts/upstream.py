"""Stage, check and invoke unmodified backtest entry points from the supplied Kronos project."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

SNAPSHOT = Path(__file__).resolve().parents[1] / 'assets' / 'kronos'
PROFILES = ('qlib', 'qlib-preprocess', 'csv-strategy', 'historical-demo', 'regression')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def serializable(value):
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'item'):
        return serializable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)  # Preserve undefined original metrics as text, never silently replace with zero.
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(serializable(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def verify(root, allow_config=True):
    manifest = json.loads((SNAPSHOT / 'source-manifest.json').read_text(encoding='utf-8'))
    changed = []
    verified = []
    for entry in manifest['files']:
        relative = entry['path']
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f'Missing original file: {path}')
        actual = sha(path)
        if actual != entry['sha256']:
            if allow_config and relative == 'finetune/config.py':
                changed.append({'path': relative, 'source_sha256': entry['sha256'], 'configured_sha256': actual})
            else:
                raise ValueError(f'Original implementation changed: {relative}; no silent acceptance')
        verified.append({'path': relative, 'sha256': actual})
    return {'source_root': manifest['source_root'], 'files': verified, 'configuration_changes': changed}


def stage(args):
    verify(SNAPSHOT, allow_config=False)
    target = args.work_dir.resolve()
    if target.exists():
        raise FileExistsError(f'Choose a new work directory: {target}')
    shutil.copytree(SNAPSHOT, target)
    (target / 'figures').mkdir()
    result = verify(target)
    write_json(target / 'stage.json', {'created_at': datetime.now().astimezone(), **result})
    print(json.dumps({'status': 'staged', 'work_dir': str(target), 'files': len(result['files'])}, ensure_ascii=False))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configured_path(value, base):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def check(args):
    root = args.work_dir.resolve()
    verification = verify(root)
    dependencies = ['numpy', 'pandas', 'matplotlib']
    if args.profile in ('qlib', 'qlib-preprocess', 'regression'):
        dependencies += ['torch', 'tqdm']
    if args.profile in ('qlib', 'regression'):
        dependencies += ['huggingface_hub', 'einops', 'safetensors']
    if args.profile.startswith('qlib'):
        dependencies += ['qlib']
    if args.profile == 'regression':
        dependencies += ['pytest']
    missing_dependencies = [name for name in dependencies if importlib.util.find_spec(name) is None]
    issues = []
    inputs = {}
    outputs = {}
    if args.profile in ('csv-strategy', 'historical-demo'):
        if not args.stock_code or not args.stock_code.isdigit():
            issues.append('Provide a numeric --stock-code')
        if args.data_dir is None:
            issues.append('Provide --data-dir')
        elif args.stock_code:
            history = args.data_dir.resolve() / f'{args.stock_code}_stock_data.csv'
            inputs['history'] = str(history)
            if not history.is_file():
                issues.append(f'Missing historical CSV: {history}')
        if args.profile == 'csv-strategy':
            if args.prediction_dir is None:
                issues.append('Provide --prediction-dir')
            elif args.stock_code:
                candidates = [args.prediction_dir.resolve() / f'{args.stock_code}{suffix}' for suffix in
                              ('_kronos_predictions.csv', '_detailed_predictions.csv', '_predictions.csv')]
                present = [p for p in candidates if p.is_file()]
                if not present:
                    issues.append('No predictions CSV matching original naming convention')
                else:
                    inputs['predictions'] = str(present[0])
                    inputs['other_matching_prediction_files'] = [str(p) for p in present[1:]]
    if args.profile.startswith('qlib'):
        cfg = load_module(root / 'finetune/config.py', 'original_kronos_config').Config()
        base = root / 'finetune'
        provider = configured_path(cfg.qlib_data_path, base)
        inputs['qlib_data_path'] = str(provider)
        if not provider.is_dir():
            issues.append(f'Missing Qlib market data directory: {provider}')
        if args.profile == 'qlib':
            test_data = configured_path(cfg.dataset_path, base) / 'test_data.pkl'
            inputs['test_data'] = str(test_data)
            if not test_data.is_file():
                issues.append(f'Missing test_data.pkl: {test_data}')
            for name in ('finetuned_tokenizer_path', 'finetuned_predictor_path'):
                value = getattr(cfg, name)
                inputs[name] = value
                # Original Config derives local fine-tuned checkpoint paths, not a download fallback.
                path = configured_path(value, base)
                if not path.is_dir():
                    issues.append(f'Missing configured checkpoint directory: {path}')
            outputs['predictions_pickle'] = str(configured_path(cfg.backtest_result_path, base) / cfg.backtest_save_folder_name / 'predictions.pkl')
            outputs['plot'] = str(root / 'figures/backtest_result_example.png')
        else:
            outputs['dataset_path'] = str(configured_path(cfg.dataset_path, base))
    return {'status': 'ready' if not missing_dependencies and not issues else 'requirements_missing',
            'profile': args.profile, 'python': sys.executable, 'work_dir': str(root),
            'missing_imports': missing_dependencies, 'issues': issues, 'inputs': inputs,
            'original_output_locations': outputs, 'source_verification': verification}


def run_csv(args, output):
    root = args.work_dir.resolve()
    if args.profile == 'csv-strategy':
        module = load_module(root / 'examples/run_backtest_kronos.py', 'original_csv_backtest')
        tester = module.KronosBacktester(str(args.data_dir.resolve()), str(args.prediction_dir.resolve()), args.initial_capital)
        result = tester.run_complete_backtest(args.stock_code, str(output), .02 if args.threshold is None else args.threshold)
        if result is None or any(x is None for x in result):
            raise RuntimeError('Original run_complete_backtest returned failure; inspect run.log')
        metrics, equity, trades = result
        write_json(output / 'metrics.json', metrics)
        equity.to_csv(output / 'equity.csv', index_label='date', encoding='utf-8-sig')
        write_json(output / 'trades.json', trades)
        return {'original_class': 'KronosBacktester', 'result_kind': 'original CSV strategy example',
                'limitation': 'Original code can use forecast prices for fills/valuation when actual prices are absent; no added fees or slippage'}
    module = load_module(root / 'examples/yuce/historical_backtest.py', 'original_historical_demo')
    tester = module.HistoricalBacktester(str(args.data_dir.resolve()), args.initial_capital)
    result = tester.run_complete_backtest(args.stock_code, str(output), args.lookback_days, args.pred_days,
                                         .03 if args.threshold is None else args.threshold)
    if result is None or any(x is None for x in result):
        raise RuntimeError('Original historical demo returned failure; inspect run.log')
    accuracy, performance, rows = result
    write_json(output / 'accuracy.json', accuracy)
    write_json(output / 'performance.json', performance)
    rows.to_csv(output / 'example-predictions.csv', index=False, encoding='utf-8-sig')
    return {'original_class': 'HistoricalBacktester', 'result_kind': 'random-price demonstration; NOT Kronos predictions',
            'limitation': 'Preserves original random predictions and simplified trade/metric behavior'}


def run(args):
    status = check(args)
    if status['status'] != 'ready':
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 2
    if args.output_dir is None:
        raise ValueError('--output-dir is required for run')
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f'Choose a new output directory: {output}')
    if not math.isfinite(args.initial_capital) or args.initial_capital <= 0:
        raise ValueError('initial-capital must be finite and positive')
    if args.threshold is not None and (not math.isfinite(args.threshold) or args.threshold < 0):
        raise ValueError('threshold must be finite and nonnegative')
    if args.lookback_days < 2 or args.pred_days < 1:
        raise ValueError('lookback-days >= 2 and pred-days >= 1 required')
    if args.profile == 'qlib':
        for path in status['original_output_locations'].values():
            if Path(path).exists():
                raise FileExistsError(f'Original script would overwrite an existing result: {path}; configure a new run')
    if args.profile == 'qlib-preprocess':
        directory = Path(status['original_output_locations']['dataset_path'])
        if any((directory / name).exists() for name in ('train_data.pkl', 'val_data.pkl', 'test_data.pkl')):
            raise FileExistsError('Original preprocessor would overwrite existing datasets; configure a new output directory')
    output.mkdir(parents=True)
    record = {'status': 'running', 'started_at': datetime.now().astimezone(), 'check': status,
              'arguments': vars(args).copy(), 'nonfinite_serialization': 'Original undefined numeric results are stored as strings nan/inf, not zero'}
    record['arguments'].pop('handler', None)
    write_json(output / 'run.json', record)
    # Display/storage settings only; no model, strategy, fills or statistics are monkey-patched.
    os.environ['MPLBACKEND'] = 'Agg'
    os.environ['MPLCONFIGDIR'] = str(output / '.matplotlib')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['HF_HOME'] = str(output / '.huggingface') if 'HF_HOME' not in os.environ else os.environ['HF_HOME']
    try:
        with (output / 'run.log').open('w', encoding='utf-8') as log:
            if args.profile in ('csv-strategy', 'historical-demo'):
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    record['original_result'] = run_csv(args, output)
            else:
                root = args.work_dir.resolve()
                if args.profile == 'regression':
                    command = [sys.executable, '-X', 'utf8', '-B', '-m', 'pytest', 'tests/test_kronos_regression.py', '-q']
                    cwd = root
                else:
                    filename = 'qlib_test.py' if args.profile == 'qlib' else 'qlib_data_preprocess.py'
                    command = [sys.executable, '-X', 'utf8', '-B', '-u', filename]
                    if args.profile == 'qlib':
                        command += ['--device', args.device]
                    cwd = root / 'finetune'
                record['command'] = command
                record['cwd'] = str(cwd)
                write_json(output / 'run.json', record)
                completed = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=False)
                if completed.returncode:
                    raise RuntimeError(f'Original process failed with exit code {completed.returncode}; inspect run.log')
                outputs = status['original_output_locations']
                if args.profile == 'qlib':
                    for path in outputs.values():
                        if not Path(path).is_file():
                            raise RuntimeError(f'Original output missing after process exit: {path}')
                elif args.profile == 'qlib-preprocess':
                    for name in ('train_data.pkl', 'val_data.pkl', 'test_data.pkl'):
                        if not (Path(outputs['dataset_path']) / name).is_file():
                            raise RuntimeError(f'Original preprocessing output missing: {name}')
        record['status'] = 'complete'
    except Exception as exc:
        record['status'] = 'failed'
        record['error'] = str(exc)
        with (output / 'run.log').open('a', encoding='utf-8') as log:
            traceback.print_exc(file=log)
        print(f'Failed: {exc}', file=sys.stderr)
    record['finished_at'] = datetime.now().astimezone()
    write_json(output / 'run.json', record)
    print(json.dumps({'status': record['status'], 'output_dir': str(output), 'run_log': str(output / 'run.log')}, ensure_ascii=False))
    return 0 if record['status'] == 'complete' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    st = subs.add_parser('stage', help='Copy original source to a new working directory')
    st.add_argument('--work-dir', type=Path, required=True)
    vf = subs.add_parser('verify', help='Verify original source; report allowed Config changes')
    vf.add_argument('--work-dir', type=Path, required=True)
    for name in ('check', 'run'):
        p = subs.add_parser(name)
        p.add_argument('--work-dir', type=Path, required=True)
        p.add_argument('--profile', choices=PROFILES, required=True)
        p.add_argument('--data-dir', type=Path)
        p.add_argument('--prediction-dir', type=Path)
        p.add_argument('--stock-code')
        p.add_argument('--output-dir', type=Path)
        p.add_argument('--initial-capital', type=float, default=100000)
        p.add_argument('--threshold', type=float)
        p.add_argument('--lookback-days', type=int, default=60)
        p.add_argument('--pred-days', type=int, default=30)
        p.add_argument('--device', default='cpu' if sys.platform == 'darwin' else 'cuda:0')
    args = parser.parse_args()
    if args.action == 'stage':
        stage(args)
        return 0
    if args.action == 'verify':
        print(json.dumps(verify(args.work_dir.resolve()), ensure_ascii=False, indent=2))
        return 0
    if args.action == 'check':
        result = check(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'ready' else 2
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
