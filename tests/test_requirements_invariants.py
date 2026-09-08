"""requirements.txt 的通用不變式守衛(與任何單一套件無關)。

本檔的來歷 —— 為什麼是「改寫」而不是「新增」
──────────────────────────────────────────────
前身是 `tests/test_hotfix_peewee_cap_2026_09_08.py`(2026-09-08 倒站 hotfix 的
守衛,12 條裡有 8 條綁在 `peewee<4.5.1` 這條 pin 上)。

**那條 pin 建立的前提後來被雲端日誌推翻了**:事故真正倒在 Streamlit Cloud 的
**apt 階段**(repo 根目錄有 `packages.txt` → 先跑 `apt-get` → Debian
bullseye-security 的 Release 檔已過期 → 非零退出 → 安裝流程中止),
**`pip` 從頭到尾一次都沒有執行**。pip 沒跑,pip 端的任何版本都不可能是原因;
peewee 4.5.1 與次要嫌疑 numpy 2.5.3 都是清白的。那條 pin 依它自己寫下的解禁
條件(「若確認與 peewee 無關,直接刪掉本行」)已撤除,綁著它的 8 條測試隨之失效。

**但有幾條測試從一開始就與 peewee 無關,是 requirements.txt 的結構性不變式**,
它們的價值獨立於那次誤判,所以保留在本檔:
  • `test_every_requirement_declares_an_upper_bound` —— 檔頭 v18.395 的立檔策略
    是「全套 upper bound pin」,而這條策略在 2026-09-08 之前**從來沒有被機器
    檢查過**。本 repo 已因上游浮動到當日新版倒站兩次(pyarrow 25.0.0 /
    starlette 1.4.0),這條是唯一擋得住第三次的東西。
  • `test_every_requirement_declares_a_floor` —— 同一件事的另一半。
  • 事故 cap 的存活與解禁條件 —— pyarrow / starlette 兩條 pin 是被真實事故打
    出來的,任何一條被順手拿掉都該在 CI 就紅,而不是等下一次部署倒站才發現。

⚠️ 刻意**不**加的東西:本檔不含任何「peewee 不得被重新 cap」之類的反向守衛。
若日後真有證據指向 peewee,該 cap 應該可以自由加回來 —— 守衛守的是
**結構紀律**,不是某一次的判斷結論。

為什麼這幾條不是恆真式
──────────────────────
它們檢的是**結構性質**(有沒有上界 / 下界運算子、宣告有沒有重複、事故 cap 還在
不在),條件全部寫死在測試端,requirements.txt 只提供被檢的宣告 —— 兩邊是獨立
的來源。刪掉任一個 cap、拿掉任一個上界、把同一個套件宣告兩次,都會真的紅。
(`test_every_requirement_declares_an_upper_bound` 在 2026-09-08 之前對當時
未宣告的 peewee 就是紅的。)

📌 `packages.txt` 這個真因的根因防護在 `tests/test_deploy_no_apt_packages.py`,
不在本檔 —— 那是部署層(apt)的事,與 pip 相依宣告正交。
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
_FLOOR_OPS = (">=", ">", "==", "~=")

# 被真實事故打出來的 cap。每一條都在 requirements.txt 該行上方留了事故說明 +
# 解禁條件;拿掉任何一條都必須是有意識的決定,而不是重構時順手掃掉。
#   pyarrow  — 2026-07-10 pyarrow 25.0.0 當日發布 → cp314 Segmentation fault
#   starlette— 2026-08-05 starlette 1.4.0 當日發布 → GZipResponder 簽章不相容
# (2026-09-08 那次的 peewee **不在此列** —— 見檔頭 docstring,那條 pin 的前提
#  已被雲端日誌推翻,真因是 apt 階段,pip 根本沒執行。)
_INCIDENT_CAPS = ("pyarrow", "starlette")


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


def _canon(name: str) -> str:
    return name.lower().replace("_", "-")


def _spec_for(name: str) -> SpecifierSet:
    matches = [r for r in _active_requirements() if _canon(r.name) == _canon(name)]
    assert matches, (
        f"requirements.txt 找不到 `{name}` 的宣告。"
        f"\n若這是有意識的移除,請一併把它從 _INCIDENT_CAPS 拿掉並在 commit 說明理由 —— "
        f"不要只是讓守衛靜靜地失去意義。"
    )
    assert len(matches) == 1, f"`{name}` 在 requirements.txt 被宣告了 {len(matches)} 次(SSOT 破裂)"
    return matches[0].specifier


def _comment_block_above(name: str) -> list[str]:
    """回傳緊鄰某個需求行上方、連續的註解行。

    ⚠️ 必須用「行」定位,不能用 `text.find("pyarrow>=")` —— 註解裡就引用了
    套件名與版本字串,字串搜尋會命中註解自己而不是真正的需求行
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


# ══════════════════════════════════════════════════════════════
# 通用不變式 — 與任何單一套件無關
# ══════════════════════════════════════════════════════════════

class TestNoUnboundedRequirement:
    """requirements.txt 的立檔策略(檔頭 v18.395)是『全套 upper bound pin』。

    這條策略在 2026-09-08 之前**從來沒有被機器檢查過** —— 也因此,
    「哪些相依有上界」一直是靠人眼維護的,而人眼漏掉過(peewee 從沒被宣告,
    自然也沒人發現它沒有上限)。本測試把該策略釘住。
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
              "(v18.395 P5-B6),本 repo 已因此類浮動倒站兩次:"
              "pyarrow 25.0.0(2026-07-10)、starlette 1.4.0(2026-08-05)。"
              "請補上上界並在該行上方寫明解禁條件。"
        )

    def test_every_requirement_declares_a_floor(self):
        """有上界沒下界一樣危險:resolver 可能解到遠古版本以滿足別的約束。"""
        offenders = [
            str(r) for r in _active_requirements()
            if not any(s.operator in _FLOOR_OPS for s in r.specifier)
        ]
        assert not offenders, "下列相依沒有 floor:\n  " + "\n  ".join(offenders)

    def test_no_duplicate_declarations(self):
        """同一個套件不得被宣告兩次 —— 兩行互相矛盾時,結果取決於 pip 的解析順序。"""
        seen: dict[str, int] = {}
        for r in _active_requirements():
            seen[_canon(r.name)] = seen.get(_canon(r.name), 0) + 1
        dupes = sorted(n for n, c in seen.items() if c > 1)
        assert not dupes, (
            "下列套件在 requirements.txt 被宣告超過一次(SSOT 破裂):\n  "
            + "\n  ".join(dupes)
        )


# ══════════════════════════════════════════════════════════════
# 事故 cap — 被真實倒站打出來的 pin,不得靜靜消失
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", _INCIDENT_CAPS)
def test_known_incident_caps_survive(name: str):
    """每一條事故 cap 都必須還在,且都仍是有上界的。

    任何一條被順手拿掉都要在 CI 就紅,而不是等到下一次部署倒站才發現。
    """
    spec = _spec_for(name)
    assert any(s.operator in _UPPER_OPS for s in spec), (
        f"{name} 的 upper bound 不見了 —— 它是被真實倒站事故打出來的 pin。"
        f"\n若確定可以解禁,請連同該行上方的事故註解一起刪掉,並把 {name} "
        f"從本檔的 _INCIDENT_CAPS 移除。"
    )


@pytest.mark.parametrize("name", _INCIDENT_CAPS)
def test_incident_caps_document_their_release_condition(name: str):
    """緊鄰事故 cap 上方的註解區塊必須寫出「解禁條件」。

    沒有解禁條件的 cap 會變成沒人敢動的永久遺跡 —— 三年後沒有人知道它為什麼在、
    也沒有人知道什麼時候可以拿掉,於是它就永遠留著,順便把整條相依鏈釘死在舊版。
    這條把 pyarrow / starlette 兩段既有前例定下的慣例釘住。
    """
    block = _comment_block_above(name)
    assert block, f"{name} 那行上方沒有任何說明註解"
    assert any("解禁條件" in ln for ln in block), (
        f"{name} cap 上方的註解沒有寫「解禁條件」。"
        "照 pyarrow / starlette 兩段既有前例,每個 hotfix cap 都要寫清楚何時可以拿掉。"
    )


# ══════════════════════════════════════════════════════════════
# 2026-09-08 事故的誠實記錄必須留在檔頭
# ══════════════════════════════════════════════════════════════

def test_header_records_the_2026_09_08_apt_incident():
    """requirements.txt 檔頭必須保留 2026-09-08 的事故紀錄與「別再加 packages.txt」的警告。

    為什麼要用測試釘住一段**註解**:這段註解是目前唯一寫著「真因在 apt、
    pip 根本沒執行」的地方。它一旦被後續整理掉,下一個人看到的就只剩
    「peewee 曾經被 cap 又被拿掉」這個沒有上下文的片段,很可能重蹈覆轍 ——
    重新 cap 一個清白的套件,或者把 packages.txt 加回來。

    (這不是恆真式:把檔頭那段刪掉、或把 packages.txt 的警告拿掉,本條就紅。)
    """
    text = _requirements_text()
    for needle in ("2026-09-08", "packages.txt", "apt"):
        assert needle in text, (
            f"requirements.txt 檔頭的 2026-09-08 事故紀錄不見了(找不到 {needle!r})。"
            "\n真因是 Streamlit Cloud 的 apt 階段失敗(Debian bullseye-security "
            "Release 檔過期),pip 從頭到尾沒有執行。這段脈絡刪掉之後,"
            "下一個人只會看到一條被拿掉的 peewee cap,無從得知真正發生了什麼。"
        )
