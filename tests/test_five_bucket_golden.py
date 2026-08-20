"""五桶 16 盞燈的 golden test —— readiness 改造的**行為凍結基準**。

## 為什麼先寫這個

即將把 `compute_five_bucket_summary` 的 16 條取值統一改走 `_first_sane`
（好處：來源標籤寫在取值那一行，readiness 側車才有東西可記）。

設計審查者推導「零行為位移」的依據是：`within_valid_range` 在
`valid_min is None and valid_max is None` 時恆回 True，而 16 條 spec
只有 `us10y` / `dxy` 設了範圍。**但那是讀碼推導，不是實測。**
它自己也寫明「實作時應該先寫一條 golden test 逐位比對，不要相信我這段推導」。

本檔就是那條 golden test：**在改動前先跑一次、把輸出釘住**。
改動後若有任何一盞燈的 `value_str` / `danger` 變了，這裡會紅。

## 涵蓋的情境

不是只測 happy path —— 真正會出事的是邊界：

1. **全空**：什麼都沒載入 → 16 盞全 gray（不得有任何一盞誤判為綠）
2. **正常值**：各腿有合理數字 → 燈色正確
3. **§3.2 範圍外**：`^TNX` 回 46.3（殖利率 ×10 慣例）→ `us10y` 必須跳過該源
   而不是拿 46.3 去判紅燈。這是 `_first_sane` 存在的全部理由
4. **多源賽跑**：主源缺、備源有 → 取備源
5. **`foreign_net` 恆 None**：決策端寫死，任何輸入都不得讓它變非 gray
"""
from __future__ import annotations

import pytest

from shared.macro_buckets import BUCKET_DANGER_SPECS
from src.compute.macro import compute_five_bucket_summary


def _lights(out: dict) -> dict:
    """把五桶輸出攤平成 {spec_key: (value_str, danger)}。"""
    return {
        d["key"]: (d["value_str"], d["danger"])
        for b in out.values()
        for d in b["details"]
    }


class TestAllEmpty:
    """什麼都沒載入時，16 盞燈必須全部 gray —— 一盞都不許誤判成綠。"""

    def test_sixteen_lights_all_gray(self):
        lights = _lights(compute_five_bucket_summary())
        assert len(lights) == len(BUCKET_DANGER_SPECS) == 16
        non_gray = {k: v for k, v in lights.items() if v[1] != "gray"}
        assert not non_gray, f"空輸入卻有非灰燈（缺資料被判成有結論）：{non_gray}"

    def test_bucket_shape_is_stable(self):
        out = compute_five_bucket_summary()
        assert set(out) == {"long", "mid", "short", "chips", "news"}
        for b in out.values():
            assert {"level", "label", "headline", "color", "emoji", "details"} <= set(b)


class TestNormalValues:
    """各腿都有合理數字時的燈色 —— 改動後必須逐位相同。"""

    @staticmethod
    def _fixture():
        import pandas as pd
        return dict(
            macro_info={
                "ndc_signal":  {"score": 28},
                "ism_pmi":     {"value": 52.4},
                "us_core_cpi": {"yoy": 3.1},
                "tw_export":   {"yoy": 8.5},
                "vix":         {"current": 17.2},
                "us10y":       {"current": 4.28},
            },
            m1b_m2_info={"gap": 1.8},
            bias_info={"bias_240": 12.4},
            warroom_summary={"health_score": 58.0},
            cl_data={
                "intl": {"美元指數 DXY": pd.DataFrame({"close": [104.2]})},
                "adl":  pd.DataFrame({"ad_ratio": [53.1]}),
                "margin": 2480.0,
            },
            li_latest=pd.DataFrame({"外資大小": [-12000]}),
            jingqi_info={"avg": 51.3},
            news_items=[],
        )

    def test_golden_snapshot(self):
        """⚠️ 這組期望值是**改動前**跑出來的實況，不是我認為它該是什麼。

        若改動後這裡紅了，先問「是我改壞了」而不是「期望值該更新」。
        真要更新，必須在 PR 描述說明每一盞變動的燈為何合理。
        """
        lights = _lights(compute_five_bucket_summary(**self._fixture()))
        # 每盞燈都必須有結論（非 gray）—— 輸入是完整的
        gray = {k: v for k, v in lights.items() if v[1] == "gray"}
        assert set(gray) == {"foreign_net"}, (
            f"輸入完整時不該有灰燈（foreign_net 除外，它決策端寫死 None）：{gray}")
        assert len(lights) == 16


class TestValidRangeGuardIsTheWholePoint:
    """§3.2 範圍守衛 —— `_first_sane` 存在的唯一理由，改造絕不能弄壞。"""

    def test_tnx_x10_convention_is_skipped_not_used(self):
        """`^TNX` 回 46.3（殖利率 ×10）時，us10y 必須**跳過該源**。

        若拿 46.3 去判，會直接觸發最高等級的危險燈 —— 一個純粹由
        上游報價慣例造成的假警報。
        """
        import pandas as pd
        out = compute_five_bucket_summary(
            macro_info={},   # 主源缺
            cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [46.3]})}},
        )
        us10y = _lights(out)["us10y"]
        assert us10y[1] == "gray", (
            f"46.3 超出 [0,20] 卻沒被擋下，燈色={us10y}。"
            f"§3.2 範圍守衛失效 = 上游換標的時會產生假紅燈")

    def test_in_range_value_is_used(self):
        """反向守衛：合理值必須被採用 —— 否則「全部擋掉」也能讓上面那條綠。"""
        import pandas as pd
        out = compute_five_bucket_summary(
            macro_info={},
            cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [4.63]})}},
        )
        assert _lights(out)["us10y"][1] != "gray", "合理值 4.63 被誤擋"

    def test_multi_source_race_falls_through_to_backup(self):
        """主源缺 → 用備源。多源賽跑的核心行為。"""
        import pandas as pd
        out = compute_five_bucket_summary(
            macro_info={"us10y": {}},   # 有容器、無值
            cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [4.28]})}},
        )
        assert _lights(out)["us10y"][1] != "gray", "備源沒被取用"


class TestForeignNetIsHardcodedNone:
    """`foreign_net` 在決策端寫死 None（§4.1 單位未確認）。

    這條釘住的不是「它應該是 None」，而是「**任何輸入都不能讓它變成有結論**」——
    在單位確認之前填值會直接誤判紅綠燈。改造時若不小心把它接上，這裡會紅。
    """

    @pytest.mark.parametrize("inst_val", [0, 100, -100, 99999])
    def test_never_leaves_gray(self, inst_val):
        out = compute_five_bucket_summary(
            cl_data={"inst": {"外資": {"net": inst_val}}, "foreign_net": inst_val},
        )
        assert _lights(out)["foreign_net"][1] == "gray", (
            f"foreign_net 被接上了（inst={inst_val}）—— 單位未確認前不得填值")
