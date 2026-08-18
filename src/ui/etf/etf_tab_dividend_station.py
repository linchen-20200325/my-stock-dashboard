"""L5 UI — 💼 我的持股戰情室（個股 + ETF 統一分析,掛在 🏦 ETF）。

定位：**持股 Sheet 綁定** → 定期健檢 → AI 總結（可推播）。
- 標的**唯一來源 = 📁 組合管理**（投資組合 Portfolio + 觀察清單 Watchlist）,進頁自動載入、**唯讀不可改**;
  無手動輸入代號的入口（§ user 2026-08：單一來源、去凌亂）。
- 逐檔（個股+ETF）跑健檢 + 235 燈 + 3-3-3,顏色高亮。
- 🤖 AI 戰情總結：先出規則式事實（汰弱 / 235 加碼 / 抓取失敗）,有金鑰再 AI 潤成推播文字。

§8.2 L5：只呼叫 L3 `dividend_station_service`,不自算。§1：抓取失敗逐列誠實標記,不炸整表;
抓取 button-gated（不每次 rerun 重抓）。個股：D折溢價 / 3-3-3 標「—」不適用(§1 不硬套 ETF 規則)。
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from shared import dividend_station_thresholds as T

_MAIN_COLS = ["代號", "名稱", "種類", "類別", "健檢", "235 燈號", "加碼金", "3-3-3", "建議動作"]
_HOLDINGS_KEY = "_station_holdings"


def _style_rows(df):
    """健檢/建議 有 🔴/🟡 → 背景高亮（紅/琥珀）。"""
    def _bg(val):
        s = str(val)
        if "🔴" in s:
            return "background-color:#3d1418"
        if "🟡" in s:
            return "background-color:#3a3416"
        return ""
    return df.style.map(_bg, subset=[c for c in ("健檢", "建議動作") if c in df.columns])


def _holding_preview_row(h: dict) -> dict:
    """service 持股 dict → 唯讀預覽列。"""
    return {
        "代號": h.get("ticker", ""),
        "名稱": h.get("name", ""),
        "種類": "個股" if h.get("asset_kind") == T.KIND_STOCK else "ETF",
        "類別": "🚀 衛星" if h.get("asset_class") == T.ASSET_SATELLITE else "🛡️ 核心",
    }


def render_dividend_station(gemini_fn: Callable[..., str] | None = None) -> None:
    import pandas as pd

    st.markdown("### 💼 我的持股戰情室 — 定期健檢 · 235 加碼 · AI 總結")
    st.caption("標的**唯一來源 = 📁 組合管理**（投資組合 Portfolio + 觀察清單 Watchlist）,自動載入、唯讀。逐檔看健檢"
               "（A賺息賠本／B夏普／C季線轉弱／D高溢價）＋235 加碼燈,AI 幫你濃縮成「今天要不要動作」。"
               "個股：D折溢價／3-3-3 標「—」不適用;資料不足標「不判定」不猜（§1）。")

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
    if not _holdings:
        with _c_hint:
            st.caption("尚未載入到持股。")
        st.warning("尚未載入到持股 —— 請先到 **📁 組合管理** 選定 Sheet 並存「投資組合 Portfolio」/「觀察清單 Watchlist」,"
                   "再回來按「🔄 重新載入」。")
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
    _vix_txt = f"{_vix:.1f}" if isinstance(_vix, (int, float)) else "抓取失敗（235 的 VIX 條件本次不觸發）"
    st.markdown(f"#### 3️⃣ 戰情表　·　VIX：**{_vix_txt}**")

    _df = pd.DataFrame([{c: r.get(c, "") for c in _MAIN_COLS} for r in _rows])
    try:
        st.dataframe(_style_rows(_df), use_container_width=True, hide_index=True)
    except Exception:  # noqa: BLE001 — Styler 相容性問題退無樣式,不炸
        st.dataframe(_df, use_container_width=True, hide_index=True)

    # 逐檔明細
    with st.expander("🔎 逐檔明細（健檢 A/B/C/D · 235 觸發 · 3-3-3）", expanded=False):
        for r in _rows:
            d = r.get("_detail", {})
            if d.get("error"):
                st.markdown(f"**{r['代號']} {r.get('名稱','')}** — ⚠️ {d['error']}")
                continue
            st.markdown(f"**{r['代號']} {r.get('名稱','')}**　{r.get('235 燈號','')}　"
                        f"3-3-3：{d.get('3-3-3明細','')}")
            st.caption(f"A：{d.get('健檢A','')}　｜　B：{d.get('健檢B','')}")
            st.caption(f"C：{d.get('健檢C','')}　｜　D：{d.get('健檢D','')}")
            if d.get("235觸發"):
                st.caption(f"235 觸發：{d['235觸發']}　深水：{d.get('深水防守','—')}")
            st.markdown("---")

    # ── 4️⃣ 換股建議（換出=持有🔴汰弱 · 換入=選股池候選 · 搭配總經位階）──────
    _switch = st.session_state.get("_station_switch")
    _render_switch_advice(_switch)

    # ── 5️⃣ AI 戰情總結（規則事實 always;AI 潤稿需金鑰;含換股建議）──────────
    _render_ai_summary(_rows, _vix, gemini_fn, _switch)

    st.caption(f"💡 目標配置：🛡️核心 {T.CORE_TARGET_PCT:.0f}% / 🚀衛星 {T.SATELLITE_TARGET_PCT:.0f}%；"
               f"衛星獲利達 {T.SATELLITE_TAKE_PROFIT_PCT:.0f}% 嚴格停利、滾回核心。"
               "本區僅研究參考,非投資建議,盈虧自負。")


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

    if _stance == "defensive":
        st.warning("🛡️ 總經轉守 → **換入從嚴**：優先處理汰弱、不急進場;下列候選僅供轉守後布局參考。")
    if _in:
        _label = "🔺 **建議換入（選股池候選）**：" if _stance != "defensive" else "候選（轉守觀望）："
        st.markdown(_label + "、".join(
            f"{d['代號']} {d.get('名稱','')}".strip()
            + (f"（綜合分 {d['綜合分']:.0f}）" if isinstance(d.get('綜合分'), (int, float)) else "")
            for d in _in))
    else:
        st.caption("選股池暫無可換入候選（未跑選股 / 掃描失敗 / 皆已持有）。")
    st.caption("換出=你**持有**的紅燈;換入=**選股池**排名候選（已排除已持有）。研究參考,非投資建議。")


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
                        # held=True(持有);種類改代號規則自動判(跟清單脫鉤,§ user 2026-08)
                        _out.append({"ticker": _c, "name": "", "held": True,
                                     "asset_kind": T.classify_asset_kind(_c),
                                     "asset_class": T.ASSET_CORE})
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
                        # held=False(僅觀察);種類改代號規則自動判(觀察 ETF 不會被誤標個股)
                        _out.append({"ticker": _c, "name": "", "held": False,
                                     "asset_kind": T.classify_asset_kind(_c),
                                     "asset_class": T.ASSET_SATELLITE})
                _more = "；此 Sheet 有多份清單,只取第一份" if len(_snames) > 1 else ""
                st.caption(f"✅ 帶入 觀察清單 Watchlist「{_snames[0]}」（{len(_out) - _n0} 檔）{_more}")
        except Exception as _e:  # noqa: BLE001 — §1 讀取失敗要看得見,不被誤當「沒持股」
            st.warning(f"觀察清單 Watchlist讀取失敗：{type(_e).__name__}：{_e}")

    return _out
