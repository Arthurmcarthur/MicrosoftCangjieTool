from pathlib import Path

import pytest

from cjtoolkit import convert


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_detect_layout_char_code(tmp_path):
    t = _write(tmp_path, "t.txt", "日\ta\n目\tbu\n月\tb\n")
    ct = convert.parse_code_table(t, "auto")
    assert ("日", "A", 0) in ct.rows
    assert ct.first_code["目"] == "bu"


def test_detect_layout_code_char(tmp_path):
    t = _write(tmp_path, "t.txt", "a\t日\nbu\t目\nb\t月\n")
    ct = convert.parse_code_table(t, "auto")
    assert ("日", "A", 0) in ct.rows


def test_multi_code_each_row(tmp_path):
    t = _write(tmp_path, "t.txt", "分\tCSH\n分\tCH\n")
    res = convert.convert(t)
    assert res.n_char == 2
    assert "CSH" in res.spd_text and "CH" in res.spd_text


def test_weight_monotonic_and_capped(tmp_path):
    chars = "日月木火土水金"
    t = _write(tmp_path, "t.txt",
               "\n".join(f"{c}\tA{'B' * i}" for i, c in enumerate(chars)) + "\n")
    res = convert.convert(t)
    weights = [int(line.split("\t")[2]) for line in res.lex_text.splitlines()
               if line and not line.startswith("#")]
    assert weights == sorted(weights, reverse=True)
    assert all(0 < w < (1 << 24) for w in weights)


def test_supplementary_plane_goes_to_ext(tmp_path):
    t = _write(tmp_path, "t.txt", "\U0002F81A\tA\n日\tA\n")
    res = convert.convert(t)
    assert "\U0002F81A" in res.ext_text
    assert "\U0002F81A" not in res.lex_text
