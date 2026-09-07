"""cjtoolkit 命令列入口。

    cjtoolkit validate <file...> [--spd companion.spd]    # 檢查合不合法
    cjtoolkit convert  <table.txt> [--phrases ms.tsv] [--layout auto] -o outdir
    cjtoolkit pack     <outdir> [--profile both]          # 三檔文本 → 二進位套件
    cjtoolkit build    <table.txt> [...] -o outdir        # convert + pack 一步到位
    cjtoolkit install  <pack_dir> [--profile both] [--dry-run]   # 僅 Windows
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
        rep = _validate.validate_path(paths[0], spd=spd, layout=args.layout)
    print(rep.render())
    return 0 if rep.ok else 1


def _cmd_convert(args: argparse.Namespace) -> int:
    res = _convert.convert(
        Path(args.table),
        layout=args.layout,
        phrases=Path(args.phrases) if args.phrases else None,
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
    lex, spd, ext = d / f"{stem}.tsv", d / f"{stem}.spd.txt", d / f"{stem}.ext.tsv"
    argv = ["encode", str(lex), "--spd", str(spd)]
    if ext.exists() and _has_entries(ext):
        argv += ["--ext", str(ext)]
    argv += ["--profile", args.profile, "-o", str(d / "pack")]
    return _codec.main(argv)


def _cmd_build(args: argparse.Namespace) -> int:
    rc = _cmd_convert(args)
    if rc:
        return rc
    return _cmd_pack(args)


def _cmd_install(args: argparse.Namespace) -> int:
    try:
        _install.require_windows()
    except _install.PlatformError as e:
        print(e, file=sys.stderr)
        return 2
    print(_install.PRE_INSTALL_ADVICE)
    if args.kill_ime and not args.dry_run:
        for m in _install.kill_cht_ime():
            print(m)
    elif not args.yes and not args.dry_run:
        if input("已切換到英文輸入法並準備好了嗎？[y/N] ").strip().lower() != "y":
            print("已取消。")
            return 1

    profiles = ["legacy", "2004"] if args.profile == "both" else [args.profile]
    for prof in profiles:
        plan = _install.plan_install(prof, Path(args.pack_dir))
        if args.backup_dir:
            b = _install.backup_existing(plan, Path(args.backup_dir))
            if b:
                print(f"已備份原檔 → {b}")
        for m in _install.apply_install(plan, dry_run=args.dry_run):
            print(m)
    return 0


def _cmd_codec(args: argparse.Namespace) -> int:
    return _codec.main(args.rest)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cjtoolkit", description=__doc__)
    p.add_argument("--version", action="version", version=f"cjtoolkit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_convert_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("table", help="txt 碼表")
        sp.add_argument("--phrases", help="微軟詞表 TSV（可選，沿用詞組並改碼）")
        sp.add_argument("--layout", default="auto",
                        choices=["auto", "char-code", "code-char"])
        sp.add_argument("--weight-base", type=int, default=_convert.CHAR_WEIGHT_BASE)
        sp.add_argument("--ext-a-separate", action="store_true",
                        help="Ext-A 放 Ext.lex 而非主 lex（預設放主 lex）")
        sp.add_argument("--stem", default="cangjie", help="輸出檔名前綴")
        sp.add_argument("-o", "--output", required=True, help="輸出資料夾")

    v = sub.add_parser("validate", help="檢查匯入的檔案合不合法")
    v.add_argument("files", nargs="+", help="txt 碼表，或 spd / lex / sdc / Ext.lex")
    v.add_argument("--spd", help="配套 .spd（驗 lex/sdc 時用來查 spell index）")
    v.add_argument("--layout", default="auto",
                   choices=["auto", "char-code", "code-char"])
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

    ins = sub.add_parser("install", help="部署到 Windows IME 目錄（僅 Windows）")
    ins.add_argument("pack_dir", help="含 ChtCangjie.* / ChtChangjie.* 的資料夾")
    ins.add_argument("--profile", default="both", choices=["2004", "legacy", "both"])
    ins.add_argument("--backup-dir", default="cj-backup")
    ins.add_argument("--kill-ime", action="store_true", help="安裝前結束 ChtIME.exe")
    ins.add_argument("-y", "--yes", action="store_true", help="略過安裝前確認")
    ins.add_argument("--dry-run", action="store_true")
    ins.set_defaults(func=_cmd_install)

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
