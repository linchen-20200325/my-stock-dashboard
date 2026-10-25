"""shared/market_conclusion.py — 「📊 大盤」頁首屏那一行**並列結論句**的組字（L0 純函式）。

出處：`docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（v4）§1.2 R1／R2 ＋
客戶 2026-10-25 裁示 Q2-1（放結論句）：

  · 五個概念**各自一個子句**，子句之間**只用「；」並列**；
    ⛔ 不用「但／因此／所以」或任何比較、因果連接詞（五概念計算路徑互相獨立，
    危險度不含多空方向、趨勢尚未定義 —— 沒有可以機械判斷的「方向相反」）。
  · 缺資料／不可用／未評估**照實寫出來**，⛔ 不寫成中性、⛔ 不省略子句、⛔ 不補值。

═══ 本模組**不做**什麼 ═══════════════════════════════════════════════
- **不判態**：每個子句的字樣由呼叫端（`src/ui/views/page_market.py`）從**該概念自己的卡**
  取來（位階卡、危險度卡）；本模組只負責「照固定順序拼起來、守住連接詞」。
- **不合成**：⛔ 不平均、不取最差、不產生第六個子句或任何彙總燈號（R3）。
- **不讀 Risk Cap 數字**：風險上限子句是固定字樣（客戶 Q2-2），本模組根本不收那個值。

分層：L0 —— 零 I/O、零 streamlit、零 L1+ 依賴。
"""
from __future__ import annotations

#: 五概念的顯示名，順序即子句順序（線框 §1.1）。
CONCEPT_REGIME: str = "市場位階"
CONCEPT_TW_TREND: str = "台股趨勢"
CONCEPT_INTL_TREND: str = "國際趨勢"
CONCEPT_DANGER: str = "指標危險度"
CONCEPT_RISK_CAP: str = "風險上限"
CONCEPT_ORDER: tuple[str, ...] = (
    CONCEPT_REGIME, CONCEPT_TW_TREND, CONCEPT_INTL_TREND, CONCEPT_DANGER, CONCEPT_RISK_CAP)

#: 趨勢兩軸的字樣（客戶 2026-10-25 Q3=A：只寫「尚未定義」，無燈色、無多空字樣）。
TREND_UNDEFINED_TEXT: str = "尚未定義"
#: 風險上限獨立卡位的狀態字樣（客戶 2026-10-25 Q2-2，**逐字**）。
RISK_CAP_PENDING_TEXT: str = "獨立顯示待 C2b＋RC-VISIBILITY Gate"
#: 風險上限在結論句裡的子句內容 ＝ 客戶逐字（2026-10-25 QA-A B1：⛔ 不附「數字見哪裡」之類的指路）。
#: ~~f"{RISK_CAP_PENDING_TEXT}（上限有效時，數字見「能不能出手」卡）"~~（有意識的修改，⛔ 不是漏刪：
#:   客戶裁示的子句是「風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate」，多出來的指路句不在裁示內）
RISK_CAP_CLAUSE_TEXT: str = RISK_CAP_PENDING_TEXT
#: 子句內容缺席時的字樣（R1：照實寫出來，⛔ 不寫成中性）。
MISSING_TEXT: str = "無資料（未評估）"

#: 子句之間**唯一允許**的連接方式。
CLAUSE_SEP: str = "；"
#: ⛔ 結論句不得出現的連接詞（R2）。測試以此斷言；組字時遇到即 raise（§1）。
FORBIDDEN_CONNECTORS: tuple[str, ...] = (
    "但", "然而", "不過", "因此", "所以", "因為", "由於", "導致", "反而", "相反", "卻")


def _clause_body(text: str | None) -> str:
    """子句內容：空白／None → `MISSING_TEXT`（照實寫缺，⛔ 不省略子句）。"""
    if text is None:
        return MISSING_TEXT
    _t = str(text).strip()
    return _t if _t else MISSING_TEXT


def build_market_conclusion(*, regime_text: str | None,
                            danger_text: str | None) -> str:
    """五個子句並列成一句。

    Args:
        regime_text: 市場位階卡**目前的字樣**（例：「未評估」「多頭」）；None／空白 ⇒ 缺。
        danger_text: 指標危險度卡**目前的字樣**（例：「黃（2 桶黃　·　最差是「中期」…）」）；
            None／空白 ⇒ 缺。
        （台股趨勢／國際趨勢／風險上限三個子句是固定字樣，不收參數 —— 收了就有人會塞值進去。）

    Returns:
        「市場位階：…；台股趨勢：尚未定義；國際趨勢：尚未定義；指標危險度：…；風險上限：…。」

    Raises:
        ValueError: 任一子句內容含 `FORBIDDEN_CONNECTORS` 或「；」（§1：⛔ 靜默刪字改寫上游字樣，
            那會讓畫面上的句子與卡面對不起來）。
    """
    _bodies = {
        CONCEPT_REGIME: _clause_body(regime_text),
        CONCEPT_TW_TREND: TREND_UNDEFINED_TEXT,
        CONCEPT_INTL_TREND: TREND_UNDEFINED_TEXT,
        CONCEPT_DANGER: _clause_body(danger_text),
        CONCEPT_RISK_CAP: RISK_CAP_CLAUSE_TEXT,
    }
    for _name, _body in _bodies.items():
        if CLAUSE_SEP in _body:
            raise ValueError(
                f"「{_name}」子句內容含分隔符「{CLAUSE_SEP}」：{_body!r} —— 會被讀成兩個子句")
        _bad = [_w for _w in FORBIDDEN_CONNECTORS if _w in _body]
        if _bad:
            raise ValueError(
                f"「{_name}」子句內容含禁用連接詞 {_bad}：{_body!r} —— "
                "結論句只准並列（R2），請在該卡的字樣端處理，⛔ 不在這裡靜默刪字")
    return CLAUSE_SEP.join(f"{_n}：{_bodies[_n]}" for _n in CONCEPT_ORDER) + "。"
