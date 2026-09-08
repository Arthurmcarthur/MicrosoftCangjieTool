"""用 Nuitka 把 cjtoolkit 打包成單一 Windows exe。

在 Windows 上跑：

    pip install -e ".[build]"
    python scripts/build_windows.py

產出：build/MSCJTool.exe（onefile）。

同一個 exe 既是 GUI 也是 CLI：
  MSCJTool.exe              → 開圖形介面
  MSCJTool.exe --help       → 命令列用法
  MSCJTool.exe install …    → 安裝流程自我提權時就是這樣重跑自己

console-mode=attach：從主控台執行時附著上去、吃得到 stdout；從檔案總管雙擊
開 GUI 時不開黑框。提權的安裝子行程沒有主控台，改由 --log 回收輸出。
不加 UAC manifest —— 安裝流程自己會提權開子行程，主程式維持一般權限。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "cjtoolkit" / "gui" / "cjico.ico"


def _version() -> str:
    ns: dict = {}
    exec((ROOT / "cjtoolkit" / "__init__.py").read_text(encoding="utf-8"), ns)
    v = ns["__version__"]
    # Nuitka 的 --file-version 要 x.x.x.x 純數字；把 "2.0.0a0" → "2.0.0.0"
    import re
    nums = re.findall(r"\d+", v)[:4]
    while len(nums) < 4:
        nums.append("0")
    return ".".join(nums)


def main() -> int:
    if sys.platform != "win32":
        print("這個腳本只能在 Windows 上跑（Nuitka 不跨平台編 exe）。", file=sys.stderr)
        return 2

    ver = _version()
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--python-flag=-m",                 # 等同 python -m cjtoolkit
        "--enable-plugin=pyside6",
        "--include-package-data=cjtoolkit",  # data/*.tsv、gui/*.ico
        "--nofollow-import-to=pytest",
        "--windows-console-mode=attach",
        f"--windows-icon-from-ico={ICON}",
        "--company-name=Arthurmcarthur",
        "--product-name=微軟倉頡碼表工具",
        f"--file-version={ver}",
        f"--product-version={ver}",
        "--file-description=微軟倉頡碼表工具（MicrosoftCangjieTool）",
        "--copyright=MIT License",
        "--output-filename=MSCJTool.exe",
        "--output-dir=build",
        "--assume-yes-for-downloads",
        "--remove-output",
        "cjtoolkit",
    ]
    print(" ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc == 0:
        print(f"\n完成：{ROOT / 'build' / 'MSCJTool.exe'}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
