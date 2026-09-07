"""src/ui/render/sector_heatmap_render.py — 產業熱力圖 treemap 組裝(L4 Render)。

2026-09-07 自 `src/ui/render/etf_render.py` 的私有 `_build_treemap_data` 抽出
成 public,**函式本體一行邏輯都沒有改**(只改名 + 換檔案)。

## 為什麼抽出來(而不是留在 etf_render 讓別人直取私有名)

IA v2 頁2「🔍 找標的 › 板塊地圖」要畫同一張 treemap。跨檔直取底線開頭的私有
符號正是 `CLAUDE.md §8.2.A.2` **V-PICKER-PRIV-1** 的前車之鑑
(`tab_stock_picker` 直取 `data_loader._fm_raw_headers`),而自己抄一份組裝邏輯
則會讓「缺值留白 / 缺值面積 / 色階跨度」三件事各有兩套。

## 為什麼落在 **L4** 而不是下沉 L2

它 `return go.Figure` —— **產出的是圖,不是數字**,那是 L4 Render 的職責
(`CLAUDE.md §8.2` 七層表:L4「圖表生成 / 通用 UI 元件」)。把它下沉 L2 會變成
「L2 純函式層裡住著一個畫圖函式」,與 §8.2.A.2 **V-LEAD-RENDER-1**
(L1 檔內定義 `render_leading_table`)是同一個病的反方向。
⚠️ 而且 `tests/test_c3_layering_guard.py` 的 `_BANNED_IN_L2` 只列
`requests / yfinance / FinMind / proxy_helper` —— **不含 plotly**,
也就是真下沉了 CI **抓不到**,會是一片假綠。

## 依賴

只有 `plotly.graph_objects`(繪圖)與 `shared.sector_heatmap`(L0 口徑 SSOT)。
**零 streamlit、零 `src.data.*`、零 `src.services.*`** —— 呼叫端把算好的
`returns` 傳進來即可,本檔不取數。
"""
from __future__ import annotations

import plotly.graph_objects as go

from shared.sector_heatmap import (
    HEATMAP_MISSING_TEXT,
    color_span_pct,
    hover_value_text,
    node_area,
    sector_display_name,
)


def build_sector_treemap(sectors: dict, returns: dict, market: str,
                         *, single_stock_proxy: bool = False,
                         period_label: str = '') -> go.Figure:
    """建立 Plotly Treemap 熱力圖。

    B4-b 修正:
    - **H-3 缺值不再填 0**:`colors` 缺值傳 `None`(Plotly 留白),hover 文字改走
      `customdata` 顯示「無資料」;原本 `colors.append(0)` + `%{marker.color:+.2f}%`
      會讓「從未抓到的標的」顯示成「+0.00%」,與真實持平長得一模一樣(§1 造假)。
    - **H-3 缺值面積縮小**:原缺值母層給 1.0 / 子層給 0.5,比一檔真實 ±0.5% 的
      類股還大。改走 `node_area()`,缺值面積嚴格小於任何有資料節點。
    - **H-9 空序列**:原 `max(abs(c) for c in colors if c != 0) or 5` 在「全部為 0」
      時炸 `ValueError: max() arg is an empty sequence`(整頁白掉)。改 `color_span_pct()`。
    - **H-2 揭露**:`single_stock_proxy=True` 時類股名帶上代表股代號。

    Args:
        sectors: `{ticker: {'name': str, 'sub': [ticker, ...]}}`。
        returns: `{ticker: rate_pct}`;取不到的 ticker **不在** dict 內。
        market: root 節點標籤。
        single_stock_proxy: 該市場的「類股」是否為單一代表股近似(台股 True)。
        period_label: 區間標籤,只用於 hover 文案(如 '1日')。
    """
    ids, labels, parents, values, texts, colors, hovers = [], [], [], [], [], [], []

    # root
    ids.append(market)
    labels.append(market)
    parents.append('')
    values.append(0)
    texts.append(market)
    colors.append(None)      # root 不參與色階(H-9:也不會被 color_span_pct 誤算)
    hovers.append('—')

    for ticker, meta in sectors.items():
        sec_ret = returns.get(ticker)
        _disp = sector_display_name(meta['name'], ticker,
                                    single_stock_proxy=single_stock_proxy)
        sec_label = (f"{_disp}<br>{sec_ret:+.1f}%" if sec_ret is not None
                     else f"{_disp}<br>{HEATMAP_MISSING_TEXT}")
        ids.append(ticker)
        labels.append(sec_label)
        parents.append(market)
        values.append(node_area(sec_ret, is_parent=True))
        texts.append(f'{_disp} [{ticker}]')
        colors.append(sec_ret)          # ← None 保留成 None,Plotly 留白
        hovers.append(hover_value_text(sec_ret))

        # sub-items
        for sub in meta.get('sub', []):
            sub_ret = returns.get(sub)
            _sub_disp = sub.replace('.TW', '').replace('.TWO', '')
            sub_label = (f"{_sub_disp}<br>{sub_ret:+.1f}%" if sub_ret is not None
                         else f"{_sub_disp}<br>{HEATMAP_MISSING_TEXT}")
            ids.append(f'{ticker}/{sub}')
            labels.append(sub_label)
            parents.append(ticker)
            values.append(node_area(sub_ret, is_parent=False))
            texts.append(sub)
            colors.append(sub_ret)      # ← 同上,不填 0
            hovers.append(hover_value_text(sub_ret))

    # 顏色：最大值對稱(H-9:全缺 / 全 0 時回預設跨度,不炸 max() 空序列)
    max_abs = color_span_pct(colors)
    _hover_prefix = f'{period_label}漲跌' if period_label else '漲跌'
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents,
        values=values, text=texts, customdata=hovers,
        textinfo='label',
        marker=dict(
            colors=colors,
            colorscale=[[0, '#0f5132'], [0.35, '#1a6e36'], [0.5, '#1e2530'],
                        [0.65, '#c0392b'], [1, '#7b1212']],  # 台灣慣例：漲=紅 跌=綠
            cmid=0, cmin=-max_abs, cmax=max_abs,
            colorbar=dict(title='漲跌%', thickness=12),
            line=dict(width=1, color='#0d1117'),
        ),
        # H-3:hover 走 customdata 字串,缺值吐「無資料」而非 %{marker.color} 的 +0.00%
        hovertemplate=f'<b>%{{text}}</b><br>{_hover_prefix}：%{{customdata}}<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_dark',
        height=600,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='#0d1117',
    )
    return fig
