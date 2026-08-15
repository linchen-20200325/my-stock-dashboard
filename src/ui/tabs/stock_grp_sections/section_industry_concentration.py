"""src/ui/tabs/stock_grp_sections/section_industry_concentration.py
— 🏭 產業集中度（T2 2026-08，L5 UI section）。

回答一個問題：**「我這籃股票，是不是全押在同一個產業？」**

§8.2 layer：L5 UI section（純展示）。資料經 L3
`services/stock_grp_service.get_portfolio_concentration()` → L2
`compute/risk/concentration.compute_industry_concentration()`，
本檔**不做任何計算**，只負責把 L2 的結果誠實地畫出來。

════════════════════════════════════════════════════════════════════
本區塊刻意「只有數字、沒有燈號」（user 2026-08-14 裁示）
════════════════════════════════════════════════════════════════════
分散度的「幾個產業才算夠」沒有普適標準 —— DOJ 的 HHI 1500/2500 是衡量
**產業市場結構**的，套到投資組合沒有依據。憑空定一個門檻就是新的
magic number（§3.3）。故本區塊只呈現事實，判讀交給使用者。

日後若要加燈號：門檻寫進 L0 `shared/`，docstring 註明來源（user 裁示 /
文獻 / 實證回測），**不要**直接寫在這個檔案裡。

════════════════════════════════════════════════════════════════════
兩處必須顯示、不可省略的誠實揭露（§1 Fail Loud, Never Fake）
════════════════════════════════════════════════════════════════════
1. **等權假設**：個股組合的 `stock_watchlist` schema 只有
   `['name','ticker','updated_at']`（`gsheet_portfolio.py:60`），
   系統**不知道**每檔實際部位大小。省略這句話 = 讓使用者以為那是他的
   真實集中度。
2. **覆蓋率**：查不到產業別的檔數不進分母，故數值只描述「已分類的那部分」。
   覆蓋率不足時必須講。

對外 API：
- render_macro_exposure_link_section(stock_list) -> None   # T1-b 總經水位對照
- render_industry_concentration_section(stock_list) -> None # T2  產業集中度

兩者同檔的理由：都在回答「**我的組合結構**，放在當前風險背景下如何」，
且都必須揭露同一個限制 —— 個股組合沒有張數資料。分開兩檔會讓那段揭露
文字複製兩份（§2.1 SSOT）。
"""
from __future__ import annotations

import streamlit as st

__all__ = [
    'render_industry_concentration_section',
    'render_macro_exposure_link_section',
]

#: 覆蓋率低於此值時，在標題旁加註「代表性有限」。
#: ⚠️ 這**不是**投資判斷門檻（那類門檻本區塊刻意不設，見模組 docstring），
#: 而是「這份統計本身可不可信」的資料品質提示 —— 半數以上查不到產業別時，
#: 剩下那半的分佈不足以描述整個投組。與 §3.3 規範的評分/訊號門檻性質不同，
#: 故就近定義而非上移 L0；若日後有第二個 consumer 再抽 SSOT。
_COVERAGE_HINT_PCT = 50.0


def render_macro_exposure_link_section(stock_list: list[str] | None) -> None:
    """📡 總經水位對照（T1-b）—— 把「總經建議持股」與「你實際有幾檔」並列。

    流程圖層次 1 那支「影響全系統風控係數」箭頭在個股組合頁的接點。
    本頁頂端的「💼 建議持股」KPI 卡（`section_market_status.py`）已顯示建議區間，
    但**沒有跟使用者自己的部位並列** —— 看得到建議、看不到自己離建議多遠。

    ⚠️ **只做並列顯示，不做水位換算**（user 2026-08-14 裁示）：
      個股組合的 `stock_watchlist` schema 沒有張數（`gsheet_portfolio.py:60`），
      「N 檔 ≈ 幾 % 部位」在數學上**無法得知** —— 12 檔可以是總資產的 5% 也可以是 95%。
      硬換算（例如假設每檔等額、或假設滿倉）就是捏造（§1）。
      故只並列兩個**各自為真**的數字，並明講為什麼不相減。

    持股建議一律取自 `allocation_service.get_allocation()`（全站唯一 SSOT），
    §1：未評估時 `range_text` 自回 '--'，本區塊直接不顯示，不回填任何預設值。
    """
    if not stock_list:
        return

    try:
        from src.services.allocation_service import get_allocation
        _alloc = get_allocation()
    except Exception as _e:  # noqa: BLE001 — 總經取不到不該炸掉整頁
        print(f'[macro_exposure_link] get_allocation 失敗: {type(_e).__name__}: {_e}')
        return

    if not _alloc.is_loaded or _alloc.range_text == '--':
        # §1：未評估就不顯示，不印「建議持股 --」那種看似有值的空殼。
        return

    st.markdown(
        '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
        'padding:10px 14px;margin-top:8px;">'
        '<b>📡 總經水位對照</b>'
        f'<div style="font-size:12px;color:#c9d1d9;margin-top:4px;">'
        f'總經建議持股 <b>{_alloc.range_text}</b>'
        f'　·　你目前清單 <b>{len(stock_list)}</b> 檔</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        '⚖️ 兩個數字**刻意不相減** —— 本頁的組合只存代號、不存張數，'
        f'所以「{len(stock_list)} 檔」等於總資產的百分之幾，系統並不知道。'
        '（12 檔可以是 5% 也可以是 95%）'
        '要看真實水位，需要能取得每檔的持有張數與總資金。'
    )


def render_industry_concentration_section(stock_list: list[str] | None) -> None:
    """🏭 產業集中度 —— 依目前組合清單即時計算，不需按「批次分析」。

    Args:
        stock_list: 個股組合的代號清單（`stock_list_t3`）。空 / None → 不渲染。
    """
    if not stock_list:
        return

    st.markdown('---')
    st.markdown('#### 🏭 產業集中度')

    try:
        from src.services.stock_grp_service import get_portfolio_concentration
        _c = get_portfolio_concentration(stock_list)
    except Exception as _e:  # noqa: BLE001 — §1：算不出來就說算不出來
        st.warning(
            f'⚠️ 產業集中度計算失敗（{type(_e).__name__}: {_e}）。\n\n'
            '產業別來自 FinMind `TaiwanStockInfo`；若持續失敗，'
            '請檢查 `FINMIND_TOKEN` 是否設定、或該來源是否暫時無回應。'
        )
        return

    # ── §1：算不出來 → 顯示診斷，絕不顯示 0 或「完美分散」 ──────────
    if not _c.is_computable:
        st.warning(
            f'⚠️ 這 {_c.n_total} 檔全部查不到產業別，無法計算集中度。\n\n'
            '產業別來自 FinMind `TaiwanStockInfo`（1 日快取）。'
            '常見原因：未設定 `FINMIND_TOKEN`、當日 quota 用罄、'
            '或清單中為非台股代號。'
        )
        return

    # ── 主要指標 ─────────────────────────────────────────────
    _c1, _c2, _c3 = st.columns(3)
    _c1.metric(
        '有效產業數',
        f'{_c.n_eff:.1f}',
        help='= 1 / HHI。意思是「你的組合實質上等於分散在幾個產業」。\n\n'
             f'目前名義上有 {_c.n_industries} 個產業，'
             f'但因為檔數分佈不均，實質只等於 {_c.n_eff:.1f} 個。\n\n'
             '數字越接近名義產業數 = 越平均；越接近 1 = 越集中在少數產業。',
    )
    _c2.metric(
        '最大產業佔比',
        f'{_c.top1_pct:.0f}%',
        help=f'佔比最高的是「{next(iter(_c.counts))}」，'
             f'{next(iter(_c.counts.values()))} 檔。',
    )
    _c3.metric(
        '前三大合計',
        f'{_c.top3_pct:.0f}%',
        help='前三大產業合計佔比。產業數不足 3 時等於 100%。',
    )

    # ── 分佈明細 ─────────────────────────────────────────────
    _rows = ''.join(
        '<div style="display:flex;align-items:center;gap:8px;margin-top:4px;">'
        f'<div style="width:120px;font-size:12px;color:#c9d1d9;">{_ind}</div>'
        '<div style="flex:1;background:#21262d;border-radius:3px;height:14px;">'
        f'<div style="width:{_pct:.1f}%;background:#58a6ff;height:14px;'
        'border-radius:3px;"></div></div>'
        f'<div style="width:86px;text-align:right;font-size:12px;color:#8b949e;">'
        f'{_c.counts[_ind]} 檔 · {_pct:.0f}%</div>'
        '</div>'
        for _ind, _pct in _c.weights_pct.items()
    )
    st.markdown(
        '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
        f'padding:10px 14px;margin-top:8px;">{_rows}</div>',
        unsafe_allow_html=True,
    )

    # ── 誠實揭露 1：等權假設（不可省）────────────────────────
    st.caption(
        f'📐 **以等權假設計算**：本頁的個股組合只存代號、不存張數，'
        f'故一律視為 {_c.n_classified} 檔各佔 '
        f'{100.0 / _c.n_classified:.1f}%。'
        '你的實際部位大小若差異很大，真實集中度會與此不同。'
        '（想用真實市值權重看單股集中度 → 下方「🎚️ 風險貢獻分解」可輸入張數）'
    )

    # ── 誠實揭露 2：覆蓋率（有缺才講，講清楚偏誤方向）──────────
    if _c.n_unclassified > 0:
        _low = _c.coverage_pct < _COVERAGE_HINT_PCT
        _head = '⚠️ ' if _low else ''
        _tail = '　本次覆蓋率偏低，上方數字僅描述其中一部分，代表性有限。' if _low else ''
        st.caption(
            f'{_head}共 {_c.n_total} 檔，其中 **{_c.n_unclassified} 檔查不到產業別**，'
            f'未列入計算（覆蓋率 {_c.coverage_pct:.0f}%）。'
            f'這些檔**不會**被歸進「其他」桶 —— 併一桶會低估集中度，'
            f'歸進最大桶則是捏造。{_tail}'
        )
