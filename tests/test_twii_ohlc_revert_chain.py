"""tests/test_twii_ohlc_revert_chain.py — Issue #1099 PR-1（TWII 日 K OHLC 唯讀契約）對
`src/data/macro/macro_cache_reader.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
PR-1 在 `macro_cache_reader.py` 新增 `load_twii_ohlc`（＋模組 docstring 一行 API 說明）。這個檔被舊鏈
（B2／D2／Z40／Z63／C1／P4…）以「新寫法 → 舊寫法」錨點還原成各自的基底 sha256；PR-1 的新增行落在它們的
比對範圍之內 ⇒ 需在鏈頭**往前接一節**：`b2_revert_for` 開頭先呼叫本節的 `twii_ohlc_revert_for`
（比照 `d2stale_revert_for` 開頭先呼叫 `b2_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha、不放寬任何斷言、不 skip）。

基底 ＝ PR-1 開工前的 `f4c7a0d`（origin/main）；`git show f4c7a0d:<檔> | sha256sum` 實算後寫死，測試不依賴 git。
還原組由 difflib 逐區塊自動產生（純新增區塊；每個 new 片段在現行檔恰 1 次、在基底 0 次）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TWII_OHLC_BASE_SHA = {'src/data/macro/macro_cache_reader.py': 'cfd5de03cdadfb83fd0c1257da137272edc895185b8c0b5bcf537c5e22335e2d'}

TWII_OHLC_REVERT_PAIRS = {'src/data/macro/macro_cache_reader.py': (('- `load_twii_ohlc(cache_dir, *, today) -> DataFrame`:讀 '
                                           'twii_ohlcv.parquet → 日 K open/high/low/close/fetched_at\n'
                                           '  (Issue #1099 PR-1;唯讀、不驗證、不去重 —— 驗證交 L0 '
                                           '`shared.twii_ohlc_contract`;⛔ 不含 volume)\n',
                                           ''),
                                          ('#: `load_twii_ohlc` 回傳的欄位(Issue #1099 PR-1;順序固定)。\n'
                                           '#: ⛔ 刻意**不含 `volume`**:parquet 的 volume 實測有 NaN 與 volume=0 列(見 '
                                           '`scripts/update_macro_history.py`\n'
                                           '#: `fetch_twii_ohlcv` 註解),DEC-156 規格明文「不畫量、不把缺量當零」—— '
                                           '不讀進來就不會被誤畫。\n'
                                           'TWII_OHLC_COLUMNS: tuple = ("open", "high", "low", "close", '
                                           '"fetched_at")\n'
                                           '\n'
                                           '\n'
                                           'def _empty_twii_ohlc() -> pd.DataFrame:\n'
                                           '    return pd.DataFrame(columns=list(TWII_OHLC_COLUMNS),\n'
                                           '                        index=pd.DatetimeIndex([], '
                                           'name="date"))\n'
                                           '\n'
                                           '\n'
                                           'def load_twii_ohlc(\n'
                                           '    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,\n'
                                           '    *,\n'
                                           '    today=None,\n'
                                           ') -> pd.DataFrame:\n'
                                           '    """讀 twii_ohlcv.parquet → 日 K DataFrame(index=date Timestamp '
                                           '升序;欄 = `TWII_OHLC_COLUMNS`)。\n'
                                           '\n'
                                           '    Issue #1099 PR-1(DEC-156 A:重用既有 Yahoo `^TWII` 日 OHLC '
                                           '快取,唯讀)。\n'
                                           '    - **只讀、不驗證**:⛔ 不去重、⛔ 不 dropna、⛔ 不補值 —— 合法性(有限正值、OHLC '
                                           '關係、日期唯一升序、\n'
                                           '      未來日、未收盤棒、as_of 同源)由 L3 呼叫 L0 '
                                           '`shared.twii_ohlc_contract.validate_ohlc_window` 判定,\n'
                                           '      在這裡先清掉會讓「壞資料」從驗證者眼前消失(§1 掩蓋 ≠ 解決)。\n'
                                           '    - 一次讀檔 = 一個快照:新鮮度判定用**同一份** '
                                           'DataFrame(`_attach_staleness(..., df=_raw)`),\n'
                                           '      掛在回傳 DataFrame 的 `.attrs`(與 `load_twii_close` 同一組 key)。\n'
                                           '    - 缺檔 / 壞檔 / 空檔 / 缺欄 / 轉型失敗 → 印一行 log 並回空 DataFrame(欄位保留,§1 '
                                           '出聲不吞)。\n'
                                           '    - 無 streamlit、無網路。\n'
                                           '\n'
                                           '    Args:\n'
                                           '        cache_dir: parquet cache 目錄(預設 data_cache/)\n'
                                           '        today: 過期判定的基準日(測試注入;None → 今天)\n'
                                           '    """\n'
                                           '    path = cache_dir / "twii_ohlcv.parquet"\n'
                                           '    df = load_parquet_safe(path, {"date", *TWII_OHLC_COLUMNS})\n'
                                           '    if df is None:\n'
                                           '        print(f"[macro_cache_reader/load_twii_ohlc] '
                                           'twii_ohlcv.parquet 讀不到、為空或缺欄"\n'
                                           '              f"(需要 {sorted({\'date\', *TWII_OHLC_COLUMNS})})→ '
                                           '回空 DataFrame")\n'
                                           '        return _empty_twii_ohlc()\n'
                                           '    try:\n'
                                           '        _raw = df\n'
                                           '        out = df.loc[:, ["date", *TWII_OHLC_COLUMNS]].copy()\n'
                                           '        out["date"] = pd.to_datetime(out["date"])\n'
                                           '        out = out.set_index("date").sort_index(kind="stable")\n'
                                           '        for _c in ("open", "high", "low", "close"):\n'
                                           '            out[_c] = out[_c].astype(float)\n'
                                           '        return _attach_staleness(out, "twii_ohlcv", '
                                           'cache_dir=cache_dir,\n'
                                           '                                 df=_raw, today=today)\n'
                                           '    except Exception as e:  # noqa: BLE001 — 轉型失敗就講出來(§1),回空讓 L3 '
                                           '走「讀不到」\n'
                                           '        print(f"[macro_cache_reader/load_twii_ohlc] 處理失敗:{e}")\n'
                                           '        return _empty_twii_ohlc()\n'
                                           '\n'
                                           '\n',
                                           ''))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def twii_ohlc_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 PR-1 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = TWII_OHLC_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} PR-1 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_twii_ohlc_revert_is_exact_base_source():
    assert set(TWII_OHLC_REVERT_PAIRS) == set(TWII_OHLC_BASE_SHA)
    for rel in sorted(TWII_OHLC_REVERT_PAIRS):
        code = twii_ohlc_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == TWII_OHLC_BASE_SHA[rel], rel


def test_twii_ohlc_revert_is_idempotent():
    for rel in sorted(TWII_OHLC_REVERT_PAIRS):
        once = twii_ohlc_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert twii_ohlc_revert_for(rel, once) == once, rel


def test_twii_ohlc_anchors_present_once_in_current_file_and_never_in_base():
    """每個新片段在現行檔恰 1 次；還原後 0 次 —— 防止還原組變成空轉。"""
    for rel, pairs in TWII_OHLC_REVERT_PAIRS.items():
        cur = (REPO / rel).read_text(encoding="utf-8")
        base = twii_ohlc_revert_for(rel, cur)
        for new, _old in pairs:
            assert cur.count(new) == 1 and base.count(new) == 0, (rel, new[:60])


def test_twii_ohlc_revert_removes_load_twii_ohlc():
    """自證：還原後的基底碼不含任何 PR-1 識別字。"""
    for rel in TWII_OHLC_REVERT_PAIRS:
        base = twii_ohlc_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert "load_twii_ohlc" not in base and "TWII_OHLC_COLUMNS" not in base, rel


def test_b2_chain_head_calls_this_node_first():
    """原鏈頭 `b2_revert_for` 必須先呼叫本節（否則舊批次的基底 sha 守衛看到的是 PR-1 的新寫法）。"""
    import inspect

    from tests.test_b2_consumer_revert_chain import b2_revert_for
    src = inspect.getsource(b2_revert_for)
    assert src.index("twii_ohlc_revert_for(file_path, code)") < src.index("B2_REVERT_PAIRS.get(rel")
