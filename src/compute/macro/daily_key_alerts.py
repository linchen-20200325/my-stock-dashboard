"""src/compute/macro/daily_key_alerts.py — ⚡ 今日關鍵橫幅判定(L2 純函式)。

v19.108(第九份 review 4-C 精簡版,§8.1 設計 2026-07-12 user 核准):
把「今天最需要看的異常」從**已載入**的指標裡挑出來,供頁首橫幅置頂顯示。

兩層判定(v1;robust-z 歷史層標「升級觸發條件:等 macro_history parquet
覆蓋更多指標」,現缺各指標歷史分布地基,§1 不腦補):
- **門檻層**:直接吃既有 `check_macro_alerts`(MACRO_ALERT_RULES SSOT)的
  🔴/🟡 命中 — 不另造第二套門檻,本模組只做「挑出+排序+送頁首」。
- **急變層(Δ)**:僅對 macro_info 內**有真 prev/序列**的指標算單期變化:
  vix(3 個月日序列取尾兩點)、fed_funds(current+prev)。門檻走
  shared/signal_thresholds SSOT。

§8.2 L2:純函式 in→out,零 I/O、零 streamlit;caller(L5 tab_macro)自
session_state 取數傳入,L4 macro_ui_components.key_alerts_banner 渲染。
失敗降級(§1):指標缺值/型別壞 → 跳過該項不腦補;全空 → items=[] 由
L4 顯示「今日無異常」;絕不因判定層錯誤炸頁(單項 try 收窄)。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    KEY_ALERT_FED_FUNDS_MOVE_PCTPT,
    KEY_ALERT_VIX_DAY_SPIKE_PCT,
)


def _threshold_items(threshold_alerts: list | None) -> list[dict]:
    """門檻層:check_macro_alerts 輸出 → 只取 red/yellow,轉橫幅 item。"""
    items: list[dict] = []
    for a in (threshold_alerts or []):
        lvl = a.get('level')
        if lvl not in ('red', 'yellow'):
            continue
        try:
            _val = float(a.get('value'))
            _val_txt = f'{_val:g}'
        except (TypeError, ValueError):
            _val_txt = str(a.get('value', '?'))
        items.append({
            'emoji': a.get('emoji') or ('🔴' if lvl == 'red' else '🟡'),
            'severity': 0 if lvl == 'red' else 1,
            'text': f"{a.get('label', '?')} {_val_txt}{a.get('unit', '')}",
            'detail': a.get('message', ''),   # 白話敘事沿用 SSOT rule 的 message
            'layer': 'threshold',
        })
    return items


def _delta_items(macro_info: dict | None) -> list[dict]:
    """急變層:只碰有真 prev/序列的指標(vix.values / fed_funds.prev)。"""
    items: list[dict] = []
    mi = macro_info or {}

    # ── VIX 單日急升(3 個月日序列尾兩點)──
    try:
        vals = [v for v in ((mi.get('vix') or {}).get('values') or [])
                if v is not None]
        if len(vals) >= 2:
            _p, _c = float(vals[-2]), float(vals[-1])
            if _p > 0:
                _chg_pct = (_c / _p - 1) * 100
                if _chg_pct >= KEY_ALERT_VIX_DAY_SPIKE_PCT:
                    items.append({
                        'emoji': '⚡', 'severity': 0,
                        'text': f'VIX 單日急升 {_chg_pct:+.0f}%（{_p:.1f}→{_c:.1f}）',
                        'detail': (f'單日漲幅 ≥ {KEY_ALERT_VIX_DAY_SPIKE_PCT:.0f}% 屬罕見級'
                                   '恐慌急升 — 留意系統性風險與流動性收縮'),
                        'layer': 'delta',
                    })
    except (TypeError, ValueError):
        pass  # smoke-allow-pass — 序列含垃圾值,急變層跳過(門檻層不受影響)

    # ── Fed Funds 月均利率動了(政策節奏變化)──
    try:
        ff = mi.get('fed_funds') or {}
        _cur, _prev = ff.get('current'), ff.get('prev')
        if _cur is not None and _prev is not None:
            _mv = float(_cur) - float(_prev)
            if abs(_mv) >= KEY_ALERT_FED_FUNDS_MOVE_PCTPT:
                _dir = '升息' if _mv > 0 else '降息'
                items.append({
                    'emoji': '🏛️', 'severity': 1,
                    'text': f'Fed 利率單月 {_mv:+.2f} 個百分點（{_dir}節奏）',
                    'detail': (f'月均變動 |Δ| ≥ {KEY_ALERT_FED_FUNDS_MOVE_PCTPT:.2f} '
                               '百分點 ≈ 該月有一碼級政策動作 — '
                               f'{_dir}=（緊縮風險 / 衰退對沖訊號）方向自行對照景氣位階'),
                    'layer': 'delta',
                })
    except (TypeError, ValueError):
        pass  # smoke-allow-pass — prev/current 型別壞,急變層跳過

    return items


def collect_key_alerts(threshold_alerts: list | None,
                       macro_info: dict | None) -> dict:
    """合併門檻層 + 急變層,依嚴重度排序,回橫幅資料。

    Args:
        threshold_alerts: `check_macro_alerts` 的輸出(session_state
            ['macro_alerts'];未載入時 None → 門檻層空)。
        macro_info: session_state['macro_info'](vix/fed_funds 等 block)。

    Returns:
        {'items': [{'emoji','severity'(0紅/1黃),'text','detail','layer'}...]
         依 severity 升冪(紅先), 'n_red': int, 'n_yellow': int}
    """
    items = _threshold_items(threshold_alerts) + _delta_items(macro_info)
    items.sort(key=lambda i: i['severity'])
    return {
        'items': items,
        'n_red': sum(1 for i in items if i['severity'] == 0),
        'n_yellow': sum(1 for i in items if i['severity'] == 1),
    }
