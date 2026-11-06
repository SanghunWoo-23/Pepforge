"""Focused regression tests for the V6 tabbed studio and V8 packaged entry."""
from pathlib import Path
import ast
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_studio_is_tabbed_with_isolated_scrollers():
    text = (ROOT / "suite_gui/pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    ast.parse(text)
    for section in ('("structure", "1. Structure Builder")', '("docking", "2. Docking & Simulation")', '("results", "3. Results & Analysis")'):
        assert section in text
    assert 'ttk.Notebook(self)' in text
    assert 'self.studio_tabs.add(tab, text=title)' in text
    assert 'self.studio_tabs.select(1)' in text
    assert 'self.studio_tabs.select(2)' in text
    assert 'ttk.LabelFrame(docking_root, text="Docking & Simulation settings"' in text
    assert 'results_stack = ttk.Frame(results_root)' in text
    assert 'self.studio_scrollers[key] = page' in text
    for old_explanation in ('Conditions are recorded for interpretation', 'Evidence-aware peptide-only modelling', 'Balanced is recommended because'):
        assert old_explanation not in text


def test_v8_build_is_an_independent_companion_executable():
    bat = (ROOT / "INSTALL_BUILD_TOOLS_AND_BUILD.bat").read_text(encoding="utf-8")
    assert 'SPPS_Planner.spec' in bat
    assert '.spps_build_dist' in bat
    assert 'dist\\Pepforge\\SPPS_Planner\\SPPS_Planner.exe' in bat
    assert 'if errorlevel 1 (' in bat
    assert (ROOT / "vendor/spps_planner_v8/SPPS_Planner.spec").exists()
    assert (ROOT / "vendor/spps_planner_v8/main_launcher.py").exists()


def test_packaged_launch_does_not_execute_vendor_python(monkeypatch, tmp_path):
    import main_launcher
    exe = tmp_path / 'Pepforge.exe'
    nested = tmp_path / 'SPPS_Planner' / 'SPPS_Planner.exe'
    nested.parent.mkdir()
    nested.touch()
    calls = []

    class Process:
        pid = 12345
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("SPPS_Planner", timeout)

    monkeypatch.setattr(main_launcher.sys, 'executable', str(exe))
    monkeypatch.setattr(main_launcher.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(main_launcher, '_ensure_runtime_environment', lambda: None)
    monkeypatch.setattr(main_launcher.subprocess, 'Popen', lambda args, **kwargs: calls.append((args,kwargs)) or Process())
    main_launcher.run_spps_planner()
    assert calls[0][0] == [str(nested)]
    assert calls[0][1]['cwd'] == str(nested.parent)


def test_packaged_launch_missing_v8_has_actionable_error(monkeypatch, tmp_path):
    import main_launcher
    monkeypatch.setattr(main_launcher.sys, 'executable', str(tmp_path / 'Pepforge.exe'))
    monkeypatch.setattr(main_launcher.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(main_launcher, '_ensure_runtime_environment', lambda: None)
    with pytest.raises(RuntimeError, match='INSTALL_BUILD_TOOLS_AND_BUILD.bat'):
        main_launcher.run_spps_planner()


def test_source_launch_uses_matching_interpreter_and_logs_errors(monkeypatch, tmp_path):
    import main_launcher
    monkeypatch.delattr(main_launcher.sys, 'frozen', raising=False)
    monkeypatch.setattr(main_launcher, '_ensure_runtime_environment', lambda: None)
    monkeypatch.setattr(main_launcher, 'RUNTIME_LOG_DIR', tmp_path / 'logs')
    calls = []

    class Process:
        pid = 17
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired('launcher', timeout)

    monkeypatch.setattr(main_launcher.subprocess, 'Popen', lambda args, **kwargs: calls.append((args,kwargs)) or Process())
    main_launcher.run_spps_planner()
    assert calls and calls[0][0][0] == sys.executable
    assert calls[0][0][1].endswith('vendor/spps_planner_v8/main_launcher.py')
    assert (tmp_path / 'logs/spps_v8_launch.log').exists()


def test_spps_source_fast_exit_reports_log_path(monkeypatch, tmp_path):
    import main_launcher
    monkeypatch.delattr(main_launcher.sys, 'frozen', raising=False)
    monkeypatch.setattr(main_launcher, '_ensure_runtime_environment', lambda: None)
    monkeypatch.setattr(main_launcher, 'RUNTIME_LOG_DIR', tmp_path / 'log')

    class FailedProcess:
        pid = 11
        def wait(self, timeout=None):
            return 1
    monkeypatch.setattr(main_launcher.subprocess, 'Popen', lambda *a, **k: FailedProcess())
    with pytest.raises(RuntimeError, match='exited before opening its GUI') as exc:
        main_launcher.run_spps_planner()
    assert 'spps_v8_launch.log' in str(exc.value)
    assert (tmp_path / 'log/spps_v8_launch.log').exists()


def test_companion_spec_not_gitignored_and_legacy_ui_description_removed():
    ignored = (ROOT / '.gitignore').read_text(encoding='utf-8')
    studio = (ROOT / 'suite_gui/pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    assert '!vendor/spps_planner_v8/SPPS_Planner.spec' in ignored
    assert 'Evidence-aware peptide-only modelling' not in studio
    assert 'Pepforge Structure Studio v1.5.0' not in studio
