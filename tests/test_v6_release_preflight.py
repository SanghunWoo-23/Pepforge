import json
import subprocess
import sys
from pathlib import Path
from tools.v6_release_preflight import run_check


def test_preflight_success(tmp_path):
    result = run_check([sys.executable, '-c', 'print(1)'], tmp_path, 10)
    assert result['status'] == 'PASS'


def test_preflight_rejects_failed_command(tmp_path):
    result = run_check([sys.executable, '-c', 'raise SystemExit(2)'], tmp_path, 10)
    assert result['status'] == 'FAIL' and result['exit_code'] == 2


def test_preflight_timeout(tmp_path):
    result = run_check([sys.executable, '-c', 'import time; time.sleep(2)'], tmp_path, 0.01)
    assert result['status'] == 'TIMEOUT'
