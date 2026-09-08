"""cjtoolkit 進入點。

    無參數   → 開圖形介面
    有參數   → 命令列（cjtoolkit <子命令> …）

`python -m cjtoolkit` 和打包後的 exe 都走這裏。安裝流程自我提權時，
會以 `<exe> install …` 的形式重跑自己，所以打包版也必須認得命令列參數。
"""
from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        return cli_main()

    try:
        from .gui.app import main as gui_main
    except ImportError:
        from .cli import main as cli_main
        print("未安裝 PySide6，無法開啟圖形介面。命令列用法：\n", file=sys.stderr)
        return cli_main(["--help"])
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
