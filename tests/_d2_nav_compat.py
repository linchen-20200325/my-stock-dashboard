"""tests/_d2_nav_compat.py — D2 導覽殼（DEC-090 ⑦）之後，舊 golden 雜湊的相容層（僅測試用）。

⑦：`ia_nav.where_to_find` 的指路句多帶方向名（「🚦 今天」→「📊 大盤 › 🚦 今天」）。
多個**修前 golden / byte-identical 雜湊**（`test_batch_z36`、`test_lamp_direction`、`test_v2_silent_fail_b4/b5_vix/b7/b8/b9`）
雜湊的是含指路句的整張卡 / 整份 HTML ⇒ 雜湊值因此變了，**除此之外一字未變**。

處置：雜湊前把方向前綴還原成修前寫法，**golden 一字不改**（它們是「修前基底輸出」的證據，不能由現行碼反推新值）。
證據（D2 實跑）：以「雜湊前套這份還原」的臨時 plugin 跑上列 7 支測試共 583 passed、0 failed；
未套還原時 54 failed ⇒ 漂移**只有**方向前綴。⛔ 若日後這些測試因別的原因紅，本檔不得被拿來蓋掉它：
只還原 `NAV_TREE` 內正確的「方向 › 頁」完整前綴（👤 我的 的指路句因方向名＝頁名而折疊，本來就與修前同字，不在此列）。
"""
#: 客戶核准線框 §3.1 的「方向 › 頁」正確組合——**寫死的第二來源，不讀 `ia_nav.NAV_TREE`**
#: （讀現行樹＝方向錯掛時前綴與樹一起錯、被一起還原而假綠）。方向名＝頁名者（📊 大盤／👤 我的）指路句已折疊，不在此列。
_CORRECT_PAIRS = (
    ("📊 大盤", "🚦 今天"),
    ("🎯 標的", "🔍 找標的"),
    ("🎯 標的", "🔬 查一檔"),
    ("🛡️ 持股", "💼 我的持股"),
    ("🩺 資料中心", "📖 憑什麼"),
)


def _known_prefixes() -> tuple[tuple[str, str], ...]:
    """只還原上列正確組合的完整前綴「「方向 › 頁」→「「頁」；方向錯掛或多插前綴都不會被還原 ⇒ golden 轉紅。"""
    return tuple((f"「{_d} › {_p}", f"「{_p}") for _d, _p in _CORRECT_PAIRS)


def strip_direction(text: str) -> str:
    for _a, _b in _known_prefixes():
        text = text.replace(_a, _b)
    return text
