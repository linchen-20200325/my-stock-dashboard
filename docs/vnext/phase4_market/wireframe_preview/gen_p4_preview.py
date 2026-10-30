"""Phase 4 步驟 0｜📊 市場頁「文字線框」的離線靜態示意＋高度量測（只讀 src.ui_v2.compact／markup；不改 src）。

用法（repo 根目錄）：
    python docs/vnext/phase4_market/wireframe_preview/gen_p4_preview.py     # 寫同目錄 *.html
    NODE_PATH=/opt/node-tools/node_modules node docs/vnext/phase4_market/wireframe_preview/shoot_p4.js

⛔ 邊界：不被 app／test import、不被 pytest 收集；元件 HTML 一律由 compact.py 產出；`pv-` 前綴為預覽外殼。
⚠️ 靜態 HTML：Streamlit 原生 st.line_chart／st.expander／st.form 以灰框示意，Streamlit 的元素間距以 16px 估算；
所有數字、日期、系列名皆為夾具（※示意），禁止當投資結論。量到的高度＝「靜態 HTML 下 compact 元件的高度」，
**不是** Streamlit 渲染後的真值（真值要等實作後用 tools/visual_fidelity 量）。
"""
from __future__ import annotations

import math
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.ui_v2 import compact as C  # noqa: E402
from src.ui_v2 import markup  # noqa: E402

OUT = Path(__file__).resolve().parent
NAN = float("nan")

# ── 逐字抄自 src/ui/views/_market_blocks.py／shared/market_conclusion.py（不 import：該檔 import streamlit）──
PAGE_TITLE, PAGE_SUBTITLE = "📊 市場", "現在適不適合投資？未來風險正在增加還是下降？"
REGIME_SCOPE = "市場位階，不是台股趨勢"
RISK_CAP_LINE = "風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate"
CONCLUSION_HEADING = "今日結論（五項各自判斷，只並列，不合成）"
CONCLUSION = ("市場位階：多頭；台股趨勢：尚未定義；國際趨勢：尚未定義；指標危險度：黃（2 桶黃 · 最差是「中期」 · "
              "只根據 8／16 項有資料）；風險上限：獨立顯示待 C2b ＋ RC-VISIBILITY Gate。")   # ※夾具（與 harness 同形）
CHART_A_TITLE = "圖A 🇹🇼 台股趨勢"
CHART_A_SAY = "看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。"
DISCLAIMER = "均線為參考，不等於正式台股趨勢判斷。"
CHART_B_TITLE = "圖B 🌍 國際趨勢"
CHART_B_SAY = "看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。"
CHART_C_TITLE = "圖C 💰 大盤合理區間"
CHART_C_EMPTY = "需先核准：EPS 資料來源、PE 情境、計算公式、更新頻率。核准前這個區塊不畫任何圖形、區間或指數位置。"
CHART_D_TITLE = "圖D ⚠️ 主要風險"
HERO_AI = "🤖 AI 投資總結：⬜ 尚未提供"
FOLD = "▸ 為什麼／來源／限制／去哪補"
RISK_LINES_FULL = ["① 🟡 📈 中期：台灣 PMI（局部走弱）｜方向：↗ 上升",
                   "② 🟡 🧩 籌碼：融資餘額（籌碼分歧）｜方向：↗ 上升｜同級並列 2 項"]   # ※夾具（harness 同形；現況整句）
RISK_LINES = ["🟡 📈 中期：台灣 PMI　↗ 上升", "🟡 🧩 籌碼：融資餘額　↗ 上升"]   # 縮短行（整句進摺疊）

PV_CSS = """
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--paper);color:var(--ink);font-family:"Noto Sans CJK TC","PingFang TC","Microsoft JhengHei","WenQuanYi Zen Hei",system-ui,sans-serif;font-size:14px;line-height:1.5}
.pv-col{margin:0 auto;padding-top:var(--top,0)}
.pv-stack>*{margin:0 0 16px 0}
.pv-h2{font-size:34px;font-weight:700;line-height:1.2;margin:0;padding:0;height:59px}
.pv-sub{font-size:13px;color:var(--ink-2);height:22px;margin:0 0 16px}
.pv-banner{font-size:11px;color:var(--ink-3);border:1px solid var(--rule);padding:4px 8px;margin:0 0 12px}
.pv-cap{font-size:12px;color:var(--ink-2)}
.pv-concl-h{font-size:15px;font-weight:700;margin:0 0 4px}
.pv-concl{font-size:15px;margin:0}
.pv-grid{display:grid;gap:12px;align-items:stretch}
.pv-g4{grid-template-columns:repeat(4,minmax(0,1fr))}.pv-g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.pv-g2{grid-template-columns:repeat(2,minmax(0,1fr))}.pv-g1{grid-template-columns:1fr}
.pv-cta{display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 16px;background:var(--cta-primary-bg);color:#fff;border-radius:6px;font-size:14px;white-space:nowrap}
.pv-cta-bar{display:flex;gap:12px;align-items:center}
.pv-native{height:var(--h,220px);border:1px dashed var(--rule-2);display:flex;align-items:center;justify-content:center;position:relative;background:var(--grid);color:var(--ink-3);font-size:12px;overflow:hidden}
.pv-native span{position:relative;background:var(--panel);padding:1px 6px}
.pv-card{background:var(--panel);border:1px solid var(--rule-2);border-radius:2px;padding:12px}
.pv-fold{border:1px solid var(--rule);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--ink-2);min-height:32px;display:flex;align-items:center}
.pv-bar{display:flex;align-items:center;gap:10px;border:1px solid var(--rule-2);border-radius:4px;padding:8px 12px;min-height:44px;flex-wrap:wrap}
.pv-bar b{font-size:14px}
.pv-risk{font-size:13px;margin:4px 0 0}
.pv-risk div{margin:2px 0}
.pv-state{margin:14px 0 6px;font-size:12px;font-weight:700;color:var(--ink-2)}
.pv-mark{outline:1px dashed #d29922}
"""


def page(title: str, body: str, width: int, top: int = 0) -> str:
    css = markup.page_css("dark") + "\n" + C.compact_css() + "\n" + PV_CSS
    return ("<!doctype html>\n<html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{css}</style></head><body>"
            f"<div class=\"pv-col pv-stack\" style=\"width:{width}px;--top:{top}px\">"
            f"{body}<div class=\"pv-banner\">Phase 4 步驟 0 離線靜態示意｜元件由 compact.py 產出，pv- 為預覽外殼｜夾具 ※示意｜"
            "靜態 HTML 高度≠Streamlit 真值</div></div></body></html>")


def spark(i: int, n: int = 60) -> str:
    vals = [100 + 8 * math.sin(i + k / 5.0) - k * (0.05 + 0.01 * i) for k in range(n)]
    return C.sparkline_svg(vals, w=100, h=48, title=f"夾具 {i}", missing_state="idle", missing_text="請按更新")


def native(h: int, label: str) -> str:
    return f'<div class="pv-native" style="--h:{h}px"><span>{escape(label)}</span></div>'


def tiles(*, risk_style: str = "lines") -> list[str]:
    t_regime = C.kpi_tile_html(label="市場位階", value="多頭", say=REGIME_SCOPE)
    t_water = C.kpi_tile_html(label="建議總持股水位", value=None, chips=[C.meta_chip("not_approved")],
                              say=RISK_CAP_LINE, say_verbatim=True)
    risk_body = "".join(f"<div>{escape(x)}</div>" for x in RISK_LINES)
    cov, _ = C.chips_html([C.meta_chip("coverage", "8／16 項有資料")])
    t_risk = ('<div class="cp-tile"><div class="cp-tile-label">今日主要風險</div>'
              f'<div class="pv-risk">{risk_body}<div class="pv-cap">另有 1 桶資料不足、無法判定（見圖 D）</div></div>{cov}</div>')
    return [t_regime, t_water, t_risk]


CTA = '<span class="pv-cta">🚀 更新今日戰情</span>'
CTA_TILE = ('<div class="cp-tile"><div class="cp-tile-label">更新</div>'
            f'<div style="margin-top:8px">{CTA}</div>'
            '<div class="cp-tile-say">▸ 更新選項（模式）</div></div>')
alert_bar = ('<div class="pv-bar"><b>⚡ 需要處理</b><span class="cp-chip cp-info">1 紅 · 1 黃</span>'
             '<span class="pv-cap">今日關鍵：VIX 21、ISM PMI 48.5（※夾具）</span><span class="pv-cap">▸ 查看清單</span></div>')


def w9_variants(width: int, mobile: bool) -> str:
    t = tiles()
    b = []
    b.append(f'<div class="pv-state">W9-A：桌機 4 欄（位階｜水位｜風險｜更新）／手機 2×2（blueprint 形）</div>')
    b.append(f'<div id="a" class="pv-grid {"pv-g2" if mobile else "pv-g4"}">' + "".join(t) + CTA_TILE + "</div>")
    b.append(f'<div class="pv-state">W9-B：3 欄 tile（位階｜水位｜風險）＋更新鈕移出成動作列；手機 {"1 欄堆疊" if mobile else "—"}</div>')
    b.append(f'<div id="b" class="pv-grid {"pv-g1" if mobile else "pv-g3"}">' + "".join(t) + "</div>")
    if mobile:
        b.append('<div class="pv-state">W9-B2：手機 2＋1（位階｜水位 並排，風險整列）＋動作列</div>')
        b.append('<div id="b2"><div class="pv-grid pv-g2">' + t[0] + t[1] + '</div><div style="height:12px"></div>' + t[2] + "</div>")
    b.append('<div class="pv-state">W9-C：3 欄 tile ＋ 第 4 欄為窄 CTA 條（同一列；桌機 3＋1，手機同 B）</div>')
    if mobile:
        b.append('<div id="c" class="pv-grid pv-g1">' + "".join(t) + f'<div class="pv-card">{CTA}</div></div>')
    else:
        b.append('<div id="c" class="pv-grid" style="grid-template-columns:repeat(3,minmax(0,1fr)) 170px">'
                 + "".join(t) + f'<div class="pv-card" style="display:flex;align-items:center;justify-content:center">{CTA}</div></div>')
    return "".join(b)


def first_screen(width: int, mobile: bool, *, conclusion_first: bool, cold: bool) -> str:
    """推薦方案 R（W9-B）：頁首＋頁級 chip＋（結論句）＋3 tile＋⚡ 一行＋Primary（圖A）。"""
    # 設計發現 F-1：compact 規定「同列最多一顆非 readable 的狀態類 chip」→ 頁級列只放 asof_missing；
    # coverage（8／16）改掛在「今日主要風險」tile 內；「尚未按過更新」留在 CTA 旁一句＋摺疊。
    chips, _ = C.chips_html([C.meta_chip("asof_missing")])
    head = (f'<div class="pv-cta-bar" style="justify-content:space-between"><div class="pv-h2" id="h2">{PAGE_TITLE}</div>'
            + ("" if mobile else CTA) + "</div>")
    sub = f'<div class="pv-sub">{PAGE_SUBTITLE}</div>'
    cta_m = f'<div id="cta">{CTA}</div>' if mobile else ""
    concl = (f'<div id="concl"><div class="pv-concl-h">{CONCLUSION_HEADING}</div><div class="pv-concl">{CONCLUSION}</div></div>')
    row = f'<div id="tiles" class="pv-grid {"pv-g1" if mobile else "pv-g3"}">' + "".join(tiles()) + "</div>"
    ai = f'<div class="pv-cap">{HERO_AI}　⬜ 資料狀態：尚未彙總</div>'
    ph = 140 if mobile else 220
    if cold:
        guards, _ = C.chips_html([C.guard_chip(DISCLAIMER), C.meta_chip("not_defined")])
        body_chart = C.chart_slot_missing_html("idle", "請按更新", height_px=ph)
    else:
        guards, _ = C.chips_html([C.guard_chip(DISCLAIMER), C.meta_chip("not_defined"), C.meta_chip("asof", "10/28"),
                                  C.meta_chip("window", "近 252 日"), C.meta_chip("readable")])
        body_chart = native(ph, "原生折線圖（指數＋均線水平參考線）")
    prim = (f'<div id="prim" class="pv-card"><div class="cp-ch-title">{CHART_A_TITLE}</div>{guards}'
            f'<div class="cp-ch-say">{CHART_A_SAY}</div>{body_chart}'
            f'<div class="pv-fold" style="margin-top:8px">{FOLD}</div></div>')
    seq = [head, sub, chips + (cta_m if mobile else "")]
    seq += ([concl, row] if conclusion_first else [row, concl])
    seq += [alert_bar, ai, prim]
    return "".join(seq)


def main() -> None:
    for vn, width, mobile in (("1440", 980, False), ("390", 358, True)):
        (OUT / f"w9_options_{vn}.html").write_text(page("W9 KPI 列欄數三案", w9_variants(width, mobile), width), "utf-8")
        for cf in (False, True):
            for cold in (False, True):
                if cold and cf:
                    continue
                name = f"first_screen_{'concl-first' if cf else 'concl-after'}_{'cold' if cold else 'loaded'}_{vn}"
                (OUT / f"{name}.html").write_text(page(name, first_screen(width, mobile, conclusion_first=cf, cold=cold),
                                                       width, top=135), "utf-8")
    print("ok")


if __name__ == "__main__":
    main()
