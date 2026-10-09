import json
import os
import subprocess
import sys
from pathlib import Path


def test_utf8_bootstrap_paths_with_non_utf8_host_locale(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config = tmp_path / "配置资料"
    library = tmp_path / "中文论文库"
    environment = {**os.environ, "PYTHONPATH": str(root / "backend"), "PYTHONUTF8": "0",
                   "PYTHONIOENCODING": "gbk"}
    process = subprocess.Popen([sys.executable, "-m", "papervault"], cwd=root, env=environment,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    payload = json.dumps({"token": "x"*64, "config_path": str(config), "library_path": str(library)},
                         ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        stdout, stderr = process.communicate(payload, timeout=20)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
    assert json.loads(stdout.splitlines()[0])["type"] == "ready"
    assert (library / "database/papervault.db").is_file()
    settings = json.loads((config / "settings.json").read_text(encoding="utf-8"))
    assert Path(settings["library_path"]) == library
