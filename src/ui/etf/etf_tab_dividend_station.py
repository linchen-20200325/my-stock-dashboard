"""L5 UI — 💼 我的持股戰情室（個股 + ETF 統一分析,掛在 🏦 ETF）。

定位：**持股 Sheet 綁定** → 定期健檢 → AI 總結（可推播）。
- 標的**唯一來源 = 📁 組合管理**（投資組合 Portfolio + 觀察清單 Watchlist）,進頁自動載入、**唯讀不可改**;
  無手動輸入代號的入口（§ user 2026-08：單一來源、去凌亂）。
- 戰情表**分兩區**（§ user 2026-08）：
  · 🛡️ 定期定額策略（ETF）→ 健檢 A/B/C/D + 235 加碼燈 + 3-3-3；
  · 🚀 個股汰換（衛星）→ 財報體檢（grade）+ KD → 是否更換（財報為主、KD 為時機輔證）。
- 🤖 AI 戰情總結：先出規則式事實（汰弱 / 235 加碼 / 抓取失敗）,有金鑰再 AI 潤成推播文字。

- 🔎 逐盞燈明細：燈格牆 + **選列就地展開**（`st.dataframe(on_select)` + 分欄面板）。
  ⚠️ 刻意**不用** `st.expander` / 巢狀 `st.tabs` 裝明細 —— 兩者的 body 每次 app run
  都會執行（收合只是前端），把 N 檔 × 12 盞燈塞進去就是 STATE.md v19.132 產業熱力圖
  那個坑的另一個入口。渲染下放 L4 `render.station_cards`（L5 → L4 為合法方向,
  **不需**新增 §8.2.A 例外）。

§8.2 L5：只呼叫 L3 `dividend_station_service`,不自算。§1：抓取失敗逐列誠實標記,不炸整表;
抓取 button-gated（不每次 rerun 重抓）。個股不套 235/3-3-3（ETF/基金規則）,資料不足標「資料不足」不猜。
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from src.ui.render.station_cards import CSS as _LIGHT_CSS
from src.ui.render.station_cards import (
    aggregate_judged,
    cruise_or_gap,
    is_fully_judged,
    judged_count,
    render_conclusion_card,
    render_credibility_card,
    render_holding_detail,
    render_legend,
    render_light_wall,
    render_todo_card,
    render_two_scales,
    tally_states,
)

# 戰情表分兩區（§ user 2026-08）：ETF 走定期定額 235/3-3-3、個股走 財報體檢 + KD。
_ETF_COLS = ["代號", "名稱", "張數", "均價", "現價", "損益%", "市值",
             "健檢", "235 燈號", "加碼金", "3-3-3", "建議動作"]
_STOCK_COLS = ["代號", "名稱", "張數", "均價", "現價", "損益%", "市值",
               "財報體檢", "財報趨勢", "KD", "建議動作"]  # B3:加財報趨勢欄


def _perf_row(r: dict, cols: list[str]) -> dict:
    """依欄位序取值;績效欄(張數/均價/現價/損益%/市值)格式化,缺 → 「—」(§1 不捏 0)。

    市值(萬) = 張數 × 現價 × 1000股/張 ÷ 1e4 = 張數 × 現價 ÷ 10（service 的「市值」欄
    是張×現價、供 80/20 比例用不含 ×1000,顯示絕對值須自算含股數）。
    """
    _lots = r.get("張數")
    _cur = r.get("現價")
    _out: dict = {}
    for _c in cols:
        if _c == "張數":
            _out[_c] = f"{_lots:g}" if isinstance(_lots, (int, float)) else "—"
        elif _c == "均價":
            _a = r.get("均價")
            _out[_c] = f"{_a:.2f}" if isinstance(_a, (int, float)) else "—"
        elif _c == "現價":
            _out[_c] = f"{_cur:.2f}" if isinstance(_cur, (int, float)) else "—"
        elif _c == "損益%":
            _p = r.get("損益%")
            _out[_c] = f"{_p:+.1f}%" if isinstance(_p, (int, float)) else "—"
        elif _c == "市值":
            _out[_c] = (f"{_lots * _cur / 10:,.1f}萬"
                        if isinstance(_lots, (int, float)) and isinstance(_cur, (int, float))
                        else "—")
        else:
            _out[_c] = r.get(_c, "")
    return _out
_HOLDINGS_KEY = "_station_holdings"


def _style_rows(df):
    """健檢/財報體檢/建議 有 🔴/🟡 → 背景高亮（紅/琥珀）。"""
    def _bg(val):
        s = str(val)
        if "🔴" in s:
            return "background-color:#3d1418"
        if "🟡" in s:
            return "background-color:#3a3416"
        return ""
    return df.style.map(_bg, subset=[c for c in ("健檢", "財報體檢", "建議動作")
                                     if c in df.columns])


def _safe_dataframe(styled, plain) -> None:
    """Styler 相容性問題退無樣式,不炸（§1）。"""
    try:
        st.dataframe(styled, use_container_width=True, hide_index=True)
    except Exception:  # noqa: BLE001 — Styler 相容性退無樣式
        st.dataframe(plain, use_container_width=True, hide_index=True)


def _holding_preview_row(h: dict) -> dict:
    """service 持股 dict → 唯讀預覽列（含張數/均價;現價/績效在下方戰情表,需跑計算才有）。

    ⚠️ 「種類」走 L0 `T.normalize_asset_kind`,**與下方戰情表同一把尺**
    （L3 `build_station_rows` 用的是同一支）。2026-08-26 前這裡讀的是原始
    `h["asset_kind"]` —— 髒值（`"ETF"` 大寫 / `None`）會讓同一頁出現兩個
    對不起來的「種類」欄:預覽表寫 ETF、戰情表卻走個股路徑。
    今天兩個持股產出端都已先分類故不可達,但同一個問題不留兩份答案（§2.1 SSOT）。
    """
    _lots = h.get("lots")
    _avg = h.get("avg_price")
    _kind = T.normalize_asset_kind(h.get("asset_kind"), h.get("ticker", ""))
    return {
        "代號": h.get("ticker", ""),
        "名稱": h.get("name", ""),
        "種類": "個股" if _kind == T.KIND_STOCK else "ETF",
        "類別": "🚀 衛星" if h.get("asset_class") == T.ASSET_SATELLITE else "🛡️ 核心",
        # 張數/均價來自持股 Sheet(觀察清單無金額 → —);現價/報酬在下方戰情表(跑計算後)。
        "張數": f"{float(_lots):g}" if _lots else "—",
        "均價": f"{float(_avg):.2f}" if _avg else "—",
    }


def render_dividend_station(gemini_fn: Callable[..., str] | None = None) -> None:
    import pandas as pd

    st.markdown("### 💼 我的持股戰情室 — 定期健檢 · 235 加碼 · AI 總結")
    st.caption("標的**唯一來源 = 📁 組合管理**（投資組合 Portfolio + 觀察清單 Watchlist）,自動載入、唯讀。"
               "戰情表分兩區：**ETF**＝定期定額（健檢 A/B/C/D＋235 加碼＋3-3-3）;**個股**＝汰換"
               "（財報體檢 grade＋KD → 是否更換）。AI 幫你濃縮成「今天要不要動作」;資料不足標「資料不足」不猜（§1）。")

    # ── 1️⃣ 我的持股（唯讀,自動載入自持股 Sheet）─────────────────────────
    if _HOLDINGS_KEY not in st.session_state:
        st.session_state[_HOLDINGS_KEY] = _load_holdings_from_portfolio()
    _c_reload, _c_hint = st.columns([1, 4])
    with _c_reload:
        if st.button("🔄 重新載入", key="_station_reload", help="重抓 📁 組合管理的持股清單"):
            try:   # 手動刷新 → 清 L1 讀取快取,繞過 TTL 抓最新(§1 使用者要的是即時)
                from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1
                _gsp.clear_read_cache()
            except Exception:  # noqa: BLE001 — 清快取失敗不該擋重載
                pass
            st.session_state[_HOLDINGS_KEY] = _load_holdings_from_portfolio()
            st.session_state.pop("_station_rows", None)
            st.session_state.pop("_station_vix", None)
            st.session_state.pop("_station_ai_text", None)
            st.rerun()
    _holdings = st.session_state.get(_HOLDINGS_KEY) or []
    # P1 v19.202(user 指派「輸入持股組合分析全移到戰情室」):把 📁 組合管理載入的持股
    # 轉成 etf_portfolio_rows 契約寫入 session → 下游 葡萄串 / 標準差·分散度·3-3-3 selectbox /
    # portfolio_linkage / tab_sector_flow 直接吃真實持股,不再靠 ETF 組合頁的手打範例列。
    # 只在產出真實持有列時才覆寫(觀察清單候選/缺張數均價會被 §1 跳過,不拿空清單清掉既有)。
    try:
        from src.services.portfolio_analysis_bridge import (
            build_portfolio_rows_from_holdings,
        )
        _pf_bridge = build_portfolio_rows_from_holdings(_holdings)
        if _pf_bridge.rows:
            st.session_state['etf_portfolio_rows'] = list(_pf_bridge.rows)
    except Exception as _e_pf_bridge:  # noqa: BLE001 — 橋接失敗不擋戰情室渲染
        print(f'[station portfolio bridge] {type(_e_pf_bridge).__name__}: {_e_pf_bridge}')
    if not _holdings:
        with _c_hint:
            st.caption("尚未載入到持股。")
        # P1 v19.205(順暢化):把原本「請先到 📁 組合管理…」的死路指路牌,改成**就地**三態綁定
        # —— 使用者不必離開本頁去別的分頁找設定(解 user 反映的順序痛點)。
        #   ⚪ 未登入      → 就地 Google 登入 CTA(portfolio_binder)
        #   🟡 已登入未綁  → 就地 Drive 挑選器 + 貼網址/ID
        #   🟢 已綁但空表  → 誠實提示去 📁 組合管理 補持股(§1 三態不混:綁定 ≠ 有資料)
        _sid_bound = ""
        try:
            from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1
            _sid_bound = _gsp._get_active_sheet_id()
        except Exception as _e_gsp:  # noqa: BLE001 — 綁定狀態讀取失敗不擋渲染(§1 誠實印 log)
            print(f"[station empty-state] {type(_e_gsp).__name__}: {_e_gsp}")
            _gsp = None
        if _sid_bound:
            st.info("✅ 已綁定持股 Sheet,但目前讀不到任何持股列 —— 可能是空表或尚未填寫。"
                    "到 **📁 組合管理** 新增「投資組合 Portfolio」/「觀察清單 Watchlist」後,"
                    "按上方「🔄 重新載入」。")
        elif _gsp is not None:
            from src.ui.tabs.portfolio_binder import render_holdings_binder
            render_holdings_binder(_gsp, key_prefix="_station_")
    else:
        with _c_hint:
            st.caption(f"共 **{len(_holdings)}** 檔（來源：持股 Sheet,唯讀;要改請到 📁 組合管理）。")
        st.dataframe(pd.DataFrame([_holding_preview_row(h) for h in _holdings]),
                     use_container_width=True, hide_index=True)

    # ── 2️⃣ 執行 ────────────────────────────────────────────────────────
    if st.button("🚀 跑存股戰情室", type="primary", key="_station_run"):
        if not _holdings:
            st.warning("清單是空的,請先載入持股。")
        else:
            try:
                from src.services.dividend_station_service import get_station_rows
                with st.spinner("戰情室運算中：抓 VIX + 逐檔週K / 折溢價 …"):
                    _rows, _vix = get_station_rows(_holdings)
                st.session_state["_station_rows"] = _rows
                st.session_state["_station_vix"] = _vix
                st.session_state.pop("_station_ai_text", None)   # 重跑 → 清舊 AI 摘要
                # 換股建議(總經位階 + 選股池候選)—— best-effort,失敗不擋戰情表(§1 誠實標)
                try:
                    from src.services.dividend_station_service import (
                        build_switch_advice, get_station_macro, get_switch_in_candidates)
                    _macro = get_station_macro()
                    _held = [h["ticker"] for h in _holdings if h.get("held")]
                    with st.spinner("換股建議：讀總經位階 + 選股池候選 …"):
                        _cands = get_switch_in_candidates(regime=_macro.get("regime"),
                                                          exclude=_held)
                    st.session_state["_station_switch"] = build_switch_advice(
                        _rows, _macro, _cands)
                except Exception as _se:  # noqa: BLE001 — 換股建議失敗不擋戰情表
                    st.session_state["_station_switch"] = None
                    st.caption(f"（換股建議暫略：{type(_se).__name__}: {_se}）")
            except Exception as _e:  # noqa: BLE001 — 整批失敗誠實報,不假裝成功
                st.error(f"戰情室運算失敗（Fail Loud）：{type(_e).__name__}: {_e}")

    # ── 3️⃣ 結果 ────────────────────────────────────────────────────────
    _rows = st.session_state.get("_station_rows")
    if not _rows:
        st.info("👆 按「🚀 跑存股戰情室」。台股 ETF 折溢價 / 週K 需部署端網路。")
        return

    _vix = st.session_state.get("_station_vix")

    # ── 1️⃣ 結論（階段 C）：三張卡放在所有細節之前 ──────────────────────
    st.markdown(_LIGHT_CSS, unsafe_allow_html=True)   # 卡片與燈格共用同一份 CSS
    _render_layer1(_rows, _vix)

    _vix_txt = f"{_vix:.1f}" if isinstance(_vix, (int, float)) else "抓取失敗（235 的 VIX 條件本次不觸發）"
    st.markdown(f"#### 3️⃣ 戰情表　·　VIX：**{_vix_txt}**")

    # 分兩區呈現（§ user 2026-08）：ETF＝定期定額策略、個股＝汰換判斷。
    _etf_rows = [r for r in _rows if r.get("種類") != "個股"]
    _stock_rows = [r for r in _rows if r.get("種類") == "個股"]

    if _etf_rows:
        st.markdown("##### 🛡️ 定期定額策略（ETF）　·　235 加碼燈 ＋ 3-3-3")
        _edf = pd.DataFrame([_perf_row(r, _ETF_COLS) for r in _etf_rows])
        _safe_dataframe(_style_rows(_edf), _edf)
    if _stock_rows:
        st.markdown("##### 🚀 個股汰換（衛星）　·　財報體檢 ＋ KD → 是否更換")
        st.caption("個股不套 235/3-3-3（那是 ETF 定期定額規則）。**財報 grade 決定汰弱、KD 定進出時機**："
                   "財報 C/F → 建議換出;KD 死亡交叉/頂背離＝賣點確認、黃金交叉/底背離＝轉強留。")
        _sdf = pd.DataFrame([_perf_row(r, _STOCK_COLS) for r in _stock_rows])
        _safe_dataframe(_style_rows(_sdf), _sdf)
    if not _etf_rows and not _stock_rows:
        st.info("無可顯示的持股列。")

    # ── 📊 80/20 實際配置偏離 + 衛星停利（#38,有張數/均價才算）─────────────
    _render_allocation_take_profit(_rows)

    # ── 2️⃣ 同一個名詞，兩套刻度（階段 C；純揭露，不改任何判定）────────────
    render_two_scales()

    _render_light_detail(_rows)

    # ── 4️⃣ 換股建議（換出=持有🔴汰弱 · 換入=選股池候選 · 搭配總經位階）──────
    _switch = st.session_state.get("_station_switch")
    _render_switch_advice(_switch)

    # ── 5️⃣ 📊 組合深度分析（P2b v19.202:從 ETF 多檔比較搬入戰情室）──────────────
    # user 指派「輸入持股組合的分析全移到戰情室」:再平衡 / 核衛 80-20 / 壓測 / VaR /
    # 效率前緣 / 配息日曆×現金流 / 稅後(組合)+ 葡萄串領息法,改在此處呈現。輸入已由
    # P2a 自動帶入 📁 組合管理真實持股(不再手打範例列)。各區 try/except 隔離,任一
    # raise 不吃掉後面(同 app.py _render_tab_isolated 精神,§1 Fail Loud)。
    with st.expander("5️⃣ 📊 組合深度分析（再平衡 / 核衛 / 壓測 / VaR / 配息現金流 / 葡萄串領息）",
                     expanded=False):
        st.caption("標的＝📁 組合管理載入的持股（上方已自動帶入,不必再手打範例列）。")
        try:
            from src.ui.etf.etf_tab_portfolio import render_etf_portfolio
            render_etf_portfolio(gemini_fn=gemini_fn)
        except Exception as _e_pf:  # noqa: BLE001 — §1 單區失敗不吃掉後面
            st.error(f"組合深度分析載入失敗（Fail Loud）：{type(_e_pf).__name__}: {_e_pf}")
        st.markdown('<hr style="margin:24px 0;border-color:#30363d;">', unsafe_allow_html=True)
        try:
            from src.ui.tabs.grape_ladder import render_grape_ladder
            render_grape_ladder(gemini_fn=gemini_fn)
        except Exception as _e_gl:  # noqa: BLE001
            st.error(f"葡萄串領息法載入失敗（Fail Loud）：{type(_e_gl).__name__}: {_e_gl}")

    # ── 6️⃣ AI 戰情總結（規則事實 always;AI 潤稿需金鑰;含換股建議）──────────
    _render_ai_summary(_rows, _vix, gemini_fn, _switch)

    st.caption(f"💡 目標配置：🛡️核心 {T.CORE_TARGET_PCT:.0f}% / 🚀衛星 {T.SATELLITE_TARGET_PCT:.0f}%；"
               f"衛星獲利達 {T.SATELLITE_TAKE_PROFIT_PCT:.0f}% 嚴格停利、滾回核心。"
               "本區僅研究參考,非投資建議,盈虧自負。")


# ══════════════════════════════════════════════════════════════════════
# 第 1 層 —— 結論（階段 C）
# ══════════════════════════════════════════════════════════════════════
#
# ⚠️ **一個新判斷都沒有（防呆 4）。** 三張卡把**上游已經算好的結論**排版出來:
#   · 該換掉 / 該加碼的檔數 ← L3 `build_station_digest` 的 `reds` / `adds`
#     （**與 LINE 每日推播吃的是同一支函式、同一組定義** —— 不另立一套「紅燈」）
#   · 未實現損益 / 總市值   ← L3 `compute_portfolio_totals`（純乘加，張→股走 SSOT）
#   · N/M 盞給得出判定      ← L4 `judged_count`（純計數，不看市場）
#
# ⚠️ **巡航 gate 做在這一層（防呆 2）。** L2 `dividend_station.suggest_action`
#    一個字都沒動 —— 它同時餵著主表「建議動作」欄與
#    `scripts/push_holdings_daily.py` 的 LINE 推播，在那裡加 gate 是行為變更。


def _render_layer1(rows: list[dict], vix) -> None:
    """1️⃣ 結論 —— 三張卡（該做什麼 / 訊號可信度 / 需要處理的檔數）。"""
    from src.services.dividend_station_service import (
        build_station_digest,
        compute_portfolio_totals,
    )

    _rows = list(rows or [])
    _digest = build_station_digest(_rows, vix)
    _cut_n = len(_digest.get("reds") or [])
    _add_n = len(_digest.get("adds") or [])
    _err_n = len(_digest.get("errors") or [])

    _cells = [r.get("_lights") or () for r in _rows]
    _has_lights = any(_cells)
    _judged, _total_lights = aggregate_judged(_cells)
    _tally = tally_states(_cells)
    # 「這一列每盞適用燈都給得出判定嗎」—— 抓取失敗的列 `missing_light_cells`
    # 會回滿滿一列 missing,自然落在 False,不必另外判 error(§1 不重寫同一個判斷)。
    _unjudged_n = sum(1 for _c in _cells if not is_fully_judged(_c))
    _all_judged = bool(_cells) and _unjudged_n == 0

    # 一句話。有東西要看就直接列出來（**不排優先序** —— 兩件事同時成立時
    # 兩個都講，不由這一層決定誰比較重要）；都沒有才輪到巡航 gate。
    _parts = []
    if _cut_n:
        _parts.append(f"{_cut_n} 檔亮汰弱紅燈")
    if _add_n:
        _parts.append(f"{_add_n} 檔亮加碼燈")
    _headline = ("今天要看的：" + "、".join(_parts) if _parts
                 else cruise_or_gap(_judged, _total_lights, all_rows_judged=_all_judged))

    # 金額。§1：算不出來就不放這個數字，**不填 0**。
    _totals = compute_portfolio_totals(_rows)
    _figs: list[tuple[str, str]] = [(f"{len(_rows)}", "檔數")]
    _note = ""
    if _totals:
        _figs.insert(0, (f"{_totals['pnl_twd']:+,.0f}",
                         f"未實現損益（元）{_totals['pnl_pct']:+.1f}%"))
        _figs.append((f"{_totals['value_twd']:,.0f}", "總市值（元）"))
        if _totals["partial"]:
            _note = (f"⚠️ {_totals['held_n'] - _totals['valued_n']}/{_totals['held_n']} 檔"
                     f"持股缺張數或均價，**沒有**納入損益與市值 —— 上面兩個金額只涵蓋"
                     f"其餘 {_totals['valued_n']} 檔。到 📁 組合管理補齊即可。")
    else:
        _note = ("未實現損益與總市值算不出來：持股沒有張數／均價／現價。"
                 "§1 這裡**不填 0** —— 到 📁 組合管理的 Portfolio 補齊才會出現。")
    if _err_n:
        _note += f"{'　' if _note else ''}⚠️ 另有 {_err_n} 檔整批抓取失敗，未納入任何判斷。"

    st.markdown("#### 1️⃣ 結論")
    _c1, _c2, _c3 = st.columns([5, 4, 3], gap="medium")
    with _c1:
        render_conclusion_card(headline=_headline, figures=_figs, note=_note)
    with _c2:
        if _has_lights:
            render_credibility_card(_judged, _total_lights, _tally)
        else:
            # 舊版執行結果留在 session（沒有 `_lights` 這個鍵）→ 不畫 0/0 假裝算過。
            st.info("這份結果是舊版執行留下的，算不出訊號可信度 —— "
                    "請重按「🚀 跑存股戰情室」。")
    with _c3:
        render_todo_card(add_n=_add_n, cut_n=_cut_n, unjudged_n=_unjudged_n)


#: 規格表 key → 這盞燈的「值」寫在 row 的 `_detail` 哪個欄位。
#:
#: 這是**呈現對應**(哪一段文字要印在哪一盞燈底下),故住 L5 —— row dict 的形狀由 L3
#: 決定,而只有本檔在讀它。L4 只收 `{key: 文字}` 不認得任何欄名(它不該知道 row 長怎樣)。
#:
#: ⚠️ **3-3-3 三個子項刻意不在這張表裡。** `_detail["3-3-3明細"]` 是三項併成的
#:    一句話(「成立✅　3年報酬✅　同儕前1/3❔」),要拆回三份得解析字串 —— L2 已經
#:    明說過那樣太脆弱(改一個字就壞,而且不會有任何錯誤)。故三個子項的「值」顯示
#:    「—」,由判定符號 + 門檻自己講清楚,**不猜**(§1);合併那句話改印在「其他明細」。
_LIGHT_VALUE_DETAIL_KEY: dict[str, str] = {
    SS.KEY_HEALTH_A: "健檢A",
    SS.KEY_HEALTH_B: "健檢B",
    SS.KEY_HEALTH_C: "健檢C",
    SS.KEY_HEALTH_D: "健檢D",
    SS.KEY_LIGHT235: "235觸發",
    SS.KEY_STOCK_HEALTH: "財報總評",
    SS.KEY_STOCK_TREND: "財報趨勢",
    SS.KEY_STOCK_KD: "KD明細",
}

#: 汰換建議那盞燈的「值」不在 `_detail`,而是主表的「建議動作」欄。
_LIGHT_VALUE_ROW_COL: dict[str, str] = {SS.KEY_STOCK_SWAP: "建議動作"}

#: `_detail` 裡**不屬於任何一盞燈**的補充欄。舊版「🔎 逐檔明細」expander 有印這些,
#: 換成選列展開後不能弄丟(§1 改呈現不等於可以少講事情)。順序即畫面順序。
_EXTRA_DETAIL_KEYS: tuple[str, ...] = (
    "3-3-3明細", "深水防守", "ETF品質", "財報弱項", "KD交叉",
)


def _light_value_texts(r: dict) -> dict[str, str]:
    """row → `{規格表 key: 這盞燈實際算出什麼}`。查無對應就不放進去(L4 顯示「—」)。"""
    _d = r.get("_detail") or {}
    _out: dict[str, str] = {}
    for _k, _col in _LIGHT_VALUE_DETAIL_KEY.items():
        _v = str(_d.get(_col) or "").strip()
        if _v:
            _out[_k] = _v
    for _k, _col in _LIGHT_VALUE_ROW_COL.items():
        _v = str(r.get(_col) or "").strip()
        if _v:
            _out[_k] = _v
    return _out


def _render_light_detail(rows: list[dict]) -> None:
    """逐盞燈明細 —— 燈格牆 + **選列就地展開**(取代原本的逐檔明細 expander)。

    ## 為什麼不是 expander / 巢狀 tabs

    `st.tabs()` 會執行**所有** tab body、`st.expander` 的 body 同樣每次 app run 都跑
    (收合只是前端)。把 N 檔 × 12 盞燈塞進每列一個 expander,就是 STATE.md v19.132
    產業熱力圖那個坑的另一個入口。這裡採 `st.dataframe(on_select="rerun")` +
    `st.columns` —— **只渲染被選中那一列**的明細,與總經 v2 第 3 層同一套做法
    (全 repo 目前只有那一處與本處用 `on_select`)。

    燈格牆本身是一次 `st.markdown` 的純 HTML,零 widget、零額外執行成本。
    """
    _rows = list(rows or [])
    if not _rows:
        return

    st.markdown(_LIGHT_CSS, unsafe_allow_html=True)
    st.markdown("##### 🔎 逐盞燈明細　·　點左表任一列,右側就地展開")

    if not any(r.get("_lights") for r in _rows):
        # 舊版執行結果留在 session 裡(沒有 `_lights` 這個鍵)。§1:不畫空格子假裝有燈。
        st.info("這份結果是舊版執行留下的,沒有逐盞燈資料 —— 請重按「🚀 跑存股戰情室」。")
        return

    st.caption(
        "**填色＝這盞燈自己的判定**、**外框／紋理＝這盞燈可不可信**(四態)。兩件事分開看:"
        "一盞「亮著綠燈但其實沒有資料」的燈,填色會是灰的、而且帶斜紋。"
        "⚠️ 235 加碼燈的紅／黃／綠是**跌多深、該加多少碼**,不是體質好壞 —— "
        "它的 🔴 是「崩盤／深水加碼」訊號。點進去每一盞燈都會寫明白。"
        "　「有判定」的分母**比格子數少**是正常的:還沒有判燈規則的燈(個股 KD)"
        "不算進分母 —— 點進去會寫明理由。"
    )
    render_legend()

    render_light_wall([
        (str(r.get("代號", "")), str(r.get("名稱", "")), r.get("_lights") or ())
        for r in _rows
    ])

    _tbl, _panel = st.columns([7, 5], gap="medium")
    with _tbl:
        # 「有判定」與燈格牆、與第 1 層結論卡**同一把尺**(`judged_count`)——
        # 三處印同一件事,不准有三個數字(user 2026-08-26 裁示)。
        # 原本這裡用寬鬆的 `watch_count`(只看四態 live),2330 在同一頁會出現
        # 第 1 層 2/4、這裡 3/4 兩個數字。
        _n_m = [judged_count(r.get("_lights") or ()) for r in _rows]
        _sel = st.dataframe(
            {
                "代號": [str(r.get("代號", "")) for r in _rows],
                "名稱": [str(r.get("名稱", "")) for r in _rows],
                "種類": [str(r.get("種類", "")) for r in _rows],
                "健檢": [str(r.get("健檢", "")) for r in _rows],
                "有判定": [f"{_n}/{_m}" for _n, _m in _n_m],
            },
            hide_index=True, width="stretch",
            on_select="rerun", selection_mode="single-row",
            key="_station_light_table",
        )

    with _panel, st.container(border=True):
        _idxs = (_sel.selection.rows if _sel and getattr(_sel, "selection", None)
                 else [])
        if _idxs and 0 <= _idxs[0] < len(_rows):
            _r = _rows[_idxs[0]]
            _d = _r.get("_detail") or {}
            render_holding_detail(
                str(_r.get("代號", "")), str(_r.get("名稱", "")),
                _r.get("_lights") or (),
                value_texts=_light_value_texts(_r),
                error=str(_d.get("error") or ""))
            _extra = [(_k, str(_d.get(_k) or "").strip())
                      for _k in _EXTRA_DETAIL_KEYS]
            _extra = [(_k, _v) for _k, _v in _extra if _v]
            if _extra:
                st.markdown("**其他明細**")
                for _k, _v in _extra:
                    st.caption(f"{_k}：{_v}")
        else:
            st.markdown("#### 點左表任一列")
            st.caption(
                "右側會就地展開那一檔的**每一盞燈**:判定是什麼意思(依該盞燈自己那把尺)、"
                "這盞燈可不可信、實際算出什麼值、門檻、來源、以及沒資料時**為什麼**沒資料"
                "(全部讀自 SSOT 規格表,不是這裡編的)。"
            )


def _render_allocation_take_profit(rows: list[dict]) -> None:
    """📊 80/20 實際配置偏離 + 衛星停利（有張數/均價才算;§1 缺金額誠實標,不捏造）。"""
    from src.services.dividend_station_service import (
        compute_allocation_split, flag_take_profit)
    _alloc = compute_allocation_split(rows)
    _tp = flag_take_profit(rows)

    if _alloc:
        _dev = _alloc["core_dev"]
        _msg = (f"📊 **實際配置**：🛡️核心 {_alloc['core_pct']:.0f}% / 🚀衛星 {_alloc['sat_pct']:.0f}%"
                f"　·　目標 {_alloc['core_target']:.0f}/{_alloc['sat_target']:.0f}"
                f"　·　核心偏離 **{_dev:+.0f}%**")
        if abs(_dev) < 5:
            st.success(_msg + "（接近目標）")
        elif _dev < 0:
            st.warning(_msg + "（核心偏低 → 可加碼核心）")
        else:
            st.warning(_msg + "（核心偏高 → 衛星部位不足）")
        _note = "核心=ETF、衛星=個股（依代號近似;若你把主題型 ETF 當衛星,此偏離僅供參考）。"
        if _alloc.get("partial"):
            _note += (f"　⚠️ 另有 {_alloc['held_n'] - _alloc['valued_n']}/{_alloc['held_n']} 檔"
                      "缺張數/均價未納入計算。")
        st.caption(_note)
    else:
        st.caption("📊 80/20 配置偏離：你的持股未帶張數/均價（或無市值）→ 無法計算實際佔比。"
                   "到 📁 組合管理的 Portfolio 填張數/均價即可顯示。")

    if _tp:
        st.info(f"💰 **衛星停利**（獲利達 {T.SATELLITE_TAKE_PROFIT_PCT:.0f}% 建議嚴格停利、滾回核心）："
                + "、".join(f"{d['代號']}（+{d['損益%']:.0f}%）" for d in _tp))


def _render_switch_advice(switch: dict | None) -> None:
    """🔄 換股建議：換出=持有🔴汰弱、換入=選股池候選,搭配總經位階攻守（§1 位階未評估誠實標）。"""
    st.markdown("#### 4️⃣ 🔄 換股建議（搭配總經位階）")
    if not switch:
        st.info("👆 按「🚀 跑存股戰情室」後產生換股建議（讀總經位階 + 選股池候選）。")
        return

    # 位階 / 攻守姿態
    if switch.get("loaded"):
        _p = switch.get("posture") or "—"
        _rng = f"（建議持股 {switch['posture_range']}）" if switch.get("posture_range") else ""
        st.caption(f"當前總經位階：**{switch.get('regime')}** ｜ 姿態 **{_p}**{_rng}")
    else:
        st.caption("當前總經位階：**未評估** —— 只依個股健檢給汰弱,不套總經攻守（§1 不瞎猜方向）。"
                   "要有位階請先到「🌍 市場環境」按一鍵更新。")

    _out = switch.get("switch_out") or []
    _in = switch.get("switch_in") or []
    _stance = switch.get("stance")

    if _out:
        st.error("🔻 **建議換出（你持有的紅燈汰弱）**：" + "、".join(
            f"{d['代號']}（{d['建議動作']}）" for d in _out))
    else:
        st.success("✅ 持有部位無健檢紅燈 —— 無汰弱換出需求。")

    _src = switch.get("switch_in_src", "screener")
    _src_txt = "你的觀察清單" if _src == "watchlist" else "選股池(全自動排名)"
    if _stance == "defensive":
        st.warning("🛡️ 總經轉守 → **換入從嚴**：優先處理汰弱、不急進場;下列候選僅供轉守後布局參考。")
    if _in:
        _label = (f"🔺 **建議換入（{_src_txt}）**：" if _stance != "defensive"
                  else f"候選（{_src_txt}·轉守觀望）：")
        st.markdown(_label + "、".join(
            f"{d['代號']} {d.get('名稱','')}".strip()
            + (f"（綜合分 {d['綜合分']:.0f}）" if isinstance(d.get('綜合分'), (int, float)) else "")
            for d in _in))
    else:
        st.caption("暫無可換入候選（觀察清單無綠燈、選股池也未跑 / 皆已持有）。")
    st.caption(f"換出=你**持有**的紅燈;換入**優先**你觀察清單的綠燈(親手選的),空才用選股池"
               f"全自動排名。本次換入來源：**{_src_txt}**。研究參考,非投資建議。")


def _render_ai_summary(rows: list[dict], vix, gemini_fn: Callable[..., str] | None,
                       switch: dict | None = None) -> None:
    """🤖 AI 戰情總結：先出規則式事實（汰弱 / 235 加碼 / 抓取失敗 / 換股）,有金鑰再 AI 潤稿。

    §1：規則事實由 L3 `build_station_digest` 純函式算,永遠有;AI 只潤稿,失敗誠實報錯不假裝。
    """
    from src.services.dividend_station_service import build_ai_summary, build_station_digest

    st.markdown("#### 5️⃣ 🤖 AI 戰情總結（可作推播內容）")
    digest = build_station_digest(rows, vix)

    if digest["reds"]:
        st.error("🔴 **汰弱警訊**：" + "、".join(
            f"{d['代號']}（{d['建議動作']}）" for d in digest["reds"]))
    if digest["adds"]:
        st.warning("🚦 **235 加碼觸發**：" + "、".join(
            f"{d['代號']} {d['235']}｜加碼 {d['加碼金']}" for d in digest["adds"]))
    if not digest["reds"] and not digest["adds"]:
        st.success("✅ 今日無汰弱紅燈、無 235 加碼觸發 —— 續抱、定期定額即可。")
    if digest["errors"]:
        st.caption(f"⚠️ {len(digest['errors'])} 檔抓取失敗未納入判斷（§1 誠實排除）："
                   + "、".join(digest["errors"]))

    if gemini_fn is None:
        st.caption("（未接 AI 金鑰,以上為規則式摘要;此摘要即為推播內容來源。）")
        return

    if st.button("✍️ 讓 AI 潤成推播文字", key="_station_ai"):
        try:
            with st.spinner("AI 撰寫推播摘要中 …"):
                st.session_state["_station_ai_text"] = build_ai_summary(
                    digest, gemini_fn, switch=switch)
        except Exception as _e:  # noqa: BLE001 — §1 AI 失敗誠實報,不回假摘要
            st.error(f"AI 摘要失敗（Fail Loud）：{type(_e).__name__}: {_e}")
    _ai = st.session_state.get("_station_ai_text")
    if _ai:
        st.info(_ai)


def _load_holdings_from_portfolio() -> list[dict]:
    """從 📁 組合管理帶入 投資組合 Portfolio（held=True/核心）+ 觀察清單 Watchlist（held=False/衛星）。

    種類（ETF/個股）改由 `T.classify_asset_kind(代號)` 依代號規則判,跟在哪個清單脫鉤（§ user）。

    回 service 格式 [{ticker,name,asset_class,asset_kind}, ...]。
    best-effort：任一份讀不到就略過該份;兩份都空 → 提示 + [] （未登入/未設）。§1 不靜默。
    """
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1
    except Exception as _e:  # noqa: BLE001
        st.caption(f"（持股 Sheet 元件載入失敗：{type(_e).__name__}）")
        return []

    _out: list[dict] = []
    # 投資組合 Portfolio（種類=ETF,預設核心）
    try:
        _etf_sid = _gsp._get_active_sheet_id()
    except Exception as _e:  # noqa: BLE001 — §1 不靜默:accessor 理應回 '' 不 raise,真炸也留痕
        _etf_sid = None
        st.caption(f"（投資組合 Portfolio Sheet 判定略過：{type(_e).__name__}：{_e}）")
    if _etf_sid:
        try:
            _names = _gsp.list_portfolios(sheet_id=_etf_sid)
            if _names:
                _n0 = len(_out)
                for _r in (_gsp.load_portfolio(_names[0], sheet_id=_etf_sid) or []):
                    _c = str(_r.get("ticker", "") or "").strip().upper()
                    if _c:
                        _kind = T.classify_asset_kind(_c)
                        # held=True(持有);種類+類別依代號自動判(郭俊宏:核心=配息ETF/衛星=成長股
                        #   → 以 ETF/個股 近似);保留張數/均價供 80/20 偏離 + 衛星停利(#38)。
                        _out.append({
                            "ticker": _c, "name": "", "held": True,
                            "asset_kind": _kind,
                            "asset_class": (T.ASSET_CORE if _kind == T.KIND_ETF
                                            else T.ASSET_SATELLITE),
                            "lots": _r.get("lots"), "avg_price": _r.get("avg_price")})
                _more = "；此 Sheet 有多本組合,只取第一本" if len(_names) > 1 else ""
                st.caption(f"✅ 帶入 投資組合 Portfolio「{_names[0]}」（{len(_out) - _n0} 檔）{_more}")
        except Exception as _e:  # noqa: BLE001 — §1 讀取失敗要看得見,不被誤當「沒持股」
            st.warning(f"投資組合 Portfolio讀取失敗：{type(_e).__name__}：{_e}")
    # 觀察清單 Watchlist（種類=個股,預設衛星）
    try:
        _stk_sid = _gsp._get_active_stock_sheet_id()
    except Exception as _e:  # noqa: BLE001 — §1 不靜默:同上,真炸也留痕
        _stk_sid = None
        st.caption(f"（觀察清單 Watchlist Sheet 判定略過：{type(_e).__name__}：{_e}）")
    if _stk_sid:
        try:
            _snames = _gsp.list_stock_watchlists(sheet_id=_stk_sid)
            if _snames:
                _n0 = len(_out)
                for _c in (_gsp.load_stock_watchlist(_snames[0], sheet_id=_stk_sid) or []):
                    _c = str(_c or "").strip().upper()
                    if _c:
                        _kind = T.classify_asset_kind(_c)
                        # held=False(僅觀察,無金額);類別同以 ETF=核心/個股=衛星判(一致)。
                        _out.append({
                            "ticker": _c, "name": "", "held": False,
                            "asset_kind": _kind,
                            "asset_class": (T.ASSET_CORE if _kind == T.KIND_ETF
                                            else T.ASSET_SATELLITE),
                            "lots": None, "avg_price": None})
                _more = "；此 Sheet 有多份清單,只取第一份" if len(_snames) > 1 else ""
                st.caption(f"✅ 帶入 觀察清單 Watchlist「{_snames[0]}」（{len(_out) - _n0} 檔）{_more}")
        except Exception as _e:  # noqa: BLE001 — §1 讀取失敗要看得見,不被誤當「沒持股」
            st.warning(f"觀察清單 Watchlist讀取失敗：{type(_e).__name__}：{_e}")

    # 補中文名（ETF→fetch_etf_zh_name、個股→get_stock_name;§1 抓不到留空不捏造）。
    # 讓預覽表 + 戰情表兩處都顯示名稱（原本兩處 name 都寫死空字串）。best-effort。
    try:
        from src.services.dividend_station_service import resolve_holding_names
        resolve_holding_names(_out)
    except Exception as _e:  # noqa: BLE001 — 名稱解析失敗不擋載入
        st.caption(f"（名稱解析略過：{type(_e).__name__}）")

    return _out
