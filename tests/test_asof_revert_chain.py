"""tests/test_asof_revert_chain.py — XV-ASOF（價格資料時間＋來源，DEC-102，2026-10-28）的還原鏈新頭節。

為什麼需要：本批改了被舊鏈（`xvext_revert_for` → `xview_revert_for` → `sheet_safety_revert_for` …）以
基底 sha 守衛的檔 ⇒ 在鏈頭**往前接一節**，先把本批改動換回（比照 `xvext_revert_for` 接
`xview_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。`xvext_revert_for` 第一步呼叫本節。

整合（`asof-integrated`）後的串接：本批與 DEC-102 批（`tests/test_dec102_revert_chain.py`）基底同為
`1e603094`、且都動了 `dividend_station_service.py` ⇒ 本表的 pair 換回的目標是「**DEC-102 批頂端**
（`7cb05bab`）的寫法」，再交給 `dec102_revert_for` 換回 `1e603094`。
- `asof_only_revert`：只套本表（`dec102_revert_for` 第一步呼叫它，讓 DEC-102 的 base_module 也正確）；
- `asof_revert_for`：本表 → `dec102_revert_for`，結果 sha ＝ `ASOF_BASE_SHA`（`1e603094`）。
pair 於產生時驗證「套用後逐字等於 `7cb05bab` 的檔、每個新寫法在現行檔恰出現 1 次、套用後 0 次」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

ASOF_BASE_SHA = {'src/services/dividend_station_service.py': '67fdaf7302ec377379fe357ea416fee1a30ed83840f378a3ff60533dd306d1ad',
 'src/ui/views/page_hold.py': '7ad99dca6c8a710beb85d5071736edf0ae06d52ec4a2bd1133538de9bbc7231d',
 'src/ui/views/page_inspect.py': '4a5fe13663cf480854d534f57d8969cf00c83c7fff107e2e724001f1252d8b13'}

ASOF_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/services/dividend_station_service.py': (('from shared import holdings_data_short as HDS\n'
                                               'from shared import price_asof_label as PAL\n'
                                               'from shared.dated_value import coerce_plain_date as '
                                               '_coerce_plain_date\n'
                                               'from shared import dividend_station_thresholds as T\n',
                                               'from shared import holdings_data_short as HDS\n'
                                               'from shared import dividend_station_thresholds as T\n'),
                                              ('            _row["現價"] = float(_cur) if _cur and float(_cur) '
                                               '> 0 else None\n'
                                               '            # XV-ASOF：價格時間＋來源（非顯示鍵，加性；💼 ① E17 '
                                               '位置讀它）。過期價照樣計入上面兩個數字。\n'
                                               '            for _k in PAL.PRICE_ASOF_KEYS:\n'
                                               '                _row[_k] = m.get(_k)\n'
                                               '            if held and not '
                                               'FXG.is_confirmed_twd_ticker(tk):\n',
                                               '            _row["現價"] = float(_cur) if _cur and float(_cur) '
                                               '> 0 else None\n'
                                               '            if held and not '
                                               'FXG.is_confirmed_twd_ticker(tk):\n'),
                                              ('\n'
                                               'def _price_asof_fields(as_of, src, *, ffilled_last: bool = '
                                               'False,\n'
                                               '                       ffilled_from=None) -> dict:\n'
                                               '    """XV-ASOF（客戶 2026-10-28 確認線框 Q1～Q3＝A，DEC-102）：價格的時間＋來源 '
                                               '→ 非顯示鍵。\n'
                                               '\n'
                                               '    **加性**：只多出 `PAL.PRICE_ASOF_KEYS` 這幾個鍵，`current_price` '
                                               '與所有數字一個字都沒動；\n'
                                               '    過期價**照樣**計入市值／損益（是否排除未裁示，本函式只標示）。\n'
                                               '    stale 判定：L0 '
                                               '`PAL.assess_price_freshness`（`expected_latest_trading_day()` '
                                               '＋ freshness SSOT\n'
                                               '    `DAILY_MAX_LAG_TRADING_DAYS`），⛔ 本檔不寫任何天數。\n'
                                               '    「今天」＝台北當日（L3 `trading_calendar_service.taipei_today`，⛔ '
                                               '不用伺服器本地時區）。\n'
                                               '    """\n'
                                               '    from src.services.trading_calendar_service import '
                                               'taipei_today\n'
                                               '    _as_of = _coerce_plain_date(as_of)\n'
                                               '    _ff_from = _coerce_plain_date(ffilled_from)\n'
                                               '    # QA MINOR-6：最後一根是補值 → 「是否最新」以**實際資料日**（補值沿用的那一天）判定。\n'
                                               '    _basis = _ff_from if (ffilled_last and _ff_from is not '
                                               'None) else _as_of\n'
                                               '    _today = taipei_today()\n'
                                               '    _stale, _exp, _lag = PAL.assess_price_freshness(_basis, '
                                               'today=_today)\n'
                                               '    _src = str(src) if src and str(src) in '
                                               'PAL.SOURCE_DISPLAY else None\n'
                                               '    return {PAL.KEY_PRICE_AS_OF: _as_of,\n'
                                               '            PAL.KEY_PRICE_SRC: _src,\n'
                                               '            PAL.KEY_IS_STALE: _stale,\n'
                                               '            PAL.KEY_IS_FALLBACK: '
                                               'PAL.is_fallback_source(_src),\n'
                                               '            PAL.KEY_FFILLED_LAST: bool(ffilled_last),\n'
                                               '            PAL.KEY_FFILLED_FROM: _ff_from,\n'
                                               '            PAL.KEY_PRICE_EXPECTED_DAY: _exp,\n'
                                               '            PAL.KEY_PRICE_LAG_DAYS: _lag,\n'
                                               '            PAL.KEY_PRICE_EVALUATED_ON: _today}\n'
                                               '\n'
                                               '\n'
                                               '#: 拿不到價格時的非顯示鍵（全部 None／False；⛔ 不用今天代替）。\n'
                                               '_PRICE_ASOF_EMPTY: dict = {PAL.KEY_PRICE_AS_OF: None, '
                                               'PAL.KEY_PRICE_SRC: None,\n'
                                               '                           PAL.KEY_IS_STALE: None, '
                                               'PAL.KEY_IS_FALLBACK: None,\n'
                                               '                           PAL.KEY_FFILLED_LAST: False, '
                                               'PAL.KEY_FFILLED_FROM: None,\n'
                                               '                           PAL.KEY_PRICE_EXPECTED_DAY: None, '
                                               'PAL.KEY_PRICE_LAG_DAYS: None,\n'
                                               '                           PAL.KEY_PRICE_EVALUATED_ON: '
                                               'None}\n'
                                               '\n'
                                               '\n'
                                               'def _fetch_stock_metrics(ticker: str, *, failed: dict | None '
                                               '= None) -> dict:\n',
                                               '\n'
                                               'def _fetch_stock_metrics(ticker: str, *, failed: dict | None '
                                               '= None) -> dict:\n'),
                                              ('               "mj_fail_items": [], "kd_state": None, '
                                               '"current_price": None, "name": "",\n'
                                               '               "trend_verdict": None, **_PRICE_ASOF_EMPTY}\n'
                                               '\n',
                                               '               "mj_fail_items": [], "kd_state": None, '
                                               '"current_price": None, "name": "",\n'
                                               '               "trend_verdict": None}\n'
                                               '\n'),
                                              ('                m["current_price"] = '
                                               'float(_ohlc["close"].iloc[-1])\n'
                                               '                # XV-ASOF：同一根 K 的日期 ＋ L1 寫在 attrs '
                                               '的實際成功那一腿（加性，不改現價）。\n'
                                               '                #   ⚠️ 讀 `_df_stk` 原表（`_ohlc` 是子集，同 index），⛔ '
                                               '不另抓一次。\n'
                                               '                if "date" in _df_stk.columns:\n'
                                               '                    try:\n'
                                               '                        m.update(_price_asof_fields(\n'
                                               '                            _df_stk.loc[_ohlc.index[-1], '
                                               '"date"],\n'
                                               '                            getattr(_df_stk, "attrs", '
                                               '{}).get("price_src")))\n'
                                               '                    except Exception as _e_asof:  # noqa: '
                                               'BLE001 — 時間來源算不出 → 照舊 None（不擋現價）\n'
                                               '                        print(f"[dividend_station] {ticker} '
                                               '價格時間來源判定失敗: "\n'
                                               '                              f"{type(_e_asof).__name__}: '
                                               '{_e_asof}")\n'
                                               '                from src.compute.strategy.tech_indicators '
                                               'import (\n',
                                               '                m["current_price"] = '
                                               'float(_ohlc["close"].iloc[-1])\n'
                                               '                from src.compute.strategy.tech_indicators '
                                               'import (\n'),
                                              ('    m["current_price"] = _cur          # #38：供 市值 = 張數×現價 / '
                                               '損益% 計算\n'
                                               '    # XV-ASOF：ETF 固定 Yahoo '
                                               '還原那一腿（`fetch_etf_price`，auto_adjust=True）；\n'
                                               '    #   最後一根是否為 L1 `df.ffill()` 補出來的，讀 L1 既有 attrs（批 Z48），⛔ '
                                               '不另判。\n'
                                               '    m.update(_PRICE_ASOF_EMPTY)\n'
                                               '    try:\n'
                                               '        from src.data.etf.etf_fetch import '
                                               'PRICE_CLOSE_FFILLED_ATTR\n'
                                               '        _ff = set(getattr(_px, "attrs", '
                                               '{}).get(PRICE_CLOSE_FFILLED_ATTR) or ())\n'
                                               '        _last = _close.index[-1]\n'
                                               '        _last_s = pd.Timestamp(_last).strftime("%Y-%m-%d")\n'
                                               '        _ff_last = _last_s in _ff\n'
                                               '        _ff_from = None\n'
                                               '        if _ff_last:\n'
                                               '            _orig = [_i for _i in _close.index\n'
                                               '                     if '
                                               'pd.Timestamp(_i).strftime("%Y-%m-%d") not in _ff and _i < '
                                               '_last]\n'
                                               '            _ff_from = _orig[-1] if _orig else None\n'
                                               '        m.update(_price_asof_fields(_last, '
                                               'PAL.SRC_YAHOO_ADJ,\n'
                                               '                                    ffilled_last=_ff_last, '
                                               'ffilled_from=_ff_from))\n'
                                               '    except Exception as _e_asof:  # noqa: BLE001 — 時間來源算不出 → '
                                               '照舊 None（不擋現價）\n'
                                               '        print(f"[dividend_station] {ticker} 價格時間來源判定失敗: '
                                               '{type(_e_asof).__name__}: {_e_asof}")\n'
                                               '\n',
                                               '    m["current_price"] = _cur          # #38：供 市值 = 張數×現價 / '
                                               '損益% 計算\n'
                                               '\n')),
 'src/ui/views/page_hold.py': (('from shared import ia_nav\n'
                                'from shared import price_asof_label as PAL\n'
                                '# L0 SSOT：燈號規格表（含 `discriminative` 旗標）與缺值原因語彙。\n',
                                'from shared import ia_nav\n'
                                '# L0 SSOT：燈號規格表（含 `discriminative` 旗標）與缺值原因語彙。\n'),
                               ('\n'
                                '#: XV-ASOF（客戶 2026-10-28 Q3＝A，DEC-102）：① 總市值下方既有 E17 位置（A 規格 E17「價格資料日」）。\n'
                                '#: QA M1（2026-10-29）：卡面一格會被截在 `FACT_VALUE_MAX_CHARS` ⇒ '
                                '例外列改成「標籤＝例外字樣、值＝代號清單」，\n'
                                '#: 代號單獨成值（太多時拆多列、⛔ 不截斷代號）；例外一定點名代號（線框 §3.3）。\n'
                                'HOLD_ASOF_GROUP_LABEL_FMT: str = PAL.HOLD_LABEL + " · {label}（{n} 檔）"\n'
                                '#: 同一組代號拆多列時，第二列起的標籤後綴（同一卡內多一列 fact，⛔ 不新增卡片／區塊）。\n'
                                'HOLD_ASOF_CONT_SUFFIX: str = "（續）"\n'
                                '#: 多數那一列的標籤（值＝多數字樣）。\n'
                                'HOLD_ASOF_MAJOR_LABEL_FMT: str = PAL.HOLD_LABEL + "（{n} 檔）"\n'
                                '#: 沒有過半的那一種（各檔不一致）→ 第一列只講這句，下面逐組列出（QA MINOR-3：中性，⛔ 不寫「另 N 檔」）。\n'
                                'HOLD_ASOF_NO_MAJORITY: str = "各檔不一致，逐組列在下面"\n'
                                '#: ⑤ 衛星停利卡只加一行指回 ①（線框 §3.4；⛔ 不逐列加）。\n'
                                'TP_ASOF_FACT_KEY: str = "價格時間"\n'
                                'TP_ASOF_POINTER: str = f"損益% 以現價計；價格時間見上方「{PAL.HOLD_LABEL}」"\n'
                                '\n'
                                '\n'
                                'def _hold_asof_items(station: StationReadout):\n'
                                '    """① E17 與 ⑤ 指回共用的列：**與總市值同一個範圍**（QA MINOR-2）。\n'
                                '\n'
                                '    逐列條件照抄 L3 `compute_portfolio_totals()` 的納入條件：持有、非整批抓取失敗、無資料異常\n'
                                '    （`KEY_INVALID_INPUTS`）、張數／均價／現價三者皆 > 0；另排除外幣／幣別未確認列\n'
                                '    （`KEY_FX_UNCONFIRMED`，XV-H3：它們不進總市值）。⛔ 本頁不另立判準。\n'
                                '    `None` ＝ 戰情表沒有列（idle／空清單）→ 兩處都不畫。分組與「多數」一律走 L0（嚴格過半）。\n'
                                '    ⚠️ 過期價**照樣**計入市值／損益（是否排除未裁示，線框 §6）—— 這裡只標示。\n'
                                '    """\n'
                                '    if not station.has_rows:\n'
                                '        return None\n'
                                '    return tuple(\n'
                                '        (str(_r.get("代號", "")), PAL.PriceAsOf.from_mapping(_r)) for _r in '
                                'station.rows\n'
                                '        if _r.get("held") and not (_r.get("_detail") or {}).get("error")\n'
                                '        and not _r.get(KEY_INVALID_INPUTS) and not '
                                '_r.get(KEY_FX_UNCONFIRMED)\n'
                                '        and all(isinstance(_r.get(_k), (int, float)) and not '
                                'isinstance(_r.get(_k), bool)\n'
                                '                and _r.get(_k) > 0 for _k in ("張數", "均價", "現價")))\n'
                                '\n'
                                '\n'
                                'def _code_rows(label: str, codes) -> list[tuple[str, str]]:\n'
                                '    """一組代號 → 一列或多列（值 ≤ 卡面上限，⛔ 不截斷代號）。"""\n'
                                '    _chunks = PAL.chunk_codes(codes)\n'
                                '    return [(label + (HOLD_ASOF_CONT_SUFFIX if _i else ""), _c) for _i, _c '
                                'in enumerate(_chunks)]\n'
                                '\n'
                                '\n'
                                'def _price_asof_facts(station: StationReadout) -> list[tuple[str, str]]:\n'
                                '    """① 總市值下方 E17：`價格資料時間（N 檔）｜{多數字樣}`；有例外才多列（標籤＝字樣、值＝代號）。"""\n'
                                '    _items = _hold_asof_items(station)\n'
                                '    if _items is None:\n'
                                '        return []\n'
                                '    if not _items:\n'
                                '        return [(PAL.HOLD_LABEL, PAL.HOLD_NOT_PROVIDED)]\n'
                                '    _by_label = {PAL.price_asof_label(_p): PAL.hold_face_label(_p) for _, '
                                '_p in _items}\n'
                                '    _g = PAL.group_price_asof(_items)\n'
                                '    if _g.majority_label is not None:\n'
                                '        _major = next(_k for _l, _k in _g.groups if _l == '
                                '_g.majority_label)\n'
                                '        _out = [(HOLD_ASOF_MAJOR_LABEL_FMT.format(n=len(_major)), '
                                '_by_label[_g.majority_label])]\n'
                                '    else:\n'
                                '        _out = [(PAL.HOLD_LABEL, HOLD_ASOF_NO_MAJORITY)]\n'
                                '    for _lbl, _codes in _g.exceptions:\n'
                                '        _out += '
                                '_code_rows(HOLD_ASOF_GROUP_LABEL_FMT.format(label=_by_label[_lbl], '
                                'n=len(_codes)),\n'
                                '                           _codes)\n'
                                '    # 線框 §5：既有「▸ 詳細」摺疊區補兩格價格說明（`V2_FOLD_ONLY_FACT_KEYS` 登記，⛔ 不上卡面、不新增區塊）。\n'
                                '    _out.extend(PAL.price_basis_facts_many([_p for _, _p in _items]))\n'
                                '    return _out\n'
                                '\n'
                                '\n'
                                'def _take_profit_asof_fact(station: StationReadout, *, state: str) -> '
                                'list[tuple[str, str]]:\n'
                                '    """⑤ 衛星停利卡那一行指回 ①（QA MINOR-4：只算 ⑤ 管的衛星個股；無衛星或紅態不出）。"""\n'
                                '    if state == UI_FAILED:\n'
                                '        return []\n'
                                '    _items = _hold_asof_items(station)\n'
                                '    if not _items:\n'
                                '        return []\n'
                                '    _sat = {str(_r.get("代號", "")) for _r in station.rows\n'
                                '            if _r.get("held") and _r.get("種類") == "個股"}\n'
                                '    if not any(_c in _sat for _c, _ in _items):\n'
                                '        return []\n'
                                '    _g = PAL.group_price_asof(_items)\n'
                                '    _exc_labels = {_l for _l, _ in _g.exceptions}\n'
                                '    _exc = [_p for _c, _p in _items if _c in _sat and '
                                'PAL.price_asof_label(_p) in _exc_labels]\n'
                                '    _stale_n = sum(1 for _p in _exc if _p.is_stale is True)\n'
                                '    # QA r2：兩位數檔數時仍須 ≤ 卡面上限 ⇒ 混合時縮成「（例外 14 檔，⚠ 11 檔）」（代號已在 ① 點名）。\n'
                                '    if _exc and _stale_n:\n'
                                '        _tail = (f"（{PAL.STALE_MARK} {_stale_n} 檔已點名）" if _stale_n == '
                                'len(_exc)\n'
                                '                 else f"（例外 {len(_exc)} 檔，⚠ {_stale_n} 檔）")\n'
                                '    elif _exc:\n'
                                '        _tail = f"（例外 {len(_exc)} 檔已點名）"\n'
                                '    else:\n'
                                '        _tail = ""\n'
                                '    return [(TP_ASOF_FACT_KEY, TP_ASOF_POINTER + _tail)]\n'
                                '\n'
                                '\n'
                                'def build_action_card(station: StationReadout) -> _Built:\n',
                                '\ndef build_action_card(station: StationReadout) -> _Built:\n'),
                               ('    _facts += _totals_facts(station)\n'
                                '    _facts += _price_asof_facts(station)     # XV-ASOF：E17 位置（總市值下方）\n'
                                '    if station.err_n:\n',
                                '    _facts += _totals_facts(station)\n    if station.err_n:\n'),
                               ('    ]\n'
                                '    _facts += _take_profit_asof_fact(station, state=_state)   # '
                                'XV-ASOF：只加一行指回 ①（線框 §3.4）\n'
                                '    if station.take_profit and not station.error:\n',
                                '    ]\n    if station.take_profit and not station.error:\n'),
                               ('                                    RISK_CAP_DISABLED_LABEL, '
                                'RISK_CAP_SAHM_LABEL}),\n'
                                '    # XV-ASOF（線框 §5）：① 該做什麼卡的價格「查看依據」兩格只進詳細。\n'
                                '    CONCLUSION_ACTION_KEY: frozenset({PAL.BASIS_USED_LABEL, '
                                'PAL.BASIS_DATE_LABEL}),\n'
                                '}\n',
                                '                                    RISK_CAP_DISABLED_LABEL, '
                                'RISK_CAP_SAHM_LABEL}),\n'
                                '}\n')),
 'src/ui/views/page_inspect.py': (('from shared import ia_nav\n'
                                   'from shared import price_asof_label as PAL\n'
                                   '# L0：要畫上畫面的上游例外字串，先洗掉金鑰／Sheet ID／檔案路徑（SEC-2，2026-09-26；\n',
                                   'from shared import ia_nav\n'
                                   '# L0：要畫上畫面的上游例外字串，先洗掉金鑰／Sheet ID／檔案路徑（SEC-2，2026-09-26；\n'),
                                  ('    price_error: str = ""\n'
                                   '    #: XV-ASOF（DEC-102）：同一輪 `fetch_metrics` 帶回的價格時間＋來源（L3 非顯示鍵的唯讀視圖）。\n'
                                   '    #: `None` ＝ 這一輪沒有價格；有價格但 L3 給不出時間 → 欄位全 None（卡上寫「⬜ 未提供」）。\n'
                                   '    price_asof: PAL.PriceAsOf | None = None\n'
                                   '\n',
                                   '    price_error: str = ""\n\n'),
                                  ('            price=_num(_m.get("current_price")),\n'
                                   '            health_error=_health_err, price_error=_price_err,\n'
                                   '            price_asof=PAL.PriceAsOf.from_mapping(_m))\n'
                                   '    _trend = _m.get("trend_verdict")\n',
                                   '            price=_num(_m.get("current_price")),\n'
                                   '            health_error=_health_err, price_error=_price_err)\n'
                                   '    _trend = _m.get("trend_verdict")\n'),
                                  ('        price=_num(_m.get("current_price")),\n'
                                   '        price_error=_price_err,\n'
                                   '        price_asof=PAL.PriceAsOf.from_mapping(_m))\n'
                                   '\n',
                                   '        price=_num(_m.get("current_price")),\n'
                                   '        price_error=_price_err)\n'
                                   '\n'),
                                  ('    invalid_items: tuple[str, ...] = ()\n'
                                   '    #: XV-ASOF：沿用健康度那一輪的同一份時間來源（⛔ 不重抓；卡上寫「同上」）。\n'
                                   '    price_asof: PAL.PriceAsOf | None = None\n'
                                   '\n',
                                   '    invalid_items: tuple[str, ...] = ()\n\n'),
                                  ('        return ValuationReadout(\n'
                                   '            requested=True, price=stock.price, '
                                   'price_asof=stock.price_asof,\n'
                                   '            error=_error_why(SRC_DIVIDENDS, repr(_e)))\n',
                                   '        return ValuationReadout(\n'
                                   '            requested=True, price=stock.price,\n'
                                   '            error=_error_why(SRC_DIVIDENDS, repr(_e)))\n'),
                                  ('        return ValuationReadout(\n'
                                   '            requested=True, price=stock.price, '
                                   'price_asof=stock.price_asof,\n'
                                   '            source=_div.source,\n'
                                   '            years_n=len(_div.years), invalid_items=("配息",))\n',
                                   '        return ValuationReadout(\n'
                                   '            requested=True, price=stock.price, source=_div.source,\n'
                                   '            years_n=len(_div.years), invalid_items=("配息",))\n'),
                                  ('        return ValuationReadout(\n'
                                   '            requested=True, price=stock.price, '
                                   'price_asof=stock.price_asof,\n'
                                   '            avg_div_twd=_div.avg_div_twd, '
                                   'paying_years=_div.paying_years,\n',
                                   '        return ValuationReadout(\n'
                                   '            requested=True, price=stock.price,\n'
                                   '            avg_div_twd=_div.avg_div_twd, '
                                   'paying_years=_div.paying_years,\n'),
                                  ('        avg_div_twd=_div.avg_div_twd, paying_years=_div.paying_years,\n'
                                   '        source=_div.source, years_n=len(_div.years), price=stock.price,\n'
                                   '        price_asof=stock.price_asof)\n'
                                   '\n',
                                   '        avg_div_twd=_div.avg_div_twd, paying_years=_div.paying_years,\n'
                                   '        source=_div.source, years_n=len(_div.years), price=stock.price)\n'
                                   '\n'),
                                  ('    error: str = ""\n'
                                   '    #: XV-ASOF：這一列現價的時間＋來源（`None` ＝ 這一列沒有現價可標）。\n'
                                   '    price_asof: PAL.PriceAsOf | None = None\n'
                                   '\n',
                                   '    error: str = ""\n\n'),
                                  ('                ("籌碼", "未接線"),\n'
                                   '            ),\n'
                                   '            price_asof=(PAL.PriceAsOf.from_mapping(_m)\n'
                                   '                        if _num(_m.get("current_price")) is not None '
                                   'else None))\n'
                                   '\n',
                                   '                ("籌碼", "未接線"),\n            ))\n\n'),
                                  ('            ("基準", str(_bench or "—")),\n'
                                   '        ),\n'
                                   '        price_asof=(PAL.PriceAsOf.from_mapping(_m)\n'
                                   '                    if _num(_m.get("current_price")) is not None else '
                                   'None))\n'
                                   '\n',
                                   '            ("基準", str(_bench or "—")),\n        ))\n\n'),
                                  ('    return BatchReadout(requested=True, rows=_rows)\n'
                                   '\n'
                                   '\n'
                                   '#: XV-ASOF：價格時間那一行在 fact 列的標籤（P1 健康度、P2 估值共用）。\n'
                                   'PRICE_ASOF_FACT_KEY: str = "現價資料時間｜來源"\n'
                                   '#: P2 估值卡：357 沿用健康度那一輪同一個價（線框 §3.2「同上」）—— 接在標籤後面。\n'
                                   'PRICE_ASOF_SAME_AS_ABOVE: str = "（同上）"\n'
                                   '#: 葉2 批次表頭下一行（線框 §4 方案 A；客戶 Q1＝A）。\n'
                                   'BATCH_ASOF_PREFIX: str = "價格資料時間："\n'
                                   'BATCH_ASOF_EXCEPTION_TAIL: str = "\u3000—\u3000例外列已在明細標示"\n'
                                   '#: 各列不一致到沒有多數 → 退回逐列寫法（線框 §4 風險欄）。\n'
                                   'BATCH_ASOF_NO_MAJORITY: str = "價格資料時間：各列不一致，逐列標示在明細"\n'
                                   '\n'
                                   '\n'
                                   '@dataclass(frozen=True)\n'
                                   'class BatchAsOfView:\n'
                                   '    """葉2 批次表的價格時間呈現（純資料；`_render_batch_leaf()` 照畫）。\n'
                                   '\n'
                                   '    Attributes:\n'
                                   '        header: 表頭下一行；`""` ＝ 這一批沒有任何一列有現價（不畫）。\n'
                                   '        suffix: 與 `rows` 同序；`""` ＝ 這一列不加字（屬於多數組、或沒有現價）。\n'
                                   '    """\n'
                                   '\n'
                                   '    header: str = ""\n'
                                   '    suffix: tuple[str, ...] = ()\n'
                                   '\n'
                                   '\n'
                                   'def batch_price_asof_view(rows: Sequence[BatchRow]) -> BatchAsOfView:\n'
                                   '    """方案 A：多數組寫在表頭下一行，只有例外列在「明細」加字；沒有過半 → 每列都寫（方案 B 寫法）。\n'
                                   '\n'
                                   '    分組與「多數」的判定一律走 L0 `PAL.group_price_asof()`（嚴格過半），本檔不另判。\n'
                                   '    只有「算出來、且有現價」的列參與（失敗／判不出型別的列沒有價格可標）。\n'
                                   '    """\n'
                                   '    _items = tuple((_i, _r.price_asof) for _i, _r in enumerate(rows)\n'
                                   '                   if _r.ok and not _r.is_unknown and _r.price_asof is '
                                   'not None)\n'
                                   '    if not _items:\n'
                                   '        return BatchAsOfView(header="", suffix=tuple("" for _ in rows))\n'
                                   '    _g = PAL.group_price_asof(_items)\n'
                                   '    if _g.majority_label is None:\n'
                                   '        _header = BATCH_ASOF_NO_MAJORITY\n'
                                   '    else:\n'
                                   '        _header = (BATCH_ASOF_PREFIX + _g.majority_label\n'
                                   '                   + (BATCH_ASOF_EXCEPTION_TAIL if _g.exceptions else '
                                   '""))\n'
                                   '    _suffix = []\n'
                                   '    for _i in range(len(rows)):\n'
                                   '        _lbl = _g.label_of(_i)\n'
                                   '        _suffix.append("" if _lbl is None or _lbl == _g.majority_label '
                                   'else f"（{_lbl}）")\n'
                                   '    return BatchAsOfView(header=_header, suffix=tuple(_suffix))\n'
                                   '\n'
                                   '\n'
                                   'def batch_detail_metrics(row: BatchRow, suffix: str) -> tuple[tuple[str, '
                                   'str], ...]:\n'
                                   '    """一列的明細 `(欄位, 值)`；有例外字樣時接在「現價」那一格後面（⛔ 不新增欄位）。"""\n'
                                   '    if not suffix:\n'
                                   '        return row.metrics\n'
                                   '    return tuple((_k, _v + suffix if _k == "現價" else _v) for _k, _v in '
                                   'row.metrics)\n'
                                   '\n',
                                   '    return BatchReadout(requested=True, rows=_rows)\n\n'),
                                  ('        _facts.append(("現價", _fmt_num(stock.price, digits=2)))\n'
                                   '        # XV-ASOF（線框 §3.1）：現價下面一行小字 ＝ 資料時間＋來源（字樣全走 L0，顏色不承載意思）。\n'
                                   '        _facts.append((PRICE_ASOF_FACT_KEY, '
                                   'PAL.price_asof_label(stock.price_asof)))\n'
                                   '        # 線框 §5：完整說明只進「▸ 詳細」摺疊區（`V2_FOLD_ONLY_FACT_KEYS`），⛔ 不上卡面。\n'
                                   '        _facts.extend(PAL.price_basis_facts(stock.price_asof))\n'
                                   '    if stock.headline:\n',
                                   '        _facts.append(("現價", _fmt_num(stock.price, digits=2)))\n'
                                   '    if stock.headline:\n'),
                                  ('    ]\n'
                                   '    if val.price is not None:\n'
                                   '        # XV-ASOF（線框 §3.2）：357 用的是健康度那一輪同一個價 ⇒ 寫「同上」＋同一份時間來源。\n'
                                   '        # QA M1：「同上」寫在標籤上（值＝同一份字樣，⛔ 不加前綴 —— 卡面一格有長度上限）。\n'
                                   '        _facts.append((PRICE_ASOF_FACT_KEY + PRICE_ASOF_SAME_AS_ABOVE,\n'
                                   '                       PAL.price_asof_label(val.price_asof)))\n'
                                   '    if val.msg:\n',
                                   '    ]\n    if val.msg:\n'),
                                  ('            "被截掉的那幾檔**沒有查過**，請分批再貼一次"))\n'
                                   '    _priced = [_r.price_asof for _r in readout.rows\n'
                                   '               if _r.ok and not _r.is_unknown and _r.price_asof is not '
                                   'None]\n'
                                   '    if _priced:\n'
                                   '        # XV-ASOF（線框 §5）：既有「▸ 詳細」摺疊區補兩格價格說明（只進摺疊區，⛔ 不新增區塊）。\n'
                                   '        _facts.extend(PAL.price_basis_facts_many(_priced))\n'
                                   '    if readout.failed_codes:\n',
                                   '            "被截掉的那幾檔**沒有查過**，請分批再貼一次"))\n    if readout.failed_codes:\n'),
                                  ('\n'
                                   '#: 只進「▸ 詳細」摺疊區的 fact 標籤（XV-ASOF 線框 §5「查看依據」：價格完整說明 ⛔ 不上 Level 1）。\n'
                                   'V2_FOLD_ONLY_FACT_KEYS: frozenset[str] = frozenset(_k for _k, _ in '
                                   'PAL.price_basis_facts(None))\n'
                                   '\n'
                                   '\n'
                                   'def v2_card_html(card: Card, facts: Sequence[tuple[str, str]] = (),\n',
                                   '\ndef v2_card_html(card: Card, facts: Sequence[tuple[str, str]] = (),\n'),
                                  ('    _short, _full = v2_short_rows(card)\n'
                                   '    # XV-ASOF（線框 §5）：「查看依據」那幾格只進摺疊區、⛔ 不上卡面。\n'
                                   '    _fold_only = tuple((v2_plain(_k), v2_plain(_v)) for _k, _v in facts\n'
                                   '                       if _k in V2_FOLD_ONLY_FACT_KEYS)\n'
                                   '    facts = tuple(_f for _f in facts if _f[0] not in '
                                   'V2_FOLD_ONLY_FACT_KEYS)\n'
                                   '    _plain_facts = tuple((v2_plain(_k), v2_plain(_v)) for _k, _v in '
                                   'facts)\n',
                                   '    _short, _full = v2_short_rows(card)\n'
                                   '    _plain_facts = tuple((v2_plain(_k), v2_plain(_v)) for _k, _v in '
                                   'facts)\n'),
                                  ('                  if _r != _f or len(_r[1]) > '
                                   'v2_markup.FACT_VALUE_MAX_CHARS)\n'
                                   '    _folded = tuple(_full) + _long + _fold_only\n'
                                   '    return v2_markup.card_html(\n',
                                   '                  if _r != _f or len(_r[1]) > '
                                   'v2_markup.FACT_VALUE_MAX_CHARS)\n'
                                   '    _folded = tuple(_full) + _long\n'
                                   '    return v2_markup.card_html(\n'),
                                  ('    #    **重疊近零**，硬併成一張寬表會有一半的格子永遠是空的。────────────\n'
                                   '    # XV-ASOF（線框 §4 方案 A；客戶 Q1＝A）：表頭下一行共同時間，例外列在明細標示。\n'
                                   '    _asof = batch_price_asof_view(_rows)\n'
                                   '    if _asof.header:\n'
                                   '        st.caption(_asof.header)\n'
                                   '    st.dataframe(\n',
                                   '    #    **重疊近零**，硬併成一張寬表會有一半的格子永遠是空的。────────────\n    st.dataframe(\n'),
                                  ('          "明細": (scrub_state_glyphs(scrub_secrets(_r.error))[0] if not '
                                   '_r.ok else\n'
                                   '                   " · ".join(f"{_k}：{_v}" for _k, _v in '
                                   'batch_detail_metrics(_r, _sfx))\n'
                                   '                   or "（此型別不取數）")}\n'
                                   '         for _r, _sfx in zip(_rows, _asof.suffix)],\n'
                                   '        hide_index=True, width="stretch")\n',
                                   '          "明細": (scrub_state_glyphs(scrub_secrets(_r.error))[0] if not '
                                   '_r.ok else\n'
                                   '                   " · ".join(f"{_k}：{_v}" for _k, _v in _r.metrics)\n'
                                   '                   or "（此型別不取數）")}\n'
                                   '         for _r in _rows],\n'
                                   '        hide_index=True, width="stretch")\n'),
                                  ('                   "顯示的是上面那一輪批次已經算完的同一份結果。")\n'
                                   '    _drill_sfx = next((_s for _r2, _s in zip(_rows, _asof.suffix) if _r2 '
                                   'is _row), "")\n'
                                   '    for _chunk, _columns in grid(batch_detail_metrics(_row, _drill_sfx), '
                                   'MAX_COLS):\n'
                                   '        for (_k, _v), _col in zip(_chunk, _columns):\n',
                                   '                   "顯示的是上面那一輪批次已經算完的同一份結果。")\n'
                                   '    for _chunk, _columns in grid(_row.metrics, MAX_COLS):\n'
                                   '        for (_k, _v), _col in zip(_chunk, _columns):\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def asof_only_revert(file_path, code: str) -> str:
    """只換回 XV-ASOF 本表的改動（不碰 DEC-102 那批）。無 pair 則原樣；只套一次。"""
    rel = _rel(file_path)
    pairs = ASOF_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} XV-ASOF 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def asof_revert_for(file_path, code: str) -> str:
    """換回 XV-ASOF ＋ DEC-102 兩批 ⇒ `1e603094` 的寫法（無 pair 則原樣；只套一次）。"""
    from tests.test_dec102_revert_chain import dec102_revert_for
    return dec102_revert_for(file_path, asof_only_revert(file_path, code))


def test_asof_revert_is_exact_base_source():
    assert set(ASOF_REVERT_PAIRS) == set(ASOF_BASE_SHA)
    for rel in sorted(ASOF_REVERT_PAIRS):
        code = asof_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == ASOF_BASE_SHA[rel], rel


def test_asof_revert_is_idempotent():
    for rel in sorted(ASOF_REVERT_PAIRS):
        once = asof_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert asof_revert_for(rel, once) == once, rel


def test_chain_head_calls_asof_first():
    """原鏈頭 `xvext_revert_for` 必須先呼叫本節；`dec102_revert_for` 第一步必須先套本表。"""
    import inspect

    from tests.test_dec102_revert_chain import dec102_revert_for
    from tests.test_xvext_revert_chain import xvext_revert_for
    src = inspect.getsource(xvext_revert_for)
    assert src.index("asof_revert_for(rel, code)") < src.index("XVEXT_REVERT_PAIRS.get(rel")
    d = inspect.getsource(dec102_revert_for)
    assert d.index("asof_only_revert(rel, code)") < d.index("DEC102_REVERT_PAIRS.get(rel")
