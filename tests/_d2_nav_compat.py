"""tests/_d2_nav_compat.py — D2 導覽殼（DEC-090 ⑦）之後，舊 golden 雜湊的相容層（僅測試用）。

⑦：`ia_nav.where_to_find` 的指路句多帶方向名（「🚦 今天」→「📊 大盤 › 🚦 今天」）。
多個**修前 golden / byte-identical 雜湊**（`test_batch_z36`、`test_lamp_direction`、`test_v2_silent_fail_b4/b5_vix/b7/b8/b9`）
雜湊的是含指路句的整張卡 / 整份 HTML ⇒ 雜湊值因此變了，**除此之外一字未變**。

處置：雜湊前把方向前綴還原成修前寫法，**golden 一字不改**（它們是「修前基底輸出」的證據，不能由現行碼反推新值）。
證據（D2 實跑）：以「雜湊前套這份還原」的臨時 plugin 跑上列 7 支測試共 583 passed、0 failed；
未套還原時 54 failed ⇒ 漂移**只有**方向前綴。⛔ 若日後這些測試因別的原因紅，本檔不得被拿來蓋掉它：
只還原下列四個固定的方向前綴（👤 我的 的指路句因方向名＝頁名而折疊，本來就與修前同字，不在此列）。
"""
_PREFIXES = ("「📊 大盤 › ", "「🎯 標的 › ", "「🛡️ 持股 › ", "「🩺 資料中心 › ")


def strip_direction(text: str) -> str:
    for _p in _PREFIXES:
        text = text.replace(_p, "「")
    return text
