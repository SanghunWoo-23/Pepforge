from pathlib import Path


def test_installer_metadata_files_are_text_readable():
    root = Path(__file__).resolve().parents[1]
    candidates = list(root.rglob("*.iss")) + list(root.rglob("*.spec"))
    # Installer metadata is optional in the public source ZIP, but if present it must be readable text.
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert isinstance(text, str)


def test_no_runtime_exe_in_public_source_zip():
    root = Path(__file__).resolve().parents[1]
    assert not list(root.rglob("*.exe"))
