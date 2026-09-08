"""2026-09-08 倒站 hotfix 守衛 — requirements.txt 的 upper bound 不得再消失。

事故
────
Streamlit Cloud 於 2026-09-08 01:27 UTC 顯示「Error installing requirements.」
(pip 裝不起來,不是程式碼錯誤)。requirements.txt 在該次事故前的五個 commit 中
**一次都沒被動過**,所以不是自家改壞的 —— 是上游某個無上限的相依浮動到了新版。

`peewee` 就是那個無上限的洞:它不是本專案直接 import 的套件,而是 yfinance 的相依,
yfinance 1.7.0 宣告 `peewee>=3.16.2`(**沒有上限**),resolver 因此會抓當日新版。
peewee 4.5.1 發布於事故前 7 分鐘,且是整個相依閉包裡該時窗內唯一的新版本。

⚠️ 本守衛守的是「**cap 還在不在**」,不是「peewee 就是根因」
──────────────────────────────────────────────────────────
根因**沒有被確證**(沒有人看過雲端實際的 pip 日誌;而且 peewee 4.5.1 是純 Python
wheel `py3-none-any`,cp314 可直接安裝,找不到致炸機制)。完整的誠實揭露寫在
`requirements.txt` 該行上方的註解裡,含解禁條件。

**為什麼這幾條不是恆真式**(§-2 規則 6 / 本 repo「假守衛」病史)
───────────────────────────────────────────────────────────
下面的版本號(4.5.1 / 4.5.0 / 4.4.0 / 3.16.1)全部**寫死在本測試檔裡**,
不是從 requirements.txt 讀出來再跟自己比。檔案端只提供「宣告的 specifier」,
測試端提供「該 specifier 必須怎麼回答」,兩邊是獨立的來源,所以會真的紅:
  • cap 被刪掉      → `4.5.1 in spec` 變成 True → 紅
  • cap 放寬成 <4.6 → 同上 → 紅
  • 被改成 ==4.5.0  → `4.4.0 in spec` 變成 False → 紅
  • floor 掉到 yfinance 要求以下 → `3.16.1 not in spec` 失敗 → 紅
`test_every_requirement_declares_an_upper_bound` 檢的是**結構性質**(有沒有
上界運算子),不是數值比對 —— 它在本次修正前對 peewee 就是紅的(當時根本沒宣告)。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

_REPO = Path(__file__).resolve().parents[1]
_REQ_PATH = _REPO / "requirements.txt"

# 上界運算子(`~=` 也隱含上界,一併視為合格)
_UPPER_OPS = ("<", "<=", "~=", "==")


def _requirements_text() -> str:
    return _REQ_PATH.read_text(encoding="utf-8")


def _active_requirements() -> list[Requirement]:
    """回傳 requirements.txt 裡所有「真的會被 pip 讀到」的需求行。"""
    out: list[Requirement] = []
    for raw in _requirements_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        out.append(Requirement(line))
    return out


def _spec_for(name: str) -> SpecifierSet:
    matches = [r for r in _active_requirements()
               if r.name.lower().replace("_", "-") == name.lower().replace("_", "-")]
    assert matches, (
        f"requirements.txt 找不到 `{name}` 的宣告。"
        f"\n若這是有意識的移除,請一併刪掉本守衛並在 commit 說明理由 —— "
        f"不要只是讓守衛靜靜地失去意義。"
    )
    assert len(matches) == 1, f"`{name}` 在 requirements.txt 被宣告了 {len(matches)} 次(SSOT 破裂)"
    return matches[0].specifier


def _comment_block_above(name: str) -> list[str]:
    """回傳緊鄰某個需求行上方、連續的註解行。

    ⚠️ 必須用「行」定位,不能用 `text.find("peewee>=")` —— 註解裡就引用了
    `peewee>=3.16.2` 這個字串,字串搜尋會命中註解自己而不是真正的需求行
    (本守衛第一版就是這樣假紅的)。
    """
    lines = _requirements_text().splitlines()
    idx = next(
        (i for i, ln in enumerate(lines)
         if ln.split("#", 1)[0].strip().lower().startswith(name.lower())),
        None,
    )
    assert idx is not None, f"requirements.txt 找不到 `{name}` 那一行"
    block: list[str] = []
    for i in range(idx - 1, -1, -1):
        if lines[i].lstrip().startswith("#"):
            block.append(lines[i])
        else:
            break
    return block


class TestPeeweeTransitiveCap:
    """peewee 是 yfinance 的 transitive 相依,必須由我們顯式壓上界。"""

    def test_peewee_is_declared(self):
        """peewee 必須留在 requirements.txt —— 沒宣告就等於沒有上限。"""
        assert _spec_for("peewee") is not None

    def test_peewee_4_5_1_is_excluded(self):
        """4.5.1 = 事故前 7 分鐘發布、時窗內唯一的新版本,必須被擋掉。"""
        spec = _spec_for("peewee")
        assert Version("4.5.1") not in spec, (
            "peewee 4.5.1 又被放進可解範圍了。它是 2026-09-08 倒站當下唯一的新變數;"
            "在拿到雲端 pip 日誌確認真因之前不得放寬(解禁條件見 requirements.txt 註解)。"
        )

    def test_peewee_4_5_0_still_allowed(self):
        """cap 的邊界要正好落在 4.5.1,不能連上一次 rebuild 用的 4.5.0 也砍掉。

        4.5.0 是 PR #668(2026-09-07 23:09:01 UTC)那次 rebuild 當下的版本 ——
        cap 的目的是「回到那個狀態」,不是「再往回退」。
        """
        assert Version("4.5.0") in _spec_for("peewee")

    def test_peewee_is_a_range_not_an_exact_pin(self):
        """禁止寫成 `==4.5.0`。

        寫死單一版本會製造新的脆弱點:上游一 yank 該版本,部署就直接無解。
        用上界保留「4.5.1 以下都可以」的迴旋空間。
        """
        spec = _spec_for("peewee")
        allowed = [v for v in ("4.4.0", "4.5.0") if Version(v) in spec]
        assert len(allowed) >= 2, (
            f"peewee 的 specifier 看起來被釘成單一版本(只有 {allowed} 可解)。"
            "hotfix 要用上界,不要用 `==`。"
        )

    def test_peewee_floor_not_below_yfinance_requirement(self):
        """floor 不得低於 yfinance 自己宣告的 `peewee>=3.16.2`。

        壓低 floor 不會讓 resolver 更好過(yfinance 的宣告仍然生效),
        只會讓 requirements.txt 說出一件不是真的事。
        """
        assert Version("3.16.1") not in _spec_for("peewee"), (
            "peewee 的 floor 掉到 yfinance 要求的 3.16.2 以下了 —— 宣告與實況不符。"
        )

    def test_cap_documents_its_release_condition(self):
        """緊鄰 peewee 那行上方的註解區塊必須寫出「解禁條件」。

        本檔既有的兩個 hotfix cap(pyarrow / starlette)都寫了解禁條件。
        沒有解禁條件的 cap 會變成沒人敢動的永久遺跡 —— 這條把該慣例釘住。
        """
        block = _comment_block_above("peewee")
        assert block, "peewee 那行上方沒有任何說明註解"
        assert any("解禁條件" in ln for ln in block), (
            "peewee cap 上方的註解沒有寫「解禁條件」。"
            "照 pyarrow / starlette 兩段既有前例,每個 hotfix cap 都要寫清楚何時可以拿掉。"
        )

    def test_cap_does_not_claim_an_unproven_root_cause(self):
        """註解不得把「peewee 是根因」寫成已確證的事實。

        實測:peewee 4.5.1 是純 Python wheel(`py3-none-any`,Root-Is-Purelib),
        cp314 直接安裝、不需編譯,METADATA 與 4.5.0 逐行相同 —— 找不到致炸機制。
        依 CLAUDE.md §-2 規則 6,未經證實的宣稱不得寫成既成事實。
        """
        block = _comment_block_above("peewee")
        assert any("不是已確證的根因" in ln or "未確證" in ln for ln in block), (
            "peewee cap 的註解必須標明「這是時序推論,不是已確證的根因」。"
        )


class TestNoUnboundedRequirement:
    """requirements.txt 的立檔策略(檔頭 v18.395)是『全套 upper bound pin』。

    這條策略在本次事故之前**從來沒有被機器檢查過** —— peewee 這個洞就是
    這樣長出來的(它從沒被宣告,自然也沒人發現它沒有上限)。本測試把該策略釘住。
    """

    def test_every_requirement_declares_an_upper_bound(self):
        offenders = [
            str(r) for r in _active_requirements()
            if not any(s.operator in _UPPER_OPS for s in r.specifier)
        ]
        assert not offenders, (
            "下列相依沒有 upper bound,會浮動到當日剛發布的新版:\n  "
            + "\n  ".join(offenders)
            + "\n\nrequirements.txt 檔頭的策略是『全套 upper bound pin』"
              "(v18.395 P5-B6),本 repo 已因此類浮動倒站三次:"
              "pyarrow 25.0.0(2026-07-10)、starlette 1.4.0(2026-08-05)、"
              "本次 2026-09-08。請補上上界並在該行上方寫明解禁條件。"
        )

    def test_every_requirement_declares_a_floor(self):
        """有上界沒下界一樣危險:resolver 可能解到遠古版本以滿足別的約束。"""
        offenders = [
            str(r) for r in _active_requirements()
            if not any(s.operator in (">=", ">", "==", "~=") for s in r.specifier)
        ]
        assert not offenders, "下列相依沒有 floor:\n  " + "\n  ".join(offenders)


@pytest.mark.parametrize("name", ["pyarrow", "starlette", "peewee"])
def test_known_incident_caps_survive(name: str):
    """三次倒站各自留下的 cap 都必須還在,且都仍是有上界的。

    這三條是「被實際事故打出來的」pin,任何一條被順手拿掉都要在 CI 就紅,
    而不是等到下一次部署倒站才發現。
    """
    spec = _spec_for(name)
    assert any(s.operator in _UPPER_OPS for s in spec), f"{name} 的 upper bound 不見了"
