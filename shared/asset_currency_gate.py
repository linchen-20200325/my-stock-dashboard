"""shared/asset_currency_gate.py — 「這筆資產能不能確定是 TWD 計價」的 fail-safe 判定（L0 純函式）。

XV-H3（客戶 2026-10-28 裁示 A）：未定義匯率來源、時點與成本幣別之前，外幣資產**不得**直接與
TWD 資產加總（總市值、未實現損益合計、80/20 或任何配置比例、AI prompt 的總額事實）。

═══ 這**不是** canonical currency 定義 ═══════════════════════════════
本檔只回答一個窄問題：「從代號本身，**能不能確定**它是台股（TWD）？」
- 能確定 → TWD：(a) 結尾 `.TW`／`.TWO`（大小寫不敏感）且前面非空；或
  (b) 裸碼為 **純 ASCII 數字 4–6 碼 ＋ 可選一個大寫字母結尾**（`2330`、`0050`、`00878`、`00631L`、`2881A`、`006208`；
  全形／非 ASCII 數字一律拒收）。
- 其餘一律排除（fail-safe，⛔ 不猜），排除原因分兩種（QA 回修）：
  · **明確外幣**：英文字母開頭、只由英數與 `.`／`-` 組成（美股 `VOO`／`BND`／`BRK.B`）→ `FX_EXCLUDED_REASON`；
  · **幣別未確認**：其餘（`50`、`^TWII`、`1234567`、小寫字母結尾、看不出來的）→ `FX_UNCONFIRMED_REASON`。
正式的幣別定義（幣別欄、匯率來源＋時點、成本幣別）**另開 Gate**；屆時本檔應被取代，而非被擴充成猜測規則。

與既有 `src/compute/etf/portfolio_fx.holding_currency`（L2，只看後綴、裸碼一律當 USD）**刻意不同**：
那支服務舊 UI 的 FX 換算；本檔是「**不換算、只排除**」的閘門，方向相反（裸碼台股在這裡是 TWD）。
本檔零 I/O、零 `src.*` import。
"""
from __future__ import annotations

import re

#: 裸碼台股：純數字 4–6 碼 ＋ 可選一個大寫字母結尾。
_TW_BARE_RE = re.compile(r"[0-9]{4,6}[A-Z]?")
#: 明確外幣（美股類）代號：英文字母開頭、只由 ASCII 英數與 `.`／`-` 組成。
_FOREIGN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.\-]*")
_TW_SUFFIXES: tuple[str, ...] = (".TWO", ".TW")

#: 畫面／LINE／AI 共用的客戶句（客戶 2026-10-28 裁示逐字）。
FX_PARTIAL_TEXT: str = "⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定"
#: 未納入原因（客戶例句「原因：外幣資產，匯率與成本幣別未定義」）—— 明確外幣。
FX_EXCLUDED_REASON: str = "外幣資產，匯率與成本幣別未定義"
#: 未納入原因 —— 看不出是不是台股（不是明確外幣，也不能確定是 TWD）。
FX_UNCONFIRMED_REASON: str = "幣別未確認"


def is_confirmed_twd_ticker(ticker) -> bool:
    """代號能確定是台股（TWD 計價）→ True；其餘（含非 str、空白）→ False（fail-safe）。"""
    if not isinstance(ticker, str):
        return False
    _t = ticker.strip()
    _u = _t.upper()
    for _suf in _TW_SUFFIXES:
        if _u.endswith(_suf):
            return len(_t) > len(_suf)
    return _TW_BARE_RE.fullmatch(_t) is not None


def fx_exclusion_reason(ticker) -> str:
    """被排除的代號 → 原因句（明確外幣 `FX_EXCLUDED_REASON`／其餘 `FX_UNCONFIRMED_REASON`）。"""
    _t = ticker.strip() if isinstance(ticker, str) else ""
    return FX_EXCLUDED_REASON if _FOREIGN_RE.fullmatch(_t) else FX_UNCONFIRMED_REASON


def fx_excluded_text(codes) -> str:
    """`未納入：VOO、BND｜原因：外幣資產，匯率與成本幣別未定義；50｜原因：幣別未確認`（去重保序；
    兩種原因各一組，明確外幣在前；只有一種時只有那一組）。"""
    _uniq = list(dict.fromkeys(str(_x) for _x in codes))
    _groups = []
    for _reason in (FX_EXCLUDED_REASON, FX_UNCONFIRMED_REASON):
        _c = [_x for _x in _uniq if fx_exclusion_reason(_x) == _reason]
        if _c:
            _groups.append(f"{'、'.join(_c)}｜原因：{_reason}")
    return "未納入：" + "；".join(_groups)

#: L3 `portfolio_deep_service` 壓測／VaR 的 `reason`：持有列**全部**是外幣／幣別未確認（台股一檔都沒有）。
#: page_hold 據此給「不適用 · 重跑無效」＋外幣原因，⛔ 不叫使用者去補張數／均價（QA 回修 #5）。
FX_ONLY_REASON: str = "持有列全是外幣／幣別未確認資產（匯率與成本幣別未定義，本站不換算、不計入）"

#: L3 `dividend_station_service.build_station_rows` 在**持有列**上標「幣別未確認、已排除於總額／比例」
#: 的非顯示欄（同 `_detail` 慣例）。⚠️ **只有排除時才有這一鍵** —— 台股列逐鍵不變。
KEY_FX_UNCONFIRMED: str = "_fx_unconfirmed"
