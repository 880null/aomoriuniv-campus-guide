"""標準ライブラリだけで仮想環境を準備し、アプリを起動する。"""

import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent.parent

# インストール済みならpipを起動せず、オフラインでも利用できる。
DEPENDENCY_CHECK = """
from importlib.metadata import version
import re
checks = [('Flask', (3, 1), 4), ('pyserial', (3, 5), 4), ('waitress', (3, 0), 4)]
for name, minimum, next_major in checks:
    actual = tuple(int(n) for n in re.match(r'(\\d+)\\.(\\d+)', version(name)).groups())
    assert actual >= minimum and actual[0] < next_major
assert version('pyserial') == '3.5'
import flask, serial, waitress
"""


def main():
    if sys.version_info < (3, 10):
        print("Python 3.10以上をインストールしてください。", file=sys.stderr)
        return 1
    os.chdir(ROOT)
    directory = ROOT / ".venv"
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("Python仮想環境を作成しています…", flush=True)
        venv.EnvBuilder(with_pip=True).create(directory)
    check = subprocess.run([str(python), "-c", DEPENDENCY_CHECK], capture_output=True)
    if check.returncode:
        print("依存パッケージを準備しています（初回はインターネット接続が必要です）…", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", str(ROOT / "requirements.txt")], check=True)
        subprocess.run([str(python), "-m", "pip", "check"], check=True)
    try:
        return subprocess.call([str(python), "-m", "scripts.run", *sys.argv[1:]], cwd=ROOT)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"起動できませんでした: {exc}\nPythonとネットワーク接続を確認してください。", file=sys.stderr)
        raise SystemExit(1)
