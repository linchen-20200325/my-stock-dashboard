"""src/ui/tabs/stock_sections/section_dragon_alert.py — 龍頭預警區 section(v18.411 U4 Phase 3-Dragon).

從 tab_stock.py:802-829 抽出。
- 龍多策略最高等級「龍頭預警區」
- 合約負債 / 股本 ≥ 50% → 未來 3-6 月訂單保障
- 資本支出(CF,季實際支出) / 股本 ≥ 80% → 大擴廠,看好未來需求

§8.2 layer:L5 UI Tab section helper(低風險,純展示)。

對外 API:
- render_dragon_alert_section(cl2, cx2, capital, *, capex=None) -> None
"""
from __future__ import annotations

import streamlit as st

# D1 v19.185（§3.3 反捏造）：原本這裡是 inline `>= 0.5` / `>= 0.8` 兩個裸數字，
# 而**同一個門檻**在 `tab_stock.py` 的 AI prompt、`section_financial_leading.py`
# 的卡片副標都各自寫了一份。三份複本 = 改一處必漏兩處。改吃 SSOT。
# FIX(§3.3 SSOT): 原本本檔自行用兩個門檻常數 + 自寫比例計算 + `except: pass`，
#   與 section_financial_leading.evaluate_leading_gates() 是**逐字重複的第二份實作**
#   （同層 L5，import 不違反 §8.2）。改為共用該純函式：
#     - 消除兩份門檻判定漂移的風險
#     - 順帶拿掉本檔的 `except: pass`（gates 內部已處理 None / 型別 / 非正值）
#   ✅ **OR→AND 已於 2026-08-14 經 user 裁示統一**（見下方 render 函式內 FIX 註記）。
#      現行：本檔與 section_financial_leading:185 **同為 AND**，
#      不再出現「本檔掛極稀有金卡、隔壁卻只給部分訊號黃燈」的自相矛盾。
from .section_financial_leading import evaluate_leading_gates


def render_dragon_alert_section(cl2, cx2, capital: float, *, capex=None) -> None:
    """龍頭預警區 — 龍多策略最高等級。

    cl2 / cx2 為 FinMind 原始元值;對「股本」算真實比例(取代舊版 >0 假判斷)。

    Args:
        cl2:    合約負債(元),None / 0 代表無資料
        cx2:    固定資產存量(BS PropertyPlantAndEquipment,元)，僅供 fallback
        capital: 股本(元),由 _precompute_xsec 預算後傳入
        capex:  CF 資本支出(季實際支出,元) — v18.457 Task#20 新增，用於「大擴廠」判斷
                若 None，退回 cx2(cx2 可能已 fallback 為 capex，見 app_stock_fetchers.py)
    """
    # v18.457: 龍多「大擴廠」用 CF 資本支出(季流量)比較，不用 PP&E 存量
    # PP&E 存量是幾十年的累積，製造業幾乎永遠 ≥ 股本；capex 是本季實際花錢，才能反映擴產意願
    _cx_for_dragon = capex if (capex is not None and capex > 0) else cx2

    # SSOT：門檻與比例計算一律交給 evaluate_leading_gates（同一份實作，兩處共用）
    _gates = evaluate_leading_gates(cl2, _cx_for_dragon, capital)
    _dragon_reasons = []
    if _gates['cl_lead']:
        _dragon_reasons.append(
            f'合約負債 {cl2/1e8:.1f}億（達股本 {_gates["cl_pct"]:.0f}% → 未來3-6月訂單保障）')
    if _gates['cx_lead']:
        _src_label = '季資本支出' if (capex is not None and capex > 0) else '固定資產'
        _dragon_reasons.append(
            f'{_src_label} {_cx_for_dragon/1e8:.1f}億'
            f'（達股本 {_gates["cx_pct"]:.0f}% → 大擴廠，看好未來需求）')
    # FIX(定義統一 OR→AND，user 2026-08-14 裁示): 原為 `bool(_dragon_reasons)`＝任一
    #   gate 成立就掛「🏆 龍頭預警區 — 極稀有高成長標的」金卡。但同一頁的
    #   `section_financial_leading` 用 **AND** 才寫「✅ 龍多確認」——
    #   於是同一支股票可以同時出現「極稀有」金卡與「⚠️ 部分訊號」黃燈，自相矛盾。
    #   且「極稀有」這個文案本身就在宣告 AND 語意：只滿足一個條件的標的並不稀有。
    #   統一為 AND 後徽章觸發率下降（這是預期的行為變更，不是回歸）。
    #   ⚠️ `_dragon_reasons` 仍逐條累積：AND 成立時兩條理由都會列出，
    #      使用者看得到「合約負債 + 資本支出」兩個獨立證據，而非只知道「有達標」。
    _is_dragon = bool(_gates['cl_lead'] and _gates['cx_lead'])

    if _is_dragon:
        st.markdown(
            '<div style="background:linear-gradient(135deg,#2a1f00,#3d2d00);'
            'border:2px solid #ffd700;border-radius:10px;padding:12px 16px;margin-bottom:10px;">'
            '<div style="font-size:14px;font-weight:900;color:#ffd700;margin-bottom:6px;">'
            '🏆 龍頭預警區 — 極稀有高成長標的</div>' +
            ''.join(f'<div style="font-size:12px;color:#ffe066;padding:2px 0;">• {r}</div>' for r in _dragon_reasons) +
            '<div style="font-size:11px;color:#997a00;margin-top:4px;">'
            '策略1：「不要聽老闆說什麼，要看他做什麼」— 最誠實的領先指標</div>'
            '</div>', unsafe_allow_html=True)
