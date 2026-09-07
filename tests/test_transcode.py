from cjtoolkit import codec, convert, validate


def _make_set(dir_, profile, entries, codes):
    dir_.mkdir(parents=True, exist_ok=True)
    spec = codec.profile_spec(profile)
    lex = codec.LexFile(entries=[codec.LexEntry(t, c, w) for t, c, w in entries])
    blob, _ = codec.encode_lex(lex, codes, max_len=spec.max_len,
                               force_lcount=spec.force_lcount)
    (dir_ / spec.dict_name).write_bytes(blob)
    (dir_ / spec.spd_name).write_bytes(codec.encode_spd(codes))
    return [dir_ / spec.dict_name, dir_ / spec.spd_name]


def test_transcode_legacy_to_2004(tmp_path):
    codes = ["A", "BU", "MM"]
    entries = [("日", ["A"], 12_000_000), ("目", ["BU"], 11_000_000),
               ("日日", ["A", "A"], 10_000_000)]
    files = _make_set(tmp_path / "src", "legacy", entries, codes)
    out = tmp_path / "out"
    res = convert.transcode_set(files, out, target="2004")
    assert (out / "ChtCangjie.sdc").exists()
    assert (out / "ChtCangjie.spd").exists()
    rep = validate.validate_set([out / "ChtCangjie.sdc", out / "ChtCangjie.spd"])
    assert rep.ok, rep.render()


def test_transcode_both_and_drop_long_phrases(tmp_path):
    codes = ["A"]
    # 一條 6 字詞，legacy(8) 留、2004(5) 丟
    entries = [("字", ["A"], 12_000_000),
               ("字字字字字字", ["A"] * 6, 10_000_000)]
    files = _make_set(tmp_path / "src", "legacy", entries, codes)
    res = convert.transcode_set(files, tmp_path / "out", target="both")
    assert res.dropped["legacy"] == 0
    assert res.dropped["2004"] == 1
    assert {p.name for p in res.written} >= {
        "ChtCangjie.sdc", "ChtChangjie.lex", "ChtCangjie.spd", "ChtChangjie.spd"}


def test_transcode_needs_full_set(tmp_path):
    (tmp_path / "only.spd").write_bytes(codec.encode_spd(["A"]))
    try:
        convert.transcode_set([tmp_path / "only.spd"], tmp_path / "o")
    except ValueError as e:
        assert "一整套" in str(e)
    else:
        raise AssertionError("單一 spd 應報錯")
