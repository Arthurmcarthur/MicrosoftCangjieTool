"""一份 txt 碼表 → 微軟倉頡三檔文本（lex / spd / ext），再交給 codec 編成二進位。

移植自 microsoft_cangjie/cangjie3/build_tables.py，去掉 cangjie3 專屬的寫死路徑，
改成可傳參數。轉換規則與硬約束見 CLAUDE.md。

輸入 txt 格式：一行一字，倉頡碼與漢字以 TAB 或半角空格分隔。
    layout="char-code"  漢字在左（cangjie3.txt）
    layout="code-char"  倉頡碼在左（本 repo 舊版 cj_sample.txt / 大部分碼表）
    layout="auto"       看第一個非註解行：整行只含 A-Za-z 的一側當碼

可選 phrases：微軟解碼出的詞表 TSV（text <TAB> codes <TAB> weight），
逐字改用本碼表的碼（一字多碼取檔內最前者），沿用原權重。
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from pathlib import Path

# ---- 硬約束常數（見 CLAUDE.md）---------------------------------------------

#: 單字 weight = CHAR_WEIGHT_BASE - 行號。必須 < 2^24（16,777,216），
#: 且高於詞組最大權重（官方詞組 max ~1.076e7）。超過 2^24 → 候選錯位/打不出。
CHAR_WEIGHT_BASE = 14_000_000

#: SPD 相異碼上限（TRIE leaf 是 16-bit）。Ext.lex 的碼是字面字串、不進 SPD。
SPD_MAX_CODES = 65_535

EXT_A_LO, EXT_A_HI = 0x3400, 0x4DBF


def is_bmp(cp: int) -> bool:
    return cp <= 0xFFFF


def is_ext_a(cp: int) -> bool:
    return EXT_A_LO <= cp <= EXT_A_HI


def is_hkscs(ch: str) -> bool:
    """big5-hkscs 可編、但 big5 不可編 → HKSCS 專有字。"""
    try:
        ch.encode("big5hkscs")
    except UnicodeEncodeError:
        return False
    try:
        ch.encode("big5")
        return False
    except UnicodeEncodeError:
        return True


# ---- 解析輸入碼表 ----------------------------------------------------------


@dataclass
class CodeTable:
    #: [(char, CODE_UPPER, line_index)]，去掉完全重複的 (char, code)，保留檔內順序
    rows: list[tuple[str, str, int]]
    #: {char: 第一個出現的碼（原大小寫）}
    first_code: dict[str, str]


#: 可選欄序 / 分隔 / 編碼（GUI 下拉、CLI 參數共用）
LAYOUTS = ("auto", "char-code", "code-char")
SEPARATORS = ("auto", "tab", "space")
#: 常見編碼；使用者也可直接填任何 Python codec 名
ENCODINGS = ("utf-8", "utf-8-sig", "utf-16", "gb18030", "big5hkscs", "big5")


def _looks_like_code(s: str) -> bool:
    return len(s) > 0 and all(c.isascii() and c.isalpha() for c in s)


def _split(ln: str, separator: str) -> list[str]:
    if separator == "tab":
        return ln.split("\t")
    if separator == "space":
        return ln.split()          # 任意空白（單／多個空格、tab）
    # auto：有 tab 用 tab，否則任意空白
    return ln.split("\t") if "\t" in ln else ln.split()


def _read_lines(path: Path, encoding: str) -> list[str]:
    enc = "utf-8-sig" if encoding == "utf-8" else encoding  # utf-8 一律容忍 BOM
    try:
        raw = path.read_text(encoding=enc)
    except (LookupError, UnicodeDecodeError) as e:
        raise ValueError(f"以 {encoding} 讀取失敗：{e}") from e
    out = []
    for line in raw.splitlines():
        s = line.rstrip("\r")
        if not s or s.lstrip().startswith("#"):
            continue
        out.append(s)
    return out


def parse_code_table(
    path: Path,
    layout: str = "auto",
    *,
    separator: str = "auto",
    encoding: str = "utf-8",
) -> CodeTable:
    """解析純文字碼表。

    layout     auto | char-code（字在左）| code-char（碼在左）
    separator  auto | tab | space（space＝任意空白）
    encoding   任何 Python codec 名；"utf-8" 會自動容忍 BOM
    """
    if layout not in LAYOUTS:
        raise ValueError(f"未知 layout: {layout!r}（{'/'.join(LAYOUTS)}）")
    if separator not in SEPARATORS:
        raise ValueError(f"未知 separator: {separator!r}（{'/'.join(SEPARATORS)}）")

    lines = _read_lines(path, encoding)
    if not lines:
        raise ValueError(f"{path.name}: 沒有可解析的資料行")

    if layout == "auto":
        layout = _detect_layout(lines, separator)

    rows: list[tuple[str, str, int]] = []
    first_code: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for i, ln in enumerate(lines):
        parts = [p for p in _split(ln, separator) if p != ""]
        if len(parts) < 2:
            raise ValueError(
                f"{path.name} 第 {i} 行無法用「{separator}」分割成兩欄: {ln!r}"
            )
        a, b = parts[0], parts[1]
        code, ch = (a, b) if layout == "code-char" else (b, a)
        if len(ch) != 1:
            raise ValueError(
                f"{path.name} 第 {i} 行漢字欄不是單字（欄序選對了嗎？）: {ln!r}"
            )
        first_code.setdefault(ch, code)
        key = (ch, code)
        if key in seen:
            continue
        seen.add(key)
        rows.append((ch, code.upper(), i))

    return CodeTable(rows=rows, first_code=first_code)


def _detect_layout(lines: list[str], separator: str = "auto") -> str:
    votes = collections.Counter()
    for ln in lines[:200]:
        parts = [p for p in _split(ln, separator) if p != ""]
        if len(parts) < 2:
            continue
        a_code, b_code = _looks_like_code(parts[0]), _looks_like_code(parts[1])
        if a_code and not b_code:
            votes["code-char"] += 1
        elif b_code and not a_code:
            votes["char-code"] += 1
    if not votes:
        raise ValueError("無法自動判斷欄位順序，請明確指定 layout（char-code / code-char）")
    return votes.most_common(1)[0][0]


# ---- 詞組 ----------------------------------------------------------------


def load_phrases(path: Path) -> list[tuple[str, int | None]]:
    """詞表的多字詞：[(text, weight)]，保留原順序。

    接受兩種欄位配置：
      text <TAB> weight               （本專案內附的 ms-phrases.tsv）
      text <TAB> codes <TAB> weight    （ime_codec decode 出的 lex TSV）
    """
    out: list[tuple[str, int | None]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        parts = ln.split("\t")
        text = parts[0]
        if len(text) < 2:
            continue
        w_field = ""
        if len(parts) == 2:
            w_field = parts[1]
        elif len(parts) >= 3:
            w_field = parts[2]
        weight = int(w_field) if w_field.strip().lstrip("-").isdigit() else None
        out.append((text, weight))
    return out


def bundled_phrases() -> Path:
    """本專案內附的微軟聯想詞詞表（44572 條，自官方 ChtChangjie.lex 解出，只含 text+weight）。"""
    return Path(__file__).with_name("data") / "ms-phrases.tsv"


# ---- 轉換 --------------------------------------------------------------


@dataclass
class ConvertResult:
    lex_text: str
    spd_text: str
    ext_text: str
    n_char: int
    n_phrase: int
    n_ext: int
    n_codes: int
    dropped_phrases: int
    flag_hist: dict[int, int] = field(default_factory=dict)


def convert(
    code_table: Path,
    *,
    layout: str = "auto",
    separator: str = "auto",
    encoding: str = "utf-8",
    phrases: Path | None = None,
    char_weight_base: int = CHAR_WEIGHT_BASE,
    ext_a_to_lex: bool = True,
) -> ConvertResult:
    ct = parse_code_table(code_table, layout, separator=separator, encoding=encoding)

    def goes_to_lex(ch: str) -> bool:
        cp = ord(ch)
        if not is_bmp(cp):
            return False  # 增補平面只能進 Ext.lex（SDC text 依 codepoint 計數）
        if is_ext_a(cp) and not ext_a_to_lex:
            return False
        return True

    # ---- LEX：單字 ----
    lex_lines: list[str] = []
    lex_codes: set[str] = set()
    n_char = 0
    for ch, code, idx in ct.rows:
        if not goes_to_lex(ch):
            continue
        weight = char_weight_base - idx
        if weight <= 0 or weight >= (1 << 24):
            raise ValueError(
                f"weight {weight} 超出 (0, 2^24)；碼表 {len(ct.rows)} 行，"
                f"調小 char_weight_base 或分批"
            )
        lex_lines.append(f"{ch}\t{code}\t{weight}")
        lex_codes.add(code)
        n_char += 1

    # ---- LEX：詞組 ----
    n_phrase = 0
    dropped = 0
    if phrases is not None:
        for text, weight in load_phrases(phrases):
            try:
                pcodes = [ct.first_code[c].upper() for c in text]
            except KeyError:
                dropped += 1
                continue
            w = weight if weight is not None else ""
            lex_lines.append(f"{text}\t{' '.join(pcodes)}\t{w}".rstrip("\t"))
            lex_codes.update(pcodes)
            n_phrase += 1

    # ---- SPD（僅主 lex 引用到的碼）----
    codes = sorted(lex_codes)
    if len(codes) > SPD_MAX_CODES:
        raise ValueError(f"SPD 相異碼 {len(codes)} > 上限 {SPD_MAX_CODES}")

    # ---- EXT ----
    ext_lines: list[str] = []
    flag_hist: collections.Counter[int] = collections.Counter()
    for ch, code, idx in ct.rows:
        if goes_to_lex(ch):
            continue
        fl = 6 if is_hkscs(ch) else 2
        flag_hist[fl] += 1
        ext_lines.append(f"{code.lower()}\t{ch}\t{fl}")

    spd_text = (
        "# type: spd\n"
        f"# {len(codes)} codes\n"
        f"# source: {code_table.name} (codes referenced by main lex)\n\n"
        + "\n".join(codes)
        + "\n"
    )
    lex_text = (
        "# type: lex\n"
        "# columns: text <TAB> codes [ <TAB> weight ]\n"
        f"# {len(lex_lines)} entries ({n_char} chars + {n_phrase} phrases)\n"
        f"# source: {code_table.name}"
        + (f" + {phrases.name} (phrases)" if phrases else "")
        + "\n\n"
        + "\n".join(lex_lines)
        + "\n"
    )
    ext_text = (
        "# type: ext\n"
        "# columns: code <TAB> char [ <TAB> flags ]\n"
        "# flags: 2=一般擴展 6=HKSCS（Ext.lex 只含增補平面字）\n"
        f"# {len(ext_lines)} entries\n"
        f"# source: {code_table.name}\n\n"
        + "\n".join(ext_lines)
        + "\n"
    )

    return ConvertResult(
        lex_text=lex_text,
        spd_text=spd_text,
        ext_text=ext_text,
        n_char=n_char,
        n_phrase=n_phrase,
        n_ext=len(ext_lines),
        n_codes=len(codes),
        dropped_phrases=dropped,
        flag_hist=dict(sorted(flag_hist.items())),
    )


def write_result(result: ConvertResult, outdir: Path, stem: str = "cangjie") -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {
        "lex": outdir / f"{stem}.tsv",
        "spd": outdir / f"{stem}.spd.txt",
        "ext": outdir / f"{stem}.ext.tsv",
    }
    paths["lex"].write_text(result.lex_text, encoding="utf-8")
    paths["spd"].write_text(result.spd_text, encoding="utf-8")
    paths["ext"].write_text(result.ext_text, encoding="utf-8")
    return paths


# ---- 跨世代轉換（已是二進位的一整套 → 另一世代）-----------------------


@dataclass
class TranscodeResult:
    written: list[Path]
    n_entries: int
    n_codes: int
    n_ext: int
    dropped: dict[str, int]          # {profile: 因詞長被丟的詞數}


def _pick_set(files: list[Path]) -> tuple[bytes, bytes, bytes | None]:
    """從一堆檔案裡挑出 spd / lex(或sdc) / ext，回傳三份 bytes（ext 可為 None）。"""
    from . import codec

    spd = lex = ext = None
    for p in files:
        raw = p.read_bytes()
        tag = codec.detect_magic(raw)
        if tag == "spd" and spd is None:
            spd = raw
        elif tag == "lex" and lex is None:   # detect_magic 對 sdc 也回 "lex"
            lex = raw
        elif tag == "ext" and ext is None:
            ext = raw
    if spd is None or lex is None:
        raise ValueError("需要一整套：至少 spd + lex/sdc（Ext.lex 可選）")
    return spd, lex, ext


def transcode_set(files: list[Path], out_dir: Path,
                  target: str = "both") -> TranscodeResult:
    """把一整套二進位（spd + lex/sdc + 可選 Ext.lex）重新編成目標世代。

    target: "2004" | "legacy" | "both"。輸出到 out_dir/（檔名依世代）。
    """
    from . import codec

    profiles = ["2004", "legacy"] if target == "both" else [target]
    spd_b, lex_b, ext_b = _pick_set(files)

    spd_codes = codec.decode_spd(spd_b)
    lex = codec.decode_lex(lex_b, spd_codes)
    ext_entries = codec.decode_ext(ext_b) if ext_b else None

    out_dir.mkdir(parents=True, exist_ok=True)
    spd_blob = codec.encode_spd(spd_codes)
    ext_blob = None
    if ext_entries:
        import struct
        ts = struct.unpack_from("<I", ext_b, 32)[0] if len(ext_b) >= 36 else None
        ext_blob = codec.encode_ext(ext_entries, timestamp=ts)

    written: list[Path] = []
    dropped: dict[str, int] = {}
    for prof in profiles:
        spec = codec.profile_spec(prof)
        blob, n_drop = codec.encode_lex(lex, spd_codes, max_len=spec.max_len,
                                        force_lcount=spec.force_lcount)
        dropped[prof] = n_drop
        for name, data in ((spec.dict_name, blob), (spec.spd_name, spd_blob)):
            (out_dir / name).write_bytes(data)
            written.append(out_dir / name)
        if ext_blob is not None:
            (out_dir / spec.ext_name).write_bytes(ext_blob)
            written.append(out_dir / spec.ext_name)

    return TranscodeResult(
        written=written,
        n_entries=len(lex.entries),
        n_codes=len(spd_codes),
        n_ext=len(ext_entries) if ext_entries else 0,
        dropped=dropped,
    )
