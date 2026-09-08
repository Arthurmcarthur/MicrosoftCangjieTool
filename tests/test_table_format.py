from cjtoolkit import convert


def w(tmp_path, text, name="t.txt", encoding="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(encoding))
    return p


def test_layout_explicit_char_code(tmp_path):
    p = w(tmp_path, "日\ta\n目\tbu\n")
    ct = convert.parse_code_table(p, "char-code")
    assert ("日", "A", 0) in ct.rows


def test_layout_explicit_code_char(tmp_path):
    p = w(tmp_path, "a\t日\nbu\t目\n")
    ct = convert.parse_code_table(p, "code-char")
    assert ("日", "A", 0) in ct.rows


def test_sep_space(tmp_path):
    p = w(tmp_path, "日 a\n目   bu\n")   # 單／多個空格
    ct = convert.parse_code_table(p, "char-code", separator="space")
    assert ct.first_code["目"] == "bu"


def test_fullwidth_space_as_target_char(tmp_path):
    # 碼對應到全形空格 U+3000 —— 不可被當成分隔符（cj3 的 zxaa 那行）
    p = w(tmp_path, "zxaa   　\n")
    assert convert.parse_code_table(p, "code-char", separator="space").first_code["　"] == "zxaa"
    assert convert.parse_code_table(p, "code-char", separator="auto").first_code["　"] == "zxaa"


def test_sep_tab_rejects_space_file(tmp_path):
    p = w(tmp_path, "日 a\n")
    try:
        convert.parse_code_table(p, "char-code", separator="tab")
    except ValueError as e:
        assert "分割" in str(e)
    else:
        raise AssertionError("應該因 tab 分不出兩欄而報錯")


def test_encoding_big5hkscs(tmp_path):
    p = w(tmp_path, "日\ta\n", encoding="big5hkscs")
    ct = convert.parse_code_table(p, "char-code", encoding="big5hkscs")
    assert ct.first_code["日"] == "a"


def test_encoding_utf8_bom_tolerated(tmp_path):
    p = w(tmp_path, "﻿日\ta\n")
    ct = convert.parse_code_table(p, "char-code", encoding="utf-8")
    assert ("日", "A", 0) in ct.rows


def test_wrong_layout_raises(tmp_path):
    p = w(tmp_path, "abc\t日\n")          # 實際是 code-char（碼 abc）
    try:
        convert.parse_code_table(p, "char-code")   # 指定錯的 → ch 會是 "abc"
    except ValueError as e:
        assert "漢字欄" in str(e)
    else:
        raise AssertionError("指定錯欄序應報錯")


def test_wrong_layout_single_letter_caught_by_validate(tmp_path):
    from cjtoolkit import validate
    p = w(tmp_path, "a\t日\n")            # code-char；用 char-code 解會得到 code="日"
    rep = validate.validate_code_table(p, "char-code")
    assert not rep.ok                     # 「日」不是 A–Z 碼
