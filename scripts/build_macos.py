"""用 Nuitka 把 cjtoolkit 打包成 macOS .app。

在 macOS 上跑（需要 Xcode Command Line Tools）：

    pip install -e ".[build]"
    python scripts/build_macos.py

產出：
    build/MSCJTool.app          可雙擊的應用程式
    build/MSCJTool-macos.zip    給 Release 用（.app 是資料夾，要壓成單一檔）

macOS 沒有微軟輸入法，所以「安裝 / 解除安裝」在介面上是停用的；
這個 app 只做轉換 / 打包 / 驗證 / 跨版本轉換，產出的辭典檔再拿到 Windows 安裝。

架構：跟著建置機器走。GitHub Actions 的 macos-latest 是 Apple Silicon，
所以 CI 產出的是 arm64；Intel Mac 需要自己在 Intel 機器上建。

未做簽章 / 公證（沒有 Apple 開發者帳號）。使用者第一次開會被 Gatekeeper 擋，
要在「系統設定 → 隱私權與安全性」按「仍要打開」，或 `xattr -dr com.apple.quarantine MSCJTool.app`。
Nuitka 預設會做 ad-hoc 簽章，Apple Silicon 上才跑得起來。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "cjtoolkit" / "gui" / "cjico.icns"
APP = ROOT / "build" / "MSCJTool.app"
ZIP = ROOT / "build" / "MSCJTool-macos.zip"


def _version() -> str:
    ns: dict = {}
    exec((ROOT / "cjtoolkit" / "__init__.py").read_text(encoding="utf-8"), ns)
    import re
    nums = re.findall(r"\d+", ns["__version__"])[:3]
    while len(nums) < 3:
        nums.append("0")
    return ".".join(nums)


def main() -> int:
    if sys.platform != "darwin":
        print("這個腳本只能在 macOS 上跑（Nuitka 不跨平台編 app）。", file=sys.stderr)
        return 2

    ver = _version()
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--macos-create-app-bundle",
        "--python-flag=-m",
        "--enable-plugin=pyside6",
        "--include-package-data=cjtoolkit",
        "--nofollow-import-to=pytest",
        f"--macos-app-icon={ICON}",
        "--macos-app-name=微軟倉頡碼表工具",
        f"--macos-app-version={ver}",
        "--macos-signed-app-name=com.github.arthurmcarthur.mscjtool",
        "--company-name=Arthurmcarthur",
        "--product-name=微軟倉頡碼表工具",
        f"--product-version={ver}",
        "--file-description=MicrosoftCangjieTool",
        "--copyright=MIT License",
        "--output-filename=MSCJTool",
        "--output-dir=build",
        "--assume-yes-for-downloads",
        "--remove-output",
        "cjtoolkit",
    ]
    print(" ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        return rc

    if not APP.is_dir():
        print(f"找不到 {APP}", file=sys.stderr)
        return 1
    ZIP.unlink(missing_ok=True)
    # ditto 比 zip 更能保住 .app 的 metadata / 簽章
    rc = subprocess.call(["ditto", "-c", "-k", "--keepParent", str(APP), str(ZIP)])
    if rc == 0:
        print(f"\n完成：{APP}\n      {ZIP}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
