"""批 Z55：「📖 憑什麼」六因子卡接線（L0 配分 SSOT）＋ 兩張卡過期理由更正 ＋ 三句冒稱線框的 fact 刪除。

  ① 六因子配分：L0 `shared/health_score_factors.py` 成為唯一來源；L2 `calc_health_score` 改讀它
     （新舊 UI 共用 ⇒ **零行為變更**：golden test 拿「改讀前」的函式原文逐字凍結在本檔當第二把尺，
     數千組輸入逐值比對）；憑什麼頁的卡讀同一份。
  ② 兩張未接線卡（持股頁葡萄串、查一檔頁明細）的「為什麼」：
     「在本頁再掛一次會撞 DuplicateWidgetID」自側欄 radio ＋ `st.stop()` 起不成立（同 FE-36）。
  ③ 憑什麼頁三張未接線面板的 fact「線框對這一格的期待」：查無出處 ⇒ 整列刪除。

revert-pair 突變（把修正拔掉 ⇒ 守衛必須轉紅）；測試內不呼叫 git。
"""
from __future__ import annotations

import ast
import math
import pathlib
import random
import re
import sys
import textwrap

import numpy as np
import pandas as pd
import pytest

from shared import health_score_factors as HSF
from shared.signal_thresholds import BB_BW_SHRINK_WARN_RATIO
from shared.ui_state import UI_FAILED, UI_LIVE, UI_UNWIRED
from src.compute.scoring import scoring_helpers as SH
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_hold as H
from src.ui.views import page_inspect as I
from src.ui.views import page_why as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SH_SRC = (_ROOT / "src" / "compute" / "scoring" / "scoring_helpers.py").read_text(encoding="utf-8")
_WF_V1 = (_ROOT / "docs" / "wireframes" / "stock_ia_v1.html").read_text(encoding="utf-8")
_WF_V2 = (_ROOT / "docs" / "v2" / "wireframe" / "wf_page_why.js").read_text(encoding="utf-8")

#: 配分的**手寫第二來源**（建表當下自 L2 程式實際值核對；⛔ 不得改成從 HSF 讀出來自己比自己）。
_EXPECTED_FACTORS = (("趨勢", 30), ("RSI", 20), ("量比", 15), ("IBS", 10), ("KD", 15), ("布林", 10))


# ══════════════════════════════════════════════════════════════════
# 凍結的參考實作：批 Z55 改讀 SSOT **之前**的 `calc_health_score` 原文（逐字，只改函式名）。
# ⛔ 不得「順手同步」成新版 —— 它存在的意義就是當第二把尺。
# ══════════════════════════════════════════════════════════════════
def _reference_calc_health_score(df, rsi, ibs, vr, k_val, d_val, bb):
    """
    綜合健康度評分，各因子分述：
    - 趨勢（MA20/MA100）    : 30分
    - RSI動能              : 20分
    - 量比                 : 15分
    - IBS位置              : 10分
    - KD排列               : 15分
    - 布林位置              : 10分
    """
    score = 0
    details = {}

    if df is not None and not df.empty:
        price  = float(df['close'].iloc[-1])
        ma20   = float(df['MA20'].iloc[-1])  if 'MA20'  in df.columns else None
        ma100  = float(df['MA100'].iloc[-1]) if 'MA100' in df.columns else None

        # 趨勢 (30分)
        if ma20 and ma100:
            if price > ma20 > ma100:
                score += 30
                details['趨勢'] = ('多頭排列', 30, 30)
            elif price > ma100 and price > ma20:
                # P6修正: 需同時站上ma20和ma100才算「多箱整理」
                score += 18
                details['趨勢'] = ('多箱整理(站上雙均)', 18, 30)
            elif price > ma20 and price < ma100:
                # 站上短均但低於長均 → 反彈初期，偏謹慎
                score += 10
                details['趨勢'] = ('短線反彈(低於長均)', 10, 30)
            elif price < ma20 and price > ma100:
                # 短均跌破但長均支撐 → 整理中
                score += 8
                details['趨勢'] = ('整理中(長均支撐)', 8, 30)
            else:
                score += 0
                details['趨勢'] = ('空頭排列', 0,  30)
        else:
            score += 15
            details['趨勢'] = ('無MA數據', 15, 30)

    # RSI (20分) — C-1 v18.382:50/40 inline 補抽(70/30 已在 config.py SSOT)
    if rsi is not None:
        from shared.signal_thresholds import RSI_STRONG_LOW, RSI_NEUTRAL_WEAK_LOW
        from src.config import RSI_OVERBOUGHT, RSI_OVERSOLD
        if RSI_STRONG_LOW <= rsi <= RSI_OVERBOUGHT:
            score += 20
            details['RSI'] = (f'{rsi}（強勢區間）', 20, 20)
        elif RSI_NEUTRAL_WEAK_LOW <= rsi < RSI_STRONG_LOW:
            score += 12
            details['RSI'] = (f'{rsi}（中性偏弱）', 12, 20)
        elif RSI_OVERSOLD <= rsi < RSI_NEUTRAL_WEAK_LOW:
            score += 8
            details['RSI'] = (f'{rsi}（超賣邊緣）', 8,  20)
        elif rsi < RSI_OVERSOLD:
            score += 14
            details['RSI'] = (f'{rsi}（超賣反彈機會）', 14, 20)
        else:  # >70
            score += 8
            details['RSI'] = (f'{rsi}（超買注意）', 8,  20)

    # 量比 (15分)
    if vr is not None:
        # P2-3 v18.381:3.0 inline → shared SSOT
        # v18.436 #8:1.5/1.0/0.5 改用既有 VOLUME_RATIO_SURGE/MILD/DRY SSOT(原 inline 重複定義)
        from shared.signal_thresholds import (
            VOLUME_RATIO_SURGE_HIGH, VOLUME_RATIO_SURGE,
            VOLUME_RATIO_MILD, VOLUME_RATIO_DRY,
        )
        if vr > VOLUME_RATIO_SURGE_HIGH:
            # P7修正: 量比>3.0是重大消息/主力介入，給高分
            score += 12
            details['量比'] = (f'{vr}（主力介入）', 12, 15)
        elif VOLUME_RATIO_SURGE <= vr <= VOLUME_RATIO_SURGE_HIGH:
            score += 15
            details['量比'] = (f'{vr}（異常放量）', 15, 15)
        elif VOLUME_RATIO_MILD <= vr < VOLUME_RATIO_SURGE:
            score += 10
            details['量比'] = (f'{vr}（溫和放量）', 10, 15)
        elif VOLUME_RATIO_DRY <= vr < VOLUME_RATIO_MILD:
            score += 5
            details['量比'] = (f'{vr}（量縮整理）', 5,  15)
        else:
            score += 2
            details['量比'] = (f'{vr}（極度縮量）', 2,  15)

    # IBS (10分) — v18.436 #9:0.2/0.8 inline → SSOT
    if ibs is not None:
        from shared.signal_thresholds import IBS_OVERSOLD_THRESHOLD, IBS_OVERBOUGHT_THRESHOLD
        if ibs <= IBS_OVERSOLD_THRESHOLD:
            score += 10
            details['IBS'] = (f'{ibs}（收低≤20%，隔日易反彈）', 10, 10)
        elif ibs >= IBS_OVERBOUGHT_THRESHOLD:
            score += 2
            details['IBS'] = (f'{ibs}（收高≥80%，隔日易賣壓）', 2,  10)
        else:
            score += 6
            details['IBS'] = (f'{ibs}（中性）', 6, 10)

    # KD (15分) — v18.436 #7:20/80 inline → SSOT;v19.94 加鈍化/背離修正(§7 user 核准)
    if k_val is not None and d_val is not None:
        from shared.signal_thresholds import KD_OVERBOUGHT_LEVEL, KD_OVERSOLD_LEVEL
        from src.compute.strategy.tech_indicators import analyze_kd_state
        _kd = analyze_kd_state(df) or {}          # 同層 L2;None → {} 退回原分級
        _hp = bool(_kd.get('high_passivation'))
        _bear = bool(_kd.get('bearish_divergence'))
        _bull = bool(_kd.get('bullish_divergence'))
        if k_val > d_val and k_val < KD_OVERBOUGHT_LEVEL:
            score += 15
            details['KD'] = (f'K={k_val} D={d_val}（黃金交叉）', 15, 15)
        elif k_val > d_val and k_val >= KD_OVERBOUGHT_LEVEL:
            # v19.94 高檔黃叉分流:頂背離=真警訊(降5);高檔鈍化=強勢續漲不誤扣(15);否則注意(8)
            if _bear:
                score += 5
                details['KD'] = (f'K={k_val} D={d_val}（高檔黃叉但頂背離⚠️）', 5, 15)
            elif _hp:
                score += 15
                details['KD'] = (f'K={k_val} D={d_val}（高檔鈍化·強勢續漲）', 15, 15)
            else:
                score += 8
                details['KD'] = (f'K={k_val} D={d_val}（高檔黃叉注意）', 8, 15)
        elif k_val < d_val and k_val > KD_OVERSOLD_LEVEL:
            score += 5
            details['KD'] = (f'K={k_val} D={d_val}（死亡交叉）', 5, 15)
        else:
            # v19.94 低檔死叉:底背離=反轉向上訊號(加分13);否則低檔可守(10)
            if _bull:
                score += 13
                details['KD'] = (f'K={k_val} D={d_val}（低檔死叉但底背離↗）', 13, 15)
            else:
                score += 10
                details['KD'] = (f'K={k_val} D={d_val}（低檔死叉可守）', 10, 15)

    # 布林 (10分)
    if bb is not None:
        if bb['near_upper']:
            score += 8
            details['布林'] = ('黏近上軌（強勢）', 8, 10)
        elif bb['price'] > bb['ma']:
            score += 6
            details['布林'] = ('站上中軌', 6, 10)
        elif bb['bw'] < bb['bw_mean'] * BB_BW_SHRINK_WARN_RATIO:
            # v18.430 Batch 5b 漏網收尾:0.7 改 SSOT(BB_BW_SHRINK_WARN_RATIO=0.7)
            # 註:scoring fn 用 WARN 級門檻(同 section_health_score / section_vcp_bollinger KPI),
            # 雖然 label 寫「極度收縮」與 ACTION 級訊號框同字串,但歷史上即用 0.7 評 9 分(從寬給分)
            score += 9
            details['布林'] = ('帶寬極度收縮（即將爆發）', 9, 10)
        else:
            score += 3
            details['布林'] = ('低於中軌', 3, 10)

    return min(score, 100), details



# ══════════════════════════════════════════════════════════════════
# 輸入產生器（固定種子；含門檻邊界值、None、NaN、空 df、缺欄、可觸發 KD 鈍化／背離的長序列）
# ══════════════════════════════════════════════════════════════════
_N_CASES = 4000


def _make_df(rng: random.Random, n: int, *, drop: str = "") -> pd.DataFrame:
    _close, _p = [], 50 + rng.random() * 100
    _drift = rng.choice((-0.02, -0.005, 0.0, 0.005, 0.02))
    for _ in range(n):
        _p = max(1.0, _p * (1 + _drift + rng.gauss(0, 0.03)))
        _close.append(_p)
    _c = pd.Series(_close)
    _hi = _c * (1 + pd.Series([rng.random() * 0.03 for _ in range(n)]))
    _lo = _c * (1 - pd.Series([rng.random() * 0.03 for _ in range(n)]))
    _df = pd.DataFrame({"close": _c, "high": _hi, "low": _lo,
                        "MA20": _c.rolling(20, min_periods=1).mean(),
                        "MA100": _c.rolling(100, min_periods=1).mean()})
    _mode = rng.random()
    if _mode < 0.08 and n:
        _df.loc[_df.index[-1], "MA20"] = _df["close"].iloc[-1]      # 價 == MA20（邊界）
    elif _mode < 0.14 and n:
        _df.loc[_df.index[-1], "MA100"] = np.nan                    # NaN 均線
    elif _mode < 0.22 and n:
        _df.loc[_df.index[-1], "MA20"] = 0.0                        # 0 均線（falsy）
    if drop:
        _df = _df.drop(columns=[drop])
    return _df


def _pick(rng: random.Random, edges: tuple, lo: float, hi: float):
    _r = rng.random()
    if _r < 0.45:
        return rng.choice(edges)
    return round(lo + (hi - lo) * rng.random(), rng.choice((0, 1, 2, 4)))


def _inputs():
    rng = random.Random(20261013)
    _pool = [None, pd.DataFrame(), _make_df(rng, 1)]
    for _ in range(140):
        _pool.append(_make_df(rng, rng.choice((5, 12, 30, 48, 60, 90, 120, 160)),
                              drop=rng.choice(("", "", "", "", "MA20", "MA100"))))
    _rsi_edges = (None, None, float("nan"), 0, 29.9, 30, 39.9, 40, 49.9, 50, 70, 70.1, 100)
    _ibs_edges = (None, 0.0, 0.19, 0.2, 0.21, 0.5, 0.79, 0.8, 0.81, 1.0)
    _vr_edges = (None, 0, 0.49, 0.5, 0.99, 1.0, 1.49, 1.5, 2.9, 3.0, 3.01, 12.0)
    _kd_edges = (None, 0, 19.9, 20, 20.1, 50, 79.9, 80, 80.1, 100)
    for _ in range(_N_CASES):
        _df = rng.choice(_pool)
        _bb = None
        if rng.random() < 0.85:
            _ma = 50 + rng.random() * 50
            _mean = 0.5 + rng.random()
            _bb = {"near_upper": rng.random() < 0.3,
                   "price": rng.choice((_ma, _ma * (1 + rng.uniform(-0.1, 0.1)))),
                   "ma": _ma,
                   "bw": rng.choice((_mean * BB_BW_SHRINK_WARN_RATIO, _mean * rng.uniform(0.2, 1.5))),
                   "bw_mean": _mean}
        _k = _pick(rng, _kd_edges, 0, 100)
        _d = _pick(rng, _kd_edges, 0, 100) if rng.random() < 0.9 else _k
        yield (_df, _pick(rng, _rsi_edges, 0, 100), _pick(rng, _ibs_edges, 0, 1),
               _pick(rng, _vr_edges, 0, 6), _k, _d, _bb)


_CASES = list(_inputs())
_RESULTS = [(SH.calc_health_score(*_a), _reference_calc_health_score(*_a)) for _a in _CASES]

#: 每個因子的分支（以 details 標籤裡的說明文字辨識），golden 必須全部走過 —— 否則「逐值相同」可能只是沒測到。
_BRANCHES = {
    "趨勢": ("多頭排列", "多箱整理", "短線反彈", "整理中", "空頭排列", "無MA數據"),
    "RSI": ("強勢區間", "中性偏弱", "超賣邊緣", "超賣反彈機會", "超買注意"),
    "量比": ("主力介入", "異常放量", "溫和放量", "量縮整理", "極度縮量"),
    "IBS": ("收低≤20%", "收高≥80%", "中性"),
    "KD": ("黃金交叉", "高檔黃叉但頂背離", "高檔鈍化", "高檔黃叉注意", "死亡交叉",
           "低檔死叉但底背離", "低檔死叉可守"),
    "布林": ("黏近上軌", "站上中軌", "帶寬極度收縮", "低於中軌"),
}


# ══════════════════════════════════════════════════════════════════
# ① golden：改讀 SSOT 前後逐值相同
# ══════════════════════════════════════════════════════════════════
class TestGoldenZeroBehaviourChange:

    def test_enough_cases(self):
        assert len(_CASES) >= 3000

    def test_every_case_matches_the_frozen_reference(self):
        bad = [i for i, (_new, _old) in enumerate(_RESULTS) if _new != _old]
        assert not bad, f"{len(bad)} 組輸入結果與改讀前不同，例：{_RESULTS[bad[0]]}"

    def test_score_type_is_unchanged_too(self):
        for (_ns, _nd), (_os, _od) in _RESULTS:
            assert type(_ns) is type(_os)
            for _k in _nd:
                assert tuple(type(_x) for _x in _nd[_k]) == tuple(type(_x) for _x in _od[_k])

    def test_golden_walks_every_branch_of_every_factor(self):
        seen = {f: set() for f in _BRANCHES}
        for (_s, _d), _ in _RESULTS:
            for _f, (_label, _pts, _max) in _d.items():
                for _b in _BRANCHES[_f]:
                    if _b in str(_label):
                        seen[_f].add(_b)
        for _f, _bs in _BRANCHES.items():
            assert seen[_f] == set(_bs), f"{_f} 沒走到：{set(_bs) - seen[_f]}"

    def test_scores_stay_within_the_scale(self):
        for (_s, _d), _ in _RESULTS:
            assert 0 <= _s <= HSF.HEALTH_SCORE_TOTAL

    def test_details_max_column_equals_the_ssot(self):
        for (_s, _d), _ in _RESULTS:
            for _f, (_label, _pts, _max) in _d.items():
                assert _max == HSF.HEALTH_SCORE_FACTOR_POINTS[_f]
                assert 0 <= _pts <= _max

    def test_mutating_a_weight_turns_the_golden_red(self, monkeypatch):
        """revert-pair：L2 真的讀 SSOT（改 SSOT 一個配分 ⇒ 與凍結參考不再逐值相同）。"""
        _mut = dict(HSF.HEALTH_SCORE_FACTOR_POINTS)
        _mut["布林"] = 11
        monkeypatch.setattr(SH, "HEALTH_SCORE_FACTOR_POINTS", _mut)
        bad = sum(1 for _a in _CASES[:300]
                  if SH.calc_health_score(*_a) != _reference_calc_health_score(*_a))
        assert bad > 0, "改了配分 golden 卻沒紅 —— 守衛空轉"


# ══════════════════════════════════════════════════════════════════
# SSOT：L0 一份、L2 不再寫死、註解不再抄
# ══════════════════════════════════════════════════════════════════
def _calc_fn() -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(_SH_SRC))
                if isinstance(n, ast.FunctionDef) and n.name == "calc_health_score")


def _detail_tuples(fn: ast.FunctionDef) -> list[ast.Tuple]:
    out = []
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Subscript)
                and getattr(n.targets[0].value, "id", "") == "details"
                and isinstance(n.value, ast.Tuple)):
            out.append(n.value)
    return out


def _calc_fn_of(src: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef) and n.name == "calc_health_score")


def _assert_weights_read_l0(src: str) -> None:
    """`_W_*` 一律是 `HEALTH_SCORE_FACTOR_POINTS['<因子名>']`（M03）。"""
    bound = {}
    for n in ast.walk(_calc_fn_of(src)):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id.startswith("_W_")):
            v = n.value
            assert (isinstance(v, ast.Subscript) and getattr(v.value, "id", "") == "HEALTH_SCORE_FACTOR_POINTS"
                    and isinstance(v.slice, ast.Constant)), (
                f"{n.targets[0].id} 不是讀 L0 SSOT：{ast.unparse(v)}")
            bound[n.targets[0].id] = v.slice.value
    assert sorted(bound.values()) == sorted(n for n, _p in HSF.HEALTH_SCORE_FACTORS), bound


def _assert_full_marks_use_weights(src: str) -> int:
    """`score += X` 緊接 `details[F] = (label, Y, Z)` 的配對（M05）。

    「滿分給分」＝給的分等於該因子配分（Y 就是 Z）。內部分段（18／12／8…）不是配分，不在守備範圍；
    但字面值**等於**該因子配分的一律視為「把滿分寫死」⇒ 紅。回傳滿分給分處數。
    """
    n_full = 0
    for node in ast.walk(_calc_fn_of(src)):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for a, b in zip(body, body[1:]):
            if not (isinstance(a, ast.AugAssign) and getattr(a.target, "id", "") == "score"
                    and isinstance(b, ast.Assign) and isinstance(b.value, ast.Tuple)
                    and isinstance(b.targets[0], ast.Subscript)):
                continue
            factor = b.targets[0].slice.value
            pts = HSF.HEALTH_SCORE_FACTOR_POINTS[factor]
            x, y, z = a.value, b.value.elts[1], b.value.elts[2]
            assert ast.dump(x) == ast.dump(y), f"第 {a.lineno} 行：加的分與 details 記的分不一致"
            for lit in (x, y):
                assert not (isinstance(lit, ast.Constant) and lit.value == pts), (
                    f"第 {a.lineno} 行：{factor} 的滿分給分寫死成 {lit.value}，應讀 L0 配分")
            if isinstance(x, ast.Name):
                assert isinstance(z, ast.Name) and x.id == z.id, f"第 {a.lineno} 行：滿分給分不是本因子配分"
                n_full += 1
    return n_full


def _assert_l0_enforces_total(src: str) -> None:
    assert re.search(r"^if HEALTH_SCORE_TOTAL != 100:\s*\n\s*raise RuntimeError", src, re.M), (
        "L0 少了「六因子配分合計＝100」的載入期檢查")


class TestSingleSource:

    def test_l0_table_values_and_total(self):
        assert HSF.HEALTH_SCORE_FACTORS == _EXPECTED_FACTORS
        assert HSF.HEALTH_SCORE_TOTAL == 100 == sum(p for _n, p in _EXPECTED_FACTORS)
        assert dict(HSF.HEALTH_SCORE_FACTOR_POINTS) == dict(_EXPECTED_FACTORS)

    def test_l0_factor_names_are_the_l2_detail_keys(self):
        _df = _make_df(random.Random(1), 60)
        _s, _d = SH.calc_health_score(_df, 55, 0.5, 1.2, 50, 40,
                                      {"near_upper": True, "price": 1, "ma": 1, "bw": 1, "bw_mean": 1})
        assert tuple(_d) == tuple(n for n, _p in HSF.HEALTH_SCORE_FACTORS)

    def test_l2_has_no_literal_max_column(self):
        tuples = _detail_tuples(_calc_fn())
        assert len(tuples) == 30, len(tuples)
        for t in tuples:
            assert isinstance(t.elts[2], ast.Name), (
                f"calc_health_score 第 {t.lineno} 行的配分欄寫死了常數 —— 配分只准讀 L0 SSOT")
            if isinstance(t.elts[1], ast.Name):
                assert t.elts[1].id == t.elts[2].id, "滿分給分必須就是該因子的配分"

    def test_l2_reads_the_points_from_the_l0_module(self):
        assert "from shared.health_score_factors import" in _SH_SRC
        fn = _calc_fn()
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "min":
                assert not isinstance(n.args[1], ast.Constant), "分數上限寫死了"
        # 滿分給分（`score += <配分>`）一律是名字，⛔ 不得有字面 30／20／15（10 有分段給分同值，另由上一條守）。
        for n in ast.walk(fn):
            if (isinstance(n, ast.AugAssign) and getattr(n.target, "id", "") == "score"
                    and isinstance(n.value, ast.Constant)):
                assert n.value.value not in (30, 20), f"第 {n.lineno} 行：滿分給分寫死"

    def test_weight_names_are_bound_to_the_l0_table(self):
        _assert_weights_read_l0(_SH_SRC)

    def test_m03_a_literal_weight_turns_red(self):
        """M03：任一 `_W_*` 改寫成字面數字（不讀 L0）⇒ 守衛轉紅。"""
        _mut = _SH_SRC.replace("_W_RSI = HEALTH_SCORE_FACTOR_POINTS['RSI']", "_W_RSI = 20")
        assert _mut != _SH_SRC
        with pytest.raises(AssertionError):
            _assert_weights_read_l0(_mut)

    def test_full_mark_awards_use_the_weight_name(self):
        assert _assert_full_marks_use_weights(_SH_SRC) == 6, "滿分給分應有 6 處（趨勢/RSI/量比/IBS/KD×2）"

    def test_m05_a_literal_full_mark_turns_red(self):
        """M05：KD 黃金交叉的滿分給分改寫成字面 15（＝KD 配分）⇒ 守衛轉紅。"""
        _old = ("            score += _W_KD\n"
                "            details['KD'] = (f'K={k_val} D={d_val}（黃金交叉）', _W_KD, _W_KD)")
        assert _old in _SH_SRC
        for _new in (_old.replace("score += _W_KD", "score += 15"),
                     _old.replace("score += _W_KD", "score += 15").replace("', _W_KD, _W_KD)", "', 15, _W_KD)")):
            with pytest.raises(AssertionError):
                _assert_full_marks_use_weights(_SH_SRC.replace(_old, _new))

    def test_l0_rejects_a_total_that_is_not_100(self):
        _l0 = (_ROOT / "shared" / "health_score_factors.py").read_text(encoding="utf-8")
        _bad = _l0.replace('("布林", 10)', '("布林", 11)')
        assert _bad != _l0
        with pytest.raises(RuntimeError):
            exec(compile(_bad, "health_score_factors_mut", "exec"), {"__name__": "_mut"})
        _dup = _l0.replace('("布林", 10)', '("KD", 10)')
        with pytest.raises(RuntimeError):
            exec(compile(_dup, "health_score_factors_dup", "exec"), {"__name__": "_mut"})

    def test_m24_removing_the_total_check_turns_red(self):
        """M24：拿掉 L0「合計＝100」檢查 ⇒ 上一條的反證（配分合計 101 仍載入成功）。"""
        _l0 = (_ROOT / "shared" / "health_score_factors.py").read_text(encoding="utf-8")
        _no_check = _l0.replace("if HEALTH_SCORE_TOTAL != 100:", "if False:")
        assert _no_check != _l0
        _bad = _no_check.replace('("布林", 10)', '("布林", 11)')
        exec(compile(_bad, "health_score_factors_m24", "exec"), {"__name__": "_mut"})   # 不再 raise
        with pytest.raises(AssertionError):
            _assert_l0_enforces_total(_no_check)
        _assert_l0_enforces_total(_l0)

    def test_no_text_copy_of_the_weights_left_in_code(self):
        pat = re.compile(r"趨勢\s*30\s*\+\s*RSI\s*20|趨勢（MA20/MA100）\s*:\s*30分")
        hits = []
        for base in ("src", "shared"):
            for f in (_ROOT / base).rglob("*.py"):
                if pat.search(f.read_text(encoding="utf-8")):
                    hits.append(str(f.relative_to(_ROOT)))
        hits += ["app.py"] if pat.search((_ROOT / "app.py").read_text(encoding="utf-8")) else []
        assert not hits, f"配分的文字抄本還在：{hits}"

    def test_position_throttle_comment_points_to_the_ssot(self):
        src = (_ROOT / "shared" / "position_throttle.py").read_text(encoding="utf-8")
        assert src.count("shared/health_score_factors.py") >= 2
        assert "趨勢30" not in src


# ══════════════════════════════════════════════════════════════════
# 憑什麼頁「健康評分六因子」卡
# ══════════════════════════════════════════════════════════════════
def _assert_health6_wired(built) -> None:
    card, facts, _sig = built
    assert card.state == UI_LIVE, f"六因子卡不是 live：{card.state}"
    assert card.value == f"合計 {HSF.HEALTH_SCORE_TOTAL}"
    rows = dict(facts)
    for name, pts in HSF.HEALTH_SCORE_FACTORS:
        assert rows.get(name) == f"{pts} 分", (name, rows.get(name))


class TestHealth6Card:

    def test_cold_card_is_live_with_ssot_values(self):
        _assert_health6_wired(P.build_health6_card())

    def test_the_edu_leaf_draws_the_wired_card(self):
        builts = P.build_edu_cards(P.load_specs(), P.build_scale_disclosure())
        _assert_health6_wired(next(b for b in builts if b[0].key == "why.edu.health6"))

    def test_card_reads_the_table_not_a_copy(self, monkeypatch):
        import shared.health_score_factors as _m
        monkeypatch.setattr(_m, "HEALTH_SCORE_FACTORS", (("甲", 60), ("乙", 40)))
        monkeypatch.setattr(_m, "HEALTH_SCORE_TOTAL", 100)
        card, facts, _ = P.build_health6_card()
        assert dict(facts).get("甲") == "60 分" and "趨勢" not in dict(facts)

    def test_facts_order_and_source_row(self):
        _c, facts, _ = P.build_health6_card()
        names = [k for k, _v in facts if k in HSF.HEALTH_SCORE_FACTOR_POINTS]
        assert names == [n for n, _p in HSF.HEALTH_SCORE_FACTORS]
        assert facts[0] == (P.PANEL_SOURCE_FACT_KEY, P.SRC_HEALTH6)

    def test_unwired_wording_is_gone(self):
        card, facts, _ = P.build_health6_card()
        assert card.note is None
        text = " ".join(v for _k, v in facts)
        assert "本頁還說不出來" not in text and "配分沒有 SSOT" not in text
        assert not hasattr(P, "HEALTH6_NOW") and not hasattr(P, "HEALTH6_WHY")

    def test_read_failure_is_red_with_the_right_source(self):
        card, _f, _ = P.build_health6_card(P.Health6Readout(error="ImportError('x')"))
        assert card.state == UI_FAILED
        assert card.note.now == P.HEALTH6_FAILED_NOW == "**健康評分六因子讀不出來**"
        assert card.note.why.startswith(P.SRC_HEALTH6)
        assert "規格表" not in card.note.why + card.note.where
        assert NO_EXIT_MARKER in card.note.where and "回報給維護者" in card.note.where
        face, fold = P.v2_short_rows(card)
        assert face and fold   # 短句表有這一列（查不到會 KeyError）

    def test_import_failure_becomes_red_not_blank(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "shared.health_score_factors", None)
        readout = P.load_health6()
        assert readout.error and not readout.factors
        assert P.build_health6_card(readout)[0].state == UI_FAILED

    def test_empty_table_without_error_is_red_not_grey(self):
        assert P.build_health6_card(P.Health6Readout())[0].state == UI_FAILED

    def test_live_card_renders_on_the_v2_face(self):
        out = P.v2_card_html(*P.build_health6_card())
        for name, pts in HSF.HEALTH_SCORE_FACTORS:
            assert name in out and f"{pts} 分" in out
        assert "合計 100" in out

    def test_reverting_to_unwired_turns_the_guard_red(self):
        """revert-pair：把卡退回未接線（批 Z55 前的形狀）⇒ 守衛必須轉紅。"""
        _old = P.build_l0_card(P.L0CardSpec(
            key="why.edu.health6", label="健康評分六因子", wired=False,
            now="**六個因子各佔幾分，本頁還說不出來**", why="x", where="y"))
        assert _old[0].state == UI_UNWIRED
        with pytest.raises(AssertionError):
            _assert_health6_wired(_old)


# ══════════════════════════════════════════════════════════════════
# ② 兩張卡的過期理由
# ══════════════════════════════════════════════════════════════════
def _grape_why() -> str:
    return next(s for s in H.DEEP_SPECS if s.key == "hold.deep.grape").why


def _detail_builts():
    return [I.build_detail_card(True, key=k, label=l, sections=("a",), entry=e)
            for k, l, e in (("inspect.stock.detail", "個股明細", "x"),
                            ("inspect.etf.detail", "ETF 明細", "y"))]


def _assert_grape_keeps_the_session_reason(text: str) -> None:
    for ph in ("撞不起來", "etf_portfolio_rows", "普通旗標", "不是 widget key",
               "跨 rerun、跨頁存活", "讀到的就是既有分頁寫進去的那一份"):
        assert ph in text, f"葡萄串卡「為什麼」少了「{ph}」"


def _assert_no_stale_collision_claim(text: str) -> None:
    assert "DuplicateWidgetID" not in text, text
    assert "整頁當場拋例外" not in text and "再掛一次會撞" not in text, text


class TestStaleCollisionReasons:

    def test_grape_why_is_corrected(self):
        _assert_no_stale_collision_claim(_grape_why())
        _assert_grape_keeps_the_session_reason(_grape_why())

    def test_deleting_the_grape_session_reason_turns_red(self):
        """M26：把「普通旗標跨頁存活」那半句理由刪掉 ⇒ 守衛轉紅（理由不得只剩結論）。"""
        _w = _grape_why()
        _cut = _w[:_w.index("；但它讀的")]
        with pytest.raises(AssertionError):
            _assert_grape_keeps_the_session_reason(_cut)
        with pytest.raises(AssertionError):
            _assert_grape_keeps_the_session_reason(_w.replace("**普通旗標**", ""))

    def test_detail_why_is_corrected(self):
        _assert_no_stale_collision_claim(I.DETAIL_WHY)
        for ph in ("撞不起來", "跨 rerun、跨頁存活", "同名 key 照樣互相污染",
                   "而把取數抄一份到本頁則會變成第二個真相源"):
            assert ph in I.DETAIL_WHY

    def test_cards_render_without_the_stale_claim(self):
        for c, f, s in _detail_builts():
            _assert_no_stale_collision_claim(c.note.why)
            face, _fold = I.v2_short_rows(c)
            _assert_no_stale_collision_claim(" ".join(v for _k, v in face))

    def test_entry_facts_in_the_render_path_drop_the_claim(self):
        tree = ast.parse((_ROOT / "src" / "ui" / "views" / "page_inspect.py").read_text(encoding="utf-8"))
        entries = [k.value.value for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "build_detail_card"
                   for k in n.keywords if k.arg == "entry" and isinstance(k.value, ast.Constant)]
        assert sorted(entries) == ["🏦 ETF 分頁（本頁不重複掛載）", "🔬 個股分頁（本頁不重複掛載）"]

    def test_cards_stay_unwired(self):
        st_ = H.StationReadout(requested=False)
        by = {c.key: c for c, _f, _s in H.build_deep_cards(st_, H.load_deep(st_))}
        assert by["hold.deep.grape"].state == UI_UNWIRED
        for c, _f, _s in _detail_builts():
            assert c.state == UI_UNWIRED

    def test_the_premise_holds_new_pages_stop_before_the_old_tabs(self):
        """查證「撞不起來」的前提：app.py 選到新頁那一輪先 `st.stop()`，舊頁籤的 `st.tabs` 在其後。"""
        tree = ast.parse((_ROOT / "app.py").read_text(encoding="utf-8"))
        stops = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", "") == "stop" and getattr(n.func.value, "id", "") == "st"]
        top_tabs = [n.value.lineno for n in tree.body if isinstance(n, ast.Assign)
                    and isinstance(n.value, ast.Call) and getattr(n.value.func, "attr", "") == "tabs"]
        assert stops and top_tabs and min(stops) < min(top_tabs)

    def test_reverting_the_text_turns_the_guard_red(self):
        old = ("這一格的實作**住在 L5**（`tabs.grape_ladder`）而不是 L3，"
               "而且它自帶寫死的 widget key —— 在本頁再掛一次會撞 "
               "`DuplicateWidgetID`，那不是「畫得醜」，是**整頁當場拋例外**")
        with pytest.raises(AssertionError):
            _assert_no_stale_collision_claim(old)


# ══════════════════════════════════════════════════════════════════
# ③ 三句冒稱線框的 fact
# ══════════════════════════════════════════════════════════════════
_UNSOURCED = ("同一個指標兩種算法並排，差額超過容差就標紅",
              "金鑰來源 · proxy 設定 · 各 endpoint 雙跑比對",
              "各來源原始 DataFrame 就地展開")
_WF_LABEL = "線框對這一格的期待"


def _assert_no_unsourced_wireframe_claim(builts) -> None:
    for c, facts, _s in builts:
        for k, v in facts:
            assert not (k == _WF_LABEL and v in _UNSOURCED), (c.key, v)


class TestNoFakeWireframeClaims:

    def test_the_three_sentences_have_no_source(self):
        """前提查證：三句在兩份線框裡都找不到（找得到就不該刪）。"""
        for s in _UNSOURCED:
            assert s not in _WF_V1
            assert s not in _WF_V2 or "批 Z55" in _WF_V2

    def test_panels_no_longer_claim_a_wireframe_expectation(self):
        _assert_no_unsourced_wireframe_claim(P.build_engineer_panel_cards())
        for spec in P.ENGINEER_PANEL_SPECS:
            assert _WF_LABEL not in dict(spec.facts)
            assert spec.facts, "其餘 fact（卡住的那一步）要留著"
            assert dict(spec.facts)["卡住的那一步"]

    def test_sourced_claim_is_kept(self):
        """有出處的那一句（FinMind 額度「🟢 額度剩 62%」，v1 線框原文）不動。"""
        assert "🟢 額度剩 62%" in _WF_V1
        facts = {k: v for c, f, _s in P.build_unmeasured_cards() for k, v in f}
        assert facts.get(_WF_LABEL) == "🟢 額度剩 62%"

    def test_reverting_the_facts_turns_the_guard_red(self):
        old = P.build_l0_card(P.L0CardSpec(
            key="why.engineer.reconcile", label="雙演算法對帳（§4.3）", wired=False,
            now=P.ENGINEER_RAW_NOW, why="x", where="y",   # 批 Z56：原 `ENGINEER_RECONCILE_NOW` 隨該卡接線刪除，改借同表另一則 now（本測試不看 now）
            facts=((_WF_LABEL, _UNSOURCED[0]),)))
        with pytest.raises(AssertionError):
            _assert_no_unsourced_wireframe_claim((old,))


# ══════════════════════════════════════════════════════════════════
# 冷啟動實跑（AppTest）
# ══════════════════════════════════════════════════════════════════
def test_cold_why_page_shows_the_wired_health6_card(tmp_path):
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_z55_why_cold.py"
    script.write_text("from src.ui.views import page_why as P\nP.render_page_why()\n",
                      encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "健康評分六因子" in md and "合計 100" in md
    for name, pts in HSF.HEALTH_SCORE_FACTORS:
        assert f"{pts} 分" in md
    assert "六個因子各佔幾分，本頁還說不出來" not in md
    assert "這一格畫不出來" not in md and "讀不出來" not in md
