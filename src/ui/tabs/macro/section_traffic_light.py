"""src/ui/tabs/macro/section_traffic_light.py — 紅綠燈決策儀表板(P3-D9 v18.391 抽出)。

原 tab_macro.py:170-235 inline(【模組一】紅綠燈卡 + warroom_summary write)。

跨 page state(critical):本檔寫 `st.session_state['warroom_summary']`,
被 tab_stock_grp / section_inputs / macro_helpers / macro/helpers / section_state
5 個檔案讀取。

⚠️ C1 v19.182 起 warroom 內的 regime 有**兩個 key、語意不同**:
- `regime`           = 趨勢面**輸入**(raw `mkt_info['regime']`),僅供揭露。
- `effective_regime` = 紅綠燈決策樹的**結論**(canonical),`get_macro_state()` 讀它。
另附 `light`(🟢🟡🔴)與 `regime_source`(哪條分支生效)。詳見
`shared/regime_arbiter.py`。

placeholder lifecycle:`_tl_placeholder = st.empty()` 物件由 caller 沿用 ——
後續 `_tl_placeholder.empty()` (refresh 時清空)+ `render_section_state(...,
_tl_placeholder, ...)` (B-S2)都需要。跨 def 傳 placeholder 已在 B-S2 證實
可行,不是反模式。

closure params:無(全部從 st.session_state 讀)

回傳 tuple (3 件):
- placeholder: st.empty 物件(caller 後續 .empty()/.markdown 用)
- show_market_data: bool(下游所有 section gate)
- tl_eff_reg: str | None('bull'/'neutral'/'bear';§九 / 戰情 / 作戰 共用)
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

import streamlit as st

# v19.170:此 import 僅剩下方 warroom_summary['throttle'] 寫入端使用,
# 而該 key 已無讀取端(死碼);保留原因見 render_traffic_light_top 內註解。
from shared.position_throttle import compute_position_throttle
from src.compute.macro import calc_traffic_light
from src.ui.tabs.macro.handlers import _render_traffic_light

# 油門帶顏色(對齊姿態 icon)
_THROTTLE_COLORS = {'🟢': '#26a641', '🟡': '#d29922', '🟠': '#db6d28', '🔴': '#da3633'}


def render_position_throttle(tl) -> None:
    """總經『建議持股油門』儀表(v19.62;v19.170 改吃建議持股 SSOT)。

    tl: calc_traffic_light / compute_macro_health 輸出。v19.170 起僅為 caller
        簽章相容保留 —— 所有數值一律取自 `get_allocation()`(全站唯一持股真相);
        本函式不再自行 compute_position_throttle,也不再自行讀
        macro_state['exposure_limit_pct'](天花板改由 SSOT 內部仲裁)。
    """
    # v19.170 P0-1:唯一取數入口。姿態帶(該多積極)× 硬否決(最多能到哪)→ 最終建議持股。
    from src.services.allocation_service import get_allocation
    _alloc = get_allocation()
    if not _alloc.is_loaded:
        # §1 Fail Loud:總經未評估 → 誠實顯示,不畫任何假的持股區間
        st.info('⬜ 建議持股油門：總經未評估 — 請先按「🚀 一鍵更新全部數據」')
        return

    _c = _THROTTLE_COLORS.get(_alloc.icon, '#8b949e')
    _p_lo, _p_hi = _alloc.posture_lo, _alloc.posture_hi
    _lo, _hi, _mid = _alloc.final_lo, _alloc.final_hi, _alloc.final_mid
    # 風險上限:無天花板時誠實寫「無硬否決」,不留白(留白會被誤讀成漏算)
    _cap_line = (f'🔒 風險上限 <b>{_alloc.cap_pct}%</b>（{_alloc.cap_name}）'
                 if _alloc.cap_pct is not None else '🔒 風險上限：無硬否決')
    _cap_marker = (
        f'<div style="position:absolute;left:calc({_alloc.cap_pct}% - 1px);top:-3px;'
        'width:2px;height:20px;background:#d29922;"></div>'
        if _alloc.cap_pct is not None else ''
    )
    # v19.170 格式一致:改吃 `_alloc.range_text`(顯示格式的 SSOT)。
    # 原本直接用 raw {_lo}–{_hi}% 繞過 range_text,lo==hi 時會印出「40–40%」——
    # 正是 range_text 註解宣稱要消滅的怪字串,且與全站其他 8 個取數點格式不一致。
    _range_txt = _alloc.range_text
    # 中值只在區間真的有寬度時才顯示;lo==hi 時中值恆等於區間本身,重複且無資訊。
    _mid_txt = (
        f'<span style="font-size:12px;font-weight:400;color:#8b949e;">'
        f'（中值 {_mid}%）</span>'
        if (_lo is not None and _hi is not None and _lo != _hi) else ''
    )
    st.markdown(
        f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
        f'padding:10px 14px;margin:6px 0 2px;">'
        f'<b>🎚️ 建議持股油門</b>&nbsp; {_alloc.icon} <b>{_alloc.posture}</b>'
        f'&nbsp;→ 姿態帶 <b>{_p_lo}–{_p_hi}%</b>'
        f'<div style="font-size:11px;color:#d29922;margin-top:4px;">{_cap_line}</div>'
        # 全站唯一該被記住的數字 → 字級最大、顏色最醒目
        f'<div style="font-size:22px;font-weight:900;color:{_c};margin:6px 0 2px;'
        f'letter-spacing:0.5px;">✅ 最終建議持股 {_range_txt}'
        f'{_mid_txt}</div>'
        f'<div style="position:relative;height:14px;background:#21262d;border-radius:7px;'
        f'margin:8px 0 4px;">'
        f'<div style="position:absolute;left:{_lo}%;width:{max(_hi - _lo, 1)}%;height:100%;'
        f'background:{_c};border-radius:7px;"></div>'
        f'<div style="position:absolute;left:calc({_mid}% - 1px);top:-3px;width:2px;'
        f'height:20px;background:#f0f6fc;"></div>{_cap_marker}</div>'
        f'<span style="font-size:11px;color:#8b949e;">0%（全現金） ← 總經健康分 '
        f'{_alloc.health:.0f} → 100%（滿倉）</span></div>',
        unsafe_allow_html=True,
    )
    st.caption('💡 **姿態帶**＝依總經健康分該多積極（積極↔防守）；**🔒 風險上限**＝薩姆／PMI／'
               '外資期貨／VIX 否決權／三環第一環 的硬否決天花板；'
               '**✅ 最終建議持股＝兩者取較低**，全站只認這一個數字（個別強勢股仍可各自判斷）。')

    # v19.170 P0-1:把推導攤開 —— 使用者看到「趨勢偏多卻只建議 0–20%」時
    # 能自己查到是哪一條天花板生效,而不是懷疑系統算錯。
    with st.expander('📖 為何是這個持股數字？', expanded=False):
        for _drv in _alloc.drivers:
            st.markdown(f'- {_drv}')
        if _alloc.conflicts:
            st.markdown('**⚠️ 被壓制的反向訊號**')
            for _cfl in _alloc.conflicts:
                st.markdown(f'- {_cfl}')


def render_traffic_light_top() -> tuple[Any, bool, str | None]:
    """渲染紅綠燈卡 + 寫 warroom_summary。

    Returns:
        (placeholder, show_market_data, tl_eff_reg)
        - placeholder: st.empty 物件
        - show_market_data: 快取新鮮 (≤30 min) 且非 refresh 中
        - tl_eff_reg: 有效 traffic light regime(bull/neutral/bear;None 表無資料)
    """
    # ════════════════════════════════════════════════════════
    # 【模組一】紅綠燈決策儀表板(st.empty 佔位符修復版)
    # 修復:先挖洞(placeholder)→ 資料到位後回填,杜絕未審先判
    # 紅綠燈計算邏輯已抽至 macro_helpers.calc_traffic_light(Phase 7A-Ext)
    # _render_traffic_light 在 macro/handlers.py(F-7.1 B-1)
    # ════════════════════════════════════════════════════════

    # ── ① 最頂端先建立佔位符(關鍵:必須在任何計算前建立)───
    _tl_placeholder = st.empty()

    # ── ② 讀取快取(快取新鮮才顯示燈號,否則顯示等待,避免誤導)──
    # 設計原則:燈號必須反映「當前資料」而非「過期快取」
    # 30 分鐘內的快取視為有效;超過則要求重新更新
    _cl_ts_str = st.session_state.get('cl_ts', '')
    _cache_fresh = False
    _age_min: float = 0.0
    if _cl_ts_str:
        try:
            _cl_ts_dt = _dt.datetime.strptime(_cl_ts_str[:16], '%Y-%m-%d %H:%M')
            _age_min = (_dt.datetime.now() - _cl_ts_dt).total_seconds() / 60
            _cache_fresh = _age_min < 30   # 30 分鐘內視為新鮮
        except Exception:
            _cache_fresh = False

    # 刷新進行中時隱藏舊資料(避免更新期間顯示過期結論)
    _is_refreshing = st.session_state.get('_is_refreshing', False)
    _show_market_data = _cache_fresh and not _is_refreshing

    _tl_init = None
    _tm_mkt_init: dict = {}
    # 是否走了「快取新鮮」分支 —— 決定文末要不要回填燈號卡。
    # ⚠️ 不能用 `_tl_init is not None` 當旗標:`calc_traffic_light` 三來源全空時
    # 回 None,而 `_render_traffic_light` 收到 tl=None 時**有它自己的畫面**
    # (⏳ 系統正在深度解析…)。用旗標才不會把那個狀態變成空白。
    _tl_computed = False
    if _cache_fresh and not _is_refreshing:
        # 快取新鮮 → 立即計算燈號(含資料新鮮度標記)
        # C1-D v18.290:走 section_inputs SSOT(對齊 5 桶 + 戰情概覽 + 今日作戰室)
        from src.services import load_section_inputs as _load_si_tl
        _tl_inp = _load_si_tl(st.session_state)
        _tm_mkt_init = _tl_inp.mkt_info or {}
        _tm_jq_init = _tl_inp.jingqi_info or {}
        _tm_cd_init = _tl_inp.cl_data or {}
        _tm_li_init = _tl_inp.li_latest
        _tl_init = calc_traffic_light(_tm_mkt_init, _tm_jq_init, _tm_cd_init, _tm_li_init)
        # ⚠️ v19.175:燈號卡**不在這裡**畫 —— `_render_traffic_light` 內部會呼叫
        # `allocation_service.get_allocation()`,而它唯一的來源 `warroom_summary`
        # 要到本函式下方才寫入 → 這裡渲染等於「先讀後寫」,用的是**上一輪**的
        # warroom(而「🚀 一鍵更新全部數據」的 on_click `_macro_session_reset`
        # 剛好會 pop 掉它)→ 卡片印出「建議持股 --」。
        #
        # 誠實註記:實機看到的那次 `--` 主因是 `calc_traffic_light` 拋 TypeError
        # 導致 warroom 整個沒寫成(見 macro_helpers.coerce_inst_dict);且正常路徑下
        # 本卡片稍後會被 `section_state.py:479` 用同一個 placeholder 重畫一次,
        # 所以這個順序缺陷平時**不可見**。這裡順手把它修掉,是為了讓本函式自身
        # 「先寫後讀」的不變量成立(section_state 沒跑到 / 提早炸掉時就會露出來)。
        # 卡片位置由頁頂的 `_tl_placeholder` 佔住,延後回填不影響版面順序。
        _tl_computed = True
    else:
        # 無快取 or 快取過期 → 顯示等待狀態,不顯示誤導性燈號
        age_note = (f'（上次更新 {_age_min:.0f} 分鐘前，已過期）'
                    if _cl_ts_str and not _cache_fresh else '（尚無資料）')
        _tl_placeholder.warning(
            f'⏳ **燈號等待中 {age_note}**\n\n'
            '燈號將在「🚀 一鍵更新全部數據」完成後自動亮起。\n'
            '確保資料是今日最新，再做投資判斷。',
        )

    # ── C1 v19.182:改讀 canonical 結論,不再由 icon 反推 ──────────────────
    # 原碼 `{'🔴':'bear','🟢':'bull','🟡':'neutral'}.get(tl['icon'])` 是**反向推導**
    # —— 決策樹知道自己走了哪一條分支,卻只吐一個 emoji,下游再猜回去。
    # 現在 `calc_traffic_light` 直接回 `effective_regime`(與燈色同源,見
    # `shared/regime_arbiter.py`),猜的步驟消失。
    # ⚠️ 值域與舊碼**完全一致**(bull/neutral/bear/None):arbiter 的分支 4
    # (趨勢 caution/bear)同樣回 'bear',對應舊碼 🔴 → 'bear'。
    _tl_eff_reg = (_tl_init or {}).get('effective_regime') or None

    # ── 同步寫入 session_state(其他頁面需要的值)────────────
    if _tl_init:
        # v19.168 IMPL-F 持股% 單一引擎 SSOT:在此(唯一同時握有 health + 有效 regime 之處)
        # 算一次「姿態油門」區間,存進 warroom_summary['throttle'],讓總經 gauge + 頁頂全域
        # 紅綠燈 bar + 今日作戰室 + 個股組合①卡 全讀同一份 → 根治「同一問題四處四個持股%」
        # (原 bar/作戰室/組合①用 regime 粗略 exposure_pct 80/50/20、gauge 用 health 細分區間)。
        #
        # ⚠️ v19.170 現況:持股% 已改由 `allocation_service.get_allocation()` **內生推導**
        # (每次由 macro_state.health 現算),不再依賴這個會被 section_state 整包覆寫的中繼 key。
        # 全 repo 已無任何**程式碼**讀取端(僅剩註解提及) → 本段實質為死碼。
        # 之所以保留而非刪除:`tests/test_position_throttle_ssot.py:28-31` 仍以
        # 原始碼字串掃描斷言本檔含 `compute_position_throttle` 與 `'throttle'`,
        # 直接移除會讓 CI 變紅;若只留註解讓字串掃描通過,則會製造該測試檔自己
        # (line 44-46)指出的 false green。廢止本 key 應與該測試一起改,屬另案。
        _wr_throttle = compute_position_throttle(
            float(_tl_init['health']), regime=_tl_eff_reg,
            defense=bool(_tl_init.get('defense')))
        st.session_state['warroom_summary'] = {
            'traffic_light': _tl_init['label'],
            'health_score':  _tl_init['health'],
            # ── C1 v19.182:regime 三欄位契約 ──────────────────────────────
            # `regime`(舊 key)語意不變 = **趨勢面輸入** raw `mkt_info['regime']`,
            # 保留給揭露「被壓制的反向訊號」用(例:趨勢 bull 但健康分跌破 → 燈 🔴)。
            # `effective_regime` 才是結論 —— `get_macro_state()` 讀它,於是置底
            # 常駐條 / ETF 配置橫幅 / 個股組合評分 與 頁頂燈號卡 **同一個答案**。
            # ⚠️ 不可把 effective 寫回 `'regime'` key:`section_state.py:511` 的
            # `_wr_sum.update({...'regime': _tl2_mkt.get('regime','neutral')...})`
            # 會在本函式之後把該 key 蓋回 raw 值(該檔本輪不在授權改動範圍),
            # 用獨立 key 才不會被蓋掉。`get_macro_state` 另備 primitives 重算路徑,
            # 即使兩個 key 都缺也能得到同一答案。
            'regime': _tm_mkt_init.get('regime', 'neutral'),
            'effective_regime': _tl_init['effective_regime'],
            'light':            _tl_init['light'],
            'regime_source':    _tl_init['regime_source'],
            'market_score':  _tl_init['score'],
            'jingqi_avg':    _tl_init['jqavg'],
            'leek_index':    _tl_init['leek'],
            'foreign_net_bn': _tl_init['fnet'],
            'futures_net':   _tl_init['fut_net'],
            'confidence_pct': _tl_init['conf'],
            # v19.170 DEPRECATED:持股% 已改由 allocation_service 內生推導,
            # 此中繼 key 現無任何程式碼讀取端(保留原因見上方註解)。
            'throttle':      _wr_throttle,   # v19.168 IMPL-F:持股% SSOT(lo/hi/mid/posture/icon)
        }
        # v19.148 ① 接線:同步寫 canonical macro_state(單一契約)→ 個股頁加碼三問 +
        # 個股組合 6 因子評分 + AI regime 全讀這裡,總經狀態終於真的影響選股決策。
        try:
            from src.services.macro_state_locker import get_macro_state
            st.session_state['macro_state'] = get_macro_state(st.session_state['warroom_summary'])
        except Exception as _e_ms:  # noqa: BLE001 — 寫 canonical 失敗不炸總經頁
            print(f"[section_traffic_light] macro_state 寫入失敗:{type(_e_ms).__name__}: {_e_ms}")

    # ── ③ 最後才回填燈號卡(必須在 warroom_summary / macro_state 寫入之後)───
    # v19.175:`_render_traffic_light` → `get_allocation()` → `get_macro_state(warroom)`。
    # 放在寫入之前 = 讀到「上一輪」(或被 on_click pop 掉)的 warroom → `is_loaded=False`
    # → 卡片印出「建議持股 --」,而同一頁下方各區塊卻是正常數字,使用者只會看到矛盾。
    # 延後回填讓卡片與全站 8 個持股消費點**同輪同源**(v19.171 置底條同一修法)。
    if _tl_computed:
        _render_traffic_light(_tl_placeholder, _tl_init, _tm_mkt_init)

    return _tl_placeholder, _show_market_data, _tl_eff_reg
