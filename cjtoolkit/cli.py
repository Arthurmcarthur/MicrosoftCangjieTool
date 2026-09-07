"""cjtoolkit 命令列入口。

    cjtoolkit validate <file...> [--spd companion.spd]    # 檢查合不合法
    cjtoolkit convert  <table.txt> [--phrases ms.tsv] [--layout auto] -o outdir
    cjtoolkit pack     <outdir> [--profile both]          # 三檔文本 → 二進位套件
    cjtoolkit build    <table.txt> [...] -o outdir        # convert + pack 一步到位
    cjtoolkit transcode <spd> <lex/sdc> [ext] -o outdir   # 一整套二進位 → 另一世代
    cjtoolkit install  <pack_dir> [--profile 2004] [--dry-run]    # 僅 Windows
    cjtoolkit uninstall <backup_dir> [--profile 2004]     # 從備份還原
    cjtoolkit codec    ...                                # 直通 vendored codec

（fetch 遠端獲取暫時隱藏，模組 cjtoolkit.fetch 仍在，之後再接。）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, convert as _convert
from . import codec as _codec
from . import install as _install
from . import validate as _validate


def _cmd_validate(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.files]
    spd = Path(args.spd) if args.spd else None
    binaries = [p for p in paths if _validate.classify(p) in ("spd", "lex", "ext")]
    if len(binaries) > 1 or (args.as_set and len(paths) > 1):
        rep = _validate.validate_set(paths)
    else:
        rep = _validate.validate_path(paths[0], spd=spd, layout=args.layout,
                                      separator=args.sep, encoding=args.encoding)
    print(rep.render())
    return 0 if rep.ok else 1


def _resolve_phrases(args: argparse.Namespace) -> Path | None:
    if args.no_phrases:
        return None
    if args.phrases:
        return Path(args.phrases)
    p = _convert.bundled_phrases()          # 預設帶內附的微軟詞庫
    return p if p.exists() else None


def _cmd_convert(args: argparse.Namespace) -> int:
    res = _convert.convert(
        Path(args.table),
        layout=args.layout,
        separator=args.sep,
        encoding=args.encoding,
        phrases=_resolve_phrases(args),
        char_weight_base=args.weight_base,
        ext_a_to_lex=not args.ext_a_separate,
    )
    paths = _convert.write_result(res, Path(args.output), stem=args.stem)
    print(f"單字 {res.n_char}  詞組 {res.n_phrase}  擴充 {res.n_ext}  SPD 碼 {res.n_codes}")
    if res.dropped_phrases:
        print(f"  詞組因缺字略過：{res.dropped_phrases}")
    print(f"  flags：{res.flag_hist}")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    return 0


def _has_entries(path: Path) -> bool:
    """檔案除註解/空行外還有內容。"""
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            return True
    return False


def _cmd_pack(args: argparse.Namespace) -> int:
    d = Path(args.outdir)
    stem = args.stem
    profile = "both" if getattr(args, "profile", "both") == "auto" else args.profile
    lex, spd, ext = d / f"{stem}.tsv", d / f"{stem}.spd.txt", d / f"{stem}.ext.tsv"
    argv = ["encode", str(lex), "--spd", str(spd)]
    if ext.exists() and _has_entries(ext):
        argv += ["--ext", str(ext)]
    argv += ["--profile", profile, "-o", str(d / "pack")]
    return _codec.main(argv)


def _cmd_transcode(args: argparse.Namespace) -> int:
    files = [Path(f) for f in args.files]
    res = _convert.transcode_set(files, Path(args.output), target=args.to)
    print(f"詞條 {res.n_entries}  SPD 碼 {res.n_codes}  擴充 {res.n_ext}")
    for prof, n in res.dropped.items():
        if n:
            print(f"  {prof}：丟掉 {n} 條過長的詞")
    for p in res.written:
        print(f"  {p}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    rc = _cmd_convert(args)
    if rc:
        return rc
    return _cmd_pack(args)


def _emit(msgs: list[str], log: str | None) -> None:
    for m in msgs:
        print(m)
    if log:
        try:
            Path(log).write_text("\n".join(msgs) + "\n", encoding="utf-8")
        except OSError:
            pass


def _cmd_install(args: argparse.Namespace) -> int:
    try:
        _install.require_windows()
    except _install.PlatformError as e:
        print(e, file=sys.stderr)
        return 2

    # 版本判定（full_install 會依此跳過系統不支援的 profile；--force 強制）
    resolved = _install.resolve_profiles(args.profile)
    print(f"目前系統：{_install.windows_name()}")
    if args.profile == "auto":
        print(f"依系統版本安裝：{' + '.join(resolved)}")
        if len(resolved) > 1:
            print("  （同時更新新舊兩處，以防你開了「使用之前版本的 Microsoft 倉頡」）")
    if not args.force and not any(_install.profile_supported(p)[0] for p in resolved):
        for p in resolved:
            ok, why = _install.profile_supported(p)
            if not why:
                continue
            print(f"⚠ {why}", file=sys.stderr)
        print("沒有可安裝的 profile（用 --force 可強制）。", file=sys.stderr)
        return 1

    # 確認：在「開 UAC 視窗、搶走焦點」之前先問清楚。提權子行程帶 --yes 跳過再問。
    interactive = not args.yes and not args.dry_run and not getattr(args, "_child", False)
    if interactive:
        print(_install.PRE_INSTALL_ADVICE)
        prompt = ("已切換成「英文（美國）」鍵盤或其他非微軟的輸入法了嗎？"
                  "（勿只把倉頡切英文模式）輸入 y 繼續 [y/N] ")
        if input(prompt).strip().lower() != "y":
            print("已取消。請先切換輸入法再重試。")
            return 1

    # 提權：非管理員且未 --dry-run / --no-elevate 時，用 UAC 開一個管理員子行程
    # 重跑 install（經 `-m cjtoolkit`，不是重跑 __main__.py 的路徑——那會壞掉）
    if not args.dry_run and not args.no_elevate and not _install.is_admin():
        print("正在請求系統管理員權限…")
        child = _install.worker_argv() + [
            "install", str(args.pack_dir), "--profile", args.profile,
            "--no-elevate", "--yes", "--_child",
        ]
        if args.no_stop_ime:
            child.append("--no-stop-ime")
        if args.no_restart:
            child.append("--no-restart")
        if args.force:
            child.append("--force")
        if args.backup_dir:
            child += ["--backup-dir", str(args.backup_dir)]
        try:
            rc = _install.run_elevated(child, cwd=_install.source_cwd(),
                                       show=True, wait=True)
        except OSError as e:
            print(f"提權失敗或被取消：{e}", file=sys.stderr)
            return 1
        return rc

    try:
        msgs = _install.full_install(
            Path(args.pack_dir),
            _install.resolve_profiles(args.profile),
            backup_root=Path(args.backup_dir) if args.backup_dir else None,
            stop_ime=not args.no_stop_ime,
            restart_ctfmon=not args.no_restart,
            force=args.force,
            dry_run=args.dry_run,
        )
        rc = 0
    except Exception as e:  # noqa: BLE001
        import traceback
        msgs = ["安裝過程發生例外：", traceback.format_exc()]
        rc = 1
    _emit(msgs, args.log)
    if getattr(args, "_child", False):
        input("\n按 Enter 關閉此視窗…")
    return rc


def _cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        _install.require_windows()
    except _install.PlatformError as e:
        print(e, file=sys.stderr)
        return 2
    if not args.dry_run and not args.no_elevate and not _install.is_admin():
        if _install.relaunch_as_admin():
            return 0
        print("提權失敗或被取消。", file=sys.stderr)
        return 1
    for m in _install.restore(Path(args.backup_dir), args.profile):
        print(m)
    return 0


def _cmd_codec(args: argparse.Namespace) -> int:
    return _codec.main(args.rest)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cjtoolkit", description=__doc__)
    p.add_argument("--version", action="version", version=f"cjtoolkit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_format_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--layout", default="auto", choices=list(_convert.LAYOUTS),
                        help="欄序：auto / char-code(字在左) / code-char(碼在左)")
        sp.add_argument("--sep", default="auto", choices=list(_convert.SEPARATORS),
                        help="分隔：auto / tab / space")
        sp.add_argument("--encoding", default="utf-8",
                        help="文字編碼（預設 utf-8，自動容忍 BOM；可填 big5hkscs、gb18030…）")

    def add_convert_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("table", help="txt 碼表")
        sp.add_argument("--phrases",
                        help="自訂詞表 TSV（預設用內附的微軟詞庫 44572 條）")
        sp.add_argument("--no-phrases", action="store_true", help="不併入任何詞組")
        add_format_args(sp)
        sp.add_argument("--weight-base", type=int, default=_convert.CHAR_WEIGHT_BASE)
        sp.add_argument("--ext-a-separate", action="store_true",
                        help="Ext-A 放 Ext.lex 而非主 lex（預設放主 lex）")
        sp.add_argument("--stem", default="cangjie", help="輸出檔名前綴")
        sp.add_argument("-o", "--output", required=True, help="輸出資料夾")

    v = sub.add_parser("validate", help="檢查匯入的檔案合不合法")
    v.add_argument("files", nargs="+", help="txt 碼表，或 spd / lex / sdc / Ext.lex")
    v.add_argument("--spd", help="配套 .spd（驗 lex/sdc 時用來查 spell index）")
    add_format_args(v)
    v.add_argument("--as-set", action="store_true", help="把多個檔當一整套交叉檢查")
    v.set_defaults(func=_cmd_validate)

    c = sub.add_parser("convert", help="txt 碼表 → 三檔文本")
    add_convert_args(c)
    c.set_defaults(func=_cmd_convert)

    pk = sub.add_parser("pack", help="三檔文本 → 二進位套件")
    pk.add_argument("outdir", help="含 <stem>.tsv/.spd.txt/.ext.tsv 的資料夾")
    pk.add_argument("--stem", default="cangjie")
    pk.add_argument("--profile", default="both", choices=["2004", "legacy", "both"])
    pk.set_defaults(func=_cmd_pack)

    b = sub.add_parser("build", help="convert + pack")
    add_convert_args(b)
    b.add_argument("--profile", default="both", choices=["2004", "legacy", "both"])
    b.set_defaults(func=_cmd_build, outdir=None)

    tc = sub.add_parser("transcode",
                        help="已是一整套二進位 → 另一世代（lex/sdc 互轉）")
    tc.add_argument("files", nargs="+",
                    help="spd + lex/sdc + 可選 Ext.lex（順序不拘）")
    tc.add_argument("--to", default="both", choices=["2004", "legacy", "both"])
    tc.add_argument("-o", "--output", required=True, help="輸出資料夾")
    tc.set_defaults(func=_cmd_transcode)

    ins = sub.add_parser("install", help="部署到 Windows IME 目錄（僅 Windows）")
    ins.add_argument("pack_dir", help="含 ChtCangjie.* / ChtChangjie.* 的資料夾")
    ins.add_argument("--profile", default="auto",
                     choices=["auto", "2004", "legacy", "both"],
                     help="auto＝依系統版本判定（預設）；系統不支援的會被跳過")
    ins.add_argument("--force", action="store_true",
                     help="即使系統版本不支援也照裝（危險）")
    ins.add_argument("--backup-dir", default=None,
                     help="備份位置（預設存到目標目錄的 Backup_<時間戳>）")
    ins.add_argument("--no-stop-ime", action="store_true", help="不要結束 IME 行程")
    ins.add_argument("--no-restart", action="store_true", help="裝完不重啟 ctfmon")
    ins.add_argument("--no-elevate", action="store_true", help="不自動 UAC 提權")
    ins.add_argument("--log", help="把結果訊息也寫到這個檔（GUI 用來回收輸出）")
    ins.add_argument("-y", "--yes", action="store_true", help="略過安裝前確認")
    ins.add_argument("--dry-run", action="store_true", help="只列出動作，不改任何檔案")
    ins.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    ins.set_defaults(func=_cmd_install)

    un = sub.add_parser("uninstall", help="從備份還原（僅 Windows）")
    un.add_argument("backup_dir", help="某次備份的資料夾")
    un.add_argument("--profile", default="2004", choices=["2004", "legacy"])
    un.add_argument("--no-elevate", action="store_true")
    un.add_argument("--dry-run", action="store_true")
    un.set_defaults(func=_cmd_uninstall)

    cd = sub.add_parser("codec", help="直通 vendored codec（info/decode/encode/roundtrip）")
    cd.add_argument("rest", nargs=argparse.REMAINDER)
    cd.set_defaults(func=_cmd_codec)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # build 用 convert 的 -o 當 outdir
    if args.cmd == "build":
        args.outdir = args.output
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
