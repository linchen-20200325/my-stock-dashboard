"""tests/test_b7c_m1b_proxy_mark.py — B7c：v2 今天頁 m1b 燈在「退到代理層」時要標明。

M1B/M2 央行兩層全敗、退到 ^TWII 動能代理（`macro_snapshot` 寫 `source='TWII-proxy'`）時：
  · L2 `compute_five_bucket_summary` 的 m1b 明細 `value_str` 後綴 v1 既有註記；
  · L2 readiness 側車 m1b 那一筆帶 `is_proxy=True`；
  · L5 `page_today.build_indicator_tile` 的卡值後綴同一個註記。
判定沿用 v1：**只揭露、不改燈**（燈號 / 桶等級照舊）。
非代理時：側車逐鍵不變、字串逐字元不變。

突變：拿掉 L0 判定（`is_m1b_m2_proxy` 恆 False）→ 代理層那幾條要轉紅。
"""
from __future__ import annotations

import pathlib

import pytest

from shared import macro_provenance as MP
from shared.macro_buckets import SPECS_BY_KEY, classify_danger, fmt_value
from src.compute.macro.macro_helpers import compute_five_bucket_summary
from src.ui.views import page_today as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_KEY = "m1b_m2_gap"
_NOTE = "（大盤動能代理估算）"   # v1 section_long 既有字面（v19.183 D2）

BANDS = {"green": ("綠", "#0ca30c"), "yellow": ("黃", "#fab219"),
         "red": ("紅", "#d03b3b"), "gray": ("無資料", "#8a8e96")}


def _band_label(band, _spec):
    return BANDS[band]


def _info(source, gap=-0.5):
    return {"m1b_yoy": 3.0, "m2_yoy": 3.0 - gap, "gap": gap, "source": source}


def _run(info):
    rd: dict = {}
    out = compute_five_bucket_summary(m1b_m2_info=info, readiness_out=rd)
    det = next(d for d in out["long"]["details"] if d["key"] == _KEY)
    return out, rd, det


def _tile(rec):
    return P.build_indicator_tile(_KEY, rec, requested=True, error="",
                                  band_label=_band_label, thr_text=None)


class TestNoteIsTheV1String:
    def test_l0_constant_is_v1_literal(self):
        # K1：不是新文案 —— 與 v1 長期桶 KPI 卡原本那串逐字相同
        assert MP.M1B_PROXY_VALUE_NOTE == _NOTE

    def test_v1_reads_the_l0_constant(self):
        src = (_ROOT / "src/ui/tabs/macro/section_long.py").read_text(encoding="utf-8")
        assert "M1B_PROXY_VALUE_NOTE if _is_m1b_proxy else ''" in src
        assert _NOTE not in src.replace(f"「{_NOTE}」", "")  # 只剩註解引述，無第二份字面


class TestProxyIsMarked:
    @pytest.mark.parametrize("src", [MP.M1B_PROXY_SOURCE_LABEL,
                                     MP.M1B_PROXY_SOURCE_LABEL_RAW])
    def test_l2_detail_and_sidecar(self, src):
        _out, rd, det = _run(_info(src))
        spec = SPECS_BY_KEY[_KEY]
        assert det["value_str"] == fmt_value(-0.5, spec) + _NOTE
        assert rd[_KEY]["is_proxy"] is True
        assert rd[_KEY]["state"] == "ok"

    def test_bool_flag_also_counts(self):
        info = _info("CBC-tier1")
        info["is_proxy_tier"] = True
        _out, rd, det = _run(info)
        assert det["value_str"].endswith(_NOTE)
        assert rd[_KEY]["is_proxy"] is True

    def test_v2_tile_value_has_note(self):
        _out, rd, _det = _run(_info(MP.M1B_PROXY_SOURCE_LABEL))
        tile = _tile(rd[_KEY])
        assert tile.card.value == fmt_value(-0.5, SPECS_BY_KEY[_KEY]) + _NOTE

    def test_headline_carries_note_when_m1b_is_main_cause(self):
        # D3（DL-f1-s17，客戶 2026-10-02 頁 1 ③「只顯示不計分」）：代理燈 gray → 只給 m1b 一盞時
        # 長期桶＝未載入（既有 headline）；真值時照舊由 m1b 當主因亮紅。
        out, _rd, _det = _run(_info(MP.M1B_PROXY_SOURCE_LABEL))
        assert out["long"]["level"] == "gray" and _NOTE not in out["long"]["headline"]
        out_r, _rd, _det = _run(_info("CBC-tier1"))
        assert out_r["long"]["level"] == "red"


class TestJudgementUnchanged:
    """~~v1 對 KPI 卡只揭露不改燈 → 燈號 / 桶等級與非代理時完全一樣。~~
    D3（DL-f1-s17，客戶 2026-10-02 頁 1 ③「M1B 代理值：只顯示不計分」）起：代理值**照樣顯示**
    （值＋註記，見上一類），但燈號走既有 gray（＝未載入），不進桶等級；真值照舊判燈。"""

    @pytest.mark.parametrize("gap", [-0.5, 0.5, 2.0])
    def test_lamp_and_bucket_same(self, gap):
        out_p, _, det_p = _run(_info(MP.M1B_PROXY_SOURCE_LABEL, gap))
        out_r, _, det_r = _run(_info("CBC-tier1", gap))
        assert det_r["danger"] == classify_danger(gap, SPECS_BY_KEY[_KEY])
        assert det_p["danger"] == "gray"
        assert out_p["long"]["level"] == "gray" and out_r["long"]["level"] == det_r["danger"]
        tp = _tile(_run(_info(MP.M1B_PROXY_SOURCE_LABEL, gap))[1][_KEY])
        tr = _tile(_run(_info("CBC-tier1", gap))[1][_KEY])
        assert tp.card.state == tr.card.state                  # 仍是「有值」那一態（照樣顯示）
        assert (tp.signal_text, tp.signal_color) == BANDS["gray"]
        assert tp.facts == tr.facts


class TestNonProxyByteIdentical:
    @pytest.mark.parametrize("src", ["CBC-tier1", "CBC-tier2", "FRED", "IMF(2025)", None])
    def test_no_note_no_new_key(self, src):
        out, rd, det = _run(_info(src))
        assert det["value_str"] == fmt_value(-0.5, SPECS_BY_KEY[_KEY])
        assert "is_proxy" not in rd[_KEY]
        assert _NOTE not in out["long"]["headline"]
        assert _tile(rd[_KEY]).card.value == fmt_value(-0.5, SPECS_BY_KEY[_KEY])

    def test_missing_value_gets_no_note(self):
        # 代理源但 gap 缺 → 不得出現「—（大盤動能代理估算）」
        info = _info(MP.M1B_PROXY_SOURCE_LABEL)
        info["gap"] = None
        _out, rd, det = _run(info)
        assert _NOTE not in det["value_str"]
        assert rd[_KEY]["state"] == "missing"
        assert "is_proxy" not in rd[_KEY]

    def test_other_lamp_ignores_is_proxy(self):
        # 側車 is_proxy 只對 m1b 那盞有意義
        rec = {"state": "ok", "value": 20.0, "is_proxy": True}
        t = P.build_indicator_tile("vix", rec, requested=True, error="",
                                   band_label=_band_label, thr_text=None)
        assert _NOTE not in t.card.value
