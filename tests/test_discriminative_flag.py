"""tests/test_discriminative_flag.py — `DangerSpec.discriminative` 守衛（2026-08-25）

user 核准把「鑑別力失效」從**開發者註解**升格為**可被程式驗證的旗標**。

## 這個旗標在守什麼

`shared/macro_buckets.py:318` 一直寫著:
> 絕對門檻已被市值成長淹沒,實測 5,148 億早已穿透兩線 → 燈號恆紅、鑑別力歸零

但那句話**只有讀 code 的人看得到**。畫面上,一盞「恆紅因為門檻壞了」的燈
和一盞「真的很危險」的紅燈**長得一模一樣** —— 使用者沒有任何方式分辨。
一盞恆亮的警告等於沒有警告(同 G2 月頻新鮮度、同 EX-CACHE-1 清單失真的教訓)。

## 與 `wired` 的分工(本檔守的核心不變式)

| 旗標 | 語意 | 燈會亮嗎 | 計入分母嗎 |
|---|---|---|---|
| `wired=False` | 決策端刻意沒接取值 | ❌ 永遠不亮 | ❌ 不計入 |
| `discriminative=False` | **有值、燈會亮**,但門檻失效 | ✅ 照常亮 | ✅ **照常計入** |

兩者都是「別信這盞燈」,但成因與處置完全相反。把它們混為一談 = 又造一個
恆亮警告。故本檔特別守 **discriminative 不得影響判燈與分母**。

## 為什麼要守「文案不得含開發者備忘」

v19.170 有過前科:`margin` 的 `note` 欄誤植了開發者備忘(含版本號、實測值、
模組路徑 `shared/relative_thresholds.margin_leverage_ratio`),而該欄會
**原文渲染在五桶籌碼卡上給一般使用者看**,實機驗證確認整段被印到畫面。
`degraded_reason` 是同一類「會直接印給使用者」的欄位,踩同一個坑只是時間問題。

⚠️ 本檔只測 L0 純資料 + L2 純函式,**不碰 streamlit / 不做網路 I/O**。
"""
from __future__ import annotations

import re

import pytest

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    SPECS_BY_KEY,
    classify_danger,
)
from src.compute.macro.macro_helpers import compute_five_bucket_summary

#: 目前唯一被標記者。新增時本清單要同步 —— 強迫「標記」是一個有意識的決定,
#: 而不是有人順手加個 flag 就悄悄改變了一盞燈的可信度語意。
KNOWN_DEGRADED_KEYS: frozenset[str] = frozenset({"margin"})

#: 開發者備忘的特徵。踩到任一條 = 這段文字不是寫給一般使用者看的。
_DEV_MEMO_PATTERNS = (
    (re.compile(r"\bv\d+\.\d+"), "版本號(如 v19.170)"),
    (re.compile(r"\.py\b"), "模組路徑(如 macro_buckets.py)"),
    (re.compile(r"[A-Za-z_]+\.[a-z_]+\("), "函式呼叫(如 classify_by_pct_rank()"),
    (re.compile(r"SSOT:|DESIGN:"), "來源標記(SSOT:/DESIGN:)"),
    (re.compile(r"\bTODO\b|\bFIXME\b|\bXXX\b"), "TODO/FIXME 標記"),
)


def _readiness() -> dict:
    """跑一次五桶取 readiness 側車(無輸入 → 全部 missing,但 16 筆紀錄仍在)。"""
    rd: dict = {}
    compute_five_bucket_summary(readiness_out=rd)
    return rd


# ════════════════════════════════════════════════════════════════
# 一、必填守衛 —— 標了旗標就一定要說明理由
# ════════════════════════════════════════════════════════════════
class TestReasonIsMandatory:

    def test_flag_false_requires_reason(self):
        """`discriminative=False` 必填 `degraded_reason`。

        比照 `wired=False` 必填 `unwired_reason` 的既有慣例。沒有理由的旗標
        等於「這盞燈不能信,但我不告訴你為什麼」—— 比不標更糟。
        """
        offenders = [
            s.key for s in BUCKET_DANGER_SPECS
            if not s.discriminative and not (s.degraded_reason or "").strip()
        ]
        assert not offenders, (
            f"以下 spec 標了 discriminative=False 卻沒填 degraded_reason:{offenders}"
        )

    def test_reason_only_when_flag_false(self):
        """反向:沒標旗標就不該有 `degraded_reason`(避免寫了卻不生效的孤兒文案)。"""
        offenders = [
            s.key for s in BUCKET_DANGER_SPECS
            if s.discriminative and (s.degraded_reason or "").strip()
        ]
        assert not offenders, (
            f"以下 spec 有 degraded_reason 但 discriminative 仍為 True(文案不會生效):"
            f"{offenders}"
        )

    def test_marked_set_matches_known_list(self):
        """被標記的集合必須與本檔清單一致 —— 新增/移除都要有人有意識地改測試。"""
        marked = {s.key for s in BUCKET_DANGER_SPECS if not s.discriminative}
        assert marked == KNOWN_DEGRADED_KEYS, (
            f"標記集合改變:實際 {sorted(marked)} vs 預期 {sorted(KNOWN_DEGRADED_KEYS)}。"
            f"若這是有意的,請同步更新 KNOWN_DEGRADED_KEYS 並在 PR 說明理由。"
        )


# ════════════════════════════════════════════════════════════════
# 二、文案品質 —— 這欄會直接印給一般使用者看
# ════════════════════════════════════════════════════════════════
class TestReasonIsUserFacing:

    @pytest.mark.parametrize("key", sorted(KNOWN_DEGRADED_KEYS))
    def test_no_developer_memo_leak(self, key):
        """v19.170 前科重演守衛:不得含版本號 / 模組路徑 / 函式呼叫 / SSOT 標記。"""
        txt = SPECS_BY_KEY[key].degraded_reason
        hits = [why for pat, why in _DEV_MEMO_PATTERNS if pat.search(txt)]
        assert not hits, (
            f"{key} 的 degraded_reason 含開發者備忘({'、'.join(hits)}):\n{txt}\n"
            f"技術細節請留在程式碼註解,本欄只寫使用者看得懂的話。"
        )

    @pytest.mark.parametrize("key", sorted(KNOWN_DEGRADED_KEYS))
    def test_tells_user_what_to_do_instead(self, key):
        """光說「不能信」沒有用 —— 必須告訴使用者**改看什麼**。"""
        txt = SPECS_BY_KEY[key].degraded_reason
        assert "該怎麼看" in txt or "改看" in txt, (
            f"{key} 的 degraded_reason 只說了不能信,沒說該改看什麼:\n{txt}"
        )

    @pytest.mark.parametrize("key", sorted(KNOWN_DEGRADED_KEYS))
    def test_reason_is_substantial(self, key):
        """太短的理由等於沒有理由(如「門檻壞了」)。"""
        txt = (SPECS_BY_KEY[key].degraded_reason or "").strip()
        assert len(txt) >= 40, f"{key} 的 degraded_reason 過短({len(txt)} 字):{txt}"


# ════════════════════════════════════════════════════════════════
# 三、零行為變更 —— 本旗標是「加註」,不是「改判」
# ════════════════════════════════════════════════════════════════
class TestFlagChangesNothing:
    """這組是本檔最重要的部分。

    旗標一旦開始影響判燈或分母,它就從「誠實標示」變成「行為變更」,
    而行為變更需要獨立回測。這組測試把那條界線釘死。
    """

    @pytest.mark.parametrize("value", [None, 0.0, 2000.0, 3000.0, 5148.0, 99999.0])
    def test_classify_danger_ignores_the_flag(self, value):
        """判燈結果完全不看 `discriminative` —— 該紅還是紅。"""
        spec = SPECS_BY_KEY["margin"]
        assert spec.discriminative is False        # 前提:它真的被標了
        got = classify_danger(value, spec)
        # 依 high_bad + yellow=2500 / red=3400 的既有語意驗算,不引用旗標
        if value is None:
            expect = "gray"
        elif value >= spec.red:
            expect = "red"
        elif value >= spec.yellow:
            expect = "yellow"
        else:
            expect = "green"
        assert got == expect, f"值 {value} 判成 {got},預期 {expect}(旗標不該影響判燈)"

    def test_margin_still_counts_in_the_denominator(self):
        """與 `wired=False` 的關鍵差異:這盞燈**照常計入分母**。

        理由:它是真的有值、真的會亮。把它踢出分母等於謊報「有幾盞燈可信」。
        """
        rd = _readiness()
        assert rd["margin"]["wired"] is True, "margin 是有接線的,不該被標成未接線"
        wired_keys = {k for k, v in rd.items() if v.get("wired")}
        assert "margin" in wired_keys

    def test_flag_is_schema_additive(self):
        """其餘 spec 一律預設 True —— 新欄位不改變任何既有 spec 的語意。"""
        others = [s for s in BUCKET_DANGER_SPECS if s.key not in KNOWN_DEGRADED_KEYS]
        assert others, "註冊表不該只有被標記者"
        assert all(s.discriminative is True for s in others)
        assert all((s.degraded_reason or "") == "" for s in others)


# ════════════════════════════════════════════════════════════════
# 四、readiness 側車 —— 旗標要真的流到消費端
# ════════════════════════════════════════════════════════════════
class TestReadinessCarriesTheFlag:

    def test_every_record_has_the_field(self):
        """16 盞燈**全部**要帶旗標。漏一盞 = 消費端得寫 `.get(..., True)` 猜。"""
        rd = _readiness()
        missing = [k for k, v in rd.items() if "discriminative" not in v]
        assert not missing, f"readiness 缺 discriminative 欄位:{missing}"

    def test_flag_value_mirrors_the_spec(self):
        """側車的值必須等於 spec 的值 —— 不得有第二份會漂移的真相。"""
        rd = _readiness()
        for key, rec in rd.items():
            spec = SPECS_BY_KEY.get(key)
            if spec is None:
                continue
            assert rec["discriminative"] is bool(spec.discriminative), (
                f"{key}:側車 {rec['discriminative']} != spec {spec.discriminative}"
            )

    def test_exactly_the_known_keys_are_flagged(self):
        rd = _readiness()
        flagged = {k for k, v in rd.items() if not v.get("discriminative", True)}
        assert flagged == KNOWN_DEGRADED_KEYS
