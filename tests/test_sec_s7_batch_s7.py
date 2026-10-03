"""批 S7（S6-n4／S6-n6／S6-n7；2026-10-02）：`tests/_git_tracked.py` 名長飽和核對＋`secret_scrub` 工作量／錨點上限的突變補強。

⭐ 本批**不改** `scrub_secrets`／`scrub_prose_secrets` 的行為（S6-n5 只改 docstring 的跳脫寫法，`__doc__` 逐字相同）。
本檔新增的全是測試；判準沿用 `tests/test_sec_s3_0928._is_masking_of`（「只多遮、不少遮」）。

- S6-n4：flags 名長 0xFFF（飽和）只在路徑 ≥ 4095 位元組時才由 git 寫出 ⇒ 路徑較短卻記 0xFFF → `IndexCorrupt`（v2／v3／v4、
  有雜湊／檔尾全 0 都要）；真的 git 寫出的長路徑索引照常讀。
- S6-n6：把 `_TOML_REM_BUDGET` 調到「剛好不夠／剛好夠」的值（固定樣本、門檻值寫死）⇒ 任何一處工作量扣點拿掉或加倍，
  門檻就移動、輸出就變 → 突變被殺。調低工作量時輸出仍是「預設輸出再多遮」，也不比 main 792c7a2／bf0ada3／e23ff2f 少遮。
- S6-n7：`_TOML_REM_MAX`（256）改成 255／257／4096 → 固定樣本（同一錨點 256／257 處）的輸出改變（⛔ 不靠計時）。
"""
from __future__ import annotations

import hashlib

import pytest

import shared.secret_scrub as _SSC
from tests.test_sec_s3_0928 import _is_masking_of, _mutant
from tests.test_sec_s3_batch_s3 import _OLD, _b64, _pkcs8, _wrap
from tests.test_sec_s4_batch_s4 import _BF0, _index
from tests.test_sec_s6_batch_s6 import _MAIN, _gt_mutant, _never_less

_SUF = " (line 1 column 1 char 0)"
_BIG = 1 << 26                                                      # 預設工作量（只在本檔還原用；⛔ 不讀模組常數）


# ══════════════════════════════════════════════════════════════════
# S6-n4：flags 名長飽和（0xFFF）但路徑 < 4095 位元組 → IndexCorrupt
# ══════════════════════════════════════════════════════════════════
def _z(data: bytes) -> bytes:
    return data[:-20] + bytes(20)


def _seal(body: bytes) -> bytes:
    return body + hashlib.sha1(body).digest()


def _set_flags(data: bytes, entry_at: int, name_len: int) -> bytes:
    """把位於 `entry_at` 的項目 flags 名長欄換成 `name_len`（保留 extended／stage 位元），重算檔尾 SHA-1。"""
    body = data[:-20]
    at = entry_at + 60
    old = int.from_bytes(body[at:at + 2], "big")
    new = (old & ~0x0FFF) | name_len
    return _seal(body[:at] + new.to_bytes(2, "big") + body[at + 2:])


def _n4_bad() -> dict[str, bytes]:
    """短路徑卻記 0xFFF 的索引（有雜湊版本；檔尾全 0 版本由測試另外產生）。"""
    out = {}
    for ver in (2, 3, 4):
        out[f"v{ver}-first"] = _set_flags(_index(["a.md", "b.md"], ver), 12, 0x0FFF)
        #: 第 1 項（v4 前綴壓縮的第二項，也要核對）。
        first_len = len(_index(["a.md"], ver)) - 20 - 12
        out[f"v{ver}-second"] = _set_flags(_index(["a.md", "b.md"], ver), 12 + first_len, 0x0FFF)
        #: 邊界：4094 位元組（差 1）。
        out[f"v{ver}-4094"] = _set_flags(_index(["L/" + "x" * 4092], ver), 12, 0x0FFF)
    return out


_N4_BAD = _n4_bad()


@pytest.mark.parametrize("trailer", ["sha1", "zero"])
@pytest.mark.parametrize("kind", sorted(_N4_BAD))
def test_n4_saturated_name_len_on_short_path_raises(kind, trailer):
    from tests._git_tracked import IndexCorrupt, IndexUnavailable, parse_index
    data = _N4_BAD[kind] if trailer == "sha1" else _z(_N4_BAD[kind])
    with pytest.raises(IndexCorrupt, match="飽和") as ei:
        parse_index(data)
    assert not isinstance(ei.value, IndexUnavailable)


@pytest.mark.parametrize("trailer", ["sha1", "zero"])
@pytest.mark.parametrize("ver", [2, 3, 4])
@pytest.mark.parametrize("n", [4095, 4096, 5000])
def test_n4_saturated_name_len_on_long_path_accepted(ver, n, trailer):
    """git 對 ≥ 4095 位元組的路徑一律寫 0xFFF（`_index` 同樣寫 `min(len, 0xFFF)`）：照常讀。"""
    from tests._git_tracked import parse_index
    paths = ["L/" + "x" * (n - 2), "zz.md"]
    data = _index(paths, ver)
    assert int.from_bytes(data[12 + 60:12 + 62], "big") & 0x0FFF == 0x0FFF, "前提：名長欄飽和"
    assert parse_index(data if trailer == "sha1" else _z(data)) == frozenset(paths)


def _n4_suite(g: dict) -> list[str]:
    parse, corrupt = g["parse_index"], g["IndexCorrupt"]
    fails = []
    for kind, data in _N4_BAD.items():
        for d in (data, _z(data)):
            try:
                parse(d)
                fails.append(kind)
            except corrupt:
                pass
    for ver in (2, 3, 4):
        paths = ["L/" + "x" * 4093, "zz.md"]
        try:
            if parse(_index(paths, ver)) != frozenset(paths):
                fails.append(f"long-v{ver}")
        except corrupt:
            fails.append(f"long-v{ver}")
    return fails


_N4_MUTANTS = {
    "check-removed": ("            if (flags & _NAME_MASK) == _NAME_MASK and len(path) < _NAME_MASK:\n",
                      "            if False:\n"),
    "bound-off-by-one": ("            if (flags & _NAME_MASK) == _NAME_MASK and len(path) < _NAME_MASK:\n",
                         "            if (flags & _NAME_MASK) == _NAME_MASK and len(path) < _NAME_MASK - 1:\n"),
    "bound-too-strict": ("            if (flags & _NAME_MASK) == _NAME_MASK and len(path) < _NAME_MASK:\n",
                         "            if (flags & _NAME_MASK) == _NAME_MASK and len(path) <= _NAME_MASK:\n"),
}


def test_n4_current_module_passes_suite():
    from tests import _git_tracked as G
    assert _n4_suite(vars(G)) == []


@pytest.mark.parametrize("name", sorted(_N4_MUTANTS))
def test_n4_each_mutant_is_killed(name):
    assert _n4_suite(_gt_mutant(*_N4_MUTANTS[name])), name


#: 真的 git 2.43.0 寫出的索引（`git update-index --add --cacheinfo`，不經檔案系統；v3 以 `--skip-worktree` 加上 extended flag，
#: 再 `--index-version N`；skiphash ＝ `-c index.skipHash=true`）—— zlib＋base64 內嵌（tests/ ⛔ 不得呼叫外部程式，
#: 見 tests/test_zz_test_portability.py；同批 S6 `_REAL_INDEX_B64` 的作法）。路徑含 4094／4095／5000 位元組三個長路徑。
_N4_REAL_PATHS = frozenset(["a.md", "L/" + "x" * 4092, "M/" + "y" * 4093, "N/" + "z" * 4998, "zz.md"])
_N4_REAL_INDEX = {
    "v2-sha1": "eNrt2q8KwlAUgPGDOKsINrtY9FbBIKhB8U8QBOvAuu6uSUwWi+gT2Fa1mBTXFHwL38BgmbMIlolwsYzvByecch7g4zRa/bqIJF5jSaTp5nMbTm7b06O69OeHTG4/WGd1/pwOOmoMAAAAAABiTb76oR88u8oFAAAAAADxZtwPekoDAAAAAAAA+DOzjidJu+SMREz/icTS+n3ImxUrvtu+Nr17qlC77Bbl4yoEnc2obw==",  # 13560 B
    "v2-skiphash": "eNrt2r8KQQEUwOGT3FnKZje6j2BgURiUsiqrnWsympUn8Agmk2LzHt7B4s9ocVM3i76vznCW8wC/Tqc7bEdE6TVJfLTavW/j5XV/urU25/WxWj+MtrWscance+kcAAAA+GuR64t+8OinCwAAAOC/Fe4HgzQDAAAAAH6sWMeL8qQ5m0YU/SeKJMvyDj0BONiejQ==",  # 13560 B
    "v3-sha1": "eNrt2j8LQWEUgPFT3FnKdo0yeu83cOtaFAalrMqkzHjvZDRYvOULMCiryaSuzWwz+wAmUv4sykLqzXJ7fnWGs5wP8HRK5XogIonnOPLRcP6+NcPjKroUzXa0SbvrxjSj87vUraL6AAAAAAAg1uSrH/rBvaoGAAAAAAAg3qz7QU1pAAAAAAAAAH9m1/H8pC+tQrdt+08kjtavM7ns5Go8bzk7hGbfG3cW0fn0AAffqp4=",  # 13560 B
    "v3-skiphash": "eNrt2r8KQWEYwOGvOLOUzW50LsEpFoVBKauy2vlMRrNyBS7BZFJs7sM9WPwZLU7qZNHz1Du8y3sBv95Od9gOIZRek4SPVrv3bby87k+31ua8Plbrh9G2FhuXyr2XzgEAAIC/FnJ90Q8e/XQBAAAA/LfC/WCQRgAAAADgx4p1vKychUlzNi36TxSSGPPOPAGeiZ8O",  # 13560 B
    "v4-sha1": "eNrt2C8PQVEYx/EnnLtp2CS66KbbbALlbAg2m2pTBElxj41JprKJCjNRUNxko4neA1W1mX9Nkc6Uu+9ne8JTfi/gW9CVvIio9zny02Dx/dW6583+lpscRrt4KqhOEyZ9jD6k6HYAAAAAAECoiVU9eM56JdcHAAAAAADhZtsP+mXXAAAAAAAAAPgzq5AnahmpZ1oNuxFHGfMZuQxjXvZ6SgbeXN+b61V7rLcvwnyr5Q==",  # 13553 B
    "v4-skiphash": "eNrt2C0KAmEUhtEvzIBNBJvd6CzBoEVQgyBYBatdR1CMZsFoEldgMgna3Id7sPgTLZMGy3AO3HDLu4Cn3Rm0QgjR9+KQaX34/UaLx+n6bG5vm0uldh7uqmn9Xn6FbjIDAAAACi3kqgfv/bKXzAEAAIBiy9sPVv0kBQAAAAD+LFfIC9GxNG5MJ/lG4ihNs0Y+WDiheg==",  # 13553 B
}


@pytest.mark.parametrize("kind", sorted(_N4_REAL_INDEX))
def test_n4_real_git_index_with_long_paths_parses(kind):
    import base64
    import zlib

    from tests._git_tracked import parse_index
    data = zlib.decompress(base64.b64decode(_N4_REAL_INDEX[kind]))
    ver = int(kind[1])
    assert int.from_bytes(data[4:8], "big") == ver, "前提：索引版本"
    if kind.endswith("skiphash"):
        assert data[-20:] == bytes(20), "前提：git 寫的檔尾是全 0"
    else:
        assert hashlib.sha1(data[:-20]).digest() == data[-20:], "前提：真的 SHA-1 檔尾"
    assert parse_index(data) == _N4_REAL_PATHS


# ══════════════════════════════════════════════════════════════════
# S6-n7：`_TOML_REM_MAX`（256）—— 同一個錨點 256／257 處的固定樣本
# ══════════════════════════════════════════════════════════════════
#: 值含 `char`（錨點 `' (line 1 column 1 char 0)` 的英數字片段）⇒ 錨點超過上限時，多出來的那一段整段遮（`_TOML_REM_MAX` 上方註解）。
_N7_HEAD = "'R7SECRET char"
_N7_MAX = 256                                                       # 寫死（⛔ 不讀模組常數 —— 突變要能被看見）
_N7_PAD = 64


def _n7_sample(n: int) -> str:
    return "\n".join(["could not convert string to float: " + _N7_HEAD + "'" + _SUF]
                     + [f"zz{i:04d}'" + _SUF for i in range(n)])


def _n7_expected(n: int) -> str:
    """預期輸出：第一行的值被遮；錨點 ≤ 256 處時其餘原樣；> 256 處時從第 257 個錨點左邊 `2×len(值)＋64` 字起、到最後一個錨點整段遮。"""
    lines = ["could not convert string to float: ***" + _SUF] + [f"zz{i:04d}'" + _SUF for i in range(n)]
    out = "\n".join(lines)
    if n <= _N7_MAX:
        return out
    anchor = "'" + _SUF
    ps, p = [], out.find(anchor)
    while p >= 0:
        ps.append(p)
        p = out.find(anchor, p + len(anchor))
    a, b = ps[_N7_MAX] - (2 * len(_N7_HEAD) + _N7_PAD), ps[-1]
    return out[:a] + "***" + out[b:]


def _n7_suite(mod) -> list[str]:
    fails = []
    for n in (255, 256, 257, 300):
        x = _n7_sample(n)
        for fn in ("scrub_secrets", "scrub_prose_secrets"):
            if getattr(mod, fn)(x) != _n7_expected(n):
                fails.append(f"{fn}:{n}")
    return fails


def test_n7_fixed_sample_output():
    assert _n7_suite(_SSC) == []
    assert _n7_expected(256).count("zz") == 256 and _n7_expected(257).count("zz") < 257, "前提：上限兩側輸出不同"


@pytest.mark.parametrize("n", [255, 256, 257, 300])
def test_n7_fixed_sample_never_less(n):
    _never_less(_n7_sample(n))
    assert "R7SECRET" not in _SSC.scrub_secrets(_n7_sample(n))


@pytest.mark.parametrize("value", ["255", "257", "4096", "1"])
def test_n7_rem_max_mutant_is_killed(value):
    m = _mutant(("_TOML_REM_MAX: int = 256\n", f"_TOML_REM_MAX: int = {value}\n"))
    assert _n7_suite(m), value


# ══════════════════════════════════════════════════════════════════
# S6-n6：工作量「剛好不夠／剛好夠」—— 每一處扣點拿掉或加倍都會移動門檻
# ══════════════════════════════════════════════════════════════════
def _n6_samples() -> dict[str, str]:
    keyline = _wrap(_b64(_pkcs8(5)))[0]
    keylike = _wrap(_b64(_pkcs8(7)))[0]
    raw = keyline + "\ncould not convert string to float: '" + keylike + " R29CSECRET'" + _SUF
    toml = keyline + "\ncould not convert string to float: '" + keylike + " R29CSECRET'\nTomlDecodeError"
    return {"der-raw": raw,                                         # 逐段比對（64／len(_l0)／2×視窗／8×段數／_lim）
            "der-toml-rr": repr(repr(toml)),                        # 開頭片段（_open_part_len 的扣點）
            "stretch-257": _n7_sample(257)}                         # 錨點超過上限的整段判斷（(_b-_a)//8）


_N6_SAMPLES = _n6_samples()
#: 各樣本「輸出等於預設輸出」所需的最小工作量（批 S7 實測、寫死）：門檻 −1 時輸出多遮，門檻時等於預設。
#: ⚠️ 門檻是**本實作**的工作量記帳結果；日後刻意調整記帳方式時，重新量測並更新這三個數（輸出不變、只是門檻移動）。
#: ⚠️ 批 Y3（S7-n3）補註：這三個數也**綁 Python 3.11 的 regex 路徑** —— 批 S7 是在 Python 3.11 上量的（同 CI 的
#: `python-version: "3.11"`）；`shared/secret_scrub.py` 的 `_POSS` 依版本探測佔有型量詞（3.11 起 `+`，3.10 以前退回
#: 一般量詞），`re` 引擎在其他版本的行為也可能不同，其他版本**沒有量過**。換 Python 版本（或 `re` 行為改變）時，
#: 同樣要重新量測，⛔ 不要沿用這三個數。
_N6_THRESHOLDS = {"der-raw": 1284, "der-toml-rr": 2317, "stretch-257": 39704}


def _n6_out(mod, x: str, budget: int, setter) -> str:
    setter(mod, budget)
    try:
        return mod.scrub_secrets(x)
    finally:
        setter(mod, _BIG)


def _n6_suite(mod, setter) -> list[str]:
    fails = []
    for name, x in _N6_SAMPLES.items():
        t = _N6_THRESHOLDS[name]
        d = _n6_out(mod, x, _BIG, setter)
        lo, hi = _n6_out(mod, x, t - 1, setter), _n6_out(mod, x, t, setter)
        if hi != d:
            fails.append(f"{name}:at-threshold-differs")
        if lo == d:
            fails.append(f"{name}:below-threshold-same")
    return fails


def _plain_set(mod, b: int) -> None:
    mod._TOML_REM_BUDGET = b


def test_n6_budget_thresholds_current_module(monkeypatch):
    def setter(mod, b):
        monkeypatch.setattr(mod, "_TOML_REM_BUDGET", b)
    assert _n6_suite(_SSC, setter) == []


@pytest.mark.parametrize("name", sorted(_N6_SAMPLES))
def test_n6_near_exhausted_output_superset_of_default_and_never_less(monkeypatch, name):
    """工作量不夠時只會多遮：輸出 ⊇ 預設輸出的遮罩，也不比 main 792c7a2／bf0ada3／e23ff2f 少遮；秘密不外露。"""
    x = _N6_SAMPLES[name]
    d = _SSC.scrub_secrets(x)
    _never_less(x)
    t = _N6_THRESHOLDS[name]
    for b in sorted({0, 1, t // 4, t // 2, t - 64, t - 2, t - 1, t, t + 1}):
        monkeypatch.setattr(_SSC, "_TOML_REM_BUDGET", b)
        o = _SSC.scrub_secrets(x)
        assert _is_masking_of(o, d), (b, o[-160:])
        for base in (_MAIN.scrub_secrets(x), _BF0.scrub_secrets(x), _OLD(x)):
            assert _is_masking_of(o, base), (b, o[-160:])
        assert "R29CSECRET" not in o and "R7SECRET" not in o, b


def _n6_mutants() -> dict[str, tuple[str, str]]:
    """`secret_scrub` 裡每一處 `budget[0] -= X`：拿掉（扣 0）與加倍各一個突變。"""
    src = open(_SSC.__file__, encoding="utf-8").read()
    out = {}
    for line in src.splitlines(True):
        if "budget[0] -= " not in line:
            continue
        pre, rest = line.split("budget[0] -= ", 1)
        expr = rest.split("#", 1)[0].rstrip()
        tail = rest[len(expr):]
        out[f"remove:{expr}"] = (line, pre + "budget[0] -= 0" + tail)
        out[f"double:{expr}"] = (line, pre + f"budget[0] -= 2 * ({expr})" + tail)
    return out


_N6_MUTANTS = _n6_mutants()


def test_n6_mutant_inventory_covers_every_charge_site():
    """前提：扣點處共 7 處（批 S7 實測）；新增扣點時本測試紅 → 補樣本與門檻。"""
    assert len(_N6_MUTANTS) == 14, sorted(_N6_MUTANTS)


@pytest.mark.parametrize("name", sorted(_N6_MUTANTS))
def test_n6_each_budget_charge_mutant_is_killed(name):
    m = _mutant(_N6_MUTANTS[name])
    assert _n6_suite(m, _plain_set), name
