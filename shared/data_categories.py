"""shared/data_categories.py — data_registry category SSOT(v18.394 SSOT 修)。

§2.1 SSOT — 對齊 `src.data.core.data_registry` 靜態 11 個 emoji category。
本檔提供:
1. 11 個 category 常數(避免 caller hardcode emoji string)
2. `category_for(entry_name: str) -> str` 對映函式
   — 從 runtime registry entry 名稱推回 category(scanner/patch 使用)
3. `coverage_emoji_for(category: str) -> str` 反向對映
   — 給 data_coverage tab / diagnostic panel UI 使用

設計理由:
- L0 層,可被 L1(static data_registry)/ L3(scanner/patch)共用
- Static `DATA_REGISTRY` 已使用這 11 個 emoji,本檔讓 runtime registry 也對齊
"""
from __future__ import annotations


# ── 11 個 category SSOT(對齊 src.data.core.data_registry 靜態註冊表)──
CAT_INTL        = '🌐 國際金融'
CAT_TW_MARKET   = '🇹🇼 台股大盤'
CAT_TW_MACRO    = '🇹🇼 台灣總經'
CAT_US_MACRO    = '🌍 美國總經'
CAT_CN_MACRO    = '🇨🇳 中國總經'
CAT_CHIPS       = '💰 籌碼'
CAT_STOCK       = '🏢 個股財報'
CAT_ETF         = '🏦 ETF / 基金'
CAT_NEWS        = '📰 新聞 RSS'
CAT_FALLBACK    = '🔄 三方備援'
CAT_AI          = '🤖 AI 服務'

ALL_CATEGORIES = (
    CAT_US_MACRO, CAT_TW_MACRO, CAT_CN_MACRO, CAT_INTL, CAT_TW_MARKET,
    CAT_CHIPS, CAT_STOCK, CAT_ETF, CAT_NEWS, CAT_FALLBACK, CAT_AI,
)


# ── 個別 entry name → category 對映(scanner/patch 使用)──
# v18.394 整理:對齊 scanner/patch 實際寫入的 entry name pattern
_NAME_TO_CATEGORY: dict[str, str] = {
    # ── 籌碼面 ─────────────────────────────────────────
    '三大法人 外資買賣超':    CAT_CHIPS,
    '三大法人 投信買賣超':    CAT_CHIPS,
    '三大法人 自營商買賣超':  CAT_CHIPS,
    '融資餘額（台股）':       CAT_CHIPS,
    # ── 台股大盤(指數 + 廣度 + 乖離) ───────────────
    'ADL 市場廣度':           CAT_TW_MARKET,
    '上漲股票家數':            CAT_TW_MARKET,
    '下跌股票家數':            CAT_TW_MARKET,
    'ADL 累計廣度值':         CAT_TW_MARKET,
    '旌旗指數（上漲佔比）':    CAT_TW_MARKET,
    'TWII 年線乖離率':         CAT_TW_MARKET,
    'TWII 月線乖離率':         CAT_TW_MARKET,
    # ── 台灣總經(貨幣 / PMI / 出口 / 景氣) ──────────
    'M1B 資金活水年增率':       CAT_TW_MACRO,
    'M2 廣義貨幣年增率':        CAT_TW_MACRO,
    'M1B-M2 資金缺口':          CAT_TW_MACRO,
    '🇹🇼 台灣 PMI 製造業指數':  CAT_TW_MACRO,
    '台灣出口年增率':           CAT_TW_MACRO,
    '景氣先行指標（NDC）':      CAT_TW_MACRO,
    # ── 美國總經(CPI / Fed) ────────────────────────
    '美國核心CPI年增率':        CAT_US_MACRO,
    '美國 Fed Funds Rate':      CAT_US_MACRO,
    # ── 國際金融(VIX 對齊 static) ──────────────────
    'VIX 波動率指數':           CAT_INTL,
}


def category_for(name: str, fallback: str = CAT_INTL) -> str:
    """從 runtime data_registry entry 名稱推回 SSOT category。

    優先順序:
    1. 前綴 pattern:`[個股]` / `[比較]` → CAT_STOCK
    2. 前綴 pattern:`[ETF]`* / `[ETF組合]`* / `[ETF回測]`* → CAT_ETF
    3. 前綴 pattern:`[先行指標]` → CAT_CHIPS
    4. 精確 name 對映:`_NAME_TO_CATEGORY` 表
    5. fallback(預設 CAT_INTL,適合 INTL_MAP/TECH_MAP 未列出的 ticker)

    Args:
        name: registry entry name
        fallback: 全部未命中時 fallback(scanner 對 TW_MAP 應傳 CAT_TW_MARKET,
                  對 INTL_MAP/TECH_MAP 傳 CAT_INTL)

    Returns:
        11 category 之一(SSOT 對齊 static DATA_REGISTRY)
    """
    if name.startswith('[個股]') or name.startswith('[比較]'):
        return CAT_STOCK
    if name.startswith('[ETF') or '[ETF組合]' in name or '[ETF回測]' in name:
        return CAT_ETF
    if name.startswith('[先行指標]'):
        return CAT_CHIPS
    return _NAME_TO_CATEGORY.get(name, fallback)


def coverage_emoji_for(category: str) -> str:
    """從 SSOT category 取 emoji 前綴(diagnostic panel UI grouping 用)。

    回傳 category 本身(category 本來就含 emoji);若給未知 category 回 `❓`。
    """
    return category if category in ALL_CATEGORIES else '❓ 未分類'


# ── Freshness threshold SSOT(v18.401 P5-SSOT-FIX 補抽)──
# data_registry_panel._freshness_emoji 原 inline `7/30 / 90/180 / 180/365` 三組,
# 改用此 mapping 集中。frequency → (warn_days, crit_days):
#   - daily/weekly:7 日內 🟢 / 7~30 🟡 / >30 🔴
#   - monthly:    90 日內 🟢 / 90~180 🟡 / >180 🔴
#   - quarterly/yearly:180 日內 🟢 / 180~365 🟡 / >365 🔴
#   - event:走 caller 特殊 path(always 🟢,觸發型),不在此 mapping
FRESHNESS_THRESHOLDS_DAYS: dict[str, tuple[int, int]] = {
    'daily':     (7, 30),
    'weekly':    (7, 30),
    'monthly':   (90, 180),
    'quarterly': (180, 365),
    'yearly':    (180, 365),
}
