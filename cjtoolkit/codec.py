#!/usr/bin/env python3
"""Microsoft CHT IME 辭典完整轉換：.spd / .lex (SDC) / Ext.lex (mschxudp).

三種格式
========

SPD  （ChtChangjie.spd / ChtQuick.spd）
    合法倉頡碼列表 + 前綴 TRIE。
    文本：一行一碼。

LEX  （ChtChangjie.lex / ChtQuick.lex，magic ``SDC ``）
    詞條 + 每字對應的 SPD 碼索引（1-based）。
    文本：``詞<TAB>碼 [碼...]``，多字詞每個字一個倉頡碼。
    解碼需要對應的 .spd（否則只輸出索引號）。

EXT  （ChtChangjieExt.lex / ChtQuickExt.lex，magic ``mschxudp``）
    CJK 擴充字。紀錄：小寫碼 + 一個漢字（BMP 或 surrogate）。
    文本：``碼<TAB>字``，可選第三欄 flags：
      2  一般擴展（本樣本幾乎全是 Ext-B；省略時 encode 也寫 2）
      4  基本區／部首等硬塞進擴展表，當兼容碼用，不是真擴展字
      5  擴展 A（U+3400–4DBF）
      6  HKSCS

用法
====

    python3 ime_codec.py info CHT/ChtChangjie.lex
    python3 ime_codec.py decode CHT/ChtChangjie.spd -o codes.txt
    python3 ime_codec.py decode CHT/ChtChangjie.lex --spd CHT/ChtChangjie.spd -o table.tsv
    python3 ime_codec.py decode CHT/ChtChangjieExt.lex -o ext.tsv
    python3 ime_codec.py encode codes.txt -o out.spd
    python3 ime_codec.py encode table.tsv --spd CHT/ChtChangjie.spd --profile 2004 -o outdir
        # → ChtCangjie.sdc + ChtCangjie.spd
    python3 ime_codec.py encode table.tsv --spd CHT/ChtChangjie.spd --profile legacy -o outdir
        # → ChtChangjie.lex + ChtChangjie.spd
    python3 ime_codec.py encode table.tsv --spd CHT/ChtChangjie.spd --ext CHT/ChtChangjieExt.lex --profile both -o outdir
        # → 新舊兩套，各含 辭典 + SPD [+ Ext.lex]
    python3 ime_codec.py encode ext.tsv -o out.ext.lex
    python3 ime_codec.py roundtrip CHT/ChtChangjie.lex --spd CHT/ChtChangjie.spd
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MAGIC_SPD = b"SPD "
MAGIC_SDC = b"SDC "
MAGIC_TRIE = b"TRIE"
MAGIC_EXT = b"mschxudp"
RECORD_SIZE = 32
MAX_CODE_UNITS = 15
ALPHABET = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
FLAG_PRESENT = 0x8000
DEFAULT_LEX_WEIGHT = 0x7D7A3C  # 原檔裡大量罕用字共用的權重

# SDC 世代：L_count 決定 L[] 槽數，從而決定 perm 起始（差 12 bytes 就不能混用）。
# 2004 / Win11 zh-hk 倉頡、速成：L_count=5，正文從 0x44 起，預設檔名 ChtCangjie.sdc
# 舊版 InputMethod ChtChangjie.lex：L_count=8，正文從 0x50 起
PROFILE_2004 = "2004"
PROFILE_LEGACY = "legacy"
PROFILE_BOTH = "both"
MAX_LEN_2004 = 5
MAX_LEN_LEGACY = 8
DEFAULT_NAME_2004 = "ChtCangjie.sdc"
DEFAULT_SPD_2004 = "ChtCangjie.spd"
DEFAULT_EXT_2004 = "ChtCangjieExt.lex"
DEFAULT_NAME_LEGACY = "ChtChangjie.lex"
DEFAULT_SPD_LEGACY = "ChtChangjie.spd"
DEFAULT_EXT_LEGACY = "ChtChangjieExt.lex"


class CodecError(ValueError):
    pass


# ---------------------------------------------------------------------------
# SPD
# ---------------------------------------------------------------------------


def _decode_spd_record(rec: bytes) -> str:
    chars: list[str] = []
    for i in range(0, RECORD_SIZE, 2):
        cp = rec[i] | (rec[i + 1] << 8)
        if cp == 0:
            break
        chars.append(chr(cp))
    return "".join(chars)


def _encode_spd_record(code: str) -> bytes:
    if not code or len(code) > MAX_CODE_UNITS:
        raise CodecError(f"invalid SPD code: {code!r}")
    raw = code.encode("utf-16le")
    if len(raw) > RECORD_SIZE:
        raise CodecError(f"code too long: {code!r}")
    return raw.ljust(RECORD_SIZE, b"\x00")


def _pack_node(n_children: int, letter: str, a: int, b: int, flags: int) -> bytes:
    return struct.pack("<6H", n_children, ord(letter) if letter else 0, 0, a, b, flags)


SPD_TRIE_DENSE_MIN = 14  # 官方：某節點實際子字母數 >= 14 就配 26 個定槽（直接索引）

# ChtChangjieDS.DLL SPD 前綴 TRIE（解析器 0x18000D42C，逐鍵查找 0x18000A038）
#
# "TRIE"(4) + size(4) + 20-byte 子檔頭 + N 個 12-byte 節點（0-based，node 0 = 根）
#   子檔頭：<H 'A'(65)> <H 26> <I 13> <I 0xFFFFFFFF> <I 0xFFFFFFFF> <I 0>
#   size 欄 = 8 + 20 + N*12（載入時要求 trie 起點 + size == 檔尾）
#   節點（小端）：
#     +0  u32  (leaf << 16)   leaf = 碼在 SPD 碼表的 index+1（非完整碼則 0）
#     +4  u32  (term << 31) | child_base   term=1 表示此前綴本身是完整碼
#                                          child_base = 第一個子節點的 index
#     +8  u16  n_children     == 26 → DLL 直接索引 child_base+(字母-'A')
#                             <  26 → 子節點依字母排序、二分搜尋
#     +10 u16  letter         根為 0
#   子節點區塊連續配置；定槽(26)模式下缺字母的槽是全 0 節點。
#   節點配置順序為前序 DFS（與官方逐位元一致）。


def build_spd_trie(codes: list[str]) -> bytes:
    """依 SPD 碼表重建前綴 TRIE。官方 ChtChangjie.spd / ChtCangjie.spd 可逐位元還原。"""
    code_index = {c: i for i, c in enumerate(codes)}
    if len(codes) > 0xFFFF:
        raise CodecError(
            f"SPD has {len(codes)} codes; the trie leaf index is 16-bit (max 65535)"
        )
    prefixes: set[str] = {""}
    for c in codes:
        for k in range(1, len(c) + 1):
            prefixes.add(c[:k])

    def kid_letters(prefix: str) -> list[str]:
        return [ch for ch in ALPHABET if prefix + ch in prefixes]

    # 每個節點：[leaf, term, child_base, n_children, letter]
    nodes: list[list[int]] = [[0, 0, 0, 0, 0]]  # node 0 = 根

    def build(prefix: str, my_index: int) -> None:
        letters = kid_letters(prefix)
        real = len(letters)
        if real == 0:
            return
        dense = real >= SPD_TRIE_DENSE_MIN
        slots = ALPHABET if dense else letters
        base = len(nodes)
        nodes.extend([0, 0, 0, 0, 0] for _ in slots)
        nodes[my_index][2] = base
        nodes[my_index][3] = 26 if dense else real
        present = set(letters)
        for offset, ch in enumerate(slots):
            if ch not in present:
                continue  # 定槽模式的空槽保持全 0
            child = base + offset
            cp = prefix + ch
            is_code = cp in code_index
            nodes[child][0] = (code_index[cp] + 1) if is_code else 0
            nodes[child][1] = 1 if is_code else 0
            nodes[child][4] = ord(ch)
            build(cp, child)

    build("", 0)
    if len(nodes) > 0x7FFFFFFF:
        raise CodecError("SPD trie exceeds addressable node count")

    body = bytearray()
    for leaf, term, child_base, n_children, letter in nodes:
        body += struct.pack(
            "<IIHH",
            (leaf & 0xFFFF) << 16,
            ((1 << 31) if term else 0) | (child_base & 0x7FFFFFFF),
            n_children,
            letter,
        )
    subheader = struct.pack("<HHIIII", ord("A"), 26, 13, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    payload = subheader + bytes(body)
    return MAGIC_TRIE + struct.pack("<I", 8 + len(payload)) + payload


def decode_spd(data: bytes) -> list[str]:
    if len(data) < 16 or data[:4] != MAGIC_SPD:
        raise CodecError("not an SPD file")
    size, _ver, count = struct.unpack_from("<III", data, 4)
    if size != len(data):
        raise CodecError(f"SPD size field {size} != {len(data)}")
    end = 16 + count * RECORD_SIZE
    if end > len(data):
        raise CodecError("truncated SPD code table")
    return [_decode_spd_record(data[16 + i * RECORD_SIZE : 16 + (i + 1) * RECORD_SIZE]) for i in range(count)]


def encode_spd(codes: list[str]) -> bytes:
    cleaned = _normalize_codes(codes)
    table = b"".join(_encode_spd_record(c) for c in cleaned)
    trie = build_spd_trie(cleaned)
    rest = struct.pack("<II", 1, len(cleaned)) + table + trie
    return MAGIC_SPD + struct.pack("<I", 8 + len(rest)) + rest


def _normalize_codes(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        code = raw.strip()
        if not code or code.startswith("#"):
            continue
        code = code.split()[0].upper()
        if not all("A" <= ch <= "Z" for ch in code):
            raise CodecError(f"code must be A-Z: {code!r}")
        if code not in seen:
            seen.add(code)
            out.append(code)
    out.sort()
    if not out:
        raise CodecError("no codes")
    return out


# ---------------------------------------------------------------------------
# LEX (SDC)
# ---------------------------------------------------------------------------


@dataclass
class LexEntry:
    text: str
    codes: list[str]  # one Changjie code per character
    weight: int = DEFAULT_LEX_WEIGHT


@dataclass
class LexFile:
    entries: list[LexEntry]
    item: int = 1
    stamp: int = 0
    extra_trie: bytes = b""


def _align4_utf16(nchars: int) -> int:
    return ((-(nchars << 1)) & 3) + (nchars << 1)


def _lex_layout(data: bytes) -> dict:
    if data[:4] != MAGIC_SDC:
        raise CodecError("not an SDC/lex file")
    size = struct.unpack_from("<I", data, 4)[0]
    if size != len(data):
        raise CodecError(f"SDC size field {size} != {len(data)}")
    item, _maxl, first_id, f13c, f140, lcount, _fe0 = struct.unpack_from("<IIIIIII", data, 8)
    stamp = struct.unpack_from("<Q", data, 36)[0]
    L = [struct.unpack_from("<I", data, 44 + i * 4)[0] for i in range(lcount + 1)]
    nwords = L[lcount]
    f8 = [0]
    for i in range(lcount):
        f8.append(f8[-1] + (L[i + 1] - L[i]) * (i + 1))
    total = f8[lcount]
    aligned = _align4_utf16(total)
    off = 44 + (lcount + 1) * 4
    perm = list(struct.unpack_from(f"<{nwords}I", data, off))
    off += nwords * 4
    if f13c:
        off += nwords * 8
    if f140:
        off += nwords * 4
    text = data[off : off + total * 2]
    off += aligned
    spell = list(struct.unpack_from(f"<{total}H", data, off))
    off += aligned
    if first_id:
        off += ((-total) & 3) + total
    weights = list(struct.unpack_from(f"<{nwords}I", data, off))
    off += nwords * 4
    trie = data[off:]
    return {
        "item": item,
        "stamp": stamp,
        "L": L,
        "f8": f8,
        "nwords": nwords,
        "total": total,
        "perm": perm,
        "text": text,
        "spell": spell,
        "weights": weights,
        "trie": trie,
        "lcount": lcount,
    }


def decode_lex(data: bytes, spd_codes: list[str] | None = None) -> LexFile:
    lay = _lex_layout(data)
    L, f8 = lay["L"], lay["f8"]
    entries: list[LexEntry] = []
    nspd = len(spd_codes) if spd_codes else None
    for length in range(1, len(L)):
        count = L[length] - L[length - 1]
        base = f8[length - 1]
        for local in range(count):
            start = base + local * length
            text = lay["text"][start * 2 : (start + length) * 2].decode("utf-16le")
            ids = lay["spell"][start : start + length]
            codes: list[str] = []
            for idx in ids:
                if spd_codes is None:
                    codes.append(f"#{idx}")
                elif 1 <= idx <= nspd:
                    codes.append(spd_codes[idx - 1])
                else:
                    raise CodecError(f"spell index {idx} out of range 1..{nspd}")
            wid = L[length - 1] + local
            entries.append(LexEntry(text=text, codes=codes, weight=lay["weights"][wid]))
    return LexFile(entries=entries, item=lay["item"], stamp=lay["stamp"], extra_trie=lay["trie"])


def _code_index_map(spd_codes: list[str]) -> dict[str, int]:
    return {c: i + 1 for i, c in enumerate(spd_codes)}


def encode_lex(
    lex: LexFile,
    spd_codes: list[str],
    *,
    max_len: int = MAX_LEN_LEGACY,
    force_lcount: int | None = None,
) -> tuple[bytes, int]:
    """Pack an SDC/lex/sdc blob.

    max_len: drop entries longer than this (5 = Win10 2004+/Win11 zh-hk;
             8 = 舊版 ChtChangjie.lex).
    force_lcount: write exactly this many L[] slots so perm 起始位址固定
                  （5 → 正文 0x44；8 → 正文 0x50）。None 則用實際最大詞長。
    Returns (blob, n_dropped).
    """
    if not lex.entries:
        raise CodecError("empty lex")
    if max_len < 1:
        raise CodecError("max_len must be >= 1")
    idx = _code_index_map(spd_codes)
    rows: list[tuple[str, list[int], int]] = []
    dropped = 0
    for e in lex.entries:
        if len(e.text) > max_len:
            dropped += 1
            continue
        if len(e.text) != len(e.codes):
            raise CodecError(f"text/code length mismatch: {e.text!r} {e.codes}")
        ids = []
        for c in e.codes:
            cu = c.upper()
            if cu not in idx:
                raise CodecError(f"code {c!r} not in SPD table")
            ids.append(idx[cu])
        rows.append((e.text, ids, e.weight))
    if not rows:
        raise CodecError(f"no entries left after applying max_len={max_len}")

    rows.sort(key=lambda r: (len(r[0]), r[0]))
    actual_max = max(len(r[0]) for r in rows)
    lcount = force_lcount if force_lcount is not None else actual_max
    if lcount < actual_max:
        raise CodecError(f"force_lcount={lcount} < actual max word length {actual_max}")
    buckets: list[list[tuple[str, list[int], int]]] = [[] for _ in range(lcount + 1)]
    for r in rows:
        buckets[len(r[0])].append(r)

    L = [0]
    texts: list[str] = []
    spell_ids: list[int] = []
    weights: list[int] = []
    first_ids: list[int] = []
    one_char = [0] * len(spd_codes)
    for length in range(1, lcount + 1):
        for text, ids, w in buckets[length]:
            texts.append(text)
            spell_ids.extend(ids)
            weights.append(w)
            first_ids.append(ids[0])
            if length == 1:
                one_char[ids[0] - 1] += 1
        L.append(len(texts))
    nwords = L[-1]
    total = sum(len(t) for t in texts)
    packed_text = "".join(texts).encode("utf-16le")
    aligned = _align4_utf16(total)
    packed_text += b"\x00" * (aligned - len(packed_text))
    packed_spell = struct.pack(f"<{total}H", *spell_ids)
    packed_spell += b"\x00" * (aligned - len(packed_spell))

    def spell_key(wid: int) -> tuple:
        length = next(k for k in range(1, len(L)) if L[k - 1] <= wid < L[k])
        local = wid - L[length - 1]
        start = sum((L[i] - L[i - 1]) * i for i in range(1, length)) + local * length
        return (tuple(spell_ids[start : start + length]), texts[wid])

    perm = sorted(range(nwords), key=spell_key)
    trie = build_lex_trie(len(spd_codes), perm, first_ids, one_char)

    header = bytearray(MAGIC_SDC + struct.pack("<I", 0))
    header += struct.pack("<IIIIIII", lex.item, 1, 0, 0, 0, lcount, 0)
    stamp = lex.stamp or ((int(time.time()) & 0xFFFFFFFF) | (0x178 << 32))
    header += struct.pack("<Q", stamp)
    header += struct.pack(f"<{lcount + 1}I", *L)

    body = (
        header
        + struct.pack(f"<{nwords}I", *perm)
        + packed_text
        + packed_spell
        + struct.pack(f"<{nwords}I", *weights)
        + trie
    )
    return MAGIC_SDC + struct.pack("<I", len(body)) + body[8:], dropped


@dataclass(frozen=True)
class ProfileSpec:
    max_len: int
    force_lcount: int
    dict_name: str
    spd_name: str
    ext_name: str


def profile_spec(profile: str) -> ProfileSpec:
    if profile == PROFILE_2004:
        return ProfileSpec(MAX_LEN_2004, MAX_LEN_2004, DEFAULT_NAME_2004, DEFAULT_SPD_2004, DEFAULT_EXT_2004)
    if profile == PROFILE_LEGACY:
        return ProfileSpec(MAX_LEN_LEGACY, MAX_LEN_LEGACY, DEFAULT_NAME_LEGACY, DEFAULT_SPD_LEGACY, DEFAULT_EXT_LEGACY)
    raise CodecError(f"unknown profile {profile!r}")


def profile_encode_params(profile: str) -> tuple[int, int, str]:
    spec = profile_spec(profile)
    return spec.max_len, spec.force_lcount, spec.dict_name


def build_lex_trie(
    n_spd: int,
    perm: list[int],
    first_ids: list[int],
    one_char: list[int],
) -> bytes:
    """Inverted index keyed by first-character SPD index.

    One 12-byte slot per SPD code:
      uint16 perm_start & 0xFFFF
      uint16 (n_1char << 4) | (perm_start >> 16)
      uint16 0
      uint16 0x8000
      uint16 0
      uint16 spd_index (1-based)

    DLL uses this to map a typed code → perm[] range. A 48-byte stub
    makes lookup fail even if text/spell/weight are complete.
    """
    if n_spd < 1:
        raise CodecError("empty SPD")
    if len(one_char) != n_spd:
        raise CodecError("one_char length must equal n_spd")
    nwords = len(perm)
    firsts = [first_ids[wid] for wid in perm]
    starts: list[int] = []
    pos = 0
    for k in range(1, n_spd + 1):
        while pos < nwords and firsts[pos] < k:
            pos += 1
        starts.append(pos)

    payload = bytearray()
    payload += struct.pack("<HH", 1, n_spd)
    payload += struct.pack("<I", n_spd // 2)
    payload += struct.pack("<IIII", 0xFFFFFFFF, 0xFFFFFFFF, 0, 0)
    payload += struct.pack("<II", 1, n_spd)
    for k in range(n_spd):
        start = starts[k]
        a = start & 0xFFFF
        b = (one_char[k] << 4) | ((start >> 16) & 0xF)
        payload += struct.pack("<6H", a, b, 0, FLAG_PRESENT, 0, k + 1)
    if len(payload) % 4:
        payload += b"\x00" * (4 - len(payload) % 4)
    return MAGIC_TRIE + struct.pack("<I", 8 + len(payload)) + bytes(payload)


# ---------------------------------------------------------------------------
# EXT (mschxudp)
# ---------------------------------------------------------------------------


@dataclass
class ExtEntry:
    code: str  # lowercase in file; we store upper for consistency
    char: str
    flags: int = 2  # 2=一般擴展 4=基本區兼容碼 5=Ext-A 6=HKSCS


def _ext_decode_char(buf: bytes, pos: int) -> tuple[str, int]:
    if pos + 2 > len(buf):
        raise CodecError("truncated Ext.lex character")
    cp = struct.unpack_from("<H", buf, pos)[0]
    pos += 2
    if 0xD800 <= cp <= 0xDBFF:
        if pos + 2 > len(buf):
            raise CodecError("truncated surrogate pair")
        lo = struct.unpack_from("<H", buf, pos)[0]
        pos += 2
        if not (0xDC00 <= lo <= 0xDFFF):
            raise CodecError(f"bad low surrogate {lo:#x}")
        cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00)
    elif 0xDC00 <= cp <= 0xDFFF:
        raise CodecError(f"unexpected low surrogate {cp:#x}")
    if pos + 2 <= len(buf):
        z = struct.unpack_from("<H", buf, pos)[0]
        if z == 0:
            pos += 2
    return chr(cp), pos


def _ext_encode_char(ch: str) -> bytes:
    cp = ord(ch)
    if cp > 0xFFFF:
        high = 0xD800 + ((cp - 0x10000) >> 10)
        low = 0xDC00 + ((cp - 0x10000) & 0x3FF)
        return struct.pack("<HHH", high, low, 0)
    return struct.pack("<HH", cp, 0)


def decode_ext(data: bytes) -> list[ExtEntry]:
    if data[:8] != MAGIC_EXT:
        raise CodecError("not an mschxudp Ext.lex")
    ver, hdr, str_off, fsize, count = struct.unpack_from("<IIIII", data, 8)
    if fsize != len(data):
        raise CodecError(f"Ext size field {fsize} != {len(data)}")
    if hdr != 0x40:
        raise CodecError(f"unexpected Ext header size {hdr}")
    offs = list(struct.unpack_from(f"<{count}I", data, hdr))
    pool = data[str_off:]
    out: list[ExtEntry] = []
    for i, start in enumerate(offs):
        end = offs[i + 1] if i + 1 < count else len(pool)
        rec = pool[start:end]
        if len(rec) < 10:
            raise CodecError(f"Ext record {i} too short")
        _a, _b, text_off, flags = struct.unpack_from("<HHHH", rec, 0)
        if text_off > len(rec) or text_off < 8:
            raise CodecError(f"Ext record {i} bad text_off {text_off}")
        code_bytes = rec[8:text_off]
        if len(code_bytes) < 2 or (len(code_bytes) % 2):
            raise CodecError(f"Ext record {i} odd code field")
        code = code_bytes.decode("utf-16le").rstrip("\x00").upper()
        ch, _ = _ext_decode_char(rec, text_off)
        out.append(ExtEntry(code=code, char=ch, flags=flags))
    return out


def encode_ext(entries: list[ExtEntry], timestamp: int | None = None) -> bytes:
    if not entries:
        raise CodecError("empty Ext.lex")
    # ChtChangjieDS.DLL 以二分搜尋在 Ext.lex 依 code 找字，記錄必須依小寫 code 升冪。
    # 穩定排序：同 code 的多個字保留輸入順序（＝重碼順序）。官方 Ext.lex 本來就已排序，
    # 排序後仍逐位元一致。
    entries = sorted(entries, key=lambda e: e.code.lower())
    recs: list[bytes] = []
    offs: list[int] = []
    cursor = 0
    for e in entries:
        code = e.code.lower()
        if not all("a" <= c <= "z" for c in code):
            raise CodecError(f"Ext code must be A-Z: {e.code!r}")
        if len(e.char) != 1:
            raise CodecError(f"Ext char must be a single character: {e.char!r}")
        code_blob = (code + "\x00").encode("utf-16le")
        text_off = 8 + len(code_blob)
        rec = struct.pack("<HHHH", 8, 8, text_off, e.flags) + code_blob + _ext_encode_char(e.char)
        offs.append(cursor)
        recs.append(rec)
        cursor += len(rec)
    pool = b"".join(recs)
    hdr_size = 0x40
    count = len(entries)
    str_off = hdr_size + count * 4
    ts = timestamp if timestamp is not None else int(time.time())
    hdr = bytearray(hdr_size)
    hdr[0:8] = MAGIC_EXT
    struct.pack_into("<I", hdr, 8, 1)
    struct.pack_into("<I", hdr, 12, hdr_size)
    struct.pack_into("<I", hdr, 16, str_off)
    struct.pack_into("<I", hdr, 24, count)
    struct.pack_into("<I", hdr, 32, ts)
    idx = struct.pack(f"<{count}I", *offs)
    total = hdr_size + len(idx) + len(pool)
    struct.pack_into("<I", hdr, 20, total)
    return bytes(hdr) + idx + pool


# ---------------------------------------------------------------------------
# Text I/O
# ---------------------------------------------------------------------------


def detect_magic(data: bytes) -> str:
    if data[:4] == MAGIC_SPD:
        return "spd"
    if data[:4] == MAGIC_SDC:
        return "lex"
    if data[:8] == MAGIC_EXT:
        return "ext"
    text = data[:32].lstrip()
    if text.startswith(b"# type:"):
        kind = text.split(b"\n", 1)[0].split(b":", 1)[1].strip().decode()
        return {"spd": "spd-text", "lex": "lex-text", "ext": "ext-text"}.get(kind, "text")
    return "text"


def spd_to_text(codes: list[str], source: str | None = None) -> str:
    lines = ["# type: spd", f"# {len(codes)} codes"]
    if source:
        lines.append(f"# source: {source}")
    lines.append("")
    lines.extend(codes)
    lines.append("")
    return "\n".join(lines)


def lex_to_text(lex: LexFile, source: str | None = None) -> str:
    lines = [
        "# type: lex",
        "# columns: text <TAB> codes [ <TAB> weight ]",
        f"# {len(lex.entries)} entries",
    ]
    if source:
        lines.append(f"# source: {source}")
    if lex.stamp:
        lines.append(f"# stamp: {lex.stamp:#x}")
    if lex.item != 1:
        lines.append(f"# item: {lex.item}")
    lines.append("")
    for e in lex.entries:
        codes = " ".join(e.codes)
        if e.weight != DEFAULT_LEX_WEIGHT:
            lines.append(f"{e.text}\t{codes}\t{e.weight}")
        else:
            lines.append(f"{e.text}\t{codes}")
    lines.append("")
    return "\n".join(lines)


def ext_to_text(entries: list[ExtEntry], source: str | None = None) -> str:
    lines = [
        "# type: ext",
        "# columns: code <TAB> char [ <TAB> flags ]",
        "# flags: 2=一般擴展 4=基本區兼容碼 5=Ext-A 6=HKSCS（省略=2）",
        f"# {len(entries)} entries",
    ]
    if source:
        lines.append(f"# source: {source}")
    lines.append("")
    for e in entries:
        if e.flags != 2:
            lines.append(f"{e.code}\t{e.char}\t{e.flags}")
        else:
            lines.append(f"{e.code}\t{e.char}")
    lines.append("")
    return "\n".join(lines)


def _parse_int_comment(s: str) -> int:
    raw = s.split(":", 1)[1].strip()
    return int(raw, 16) if raw.lower().startswith("0x") else int(raw)


def parse_text(text: str) -> tuple[str, object]:
    kind = "auto"
    rows: list[str] = []
    stamp = 0
    item = 1
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("# type:"):
            kind = s.split(":", 1)[1].strip().lower()
            continue
        if s.startswith("# stamp:"):
            stamp = _parse_int_comment(s)
            continue
        if s.startswith("# item:"):
            item = _parse_int_comment(s)
            continue
        if not s or s.startswith("#"):
            continue
        rows.append(ln.rstrip("\n"))
    if kind in ("auto", "spd") and all(len(r.split("\t")) == 1 for r in rows[:20] or [""]):
        if kind == "auto":
            kind = "spd"
    if kind == "spd":
        return "spd", [r.split()[0] for r in rows]
    if kind in ("lex", "auto") and any("\t" in r for r in rows):
        entries: list[LexEntry] = []
        for r in rows:
            parts = r.split("\t")
            if len(parts) < 2:
                raise CodecError(f"lex line needs text<TAB>codes: {r!r}")
            text_s, codes_s = parts[0], parts[1]
            weight = int(parts[2]) if len(parts) > 2 and parts[2] else DEFAULT_LEX_WEIGHT
            codes = [c.upper() for c in codes_s.replace(",", " ").split() if c]
            if len(codes) != len(text_s):
                raise CodecError(f"{text_s!r}: {len(text_s)} chars vs {len(codes)} codes")
            entries.append(LexEntry(text=text_s, codes=codes, weight=weight))
        # distinguish ext vs lex: ext has 1 char and 1 code typically all lowercase originally
        if kind == "auto":
            if entries and all(len(e.text) == 1 for e in entries[:50]):
                # could be ext; if any code looks like multi-letter and char is rare, still lex
                kind = "lex"
        return "lex", LexFile(entries=entries, item=item, stamp=stamp)
    if kind == "ext":
        entries_e: list[ExtEntry] = []
        for r in rows:
            parts = r.split("\t")
            if len(parts) < 2:
                raise CodecError(f"ext line needs code<TAB>char: {r!r}")
            flags = int(parts[2]) if len(parts) > 2 and parts[2] else 2
            ch = parts[1]
            if len(ch) != 1:
                raise CodecError(f"ext char must be 1 character: {ch!r}")
            entries_e.append(ExtEntry(code=parts[0].upper(), char=ch, flags=flags))
        return "ext", entries_e
    raise CodecError(f"cannot parse text (type={kind})")


def parse_text_force(text: str, kind: str) -> object:
    if kind == "spd":
        return [r.split()[0] for r in text.splitlines() if r.strip() and not r.strip().startswith("#") and not r.strip().startswith("# type")]
    got, obj = parse_text(text if "# type:" in text else f"# type: {kind}\n{text}")
    return obj


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_info(args: argparse.Namespace) -> int:
    data = Path(args.input).read_bytes()
    kind = detect_magic(data)
    print(f"file: {args.input}")
    print(f"size: {len(data)}")
    print(f"type: {kind}")
    if kind == "spd":
        codes = decode_spd(data)
        print(f"codes: {len(codes)}")
        print(f"min/max length: {min(map(len, codes))}/{max(map(len, codes))}")
        print(f"sample: {codes[:8]}")
        n = struct.unpack_from("<I", data, 12)[0]
        trie_off = 16 + n * RECORD_SIZE
        if trie_off + 8 <= len(data) and data[trie_off : trie_off + 4] == MAGIC_TRIE:
            print(f"trie at {trie_off:#x}, size {struct.unpack_from('<I', data, trie_off + 4)[0]}")
    elif kind == "lex":
        spd = decode_spd(Path(args.spd).read_bytes()) if args.spd else None
        if spd:
            print(f"spd codes: {len(spd)} from {args.spd}")
        lex = decode_lex(data, spd)
        print(f"entries: {len(lex.entries)}")
        from collections import Counter

        c = Counter(len(e.text) for e in lex.entries)
        print("by length:", dict(sorted(c.items())))
        print("sample:")
        for e in lex.entries[:8]:
            print(f"  {e.text!r}  {' '.join(e.codes)}")
        lay = _lex_layout(data)
        body = 44 + (lay["lcount"] + 1) * 4
        print(f"L_count: {lay['lcount']}  perm starts at {body:#x}  nwords={lay['nwords']}")
        print(f"trie: {len(lay['trie'])} bytes, magic {lay['trie'][:4]!r}")
    elif kind == "ext":
        entries = decode_ext(data)
        print(f"entries: {len(entries)}")
        print("sample:")
        for e in entries[:8]:
            print(f"  {e.code}  {e.char}  U+{ord(e.char):04X}  flags={e.flags}")
    else:
        print("unknown / text")
    return 0


def cmd_decode(args: argparse.Namespace) -> int:
    data = Path(args.input).read_bytes()
    kind = detect_magic(data)
    if kind == "spd":
        out = spd_to_text(decode_spd(data), args.input)
    elif kind == "lex":
        spd = decode_spd(Path(args.spd).read_bytes()) if args.spd else None
        if spd is None:
            print("warning: no --spd, codes dumped as #index", file=sys.stderr)
        out = lex_to_text(decode_lex(data, spd), args.input)
    elif kind == "ext":
        out = ext_to_text(decode_ext(data), args.input)
    else:
        raise CodecError(f"not a known binary: {args.input}")
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


def cmd_encode(args: argparse.Namespace) -> int:
    text = Path(args.input).read_text(encoding="utf-8")
    kind_hint = args.type
    if kind_hint:
        text = f"# type: {kind_hint}\n" + text
    kind, obj = parse_text(text)
    if kind == "spd":
        blob = encode_spd(obj)  # type: ignore[arg-type]
    elif kind == "lex":
        if not args.spd:
            raise CodecError("encoding lex requires --spd (code table)")
        spd = _load_spd_codes(Path(args.spd))
        return _encode_lex_profiles(obj, spd, args)  # type: ignore[arg-type]
    elif kind == "ext":
        blob = encode_ext(obj)  # type: ignore[arg-type]
    else:
        raise CodecError(f"unknown text type {kind}")
    Path(args.output).write_bytes(blob)
    print(f"wrote {len(blob)} bytes -> {args.output} ({kind})", file=sys.stderr)
    return 0


def _load_spd_codes(path: Path) -> list[str]:
    """SPD 碼表清單。接受二進位 .spd 或一行一碼的文字（# type: spd）。

    順序與 encode_spd 寫出的碼表一致（_normalize_codes：去重、排序），
    _code_index_map / build_spd_trie 才對得上。
    """
    raw = path.read_bytes()
    if detect_magic(raw) == "spd":
        return decode_spd(raw)
    text = path.read_text(encoding="utf-8")
    if "# type:" not in text:
        text = "# type: spd\n" + text
    kind, obj = parse_text(text)
    if kind == "spd":
        return _normalize_codes(obj)  # type: ignore[arg-type]
    raise CodecError(f"--spd is not an SPD file or codes text: {path}")


def _load_spd_blob(path: Path, fallback_codes: list[str]) -> bytes:
    raw = path.read_bytes()
    if detect_magic(raw) == "spd":
        return raw
    text = path.read_text(encoding="utf-8")
    if "# type:" not in text:
        text = "# type: spd\n" + text
    kind, obj = parse_text(text)
    if kind == "spd":
        return encode_spd(obj)  # type: ignore[arg-type]
    if fallback_codes:
        return encode_spd(fallback_codes)
    raise CodecError(f"--spd is not an SPD file or codes text: {path}")


def _load_ext_blob(path: Path) -> bytes:
    raw = path.read_bytes()
    if detect_magic(raw) == "ext":
        return raw
    text = path.read_text(encoding="utf-8")
    if "# type:" not in text:
        text = "# type: ext\n" + text
    kind, obj = parse_text(text)
    if kind != "ext":
        raise CodecError(f"--ext is not Ext.lex / ext tsv: {path}")
    return encode_ext(obj)  # type: ignore[arg-type]


def _encode_dest_dir(out: Path, profile: str) -> tuple[Path, bool]:
    """Return (directory, honor_custom_dict_filename)."""
    named_file = out.suffix.lower() in {".sdc", ".lex"}
    if profile == PROFILE_BOTH:
        if named_file:
            raise CodecError("-o must be a directory when --profile both (each set needs sdc/lex + spd)")
        if out.exists() and not out.is_dir():
            raise CodecError(f"-o exists and is not a directory: {out}")
        return out, False
    if named_file:
        dest = out.parent if out.parent.parts else Path(".")
        dest.mkdir(parents=True, exist_ok=True)
        return dest, True
    return out, False


def _encode_lex_profiles(lex: LexFile, spd: list[str], args: argparse.Namespace) -> int:
    profile = getattr(args, "profile", PROFILE_BOTH) or PROFILE_BOTH
    out = Path(args.output)
    jobs: list[str] = [PROFILE_2004, PROFILE_LEGACY] if profile == PROFILE_BOTH else [profile]
    dest_dir, honor_name = _encode_dest_dir(out, profile)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if not args.spd:
        raise CodecError("encoding lex requires --spd (binary .spd or codes text); companion SPD is written next to the dictionary")
    spd_blob = _load_spd_blob(Path(args.spd), spd)

    ext_blob = _load_ext_blob(Path(args.ext)) if getattr(args, "ext", None) else None

    for prof in jobs:
        spec = profile_spec(prof)
        blob, dropped = encode_lex(lex, spd, max_len=spec.max_len, force_lcount=spec.force_lcount)
        dict_path = dest_dir / spec.dict_name
        if honor_name:
            dict_path = out
        dict_path.write_bytes(blob)
        lcount = struct.unpack_from("<I", blob, 28)[0]
        body = 44 + (lcount + 1) * 4
        note = f", dropped {dropped} words longer than {spec.max_len}" if dropped else ""
        print(
            f"wrote {len(blob)} bytes -> {dict_path} "
            f"(profile={prof}, L_count={lcount}, perm@{body:#x}{note})",
            file=sys.stderr,
        )

        spd_path = dict_path.parent / spec.spd_name
        spd_path.write_bytes(spd_blob)
        print(f"wrote {len(spd_blob)} bytes -> {spd_path} (companion SPD)", file=sys.stderr)

        if ext_blob is not None:
            ext_path = dict_path.parent / spec.ext_name
            ext_path.write_bytes(ext_blob)
            print(f"wrote {len(ext_blob)} bytes -> {ext_path} (companion Ext.lex)", file=sys.stderr)

        extras = spec.spd_name if ext_blob is None else f"{spec.spd_name} + {spec.ext_name}"
        print(f"pack {prof}: {dict_path.name} + {extras}", file=sys.stderr)
    return 0


def cmd_roundtrip(args: argparse.Namespace) -> int:
    data = Path(args.input).read_bytes()
    kind = detect_magic(data)
    ok = True
    if kind == "spd":
        codes = decode_spd(data)
        rebuilt = encode_spd(codes)
        again = decode_spd(rebuilt)
        n = struct.unpack_from("<I", data, 12)[0]
        t0 = data[16 : 16 + n * RECORD_SIZE]
        n2 = struct.unpack_from("<I", rebuilt, 12)[0]
        t1 = rebuilt[16 : 16 + n2 * RECORD_SIZE]
        trie0 = data[16 + n * RECORD_SIZE :]
        trie1 = rebuilt[16 + n2 * RECORD_SIZE :]
        trie_exact = trie0 == trie1
        print(
            f"spd codes {len(codes)} identical={codes == again} "
            f"table_bytes={t0 == t1} trie_bytes={trie_exact}"
        )
        if not trie_exact:
            for i, (a, b) in enumerate(zip(trie0, trie1)):
                if a != b:
                    print(f" first trie diff at byte {i} ({i:#x}): {a} vs {b}")
                    break
            print(f" trie lengths: {len(trie0)} vs {len(trie1)}")
        ok = codes == again and t0 == t1 and trie_exact
    elif kind == "lex":
        if not args.spd:
            raise CodecError("lex roundtrip needs --spd")
        spd = decode_spd(Path(args.spd).read_bytes())
        lex = decode_lex(data, spd)
        lcount = struct.unpack_from("<I", data, 28)[0]
        rebuilt, dropped = encode_lex(lex, spd, max_len=lcount, force_lcount=lcount)
        if dropped:
            print(f"warning: roundtrip dropped {dropped} entries", file=sys.stderr)
        lex2 = decode_lex(rebuilt, spd)
        pairs1 = [(e.text, tuple(e.codes)) for e in lex.entries]
        pairs2 = [(e.text, tuple(e.codes)) for e in lex2.entries]
        print(f"lex entries {len(pairs1)} identical={pairs1 == pairs2}")
        if pairs1 != pairs2:
            for a, b in zip(pairs1, pairs2):
                if a != b:
                    print(" first diff", a, "vs", b)
                    break
            print(" lens", len(pairs1), len(pairs2))
        ok = pairs1 == pairs2
    elif kind == "ext":
        e1 = decode_ext(data)
        rebuilt = encode_ext(e1)
        e2 = decode_ext(rebuilt)
        a = [(x.code, x.char, x.flags) for x in e1]
        b = [(x.code, x.char, x.flags) for x in e2]
        print(f"ext entries {len(a)} identical={a == b} orig={len(data)} new={len(rebuilt)}")
        ok = a == b
    else:
        raise CodecError("unknown type")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CHT IME lex/spd/Ext.lex codec")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_spd(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--spd", help="companion ChtChangjie.spd / ChtCangjie.spd")
        sp.add_argument("--ext", help="companion Ext.lex (copied into each generated set)")

    i = sub.add_parser("info", help="summarise a binary")
    i.add_argument("input")
    add_spd(i)
    i.set_defaults(func=cmd_info)

    d = sub.add_parser("decode", help="binary → text")
    d.add_argument("input")
    d.add_argument("-o", "--output")
    add_spd(d)
    d.set_defaults(func=cmd_decode)

    e = sub.add_parser("encode", help="text → binary")
    e.add_argument("input")
    e.add_argument("-o", "--output", required=True)
    e.add_argument("--type", choices=["spd", "lex", "ext"])
    e.add_argument(
        "--profile",
        choices=[PROFILE_2004, PROFILE_LEGACY, PROFILE_BOTH],
        default=PROFILE_BOTH,
        help="lex/sdc 世代：2004=Win10 2004+/Win11（ChtCangjie.sdc+ChtCangjie.spd）；"
        "legacy=舊版（ChtChangjie.lex+ChtChangjie.spd）；both=兩套都生成（預設）。"
        "每套必寫配套 SPD；加 --ext 再寫配套 Ext.lex。IME 不能只靠單獨一個 sdc/lex。",
    )
    add_spd(e)
    e.set_defaults(func=cmd_encode)

    r = sub.add_parser("roundtrip", help="decode+encode and compare payload")
    r.add_argument("input")
    add_spd(r)
    r.set_defaults(func=cmd_roundtrip)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except CodecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
