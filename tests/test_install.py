"""install.py 在非 Windows 上能安全 import 且純函式行為正確。"""
from pathlib import Path

import pytest

from cjtoolkit import install


def test_profiles_shape():
    assert set(install.PROFILES) == {"2004", "legacy"}
    assert install.PROFILES["2004"]["needs_ownership"] is False
    assert install.PROFILES["legacy"]["needs_ownership"] is True


def test_non_windows_guards():
    if install.is_windows():
        pytest.skip("Windows")
    assert install.is_admin() is False
    assert install.relaunch_as_admin() is False
    assert "非 Windows" in install.stop_processes()[0]
    with pytest.raises(install.PlatformError):
        install.require_windows()
    with pytest.raises(install.PlatformError):
        install.run_elevated(["x"])


def test_version_helpers():
    # 非 Windows：build None、都視為支援、auto→新舊兩處
    assert install.resolve_profiles("both") == ["2004", "legacy"]
    assert install.resolve_profiles("auto") == ["2004", "legacy"]
    assert install.profile_supported("legacy") == (True, "")
    ok, _ = install.profile_supported("2004")
    assert ok  # 非 Windows 不擋


def test_auto_new_windows_updates_both(monkeypatch):
    monkeypatch.setattr(install, "windows_build", lambda: 22631)  # Win11
    assert install.recommended_profiles() == ["2004", "legacy"]
    assert install.resolve_profiles("auto") == ["2004", "legacy"]


def test_profile_supported_blocks_old_windows(monkeypatch):
    monkeypatch.setattr(install, "windows_build", lambda: 18363)  # Win10 1909
    ok, why = install.profile_supported("2004")
    assert not ok and "2004" in why
    assert install.profile_supported("legacy") == (True, "")
    assert install.recommended_profiles() == ["legacy"]
    assert install.resolve_profiles("auto") == ["legacy"]


def test_worker_argv():
    av = install.worker_argv()
    assert av[0]  # 可執行檔
    assert "cjtoolkit" in " ".join(av) or getattr(__import__("sys"), "frozen", False)


def test_ime_processes_includes_chtime():
    assert "ChtIME" in install.IME_PROCESSES


def test_plan_install_lists_present_and_missing(tmp_path):
    (tmp_path / "ChtCangjie.sdc").write_bytes(b"x")
    (tmp_path / "ChtCangjie.spd").write_bytes(b"x")
    plan = install.plan_install("2004", tmp_path)
    got = {s.name for s, _ in plan.copies}
    assert got == {"ChtCangjie.sdc", "ChtCangjie.spd"}
    assert plan.missing_src == ["ChtCangjieExt.lex"]
    assert plan.dst_dir.name == "zh-hk"


def test_backup_existing_writes_copies(tmp_path, monkeypatch):
    # 假造一個「目標目錄」，塞兩個舊檔
    dst = tmp_path / "target"
    dst.mkdir()
    for n in ("ChtCangjie.sdc", "ChtCangjie.spd"):
        (dst / n).write_bytes(b"old")
    plan = install.InstallPlan(
        profile="2004", src_dir=tmp_path, dst_dir=dst,
        copies=[(tmp_path / n, dst / n) for n in ("ChtCangjie.sdc", "ChtCangjie.spd")],
        missing_src=[],
    )
    bdir = install.backup_existing(plan, tmp_path / "bk")
    assert bdir is not None
    assert {p.name for p in bdir.iterdir()} == {"ChtCangjie.sdc", "ChtCangjie.spd"}
