"""Phase 3 共用視覺元件｜離線靜態預覽產生器（Migration Plan §16.2 步驟 5）。

用法（repo 根目錄）：
    python tools/phase3_preview/gen.py            # 寫 docs/vnext/phase3_preview/*.html
    node   tools/phase3_preview/shoot.js          # Playwright 截圖 1440x900 / 390x844
    python tools/phase3_preview/compress.py       # PNG > 280KB 時量化壓縮

⛔ 邊界：本檔不被 app／test import、不被 pytest 收集（檔名非 test_*）、不掛任何頁；
只讀 `src.ui_v2.compact`／`markup.page_css`／`tokens`，不改 src。
元件 HTML 一律由 compact.py 產出；預覽專用的外框／標註 CSS 全部加 `pv-` 前綴並在頁內標明
「預覽外殼，非 compact 產出」。所有數字、日期、系列名皆為夾具（※示意），禁止當投資結論。
"""
from __future__ import annotations

import math
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.ui_v2 import compact as C  # noqa: E402
from src.ui_v2 import markup, tokens  # noqa: E402

OUT = ROOT / "docs" / "vnext" / "phase3_preview"
NAN = float("nan")

# ── 夾具字串：逐字抄自 src/ui/views/_market_blocks.py（不 import：該檔 import streamlit／services）──
CHART_A_TITLE = "圖A 🇹🇼 台股趨勢"
CHART_A_SAY = "看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。"
CHART_A_MA_DISCLAIMER = "均線為參考，不等於正式台股趨勢判斷。"
CHART_B_TITLE = "圖B 🌍 國際趨勢"
CHART_B_SAY = "看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。"
ZONE1_SORT_NOTE = "排序依據：法人資金動能，非產業趨勢。"
FOLD_LABEL = "▸ 為什麼／來源／限制／去哪補"
NOT_LOADED_REASON = "請按更新"           # 狀態符號與「尚未載入」由 UI_STATE_META 讀，原因字不可自帶符號


def _verify_fixture_strings() -> str:
    """若環境能 import `_market_blocks`，對帳夾具字串；不能就明說沒對帳（不靜默）。"""
    try:
        from src.ui.views import _market_blocks as mb  # type: ignore
    except Exception as e:  # noqa: BLE001 - 預覽工具，對帳失敗只回報
        return f"未對帳（import _market_blocks 失敗：{type(e).__name__}）"
    pairs = {
        "CHART_A_TITLE": CHART_A_TITLE, "CHART_A_SAY": CHART_A_SAY,
        "CHART_A_MA_DISCLAIMER": CHART_A_MA_DISCLAIMER, "CHART_B_TITLE": CHART_B_TITLE,
        "CHART_B_SAY": CHART_B_SAY,
    }
    bad = [k for k, v in pairs.items() if getattr(mb, k, None) != v]
    return "已對帳 5 條逐字句，全部相等" if not bad else f"⚠ 夾具與常數不符：{bad}"


# ══════════════════════════════════════════════════════════════════
# 預覽外殼（pv-*：非 compact 產出）
# ══════════════════════════════════════════════════════════════════
PV_CSS = """
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--paper);color:var(--ink);font-family:"Noto Sans CJK TC","PingFang TC","Microsoft JhengHei","WenQuanYi Zen Hei",system-ui,sans-serif;font-size:14px;line-height:1.5}
.pv-wrap{max-width:940px;margin:0 auto;padding:16px}
.pv-h1{font-size:18px;margin:0 0 4px}
.pv-banner{font-size:12px;color:var(--ink-3);border:1px solid var(--rule);padding:6px 10px;margin:0 0 14px}
.pv-state{margin:18px 0 6px;font-size:12px;font-weight:700;color:var(--ink-2);letter-spacing:.04em}
.pv-state b{color:var(--sig-blue)}
.pv-card{background:var(--panel);border:1px solid var(--rule-2);border-radius:2px;padding:12px}
.pv-note{font-size:11.5px;color:var(--ink-3);margin:6px 0 0}
.pv-fold{border-top:1px solid var(--rule);margin-top:10px;padding-top:6px;font-size:12.5px;color:var(--ink-2)}
.pv-fold .t{color:var(--ink);font-size:13px}
.pv-fold dl{margin:6px 0 0;display:grid;grid-template-columns:auto 1fr;gap:2px 10px}
.pv-fold dt{color:var(--ink-3)} .pv-fold dd{margin:0}
.pv-native{height:var(--h,220px);border:1px dashed var(--rule-2);display:flex;align-items:center;justify-content:center;position:relative;background:var(--grid);color:var(--ink-3);font-size:12px;overflow:hidden}
.pv-native svg{position:absolute;inset:0;width:100%;height:100%}
.pv-native span{position:relative;background:var(--panel);padding:1px 6px}
.pv-row3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.pv-row2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.pv-cell{display:flex;flex-direction:column;gap:4px;align-items:flex-start;min-width:0}
.pv-cap{font-size:11.5px;color:var(--ink-3)}
.pv-list{margin:6px 0;padding:0;list-style:none}
.pv-list li{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--rule);min-height:36px;align-items:center}
.pv-list .r{color:var(--ink-3);width:18px}
.pv-list .v{margin-left:auto;font-family:var(--mono);color:var(--ink-2)}
.pv-allbtn{display:flex;align-items:center;min-height:var(--cp-touch-min);color:var(--ink-2)}
.pv-seg{display:inline-flex;border:1px solid var(--rule-2);border-radius:999px;padding:2px;gap:2px}
.pv-seg span{padding:6px 14px;border-radius:999px;color:var(--ink-2);min-height:var(--cp-touch-min);display:inline-flex;align-items:center}
.pv-seg span.on{background:var(--cta-primary-bg);color:var(--cta-primary-fg)}
table.pv-t{border-collapse:collapse;width:100%;font-size:12.5px}
table.pv-t th,table.pv-t td{border:1px solid var(--rule);padding:5px 8px;text-align:left;vertical-align:top}
table.pv-t th{color:var(--ink-3);font-weight:600}
.pv-sw{display:inline-block;width:14px;height:14px;border:1px solid #888;vertical-align:-2px;margin-right:6px}
.pv-bgbox{padding:12px;border:1px solid #444;margin:6px 0}
@media (max-width:640px){.pv-wrap{padding:16px}.pv-row3{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""


def page(title: str, body: str, *, mode: str = "dark", extra_state_note: str = "") -> str:
    css = markup.page_css(mode) + "\n" + C.compact_css() + "\n" + PV_CSS
    return (
        "<!doctype html>\n<html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{escape(title)}</title><style>{css}</style></head><body>"
        f"<div class=\"pv-wrap\"><h1 class=\"pv-h1\">{escape(title)}</h1>"
        "<div class=\"pv-banner\">Phase 3 離線靜態預覽｜元件 HTML 由 <code>compact.py</code> 產出，"
        "<code>pv-</code> 前綴為預覽外殼（非元件）｜資料全為夾具 ※示意，禁止當投資結論"
        f"｜mode={mode}{extra_state_note}</div>{body}</div></body></html>"
    )


def state(label: str) -> str:
    return f'<div class="pv-state"><b>●</b> {escape(label)}</div>'


def native_mock(h: int, label: str) -> str:
    """Primary 原生圖位置的『示意框』（Streamlit 原生 Vega 圖不能放進靜態 HTML，故以灰框＋假折線佔位）。"""
    pts = " ".join(f"{i * 10:.0f},{60 + 25 * math.sin(i / 3.2) - i * 0.5:.1f}" for i in range(0, 101))
    return (f'<div class="pv-native" style="--h:{h}px"><svg viewBox="0 0 1000 120" preserveAspectRatio="none">'
            f'<polyline points="{" ".join(f"{i*10},{60+18*math.sin(i/3.2)-i*0.15:.1f}" for i in range(101))}" '
            'fill="none" stroke="#5b6b7a" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>'
            f'<span>{escape(label)}</span></div>')


def fold_open() -> str:
    return ('<div class="pv-fold"><div class="t">▾ 為什麼／來源／限制／去哪補'
            '（靜態展開示意區，非 compact 元件）</div><dl>'
            '<dt>為什麼</dt><dd>判讀說明全文（※示意）</dd>'
            '<dt>來源</dt><dd>Yahoo；資料日 10/28；每日更新（※示意）</dd>'
            '<dt>限制</dt><dd>近 252 日；均線為最新值水平參考線（※示意）</dd>'
            '<dt>去哪補</dt><dd>請按頁首「更新」（※示意）</dd></dl></div>')


def fold_open_with_overflow(overflow: tuple) -> str:
    src = "、".join(c.text for c in overflow) or "—"
    return fold_open().replace("Yahoo；資料日 10/28；每日更新（※示意）",
                               f"被擠出的 chip：{escape(src)}；資料日 10/28（※示意）")


def fold_closed() -> str:
    return f'<div class="pv-fold"><div class="t">{FOLD_LABEL}</div></div>'


# ══════════════════════════════════════════════════════════════════
# 元件頁
# ══════════════════════════════════════════════════════════════════
def pg_chips(mode: str = "dark") -> str:
    def row(chips) -> str:
        html, ov = C.chips_html(chips)
        return html + (f'<div class="pv-note">溢出 → 摺疊：{[c.text for c in ov]}</div>' if ov else "")

    b = []
    b.append(state("冷啟動（未載入）：護欄 chip 單獨；「尚未載入」由槽承載，chip 列不重複"))
    b.append(row([C.meta_chip("not_defined")]))
    b.append(state("已載入 live（資訊族＋狀態族）"))
    b.append(row([C.meta_chip("asof", "10/28"), C.meta_chip("source", "Yahoo"),
                  C.meta_chip("window", "近 252 日"), C.meta_chip("readable")]))
    b.append(state("已載入 過期（琥珀，不是紅）"))
    b.append(row([C.meta_chip("asof", "10/21"), C.meta_chip("stale", "7 天"),
                  C.meta_chip("window", "近 252 日")]))
    b.append(state("護欄族（D3=A 實線粗框）與資訊族並排比較"))
    b.append(row([C.guard_chip(CHART_A_MA_DISCLAIMER), C.meta_chip("not_defined"),
                  C.meta_chip("data_quality"), C.meta_chip("estimated"),
                  C.meta_chip("asof", "10/28")]))
    b.append(state("狀態族各態（讀 UI_STATE_META）"))
    sts = [C.status_chip("idle"), C.status_chip("empty"), C.status_chip("missing_retryable"),
           C.status_chip("not_applicable"), C.status_chip("unwired"), C.status_chip("partial", n=3, m=5),
           C.status_chip("failed")]
    b.append('<div class="cp-chips">' + "".join(C._chip_span(c) for c in sts) + "</div>")
    b.append(state("系統真錯誤（紅只給 failed；原因 1 句在 chip 外）"))
    b.append(row([C.status_chip("failed")]) + '<div class="cp-ch-say">原因：來源逾時（※示意）</div>')
    b.append(state("fx_partial 逐字長 chip（手機換行檢查）"))
    b.append(row([C.meta_chip("fx_partial", verbatim="部分外幣標的未換算，僅供參考", value="2"),
                  C.meta_chip("asof", "10/28")]))
    return page(f"chips（{mode}）", "".join(b), mode=mode)


def pg_header() -> str:
    b = []
    cold, ov0 = C.chart_header_html(
        title=CHART_A_TITLE, chips=[C.guard_chip(CHART_A_MA_DISCLAIMER), C.meta_chip("not_defined")],
        say=CHART_A_SAY, title_verbatim=True, say_verbatim=True)
    b.append(state("圖 A 冷啟動（Primary 圖槽同高 220px；chip 下限 3 顆，這裡只有 2 顆，見 README 發現）"))
    b.append('<div class="pv-card">' + cold + C.chart_slot_missing_html("idle", NOT_LOADED_REASON, height_px=220)
             + fold_closed() + "</div>")
    chips = [C.guard_chip(CHART_A_MA_DISCLAIMER), C.meta_chip("not_defined"), C.meta_chip("asof", "10/28"),
             C.meta_chip("source", "Yahoo"), C.meta_chip("window", "近 252 日"), C.meta_chip("readable")]
    live, ov = C.chart_header_html(title=CHART_A_TITLE, chips=chips, say=CHART_A_SAY,
                                   title_verbatim=True, say_verbatim=True)
    b.append(state("圖 A 已載入（傳入 6 顆 → 外露 5 顆；來源溢出到摺疊，D10=a）"))
    b.append('<div class="pv-card">' + live + native_mock(220, "※原生折線圖示意（Primary ≤220px；非 compact 產出）")
             + fold_open_with_overflow(ov) + "</div>")
    b.append(f'<div class="pv-note">溢出（交給 render_fold「來源」段）：{[c.text for c in ov]}</div>')
    liveB, _ = C.chart_header_html(
        title=CHART_B_TITLE, chips=[C.meta_chip("not_defined"), C.meta_chip("asof", "10/28"),
                                    C.meta_chip("window", "近 120 日")],
        say=CHART_B_SAY, title_verbatim=True, say_verbatim=True)
    b.append(state("圖 B header（已載入；3 顆 chip，下限）"))
    b.append('<div class="pv-card">' + liveB + fold_closed() + "</div>")
    return page("chart header", "".join(b))


def pg_missing() -> str:
    b = []
    b.append(state("Primary（variant=primary）：同高 220px，各狀態（符號與狀態字讀 UI_STATE_META）"))
    for st_, why in (("idle", "請按更新"), ("empty", "此區間來源沒有資料"), ("failed", "來源逾時，稍後重試"),
                     ("unwired", "此圖尚未接線")):
        b.append('<div class="pv-card" style="margin-bottom:8px">'
                 + C.chart_slot_missing_html(st_, why, height_px=220)
                 + f'<div class="pv-note">state={st_}'
                 + '（高 220，四態傳同一 height_px）' + "</div></div>")
    b.append(state("Secondary（variant=secondary，D6=B）：縮成一行，不隱藏 Missing"))
    b.append('<div class="pv-card">')
    for st_, why in (("idle", "請按更新"), ("empty", "此區間來源沒有資料"),
                     ("missing_retryable", "來源暫時讀不到，可重跑一次"),
                     ("not_applicable", "此標的沒有這項資料"), ("failed", "來源逾時")):
        b.append(C.chart_slot_missing_html(st_, why, variant="secondary"))
    b.append(C.chart_slot_missing_html("partial", "其餘來源缺漏", variant="secondary", n=3, m=5))
    b.append("</div>")
    b.append(state("Secondary 原因文字很長（換行檢查）"))
    b.append('<div class="pv-card">' + C.chart_slot_missing_html(
        "empty", "上游這一輪只回傳部分標的而且日期落在窗口之外，已依規則排除不畫", variant="secondary") + "</div>")
    return page("Missing 槽", "".join(b))


def pg_tile(vp_mobile: bool = False) -> str:
    grp, _ = C.chips_html([C.meta_chip("asof", "10/28"), C.meta_chip("readable")])
    sp = C.sparkline_svg([18 + 3 * math.sin(i / 3) for i in range(30)], title="VIX 近 30 日",
                         missing_state="idle", missing_text=NOT_LOADED_REASON)
    sp_ph = C.sparkline_svg([NAN] * 30, title="VIX 近 30 日", missing_state="idle",
                            missing_text=NOT_LOADED_REASON)
    t_loaded = [
        C.kpi_tile_html(label="市場位階", value="震盪", say="市場位階，不是台股趨勢"),
        C.kpi_tile_html(label="VIX", value="18.4", chips=[C.meta_chip("window", "近 30 日")], spark=sp),
        C.kpi_tile_html(label="建議總持股水位", value="5 成", chips=[C.meta_chip("estimated")],
                        say="估算，非建議"),
    ]
    t_cold = [
        C.kpi_tile_html(label="市場位階", value=None, chips=[C.status_chip("idle")]),
        C.kpi_tile_html(label="VIX", value=None, chips=[C.status_chip("idle")]),   # F3 修正後：冷啟動不傳 placeholder spark
        C.kpi_tile_html(label="建議總持股水位", value=None, chips=[C.meta_chip("not_approved")],
                        say="風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate", say_verbatim=True),
    ]
    long_val = C.kpi_tile_html(label="市場位階", value="高檔震盪偏弱格局", say="市場位階，不是台股趨勢")
    stale_t = C.kpi_tile_html(label="外資買賣超", value="+12.3 億", chips=[C.meta_chip("stale", "7 天")])
    cls = "pv-row2" if vp_mobile else "pv-row3"
    b = []
    b.append(state("已載入（頁級 chip 列整列共用一次；tile 內無資料日）"))
    b.append(grp + f'<div class="{cls}">' + "".join(t_loaded) + "</div>")
    b.append(state("冷啟動（主值留白 → 必有說明原因的 chip；tile 高 ≥96px）"))
    b.append(f'<div class="{cls}">' + "".join(t_cold) + "</div>")
    b.append(state("邊界：12 字主值（2 欄手機寬度 U2）與過期 tile"))
    b.append(f'<div class="{cls}">' + long_val + stale_t + "</div>")
    b.append('<div class="pv-note">預覽外殼的列欄數（桌 3／手 2）只是示意；欄數待 W9（CV1-DR-12），compact 不假設。'
             '※ 建議總持股水位 的 5 成為夾具。</div>')
    return page("KPI tile", "".join(b))


def pg_spark() -> str:
    def cellx(name, vals, win="近 30 日", w=100, h=48, ms="idle"):
        sv = C.sparkline_svg(vals, w=w, h=h, title=f"{name}（{win}）", missing_state=ms,
                             missing_text=NOT_LOADED_REASON if ms == "idle" else "此區間沒有資料")
        return (f'<div class="pv-cell"><div class="pv-cap">{escape(name)}</div>{sv}'
                f'<span class="cp-chip cp-info">{escape(win)}</span></div>')
    smooth = [18 + 3 * math.sin(i / 3) for i in range(30)]
    gap = list(smooth)
    for i in range(10, 16):
        gap[i] = NAN
    b = [state("已載入：連續 / 中段缺口 / 末端缺值 / 孤立點")]
    b.append('<div class="pv-card"><div class="pv-row3">'
             + cellx("連續 30 點", smooth) + cellx("中段缺口(6 點 NaN)", gap)
             + cellx("[1,2,nan]", [1, 2, NAN], "近 3 日")
             + cellx("[1,nan,3]", [1, NAN, 3], "近 3 日") + cellx("[3,nan,1,nan,2]", [3, NAN, 1, NAN, 2], "近 5 日")
             + cellx("等值(平線)", [5.0] * 10, "近 10 日") + "</div></div>")
    b.append(state("冷啟動／缺值：全 NaN、有效點 <2（placeholder，不顯示數字）"))
    b.append('<div class="pv-card"><div class="pv-row3">'
             + cellx("全 NaN（idle）", [NAN] * 30) + cellx("[1,nan,nan]（empty）", [1, NAN, NAN], ms="empty")
             + cellx("空序列（idle）", []) + "</div></div>")
    b.append(state("最大尺寸 h=64（A6 上限）與 w=120"))
    b.append('<div class="pv-card">' + cellx("64px 高", smooth, w=120, h=64) + "</div>")
    b.append('<div class="pv-note">窗口 chip 為預覽外殼手寫的 cp-chip（sparkline 旁必須有可見窗口）；'
             '圖本身由 sparkline_svg 產出。</div>')
    return page("sparkline", "".join(b))


def pg_sm() -> str:
    def sv(name, vals):
        return C.SmCell(name, C.sparkline_svg(vals, w=160, h=64, title=name, missing_state="idle",
                                              missing_text=NOT_LOADED_REASON))
    series = [("道瓊 DJI", [100 + 6 * math.sin(i / 5) + i * .3 for i in range(60)]),
              ("那指 IXIC", [100 + 9 * math.sin(i / 4) + i * .5 for i in range(60)]),
              ("費半 SOX", [100 + 14 * math.sin(i / 6) - i * .2 for i in range(60)]),
              ("美債 10Y", [4 + .3 * math.sin(i / 7) for i in range(60)])]
    cells5 = [sv(n, v) for n, v in series] + [C.SmCell("美元 DXY", None, None, "empty", "本輪沒有這個系列")]
    grp, _ = C.chips_html([C.meta_chip("asof", "10/28"), C.meta_chip("window", "近 120 日")])
    hdr, _ = C.chart_header_html(title=CHART_B_TITLE, chips=[C.meta_chip("not_defined")] + [
        C.meta_chip("asof", "10/28"), C.meta_chip("window", "近 120 日")], say=CHART_B_SAY,
        title_verbatim=True, say_verbatim=True)
    b = [state("已載入 5 格（含缺系列格 美元 DXY；桌 3 欄／手 2 欄；格內無資料日、無數字）")]
    b.append('<div class="pv-card">' + hdr + C.small_multiples_html(cells5) + fold_closed() + "</div>")
    b.append(state("格內窗口 chip（僅窗口與組級不同時）"))
    wc = [C.SmCell("道瓊 DJI", cells5[0].svg, C.meta_chip("window", "近 60 日")), cells5[1], cells5[2]]
    b.append('<div class="pv-card">' + C.small_multiples_html(wc) + "</div>")
    b.append(state("冷啟動（D6=B）：整組縮成一行 Missing；Primary 不受影響"))
    cold_hdr, _ = C.chart_header_html(title=CHART_B_TITLE, chips=[C.meta_chip("not_defined")], say=CHART_B_SAY,
                                      title_verbatim=True, say_verbatim=True)
    b.append('<div class="pv-card">' + cold_hdr
             + C.chart_slot_missing_html("idle", NOT_LOADED_REASON, variant="secondary") + fold_closed() + "</div>")
    b.append(state("冷啟動若改為每格各自 Missing（對照：Secondary 5 格逐一縮一行）"))
    cold_cells = [C.SmCell(n, None, None, "idle", NOT_LOADED_REASON) for n, _v in series] + [
        C.SmCell("美元 DXY", None, None, "idle", NOT_LOADED_REASON)]
    b.append('<div class="pv-card">' + C.small_multiples_html(cold_cells) + "</div>")
    return page("small multiples", "".join(b))


def pg_topn() -> str:
    rows = [(f"產業 {chr(65 + i % 26)}{i // 26 or ''}", f"{(90 - i * 2.1):.1f}") for i in range(36)]
    tv = C.topn_view(rows, 5)
    li = "".join(f'<li><span class="r">{i + 1}</span><span>{escape(n)}</span><span class="v">{v}</span></li>'
                 for i, (n, v) in enumerate(tv.shown))
    more = C.chips_html([tv.more_chip()])[0]   # F10：TopN.more_chip()
    grp, _ = C.chips_html([C.meta_chip("asof", "10/28")])
    b = [state("已載入 Top-5 / 共 36（排序依據句維持現況說明句，非 chip；列內無資料日）")]
    b.append('<div class="pv-card"><div class="cp-ch-say" style="margin-top:0">' + escape(ZONE1_SORT_NOTE)
             + "</div>" + grp + f'<ul class="pv-list">{li}</ul>'
             + f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">{more}'
             f'<span class="pv-allbtn">{escape(tv.all_label or "")}</span></div></div>')
    b.append('<div class="pv-note">「另 K 筆見全部」chip 由 TopN.more_chip() 產生（F10 已修）。</div>')
    b.append(state("n 大於總數（hidden=0，不顯示『另 K 筆』與『查看全部』）"))
    tv2 = C.topn_view(rows[:3], 5)
    li2 = "".join(f'<li><span class="r">{i + 1}</span><span>{escape(n)}</span><span class="v">{v}</span></li>'
                  for i, (n, v) in enumerate(tv2.shown))
    b.append(f'<div class="pv-card"><ul class="pv-list">{li2}</ul>'
             f'<div class="pv-note">more_text={tv2.more_text!r} all_label={tv2.all_label!r}</div></div>')
    b.append(state("冷啟動／空清單：呼叫端須另行處理為 Missing（TopN.empty）"))
    te = C.topn_view([], 5)
    b.append('<div class="pv-card">' + C.chart_slot_missing_html("idle", NOT_LOADED_REASON, variant="secondary")
             + f'<div class="pv-note">TopN.empty={te.empty}（空清單不是「0 筆結果」）</div></div>')
    return page("Top-N 切片", "".join(b))


def pg_segment() -> str:
    spec = C.segment_options(["台股", "海外市場", "利率", "美元", "台股"], "台股")
    dedup_note = "輸入 ['台股','海外市場','利率','美元','台股'] → 去重保序"
    seg = '<div class="pv-seg">' + "".join(
        f'<span class="{"on" if o == spec.default else ""}">{escape(o)}</span>' for o in spec.options) + "</div>"
    try:
        C.segment_options(["台股", "利率"], "美元")
        bad = "未擋（⚠）"
    except ValueError as e:
        bad = f"ValueError：{e}"
    b = [state("segment_options 的資料輸出（compact 只產出資料；widget 在後續步驟由 _ui_kit 包 st.segmented_control）")]
    b.append('<div class="pv-card"><table class="pv-t"><tr><th>項目</th><th>值</th></tr>'
             f'<tr><td>輸入</td><td>{escape(dedup_note)}</td></tr>'
             f'<tr><td>options</td><td>{escape(str(spec.options))}</td></tr>'
             f'<tr><td>default</td><td>{escape(spec.default)}（index={spec.default_index}）</td></tr>'
             f'<tr><td>default 不在 options</td><td>{escape(bad)}</td></tr></table></div>')
    b.append(state("預覽外殼自繪的膠囊（pv-seg，僅示意 D8=B 外觀；不是 st 元件、不是 compact 產出）"))
    b.append('<div class="pv-card">' + seg + '<div class="pv-note">高 ≥44px 觸控區（--cp-touch-min）；'
             '真實 widget 外觀以 floor 1.56 實跑為準（步驟 4）。</div></div>')
    return page("segment", "".join(b))


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def cr(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + .05) / (lo + .05)


def contrast_rows() -> list[tuple[str, str, str, float, float]]:
    """(用途, fg token, bg token, dark 對比, light 對比)；token 值取自 tokens.DARK/LIGHT。"""
    pairs = [("資訊 chip 字 / 面板", "--ink-2", "--panel"), ("資訊 chip 字 / 頁底", "--ink-2", "--paper"),
             ("護欄 chip 字 / 面板", "--ink", "--panel"), ("綠 chip", "--sig-green", "--sig-green-bg"),
             ("琥珀 chip", "--sig-amber", "--sig-amber-bg"), ("紅 chip", "--sig-red", "--sig-red-bg"),
             ("灰 chip(⬜ 等)", "--sig-grey", "--sig-grey-bg"), ("Missing 槽字 / 面板", "--sig-grey", "--panel"),
             ("Missing 槽字 / 頁底", "--sig-grey", "--paper"), ("tile 標籤 / 面板", "--ink-2", "--panel"),
             ("次要墨 ink-3 / 面板", "--ink-3", "--panel"), ("資訊 chip 邊框 ink-3 / 面板（F6 現行）", "--ink-3", "--panel"),
             ("〔舊〕chip 細邊框 rule-2 / 面板（F6 前；現已不用）", "--rule-2", "--panel"),
             ("護欄粗框 ink-2 / 面板", "--ink-2", "--panel")]
    out = []
    for name, f, bgk in pairs:
        vals = []
        for m in ("dark", "light"):
            vals.append(cr(str(tokens.get_token(f, mode=m)), str(tokens.get_token(bgk, mode=m))))
        out.append((name, f, bgk, vals[0], vals[1]))
    return out


def pg_palette() -> str:
    bgs = [("D1a/D1b：config.toml [theme]", "#0e1117"), ("D1b 現況：tokens --paper", "#0e141b"),
           ("D1b 現況：blueprint market.html --bg", "#0a0e16")]
    b = [state("D1a 維持（客戶裁示色，Phase 3 不改）")]
    rows = ""
    for nm in ("--cta-primary-bg", "--cta-primary-fg", "--sig-neutral", "--sig-neutral-bg"):
        rows += (f'<tr><td>{nm}</td><td><span class="pv-sw" style="background:{tokens.get_token(nm, mode="dark")}"></span>'
                 f'{tokens.get_token(nm, mode="dark")}</td><td><span class="pv-sw" style="background:{tokens.get_token(nm, mode="light")}"></span>'
                 f'{tokens.get_token(nm, mode="light")}</td></tr>')
    b.append('<div class="pv-card"><table class="pv-t"><tr><th>token</th><th>dark</th><th>light</th></tr>'
             + rows + "</table><div class=\"pv-note\">light 的 --sig-neutral/-bg 為 AI 總管暫選值（可被推翻）。"
             "按鈕白字對比 " + f"{cr('#ffffff', '#1f6feb'):.2f}:1（dark）／{cr('#ffffff', '#044cb6'):.2f}:1（light）"
             "</div></div>")
    b.append(state("D1b 現況：三套頁底色並排，同一組 chip／Missing 槽放在各底色上（Phase 3 不收斂，僅供對照）"))
    cell = (C.chips_html([C.meta_chip("asof", "10/28"), C.meta_chip("readable"), C.meta_chip("not_defined")])[0]
            + '<div class="cp-chips">' + C._chip_span(C.status_chip("failed")) + "</div>"
            + C.chart_slot_missing_html("idle", NOT_LOADED_REASON, variant="secondary"))
    for label, hexv in bgs:
        b.append(f'<div class="pv-bgbox" style="background:{hexv}"><div class="pv-cap" style="color:#aab">'
                 f'<span class="pv-sw" style="background:{hexv}"></span>{escape(label)} {hexv}</div>{cell}</div>')
    b.append(state("元件色彩對比（WCAG 相對亮度公式，本預覽腳本計算；文字 AA 需 ≥4.5，非文字邊框 ≥3）"))
    t = '<table class="pv-t"><tr><th>用途</th><th>前景 / 背景 token</th><th>dark</th><th>light</th></tr>'
    for name, f, bgk, d, l in contrast_rows():
        flag_d = " ⚠" if d < 4.5 else ""
        flag_l = " ⚠" if l < 4.5 else ""
        t += f"<tr><td>{escape(name)}</td><td>{f} / {bgk}</td><td>{d:.2f}{flag_d}</td><td>{l:.2f}{flag_l}</td></tr>"
    b.append('<div class="pv-card">' + t + "</table></div>")
    return page("色票並排表", "".join(b))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pages = {
        "chips": pg_chips("dark"), "chips_light": pg_chips("light"), "chart_header": pg_header(),
        "missing_slot": pg_missing(), "kpi_tile": pg_tile(False), "kpi_tile_m": pg_tile(True),
        "sparkline": pg_spark(), "small_multiples": pg_sm(), "topn": pg_topn(), "segment": pg_segment(),
        "palette": pg_palette(),
    }
    for name, html in pages.items():
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    print("fixture check:", _verify_fixture_strings())
    print("wrote", len(pages), "pages to", OUT)


if __name__ == "__main__":
    main()
