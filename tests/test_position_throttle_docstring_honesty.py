"""守衛:`shared/position_throttle.py` 的 docstring 宣稱值必須等於實際常數。

## 為什麼需要這道守衛(不是儀式性測試)

2026-08-11(commit `7d76267`)寫下的模組 docstring 宣稱:
    「健康分界 80 / 50 / 35 對齊 HEALTH_GRADE_A_MIN / HEALTH_GRADE_B_MIN /
      HEALTH_DEFENSE_THRESHOLD 預設。」
2026-08-19(commit `ff5f00d`)A 切點分兩段改成 80 → 65 → 70(**尺度借用錯誤修正,user 核准**),
**docstring 沒跟著改**。之後那段文字同時錯兩層:

  1. **數字錯**:宣稱 80,實際 `THROTTLE_HEALTH_A = 70`。
  2. **對齊對象錯**:`HEALTH_GRADE_A_MIN` 是**個股六因子健康分**的 A 級線,
     與**總經 health** 是兩個不同尺度的量 —— 而「不該對齊它」正是那次修掉的 bug 本身。

危害不是「文件不好看」,而是:**下一個做 SSOT 收斂的人(或 AI)讀到那句話,會很合理地
「恢復對齊」把 A 改回 80 —— 把 user 核准修掉的錯誤重新種回去。**
該模組**零 import 任何門檻 SSOT**(刻意複寫值避免 L0 交叉耦合),所以沒有任何 import
會在背後阻止這件事;原檔只寫「以註解釘一致」,而那條註解自己就是爛掉的那條。

⇒ 本檔把「一致」從**自律**改成**CI 紅燈**。

## 守衛設計(四層,由弱到強)

- L1 **數值同步**(`test_docstring_declared_values_match_constants`):
  docstring 內一行 machine-readable 宣告 `現行健康分界:A=.. / B=.. / DEF=..`,
  以 regex 抽出後與實際常數逐一比對。**改常數沒改 docstring → 紅燈**,反之亦然。
  這一條直接對應本次事故的成因(常數動了、文件沒動)。
- L2 **結構性反向釘**(`test_throttle_a_must_not_be_realigned_...`):
  `THROTTLE_HEALTH_A != HEALTH_GRADE_A_MIN`。
  L1 只擋「文件沒跟上」,擋不住「**兩邊一起改回 80**」這種「好心的收斂」;
  L2 擋的就是那個 —— 它釘的是**值**不是**措辭**,任何改寫註解的手法都繞不過。
- L3 **措辭反向釘**(`test_docstring_never_asserts_a_aligns_...`):
  docstring 內凡提到 `HEALTH_GRADE_A_MIN` 的行,必須同時帶否定/說明標記,
  防止那句肯定句以任何形式被寫回來(即使值還沒被改)。
- L4 **理由不得被刪**(`test_docstring_keeps_the_scale_explanation`):
  只把數字改對、卻刪掉「為什麼不能對齊」的說明,下一個人還是會想去對齊。
  故把「個股六因子 / 不同尺度」這個理由本身也釘住。

另附 `test_def_cut_really_aligns_with_defense_threshold_default`:
三個切點裡**只有 DEF 是真對齊**(同為總經 health 尺度),故它值得一條真的跨模組 pin。

⚠️ **刻意不釘 `THROTTLE_HEALTH_B == HEALTH_GRADE_B_MIN`(=50)**:
兩者數值相同是**巧合**,B 那條線同樣出自個股六因子尺度,與 A 的錯誤同源、只是尚未被單獨校準。
釘它等於把同一個尺度借用錯誤用測試**固化**下來。**請不要「順手補上」這條 pin。**
"""
from __future__ import annotations

import re

from shared.health_thresholds import HEALTH_GRADE_A_MIN
from shared.macro_calibration import HEALTH_DEFENSE_THRESHOLD_DEFAULT
from shared.position_throttle import (
    THROTTLE_HEALTH_A,
    THROTTLE_HEALTH_B,
    THROTTLE_HEALTH_DEF,
    THROTTLE_TIERS,
)
from shared import position_throttle as _mod

# docstring 內的 machine-readable 宣告行。全形/半形冒號皆接受。
_DECLARED_RE = re.compile(
    r"現行健康分界[:：]\s*A=(\d+)\s*/\s*B=(\d+)\s*/\s*DEF=(\d+)"
)

# L3 允許的「否定/說明」標記 —— 提到 HEALTH_GRADE_A_MIN 的行必須帶其中之一。
_NEGATION_MARKERS = ("不對齊", "禁止", "不得", "不收", "個股六因子", "~~")


def _doc() -> str:
    doc = _mod.__doc__
    assert doc, "position_throttle 模組 docstring 不得為空(本守衛依賴它)"
    return doc


# ── L1:docstring 宣稱值 == 實際常數 ─────────────────────────────────────
def test_docstring_declared_values_match_constants():
    """本次事故的直接成因:常數改了(80→70),docstring 沒改。"""
    m = _DECLARED_RE.search(_doc())
    assert m, (
        "position_throttle docstring 缺少 machine-readable 宣告行 "
        "`現行健康分界:A=.. / B=.. / DEF=..` —— 該行是本守衛的錨點,不得刪除或改格式。"
    )
    declared_a, declared_b, declared_def = (int(g) for g in m.groups())
    assert declared_a == THROTTLE_HEALTH_A, (
        f"docstring 宣稱 A={declared_a},實際 THROTTLE_HEALTH_A={THROTTLE_HEALTH_A}。"
        " 改常數請同步改 docstring —— 2026-08-19 就是漏了這一步,讓 docstring 變成假引用。"
    )
    assert declared_b == THROTTLE_HEALTH_B, (
        f"docstring 宣稱 B={declared_b},實際 THROTTLE_HEALTH_B={THROTTLE_HEALTH_B}。"
    )
    assert declared_def == THROTTLE_HEALTH_DEF, (
        f"docstring 宣稱 DEF={declared_def},實際 THROTTLE_HEALTH_DEF={THROTTLE_HEALTH_DEF}。"
    )


# ── L2:結構性反向釘(擋「好心的收斂」)────────────────────────────────────
def test_throttle_a_must_not_be_realigned_to_health_grade_a_min():
    """A 切點禁止對齊個股六因子健康分的 A 級線(user 2026-08-19 核准的修正)。

    這條釘的是**值**,不是措辭 —— 就算有人把註解改得很有說服力,只要把 A 設回 80
    (= `HEALTH_GRADE_A_MIN`)就紅燈。
    """
    assert THROTTLE_HEALTH_A != HEALTH_GRADE_A_MIN, (
        f"THROTTLE_HEALTH_A 被設成 {THROTTLE_HEALTH_A} = HEALTH_GRADE_A_MIN"
        f"({HEALTH_GRADE_A_MIN}) —— 這是 2026-08-19 由 user 核准修掉的**尺度借用錯誤**"
        " 被重新種回來了。HEALTH_GRADE_A_MIN 是個股六因子健康分的線;總經 health 值域"
        " 僅 [21.6, 78.1],照 80 切會讓『積極』帶在 4,769 個交易日裡一次都不觸發。"
        " 若真要改 A,請走總經 health 自身分布的校準(現值 70 = P90),不要對齊個股尺度。"
    )


# ── L3:措辭反向釘(那句肯定句不得以任何形式寫回來)──────────────────────
def test_docstring_never_asserts_a_aligns_with_health_grade_a_min():
    offenders = [
        ln.strip()
        for ln in _doc().splitlines()
        if "HEALTH_GRADE_A_MIN" in ln
        and not any(mark in ln for mark in _NEGATION_MARKERS)
    ]
    assert not offenders, (
        "docstring 出現未帶否定/說明標記的 HEALTH_GRADE_A_MIN 引用 —— 讀者會照著去"
        f"「恢復對齊」。違規行:{offenders}"
    )


# ── L4:理由不得被刪(只改數字不寫理由,下一個人還是會去對齊)────────────
def test_docstring_keeps_the_scale_explanation():
    doc = _doc()
    for token in ("個股六因子", "不同尺度"):
        assert token in doc, (
            f"docstring 缺少『{token}』——『A 為何不能對齊 HEALTH_GRADE_A_MIN』的理由"
            " 不得被精簡掉。只把數字改對而不寫理由,下一個做 SSOT 收斂的人仍會去對齊。"
        )


# ── 持股% 帶宣稱值 == THROTTLE_TIERS 實際值 ─────────────────────────────
def test_docstring_pct_band_claim_matches_tiers():
    """docstring 宣稱持股帶 80/50/20;同一種腐爛方式(值變了、文字沒變)一併釘住。"""
    assert "80/50/20" in _doc(), "docstring 持股% 帶宣稱行遺失或改格式"
    assert THROTTLE_TIERS[0][1] == 80, "積極帶下界(EXPOSURE_BULL)與 docstring 宣稱不符"
    assert THROTTLE_TIERS[1][1] == 50, "中性帶下界(EXPOSURE_NEUTRAL)與 docstring 宣稱不符"
    assert THROTTLE_TIERS[-1][2] == 20, "防禦帶上界(EXPOSURE_BEAR)與 docstring 宣稱不符"


# ── 三個切點裡唯一的真對齊,值得一條真的跨模組 pin ──────────────────────
def test_def_cut_really_aligns_with_defense_threshold_default():
    """DEF=35 與 HEALTH_DEFENSE_THRESHOLD 預設同為**總經 health** 尺度 → 真對齊。

    ⚠️ 不要照本測試「補一條 B 對齊 HEALTH_GRADE_B_MIN」——理由見本檔 docstring 末段。
    """
    assert THROTTLE_HEALTH_DEF == HEALTH_DEFENSE_THRESHOLD_DEFAULT, (
        f"THROTTLE_HEALTH_DEF={THROTTLE_HEALTH_DEF} 已與 "
        f"HEALTH_DEFENSE_THRESHOLD_DEFAULT={HEALTH_DEFENSE_THRESHOLD_DEFAULT} 脫鉤;"
        " docstring 仍宣稱兩者對齊 → 兩邊擇一修正。"
    )
