"""Run one bounded browser step and log its duration without logging credentials.

Use --binary for a native agent-browser binary on Windows (PowerShell wrappers
may drop stdin). This helper never retries a mutation or decides to publish.
"""
import argparse
import base64
import json
import shutil
import subprocess
import time
from pathlib import Path


def run_step(binary, session, label, args, log, timeout=30):
    if not 1 <= timeout <= 60:
        raise ValueError('Timeout must be 1..60 seconds')
    started = time.monotonic()
    event = {'step': label, 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    try:
        result = subprocess.run([binary, '--session', session, *args], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout)
        event.update(status='ok' if result.returncode == 0 else 'failed', exit_code=result.returncode)
        return result
    except subprocess.TimeoutExpired:
        event.update(status='timeout_unknown_outcome')
        raise
    finally:
        event['seconds'] = round(time.monotonic() - started, 3)
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with Path(log).open('a', encoding='utf-8') as file:
            file.write(json.dumps(event, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', default=shutil.which('agent-browser'))
    p.add_argument('--session', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=30)
    p.add_argument('--eval-file', type=Path)
    p.add_argument('args', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if not a.binary:
        p.error('agent-browser not found; install from its official distribution first')
    args = a.args[1:] if a.args[:1] == ['--'] else a.args
    if a.eval_file:
        if args:
            p.error('Use --eval-file or browser arguments, not both')
        args = ['eval', '-b', base64.b64encode(a.eval_file.read_bytes()).decode('ascii')]
    try:
        result = run_step(a.binary, a.session, a.label, args, a.log, a.timeout)
    except subprocess.TimeoutExpired:
        print('Timed out: outcome unknown. Read page state before retrying any write.')
        raise SystemExit(124)
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='')
    raise SystemExit(result.returncode)
