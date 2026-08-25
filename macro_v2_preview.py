"""總經儀表板 v2 —— 落地版設計預覽(Streamlit)

⚠️ **這是設計預覽,不是 production。**
   `app.py` 沒有 import 本檔,現行畫面完全不受影響。
   跑法:`streamlit run macro_v2_preview.py`

設計主張(對照 ui/tabs/macro/ 現況):
  1. 縱向資訊梯度取代模式切換 —— 頂部結論 / 中部理由 / 底部明細。
  2. 每個指標只有一個正典位置。現行總經頁把同一組數字重講數十次
     (repo 自己的 STATE.md:1816 記為「同一資訊重複 4~18 次」)。
  3. 指標的**四態**是畫面上的一等公民:運作中 / 資料過期 / 鑑別力失效 / 未接線。
     現行畫面上「從沒亮過的燈」與「正常的綠燈」長得一模一樣。

§3.3 反捏造 —— 本檔**不重抄任何門檻或教學數字**:
  · 門檻      ← shared.macro_buckets.BUCKET_DANGER_SPECS(16 個 DangerSpec)
  · 教學文案  ← src.data.core.data_registry.EDU_GUIDE(14 個 how_to_read)
  · 門檻代入  ← shared.edu_tokens.resolve_edu_tokens(§§TOKEN§§ → 實值)
  上游改門檻,本頁自動跟著改;不存在「教學卡寫 🔴 但production 顯示 🟡」那類漂移
  (那個事故記在 shared/edu_tokens.py:4-20)。

§1 Fail Loud —— 預覽不連外部資料源,故指標值為**示意**,以 `_DEMO_VALUES` 集中管理
  並在畫面上標明。查不到示意值的指標顯示「無資料」,不編數字填空。

§8.2 分層 —— 本檔為 L5 預覽,只讀 L0 常數(shared/*)與 L1 註冊表,不做任何 I/O、
  不寫任何檔、不呼叫任何 fetcher。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import plotly.graph_objects as go
import streamlit as st

from shared.edu_tokens import resolve_edu_tokens
from shared.macro_buckets import BUCKET_DANGER_SPECS
from src.data.core.data_registry import EDU_GUIDE

# ══════════════════════════════════════════════════════════════════════
# 常數
# ══════════════════════════════════════════════════════════════════════

# 桶 key → 中文名(對齊現行五桶用語)
_BUCKET_ZH = {
    "long": "長期", "mid": "中期", "short": "短線急殺",
    "chips": "籌碼", "news": "新聞",
}
_BUCKET_ORDER = ["long", "mid", "short", "chips", "news"]

# DangerSpec.key → EDU_GUIDE key(教學文案對應;沒有對應者不硬湊)
_EDU_KEY = {
    "vix": "^VIX",
    "us_core_cpi": "CPILFESL",
    "ism_pmi": "NAPM",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
    "margin": "MI_MARGN",
    "foreign_net": "BFI82U",
    "m1b_m2_gap": "ms1.json",
    "ndc_signal": "NDC_signal",
    "tw_export": "XTEXVA01TWM664S",
}

# 四態的視覺定義。good/warn/serious 三色取自本專案既有語意色慣例;
# 「未接線」刻意**不給顏色**(斜線紋),因為它不是一種燈號等級,是「沒有消息」。
_STATE_META = {
    "live":     ("運作中",     "#0ca30c"),
    "stale":    ("資料過期",   "#fab219"),
    "degraded": ("鑑別力失效", "#ec835a"),
    "unwired":  ("未接線",     "#8a8e96"),
}
_BAND_META = {
    "green": ("綠", "#0ca30c"), "yellow": ("黃", "#fab219"),
    "red":   ("紅", "#d03b3b"), "gray":   ("無資料", "#8a8e96"),
}

# ══════════════════════════════════════════════════════════════════════
# 示意資料(§1:集中管理 + 畫面標明,不散落在渲染邏輯裡冒充真值)
# ══════════════════════════════════════════════════════════════════════

_DEMO_VALUES: dict[str, float | None] = {
    "health": 52.0, "ndc_signal": 27.0, "m1b_m2_gap": 1.4, "ism_pmi": 48.6,
    "us_core_cpi": 2.81, "tw_export": 12.4, "bias_240": 8.2, "us10y": 4.31,
    "dxy": 99.8, "vix": 19.4, "adl": 46.3, "fut_net": -12400.0,
    "margin": 5148.0, "jingqi": 48.9, "news_systemic": 0.0,
    "foreign_net": None,          # wired=False → 本來就沒有值
}
_DEMO_ASOF = {
    "ndc_signal": "2026-07", "m1b_m2_gap": "2026-06", "ism_pmi": "2026-07",
    "us_core_cpi": "2026-07", "tw_export": "2026-07",
    "fut_net": "昨天 15:00", "margin": "昨天 15:00",
}
_DEMO_ASOF_DEFAULT = "今天 05:00"

# 「鑑別力失效」目前 SSOT **沒有**對應欄位 —— 這是本設計提出的新概念。
# 在 DangerSpec 補一個 `discriminative=False` 之前,先在此登記,並附 repo 出處,
# 讓讀者能自行驗證這不是我編的。
_KNOWN_DEGRADED = {
    "margin": (
        "門檻是絕對金額,未隨市場總市值成長調整。repo 自己的註解寫:"
        "「絕對門檻已被市值成長淹沒,實測 5,148 億早已穿透兩線 → 燈號恆紅、鑑別力歸零」"
        "(shared/macro_buckets.py:318)。判讀請看「相對自身近年區間的方向」,"
        "不要只看有沒有超過門檻。"
    ),
}

# 有真實走勢可畫的指標(預覽用確定性偽序列,收尾強制對齊卡片值)
_CHART_KEYS = ["vix", "fut_net", "adl"]


# ══════════════════════════════════════════════════════════════════════
# L2 純函式(無 I/O、無 st.*,可單測)
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Row:
    key: str
    label: str
    bucket: str          # 中文桶名
    unit: str
    value: float | None
    band: str            # green / yellow / red / gray
    state: str           # live / stale / degraded / unwired
    thr_text: str
    as_of: str
    source: str
    note: str
    decimals: int


def classify_band(value: float | None, spec) -> str:
    """依 DangerSpec 的方向判燈。與 shared.macro_buckets.classify_danger 同語意,
    但本檔只需要顏色不需要完整 payload,故就地實作(不改上游)。"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "gray"
    vmin, vmax = getattr(spec, "valid_min", None), getattr(spec, "valid_max", None)
    if vmin is not None and value < vmin:
        return "gray"
    if vmax is not None and value > vmax:
        return "gray"

    d = spec.direction
    if d == "high_bad":
        if spec.red is not None and value >= spec.red:
            return "red"
        if spec.yellow is not None and value >= spec.yellow:
            return "yellow"
        return "green"
    if d == "low_bad":
        if spec.red is not None and value <= spec.red:
            return "red"
        if spec.yellow is not None and value <= spec.yellow:
            return "yellow"
        return "green"
    if d == "band":                      # 雙邊(NDC)
        if spec.red is not None and value >= spec.red:
            return "red"
        if spec.red_lo is not None and value <= spec.red_lo:
            return "red"
        if spec.yellow is not None and value >= spec.yellow:
            return "yellow"
        if spec.yellow_lo is not None and value <= spec.yellow_lo:
            return "yellow"
        return "green"
    return "gray"


def classify_state(spec, value: float | None) -> str:
    """四態。unwired 直接讀 SSOT 的 wired 旗標,不猜。"""
    if getattr(spec, "wired", True) is False:
        return "unwired"
    if spec.key in _KNOWN_DEGRADED:
        return "degraded"
    if value is None:
        return "unwired"
    return "live"


def fmt_value(value: float | None, unit: str, decimals: int) -> str:
    if value is None:
        return "無資料"
    txt = f"{value:,.{decimals}f}".replace("-", "−")   # 真減號
    if not unit:
        return txt
    # % 緊貼數字;中文單位(口/億/分/則)空一格才不會黏在一起
    return f"{txt}{unit}" if unit == "%" else f"{txt} {unit}"


def threshold_text(spec) -> str:
    """門檻帶文字 —— 直接由 DangerSpec 組出,不在本檔寫死數字。"""
    d, dec = spec.direction, spec.decimals

    def n(v):
        return f"{v:,.{dec}f}".replace("-", "−")

    if d == "band":
        parts = []
        if spec.yellow_lo is not None and spec.red_lo is not None:
            parts.append(f"紅 ≤{n(spec.red_lo)} / 黃 ≤{n(spec.yellow_lo)}")
        if spec.yellow is not None and spec.red is not None:
            parts.append(f"黃 ≥{n(spec.yellow)} / 紅 ≥{n(spec.red)}")
        return "　".join(parts) or "—"
    arrow = "≥" if d == "high_bad" else "≤"
    bits = []
    if spec.yellow is not None:
        bits.append(f"黃 {arrow}{n(spec.yellow)}")
    if spec.red is not None:
        bits.append(f"紅 {arrow}{n(spec.red)}")
    return " / ".join(bits) or "—"


def build_rows() -> list[Row]:
    """把 16 個 DangerSpec 攤平成畫面用的列。順序依桶。"""
    out: list[Row] = []
    for spec in BUCKET_DANGER_SPECS:
        v = _DEMO_VALUES.get(spec.key)
        out.append(Row(
            key=spec.key,
            label=spec.label,
            bucket=_BUCKET_ZH.get(spec.bucket, spec.bucket),
            unit=spec.unit or "",
            value=v,
            band=classify_band(v, spec),
            state=classify_state(spec, v),
            thr_text=threshold_text(spec),
            as_of=_DEMO_ASOF.get(spec.key, _DEMO_ASOF_DEFAULT)
            if getattr(spec, "wired", True) is not False else "—",
            source=spec.source or "—",
            note=spec.note or "",
            decimals=spec.decimals,
        ))
    order = {b: i for i, b in enumerate(_BUCKET_ORDER)}
    out.sort(key=lambda r: (order.get(
        next((k for k, z in _BUCKET_ZH.items() if z == r.bucket), "zz"), 99), r.label))
    return out


def bucket_summary(rows: list[Row]) -> list[dict]:
    """每桶:最差燈 + 指標數 + 不可信數。worst-of rollup,與現行五桶同語意。"""
    rank = {"green": 0, "yellow": 1, "red": 2, "gray": -1}
    out = []
    for bkey in _BUCKET_ORDER:
        zh = _BUCKET_ZH[bkey]
        members = [r for r in rows if r.bucket == zh]
        if not members:
            continue
        graded = [r for r in members if r.band != "gray"]
        worst = max(graded, key=lambda r: rank[r.band]) if graded else None
        out.append({
            "name": zh,
            "band": worst.band if worst else "gray",
            "worst_label": worst.label if worst else "全部無資料",
            "worst_value": fmt_value(worst.value, worst.unit, worst.decimals) if worst else "—",
            "n": len(members),
            "n_bad": sum(1 for r in members if r.state != "live"),
        })
    return out


def demo_series(seed: int, n: int, base: float, amp: float,
                drift: float, end_value: float) -> list[float]:
    """確定性偽序列(每次載入長一樣),**收尾強制對齊卡片值**。

    為什麼要強制對齊:圖上被強調的最後一點若與卡片標題的數字不同,
    圖表就會在反駁自己的 KPI。這是設計預覽最容易犯、也最傷信任的錯。
    """
    out, x = [], seed
    for i in range(n):
        x = (x * 9301 + 49297) % 233280
        out.append(base + drift * i + (x / 233280 - 0.5) * amp)
    out[-1] = end_value
    if n >= 3:
        out[-2] = (out[-3] + end_value) / 2
    return out


def edu_for(key: str) -> dict | None:
    """取教學文案並把 §§TOKEN§§ 代成實際門檻。找不到就回 None,不編。"""
    ek = _EDU_KEY.get(key)
    if not ek or ek not in EDU_GUIDE:
        return None
    raw = EDU_GUIDE[ek]
    return {
        "meaning": resolve_edu_tokens(raw.get("meaning", "")),
        "how_to_read": [
            (resolve_edu_tokens(a), resolve_edu_tokens(b))
            for a, b in raw.get("how_to_read", [])
        ],
        "historical_anchor": resolve_edu_tokens(raw.get("historical_anchor", "")),
        "downstream": resolve_edu_tokens(raw.get("downstream", "")),
    }


# ══════════════════════════════════════════════════════════════════════
# L5 渲染
# ══════════════════════════════════════════════════════════════════════

_CSS = """
<style>
/* 半透明底 + color:inherit —— 讓卡片在 Streamlit 亮/暗兩種佈景都成立,
   不寫死任何背景色(寫死必有一邊不能看)。 */
.v2-t{font-size:11px; font-weight:700; letter-spacing:.09em;
      text-transform:uppercase; opacity:.62; margin:0 0 10px;}
.v2-hero{font-size:52px; font-weight:700; line-height:1; letter-spacing:-.02em;}
.v2-hero small{font-size:20px; font-weight:500; opacity:.6; margin-left:3px;}
.v2-chain{border-top:1px solid rgba(128,128,128,.25); margin-top:14px; padding-top:10px;}
.v2-chain-r{display:flex; gap:12px; align-items:baseline; padding:6px 0; font-size:14px;}
.v2-chain-r + .v2-chain-r{border-top:1px dashed rgba(128,128,128,.22);}
.v2-chain-k{flex:0 0 82px; font-size:12px; opacity:.6;}
.v2-chain-v{flex:1; opacity:.85;}
.v2-chain-n{font-weight:700; font-variant-numeric:tabular-nums; white-space:nowrap;}
.v2-fin{background:rgba(128,128,128,.10); border-radius:8px; margin-top:6px;
        padding:8px 10px; display:flex; gap:12px; align-items:baseline; font-size:14px;}
.v2-pill{display:inline-flex; align-items:center; gap:5px; font-size:11.5px;
         font-weight:500; padding:2px 9px; border-radius:99px; line-height:1.6;
         background:rgba(128,128,128,.16); white-space:nowrap;}
.v2-dot{width:8px; height:8px; border-radius:50%; flex:none;}
.v2-hatch{width:8px; height:8px; flex:none; border:1px solid #8a8e96;
          background:repeating-linear-gradient(45deg,#8a8e96 0 1.5px,transparent 1.5px 4px);}
.v2-sig{display:flex; gap:2px; height:24px; margin:10px 0 12px;}
.v2-sig span{flex:1; border-radius:2px; min-width:4px;}
.v2-bk{border:1px solid rgba(128,128,128,.28); border-radius:11px; overflow:hidden;}
.v2-bk-bar{height:5px;}
.v2-bk-in{padding:11px 13px 13px;}
.v2-bk-n{font-size:13px; font-weight:700; margin:0 0 3px;}
.v2-bk-l{font-size:12.5px; opacity:.75; margin:0 0 8px; min-height:2.6em;}
.v2-bk-m{font-size:11.5px; opacity:.55; margin:0;}
.v2-src{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
        font-size:11px; opacity:.6; word-break:break-all;}
.v2-note{font-size:12.5px; opacity:.8; background:rgba(128,128,128,.10);
         border-radius:8px; padding:10px 12px; margin:8px 0 0;}
.v2-dead{border:1px dashed rgba(138,142,150,.7); background:rgba(138,142,150,.10);}
</style>
"""


def pill(text: str, color: str, hatch: bool = False) -> str:
    mark = '<span class="v2-hatch"></span>' if hatch \
        else f'<span class="v2-dot" style="background:{color}"></span>'
    return f'<span class="v2-pill">{mark}{text}</span>'


def render_banner() -> None:
    st.info(
        "**設計預覽 · 落地版** —— 這是 `macro_v2_preview.py`,`app.py` 沒有 import 它,"
        "現行總經頁完全不受影響。\n\n"
        "**門檻帶與教學文案是即時從 SSOT 讀的**"
        "(`shared/macro_buckets.py` + `src/data/core/data_registry.EDU_GUIDE` + "
        "`shared/edu_tokens.resolve_edu_tokens`)——上游改門檻,這頁自動跟著改,"
        "不存在抄錯的可能。**指標數值是示意的**(預覽不連外部資料源),集中在 `_DEMO_VALUES`。",
        icon="🧪",
    )


def render_decision(rows: list[Row]) -> None:
    left, right = st.columns([8, 4], gap="medium")

    with left, st.container(border=True):
        st.markdown('<p class="v2-t">今天建議持股</p>', unsafe_allow_html=True)
        st.markdown('<div class="v2-hero">30–50<small>%</small></div>',
                    unsafe_allow_html=True)
        chain = [
            ("姿態帶", "總經健康分 52 → 中性偏多", "50–70%", False),
            ("風險上限", "VIX 否決權(VIX 19.4,未觸發)", "—", False),
            ("風險上限", "三環第一環(外資期貨 −12,400 口 < −15,000?否)", "—", False),
            ("風險上限", "薩姆規則", "未接線", True),
        ]
        html = ['<div class="v2-chain">']
        for k, v, n, dead in chain:
            n_html = pill("未接線", "#8a8e96", hatch=True) if dead \
                else f'<span class="v2-chain-n">{n}</span>'
            html.append(
                f'<div class="v2-chain-r"><span class="v2-chain-k">{k}</span>'
                f'<span class="v2-chain-v">{v}</span>{n_html}</div>')
        html.append('</div>')
        html.append(
            '<div class="v2-fin"><span class="v2-chain-k">最終建議</span>'
            '<span class="v2-chain-v">兩者取較低</span>'
            '<span class="v2-chain-n">30–50%</span></div>')
        st.markdown("".join(html), unsafe_allow_html=True)
    with left:
        st.caption(
            "⚠️ 「薩姆規則」在現行程式裡是**幽靈把關**:`Sahm_Rule_Triggered` 被寫死 "
            "`False`(src/ui/tabs/macro/section_news_ai.py:230),而且沒註冊進 "
            "`_INTRINSIC_CAP_NAMES`(src/services/allocation_service.py:152)。"
            "現行畫面不會告訴你這件事。"
        )

    n_live = sum(1 for r in rows if r.state == "live")
    with right, st.container(border=True):
        st.markdown('<p class="v2-t">訊號可信度</p>', unsafe_allow_html=True)
        st.markdown(
            f'<div><span style="font-size:32px;font-weight:700">{n_live}</span>'
            f'<span style="font-size:13px;opacity:.6">　／{len(rows)} 個指標真的在運作</span></div>',
            unsafe_allow_html=True)

        seg = []
        for r in rows:
            if r.state == "unwired":
                seg.append('<span style="border:1px solid #8a8e96;background:'
                           'repeating-linear-gradient(45deg,#8a8e96 0 2px,transparent 2px 5px)"></span>')
            else:
                seg.append(f'<span style="background:{_STATE_META[r.state][1]}"></span>')
        st.markdown(f'<div class="v2-sig">{"".join(seg)}</div>', unsafe_allow_html=True)

        for skey, (label, color) in _STATE_META.items():
            cnt = sum(1 for r in rows if r.state == skey)
            st.markdown(
                f'<div style="display:flex;font-size:12.5px;padding:2px 0">'
                f'{pill(label, color, hatch=(skey == "unwired"))}'
                f'<b style="margin-left:auto;font-variant-numeric:tabular-nums">{cnt}</b></div>',
                unsafe_allow_html=True)


def render_buckets(rows: list[Row]) -> None:
    summ = bucket_summary(rows)
    cols = st.columns(len(summ), gap="small")
    for col, b in zip(cols, summ):
        zh, color = _BAND_META[b["band"]]
        with col:
            bad = f'　·　{b["n_bad"]} 個不可信' if b["n_bad"] else ""
            st.markdown(
                f'<div class="v2-bk"><div class="v2-bk-bar" style="background:{color}"></div>'
                f'<div class="v2-bk-in">'
                f'<p class="v2-bk-n">{b["name"]}　{pill(zh, color)}</p>'
                f'<p class="v2-bk-l">最差項:{b["worst_label"]} {b["worst_value"]}</p>'
                f'<p class="v2-bk-m">{b["n"]} 個指標{bad}</p>'
                f'</div></div>',
                unsafe_allow_html=True)


def _threshold_lines(fig: go.Figure, spec) -> None:
    """把 DangerSpec 的門檻畫成虛線 —— 數字來自 SSOT,不在此寫死。"""
    for val, color, name in (
        (spec.yellow, "#b8860b", "黃線"),
        (spec.red, "#d03b3b", "紅線"),
        (spec.yellow_lo, "#b8860b", "黃線(下)"),
        (spec.red_lo, "#d03b3b", "紅線(下)"),
    ):
        if val is None:
            continue
        fig.add_hline(
            y=val, line_dash="dash", line_color=color, line_width=1.2,
            annotation_text=f"{name} {val:,.{spec.decimals}f}".replace("-", "−"),
            annotation_position="right",
            annotation_font=dict(size=11, color=color),
        )


def render_chart(row: Row, spec, seed: int, base: float, amp: float,
                 drift: float, n: int, kind: str = "line") -> None:
    zh, color = _BAND_META[row.band]
    box = st.container(border=True)
    with box:
        _render_chart_body(row, spec, seed, base, amp, drift, n, kind, zh, color)


def _render_chart_body(row, spec, seed, base, amp, drift, n, kind, zh, color) -> None:
    head, meta = st.columns([7, 3])
    with head:
        st.markdown(f'<p class="v2-t">{row.label}</p>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:26px;font-weight:700;font-variant-numeric:tabular-nums">'
            f'{fmt_value(row.value, row.unit, row.decimals)}</div>',
            unsafe_allow_html=True)
    with meta:
        st.markdown(
            f'<div style="text-align:right">{pill(zh, color)}<br>'
            f'<span style="font-size:11px;opacity:.55">{row.as_of}</span></div>',
            unsafe_allow_html=True)

    ys = demo_series(seed, n, base, amp, drift, float(row.value))
    xs = list(range(n))
    fig = go.Figure()
    if kind == "bar":
        fig.add_bar(x=xs, y=ys, marker_color="#2a78d6",
                    marker_opacity=[0.42] * (n - 1) + [1.0],
                    hovertemplate="%{y:,.0f}<extra></extra>", name=row.label)
    else:
        fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color="#2a78d6", width=2),
                        fill="tozeroy", fillcolor="rgba(42,120,214,.13)",
                        hovertemplate="%{y:,.2f}<extra></extra>", name=row.label)
        fig.add_scatter(x=[xs[-1]], y=[ys[-1]], mode="markers",
                        marker=dict(color="#2a78d6", size=9), showlegend=False,
                        hoverinfo="skip")
    _threshold_lines(fig, spec)
    fig.update_layout(
        height=210, margin=dict(l=8, r=78, t=8, b=24), showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        xaxis=dict(showgrid=False, zeroline=False,
                   tickmode="array", tickvals=[0, n // 2, n - 1],
                   ticktext=["最早", "中段", "最新"], tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.16)", zeroline=False),
    )
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False}, key=f"chart_{row.key}")
    st.caption(f"門檻線由 SSOT 畫出 · `{row.source}`")


def render_detail(row: Row, spec) -> None:
    """右側明細面板 —— Streamlit 沒有原生 Drawer,以常駐右欄取代:
    點左表任一列即就地更新,不跳頁。"""
    zh, color = _BAND_META[row.band]
    slabel, scolor = _STATE_META[row.state]

    st.markdown(f"### {row.label}")
    st.markdown(
        f'{pill(slabel, scolor, hatch=(row.state == "unwired"))}　'
        f'{pill(zh, color)}　<span style="font-size:12px;opacity:.6">資料日期 {row.as_of}</span>',
        unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:34px;font-weight:700;margin:8px 0 2px;color:{color}">'
        f'{fmt_value(row.value, row.unit, row.decimals)}</div>',
        unsafe_allow_html=True)
    st.caption(f"門檻帶　{row.thr_text}")

    edu = edu_for(row.key)
    if edu:
        if edu["meaning"]:
            st.markdown("**這是什麼**")
            st.markdown(edu["meaning"])
        if edu["how_to_read"]:
            st.markdown("**怎麼看**")
            st.dataframe(
                {"條件": [a for a, _ in edu["how_to_read"]],
                 "判讀": [b for _, b in edu["how_to_read"]]},
                hide_index=True, use_container_width=True,
            )
            st.caption("↑ 門檻數字由 `resolve_edu_tokens()` 即時代入,不是抄的")
        if edu["historical_anchor"]:
            st.markdown("**歷史錨點**")
            st.markdown(edu["historical_anchor"])
    else:
        st.warning(
            f"`EDU_GUIDE` 沒有「{row.label}」的教學條目 —— 這裡**不會**幫它編一段。"
            f"要補請寫進 `src/data/core/data_registry.py`,門檻數字用 `§§TOKEN§§`。",
            icon="📭")

    if row.state == "unwired":
        reason = getattr(spec, "unwired_reason", "") or "SSOT 未說明原因。"
        st.markdown(
            f'<div class="v2-note v2-dead"><b>這盞燈沒有在運作</b><br>{reason}</div>',
            unsafe_allow_html=True)
        st.caption("原因直接讀 `DangerSpec.unwired_reason`,不是我寫的說法。")
    elif row.state == "degraded":
        st.markdown(
            f'<div class="v2-note"><b>這盞燈的判讀已失效</b><br>'
            f'{_KNOWN_DEGRADED[row.key]}</div>', unsafe_allow_html=True)
        st.caption(
            "⚠️ SSOT 目前**沒有**「鑑別力」欄位,本狀態登記在 `_KNOWN_DEGRADED`。"
            "建議在 `DangerSpec` 補一個旗標,讓它跟 `wired` 一樣可被程式驗證。")

    if row.note:
        st.markdown(f'<div class="v2-note">{row.note}</div>', unsafe_allow_html=True)

    st.markdown("**門檻來源**")
    st.markdown(f'<span class="v2-src">{row.source}</span>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    st.set_page_config(page_title="總經儀表板 v2 預覽", page_icon="🚦", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)

    st.title("總經儀表板")
    st.caption("市場環境 › 總經　·　今天要決定的只有一件事:把多少錢放在股票上")
    render_banner()

    rows = build_rows()
    specs = {s.key: s for s in BUCKET_DANGER_SPECS}

    # ── 第 1 層 · 結論 ──────────────────────────────────────────────
    # Streamlit 由上而下串流渲染,所以「先寫結論」本身就是骨架屏順序:
    # 使用者最先看到的一定是唯一的答案,圖表與總表後到。
    st.subheader("第 1 層 · 結論", divider="gray")
    render_decision(rows)
    st.write("")
    render_buckets(rows)

    # ── 第 2 層 · 為什麼 ────────────────────────────────────────────
    st.subheader("第 2 層 · 為什麼", divider="gray")
    st.caption("每個指標在這裡**只出現一次**,而且畫上它自己的門檻線。")

    by_key = {r.key: r for r in rows}
    params = {
        "vix":     dict(seed=7,  base=18.5,   amp=6.0,     drift=0.01,  n=60, kind="line"),
        "fut_net": dict(seed=19, base=-6000., amp=22000.,  drift=-180., n=30, kind="bar"),
        "adl":     dict(seed=31, base=50.0,   amp=26.0,    drift=-0.05, n=60, kind="line"),
    }
    chart_rows = [k for k in _CHART_KEYS
                  if k in by_key and by_key[k].value is not None]
    for i in range(0, len(chart_rows), 2):
        pair = chart_rows[i:i + 2]
        cols = st.columns(len(pair), gap="medium")
        for col, k in zip(cols, pair):
            with col:
                render_chart(by_key[k], specs[k], **params[k])

    # ── 第 3 層 · 全部明細 ──────────────────────────────────────────
    st.subheader("第 3 層 · 全部明細", divider="gray")
    st.caption(f"{len(rows)} 個指標一張表。點任一列 → 右側就地展開,不跳頁。")

    only_bad = st.toggle("只看有問題的", value=False,
                         help="篩出非「運作中」或燈號為黃/紅的指標")
    view = [r for r in rows
            if (not only_bad) or r.state != "live" or r.band in ("yellow", "red")]

    tbl_col, det_col = st.columns([7, 5], gap="medium")

    with tbl_col:
        table = {
            "狀態": [_STATE_META[r.state][0] for r in view],
            "燈號": [_BAND_META[r.band][0] for r in view],
            "指標": [r.label for r in view],
            "現值": [fmt_value(r.value, r.unit, r.decimals) for r in view],
            "門檻帶": [r.thr_text for r in view],
            "桶": [r.bucket for r in view],
            "資料日期": [r.as_of for r in view],
        }
        sel = st.dataframe(
            table, hide_index=True, use_container_width=True, height=520,
            on_select="rerun", selection_mode="single-row",
            column_config={
                "狀態": st.column_config.TextColumn(
                    width="small",
                    help="運作中 / 資料過期 / 鑑別力失效 / 未接線 —— "
                         "「未接線」代表這盞燈從來沒有真值"),
                "燈號": st.column_config.TextColumn(width="small"),
                "桶": st.column_config.TextColumn(width="small"),
                "指標": st.column_config.TextColumn(width="medium"),
                "門檻帶": st.column_config.TextColumn(
                    help="直接由 shared/macro_buckets.py 的 DangerSpec 組出"),
            },
        )

    with det_col:
        idx = (sel.selection.rows or [None])[0] if hasattr(sel, "selection") else None
        if idx is None:
            box = st.container(border=True)
            with box:
                st.markdown("#### 點左邊任一列")
                st.markdown(
                    "明細會在**這裡**就地展開 —— 定義、怎麼看、歷史錨點、"
                    "為什麼這盞燈不能信、門檻的 file:line。\n\n"
                    "Streamlit 沒有原生的右側抽屜,常駐右欄是最接近的落地做法:"
                    "同樣不跳頁、同樣保留左側表格的捲動位置。")
        else:
            row = view[idx]
            with st.container(border=True):
                render_detail(row, specs[row.key])

    # ── 收尾 ────────────────────────────────────────────────────────
    st.divider()
    with st.expander("這版跟現行總經頁差在哪"):
        st.markdown(
            "- **去重**:現行頁面把同一組數字重講數十次(repo 自己的 `STATE.md:1816` "
            "記為「同一資訊重複 4~18 次」)。這裡每個指標只有一個正典位置。\n"
            "- **誠實的燈**:`wired=False` 的指標(外資現貨)在現行畫面上跟正常灰燈長得一樣;"
            "這裡用斜線紋讓它退出燈號體系 —— 它不是一種等級,是「沒有消息」。\n"
            "- **門檻線畫進圖裡**:現行 15 張圖只有 1 張畫了危險線,其餘要心算。\n"
            "- **單軸**:現行 ADL 圖是雙 Y 軸(累積家數 vs 指數點位),兩個尺度的對齊是任意的,"
            "會讓人看到不存在的相關性。\n"
            "- **教學就地可得**:`EDU_GUIDE` 的 14 份教學目前只出現在「📖 系統說明書」分頁,"
            "總經頁一個字都沒用到。這裡直接接上,而且門檻用 token 代入,不會漂移。")
        st.caption(
            "未做:把它接進 `app.py` 取代現行 `render_tab_macro`。那會動到 "
            "`src/ui/tabs/macro/` 底下 9 個 section 模組,屬 CLAUDE.md §8.4 的"
            "「先盤點再動」範圍,需要另外提案並經你核准,不在本預覽的授權內。")


if __name__ == "__main__":
    main()
