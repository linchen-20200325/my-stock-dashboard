"""TAB 教學：策略邏輯說明書（靜態 Markdown）— 從 app.py 抽出（PR P2-B Phase 5-A）

依賴極簡：僅 streamlit；內部所需 data_registry / shared.macro_card / pandas
皆在函式內 late import，避免循環 import 與啟動成本。

呼叫端
======
- app.py: `with tab_edu: render_tab_edu()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.fred_series import FRED_NAPM
from shared.ttls import TTL_1DAY


# #U7：單值總經指標若 identifier 為 FRED series id → 可抓歷史序列畫 sparkline
_FRED_EDU_UNITS = {'CPILFESL': 'pc1', 'XTEXVA01TWM664S': 'pc1', FRED_NAPM: 'lin'}


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _fetch_fred_series_edu(series_id: str, units: str = 'lin', months: int = 24):
    """抓 FRED 指標近 N 月歷史序列（教學 tab sparkline 用）；units=pc1 取 YoY%。失敗回 None。"""
    try:
        import os as _o
        import pandas as _pd
        from src.data.proxy import fetch_url as _fu
        _key = (_o.environ.get('FRED_API_KEY')
                or (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else '') or '')
        if not _key:
            return None
        _r = _fu('https://api.stlouisfed.org/fred/series/observations',
                 params={'series_id': series_id, 'api_key': _key, 'file_type': 'json',
                         'units': units, 'sort_order': 'desc', 'limit': months},
                 timeout=12, attempts=1)
        if _r is None or getattr(_r, 'status_code', 0) != 200:
            return None
        _pairs = [(_ob['date'], float(_ob['value']))
                  for _ob in _r.json().get('observations', [])
                  if _ob.get('value') not in ('.', '', None)]
        if len(_pairs) < 3:
            return None
        _pairs.sort(key=lambda x: x[0])
        _result = _pd.Series([v for _, v in _pairs],
                             index=_pd.to_datetime([d for d, _ in _pairs]))
        # v18.357 PR-Q5c S-PROV-1 phase 19:Series attrs
        try:
            _result.attrs.setdefault('source', f'FRED:{series_id}:units={units}:months={months}')
            _result.attrs.setdefault('fetched_at', _pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result
    except Exception:
        return None


def render_tab_edu():
    st.markdown('## 📖 系統說明書 — 公式、策略與資料來源完整說明')
    st.caption('整理自各大師公開課程，僅供學術研究。投資涉及風險，本系統不構成買賣建議，盈虧自負。'
               '｜v18.281 合併原理教室 + 資料來源地圖,單一說明書集中查閱。')

    # ════════════════════════════════════════════════════════════
    # v18.281 — ⓪ 資料來源完整地圖(學 Fund tab6 Section ⓪)
    # 每筆資料 → 用在哪個 Tab → 來源 endpoint → refresh → fallback
    # ════════════════════════════════════════════════════════════
    with st.expander('⓪ 📊 資料來源完整地圖（每筆資料→Tab→endpoint→refresh→fallback）',
                     expanded=False):
        st.caption('本系統各 Tab 用到的所有資料來源,對照 CLAUDE.md §2.1 SSOT 5-Tier 權威分級。'
                   '**任一筆失敗會在 🔎 資料診斷 Tab 用紅燈標出**。')
        _dm = [
            ('📈 美國總經指標', '🌐 總經',
             'FRED API（NAPM / DGS10 / DGS2 / DGS3MO / BAMLH0A0HYM2 / M2SL / WALCL / CPIAUCSL / FEDFUNDS / UNRATE / PPIACO）',
             'FRED 30min / 月後 ~13 天（CPI/NFP 有修正）',
             'FRED → DBnomics → ISM 官網 → MacroMicro'),
            ('📊 VIX / DXY / 銅', '🌐 總經',
             'Yahoo Chart（^VIX / DX-Y.NYB / HG=F）',
             'Yahoo 1hr / EOD 翌日 04:00 TW',
             'Yahoo → CBOE CDN（VIX）'),
            ('🇹🇼 TW PMI', '🌐 總經',
             '8 源賽跑：CIER-EN → data.gov.tw → NDC → CIER首頁 → StockFeel → Cnyes → CIER-cid8 → MoneyDJ（v19.113）',
             '月後第 1 營業日',
             'PMI_SOURCE_REGISTRY 順序賽跑,取第一命中（禁止平均）'),
            ('🏦 CBC M1B / M2', '🌐 總經',
             'CBC ms1.json（央行）',
             '月後 ~5-7 天,90 天 cache',
             'CBC（TWD）→ IMF（USD,僅 fallback,禁跨幣別平均）'),
            ('🇨🇳 中國拖累 modifier', '🌐 總經',
             'FRED（CNCPIALLMINMEI / IRLTCT01CNM156N / MYAGM3CNM189N / XTEXVA01CNM664S）',
             '月頻,90 天 cache',
             '全敗 → modifier = 1.0 中性'),
            ('💹 個股 OHLCV', '📈 個股',
             'TWSE OpenAPI / TPEX OpenAPI / FinMind / Yahoo',
             '同日盤後 14:30 TW,30min cache',
             'TWSE → FinMind → Yahoo'),
            ('💰 三大法人 / 融資', '📈 個股 / 💰 籌碼',
             'TWSE 三大法人表 / TWSE 融資餘額',
             '同日盤後,30min cache',
             'TWSE → HiStock → Wearn（融資）'),
            ('📐 期貨 / 選擇權 PCR', '💰 籌碼',
             'TAIFEX（外資 TX 期貨 / Put-Call Ratio）',
             '同日盤後 14:00 TW',
             'TAIFEX 主源,無備援'),
            ('📅 月營收', '📈 個股',
             'FinMind / MOPS / Goodinfo',
             '月後 ~10 天,3 天 cache',
             'FinMind → MOPS → Goodinfo'),
            ('🏦 ETF NAV / 持股', '🏦 ETF',
             'etf_fetch（TWSE / 投信官網）',
             '2hr cache',
             'fallback chain 內部處理'),
            ('📰 新聞 RSS', '🌐 總經',
             'Google News / Bloomberg / CNBC / Yahoo Finance',  # v18.458: Reuters removed (dead since 2020)
             '即時',
             '個別失敗 → 其他源繼續'),
            ('🤖 AI 摘要', '🌐 總經 / 📈 個股',
             'Google Gemini API（EX-AI-1 例外,回 str）',
             'On-demand 無 cache',
             'GEMINI_KEY 未設 → AI 區塊跳過（不擋畫面）'),
        ]
        _th = ('font-size:10px;color:#888;font-weight:700;padding:8px 10px;'
               'border-bottom:1px solid #30363d')
        _td = 'font-size:11px;padding:8px 10px;line-height:1.4'
        _html = (
            f"<div style='display:grid;grid-template-columns:1.4fr 1.1fr 2.6fr 1.5fr 2.2fr;"
            f"background:#0d1117;border-radius:6px 6px 0 0'>"
            f"<span style='{_th}'>資料項目</span>"
            f"<span style='{_th}'>用在 Tab</span>"
            f"<span style='{_th}'>來源 / endpoint</span>"
            f"<span style='{_th}'>Refresh / 延遲</span>"
            f"<span style='{_th}'>Fallback chain</span></div>"
        )
        for _item, _tab, _src, _ref, _fb in _dm:
            _html += (
                f"<div style='display:grid;grid-template-columns:1.4fr 1.1fr 2.6fr 1.5fr 2.2fr;"
                f"background:#0d1117;border-bottom:1px solid #21262d'>"
                f"<span style='{_td};color:#e6edf3;font-weight:600'>{_item}</span>"
                f"<span style='{_td};color:#79c0ff'>{_tab}</span>"
                f"<span style='{_td};color:#bbb;font-family:monospace;font-size:10px'>{_src}</span>"
                f"<span style='{_td};color:#888'>{_ref}</span>"
                f"<span style='{_td};color:#a5d6ff;font-size:10px'>{_fb}</span></div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_html}</div>", unsafe_allow_html=True)
        st.caption('**📖 對應憲法**：CLAUDE.md §2.1 SSOT（5-Tier）、§2.3 PIT（發布延遲）、'
                   '§2.4 Freshness（TTL）、§4.6 領域邊界。任一筆紅燈 → 🔎 資料診斷 Tab 找對應 fetcher 修。')

    # ── 📖 指標解讀手冊（從 data_registry 自動生成）──────────────
    # v17: 新增「即時數值 + 24M 趨勢圖」chip + sparkline，使用 shared/macro_card 共用模組
    with st.expander('📖 指標解讀手冊 — 數字 + 趨勢 + 完整教學', expanded=True):
        try:
            from src.data.core import (
                get_categories, get_by_category, get_edu, get_edu_count,
                render_edu_card_html,
            )
            from shared.macro_card import calc_z_score, make_sparkline
            import pandas as _pd_edu

            # ─── identifier → (current_value, pd.Series|None, t_warn, t_crit, high_is_bad) ───
            def _get_indicator_data(identifier: str):
                """從 session_state 取出指標的即時值 + 24M series + 警戒/危險閾值。

                覆蓋範圍：
                  ✓ 有 series：^VIX / ^TNX / ^SOX / DX-Y.NYB（cl_data.intl 有 90D OHLC）
                  ✓ 僅單值：CPILFESL / NAPM / XTEXVA01TWM664S / NDC_signal /
                            ms1.json / MI_MARGN / BFI82U（macro_info / m1b_m2_info / cl_data）
                  ✗ 無資料：BWIBBU_d（TWSE 大盤散點資料，無單一聚合值，請至個股 Tab 看）
                """
                _macro = st.session_state.get('macro_info') or {}
                _cl    = st.session_state.get('cl_data') or {}
                _intl  = _cl.get('intl') or {}
                _m1b   = st.session_state.get('m1b_m2_info') or {}
                _bias  = st.session_state.get('bias_info') or {}

                # ─ 國際金融（有完整 OHLC DataFrame）─
                _intl_map = {
                    '^TNX':      ('10Y公債殖利率', 4,    5,   True),
                    '^SOX':      ('費城半導體 SOX', None, None, False),
                    'DX-Y.NYB':  ('美元指數 DXY',   105,  110, True),
                }
                if identifier in _intl_map:
                    _name, _tw, _tc, _hib = _intl_map[identifier]
                    _df = _intl.get(_name)
                    if _df is not None and not _df.empty:
                        _ccol = 'Close' if 'Close' in _df.columns else (
                            'close' if 'close' in _df.columns else None)
                        if _ccol:
                            _s = _df[_ccol].dropna()
                            if len(_s) >= 2:
                                return float(_s.iloc[-1]), _s, _tw, _tc, _hib
                    return None, None, _tw, _tc, _hib

                # ─ ^VIX：macro_info.vix 已有 60 天 series ─
                if identifier == '^VIX':
                    _v = _macro.get('vix') or {}
                    if _v.get('values') and _v.get('dates'):
                        try:
                            _s = _pd_edu.Series(_v['values'],
                                                index=_pd_edu.to_datetime(_v['dates']))
                            return _v.get('current'), _s, 22, 30, True
                        except Exception:
                            pass
                    return _v.get('current'), None, 22, 30, True

                # ─ 單值類（無 series，但顯示當前值 + 閾值線）─
                _single = {
                    'CPILFESL':       ((_macro.get('us_core_cpi') or {}).get('yoy'),         2.5,  4,    True),
                    FRED_NAPM:        ((_macro.get('ism_pmi')     or {}).get('value') or
                                       (_macro.get('ism_pmi')     or {}).get('current'),     50,   45,   False),
                    'XTEXVA01TWM664S':  ((_macro.get('tw_export')   or {}).get('yoy'),         0,    -5,   False),
                    'NDC_signal':     ((_macro.get('ndc_signal')  or {}).get('score') or
                                       (_macro.get('ndc_signal')  or {}).get('value'),       32,   22,   None),
                    'ms1.json':       ((_m1b.get('m1b_yoy')      or 0) -
                                       (_m1b.get('m2_yoy')        or 0)
                                       if (_m1b.get('m1b_yoy') is not None
                                           and _m1b.get('m2_yoy') is not None)
                                       else None,                                            0,    -2,   False),
                }
                # ─ BFI82U：三大法人現貨買賣超（取外資 net，億）─
                if identifier == 'BFI82U':
                    _inst = _cl.get('inst') or {}
                    _foreign_key = next((k for k in _inst if '外資' in str(k)), None)
                    if _foreign_key:
                        _net = _inst.get(_foreign_key, {}).get('net')
                        if _net is not None:
                            _val = float(_net) / 1e8 if abs(float(_net)) > 1e6 else float(_net)
                            return _val, None, 0, -100, False
                    return None, None, 0, -100, False

                if identifier in _single:
                    _v, _tw, _tc, _hib = _single[identifier]
                    _funits = _FRED_EDU_UNITS.get(identifier)
                    if _funits is not None:
                        _ser = _fetch_fred_series_edu(identifier, _funits)
                        if _ser is not None and len(_ser) >= 3:
                            return ((_v if _v is not None else float(_ser.iloc[-1])),
                                    _ser, _tw, _tc, _hib)
                    return _v, None, _tw, _tc, _hib

                # ─ 其他（暫無資料，後續 PR 處理）─
                return None, None, None, None, None

            _edu_total = get_edu_count()
            st.markdown(
                f"""
**新人最大的痛點**：指標一堆，但每個是什麼？要怎麼看？要搭配什麼一起看？
本手冊把每個核心指標拆解成 **6 個問題** + **24 個月趨勢圖**：

| 問題 | 內容 |
|------|------|
| 💡 **是什麼** | 用一句白話解釋這個指標在量什麼 |
| 📐 **怎麼判讀** | 數字到了哪個門檻代表什麼訊號 |
| 🔗 **搭配看什麼** | 不能只看單一指標，要對照哪些指標 |
| 📊 **歷史錨點** | 歷史上的關鍵數字（讓你有比例尺） |
| ⬆️ **上游因** | 誰會影響這指標（找根源） |
| ⬇️ **下游果** | 這指標會影響誰（找連動效應） |
| 📈 **即時值 + 24M 趨勢** | 當前值 + Z-Score + 趨勢圖（含警戒/危險閾值線） |

📌 目前已撰寫 **{_edu_total} 個** 核心指標教學卡（持續擴充中）。
未列出的指標請見「🔎 資料診斷」Tab → 各類別展開查看完整資料目錄。
""")
            st.markdown('---')
            for _cat in get_categories():
                _entries_in_cat = get_by_category(_cat)
                _edu_pairs = [(e, get_edu(e.get('identifier'))) for e in _entries_in_cat]
                _edu_pairs = [(e, ed) for e, ed in _edu_pairs if ed is not None]
                if not _edu_pairs:
                    continue
                st.markdown(f'### {_cat}')
                for _e, _edu in _edu_pairs:
                    _id = _e.get('identifier', '')
                    _val, _series, _tw, _tc, _hib = _get_indicator_data(_id)
                    # ─ 即時值 + Z-Score chip ─
                    _z = (calc_z_score(_series, _val)
                          if _series is not None and len(_series) >= 10 else None)
                    if _val is not None or _series is not None:
                        _val_str = (f"{_val:.2f}" if isinstance(_val, (int, float))
                                    else "—")
                        _z_str   = f"  Z={_z:+.2f}" if _z is not None else ""
                        _z_color = (MATERIAL_RED if _z is not None and abs(_z) >= 2 and
                                    ((_hib and _z > 0) or (_hib is False and _z < 0))
                                    else (MATERIAL_GREEN if _z is not None and abs(_z) >= 2
                                          else (MATERIAL_ORANGE if _z is not None and abs(_z) >= 1.5
                                                else "#79c0ff")))
                        st.markdown(
                            f"<div style='display:flex;gap:14px;align-items:baseline;"
                            f"margin:14px 0 0;padding:8px 14px;background:#161b22;"
                            f"border:1px solid #30363d;border-radius:8px 8px 0 0;"
                            f"border-bottom:none'>"
                            f"<span style='color:#8b949e;font-size:11px;font-weight:600;"
                            f"letter-spacing:1px'>📈 即時值與趨勢</span>"
                            f"<span style='color:#e6edf3;font-size:18px;font-weight:700'>"
                            f"{_val_str}</span>"
                            f"<span style='color:{_z_color};font-size:12px'>{_z_str}</span>"
                            f"</div>",
                            unsafe_allow_html=True)
                        # ─ Sparkline（有 series 才畫）─
                        if _series is not None and len(_series) >= 2:
                            # v18.440 修:make_sparkline 簽章為
                            # (values, dates, height, line_color, threshold_warn, threshold_crit)
                            # 原呼叫傳了不存在的 high_is_bad / lookback → TypeError
                            # (教學分頁原本未綁定渲染,故此 latent bug 一直沒被觸發)。
                            # lookback=60 改 slice 最後 60 點;轉 list 確保 make_sparkline 內
                            # values[-1] 不踩 pandas label-index。high_is_bad 上方 Z 卡已用,sparkline 不需。
                            _fig = make_sparkline(
                                list(_series)[-60:],
                                threshold_warn=_tw, threshold_crit=_tc,
                                height=70,
                            )
                            if _fig is not None:
                                st.plotly_chart(
                                    _fig, use_container_width=True,
                                    config={'displayModeBar': False},
                                    key=f'spark_{_id}_{_cat}')
                        else:
                            st.caption("⚠️ 此指標目前僅有單一最新值，趨勢圖待後續 PR 補齊（需擴充 macro fetcher）")
                    # ─ 既有 EDU HTML 卡（白話/判讀/搭配/上下游/歷史）─
                    st.markdown(render_edu_card_html(_e, _edu),
                                unsafe_allow_html=True)
        except ImportError as _ie:
            st.error(f'❌ 無法載入 data_registry：{_ie}')

    # ── 孫慶龍 ───────────────────────────────────────────────────
    with st.expander('📊 策略1（估值 / 存股）— 財報領先指標與盈餘成長選股', expanded=True):
        st.markdown("""
### 核心邏輯：在「業績加速成長」前提早佈局

本策略強調，股價長期反映的是企業「未來盈餘的折現值」。
市場往往落後財報數字，懂得讀「領先財報」的人就能在機構法人之前看見機會。

---

#### 🔑 財報領先指標一：合約負債（Contract Liabilities）

> **白話定義**：客戶已付錢但公司尚未交貨 → 代表「口袋裡的訂單」

| 門檻 | 訊號 | 意義 |
|------|------|------|
| 合約負債 **> 股本 50%** | 🟢 龍多信號 | 訂單爆滿，未來 1–2 季業績有保證 |
| 合約負債 **> 股本 100%** | 🔥 超強信號 | 產能供不應求，定價權在手 |
| 合約負債持續季增 | 🔼 加分項 | 訂單持續進來，成長趨勢確認 |

**篩選口訣**：合約負債高 → 代表「客戶先給錢」，這樣的公司最不怕景氣波動。

---

#### 🔑 財報領先指標二：資本支出（CapEx）

> **白話定義**：公司在大買機器、蓋廠房 → 代表對未來「投票」

| 門檻 | 訊號 | 意義 |
|------|------|------|
| 資本支出 **> 股本 80%** | 🟢 擴張信號 | 大膽押注未來需求，對訂單有把握才會花這麼多 |
| 資本支出連續 2 季增加 | 🔼 加分項 | 不是一次性，是持續擴產 |

---

#### 🔑 盈餘成長率：EPS 加速是關鍵

- **近 4 季 EPS 年增率加速**（從 +5% → +10% → +20%）= 最強選股信號
- 毛利率 ≥ 30% 且維持 or 提升 → 高護城河企業
- 營業利益率提升 → 靠本業賺錢，非業外收益

#### ✅ 龍多股完整篩選框架

```
合約負債 > 股本 50%  ✓
資本支出 > 股本 80%  ✓
近 4 季 EPS 加速成長  ✓
月營收 YoY 加速 (3個月均線上彎)  ✓
→ 龍多股確認，大型法人機構尚未追入前的黃金買點
```
""")

    # ── 老師 ─────────────────────────────────────────────────────
    with st.expander('📐 策略3（技術 / 動能）— 型態學：破底翻 × 頭肩底 × 頸線突破', expanded=True):
        st.markdown(r"""
### 核心邏輯：用「型態」讀懂主力換手完畢的訊號

本策略認為，K線型態是「資金博弈的足跡」。主力洗盤完畢後，往往留下可辨識的底部型態。

---

#### 🔑 型態一：破底翻（Fake Breakdown Reversal）

> 股價跌破前低 → 但**隔日收回**前低之上 → 散戶停損被洗出後主力拉抬

| 步驟 | 判斷標準 |
|------|---------|
| ① 量縮跌破前低 | 成交量明顯萎縮（代表散戶恐慌賣壓，非主力出貨） |
| ② 當日或隔日大量紅K | 量比 ≥ 1.5，收盤站回前低之上 |
| ③ 連續 2 根紅K確認 | 第 2 根紅 K 收盤突破近期高點 → 破底翻確認 |

**停損設定**：破底翻 K 棒低點即為硬停損，跌破即出場。

---

#### 🔑 型態二：頭肩底（Inverse Head & Shoulders）

```
         左肩          右肩
          /\            /\
         /  \    頭    /  \
        /    \  /  \  /    \
───────/──────\/────\/──────────  ← 頸線（Neckline）
                底部（最低點）
```

| 要素 | 判斷標準 |
|------|---------|
| 左肩 | 下跌後反彈，成交量萎縮 |
| 頭部 | 跌破左肩低點，量更小（洗盤） |
| 右肩 | 反彈至接近左肩高點，**量比頭部大** |
| 突破頸線 | 收盤站上頸線 + 成交量爆增 ≥ 均量 1.5 倍 → 買點 |

---

#### 🔑 操作細節：頸線突破買點

1. **等收盤確認**：不追日內突破，等收盤穩站頸線之上
2. **回測不破**：突破後如回測頸線不跌破 → 加碼機會
3. **目標價**：頸線 + 頭部到頸線距離（等幅量測）
4. **停損**：跌破右肩低點即出場
""")

    # ── 春哥 ─────────────────────────────────────────────────────
    with st.expander('🌀 策略3（技術 / 動能）— VCP 波幅收縮與爆量突破', expanded=True):
        st.markdown(r"""
### 核心邏輯：波幅每次比上次小 → 籌碼鎖定完成 → 等爆量突破

VCP（Volatility Contraction Pattern）找的是「橫盤整理中能量不斷蓄積」的股票，
波幅每次比前次更小，量能不斷萎縮，直到爆量突破才確認方向。

---

#### 🔑 VCP 四大關鍵條件

| 條件 | 標準 | 說明 |
|------|------|------|
| ① **多次波幅收縮** | ≥ 3 次 | 每次高低振幅比前次縮小 ≥ 1/3 |
| ② **成交量持續萎縮** | 量比 < 0.8 | 籌碼鎖定，浮額洗盡 |
| ③ **不跌破關鍵均線** | 站上 MA20 | 型態不能在均線下方整理 |
| ④ **突破需有爆量** | 量比 ≥ 2.0 | 收盤突破近期整理高點 + 巨量 = 有效突破 |

---

#### 🔑 VCP 示意圖

```
價格
│    /\        /\      /\
│   /  \      /  \    /  \  ← 波幅一次比一次小
│  /    \    /    \  /    \___________  突破!▲▲▲ (爆量)
│ /      \  /      \/
│/        \/
└─────────────────────────────── 時間
        收縮①  收縮②  收縮③   Pivot Point(突破點)
```

---

#### 🔑 進出場規則

| 動作 | 標準 |
|------|------|
| **進場** | 突破 Pivot Point（整理高點）+ 當日收盤接近最高（收盤在當日高點 95% 以上） |
| **加碼** | 突破後回測 Pivot 不破，再加 0.5 倍部位 |
| **停損** | 跌破進場 K 棒低點（通常約 7–8% 以內） |
| **停利** | 距停損 3 倍獲利（盈虧比 ≥ 3:1）先設目標；強勢股跟蹤 MA10 |

> **策略3 心法**：「量縮到極點就是爆發前夕。等的不是上漲，等的是籌碼。」
""")

    # ── 老師 ─────────────────────────────────────────────────────
    with st.expander('💰 老師 — 資金動能 M1B-M2 × 均線多頭家數 × 外資期貨防守', expanded=True):
        st.markdown("""
### 核心邏輯：用「總體資金」判斷大盤體質，而非個股

老師認為，股票市場是資金推動的遊戲。M1B-M2 利差是最領先的資金指標，
比任何技術指標都早 6–9 個月看到轉折。

---

#### 🔑 指標一：M1B – M2 利差（資金寬鬆度）

> **白話**：M1B 是活錢（活存），M2 是定存 + 活存。
> 活錢比例上升 → 錢從定存搬出來 → 準備進股市

| 利差 | 訊號 | 建議倉位 |
|------|------|---------|
| M1B YoY **> M2 YoY** 且擴大 | 🟢 資金寬鬆，多頭啟動 | **持股 70–100%** |
| M1B YoY **= M2 YoY**（利差收斂） | 🟡 轉折警戒，注意方向 | **持股 50%** |
| M1B YoY **< M2 YoY**（利差翻負） | 🔴 資金緊縮，熊市風險 | **持股 0–30%** |

---

#### 🔑 指標二：均線多頭排列家數

> **白話**：台股 1800 支股票中，有幾支站在 240 日均線（年線）之上？

| 家數比例 | 市場意義 |
|---------|---------|
| ≥ **60%** 站上年線 | 🟢 多頭格局強健，可積極持股 |
| **40–60%** 站上年線 | 🟡 多空拉鋸，選股不選市 |
| ≤ **40%** 站上年線 | 🔴 熊市格局，嚴控倉位 |

搭配「大盤 vs 個股」強弱：
- 指數創高但多頭家數不創高 → 警訊（領頭羊撐盤，底層崩潰）
- 多頭家數先反彈 → 領先大盤底部的信號

---

#### 🔑 指標三：外資期貨空單防守線

| 外資期貨淨部位 | 訊號 | 操作建議 |
|--------------|------|---------|
| 淨**多單** > 0 且擴大 | 🟢 外資看多台股 | 可積極作多 |
| 淨多單縮減中 | 🟡 外資降低多頭暴露 | 適度降低倉位 |
| 淨**空單** > 0 | 🔴 外資對沖台股風險 | 大盤需謹慎 |
| 淨空單急速擴大 | 🚨 系統性風險信號 | 立即減碼至 30% 以下 |

---

#### ✅ 老師完整多空判斷矩陣

| M1B-M2 | 多頭家數 | 外資期貨 | 建議倉位 |
|--------|---------|---------|---------|
| ✅ 寬鬆 | ✅ ≥60% | ✅ 多單 | **滿倉 80–100%** |
| ✅ 寬鬆 | ✅ ≥60% | ❌ 空單 | **七成 70%** |
| ✅ 寬鬆 | ❌ <40% | 任何 | **五成 50%，選股不選市** |
| ❌ 緊縮 | 任何 | 任何 | **防守 0–30%，保留現金** |

> **老師口訣**：「M1B-M2 翻正是起跑槍，年線家數過半是加速器，外資空單是急剎車。」

---

#### 📌 股匯四象限快查表（連動操作）

| 象限 | 台股 | 台幣 | 外資行為 | 持股建議 |
|------|------|------|---------|---------|
| 🟢 股匯雙漲 | ↑ | 升值 | 匯入真實資金 | **80–100%** |
| ⚠️ 股漲匯貶 | ↑ | 貶值 | 疑似拉高出貨 | **50%，不追高** |
| 🔴 股匯雙殺 | ↓ | 貶值 | 大舉提款撤出 | **0–30%，嚴格防守** |
| 🟡 股跌匯升 | ↓ | 升值 | 資金停泊台灣 | **50–70%，找錯殺股** |
""")

    # ── v18.281 原理教室(從 macro_classroom 移入,合併成單一說明書)──
    render_principle_classroom()

    st.markdown("""---
<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
padding:10px 14px;font-size:11px;color:#8b949e;margin-top:8px;text-align:center;">
⚠️ 本教學整理自各大師公開課程內容，僅供學術研究與教育用途。<br>
投資涉及風險，任何操作均應自行判斷，盈虧自負。本系統非投資顧問，不構成買賣建議。
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# v18.281 — 總經原理教室(從 macro_classroom.py 移入,合併成單一說明書)
# 內容已對權威來源查證(CIER/國發會/TWSE/FRED/ISM/CBOE,見 v18.279)
# ════════════════════════════════════════════════════════════════
_PRINCIPLE_CHAPTERS: list[tuple[str, str]] = [
    (
        "🌀 景氣循環四階段(復甦 → 擴張 → 高峰 → 衰退)",
        """
經濟不是直線成長,而是循環:**復甦 → 擴張 → 高峰 → 衰退**,平均一個完整循環約 5-10 年。

- **復甦**:谷底翻揚,失業率高但 PMI 反轉、央行寬鬆,股市最佳買點
- **擴張**:GDP 穩步成長,通膨溫和,股市持續上行
- **高峰**:景氣過熱,通膨升溫迫使央行升息,股市見頂
- **衰退**:企業獲利衰退,失業率上升,股市熊市

**TW 在地補充**:台股景氣高度同步美股(R² ≈ 0.7),但加掛「外資資金流」因子 —
外資撤退時即使美股漲,台股也可能 K 線轉弱。判讀位階時要兩面看。

📐 **數學定義(NBER 衰退判定 / TW 國發會景氣燈號)**

**NBER 美國版**:無單一公式,看 6 大月度指標(實質個人所得 / 非農就業 / 個人消費 /
製造批發銷售 / 家戶就業 / 工業生產)。GDP 連 ≥ 2 季 QoQ < 0 → 技術性衰退。

**TW 國發會景氣燈號**:綜合 9 項指標(M1B / 股價 / 工業生產 / 海關出口 / 機械設備 /
製造業銷售值 / 批發零售餐飲 / 非農就業 / PMI)→ 紅(熱絡)/ 黃紅(轉熱)/ 綠(穩定)/
黃藍(轉弱)/ 藍(低迷)5 燈號。

📜 **歷史案例(TWII 反應)**

| 年份 | 全球事件 | TWII 高點→低點 | 持續 | 國發會燈號 |
|---|---|---|---|---|
| 2000-2001 | dot-com + 911 | 10393 → 3411(-67%) | 19 月 | 連 **15** 月藍燈(2000/12–2002/2,**史上最長**) |
| 2008 | 金融海嘯 | 9859 → 3955(-60%) | 12 月 | 連 **9** 月藍燈(2008/9–2009/5,史上第三長) |
| 2015 | 中國股災 | 10014 → 7203(-28%) | 7 月 | 景氣低迷黃藍燈為主 |
| **2020** | **COVID-19** | **12197 → 8523(-30%)** | **2 月**(史上最短) | 黃藍 → 紅燈 |
| 2022 | Fed 升息 | 18619 → 12629(-32%) | 10 月 | 紅 → 黃藍 |

> 國發會藍燈紀錄排名:① 網路泡沫 15 月(2000/12–2002/2)> ② 歐債 10 月(2011/11–2012/8)> ③ 金融海嘯 9 月(2008/9–2009/5)。
        """.strip(),
    ),
    (
        "📊 PMI 為何 50 是分水嶺?",
        """
PMI(Purchasing Managers Index, 採購經理人指數)向採購經理調查 5 個面向(新訂單 / 生產 /
雇用 / 供應商交貨 / 存貨)。每面向「比上月好/差/持平」三選一,**好佔比 - 差佔比 + 50 = PMI**。

- PMI > 50:**多數企業比上月好** → 經濟擴張
- PMI < 50:**多數企業比上月差** → 經濟收縮
- PMI = 50:**好壞均衡** → 經濟停滯

**領先性**:PMI 領先實質 GDP / 工業生產 約 1-3 個月,因為採購決定先於生產。

**TW 在地來源**:本系統按優先序賽跑 10 個源(CIER → data.gov.tw → NDC → MacroMicro →
StockFeel → FinMind → MoneyDJ 等),**禁止平均**(混合不同方法論 = 雜訊)。
台灣官方製造業 PMI 由中華經濟研究院(CIER)**2012/7 才創編**,故 2008-09 金融海嘯**無台灣官方 PMI**,僅能參照美國 ISM。

📐 **數學定義**

```
PMI = 30% × 新訂單 + 25% × 生產 + 20% × 雇用 + 15% × 供應商交貨 + 10% × 存貨

各子指標 = (好的%) + 0.5 × (持平%) + 50 - 50 → 落 0~100
```

**權重邏輯**:新訂單最領先(下單→生產→出貨→銷售 chain 最早),故給最高權重 30%。

📜 **歷史案例(製造業 PMI vs TWII)**

| 月份 | 美 ISM | 台灣 PMI(中經院)| TWII 同期 | 市場狀態 |
|---|---|---|---|---|
| 2008/12 | 32.4(26 年新低)| —(2012/7 才創編)| 4591(底部區) | 後 12 月 +78%(8188)|
| 2009/3 | 36.3(反轉)| — | 5210 | 復甦起點 |
| 2020/4 | 41.5 | 47.6 | 9978 | 後 6 月 +26%(12552 / 2020/10)|
| **2022/12** | **48.4** | **43.7** | 14138 | 谷底區 |
| 2024/9 | 47.2 | 49.2(緊縮)| 22260 | 與景氣脫鉤(指數創高)|

> ⚠️ 台灣官方 PMI(中經院 CIER)2012/7 才創編,2008-09 兩列僅有美國 ISM;先前誤填的 2008-09 台灣 PMI 為不存在數據,已移除(§1 反捏造)。
        """.strip(),
    ),
    (
        "🚨 薩姆規則(Sahm Rule)— 衰退鎖定指標",
        """
2019 年聯準會經濟學家 **Claudia Sahm** 提出:
**美國失業率 3 個月滾動平均** - **過去 12 個月最低點** ≥ 0.5 百分點 → 衰退鎖定。

歷史回測:**1949 年以來 100% 命中**(11 次衰退全部觸發,無假警報)。

**為何 0.5?** 失業率單月雜訊大,**3M 平均**過濾噪音;**12M 低點**抓「動能轉折」;
0.5pp 是統計顯著閾值。

**啟示**:薩姆觸發 = 衰退**已開始**,不是預警 → 立刻降低風險。
台股無法忽視美股拖累,薩姆觸發後 TW 大盤平均 6 個月回檔 -15%。

📐 **數學定義**

```
Sahm = MA(美失業率, 3M) - min(美失業率[-12M : now])

if Sahm ≥ 0.5 → 衰退鎖定
```

**為何用 3M 平均?** 月度勞動數據雜訊 ±0.1-0.2pp,3M 滑動平均降噪 √3 倍。
**為何用 12M 低點?** 抓「最近一次景氣谷底後升的幅度」,直接捕捉動能反轉。

📜 **歷史案例(衰退起點後 TWII 反應)**

| 美衰退起點(NBER) | 約略 Sahm | 後 6 月 TWII | 後 12 月 TWII |
|---|---|---|---|
| 1990/7 | 0.5 | -57%(海灣戰爭崩盤)| -38% |
| 2001/3 | 0.6 | -32% | -7% |
| **2008/2** | **0.5** | **-22%** | **-46%** |
| 2020/4 | 2.4(史上最高)| +30%(QE 異常) | +57% |
| 2024/8 | 0.5 | +5%(進行中) | TBD |

> ⚠️ 表中日期為 **NBER 衰退起始月**。薩姆規則屬即時指標,實際跨 0.5 觸發點通常**落在衰退起點後 0-3 月**(2020/4、2024/8 為薩姆實際觸發月,其餘為衰退起點對照)。

**規則**:衰退起點後 TWII 平均 6 月回檔 -15%(2020 為政策例外)。
        """.strip(),
    ),
    (
        "📉 殖利率曲線倒掛 — 50 年最準衰退預警",
        """
正常:**長天期公債殖利率 > 短天期**(借錢越久利率越高,合理)。
**倒掛**:10 年期 < 2 年期 / 3 個月,即 10Y-2Y 或 10Y-3M < 0。

**為何能預測衰退?** 倒掛代表市場預期:
- **未來會降息**(經濟轉壞 → Fed 降息 → 長債殖利率先下)
- **企業借短貸長利潤萎縮** → 銀行不願放貸 → 信用收縮
- **投資人爭搶長債避險** → 長債價格上漲、殖利率下跌

**歷史**:1969 以來每次衰退前 10Y-3M 都倒掛,**平均提前 12 個月**(6-24 範圍)。
**台股應對**:倒掛後 12 個月內,TW 50 通常先見頂、後修正,可降低個股 β 暴露。

📐 **數學定義**

```
Spread_10Y2Y = Yield_10Y - Yield_2Y
Spread_10Y3M = Yield_10Y - Yield_3M

if Spread < 0 → 倒掛
if Spread < 0 持續 ≥ 3 月 → 高機率衰退
```

**Fed NY logistic 衰退機率**:
```
P(recession) = 1 / (1 + exp(0.5 + 0.55 × Spread_10Y3M_12M_avg))
```
Spread = -1% → P ≈ 50%;Spread = -2% → P ≈ 78%。

📜 **歷史案例(倒掛 → TWII 反應)**

| 倒掛日 | 倒掛深度 | 美衰退起點 | 提前期 | TWII 高峰→谷底 |
|---|---|---|---|---|
| 2000/2 | -0.5% | 2001/3 | 13 月 | 10393 → 3411(-67%) |
| 2006/7 | -0.2% | 2007/12 | 17 月 | 9859 → 3955(-60%) |
| 2019/3* | -0.3% | 2020/2 | 11 月 | 12197 → 8523(-30%) |
| **2022/7** | **-1.08%**(2023/7,**1981 年來最深**) | TBD | 已 24+ 月 | 進行中(2024/7 24416 是否頂?)|

> *2019/3 先倒掛的是 10Y-3M;10Y-2Y 主倒掛在 2019/8。
> 倒掛深度:-1.08%(2023/7/3)是 **1981 年來最深**;真史上最深為 1980-81 Volcker 期(< -2%)。

**2022 異常**:1981 年來最深倒掛但衰退遲未到,可能 AI 資本支出 + 寬鬆財政對沖。
        """.strip(),
    ),
    (
        "📐 外資籌碼 — TW 股市定價最重要的單一指標",
        """
TW 股市外資持股比 ~40%(2024 年),日均成交量占比 25-30%,**外資動向是定價核心**。

本系統三大外資觀察:
- **外資現貨買賣超**:當日 net buy/sell,> +100 億 = 強買,< -100 億 = 強賣
- **外資期貨大小**:多空淨部位(口數),> +30000 口 = 看多 / < -30000 = 看空
- **三大法人**:外資 + 投信 + 自營商合計動向

**外資撤退的早期訊號**:
1. 連續 5 個交易日淨賣超
2. 期貨大空單建立 + 現貨同時賣超
3. 押注大跌:put/call 比飆高

**TW 在地警訊**:外資期貨大空單 > 5 萬口 + 大盤跌破年線 → 系統強制「防禦模式」。

📐 **數學定義(系統實際 logic)**

```
外資現貨買賣超 (億 TWD)  = TWSE 三大法人表「外資及陸資」買進 - 賣出
外資期貨大空 (口)        = TAIFEX「外資」TX 期貨未平倉淨額(多 - 空)

警訊觸發 = (期貨 net < -30000) AND (現貨連 5 日 net < 0)
強警訊   = (期貨 net < -50000) AND (TWII < MA240)  → 防禦模式
```

**為何選 30000 口為閾值?** 對應 ~6 億 TWD 名目部位,歷史回測 30000 口空單持續 5 日後
TWII 6 月平均報酬 -8%。

📜 **歷史案例**

| 期間 | 外資累計淨賣 | TWII 反應 | 觸發強度 |
|---|---|---|---|
| 2008 全年 | 約 -4,600 億 + 期空 -8 萬口 | 8506 → 4591(全年 -46%)| 極端 |
| 2015/8 中國股災 | 8 月單月大賣(全年實為**淨買超 +422 億**)| 10014 → 7203(-28%)| 強 |
| 2020/3 COVID | -3100 億(1 月內) | 12197 → 8523(-30%)| 極端 |
| **2022 Fed 升息** | **-1.23 兆**(全年!) | **18619 → 12629(-32%)** | **史上最大單年** |
| 2024/8 套利平倉 | 約 -2,800 億(3 日) | 24416 → 19830(8/5 收盤,-19%)| 快速 |

> 金額為概略量級,精確值以 TWSE 三大法人統計為準。**注意 2015 全年外資是淨買超**(+422 億),僅 8 月股災單月賣超,勿與全年混淆。
        """.strip(),
    ),
    (
        "💸 韭菜指數(融資餘額)— 散戶情緒反指標",
        """
**融資餘額**:散戶向券商借錢買股的金額。本系統「韭菜指數」歸一到 0-100:
- 韭菜指數 > 35:散戶**過度樂觀**(歷史頂部訊號)
- 韭菜指數 10-35:正常
- 韭菜指數 < 10:散戶**極度悲觀**(歷史底部訊號)

**為何是反指標?** 散戶資訊不對稱、追高殺低 → 集體買進時往往接近頂、集體賣出時接近底。
本系統用作「逆向確認」:多頭訊號 + 韭菜偏低 = 高勝率;多頭訊號 + 韭菜飆高 = 警覺。

**歷史**:2021 年 11 月韭菜飆 45 → 2022 年大盤 18619 跌至 12629(-32%)。

📐 **數學定義**

```
原始融資餘額 = TWSE + TPEX 每日融資餘額總和(億 TWD)

韭菜指數 = ((融資 - μ_5Y) / σ_5Y + 2) / 4 × 100

其中:
  μ_5Y = 過去 5 年融資餘額均值
  σ_5Y = 過去 5 年融資餘額標準差

clip 到 [0, 100],對應 Z-Score:
  韭菜 = 100 → Z ≈ +2(極端樂觀)
  韭菜 = 50  → Z ≈ 0(中性)
  韭菜 = 0   → Z ≈ -2(極端悲觀)
```

**為何用 5Y 滾動?** 融資結構隨市場規模變化,絕對金額不可比,標準化才有意義。

📜 **歷史案例(融資頂峰 vs TWII 修正)**

| 韭菜高峰日 | 韭菜值 | 融資餘額 | TWII | 後 12 月 TWII |
|---|---|---|---|---|
| 2000/4(融資天花板)| 48 | **5,956 億**(史上最高)| 9855 | -50% |
| 2007/10(海嘯前) | 42 | 約 3,200 億 | 9809 | -60% |
| 2018/1 | 38 | 1,840 億 | 11103 | -16% |
| **2021/11** | **45** | 約 2,540 億 | 17840 | **-29%** |
| 2024/7 | 35 | 約 2,500 億 | 24416 | 警戒中 |

> 註:融資**絕對**金額史上最高在 2000/4(5,956 億);2021 這輪絕對峰在 4 月(約 2,600 億),11 月為韭菜**指數**(5Y 標準化)高點。

**底部反例**:2009/3 韭菜跌至 8 → TWII 後 12 月 +97%。極端低位 = 散戶絕望 = 反向買點。
        """.strip(),
    ),
    (
        "😱 VIX 30 — 恐慌指數歷史標竿",
        """
**VIX**:CBOE 用 SPX 選擇權隱含波動率計算的「市場預期未來 30 天波動」。

- VIX < 15:**極平靜**(常見牛市末期,警覺自滿)
- VIX 15-20:**正常**
- VIX 20-30:**警戒**(出現賣壓)
- VIX ≥ 30:**恐慌**(2008/2020/2018Q4 都觸發)
- VIX ≥ 40:**極度恐慌**,歷史上多為**最佳逆向買點**

**TW 對應**:無等價 TW VIX(TAIFEX 有 VIX 指數但流動性低)。本系統用美股 VIX
作為「全球風險偏好」proxy:VIX 飆 → 外資撤新興市場 → 台股賣壓。

📐 **數學定義**

```
VIX² = (2/T) Σ [(ΔK_i / K_i²) × e^(rT) × Q(K_i)] - (1/T) × (F/K_0 - 1)²

化簡:VIX = SPX 30 天 ATM 選擇權隱含 σ × 100

T   = 30 天 / 365
K_i = 第 i 個 OTM 履約價
Q   = 該選擇權買賣中價
```

**標準差換算**:VIX 30 = 年化 σ 30% → 1 月 σ = 30/√12 ≈ 8.7%
所以 VIX 30 = 「68% 機率 SPX 1 月內變動 ±8.7%」。

📜 **歷史案例(VIX 高峰 vs TWII 反應)**

| 日期 | VIX 峰值 | 觸發事件 | TWII 同期(% 變化) |
|---|---|---|---|
| 2008/10/24 | **89.5**(盤中史上最高;收盤 79)| 雷曼倒閉 | -34%(4 月內) |
| 2010/5 | 46(5/20 餘波) | Flash Crash | -8%(快速恢復) |
| 2018/2/5 | 50(盤中;收盤 37) | volmageddon | -10% |
| **2020/3/16** | **82.7**(收盤史上最高) | COVID | -30%(2 月內) |
| 2022/9 | 33 | Fed 鷹派 | -7% |
| 2024/8/5 | 65(盤中) | 套利平倉 | -19% 同日大跌 |

> VIX 紀錄:**盤中史上最高 89.53(2008/10/24)**;**收盤史上最高 82.69(2020/3/16)**,兩者不同口徑。

**規則**:VIX > 40 後 6 月 TWII 平均 +18%(6 次中 5 次正報酬),但須承受續跌 -10% 風險。
        """.strip(),
    ),
    (
        "🕐 美林時鐘 — 景氣 × 通膨 二維配置框架",
        """
2004 年美林證券提出,用 **GDP 動能(↑↓)** × **通膨方向(↑↓)** 切 4 象限:

| 階段 | GDP | 通膨 | 最佳資產 |
|---|---|---|---|
| **復甦** | ↑ | ↓ | **股票**(成長 + 寬鬆) |
| **擴張** | ↑ | ↑ | **商品**(原物料定價) |
| **高峰** | ↓ | ↑ | **現金**(避險 + 等高息) |
| **衰退** | ↓ | ↓ | **債券**(降息 + 避險) |

**台股對應策略**:
- 復甦/擴張:增加成長股、半導體、原物料
- 高峰:轉防禦股(電信、公用)、現金、海外債
- 衰退:長期公債、防禦股、避開高 β 個股

📐 **數學定義(階段判斷)**

```
GDP 動能 = sign(GDP_QoQ_annualized 趨勢 over 6M)
通膨方向 = sign(CPI YoY 趨勢 over 6M)

→ 復甦  if GDP↑ & CPI↓
→ 擴張  if GDP↑ & CPI↑
→ 高峰  if GDP↓ & CPI↑
→ 衰退  if GDP↓ & CPI↓
```

**美林原版回測(1973-2004)4 階段年化報酬**(原報告階段名 Reflation/Recovery/Overheat/Stagflation)

| 階段(原文) | 股票 | 債券 | 商品 | 現金 |
|---|---|---|---|---|
| 復甦 Recovery | **+19%** | +7% | -7% | +2% |
| 擴張 Overheat | +6% | 0% | **+19%** | +1% |
| 高峰 Stagflation | -11% | -1% | **+28%** | 0% |
| 衰退 Reflation | +6% | **+9%** | -11% | +3% |

> 數據引自美林 2004《The Investment Clock》原始報告,各方引用略有出入(整數 vs 小數、Stagflation 商品 +28%/+29% 兩版)。
> 上方白話的「高峰→現金」是**風險定位**口訣;原報告**實證**1973-2004 滯脹期反而**商品最強**(石油危機),兩者出發點不同(防守口訣 vs 歷史回測),不矛盾。

📜 **歷史案例(TWII 年報酬 vs 階段)**

| 年份 | 階段 | TWII 年報酬 | 重點 |
|---|---|---|---|
| 2009 | 復甦 | **+78%** | 4591 → 8188(從谷底反彈)|
| 2017 | 擴張 | +15% | 9253 → 10643(半導體領軍)|
| 2018 | 高峰 | -8% | 10643 → 9727 |
| 2008 | 衰退 | -46% | 8506 → 4591 |
| **2020** | **復甦** | **+22%** | 11997 → 14732(疫情後反彈) |
| 2022 | 高峰→衰退 | -22% | 18219 → 14137(Fed 升息) |
| 2023 | 復甦 | +27% | 14137 → 17930 |
| 2024 | 復甦/擴張 | +28% | 17930 → 23035(AI 行情)|
        """.strip(),
    ),
    (
        "💰 M1B-M2 黃金交叉 — TW 在地動能信號",
        """
- **M1B**:活期 + 支存(高流動性,即時可用)
- **M2**:M1B + 定存 + 外幣存款(全部準貨幣)

**M1B/M2 比率**上升 = 錢從定存轉活存,**等著進股市** → 多頭動能。
**M1B/M2 比率**下降 = 錢回流定存,股市籌碼乾涸 → 空頭風險。

**經典訊號**:M1B YoY > M2 YoY 持續 ≥ 3 個月 → **黃金交叉**,台股歷史上 6-12 月平均
報酬 +20%(2009 / 2017 / 2020 都觸發)。**死亡交叉**反之。

**資料源**:央行 CBC ms1.json 月公布,本系統 90 天 cache fallback。

📐 **數學定義**

```
M1B = 通貨 + 支票存款 + 活期存款 + 活期儲蓄存款
M2  = M1B + 定存 + 定儲 + 外幣存款 + 郵儲

M1B YoY (%) = (M1B_now - M1B_12M_ago) / M1B_12M_ago × 100
M2  YoY (%) = (M2_now  - M2_12M_ago)  / M2_12M_ago  × 100

Spread = M1B YoY - M2 YoY

黃金交叉 = Spread 由負轉正 且持續 ≥ 3 月
死亡交叉 = Spread 由正轉負 且持續 ≥ 3 月
```

**為何 M1B/M2 比率有解釋力?** 該比率反映「**準備買股的錢** / **總準貨幣**」,
比率上升即「資金正從定存搬到活存準備進場」,屬於 TW 在地獨家動能。

📜 **歷史案例(M1B-M2 交叉 vs TWII)**

| 黃金交叉日 | Spread 由負轉正 | TWII 起點 | 後 12 月 TWII |
|---|---|---|---|
| 2009/2 | -3% → +4% | 4591 | **+78%**(8188)|
| 2012/9 | -2% → +1% | 7715 | +12% |
| 2017/3 | -1% → +3% | 9811 | +13% |
| **2020/6** | **+5% → +13%**(最大 spread) | **11621** | **+30%**(15125)|
| 2023/9 | -1% → +2% | 16480 | +30%(21450)|

**死亡交叉反例**:2007/12 Spread 由正轉負 → 2008 大跌 -46%。
2022/3 Spread 由正轉負 → 12 月內 -22%。
        """.strip(),
    ),
    (
        "📏 Z-Score / σ band — 統計極端值如何用於進出場",
        """
**Z-Score**:某指標**現值** vs **歷史平均** 差幾個標準差(σ):

```
Z = (現值 - μ) / σ
```

- Z = 0:正常區
- |Z| > 1:偏離(機率 ~32%)
- |Z| > 2:極端(機率 ~5%)
- |Z| > 3:罕見(機率 ~0.3%)

**應用**(本系統 σ band 進出場):
- **z=+2** 過熱 → 賣出訊號(年高 + 2σ 對應的價格)
- **z=-2** 過冷 → 買進訊號(年低 - 2σ 對應的價格)
- **z=+3 / z=-3** 極端 → 加倍訊號

**為何 ±1.5σ / ±2σ 是常用 cut-off?** 統計上 ±2σ 約 5%,**極罕見必反應**;
±1.5σ 約 13%,**夠少見值得反應**。

📐 **數學定義**

```
μ (mean)    = Σ x_i / n
σ (std dev) = √(Σ (x_i - μ)² / (n-1))
Z = (x_current - μ) / σ

常態分布累積機率(經驗法則 68-95-99.7):
  P(|Z| < 1) ≈ 68.27%
  P(|Z| < 2) ≈ 95.45%
  P(|Z| < 3) ≈ 99.73%
  P(|Z| > 2) ≈ 4.55% → 「20 次出現 1 次」
```

**Lookback 選擇(本系統)**:
- 個股 vol / 韭菜指數 → **252 / 1250 交易日**(1Y / 5Y)
- 殖利率 / VIX → **252 交易日**
- M1B-M2 spread → **60 月**(5Y 月頻)

📜 **歷史案例(TW 在地 Z-Score 應用)**

| 指標 | 日期 | 現值 | μ / σ | Z | 後續(6-12M)|
|---|---|---|---|---|---|
| VIX | 2020/3 | 82.7(收盤)| 19/8 | **+8.0** | TWII +35% |
| 外資期貨 net | 2008/10 | -8.5 萬口 | -1/3 萬 | **-2.5** | TWII -22%(續跌)/ -34%(底)|
| 融資餘額 | 2021/11 | 2540 億 | 1600/450 | **+2.1** | TWII -29% |
| TWII RSI | 2009/3 | 25 | 50/15 | -1.7 | +78%(極端低反彈)|
| 美 ISM | 2008/12 | 32.4 | 52/5 | **-4.0** | TWII 後 12 月 +78%(谷底反彈)|

**逆向操作經驗值**:Z > +3 或 Z < -3 的指標後 6-12 月,均值回歸機率 > 75%。
        """.strip(),
    ),
]


def render_principle_classroom() -> None:
    """📚 總經原理小教室 — 永久 expander,初學者隨時可查的書本式解釋。

    10 段核心概念,每段 200-400 字,適合「學一次 → 看其他指標都通」。
    對齊 Fund 版本但加 TW 在地補充(外資/韭菜/M1B-M2 等台股獨家章節)。
    """
    st.divider()
    with st.expander(
        "📚 總經原理小教室 — 看不懂的指標?點這裡學一次,終身受用",
        expanded=False,
    ):
        st.caption(
            "為初學者整理的 10 個核心總經概念,**含 TW 股市在地補充**。"
            "每段都解釋「是什麼 / 為何重要 / 怎麼判讀」。"
            "建議按順序讀完,之後看其他指標就會通。"
        )
        for _i, (_title, _body) in enumerate(_PRINCIPLE_CHAPTERS, 1):
            st.markdown(f"### {_i}. {_title}")
            st.markdown(_body)
            st.markdown("---")
