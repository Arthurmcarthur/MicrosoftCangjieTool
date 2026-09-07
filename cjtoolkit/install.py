"""把產出的碼表套件部署到 Windows 微軟 IME 目錄。僅 Windows 可用。

兩套目標（可各自獨立安裝）：

  legacy  %windir%\\InputMethod\\Cht\\      ChtChangjie.lex / ChtChangjie.spd / ChtChangjieExt.lex
  2004    %windir%\\System32\\zh-hk\\        ChtCangjie.sdc  / ChtCangjie.spd  / ChtCangjieExt.lex

注意事項（見 CLAUDE.md「安裝」）：
  - legacy（InputMethod\\CHT）原檔屬 TrustedInstaller：需提權 + 取得所有權
    （takeown /f + icacls /grant，或 MoveFileEx 排程重開機取代）。
  - 2004（System32\\zh-hk）：只要提權即可，不必取得所有權。
  - IME 正在使用時檔案可能被鎖定：安裝前先請使用者把輸入法切到英文，
    再結束 ChtIME.exe（kill_cht_ime）。安裝後需登出或重啟輸入法。
  - 一律先把原檔備份到 backup_dir。
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROFILES = {
    "legacy": {
        "subdir": Path("InputMethod") / "CHT",
        "needs_ownership": True,   # 原檔屬 TrustedInstaller
        "files": {
            "lex": "ChtChangjie.lex",
            "spd": "ChtChangjie.spd",
            "ext": "ChtChangjieExt.lex",
        },
    },
    "2004": {
        "subdir": Path("System32") / "zh-hk",
        "needs_ownership": False,  # 提權即可
        "files": {
            "sdc": "ChtCangjie.sdc",
            "spd": "ChtCangjie.spd",
            "ext": "ChtCangjieExt.lex",
        },
    },
}


class PlatformError(RuntimeError):
    pass


def is_windows() -> bool:
    return sys.platform == "win32"


def require_windows() -> None:
    if not is_windows():
        raise PlatformError(
            "安裝功能僅限 Windows。其他平台請用 convert / pack 產生檔案，"
            "再手動複製到目標機器。"
        )


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def windir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows"))


#: 安裝前提示使用者的動作。GUI 應以彈窗顯示，等使用者確認後才 apply_install。
PRE_INSTALL_ADVICE = (
    "安裝前請先：\n"
    "  1. 把輸入法切換到英文（或其他非微軟倉頡的輸入法）\n"
    "  2. 結束 ChtIME.exe（本工具可代為結束）\n"
    "否則碼表檔案正被輸入法佔用，會無法覆寫。"
)

CHT_IME_PROCESS = "ChtIME.exe"


def kill_cht_ime() -> list[str]:
    """結束 ChtIME.exe。回傳訊息行。僅 Windows；失敗不拋例外。"""
    if not is_windows():
        return ["非 Windows，略過結束 ChtIME.exe"]
    import subprocess

    try:
        r = subprocess.run(
            ["taskkill", "/F", "/IM", CHT_IME_PROCESS],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:  # noqa: BLE001
        return [f"結束 {CHT_IME_PROCESS} 失敗：{e}"]
    if r.returncode == 0:
        return [f"已結束 {CHT_IME_PROCESS}（系統稍後會自動重啟它）"]
    return [f"{CHT_IME_PROCESS} 可能未在執行：{r.stderr.strip() or r.stdout.strip()}"]


def target_dir(profile: str) -> Path:
    return windir() / PROFILES[profile]["subdir"]


@dataclass
class InstallPlan:
    profile: str
    src_dir: Path
    dst_dir: Path
    #: [(src, dst)]
    copies: list[tuple[Path, Path]]
    missing_src: list[str]


def plan_install(profile: str, pack_dir: Path) -> InstallPlan:
    if profile not in PROFILES:
        raise ValueError(f"未知 profile: {profile!r}")
    spec = PROFILES[profile]["files"]
    dst_dir = target_dir(profile)
    copies: list[tuple[Path, Path]] = []
    missing: list[str] = []
    for name in spec.values():
        src = pack_dir / name
        if src.exists():
            copies.append((src, dst_dir / name))
        else:
            missing.append(name)
    return InstallPlan(
        profile=profile,
        src_dir=pack_dir,
        dst_dir=dst_dir,
        copies=copies,
        missing_src=missing,
    )


def backup_existing(plan: InstallPlan, backup_root: Path) -> Path | None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = backup_root / f"{plan.profile}-{stamp}"
    saved = False
    for _src, dst in plan.copies:
        if dst.exists():
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, bdir / dst.name)
            saved = True
    return bdir if saved else None


def apply_install(plan: InstallPlan, *, dry_run: bool = False) -> list[str]:
    """實際複製。回傳訊息行。呼叫前應已 require_windows() + 提權。"""
    require_windows()
    msgs: list[str] = []
    if plan.missing_src:
        msgs.append(f"缺少來源檔（跳過）：{', '.join(plan.missing_src)}")
    if not is_admin():
        msgs.append("⚠ 目前非系統管理員；覆寫 System32 會失敗。請以管理員重試。")
    plan.dst_dir.mkdir(parents=True, exist_ok=True)
    for src, dst in plan.copies:
        if dry_run:
            msgs.append(f"[dry-run] {src.name} → {dst}")
            continue
        # TODO: System32\zh-hk 原檔屬 TrustedInstaller，需先 takeown / icacls
        #       或呼叫 MoveFileEx 排程重開機取代。目前直接 copy，失敗則提示。
        try:
            shutil.copy2(src, dst)
            msgs.append(f"已安裝 {dst}")
        except PermissionError as e:
            msgs.append(f"✗ 無權覆寫 {dst}：{e}（需提權 + 取得檔案擁有權）")
    if not dry_run and any(m.startswith("已安裝") for m in msgs):
        msgs.append("完成。請登出再登入，或重啟輸入法讓新碼表生效。")
    return msgs
