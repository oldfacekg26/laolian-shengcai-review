import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from browser_step import run_step


class BrowserStepTests(unittest.TestCase):
    def test_timeout_logs_unknown_result_without_retry_or_sensitive_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'steps.jsonl'
            with patch('browser_step.subprocess.run', side_effect=subprocess.TimeoutExpired('browser', 2)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_step('browser', 'test', 'fill', ['secret-content'], log, 2)
                self.assertEqual(run.call_count, 1)
            data = log.read_text()
            self.assertNotIn('secret-content', data)
            self.assertEqual(json.loads(data)['status'], 'timeout_unknown_outcome')

    def test_failed_step_preserves_return_code(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'steps.jsonl'
            with patch('browser_step.subprocess.run', return_value=subprocess.CompletedProcess([], 3, '', 'failure')):
                result = run_step('browser', 'test', 'read', [], log)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(log.read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
