"""src/compute/etf/portfolio_coherence.py — 股債比 + 總經一致性(L2 純函式,v19.63)。

框架討論結論(#2 + #3 股債比):
- 真正的抗跌分散來自**不同資產類別(債券/現金)**,不是挑不相關的股票型 ETF → 顯示股債比。
- 「一致性」:總經姿態(油門)vs 你的組合股債配置是否**自相矛盾**
  (總經喊防守、你卻幾乎全股票 = 打架)。

純函式,零 I/O,易測。門檻走本檔 SSOT。
"""
from __future__ import annotations

import re

# 已知美股債券 ETF(台股債券 ETF 以「數字+B」pattern 判斷)。
_BOND_US: frozenset[str] = frozenset({
    'BND', 'AGG', 'TLT', 'IEF', 'SHY', 'LQD', 'BNDX', 'GOVT', 'TIP', 'HYG', 'EMB',
})
_TW_BOND_RE = re.compile(r'^\d{4,5}B$')  # 00679B / 00937B …

# 一致性門檻 SSOT
BOND_LOW_PCT: float = 20.0    # 債券 < 此 → 視為「幾乎全股票」
BOND_HIGH_PCT: float = 60.0   # 債券 > 此 → 視為「偏保守」


def classify_asset_class(ticker) -> str:
    """'bond' 或 'stock'。台股 *B / 已知美債 ETF → bond;其餘 → stock。"""
    _t = str(ticker or '').upper().strip()
    _base = _t.replace('.TWO', '').replace('.TW', '')
    if _base in _BOND_US:
        return 'bond'
    if _TW_BOND_RE.match(_base):
        return 'bond'
    return 'stock'


def assess_stock_bond(rows) -> dict:
    """rows: iterable of {ticker, value(市值)} → 股債金額 + 佔比。

    Returns {stock_value, bond_value, total, stock_pct, bond_pct}。
    total=0 → 佔比皆 0。
    """
    _stock = _bond = 0.0
    for r in rows or []:
        try:
            _v = float(r.get('value') or 0)
        except (TypeError, ValueError):
            continue
        if _v <= 0:
            continue
        if classify_asset_class(r.get('ticker')) == 'bond':
            _bond += _v
        else:
            _stock += _v
    _total = _stock + _bond
    return {
        'stock_value': _stock, 'bond_value': _bond, 'total': _total,
        'stock_pct': round(_stock / _total * 100, 1) if _total else 0.0,
        'bond_pct': round(_bond / _total * 100, 1) if _total else 0.0,
    }


# 核心 = 追大盤市值型(定期定額、不理循環);其餘股票型 = 衛星(才做戰術/景氣調整)。
_CORE_CATEGORIES: frozenset[str] = frozenset({'市值型'})


def classify_core_satellite(ticker) -> str:
    """'債券' / '核心' / '衛星'。債券→債券;市值型 ETF→核心;其餘股票→衛星。"""
    if classify_asset_class(ticker) == 'bond':
        return '債券'
    from src.compute.etf.etf_categories import get_category_name  # noqa: PLC0415
    if get_category_name(ticker) in _CORE_CATEGORIES:
        return '核心'
    return '衛星'


def assess_core_satellite(rows) -> dict:
    """rows: [{ticker, value}] → 核心/衛星/債券 金額 + 佔比。

    Returns {core_pct, satellite_pct, bond_pct, total, ...}。
    """
    _buckets = {'核心': 0.0, '衛星': 0.0, '債券': 0.0}
    for r in rows or []:
        try:
            _v = float(r.get('value') or 0)
        except (TypeError, ValueError):
            continue
        if _v <= 0:
            continue
        _buckets[classify_core_satellite(r.get('ticker'))] += _v
    _total = sum(_buckets.values())
    _pct = {f'{k}_pct': (round(v / _total * 100, 1) if _total else 0.0)
            for k, v in _buckets.items()}
    return {
        'core_pct': _pct['核心_pct'], 'satellite_pct': _pct['衛星_pct'],
        'bond_pct': _pct['債券_pct'], 'total': _total,
        'core_value': _buckets['核心'], 'satellite_value': _buckets['衛星'],
        'bond_value': _buckets['債券'],
    }


def coherence_note(macro_posture, bond_pct: float) -> tuple[str, str]:
    """總經姿態 vs 股債配置一致性 → (level, message)。

    macro_posture: 油門姿態字('積極'/'中性偏多'/'轉守'/'防禦'[/總經否決])。
    level: 'warn' / 'info' / 'ok' / 'na'。
    """
    if not macro_posture:
        return ('na', '（總經姿態未知,略過一致性檢查）')
    _defensive = ('防禦' in macro_posture) or ('轉守' in macro_posture)
    if _defensive and bond_pct < BOND_LOW_PCT:
        return ('warn',
                f'⚠️ **訊號打架**：總經偏防守（{macro_posture}），但你組合債券只有 '
                f'{bond_pct:.0f}%（<{BOND_LOW_PCT:.0f}%）幾乎全股票 —— 考慮加**債券/現金**提高防禦。')
    if (not _defensive) and bond_pct > BOND_HIGH_PCT:
        return ('info',
                f'💡 總經偏多（{macro_posture}），但你債券占 {bond_pct:.0f}%（>{BOND_HIGH_PCT:.0f}%）'
                f'偏保守 —— 沒錯,但留意機會成本(看你風險偏好)。')
    return ('ok', f'✅ 股債配置與總經姿態（{macro_posture}）大致一致。')
