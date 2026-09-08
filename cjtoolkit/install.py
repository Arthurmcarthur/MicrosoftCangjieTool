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
  5. 重啟 ctfmon，提示使用者重新選字或登出

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
#: （C:\Windows\System32\InputMethod\CHT\ChtIME.exe），它才是鎖住碼表檔的那個。
#: 不動 ctfmon —— 殺了它語言列會壞，而且從提權行程很難乾淨地把它拉回來。
IME_PROCESSES = ("ChtIME", "MicrosoftIME")

PRE_INSTALL_ADVICE = (
    "請先把輸入法切換成「英文（美國）」鍵盤，或其他非微軟的輸入法。\n"
    "請勿簡單將微軟倉頡切換到英文模式，這種做法無法解除佔用。\n"
    "本工具會結束 ChtIME 行程後覆寫碼表檔；裝完可能要重新選一次輸入法或登出。"
)


class PlatformError(RuntimeError):
    pass


# ---- 平台 / 版本 / 權限 --------------------------------------------

WIN10_2004_BUILD = 19041   # Windows 10 version 2004（新版碼表格式起點）
WIN11_BUILD = 22000


def is_windows() -> bool:
    return sys.platform == "win32"


def is_frozen() -> bool:
    """打包成單一 exe（Nuitka onefile / PyInstaller）後為 True。"""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def windows_build() -> int | None:
    """目前 Windows 的 build 編號；非 Windows 回 None。"""
    if not is_windows():
        return None
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        return None


def windows_name() -> str:
    b = windows_build()
    if b is None:
        return "非 Windows"
    if b >= WIN11_BUILD:
        return f"Windows 11（build {b}）"
    if b >= WIN10_2004_BUILD:
        return f"Windows 10 2004 或更新（build {b}）"
    return f"Windows 10 2004 以前或更舊（build {b}）"


def recommended_profiles() -> list[str]:
    """依目前系統版本建議安裝哪些 profile。

    - Windows 10 2004 以前：只有 legacy 能用。
    - Windows 10 2004 及以後 / Windows 11：同時更新 2004 與 legacy 兩處——
      因為使用者可能在 IME 設定裡開了「使用之前版本的 Microsoft 倉頡」，
      那樣輸入法會改讀 legacy 路徑，只更新 2004 就沒效果。
    """
    b = windows_build()
    if b is not None and b < WIN10_2004_BUILD:
        return ["legacy"]
    return ["2004", "legacy"]


def recommended_profile() -> str:
    """單一建議值（給標籤等用）。"""
    return recommended_profiles()[0]


def profile_supported(profile: str) -> tuple[bool, str]:
    """(可否在目前系統安裝, 不可的原因)。非 Windows 一律視為可（可能在替別台打包）。"""
    if profile == "legacy":
        return True, ""            # 相容性一直保留，新系統也能裝舊版
    b = windows_build()
    if b is None or b >= WIN10_2004_BUILD:
        return True, ""
    return False, (
        f"目前是{windows_name()}，早於 Windows 10 2004（build {WIN10_2004_BUILD}），"
        "無法使用新版碼表格式。請改選「Windows 10 2004 以前」。"
    )


def resolve_profiles(name: str) -> list[str]:
    """auto → 依系統版本建議（2004+ 會同時更新新舊兩處）；both → 兩者；其餘 → 自身。"""
    if name == "auto":
        return recommended_profiles()
    if name == "both":
        return ["2004", "legacy"]
    return [name]


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


def source_cwd() -> str | None:
    """從原始碼跑（未 pip install、未凍結）時，回傳含 cjtoolkit/ 套件的資料夾，
    供提權子行程當工作目錄用（否則 `python -m cjtoolkit` 會找不到模組）。"""
    if is_frozen():
        return None
    root = Path(__file__).resolve().parent.parent
    return str(root) if (root / "cjtoolkit" / "__init__.py").exists() else None


def run_elevated(argv: list[str], *, cwd: str | None = None,
                 show: bool = True, wait: bool = True) -> int:
    """以管理員身分執行 argv（argv[0] 是可執行檔）。

    cwd    子行程工作目錄（None＝繼承）。
    show   True 顯示子行程主控台視窗。
    wait   True 等它結束並回傳 exit code（否則回傳 0）。
    用 ShellExecuteExW，不重開呼叫者本身。
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
    info.lpDirectory = cwd
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
    if is_frozen():
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
        if r.returncode == 0:
            # taskkill 成功。ChtIME / ctfmon 常被系統立即重啟，這是正常的——
            # 重點是「刪除原檔的那一刻」它沒鎖住檔案，copy 成功即可。
            msgs.append(f"已結束 {n}" + ("（系統已立即重啟，屬正常）" if is_running(n) else ""))
        elif r.returncode == 128:
            msgs.append(f"{n} 未在執行")
        else:
            detail = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
            msgs.append(f"⚠ 結束 {n} 失敗（代碼 {r.returncode}）："
                        f"{detail[-1] if detail else ''}")
    return msgs


# 相容舊名
def kill_cht_ime() -> list[str]:
    return stop_processes(("ChtIME",))


def start_ctfmon() -> list[str]:
    """確保 ctfmon 在跑。預設流程不會殺它，所以通常這裡什麼都不用做。"""
    if not is_windows():
        return []
    if is_running("ctfmon"):
        return []
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    ctfmon = str(Path(sysroot) / "System32" / "ctfmon.exe")
    try:
        subprocess.Popen([ctfmon], close_fds=True)
        return ["已啟動 ctfmon"]
    except OSError:
        return ["ctfmon 未在執行；請登出再登入，或按 Win+R 執行 ctfmon"]


# ---- 所有權（legacy 用）---------------------------------------------


def take_ownership(path: Path, *, recurse: bool = False) -> list[str]:
    """takeown + icacls 取得檔案或資料夾的寫入權。best-effort。"""
    if not is_windows():
        return []
    msgs: list[str] = []
    user = os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    who = f"{domain}\\{user}" if domain else user
    takeown = ["takeown", "/f", str(path)] + (["/r", "/d", "Y"] if recurse else [])
    icacls = ["icacls", str(path), "/grant", f"{who}:F"] + (["/t"] if recurse else [])
    for cmd in (takeown, icacls):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                msgs.append(f"{cmd[0]} 失敗：{(r.stderr or r.stdout).strip().splitlines()[-1:]}")
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
    if not is_admin() and not dry_run:
        msgs.append("⚠ 非管理員，覆寫會失敗；請提權後重試。")

    plan.dst_dir.mkdir(parents=True, exist_ok=True)
    needs_own = PROFILES[plan.profile]["needs_ownership"]
    dir_owned = False

    for src, dst in plan.copies:
        if dry_run:
            msgs.append(f"[dry-run] {src.name} → {dst}")
            continue
        try:
            _replace_file(src, dst, delete_first)
            msgs.append(f"已安裝 {dst.name}")
        except PermissionError as e:
            if needs_own and allow_takeown:
                if not dir_owned:
                    msgs.append(f"{plan.dst_dir.name}：覆寫被拒，取得目錄與檔案所有權…")
                    msgs += take_ownership(plan.dst_dir)
                    dir_owned = True
                if dst.exists():
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
    stop_ime: bool = True,
    restart_ctfmon: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """CLI / GUI 共用的安裝編排。要求已提權。

    force=False 時，系統版本不支援的 profile 會被跳過（只警告不安裝壞碼表）。
    """
    require_windows()
    msgs: list[str] = [f"目前系統：{windows_name()}"]

    todo: list[str] = []
    for prof in profiles:
        ok, why = profile_supported(prof)
        if ok or force:
            if not ok:
                msgs.append(f"⚠ 仍安裝 {prof}（--force）：{why}")
            todo.append(prof)
        else:
            msgs.append(f"✗ 略過 {prof}：{why}")
    if not todo:
        msgs.append("沒有可安裝的 profile。")
        return msgs

    if stop_ime and not dry_run:
        msgs += stop_processes()
    for prof in todo:
        plan = plan_install(prof, pack_dir)
        if not dry_run:
            b = backup_existing(plan, backup_root)
            if b:
                msgs.append(f"已備份 {prof} 原檔 → {b}")
        msgs.append(f"— {prof} → {plan.dst_dir}")
        msgs += apply_install(plan, dry_run=dry_run)
    if restart_ctfmon and not dry_run:
        msgs += start_ctfmon()
    return msgs
