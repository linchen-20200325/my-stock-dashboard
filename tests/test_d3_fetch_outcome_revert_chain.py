"""tests/test_d3_fetch_outcome_revert_chain.py — D3(空抓取三態,DEC-148)對 `scripts/update_macro_history.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
D3 在 `update_macro_history.py` 加了 `FetchOutcome` 的標記（`_finmind_get`／`fetch_twii_ohlcv`／`fetch_finmind_inst`／
`fetch_finmind_margin`／`fetch_finmind_m1m2`／`fetch_tw_pmi_history` 的空表出口）與 `update_one` 空抓取分支的 additive metadata 欄。
該檔被舊鏈（Z40／Z63／C1…）以「新寫法 → 舊寫法」錨點還原成各自的基底 sha256;D3 的新增行落在它們的比對範圍之內
⇒ 需在鏈頭**往前接一節**，先把 D3 換回（比照 `d2stale_revert_for` 接在 `p4_revert_for` 開頭的作法;
⛔ 不動任何舊表與舊基底 sha、不放寬任何斷言）。

基底 ＝ D3 開工前的 `b6d2ee4`(origin/main);`git show b6d2ee4:<檔> | sha256sum` 實算後寫死,測試不依賴 git。
還原組由 difflib 逐區塊自動產生（每個 new 片段在現行檔恰 1 次、在基底 0 次）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_UMH_REL = "scripts/update_macro_history.py"

D3_BASE_SHA = {
    _UMH_REL: "3c3c7ff5b4785fe96a9dae13fecabf3398e9da2c0f7671b4f8d0781fa231e7cb",
}

D3_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _UMH_REL: (
        (('                                             D3 起另有 additive 欄 '
          'fetch_outcome／fetch_evidence（只在本輪「抓取為空」時寫；例外／缺 token 路徑不寫，沿用「有 last_error 且非空抓取標記」；\n'
          '                                             三態 NO_NEW_DATA／FETCH_FAILED／UNDETERMINED，定義見 '
          '`shared/fetch_outcome.py`；\n'
          '                                             與 freshness 分離、不取代 last_updated、last_error 照舊）\n'),
         ''),
        (('\n'
          '# D3(DEC-148):空抓取三態(NO_NEW_DATA／FETCH_FAILED／UNDETERMINED)。L0 純規則、不 import pandas／streamlit,\n'
          '# 放檔頭不擴大故障半徑。fetcher 以 DataFrame.attrs 帶結果;缺 attrs ＝ UNDETERMINED(保守預設)。\n'
          'from shared.fetch_outcome import (  # noqa: E402\n'
          '    META_EVIDENCE_KEY as _META_EVIDENCE_KEY,\n'
          '    META_OUTCOME_KEY as _META_OUTCOME_KEY,\n'
          '    FetchOutcome as _FO,\n'
          '    read_outcome as _read_outcome,\n'
          '    tag_outcome as _tag,\n'
          ')\n'),
         ''),
        ('            return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"FinMind {dataset}: HTTP {r.status_code}")\n',
         '            return pd.DataFrame()\n'),
        (('            return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"FinMind {dataset}: status '
          '{d.get(\'status\')}")\n'),
         '            return pd.DataFrame()\n'),
        (('        if df.empty:\n'
          '            # D3:正面證據 = HTTP 200 ＋ status 200 ＋ 回應明確帶 `data: []`。缺 `data` 鍵（或型別不是 list）= 證據不足。\n'
          '            if isinstance(d.get("data"), list):\n'
          '                return _tag(df, _FO.NO_NEW_DATA, f"FinMind {dataset}: HTTP 200, status 200, data=[]")\n'
          '            return _tag(df, _FO.UNDETERMINED, f"FinMind {dataset}: HTTP 200 但回應無 data 清單")\n'),
         ''),
        ('        return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"FinMind {dataset}: exception {type(e).__name__}")\n',
         '        return pd.DataFrame()\n'),
        (('        return _tag(pd.DataFrame(), _FO.FETCH_FAILED,\n'
          '                    f"Yahoo ^TWII: HTTP {r.status_code}" if r is not None else "Yahoo ^TWII: 無回應")\n'),
         '        return pd.DataFrame()\n'),
        (('        try:\n'
          '            j = r.json()\n'
          '        except ValueError as e:      # D3:回應不是 JSON ＝ 明確解析錯誤(與下方「結構缺欄」不同,後者可能只是區間無交易日)\n'
          '            print(f"[twii_ohlcv] json decode error: {type(e).__name__}: {e}")\n'
          '            return _tag(pd.DataFrame(), _FO.FETCH_FAILED, "Yahoo ^TWII: 回應不是合法 JSON")\n'
          '        _chart_err = j.get("chart", {}).get("error") if isinstance(j, dict) else None\n'
          '        if _chart_err:               # D3:API 明確回報錯誤(chart.error 非 null)\n'
          '            print(f"[twii_ohlcv] chart.error: {_chart_err}")\n'
          '            _code = _chart_err.get("code") if isinstance(_chart_err, dict) else None\n'
          '            return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"Yahoo ^TWII: chart.error code={_code}")\n'),
         '        j = r.json()\n'),
        (('        if df.empty:\n'
          '            # D3:結構可解析、但沒有任何有效 close。與「區間無交易日」無從分辨 ⇒ 只能 UNDETERMINED\n'
          '            # (⛔ 不依 weekday 推論成功)。\n'
          '            return _tag(df, _FO.UNDETERMINED, "Yahoo ^TWII: 回應可解析但 0 筆有效 close")\n'),
         ''),
        (("        # D3:此處吞掉的例外包含 KeyError('timestamp')（區間無交易日時 Yahoo 的合法形狀）與真正的 schema 漂移,\n"
          '        # 兩者不可分 ⇒ UNDETERMINED(⛔ 不標 NO_NEW_DATA、不標 FETCH_FAILED);型別名留作證據。\n'
          '        return _tag(pd.DataFrame(), _FO.UNDETERMINED,\n'
          '                    f"Yahoo ^TWII: 解析例外 {type(e).__name__}(含區間無交易日的合法形狀,無法區分)")\n'),
         '        return pd.DataFrame()\n'),
        (('        return _tag(pd.DataFrame(), _FO.UNDETERMINED,\n'
          '                    "FinMind inst: 有資料列但無 Foreign_Investor 列(來源形狀不明,非正面的「無新資料」證據)")\n'),
         '        return pd.DataFrame()\n'),
        (('    if out.empty:   # D3:有 Foreign 列但整日皆因 buy／sell 缺值被剔除 → 證據不足\n'
          '        return _tag(out, _FO.UNDETERMINED, "FinMind inst: 外資列的日期全因 buy／sell 缺值被剔除")\n'),
         ''),
        (('        # D3:來源有回資料列、但取不到 Money 序列 ＝ schema／欄位驗證失敗 ⇒ FETCH_FAILED(附 reason)\n'
          '        return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"FinMind margin: 取不到融資金額序列：{meta[\'reason\']}")\n'),
         '        return pd.DataFrame()\n'),
        ('        return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"CBC EF15M01: import 失敗 {type(e).__name__}")\n',
         '        return pd.DataFrame()\n'),
        ('    _fail_ev = f"CBC {_EF15_FILE}: 未取得可用資料"   # D3:EF15M01 無可用資料時的錯誤證據(各失敗分支覆寫)\n',
         ''),
        (('        _fail_ev = (f"CBC {_EF15_FILE}: HTTP {r.status_code}" if r is not None\n'
          '                    else f"CBC {_EF15_FILE}: 無回應")\n'),
         ''),
        ('            _fail_ev = f"CBC {_EF15_FILE}: 回應不是合法 JSON"\n',
         ''),
        (('            if ef15 is None:     # D3:解析／單位／對帳被拒 ＝ 明確的解析或欄位驗證失敗,拒用原因即證據\n'
          '                _fail_ev = f"CBC {_EF15_FILE}: 解析或驗證被拒：{ef15_desc}"\n'),
         ''),
        ('        return _tag(pd.DataFrame(), _FO.FETCH_FAILED, _fail_ev)\n',
         '        return pd.DataFrame()\n'),
        ('        return _tag(pd.DataFrame(), _FO.UNDETERMINED, f"CBC {_EF15_FILE}: 解析通過但無有效列")\n',
         '        return pd.DataFrame()\n'),
        ('        return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"CBC {_EF15_FILE}: 期間重複,無法對齊 t−12")\n',
         '        return pd.DataFrame()\n'),
        ('    _full = out[["date", "m1b", "m2", "m1b_m2_gap"]].copy()    # D3:窗口前的整張表,只供「窗口內 0 列」時判定正面證據\n',
         ''),
        ('            return _tag(pd.DataFrame(), _FO.FETCH_FAILED, f"CBC {_EF15_FILE}: 寫檔前 sanity 不過：{_msg}")\n',
         '            return pd.DataFrame()\n'),
        (('    else:\n'
          '        # D3:窗口內 0 列。正面證據 = EF15M01 HTTP 200、JSON 可解析、通過單位／對帳解析，且整張表通過同一條 sanity\n'
          '        # (只是沒有落在 [start, end] 的月份)。整張表 sanity 不過 → 證據不足,不標 NO_NEW_DATA。\n'
          '        _ok_full, _msg_full = _m1m2_level_sanity(_full)\n'
          '        if _ok_full:\n'
          '            return _tag(out, _FO.NO_NEW_DATA,\n'
          '                        f"CBC {_EF15_FILE}: 解析與 sanity 通過,請求窗口內無新月份")\n'
          '        return _tag(out, _FO.UNDETERMINED, f"CBC {_EF15_FILE}: 窗口內 0 列,但整張表 sanity 不過：{_msg_full}")\n'),
         ''),
        (('    # D3:本輪遇到的「明確錯誤」證據(HTTP 非 200／JSON 壞／解析不出列／例外);全敗且有任一筆 ⇒ FETCH_FAILED,\n'
          '    # 全敗但只有「200 卻無 resources 清單」這類形狀不明 ⇒ UNDETERMINED。證據不含 URL 以外的變動內容。\n'
          '    _errs: list[str] = []\n'),
         ''),
        (('                _errs.append(f"metadata {\'無回應\' if _r_meta is None else \'HTTP \' + '
          'str(_r_meta.status_code)}")\n'),
         ''),
        ('                _errs.append("metadata 不是合法 JSON")\n',
         ''),
        (('                    _errs.append(f"resource {\'無回應\' if _r_csv is None else \'HTTP \' + '
          'str(_r_csv.status_code)}")\n'),
         ''),
        ('                    _errs.append("resource CSV 解析後無有效列")\n',
         ''),
        (('                if _df.empty:\n'
          '                    # D3:正面證據 = CSV HTTP 200 且整份解析出有效列(PMI ∈ [20, 80])，只是沒有落在 [start, end] 的月份\n'
          '                    return _tag(_df, _FO.NO_NEW_DATA,\n'
          '                                "data.gov.tw 6100: CSV 解析成功,請求窗口內無新月份")\n'),
         ''),
        ('            _errs.append(f"例外 {type(_e_outer).__name__}")\n',
         ''),
        (('    _empty = pd.DataFrame(columns=["date", "pmi"])\n'
          '    if _errs:\n'
          '        return _tag(_empty, _FO.FETCH_FAILED, "data.gov.tw 6100: " + "；".join(dict.fromkeys(_errs)))\n'
          '    return _tag(_empty, _FO.UNDETERMINED, "data.gov.tw 6100: 回應 200 但無可用 resources／url(形狀不明)")\n'),
         '    return pd.DataFrame(columns=["date", "pmi"])\n'),
        (('        # D3:空抓取三態(額外欄,additive;last_error／EMPTY_FETCH_MARKER／last_updated／row_count 一律照舊)。\n'
          '        # 缺 attrs ＝ UNDETERMINED;⛔ 不寫 0、不依 weekday 推論成功。\n'
          '        _oc, _ev = _read_outcome(new)\n'
          '        meta[_META_OUTCOME_KEY] = _oc.value\n'
          '        meta[_META_EVIDENCE_KEY] = _ev\n'),
         ''),
        (('\n'
          '\n'
          '# D3:抓取拋例外／缺 token 跳過這兩條錯誤路徑**刻意不寫** fetch_outcome 欄：它們回傳的 metadata 形狀被\n'
          '# test_d2_update_one_exception_meta、test_dl_f1_r4_batch（整本 dict 相等）釘死，且語意本來就明確 ——\n'
          '# 「有 last_error、不是空抓取標記、沒有 fetch_outcome」＝ 錯誤（讀取端與 publish_data_pr 皆如此判讀，\n'
          '# 即 FETCH_FAILED 的向後相容表示法）。三態欄只在「空抓取」分支寫（update_one），那才是需要分流的地方。\n'),
         ''),
    ),
}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def d3_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`(或 repo 相對路徑)與原始碼,換回 D3 之前的寫法(無 pair 則原樣;只套一次)。"""
    rel = _rel(file_path)
    pairs = D3_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} D3 還原組錨點漂移(各組出現次數 {counts};應全 1 或全 0)—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_d3_revert_is_exact_base_source():
    assert set(D3_REVERT_PAIRS) == set(D3_BASE_SHA)
    for rel in sorted(D3_REVERT_PAIRS):
        code = d3_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == D3_BASE_SHA[rel], rel


def test_d3_revert_is_idempotent():
    for rel in sorted(D3_REVERT_PAIRS):
        once = d3_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert d3_revert_for(rel, once) == once, rel


def test_d3_anchors_present_once_in_current_file_and_never_in_base():
    """每個新片段在現行檔恰 1 次;還原後 0 次 —— 防止還原組變成空轉。"""
    for rel, pairs in D3_REVERT_PAIRS.items():
        cur = (REPO / rel).read_text(encoding="utf-8")
        base = d3_revert_for(rel, cur)
        for new, _old in pairs:
            assert cur.count(new) == 1 and base.count(new) == 0, (rel, new[:60])


def test_d3_revert_removes_every_outcome_marker():
    """自證:還原後的基底碼不含任何 D3 識別字(分類邏輯真的在被還原的區塊內,不是漏掉一塊)。"""
    for rel in D3_REVERT_PAIRS:
        base = d3_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        for tok in ("fetch_outcome", "_FO.", "_tag(", "_read_outcome", "FetchOutcome"):
            assert tok not in base, (rel, tok)
        cur = (REPO / rel).read_text(encoding="utf-8")
        assert "_FO.NO_NEW_DATA" in cur and "_FO.FETCH_FAILED" in cur and "_FO.UNDETERMINED" in cur


def test_chain_head_calls_d3_first():
    """原鏈頭 `p4_revert_for` 必須先呼叫本節,再 D2、再 P4(否則舊批次的基底 sha 守衛看到的是 D3 的新寫法)。"""
    import inspect

    from tests.test_p4_revert_chain import p4_revert_for
    src = inspect.getsource(p4_revert_for)
    assert (src.index("d3_revert_for(file_path, code)")
            < src.index("d2stale_revert_for(file_path, code)")
            < src.index("P4_REVERT_PAIRS.get(rel"))
