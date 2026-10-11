"""shared/inst_labels.py — 三大法人身分別名稱判定 SSOT（L0，批 Z40，2026-10-11）。

客戶裁示（Q-z24＝A' 官方口徑、Q-z25＝A）
=========================================
- **外資** ＝ 外資及陸資（**不含**外資自營商）。
- **自營商** ＝ 自營商（自行買賣）＋ 自營商（避險）。
- **外資自營商不再額外加到任何一類**；三大法人合計不含外資自營商項。
  TWSE BFI82U notes 原文：「因外資自營商買賣金額已計入自營商買賣金額，故不納入三大法人買賣金額之合計數計算。」
  ⇒ 外資自營商**已含在**自營商（自行＋避險）內，另加＝重複計算。

官方報表實測（runner 探針 run 38104351927／38105028779，2026-10-08；派工規格轉述）
------------------------------------------------------------------------------
- TWSE T86 19 欄：外資＝`外陸資買賣超股數(不含外資自營商)`、外資自營商＝`外資自營商買賣超股數`、
  投信＝`投信買賣超股數`、自營商＝`自營商買賣超股數`（＝自行＋避險，18975/18975 列成立）、
  三大法人＝`三大法人買賣超股數`（＝外資(不含)＋投信＋自營商，100%）。
- TWSE BFI82U 列：`自營商(自行買賣)`、`自營商(避險)`、`投信`、`外資及陸資(不含外資自營商)`、
  `外資自營商`、`合計`；合計 ＝ 自行＋避險＋投信＋外資(不含)。
- FinMind name：`Foreign_Investor`（＝外資(不含)）、`Foreign_Dealer_Self`（外資自營商）、
  `Investment_Trust`、`Dealer_self`（自行）、`Dealer_Hedging`（避險）、`total`。

⚠️ 子字串陷阱（本模組存在的理由）
- 「外資及陸資(不含外資自營商)」／「外陸資買賣超股數(不含外資自營商)」**含**子字串「外資自營商」與「自營」；
- 「外資自營商買賣超股數」**含**子字串「自營商買賣超股數」；
- 「Foreign_Dealer_Self」**同時含** `foreign` 與 `dealer`。
⇒ 判定一律走本模組，不在各 fetcher 各寫一套 `in` 子字串。

純函式／常數模組，零 import 依賴（可被全層 import）。
"""
from __future__ import annotations

#: FinMind name 值（大小寫依 FinMind 實際回傳）
FINMIND_FOREIGN_INVESTOR: str = "Foreign_Investor"
FINMIND_FOREIGN_DEALER_SELF: str = "Foreign_Dealer_Self"
FINMIND_INVESTMENT_TRUST: str = "Investment_Trust"
#: 自營商 ＝ 自行買賣 ＋ 避險（客戶 Q-z25＝A）
FINMIND_DEALER_NAMES: tuple[str, str] = ("Dealer_self", "Dealer_Hedging")

#: TWSE T86 欄名（strip 後**完全相等**比對；⛔ 不用子字串 —— 見模組 docstring 子字串陷阱）
T86_FOREIGN_NET_COL: str = "外陸資買賣超股數(不含外資自營商)"
#: 2017-12-18 前舊格式外資欄（當時官方外資口徑含外資自營商；只作舊格式備援，完全相等比對）
T86_FOREIGN_NET_COL_LEGACY: str = "外資買賣超股數"
T86_TRUST_NET_COL: str = "投信買賣超股數"
T86_DEALER_NET_COL: str = "自營商買賣超股數"                 # 自行＋避險合計
T86_DEALER_SELF_NET_COL: str = "自營商買賣超股數(自行買賣)"
T86_DEALER_HEDGE_NET_COL: str = "自營商買賣超股數(避險)"
T86_TOTAL_NET_COL: str = "三大法人買賣超股數"


def is_foreign_dealer_label(name: object) -> bool:
    """「外資自營商」身分別（列名／欄名／FinMind name）→ True。

    - 英文：`Foreign_Dealer_Self`（不分大小寫、去頭尾空白）。
    - 中文：含「外資自營商」且**不含**「不含」（排除「外資及陸資(不含外資自營商)」這類外資列）。
    """
    s = str(name).strip()
    if s.lower() == FINMIND_FOREIGN_DEALER_SELF.lower():
        return True
    return "外資自營商" in s and "不含" not in s


def is_finmind_foreign_investor(name: object) -> bool:
    """FinMind 外資（不含外資自營商）：name 完全等於 `Foreign_Investor`（去頭尾空白、不分大小寫）。"""
    return str(name).strip().lower() == FINMIND_FOREIGN_INVESTOR.lower()


def is_finmind_dealer(name: object) -> bool:
    """FinMind 自營商（自行＋避險）：name 完全等於 `Dealer_self` 或 `Dealer_Hedging`（去頭尾空白、不分大小寫）。"""
    return str(name).strip().lower() in tuple(n.lower() for n in FINMIND_DEALER_NAMES)
