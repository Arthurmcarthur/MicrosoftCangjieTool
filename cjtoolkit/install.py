"""把產出的碼表套件部署到 Windows 微軟 IME 目錄。僅 Windows 可用。

兩套目標（可各自獨立安裝）：

  2004    %windir%\\System32\\zh-hk\\      ChtCangjie.sdc / ChtCangjie.spd / ChtCangjieExt.lex
  legacy  %windir%\\InputMethod\\CHT\\     ChtChangjie.lex / ChtChangjie.spd / ChtChangjieExt.lex

流程（見 docs/format-notes.md）：
  1. 非管理員 → UAC 提權重啟自己
  2. 結束 IME 行程（ChtIME / MicrosoftIME），避免檔案被鎖
  3. 備份原檔 → <目標目錄>\\Backup_<時間戳>\\
  4. 刪除原檔 → 複製新檔
     · 2004（System32\\zh-hk）：提權即可
     · legacy（InputMethod\\CHT）：原檔屬 TrustedInstaller，覆寫失敗時
       用 takeown /f + icacls /grant 取得所有權再試
  5. （可選）開啟 HKCU 的「Enable HKSCS」讓擴充區字可打
  6. 重啟 ctfmon，提示使用者重新選字或登出

參考 Eden5Wu/Windows-Cangjie-Updater（PowerShell）的做法，實作為 Python。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROFILES = {
    "2004": {
        "subdir": Path("System32") / "zh-hk",
        "needs_ownership": False,   # 提權即可
        "files": {
            "sdc": "ChtCangjie.sdc",
            "spd": "ChtCangjie.spd",
            "ext": "ChtCangjieExt.lex",
        },
    },
    "legacy": {
        "subdir": Path("InputMethod") / "CHT",
        "needs_ownership": True,    # 原檔屬 TrustedInstaller
        "files": {
            "lex": "ChtChangjie.lex",
            "spd": "ChtChangjie.spd",
            "ext": "ChtChangjieExt.lex",
        },
    },
}

#: 安裝前要結束的行程（不含 .exe）。ChtIME 是微軟倉頡 IME 本體
#: （C:\Windows\System32\InputMethod\CHT\ChtIME.exe）；ctfmon 裝完會重啟。
IME_PROCESSES = ("ChtIME", "MicrosoftIME", "ctfmon")

#: HKSCS（擴充區）開關：HKCU\Software\Microsoft\IME\15.0\CHT\Cangjie\Enable HKSCS = 1
HKSCS_KEY = r"Software\Microsoft\IME\15.0\CHT\Cangjie"
HKSCS_VALUE = "Enable HKSCS"

PRE_INSTALL_ADVICE = (
    "安裝前請先把輸入法切換到英文（或非微軟倉頡的輸入法）。\n"
    "本工具會自動結束 ChtIME / MicrosoftIME 行程再覆寫檔案，"
    "裝完重啟 ctfmon；你可能需要重新選一次輸入法或登出。"
)


class PlatformError(RuntimeError):
    pass


# ---- 平台 / 權限 -----------------------------------------------------


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


def relaunch_as_admin(extra_args: list[str] | None = None) -> bool:
    """非管理員時用 UAC 重新啟動「同一條命令」（給 CLI 直接用）。

    回傳 True 表示已送出提權請求（呼叫端應立即結束目前這個非提權行程）。
    回傳 False 表示已是管理員、或非 Windows、或使用者取消。

    GUI 不要用這個（會整個重開）；GUI 用 run_elevated() 只提權跑 install 子命令。
    """
    if not is_windows() or is_admin():
        return False
    import ctypes

    argv = extra_args if extra_args is not None else sys.argv
    params = subprocess.list2cmdline(argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    return int(rc) > 32  # <=32 代表失敗（含使用者按取消）


def run_elevated(argv: list[str], *, show: bool = True, wait: bool = True) -> int:
    """以管理員身分執行 argv（argv[0] 是可執行檔）。

    show=True 顯示子行程主控台視窗；wait=True 等它結束並回傳 exit code
    （否則回傳 0）。用 ShellExecuteExW，不重開呼叫者本身。
    """
    require_windows()
    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SW_HIDE, SW_SHOWNORMAL = 0, 1
    INFINITE = 0xFFFFFFFF

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = argv[0]
    info.lpParameters = subprocess.list2cmdline([str(a) for a in argv[1:]])
    info.nShow = SW_SHOWNORMAL if show else SW_HIDE

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        err = ctypes.get_last_error()
        raise OSError(f"ShellExecuteExW 失敗（{err}）；使用者可能按了取消")
    if not wait or not info.hProcess:
        return 0
    k32 = ctypes.windll.kernel32
    k32.WaitForSingleObject(info.hProcess, INFINITE)
    code = wintypes.DWORD()
    k32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    k32.CloseHandle(info.hProcess)
    return int(code.value)


def worker_argv() -> list[str]:
    """回傳可用來執行 cjtoolkit CLI 的前綴（凍結成 exe 時是 exe 本身）。

    GUI 常經由 pythonw.exe 啟動（無主控台）；提權跑安裝時改用 python.exe，
    這樣有視窗、錯誤看得到。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = Path(exe).with_name("python.exe")
        if cand.exists():
            exe = str(cand)
    return [exe, "-m", "cjtoolkit"]


# ---- 行程 ---------------------------------------------------------


def _taskkill(name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["taskkill", "/F", "/T", "/IM", f"{name}.exe"],
        capture_output=True, text=True, timeout=10,
    )


def is_running(name: str) -> bool:
    if not is_windows():
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}.exe", "/NH"],
                           capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001
        return False
    return f"{name}.exe".lower() in r.stdout.lower()


def stop_processes(names: tuple[str, ...] = IME_PROCESSES) -> list[str]:
    if not is_windows():
        return ["非 Windows，略過結束 IME 行程"]
    msgs: list[str] = []
    for n in names:
        if not is_running(n):
            msgs.append(f"{n} 未在執行")
            continue
        try:
            r = _taskkill(n)
        except Exception as e:  # noqa: BLE001
            msgs.append(f"結束 {n} 失敗：{e}")
            continue
        if r.returncode == 0 and not is_running(n):
            msgs.append(f"已結束 {n}")
        else:
            detail = (r.stderr or r.stdout).strip().splitlines()
            msgs.append(f"⚠ {n} 未能結束：{detail[-1] if detail else r.returncode}"
                        "（可能被系統立即重啟；請確認已切到英文輸入法）")
    return msgs


# 相容舊名
def kill_cht_ime() -> list[str]:
    return stop_processes(("ChtIME",))


def start_ctfmon() -> list[str]:
    if not is_windows():
        return []
    try:
        subprocess.Popen(["ctfmon.exe"], close_fds=True)
        return ["已重啟 ctfmon"]
    except Exception as e:  # noqa: BLE001
        return [f"重啟 ctfmon 失敗（可登出再登入）：{e}"]


# ---- HKSCS 開關 --------------------------------------------------


def get_hkscs() -> bool | None:
    if not is_windows():
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, HKSCS_KEY) as k:
            val, _ = winreg.QueryValueEx(k, HKSCS_VALUE)
            return bool(val)
    except FileNotFoundError:
        return False
    except OSError:
        return None


def set_hkscs(enable: bool = True) -> list[str]:
    if not is_windows():
        return ["非 Windows，略過 HKSCS 開關"]
    import winreg

    try:
        k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, HKSCS_KEY, 0,
                               winreg.KEY_SET_VALUE)
        with k:
            winreg.SetValueEx(k, HKSCS_VALUE, 0, winreg.REG_DWORD, 1 if enable else 0)
        return [f"HKSCS 擴充區開關已設為 {'開' if enable else '關'}"]
    except OSError as e:
        return [f"設定 HKSCS 開關失敗：{e}"]


# ---- 所有權（legacy 用）---------------------------------------------


def take_ownership(path: Path) -> list[str]:
    """takeown + icacls 取得單一檔案的寫入權。best-effort。"""
    if not is_windows():
        return []
    msgs: list[str] = []
    user = os.environ.get("USERNAME", "")
    for cmd in (
        ["takeown", "/f", str(path)],
        ["icacls", str(path), "/grant", f"{user}:F"],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                msgs.append(f"{cmd[0]} 失敗：{(r.stderr or r.stdout).strip()}")
        except Exception as e:  # noqa: BLE001
            msgs.append(f"{cmd[0]} 例外：{e}")
    return msgs


# ---- 規劃 / 備份 / 套用 -------------------------------------------


def windir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows"))


def target_dir(profile: str) -> Path:
    return windir() / PROFILES[profile]["subdir"]


@dataclass
class InstallPlan:
    profile: str
    src_dir: Path
    dst_dir: Path
    copies: list[tuple[Path, Path]]   # [(src, dst)]
    missing_src: list[str]


def plan_install(profile: str, pack_dir: Path) -> InstallPlan:
    if profile not in PROFILES:
        raise ValueError(f"未知 profile: {profile!r}")
    dst_dir = target_dir(profile)
    copies: list[tuple[Path, Path]] = []
    missing: list[str] = []
    for name in PROFILES[profile]["files"].values():
        src = pack_dir / name
        if src.exists():
            copies.append((src, dst_dir / name))
        else:
            missing.append(name)
    return InstallPlan(profile, pack_dir, dst_dir, copies, missing)


def backup_existing(plan: InstallPlan, backup_root: Path | None = None) -> Path | None:
    """備份現有原檔。backup_root=None → 存到 <目標目錄>\\Backup_<時間戳>\\。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = (backup_root / f"{plan.profile}-{stamp}" if backup_root
            else plan.dst_dir / f"Backup_{stamp}")
    saved = False
    for _src, dst in plan.copies:
        if dst.exists():
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, bdir / dst.name)
            saved = True
    return bdir if saved else None


def apply_install(plan: InstallPlan, *, dry_run: bool = False,
                  delete_first: bool = True, allow_takeown: bool = True) -> list[str]:
    """把 plan.copies 寫進目標目錄。呼叫前應已 require_windows() 且為管理員。"""
    require_windows()
    msgs: list[str] = []
    if plan.missing_src:
        msgs.append(f"缺少來源檔（跳過）：{', '.join(plan.missing_src)}")
    if not plan.copies:
        msgs.append("沒有可安裝的檔案。")
        return msgs
    if not is_admin():
        msgs.append("⚠ 非管理員，覆寫會失敗；請提權後重試。")

    plan.dst_dir.mkdir(parents=True, exist_ok=True)
    needs_own = PROFILES[plan.profile]["needs_ownership"]

    for src, dst in plan.copies:
        if dry_run:
            msgs.append(f"[dry-run] {src.name} → {dst}")
            continue
        try:
            _replace_file(src, dst, delete_first)
            msgs.append(f"已安裝 {dst.name}")
        except PermissionError as e:
            if needs_own and allow_takeown and dst.exists():
                msgs.append(f"{dst.name}：覆寫被拒，嘗試取得所有權…")
                msgs += take_ownership(dst)
                try:
                    _replace_file(src, dst, delete_first)
                    msgs.append(f"已安裝 {dst.name}（取得所有權後）")
                    continue
                except OSError as e2:
                    e = e2  # noqa: PLW2901
            msgs.append(f"✗ 無法覆寫 {dst}：{e}")
        except OSError as e:
            msgs.append(f"✗ 複製 {dst.name} 失敗：{e}")

    if not dry_run and any(m.startswith("已安裝") for m in msgs):
        msgs.append("完成。可能需要重新選一次輸入法或登出再登入。")
    return msgs


def _replace_file(src: Path, dst: Path, delete_first: bool) -> None:
    if delete_first and dst.exists():
        dst.unlink()
    shutil.copy2(src, dst)


def restore(backup_dir: Path, profile: str) -> list[str]:
    """把某次備份的檔案複製回目標目錄。"""
    require_windows()
    dst_dir = target_dir(profile)
    msgs: list[str] = []
    files = list(backup_dir.glob("*"))
    if not files:
        return [f"備份資料夾沒有檔案：{backup_dir}"]
    for f in files:
        if f.is_file():
            try:
                _replace_file(f, dst_dir / f.name, delete_first=True)
                msgs.append(f"已還原 {f.name}")
            except OSError as e:
                msgs.append(f"✗ 還原 {f.name} 失敗：{e}")
    return msgs


# ---- 一鍵流程 -----------------------------------------------------


def full_install(
    pack_dir: Path,
    profiles: list[str],
    *,
    backup_root: Path | None = None,
    enable_hkscs: bool = False,
    stop_ime: bool = True,
    restart_ctfmon: bool = True,
    dry_run: bool = False,
) -> list[str]:
    """CLI / GUI 共用的安裝編排。要求已提權。"""
    require_windows()
    msgs: list[str] = []
    if stop_ime and not dry_run:
        msgs += stop_processes()
    for prof in profiles:
        plan = plan_install(prof, pack_dir)
        if not dry_run:
            b = backup_existing(plan, backup_root)
            if b:
                msgs.append(f"已備份 {prof} 原檔 → {b}")
        msgs.append(f"— {prof} → {plan.dst_dir}")
        msgs += apply_install(plan, dry_run=dry_run)
    if enable_hkscs and not dry_run:
        msgs += set_hkscs(True)
    if restart_ctfmon and not dry_run:
        msgs += start_ctfmon()
    return msgs
