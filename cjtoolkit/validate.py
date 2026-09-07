"""驗證匯入的檔案合不合法：純文字碼表，或微軟倉頡二進位（spd / lex / sdc / Ext.lex）。

合法（無 error）才允許後續轉換或安裝。檢查項對應 docs/format-notes.md 的硬約束：
lex 權重 < 2^24、SPD 相異碼 ≤ 65535、Ext.lex 依小寫 code 升冪、SPD TRIE 標準格式。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import codec

WEIGHT_CAP = 1 << 24          # lex 權重硬上限
SPD_MAX_CODES = 0xFFFF        # 65535
EXT_KNOWN_FLAGS = {2, 4, 5, 6}
LCOUNT_KNOWN = {5, 8}


@dataclass
class Issue:
    level: str   # "error" | "warning" | "info"
    msg: str


@dataclass
class Report:
    kind: str                       # spd | lex | sdc | ext | code-table | set | unknown
    path: str
    issues: list[Issue] = field(default_factory=list)
    info: dict = field(default_factory=dict)
    #: 子報告（set 用）
    parts: list["Report"] = field(default_factory=list)

    def add(self, level: str, msg: str) -> None:
        self.issues.append(Issue(level, msg))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors and all(p.ok for p in self.parts)

    def render(self) -> str:
        lines = [f"[{self.kind}] {self.path}"]
        for k, v in self.info.items():
            lines.append(f"  · {k}: {v}")
        for i in self.issues:
            mark = {"error": "✗", "warning": "⚠", "info": "ℹ"}[i.level]
            lines.append(f"  {mark} {i.msg}")
        for p in self.parts:
            lines.append("")
            lines.append("\n".join("  " + ln for ln in p.render().splitlines()))
        lines.append(f"  → {'合法' if self.ok else '不合法'}")
        return "\n".join(lines)


# ---- 分類 --------------------------------------------------------------


def classify(path: Path) -> str:
    """回傳 spd | lex | ext | spd-text | lex-text | ext-text | code-table。"""
    data = path.read_bytes()
    tag = codec.detect_magic(data)
    if tag == "text":
        return "code-table"
    return tag  # spd / lex / ext / spd-text / lex-text / ext-text


# ---- 二進位驗證 --------------------------------------------------------


def validate_spd(data: bytes, path: str = "<spd>") -> Report:
    r = Report("spd", path)
    try:
        codes = codec.decode_spd(data)
    except codec.CodecError as e:
        r.add("error", f"無法解析 SPD：{e}")
        return r
    r.info["相異碼"] = len(codes)
    if len(codes) > SPD_MAX_CODES:
        r.add("error", f"相異碼 {len(codes)} > 上限 {SPD_MAX_CODES}（TRIE leaf 是 16-bit）")
    if codes != sorted(codes):
        r.add("error", "碼未依升冪排序（DLL 以二分搜尋查碼）")
    if len(set(codes)) != len(codes):
        r.add("error", "有重複碼")
    for c in codes:
        if not c or not all("A" <= ch <= "Z" for ch in c):
            r.add("error", f"碼含非 A–Z 字元：{c!r}")
            break
        if len(c) > codec.MAX_CODE_UNITS:
            r.add("error", f"碼過長（>{codec.MAX_CODE_UNITS}）：{c!r}")
            break
    # TRIE 區塊與標準重建比對
    try:
        file_trie = data[16 + len(codes) * codec.RECORD_SIZE:]
        rebuilt = codec.build_spd_trie(sorted(set(codes)))
        if file_trie != rebuilt:
            r.add("warning",
                  "SPD TRIE 與標準格式不一致；非官方工具產生的 TRIE 可能讓輸入法卡死。"
                  "建議用本工具重新打包 SPD。")
        else:
            r.info["TRIE"] = "標準格式"
    except codec.CodecError as e:
        r.add("error", f"TRIE 重建失敗：{e}")
    return r


def validate_lex(data: bytes, spd_codes: list[str] | None = None,
                 path: str = "<lex>") -> Report:
    kind = "lex"
    r = Report(kind, path)
    try:
        lay = codec._lex_layout(data)
    except codec.CodecError as e:
        r.add("error", f"無法解析 lex/sdc：{e}")
        return r
    lcount = lay["lcount"]
    r.kind = "sdc" if lcount == 5 else "lex"
    r.info["世代"] = {5: "2004 / zh-hk（ChtCangjie.sdc）",
                     8: "舊版（ChtChangjie.lex）"}.get(lcount, f"L_count={lcount}")
    r.info["詞條"] = lay["nwords"]
    if lcount not in LCOUNT_KNOWN:
        r.add("warning", f"L_count={lcount} 非 5 或 8，可能無法載入")

    # 權重硬上限
    over = [w for w in lay["weights"] if w >= WEIGHT_CAP]
    if over:
        r.add("error",
              f"{len(over)} 條權重 >= 2^24（最大 {max(over)}）；"
              "DLL 會把高位元組另作他用 → 候選錯位/選字上屏錯字/打不出")
    r.info["權重範圍"] = f"{min(lay['weights'])}–{max(lay['weights'])}" if lay["weights"] else "—"

    # 需要配套 SPD 才能查 spell index
    if spd_codes is None:
        r.add("warning", "未提供配套 SPD，無法檢查 spell index 是否有效")
    else:
        try:
            lex = codec.decode_lex(data, spd_codes)
            bad = [e for e in lex.entries if len(e.text) != len(e.codes)]
            if bad:
                r.add("error", f"{len(bad)} 條文字長度與碼數不符")
            toolong = [e for e in lex.entries if len(e.text) > lcount]
            if toolong:
                r.add("error", f"{len(toolong)} 條詞長 > L_count({lcount})")
        except codec.CodecError as e:
            r.add("error", f"spell index 超出 SPD 範圍：{e}")
    return r


def validate_ext(data: bytes, path: str = "<ext>") -> Report:
    r = Report("ext", path)
    try:
        entries = codec.decode_ext(data)
    except codec.CodecError as e:
        r.add("error", f"無法解析 Ext.lex：{e}")
        return r
    r.info["擴充字"] = len(entries)
    lower = [e.code.lower() for e in entries]
    inversions = sum(1 for a, b in zip(lower, lower[1:]) if a > b)
    if inversions:
        r.add("error",
              f"記錄未依小寫 code 升冪（{inversions} 處逆序）；"
              "DLL 以二分搜尋查字，亂序會讓部分字打不出/只在糾錯候選出現")
    unknown = sorted({e.flags for e in entries} - EXT_KNOWN_FLAGS)
    if unknown:
        r.add("warning", f"未知 flags：{unknown}（已知 2/4/5/6）")
    for e in entries:
        if not e.code or not all("a" <= c <= "z" for c in e.code.lower()):
            r.add("error", f"碼含非 A–Z：{e.code!r}")
            break
        if len(e.char) != 1:
            r.add("error", f"一筆記錄不是單一字元：{e.char!r}")
            break
    return r


# ---- 文字碼表驗證 -----------------------------------------------------


def validate_code_table(path: Path, layout: str = "auto", *,
                        separator: str = "auto", encoding: str = "utf-8",
                        weight_base: int = 14_000_000) -> Report:
    r = Report("code-table", str(path))
    from . import convert as _convert

    try:
        ct = _convert.parse_code_table(path, layout, separator=separator,
                                       encoding=encoding)
    except (ValueError, OSError) as e:
        r.add("error", str(e))
        return r
    r.info["格式"] = f"欄序={layout} 分隔={separator} 編碼={encoding}"

    r.info["列（去重後）"] = len(ct.rows)
    r.info["相異字"] = len(ct.first_code)

    bad_chars = [(ch, c) for ch, c, _ in ct.rows
                 if not c or not all("A" <= x <= "Z" for x in c)]
    if bad_chars:
        sample = ", ".join(f"{c!r}({ch})" for ch, c in bad_chars[:5])
        r.add("error", f"{len(bad_chars)} 個碼含非 A–Z 字元：{sample} …")

    long_codes = [c for _, c, _ in ct.rows if len(c) > codec.MAX_CODE_UNITS]
    if long_codes:
        r.add("error", f"{len(long_codes)} 個碼長 > {codec.MAX_CODE_UNITS}：{long_codes[0]!r} …")

    dup = len(ct.rows) - len({(ch, c) for ch, c, _ in ct.rows})
    if dup:
        r.add("warning", f"{dup} 對 (字, 碼) 完全重複（會自動去重）")

    bmp_codes = {c for ch, c, _ in ct.rows if ord(ch) <= 0xFFFF}
    r.info["主 lex 相異碼(估)"] = len(bmp_codes)
    if len(bmp_codes) > SPD_MAX_CODES:
        r.add("error", f"主 lex 相異碼估 {len(bmp_codes)} > SPD 上限 {SPD_MAX_CODES}")

    n_bmp = sum(1 for ch, _, _ in ct.rows if ord(ch) <= 0xFFFF)
    if weight_base - n_bmp <= 0:
        r.add("error",
              f"單字 {n_bmp} 列，weight_base={weight_base} 會使權重歸零或轉負；調大 weight_base")
    elif weight_base >= WEIGHT_CAP:
        r.add("error", f"weight_base={weight_base} >= 2^24")
    elif weight_base - n_bmp < 10_800_000:
        r.add("warning", "最小單字權重接近官方詞組最大權重(~1.076e7)，可能與詞組交錯")
    return r


# ---- 整套驗證 --------------------------------------------------------

_SET_NAMES = {
    "ChtCangjie.sdc": ("2004", "lex"),
    "ChtCangjie.spd": ("2004", "spd"),
    "ChtCangjieExt.lex": ("2004", "ext"),
    "ChtChangjie.lex": ("legacy", "lex"),
    "ChtChangjie.spd": ("legacy", "spd"),
    "ChtChangjieExt.lex": ("legacy", "ext"),
}


def validate_set(paths: list[Path]) -> Report:
    """一組檔案（官方檔名，或任意 spd + lex/sdc + 可選 ext）。跨檔互相檢查。"""
    r = Report("set", ", ".join(p.name for p in paths))
    by_role: dict[str, Path] = {}
    gens: set[str] = set()
    for p in paths:
        if p.name in _SET_NAMES:
            gen, role = _SET_NAMES[p.name]
            gens.add(gen)
            by_role.setdefault(role, p)
        else:
            tag = classify(p)
            role = {"spd": "spd", "lex": "lex", "ext": "ext"}.get(tag)
            if role:
                by_role.setdefault(role, p)

    if len(gens) > 1:
        r.add("warning", f"混到不同世代的檔名：{sorted(gens)}")

    spd_codes: list[str] | None = None
    if "spd" in by_role:
        sr = validate_spd(by_role["spd"].read_bytes(), str(by_role["spd"]))
        r.parts.append(sr)
        if sr.ok or not sr.errors:
            try:
                spd_codes = codec.decode_spd(by_role["spd"].read_bytes())
            except codec.CodecError:
                spd_codes = None
    else:
        r.add("error", "缺少配套 .spd（lex/sdc 無法單獨安裝）")

    if "lex" in by_role:
        r.parts.append(validate_lex(by_role["lex"].read_bytes(), spd_codes,
                                    str(by_role["lex"])))
    else:
        r.add("error", "缺少 lex / sdc 辭典本體")

    if "ext" in by_role:
        r.parts.append(validate_ext(by_role["ext"].read_bytes(), str(by_role["ext"])))

    # 交叉檢查：lex 用到的碼是否都在 SPD
    if spd_codes is not None and "lex" in by_role:
        try:
            lex = codec.decode_lex(by_role["lex"].read_bytes(), spd_codes)
            spd_set = set(spd_codes)
            missing = {c for e in lex.entries for c in e.codes if c not in spd_set}
            if missing:
                r.add("error", f"{len(missing)} 個 lex 碼不在 SPD：{sorted(missing)[:5]} …")
        except codec.CodecError:
            pass
    return r


# ---- 入口 -----------------------------------------------------------


def validate_path(path: Path, *, spd: Path | None = None,
                  layout: str = "auto", separator: str = "auto",
                  encoding: str = "utf-8") -> Report:
    tag = classify(path)
    data = path.read_bytes() if not tag.endswith("text") and tag != "code-table" else None
    spd_codes = None
    if spd is not None:
        try:
            spd_codes = codec.decode_spd(spd.read_bytes())
        except codec.CodecError:
            spd_codes = _load_spd_text(spd)

    if tag == "spd":
        return validate_spd(data, str(path))
    if tag == "lex":
        return validate_lex(data, spd_codes, str(path))
    if tag == "ext":
        return validate_ext(data, str(path))
    if tag in ("code-table", "spd-text", "lex-text", "ext-text"):
        if tag == "code-table":
            return validate_code_table(path, layout, separator=separator,
                                       encoding=encoding)
        r = Report(tag, str(path))
        r.add("info", "文字中介檔；用 convert / pack 產生二進位後再驗證")
        return r
    r = Report("unknown", str(path))
    r.add("error", "無法辨識的檔案類型")
    return r


def _load_spd_text(path: Path) -> list[str] | None:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    codes = [ln.strip().upper() for ln in lines
             if ln.strip() and not ln.strip().startswith("#")]
    return sorted(set(codes)) or None
