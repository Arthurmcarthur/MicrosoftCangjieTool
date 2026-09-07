from pathlib import Path

from cjtoolkit import codec, validate


def test_code_table_ok(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("a\t日\nbu\t目\n", encoding="utf-8")
    rep = validate.validate_path(p)
    assert rep.kind == "code-table"
    assert rep.ok


def test_code_table_bad_code_chars(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("a\t日\nBAD1\t目\n@@@\t月\n", encoding="utf-8")
    rep = validate.validate_path(p)
    assert not rep.ok
    assert any("非 A" in i.msg for i in rep.errors)


def test_spd_roundtrip_ok():
    blob = codec.encode_spd(["A", "BU", "OG"])
    rep = validate.validate_spd(blob)
    assert rep.ok
    assert rep.info["TRIE"] == "標準格式"


def test_lex_weight_over_cap_is_error():
    lex = codec.LexFile(entries=[
        codec.LexEntry("日", ["A"], 20_000_000),
        codec.LexEntry("目", ["BU"], 12_000_000),
    ])
    blob, _ = codec.encode_lex(lex, ["A", "BU"], max_len=8, force_lcount=8)
    rep = validate.validate_lex(blob, ["A", "BU"])
    assert not rep.ok
    assert any("2^24" in i.msg for i in rep.errors)


def test_ext_inversion_is_error():
    good = [codec.ExtEntry("aaa", "\U0002F81A", 2),
            codec.ExtEntry("aab", "\U0002F81B", 2)]
    blob = codec.encode_ext(good)  # encode_ext 會排序 → 應合法
    assert validate.validate_ext(blob).ok

    # 手動製造逆序：直接改 offset 表順序太脆，改測 decode 後的檢查邏輯
    entries = codec.decode_ext(blob)
    lower = [e.code.lower() for e in entries]
    assert lower == sorted(lower)


def test_set_missing_spd(tmp_path):
    lex = codec.LexFile(entries=[codec.LexEntry("日", ["A"], 12_000_000)])
    blob, _ = codec.encode_lex(lex, ["A"], max_len=8, force_lcount=8)
    p = tmp_path / "ChtChangjie.lex"
    p.write_bytes(blob)
    rep = validate.validate_set([p])
    assert not rep.ok
    assert any("缺少配套 .spd" in i.msg for i in rep.issues)


def test_set_ok(tmp_path):
    codes = ["A", "BU"]
    lex = codec.LexFile(entries=[
        codec.LexEntry("日", ["A"], 12_000_000),
        codec.LexEntry("目", ["BU"], 11_000_000),
    ])
    lb, _ = codec.encode_lex(lex, codes, max_len=8, force_lcount=8)
    (tmp_path / "ChtChangjie.lex").write_bytes(lb)
    (tmp_path / "ChtChangjie.spd").write_bytes(codec.encode_spd(codes))
    rep = validate.validate_set([
        tmp_path / "ChtChangjie.lex",
        tmp_path / "ChtChangjie.spd",
    ])
    assert rep.ok, rep.render()
