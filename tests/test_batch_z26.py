"""批 Z26：Z25 實作組發現 (d)，及本批實作組發現 (b)（同檔、同性質，總管指示一併納入）。

L5 `src/ui/tabs/macro/section_warroom.py` 作戰室「今日操作前 5 分鐘清單」：
- 「融資餘額」未取得（`cl_data['margin']` 缺鍵／None／0 —— 同格文字已印「未取得 (N/A)」的同一判式）
- 「年線位置」未知（`bias_info` 為空，或 `bias_240` 缺鍵／None／NaN／±inf／bool —— 同格文字已印「未知」）
修前兩格的 `_ok` 皆給 True ⇒ 綠框 ✅（把「沒資料」畫成「安全」，違 §1／§1.A 第 4 點）。
修法比照 Z16-n1（批 Z25）：缺值時 `_ok` 給 None ⇒ 走同檔既有「無資料」灰 #484f58 ＋ ⬜；
文字（「未取得 (N/A)」「未知」）不變；有值時整段輸出逐字不變（golden 於修前基底 `34904717` 實跑寫死）。

觸發路徑（實查）：融資 —— L3 `macro_fetch_orchestrator._job_margin` 抓取例外回 None、
`fetch_margin_balance` 六段備援全敗回 None、冷啟動沿用 `prev_cl_data.get('margin')`（從未載入即 None）；
年線 —— `macro_trio_orchestrator` 的 bias job 失敗不寫 `bias_info`（session 為空 dict）、
`macro_snapshot` 的 `calc_bias_pct` 算不出時 `bias_240` 留 None。

(b)：同一清單「大盤燈號」未評估（regime 非 bull／bear／neutral）、「持股比例」未載入
（`get_allocation().is_loaded` 為 False）時，文字已是「⬜ 總經未評估」，框卻是紅 ⚠️
（把未評估畫成出錯／偏空）⇒ 同一作法改走灰框 ⬜；已評估時的判定與輸出逐字不變。

本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import hashlib
import math

import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_warroom as W
from shared.allocation_decision import Cap, build_allocation_decision
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.inst_net import InstNetDict
from tests.test_m2n2_no_zero_fill import _FakeST

_GRAY = '#484f58'
_FK = '外資及陸資'
_INST = InstNetDict({_FK: {'net': 12.0}, '投信': {'net': 1.0}, '自營商': {'net': -1.0}})
_BIAS = {'price': 20000.0, 'ma240': 19000.0, 'bias_240': 5.3}
_ABSENT = object()

#: 修前基底（`34904717`）實跑寫死：兩格缺值時的整格輸出（綠框 ✅）。
_PRE_MARGIN_CARD = (
    "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #22c55e;"
    "border-radius:8px;padding:8px 10px;margin:2px 0;min-height:108px;display:flex;"
    "flex-direction:column;justify-content:space-between;'><div><div style='font-size:11px;"
    "color:#8b949e;'>✅ 融資餘額</div><div style='font-size:15px;font-weight:800;color:#22c55e;"
    "margin:5px 0;line-height:1.25;'>未取得 (N/A)</div></div><div style='font-size:10px;color:#484f58;"
    "line-height:1.3;'>>2,500億警戒，>3,400億極危</div></div>")
_PRE_BIAS_CARD = (
    "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #22c55e;"
    "border-radius:8px;padding:8px 10px;margin:2px 0;min-height:108px;display:flex;"
    "flex-direction:column;justify-content:space-between;'><div><div style='font-size:11px;"
    "color:#8b949e;'>✅ 年線位置</div><div style='font-size:15px;font-weight:800;color:#22c55e;"
    "margin:5px 0;line-height:1.25;'>未知</div></div><div style='font-size:10px;color:#484f58;"
    "line-height:1.3;'>超過±20%要警惕</div></div>")

#: 修前基底（`34904717`）實跑寫死：未評估兩格的整格輸出（紅框 ⚠️）。
_PRE_REGIME_CARD = (
    "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;"
    "border-radius:8px;padding:8px 10px;margin:2px 0;min-height:108px;display:flex;"
    "flex-direction:column;justify-content:space-between;'><div><div style='font-size:11px;"
    "color:#8b949e;'>⚠️ 大盤燈號</div><div style='font-size:15px;font-weight:800;color:#ef4444;"
    "margin:5px 0;line-height:1.25;'>⬜ 總經未評估</div></div><div style='font-size:10px;color:#484f58;"
    "line-height:1.3;'>多頭才積極操作</div></div>")
_PRE_ALLOC_CARD = (
    "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;"
    "border-radius:8px;padding:8px 10px;margin:2px 0;min-height:108px;display:flex;"
    "flex-direction:column;justify-content:space-between;'><div><div style='font-size:11px;"
    "color:#8b949e;'>⚠️ 持股比例</div><div style='font-size:15px;font-weight:800;color:#ef4444;"
    "margin:5px 0;line-height:1.25;'>⬜ 總經未評估</div></div><div style='font-size:10px;color:#484f58;"
    "line-height:1.3;'>按建議比例，不要滿倉</div></div>")

#: 格名 → 修前（圖示, 顏色）。(d) 兩格修前綠 ✅；(b) 兩格修前紅 ⚠️。
_PRE = {'融資餘額': ('✅', TRAFFIC_GREEN), '年線位置': ('✅', TRAFFIC_GREEN),
        '大盤燈號': ('⚠️', TRAFFIC_RED), '持股比例': ('⚠️', TRAFFIC_RED)}

_UNLOADED = build_allocation_decision(None)
_LOADED = build_allocation_decision({'is_loaded': True, 'regime': 'bull', 'health': 70})
_CAPPED = build_allocation_decision({'is_loaded': True, 'regime': 'bull', 'health': 70},
                                    caps=[Cap('VIX 否決權', 10, 'z26')])


def undo_z26_gray_card(out):
    """把修後「融資餘額」「年線位置」「大盤燈號」「持股比例」灰框 ⬜ 換回修前寫法（各格 3 處；其他格不碰）。

    供既有作戰室整段 golden 測試（批 Z6／Z9 第 2 組／Z25）沿用修前 golden：那些測試守的不是這幾格，
    這幾格的修後行為由本檔 `TestMissingIsGray`／`TestUnevaluatedIsGray` 守。
    """
    def _one(t):
        for name, (ic, color) in _PRE.items():
            if f'⬜ {name}</div>' in t:
                return (t.replace(f'border-top:3px solid {_GRAY};', f'border-top:3px solid {color};')
                         .replace(f'font-weight:800;color:{_GRAY};', f'font-weight:800;color:{color};')
                         .replace(f'⬜ {name}</div>', f'{ic} {name}</div>'))
        return t
    return [(k, _one(t)) for k, t in out]


def _wr(mp, margin=2000.0, bias=_BIAS, reg='bull', alloc=_UNLOADED):
    mp.setattr(AS, 'get_allocation', lambda *a, **k: alloc)
    cd = {'inst': _INST}
    if margin is not _ABSENT:
        cd['margin'] = margin
    state = {'cl_data': cd, 'warroom_summary': {'futures_net': None}}
    if bias is not _ABSENT:
        state['bias_info'] = bias
    fake = _FakeST(state)
    mp.setattr(W, 'st', fake)
    W.render_section_warroom(reg, True, False)
    return list(fake.out)


def _card(out, name) -> str:
    cards = [t for _k, t in out if f'{name}</div>' in t]
    assert len(cards) == 1
    return cards[0]


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode()).hexdigest()


def _gray_count(out) -> int:
    return '\x1e'.join(t for _k, t in out).count(f'border-top:3px solid {_GRAY};')


def _assert_gray(card, name, text):
    assert f'border-top:3px solid {_GRAY};' in card
    assert f'font-weight:800;color:{_GRAY};' in card
    assert f'⬜ {name}</div>' in card
    assert f"line-height:1.25;'>{text}</div>" in card          # 文字不變
    assert TRAFFIC_GREEN not in card and TRAFFIC_RED not in card
    assert '✅' not in card and '⚠️' not in card


_MARGIN_MISSING = [
    pytest.param(None, id='none'),
    pytest.param(_ABSENT, id='no-key'),
    pytest.param(0, id='zero-int'),
    pytest.param(0.0, id='zero-float'),
]
_BIAS_MISSING = [
    pytest.param(_ABSENT, id='bias-info-never-written'),
    pytest.param({}, id='empty'),
    pytest.param({'price': 20000.0, 'ma240': 19000.0}, id='no-key'),
    pytest.param({'price': 20000.0, 'ma240': 19000.0, 'bias_240': None}, id='none'),
    pytest.param({'price': 20000.0, 'ma240': 19000.0, 'bias_240': math.nan}, id='nan'),
    pytest.param({'price': 20000.0, 'ma240': 19000.0, 'bias_240': math.inf}, id='inf'),
    pytest.param({'price': 20000.0, 'ma240': 19000.0, 'bias_240': True}, id='bool'),
]


class TestMissingIsGray:
    @pytest.mark.parametrize('margin', _MARGIN_MISSING)
    def test_margin_missing_gray(self, monkeypatch, margin):
        out = _wr(monkeypatch, margin=margin)
        _assert_gray(_card(out, '融資餘額'), '融資餘額', '未取得 (N/A)')
        assert f'border-top:3px solid {TRAFFIC_GREEN};' in _card(out, '年線位置')   # 另一格照舊

    @pytest.mark.parametrize('bias', _BIAS_MISSING)
    def test_bias_missing_gray(self, monkeypatch, bias):
        out = _wr(monkeypatch, bias=bias)
        _assert_gray(_card(out, '年線位置'), '年線位置', '未知')
        assert f'border-top:3px solid {TRAFFIC_GREEN};' in _card(out, '融資餘額')   # 另一格照舊

    def test_both_missing_only_two_cards_gray(self, monkeypatch):
        out = _wr(monkeypatch, margin=None, bias={}, alloc=_LOADED)
        joined = '\x1e'.join(t for _k, t in out)
        assert _gray_count(out) == 2
        assert joined.count('⬜ 融資餘額</div>') == 1 and joined.count('⬜ 年線位置</div>') == 1
        assert '✅ 外資方向</div>' in joined                                       # 外資有值格照舊


class TestUndoHelper:
    """還原替換恰好只改缺值／未評估的那幾格，且還原後整段輸出等於修前基底（`34904717`）實跑。

    （以下 n_cards 含「持股比例」：本組以未載入的 allocation 實跑。）
    """

    @pytest.mark.parametrize('margin, bias, n_cards, golden', [
        (None, _BIAS, 2, '05857576fc10cb51ec3cd77cc1a9863dc3186ddbdbe349369cf2db66e7aa45bf'),
        (0, _BIAS, 2, '05857576fc10cb51ec3cd77cc1a9863dc3186ddbdbe349369cf2db66e7aa45bf'),
        (2000.0, {}, 2, '56b376581a6b07b552abd59364d47a6b52ebe64f1a411dd0cd1b83412a922ca3'),
        (2000.0, {'price': 20000.0, 'ma240': 19000.0, 'bias_240': math.nan}, 2,
         'a339aa139782d3258dd6a50571d9e3e96b898891401b4de9c1f63c1cd26d4b6a'),
        (_ABSENT, {}, 3, 'bf3b38cdc5d274f749105cbfcdbb1df14e58c0a6e23ebc0925d16930ebf62695'),
    ])
    def test_undo_equals_pre_fix(self, monkeypatch, margin, bias, n_cards, golden):
        out = _wr(monkeypatch, margin=margin, bias=bias)
        undone = undo_z26_gray_card(out)
        assert sum(a != b for a, b in zip(out, undone)) == n_cards
        assert _digest(undone) == golden
        assert _digest(out) != golden

    def test_undo_card_literals(self, monkeypatch):
        undone = undo_z26_gray_card(_wr(monkeypatch, margin=None, bias={}))
        assert _card(undone, '融資餘額') == _PRE_MARGIN_CARD
        assert _card(undone, '年線位置') == _PRE_BIAS_CARD

    def test_undo_card_literals_unevaluated(self, monkeypatch):
        undone = undo_z26_gray_card(_wr(monkeypatch, reg=None))
        assert _card(undone, '大盤燈號') == _PRE_REGIME_CARD
        assert _card(undone, '持股比例') == _PRE_ALLOC_CARD

    def test_undo_noop_when_valued(self, monkeypatch):
        out = _wr(monkeypatch, alloc=_LOADED)
        assert _gray_count(out) == 0
        assert undo_z26_gray_card(out) == out


class TestValuedOutputUnchanged:
    #: 修前基底（`34904717`）實跑寫死：整段輸出 sha256（kind\x1ftext 以 \x1e 串接）。
    #  涵蓋融資 2,500 警戒門檻兩側（2500.0 綠／2500.4 紅）、3,400 極危以上、正負小值，
    #  與年線 ±20 門檻兩側（±20.0 紅／−19.96 綠）、0.0。
    @pytest.mark.parametrize('margin, b240, golden', [
        (2000.0, 5.3, '1047165428a093705bb751415566879f3fc5c4bf81c6512c892f53277b1a1cdb'),
        (2000.0, -25.0, 'b7892d2c8cd133dae524ad7a68ab9dd417f0dce4f44e95cea3d5380a14799f84'),
        (2000.0, 25.0, '63176d9932db49ab53730e88d443f8fe6d6c55767fea7e73d1699bfc7ef98440'),
        (2000.0, 0.0, '0a3f42b4e30c49da52fd999f03ae2bb0bfae191ab2a2f00b6b1e797569da6e10'),
        (2000.0, 20.0, '67bef2f7efe58d8636da047918c973d8d75c5c09ff148967932a91af0724132b'),
        (2000.0, -20.0, 'c3540844d559a4fed29b58461a87652466fef3fb5bf6daa110bbcc1a47b07a54'),
        (2000.0, -19.96, '190411a19380bba6102f0a7902cc8dfeac07f6477bb23c2f98de1083fe57be41'),
        (2500.0, 5.3, 'f88d7af651ee6b83464ab2f0b67e14c117615353d499fdcca79668a72a03ba2b'),
        (2500.4, 5.3, '7fc292c8664a02b83ac6cc438eff5b21ab9cc3e878c434bc3ec38ff9ce94e4ee'),
        (2500.4, -19.96, 'ab414ae9c70a6290d43195f1c913afdad5a13404653cc9400cadd4abd0e917d7'),
        (3000.0, 20.0, 'b9e43842ca77214f79b24201ed797615f1c3865541a3c0294ff9fca53af92d97'),
        (3401.0, 25.0, 'ca7189611375bd29646b1c961cf4fb2fac838636aea81462b987c9799034a986'),
        (3401.0, -25.0, 'ff7d5ddfa1a4ff93bda5cd9616325d0689edcdeebd7610e9623d9cea465bcc47'),
        (1.0, 0.0, 'b2ed8bfbed31c3962c18027746967fc356c358e679de8ac8f29394c58a1b3716'),
        (0.4, 5.3, '68423dfe27c80551702681932164160e6535f05b80dc0a7631560a2b4e5d90bb'),
        (-5.0, -20.0, '3d9ef5a21bcd011a668afa280b680f19da884ebde250b5a7840142c0298fa772'),
    ])
    def test_golden(self, monkeypatch, margin, b240, golden):
        out = _wr(monkeypatch, margin=margin,
                  bias={'price': 20000.0, 'ma240': 19000.0, 'bias_240': b240})
        # 本組以未載入的 allocation 實跑 ⇒「持股比例」修後走灰（由 TestUnevaluatedIsGray 守）⇒ 恰一次還原後比修前。
        for name in ('融資餘額', '年線位置'):
            assert f'border-top:3px solid {_GRAY};' not in _card(out, name)
        assert _gray_count(out) == 1
        assert _digest(undo_z26_gray_card(out)) == golden



# ══════════════════════════════════════════════════════════════════════════
# (b)：「大盤燈號」未評估、「持股比例」未載入 ⇒ 灰，不畫紅框 ⚠️
# ══════════════════════════════════════════════════════════════════════════
_UNEVALUATED_REG = [
    pytest.param(None, id='none'),
    pytest.param('unknown', id='unknown'),
    pytest.param('sideways', id='other-str'),
]


class TestUnevaluatedIsGray:
    @pytest.mark.parametrize('reg', _UNEVALUATED_REG)
    def test_regime_unevaluated_gray(self, monkeypatch, reg):
        out = _wr(monkeypatch, reg=reg, alloc=_LOADED)
        _assert_gray(_card(out, '大盤燈號'), '大盤燈號', '⬜ 總經未評估')
        assert _gray_count(out) == 1                                              # 持股已載入 ⇒ 照舊

    @pytest.mark.parametrize('reg', ['bull', 'bear', 'neutral'])
    def test_alloc_unloaded_gray(self, monkeypatch, reg):
        out = _wr(monkeypatch, reg=reg, alloc=_UNLOADED)
        _assert_gray(_card(out, '持股比例'), '持股比例', '⬜ 總經未評估')
        assert _gray_count(out) == 1                                              # 燈號已評估 ⇒ 照舊

    def test_both_unevaluated(self, monkeypatch):
        out = _wr(monkeypatch, reg=None, alloc=_UNLOADED)
        assert _gray_count(out) == 2
        assert '⚠️ 大盤燈號' not in '\x1e'.join(t for _k, t in out)

    #: 修前基底（`34904717`）實跑寫死：燈號三態 × 持股已載入（未壓低／被硬否決壓低）整段輸出 sha256。
    @pytest.mark.parametrize('reg, alloc, golden', [
        ('bull', _LOADED, 'e06a52dae85930bd31c140321809e702b418e63ed1d085c20da303b86d2cad84'),
        ('bull', _CAPPED, 'bc05383f99677f21198ee53b54f3aa244511c102a48280cd121ca2a809f6bb6a'),
        ('bear', _LOADED, 'e4900003e91a701fd28250808e35893bf2a9171b5016e6db0e524daf6f84fd0e'),
        ('bear', _CAPPED, 'b5053a5cb2602f000f993cd6a8d10fd7469f80230be9f4fa3df3ed23e288be32'),
        ('neutral', _LOADED, '957dea2b5fc7bdf101e9c1c327c87dc01aa976e30b296ddd15b785a5985b88bb'),
        ('neutral', _CAPPED, '9de003496b067a030168223c5df2b6e77b948e9233051bd6893987d45a6995f1'),
    ])
    def test_evaluated_golden(self, monkeypatch, reg, alloc, golden):
        out = _wr(monkeypatch, reg=reg, alloc=alloc)
        assert _gray_count(out) == 0
        assert _digest(out) == golden

    #: 修前基底（`34904717`）實跑寫死：未評估情形整段輸出 sha256（還原恰一次後比對）。
    @pytest.mark.parametrize('reg, alloc, n_cards, golden', [
        (None, _UNLOADED, 2, 'a2f8075adb8bb30fd85cf6a45545b75ba058915fa23adf371d0f44f0d9bdcefc'),
        ('unknown', _LOADED, 1, '9c09431c26a2aefd1da6b803f36b925696c856aaf8a56bf053d72d236f6ef795'),
        ('sideways', _CAPPED, 1, '40ee14ab4f90537bda7b0784ff9623693d9bdffc6a262d05da418fbb9ebf1810'),
        ('bear', _UNLOADED, 1, 'aca620781635114158a25b5c9117ab713db04cb325d5df2c51da073af5069984'),
        ('neutral', _UNLOADED, 1, 'fbfedb7c506ae4009176bcc812ca0c91e8b30582da93c7efa86391a789d03330'),
    ])
    def test_unevaluated_undo_equals_pre_fix(self, monkeypatch, reg, alloc, n_cards, golden):
        out = _wr(monkeypatch, reg=reg, alloc=alloc)
        undone = undo_z26_gray_card(out)
        assert sum(a != b for a, b in zip(out, undone)) == n_cards
        assert _digest(undone) == golden
