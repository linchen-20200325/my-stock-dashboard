"""tests/test_dl_f1_s5_m1b_proxy_label.py — DL-f1-s5：M1B／M2 落在代理層時必須標示（批 P）。

病史（本檔存在的理由）
────────────────────────────────────────────────────────────────
`src/data/macro/tw_macro.fetch_cbc_m1b_m2` 在央行（CBC）取不到時會落到 Tier 3
`^TWII` 動能代理（`is_proxy_tier=True`），`macro_snapshot.fetch_m1b_m2_block` 再把它打包成
`session_state['m1b_m2_info'] = {m1b_yoy, m2_yoy, gap, source='TWII-proxy'}`。
下列 5 處讀這份 dict，卻**沒有**標示代理 —— 把大盤動能當成 M1B／M2 年增率呈現或送進 AI：

    ① src/ui/tabs/macro/section_cross_ai.py        §九「③ 目前貨幣流向」卡 + 「⑤ 結論」條列
    ② src/ui/tabs/macro/section_news_ai.py         §十一 送 Gemini 的裁決 prompt（`_ctx` 那一行）
    ③ src/ui/tabs/macro/section_mid.py             §八 策略3「M1B-M2 資金動能」（gap≥1 → 積極作多）
       ＋（第二個 commit 補）同檔 ⚔️ 三環第二環「D M1B-M2=+x.xx%」徽章
    ④ src/ui/tabs/stock_sections/section_op_recommendation.py
       → L3 src/services/app_ai_service.generate_ai_comment（個股即時操作建議文案）
    ⑤ src/ui/tabs/tab_edu.py                       指標解讀手冊 ms1.json「📈 即時值」chip

第三個 commit（獨立 QA 以真 AppTest 另找到，同一件事）：
    ⑥ src/ui/tabs/macro/section_long.py            §七「策略3 × 策略1 結論」卡的 M1B-M2 數字
                                                    （同頁 KPI 卡早已有標，這張沒標）
    ⑦ src/ui/tabs/tab_macro_v2.py（＋ L4 src/ui/render/macro_v2_cards.py `Row.value_note`）
       總經 v2：總表「目前值」、桶摘要「最差項」、右側明細的數值
    （QA 另點名的頂部紅綠燈 chip —— `market_strategy` 產的 `mkt_info['signals']` ——
     在 L3 1～3 行內／L5 不嗅探字串的前提下做不到，**本批未改**，已停手回報。）

已有標示的前例：v1 `section_long` KPI 卡、L2 `compute_five_bucket_summary`、
v2 `page_today`（B7c）—— 一律後綴 L0 `shared.macro_provenance.M1B_PROXY_VALUE_NOTE`。

本批範圍（**純標示**，⛔ 不改計分／門檻／燈號／建議邏輯）
────────────────────────────────────────────────────────────────
  · 代理時：數字（或據其產生的結論句中的「M1B-M2」）後面接 L0 既有註記；
  · 非代理時：輸出逐字不變；
  · K1：只准引 L0 既有字樣，不自擬新句。

本檔釘的東西（行為斷言優先；唯一的 AST 守衛是 K1「不得自帶註記字面」）
────────────────────────────────────────────────────────────────
  A. 每處：代理（精確 source 標籤 ×2 ＋ 布林旗標）→ 註記出現在指定位置。
  B. 每處：非代理 → 關鍵字串與 **origin/main（7020d13）改動前實際輸出**逐字相同
     （下方 `_ORIG_*` 字面值 = 改動前以同一個 harness 實跑擷取）。
  C. 每處：差分 —— 代理輸出拿掉註記後 == 非代理輸出（整份 render 記錄／整份 prompt），
     ⇒ 除了那串註記，燈號顏色、結論、計分、其餘文案**一個字元都沒動**。
  D. 兩段 AI prompt（§十一 Gemini、個股 generate_ai_comment）代理時含註記。
  E. 反向對照：代理與非代理的輸出確實不同（C 不是因為註記根本沒接上而恆綠）。

⚠️ harness 說明：`_FakeST` 以 monkeypatch 換掉**被測模組**的 module-level `st`
   （測完自動還原，不動 `sys.modules['streamlit']`）；外部依賴（配置 SSOT、Gemini、
   新聞 RSS、狀態鎖寫檔）一律 monkeypatch 成離線替身，並斷言替身真的被呼叫過。
   本檔不吃執行當天日期、不觸網、不寫檔。
"""
from __future__ import annotations

import ast
import re
import types
from pathlib import Path

import pytest

from shared.macro_provenance import (
    M1B_PROXY_SOURCE_LABEL,
    M1B_PROXY_SOURCE_LABEL_RAW,
    M1B_PROXY_VALUE_NOTE as NOTE,
)

_REPO = Path(__file__).resolve().parents[1]

#: 本批動到的 6 個檔（K1 守衛掃這 6 個）
_TOUCHED = (
    "src/ui/tabs/macro/section_cross_ai.py",
    "src/ui/tabs/macro/section_news_ai.py",
    "src/ui/tabs/macro/section_mid.py",
    "src/ui/tabs/stock_sections/section_op_recommendation.py",
    "src/services/app_ai_service.py",
    "src/ui/tabs/tab_edu.py",
    # 第三個 commit（獨立 QA 以真 AppTest 找到的另外兩處）
    "src/ui/tabs/macro/section_long.py",
    "src/ui/tabs/tab_macro_v2.py",
    "src/ui/render/macro_v2_cards.py",
)


# ══════════════════════════════════════════════════════════════════════════
# 測資
# ══════════════════════════════════════════════════════════════════════════
def _info(m1b=5.1, m2=2.0, source="CBC-tier1", **extra) -> dict:
    """`m1b_m2_info` 的 production 形狀（`macro_snapshot.fetch_m1b_m2_block` 回傳鍵）。"""
    d: dict = {"m1b_yoy": m1b, "source": source}
    if m2 is not None:
        d["m2_yoy"] = m2
        d["gap"] = round(m1b - m2, 2) if m1b is not None else None
    d.update(extra)
    return d


#: 三條會被 L0 `is_m1b_m2_proxy` 判為代理的路徑
_PROXY_KW = {
    "source_label": {"source": M1B_PROXY_SOURCE_LABEL},
    "source_label_raw": {"source": M1B_PROXY_SOURCE_LABEL_RAW},
    "flag_is_proxy_tier": {"source": "CBC-tier1", "is_proxy_tier": True},
}
#: 非代理（央行兩層 / FRED / IMF / 沒帶 source）
_REAL_SOURCES = ("CBC-tier1", "CBC-tier2", "FRED", "IMF(2025)", None)

#: 三種 gap 情境：強（≥2，積極作多）/ 溫和（0~1）/ 死亡交叉（<0）
_GAPS = {"strong": (5.1, 2.0), "mild": (3.0, 2.5), "negative": (1.2, 5.0)}


def _proxy(scn="strong", how="source_label"):
    m1b, m2 = _GAPS[scn]
    return _info(m1b, m2, **_PROXY_KW[how])


def _real(scn="strong", source="CBC-tier1"):
    m1b, m2 = _GAPS[scn]
    return _info(m1b, m2, source=source)


# ══════════════════════════════════════════════════════════════════════════
# 假的 streamlit（只記錄文字；未知 API 一律 no-op）
# ══════════════════════════════════════════════════════════════════════════
class _Rerun(Exception):
    """`st.rerun()` 的替身：讓 §十一 裁決流程在 Gemini 回來後乾淨地停下。"""


class _Any:
    """未實作的 st.* 回傳值：可呼叫 / 可 with / falsy（未知 widget = 沒被按）。"""

    def __init__(self, st):
        self._st = st

    def __call__(self, *a, **k):
        return _Any(self._st)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._st, name)      # column.markdown(...) → 同一個記錄器

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __bool__(self):
        return False


class _FakeST:
    _TEXT = ("markdown", "caption", "info", "warning", "success", "error", "write")

    def __init__(self, session_state=None, clicked=()):
        self.session_state = dict(session_state or {})
        self.secrets: dict = {}
        self.out: list[tuple[str, str]] = []
        self._clicked = set(clicked)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in _FakeST._TEXT:
            def _rec(body="", *a, **k):
                self.out.append((name, str(body)))
                return _Any(self)
            return _rec
        return _Any(self)

    def columns(self, spec, *a, **k):
        return [_Any(self) for _ in range(spec if isinstance(spec, int) else len(spec))]

    def tabs(self, labels, *a, **k):
        return [_Any(self) for _ in labels]

    def expander(self, label="", *a, **k):
        self.out.append(("expander", str(label)))
        return _Any(self)

    def button(self, label="", key=None, *a, **k):
        return key in self._clicked

    def checkbox(self, *a, **k):
        return False

    toggle = checkbox

    def rerun(self, *a, **k):
        raise _Rerun()

    @property
    def sidebar(self):
        return _Any(self)

    @property
    def text(self) -> str:
        return "\n".join(t for _, t in self.out)


def _strip_note(records):
    return [(k, t.replace(NOTE, "")) for k, t in records]


# ══════════════════════════════════════════════════════════════════════════
# 5 個 render 入口（全部離線）
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def run(monkeypatch):
    """回一個具 5 個方法的物件；每個方法吃 `m1b_m2_info`，回 render 記錄。"""
    import src.services.allocation_service as AS

    calls: dict[str, int] = {}

    def _hit(name):
        calls[name] = calls.get(name, 0) + 1

    class _Runner:
        calls_seen = calls

        # ① §九 跨桶規則決策
        @staticmethod
        def cross_ai(info) -> _FakeST:
            import src.ui.tabs.macro.section_cross_ai as M
            fake = _FakeST({"m1b_m2_info": info,
                            "macro_info": {"vix": {"current": 15.0}}})
            monkeypatch.setattr(M, "st", fake)

            def _alloc(*a, **k):
                _hit("get_allocation")
                return types.SimpleNamespace(is_loaded=False)
            monkeypatch.setattr(AS, "get_allocation", _alloc)
            M.render_section_cross_ai({}, {})
            return fake

        # ② §十一 AI 總裁決（按下「🔒 執行 AI 裁決」→ 攔下送 Gemini 的 prompt）
        @staticmethod
        def news(info):
            import src.data.news as N
            import src.services.app_ai_service as A
            import src.ui.tabs.macro.section_news_ai as M
            fake = _FakeST({"m1b_m2_info": info}, clicked={"btn_run_verdict"})
            prompts: list[str] = []
            locked: list[dict] = []

            class _Locker:                       # 不寫 macro_state.json
                def lock_system_state_only(self, state):
                    locked.append(state)

            def _gemini(prompt, max_tokens=2048):
                prompts.append(prompt)
                return "（測試替身報告）"

            def _news(*a, **k):
                _hit("fetch_macro_news")
                return []

            monkeypatch.setattr(M, "st", fake)
            monkeypatch.setattr(M, "render_macro_bucket_summary_bar", lambda *a, **k: None)
            monkeypatch.setattr(M, "MacroStateLocker", _Locker)
            monkeypatch.setattr(A, "gemini_call", _gemini)
            monkeypatch.setattr(N, "fetch_macro_news", _news)
            with pytest.raises(_Rerun):
                M.render_section_news_ai({}, "unknown")
            assert len(prompts) == 1, "Gemini 替身沒被呼叫到 —— patch 目標失效"
            assert len(locked) == 1, "狀態鎖替身沒被呼叫到 —— patch 目標失效"
            return prompts[0], locked[0]

        # ③ §八 策略3
        @staticmethod
        def mid(info) -> _FakeST:
            import src.ui.tabs.macro.section_chips as SC
            import src.ui.tabs.macro.section_mid as M
            fake = _FakeST({"m1b_m2_info": info})
            monkeypatch.setattr(M, "st", fake)
            monkeypatch.setattr(AS, "apply_vix_veto", lambda *a, **k: _hit("apply_vix_veto"))
            monkeypatch.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
            monkeypatch.setattr(AS, "register_conflict", lambda *a, **k: None)
            monkeypatch.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
                is_loaded=False, final_hi=None))
            monkeypatch.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
            M.render_section_mid(False, {}, {}, {})
            return fake

        # ④ 個股「即時操作建議」（L5 → L3 generate_ai_comment）
        @staticmethod
        def op(info) -> _FakeST:
            import src.ui.tabs.stock_sections.section_op_recommendation as M

            def _regime(*a, **k):
                _hit("get_macro_regime")
                return {"is_loaded": False}
            fake = _FakeST({"m1b_m2_info": info, "cl_data": {"inst": {}}})
            monkeypatch.setattr(M, "st", fake)
            monkeypatch.setattr(AS, "get_macro_regime", _regime)
            M.render_op_recommendation_section("2330", 82.0, {"contracting": True},
                                               5.0, 100.0, 55.0, 0, 0)
            return fake

        # ⑤ 系統說明書 → 指標解讀手冊
        @staticmethod
        def edu(info) -> _FakeST:
            import src.ui.tabs.tab_edu as M

            def _no_fred(*a, **k):
                _hit("fred")
                return None
            fake = _FakeST({"m1b_m2_info": info})
            monkeypatch.setattr(M, "st", fake)
            monkeypatch.setattr(M, "_fetch_fred_series_edu", _no_fred)
            M.render_tab_edu()
            return fake

        # ⑥ §七 長期桶（「策略3 × 策略1 結論」卡）
        @staticmethod
        def long(info) -> _FakeST:
            import src.ui.tabs.macro.section_long as M

            def _no_bar(*a, **k):                # 五桶 bar 另有自己的 st，非本批範圍
                _hit("bucket_bar")
            fake = _FakeST({"m1b_m2_info": info})
            monkeypatch.setattr(M, "st", fake)
            monkeypatch.setattr(M, "render_macro_bucket_summary_bar", _no_bar)
            M.render_section_long(False, {}, {}, {}, {}, {}, {})
            return fake

        # ⑦ 總經 v2：L2 側車 → L5 `build_rows`（純函式，不需 st）
        @staticmethod
        def v2_rows(info) -> list:
            import src.ui.tabs.tab_macro_v2 as V
            from src.compute.macro.macro_helpers import compute_five_bucket_summary
            rd: dict = {}
            compute_five_bucket_summary(m1b_m2_info=info, readiness_out=rd)
            return V.build_rows(rd)

        # ⑦ 總經 v2：L4 右側明細面板
        @staticmethod
        def v2_detail(row) -> _FakeST:
            import src.ui.render.macro_v2_cards as C
            from shared.macro_buckets import SPECS_BY_KEY
            fake = _FakeST({})
            monkeypatch.setattr(C, "st", fake)
            C.render_detail(row, SPECS_BY_KEY[row.key], edu=None, reason_text="")
            return fake

    return _Runner()


def _card(fake: _FakeST, title: str) -> str:
    hits = [t for _, t in fake.out if title in t]
    assert len(hits) == 1, f"找不到（或不只一張）「{title}」卡：{len(hits)} 張"
    return hits[0]


# ══════════════════════════════════════════════════════════════════════════
# ① §九 跨桶規則決策：③ 目前貨幣流向 + ⑤ 結論
# ══════════════════════════════════════════════════════════════════════════
#: origin/main（7020d13）改動前實際輸出（非代理）
_ORIG_XAI_CARD3 = {
    "strong": "M1B=5.1% M2=2.0% Gap=+3.10% — 黃金交叉大幅擴散，投機資金湧入，活絡貨幣遠超廣義貨幣",
    "mild": "M1B=3.0% M2=2.5% Gap=+0.50% — M1B微幅領先，資金偏多但動能尚未爆發，需等待 Gap≥1% 確認",
    "negative": "M1B=1.2% M2=5.0% Gap=-3.80% — 死亡交叉，資金轉向固定收益，股市失血，謹慎操作",
}
_ORIG_XAI_POINT_STRONG = "M1B-M2 Gap=+3.1% 資金動能正向共振"
_ORIG_XAI_POINT_NEGATIVE = "M1B-M2死亡交叉，貨幣資金外逃"
_ORIG_XAI_M2_MISSING_LABEL = "M1B=5.1% M2待取得"


class TestCrossAiSection9:

    def test_harness_reaches_the_cards(self, run):
        fake = run.cross_ai(_real())
        assert run.calls_seen.get("get_allocation") == 1, "配置替身沒被呼叫到 —— patch 失效"
        assert _ORIG_XAI_CARD3["strong"] in _card(fake, "③ 目前貨幣流向")

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_proxy_card3_value_has_note(self, run, scn, how):
        card = _card(run.cross_ai(_proxy(scn, how)), "③ 目前貨幣流向")
        m1b, m2 = _GAPS[scn]
        gap = round(m1b - m2, 2)
        assert f"Gap={gap:+.2f}%{NOTE} — " in card, card

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    def test_proxy_conclusion_points_have_note(self, run, how):
        c5 = _card(run.cross_ai(_proxy("strong", how)), "⑤ 結論")
        assert f"M1B-M2 Gap=+3.1%{NOTE} 資金動能正向共振" in c5, c5
        c5n = _card(run.cross_ai(_proxy("negative", how)), "⑤ 結論")
        assert f"M1B-M2{NOTE}死亡交叉，貨幣資金外逃" in c5n, c5n

    def test_proxy_m2_missing_label_has_note(self, run):
        info = _info(5.1, None, source=M1B_PROXY_SOURCE_LABEL)
        card = _card(run.cross_ai(info), "③ 目前貨幣流向")
        assert f"M1B=5.1%{NOTE} M2待取得" in card, card

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_non_proxy_card3_is_byte_identical_to_before(self, run, scn, source):
        fake = run.cross_ai(_real(scn, source))
        assert _ORIG_XAI_CARD3[scn] in _card(fake, "③ 目前貨幣流向")
        assert NOTE not in fake.text

    def test_non_proxy_conclusion_points_are_byte_identical_to_before(self, run):
        assert _ORIG_XAI_POINT_STRONG in _card(run.cross_ai(_real("strong")), "⑤ 結論")
        assert _ORIG_XAI_POINT_NEGATIVE in _card(run.cross_ai(_real("negative")), "⑤ 結論")
        assert _ORIG_XAI_M2_MISSING_LABEL in _card(
            run.cross_ai(_info(5.1, None)), "③ 目前貨幣流向")

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_only_difference_is_the_note(self, run, scn, how):
        """燈號顏色 / ⑤ 多空計分結論 / 其餘文案：代理與非代理逐字相同，差別只有註記。"""
        p = run.cross_ai(_proxy(scn, how)).out
        r = run.cross_ai(_real(scn)).out
        assert _strip_note(p) == r
        assert p != r, "反向對照：代理時必須真的多出註記（否則上一行恆綠）"

    def test_no_note_without_a_number(self, run):
        """代理源但 M1B 缺 → 卡片是「待取得」，不得出現孤零零的註記。"""
        fake = run.cross_ai(_info(None, None, source=M1B_PROXY_SOURCE_LABEL))
        assert "待取得 M1B/M2" in _card(fake, "③ 目前貨幣流向")
        assert NOTE not in fake.text


# ══════════════════════════════════════════════════════════════════════════
# ② §十一 送 Gemini 的裁決 prompt
# ══════════════════════════════════════════════════════════════════════════
_ORIG_NEWS_LINE = {
    "strong": "• M1B=5.1%  M2=2.0%  差額=+3.10%（正=資金行情啟動；",
    "negative": "• M1B=1.2%  M2=5.0%  差額=-3.80%（正=資金行情啟動；",
}


def _m1b_line(prompt: str) -> str:
    lines = [ln for ln in prompt.splitlines() if ln.startswith("• M1B=")]
    assert len(lines) == 1, f"prompt 內 M1B 行數應為 1，實得 {len(lines)}"
    return lines[0]


class TestNewsAiPrompt:

    def test_harness_reaches_gemini(self, run):
        prompt, _ = run.news(_real())
        assert run.calls_seen.get("fetch_macro_news") == 1, "新聞替身沒被呼叫到 —— patch 失效"
        assert _m1b_line(prompt).startswith(_ORIG_NEWS_LINE["strong"])

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", ["strong", "negative"])
    def test_proxy_line_carries_the_note(self, run, scn, how):
        line = _m1b_line(run.news(_proxy(scn, how))[0])
        m1b, m2 = _GAPS[scn]
        gap = round(m1b - m2, 2)
        assert f"差額={gap:+.2f}%{NOTE}（正=資金行情啟動；" in line, line

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", ["strong", "negative"])
    def test_non_proxy_line_is_byte_identical_to_before(self, run, scn, source):
        prompt, _ = run.news(_real(scn, source))
        assert _m1b_line(prompt).startswith(_ORIG_NEWS_LINE[scn])
        assert NOTE not in prompt

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", ["strong", "negative"])
    def test_only_difference_is_the_note_and_rule_engine_unchanged(self, run, scn, how):
        """整份 prompt 拿掉註記後逐字相同；規則引擎寫進狀態鎖的結果也完全相同。

        兩個情境（第三個 commit 依獨立 QA 建議補 strong）：
          · strong（gap +3.10）：M1B 讓分數 +15 → 狀態**成為多頭**；
          · negative（gap −3.80）：M1B 讓分數 −10 並加註「資金緊縮」。
        ⚠️ 「只在代理時把 M1B 從引擎拿掉（M2 照送）」這種偷改計分，**只有 strong 抓得到**
        —— negative 情境拿掉 M1B 後 spread 變 −5.00，仍 < −3，分數與標籤碰巧相同
        （實測：只跑 negative 時該突變不會轉紅）。前提見下一條守衛。
        """
        p_prompt, p_state = run.news(_proxy(scn, how))
        r_prompt, r_state = run.news(_real(scn))
        assert p_prompt.replace(NOTE, "") == r_prompt
        assert p_prompt != r_prompt, "反向對照：代理時 prompt 必須真的多出註記"
        assert p_state == r_state, "只准揭露：calculate_system_state 的結果不得因代理而變"

    def test_strong_scenario_is_sensitive_to_m1b_only_removal(self, run):
        """前提守衛（QA 的 M10）：上一條要抓得到「只在代理時把 M1B 從引擎拿掉」，
        strong 情境本身必須對「只拿掉 M1B、M2 照送」敏感 —— 否則 `p_state == r_state`
        就算引擎被偷改也照樣綠。
        """
        from src.services.macro_state_locker import calculate_system_state
        _, r_state = run.news(_real("strong"))
        assert r_state["market_regime"] == "多頭", r_state
        m1b, m2 = _GAPS["strong"]
        with_m1b = calculate_system_state({"M1B_YoY_pct": m1b, "M2_YoY_pct": m2})
        m1b_removed = calculate_system_state({"M1B_YoY_pct": None, "M2_YoY_pct": m2})
        assert with_m1b == r_state, "前提：prompt 流程送進引擎的就是這組 M1B/M2"
        assert m1b_removed["market_regime"] != "多頭", m1b_removed


# ══════════════════════════════════════════════════════════════════════════
# ③ §八 策略3 M1B-M2 資金動能
# ══════════════════════════════════════════════════════════════════════════
_ORIG_MID = {
    "strong": ("M1B-M2 Gap = +3.10%（黃金交叉·熱錢狂潮）",
               "🔥 資金動能強勁（M1B=5.1% > M2=2.0%），熱錢湧入股市，積極作多強勢股。"),
    "mild": ("M1B-M2 Gap = +0.50%（資金溫和·中性擴張）",
             "💧 資金動能溫和（M1B=3.0% ≥ M2=2.5%），無失血風險，回歸個股基本面與籌碼面操作。"),
    "negative": ("M1B-M2 Gap = -3.80%（死亡交叉·資金退潮）",
                 "📉 資金動能趨緩（M1B=1.2% < M2=5.0%），資金轉向定存或匯出，減碼等待訊號確認。"),
}
_MID_TAIL = {"strong": "（黃金交叉·熱錢狂潮）", "mild": "（資金溫和·中性擴張）",
             "negative": "（死亡交叉·資金退潮）"}


def _strategy3(fake: _FakeST) -> str:
    hits = [t for _, t in fake.out if "M1B-M2 Gap = " in t]
    assert len(hits) == 1, f"策略3 M1B-M2 卡應恰 1 張，實得 {len(hits)}"
    return hits[0]


class TestMidStrategy3:

    def test_harness_reaches_strategy3(self, run):
        fake = run.mid(_real())
        assert run.calls_seen.get("apply_vix_veto") == 1, "VIX 否決替身沒被呼叫到 —— patch 失效"
        assert _ORIG_MID["strong"][0] in _strategy3(fake)

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_proxy_gap_value_has_note(self, run, scn, how):
        card = _strategy3(run.mid(_proxy(scn, how)))
        m1b, m2 = _GAPS[scn]
        gap = round(m1b - m2, 2)
        _num = f"+{gap:.2f}" if gap >= 0 else f"{gap:.2f}"
        assert f"M1B-M2 Gap = {_num}%{NOTE}{_MID_TAIL[scn]}" in card, card

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_non_proxy_is_byte_identical_to_before(self, run, scn, source):
        card = _strategy3(run.mid(_real(scn, source)))
        indicator, conclusion = _ORIG_MID[scn]
        assert indicator in card and conclusion in card, card
        assert NOTE not in card

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_only_difference_is_the_note(self, run, scn, how):
        """含顏色、「積極作多強勢股」結論、⚔️ 三環火力分級：全部逐字相同。"""
        p = run.mid(_proxy(scn, how)).out
        r = run.mid(_real(scn)).out
        assert _strip_note(p) == r
        assert p != r


# ══════════════════════════════════════════════════════════════════════════
# ③' §八 ⚔️ 三環第二環「D M1B-M2」徽章（同一個 M1B-M2 數字，第二個 commit 補）
# ══════════════════════════════════════════════════════════════════════════
#: 改動前（7020d13）實際輸出：徽章 span 內文就是 `D M1B-M2=+3.10%`，後面緊接 `</span>`
_ORIG_D_TEXT = {"strong": "D M1B-M2=+3.10%", "mild": "D M1B-M2=+0.50%",
                "negative": "D M1B-M2=-3.80%"}
_D_SPAN = re.compile(r'<span style="[^"]*">(D M1B-M2[^<]*)</span>')


def _d_badge(fake: _FakeST) -> tuple[str, str]:
    """回 (徽章完整 span HTML, 徽章文字)；三環卡應恰有一張、D 徽章恰一個。"""
    cards = [t for _, t in fake.out if "第二環（確認燃料）" in t]
    assert len(cards) == 1, f"⚔️ 三環火力分級卡應恰 1 張，實得 {len(cards)}"
    hits = list(_D_SPAN.finditer(cards[0]))
    assert len(hits) == 1, f"D 徽章應恰 1 個，實得 {len(hits)}：{cards[0]}"
    return hits[0].group(0), hits[0].group(1)


class TestMidRing2DBadge:

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_proxy_d_badge_has_note(self, run, scn, how):
        _span, text = _d_badge(run.mid(_proxy(scn, how)))
        assert text == f"{_ORIG_D_TEXT[scn]}{NOTE}", text

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_non_proxy_d_badge_is_byte_identical_to_before(self, run, scn, source):
        span, text = _d_badge(run.mid(_real(scn, source)))
        assert text == _ORIG_D_TEXT[scn], text
        assert span.endswith(f">{_ORIG_D_TEXT[scn]}</span>"), span

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_badge_color_and_condition_unchanged(self, run, scn, how):
        """`_cD` 判定（徽章綠／灰）不因代理而變：span 拿掉註記後與非代理逐字相同。"""
        p_span, _ = _d_badge(run.mid(_proxy(scn, how)))
        r_span, _ = _d_badge(run.mid(_real(scn)))
        assert p_span.replace(NOTE, "") == r_span
        assert p_span != r_span, "反向對照：代理時徽章必須真的多出註記"

    def test_unknown_badge_has_no_note(self, run):
        """代理源但缺數字 → 仍是「D M1B-M2未知」，不得貼註記。"""
        _span, text = _d_badge(run.mid(_NO_NUMBER))
        assert text == "D M1B-M2未知", text


# ══════════════════════════════════════════════════════════════════════════
# ⑥ §七「策略3 × 策略1 結論」卡（第三個 commit；獨立 QA 以真 AppTest 找到）
# ══════════════════════════════════════════════════════════════════════════
#: 本組另加一個「接近 0」情境，讓 §七 的三段分支（>0 / >-2 / 其餘）全部走到
_S7_GAPS = {**_GAPS, "near_zero": (1.0, 2.0)}
#: 改動前（a2cf529）實際輸出：strategy_conclusion 的指標段（含結尾「 → 」）
_ORIG_S7 = {
    "strong": "M1B-M2=+3.10% 正值 → ",
    "mild": "M1B-M2=+0.50% 正值 → ",
    "negative": "M1B-M2=-3.80% 負值 → ",
    "near_zero": "M1B-M2=-1.00% 接近0 → ",
}
_S7_TAIL = {"strong": " 正值 → ", "mild": " 正值 → ", "negative": " 負值 → ",
            "near_zero": " 接近0 → "}
#: 同頁 KPI 卡在代理時**本來就**多印一行獨立警語（v19.183 D2，不是本批加的）。
#: 差分比對前把它拿掉 —— 用它的具名開頭定位，且斷言恰好拿掉一行。
_D2_PROXY_CAPTION_HEAD = "⚠️ 央行 M1B/M2 三層來源全部失敗"


def _s7_info(scn, proxy_how=None, source="CBC-tier1"):
    m1b, m2 = _S7_GAPS[scn]
    return (_info(m1b, m2, **_PROXY_KW[proxy_how]) if proxy_how
            else _info(m1b, m2, source=source))


def _s7_card(fake: _FakeST) -> str:
    hits = [t for _, t in fake.out if "🎯 策略3" in t and "M1B-M2=" in t]
    assert len(hits) == 1, f"§七 M1B 結論卡應恰 1 張，實得 {len(hits)}"
    return hits[0]


class TestSection7ConclusionCard:

    def test_harness_reaches_the_card(self, run):
        card = _s7_card(run.long(_s7_info("strong")))
        # 本 section 會畫不只一條桶 bar（長期 + 中期）→ 只斷言替身確實被呼叫過
        assert run.calls_seen.get("bucket_bar", 0) >= 1, "五桶 bar 替身沒被呼叫到 —— patch 失效"
        assert f">{_ORIG_S7['strong']}</span>" in card, card

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_S7_GAPS))
    def test_proxy_value_has_note(self, run, scn, how):
        card = _s7_card(run.long(_s7_info(scn, how)))
        m1b, m2 = _S7_GAPS[scn]
        assert f">M1B-M2={m1b - m2:+.2f}%{NOTE}{_S7_TAIL[scn]}</span>" in card, card

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", sorted(_S7_GAPS))
    def test_non_proxy_is_byte_identical_to_before(self, run, scn, source):
        fake = run.long(_s7_info(scn, source=source))
        assert f">{_ORIG_S7[scn]}</span>" in _s7_card(fake)
        assert NOTE not in fake.text

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_S7_GAPS))
    def test_only_difference_is_the_note(self, run, scn, how):
        """結論文案、顏色、同頁其餘卡片：拿掉註記（與 D2 既有警語）後逐字相同。"""
        p = run.long(_s7_info(scn, how)).out
        r = run.long(_s7_info(scn)).out
        p_wo_d2 = [x for x in p if not x[1].startswith(_D2_PROXY_CAPTION_HEAD)]
        assert len(p) - len(p_wo_d2) == 1, "D2 既有警語應恰好一行（定位失準會讓差分失真）"
        assert _strip_note(p_wo_d2) == r
        assert p_wo_d2 != r, "反向對照：代理時必須真的多出註記"


# ══════════════════════════════════════════════════════════════════════════
# ⑦ 總經 v2：總表「目前值」、桶摘要「最差項」、右側明細（第三個 commit）
# ══════════════════════════════════════════════════════════════════════════
#: 改動前（a2cf529）實際輸出：`fmt_value` 的結果（負號為 U+2212）
_ORIG_V2_VALUE = {"strong": "3.10%", "mild": "0.50%", "negative": "−3.80%"}


def _v2_m1b(rows):
    hits = [r for r in rows if r.key == "m1b_m2_gap"]
    assert len(hits) == 1, f"m1b_m2_gap 應恰 1 列，實得 {len(hits)}"
    return hits[0]


def _v2_views(rows):
    """(總表 m1b 的「目前值」, 長期桶摘要, 整張表, 整份摘要)。"""
    import src.ui.tabs.tab_macro_v2 as V
    vis, table = V.visible_table(rows)
    i = [r.key for r in vis].index("m1b_m2_gap")
    summary = V.bucket_summary(rows)
    long_b = [b for b in summary if b["name"] == "長期"]
    assert len(long_b) == 1, summary
    return table["目前值"][i], long_b[0], table, summary


def _v2_big_value(fake: _FakeST) -> str:
    hits = [t for _, t in fake.out if "font-size:34px" in t]
    assert len(hits) == 1, f"右側明細的大字數值應恰 1 個，實得 {len(hits)}"
    return hits[0]


class TestMacroV2Page:

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_proxy_table_summary_and_detail_have_note(self, run, scn, how):
        rows = run.v2_rows(_proxy(scn, how))
        cur, long_b, _t, _s = _v2_views(rows)
        want = f"{_ORIG_V2_VALUE[scn]}{NOTE}"
        assert cur == want, cur
        # 只餵 M1B → 長期桶其餘燈無資料 → 最差項必為 M1B（前提照實斷言）
        assert long_b["worst_label"] == "M1B-M2 資金動能", long_b
        assert long_b["worst_value"] == want, long_b
        assert f">{want}</div>" in _v2_big_value(run.v2_detail(_v2_m1b(rows)))

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_non_proxy_is_byte_identical_to_before(self, run, scn, source):
        """只看畫面字串（改動前後都能跑）：與 a2cf529 實際輸出逐字相同。"""
        rows = run.v2_rows(_real(scn, source))
        cur, long_b, table, summary = _v2_views(rows)
        assert cur == _ORIG_V2_VALUE[scn] and long_b["worst_value"] == _ORIG_V2_VALUE[scn]
        assert NOTE not in str(table) and NOTE not in str(summary)
        assert f">{_ORIG_V2_VALUE[scn]}</div>" in _v2_big_value(run.v2_detail(_v2_m1b(rows)))

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    def test_non_proxy_rows_carry_no_note(self, run, source):
        assert all(r.value_note == "" for r in run.v2_rows(_real("strong", source)))

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_only_difference_is_the_note(self, run, scn, how):
        """燈色 / 狀態 / 桶等級 / 指標危險度：代理與非代理完全相同，差別只有註記。"""
        import dataclasses

        import src.ui.tabs.tab_macro_v2 as V
        p_rows = run.v2_rows(_proxy(scn, how))
        r_rows = run.v2_rows(_real(scn))
        assert [dataclasses.replace(r, value_note="") for r in p_rows] == r_rows
        _pc, _pl, p_table, p_summary = _v2_views(p_rows)
        _rc, _rl, r_table, r_summary = _v2_views(r_rows)
        strip = {k: [str(v).replace(NOTE, "") for v in vs] for k, vs in p_table.items()}
        assert strip == {k: [str(v) for v in vs] for k, vs in r_table.items()}
        assert [{k: (v.replace(NOTE, "") if isinstance(v, str) else v) for k, v in b.items()}
                for b in p_summary] == r_summary
        assert V.overall_verdict(p_summary) == V.overall_verdict(r_summary)
        assert p_table != r_table, "反向對照：代理時總表必須真的多出註記"

    def test_no_note_without_a_number(self, run):
        """代理源但缺數字 → 那一列是「無資料」，不得貼註記。"""
        rows = run.v2_rows(_NO_NUMBER)
        cur, _long_b, table, summary = _v2_views(rows)
        assert cur == "無資料"
        assert NOTE not in str(table) and NOTE not in str(summary)

    def test_value_note_is_display_only_default(self):
        """L4 `Row.value_note` 預設空字串 —— 既有呼叫端（不帶此欄）行為不變。"""
        from src.ui.render.macro_v2_cards import Row
        r = Row(key="vix", label="VIX", bucket="short", unit="", value=20.0, band="green",
                state="live", reason=None, hit_source=None, thr_text="—", source="—",
                note="", decimals=1)
        assert r.value_note == ""


# ══════════════════════════════════════════════════════════════════════════
# ④ 個股即時操作建議：L5 帶 m1b_m2_info → L3 generate_ai_comment
# ══════════════════════════════════════════════════════════════════════════
_ORIG_GAC = {
    3.1: "• 🌐 【景氣環境】M1B-M2為正且強勁，資金行情啟動中，可積極持股。",
    -3.8: ("• 🌐 【景氣環境】M1B-M2為負，目前處於資金縮減期。"
           "建議偏保守、降低持股比重，優先選擇低位階、高股利標的"
           "（實際持股水位見 🎚️ 建議持股油門）。"),
}


def _gac(m1b_diff, info="__absent__"):
    from src.services.app_ai_service import generate_ai_comment
    data = {"m1b_diff": m1b_diff}
    if info != "__absent__":
        data["m1b_m2_info"] = info
    return generate_ai_comment(data)


class TestGenerateAiComment:

    @pytest.mark.parametrize("diff", sorted(_ORIG_GAC))
    def test_old_callers_are_byte_identical(self, diff):
        """不帶 `m1b_m2_info` 的舊 caller → 與改動前逐字相同。"""
        assert _gac(diff) == _ORIG_GAC[diff]

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("diff", sorted(_ORIG_GAC))
    def test_non_proxy_info_is_byte_identical(self, diff, source):
        assert _gac(diff, {"m1b_yoy": 1.0, "m2_yoy": 1.0, "source": source}) == _ORIG_GAC[diff]

    @pytest.mark.parametrize("bad", [None, {}, "x"])
    def test_malformed_info_is_byte_identical(self, bad):
        assert _gac(3.1, bad) == _ORIG_GAC[3.1]

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("diff", sorted(_ORIG_GAC))
    def test_proxy_puts_note_right_after_m1b_m2(self, diff, how):
        out = _gac(diff, _proxy("strong", how))
        assert f"【景氣環境】M1B-M2{NOTE}為" in out, out
        assert out.replace(NOTE, "") == _ORIG_GAC[diff], "註記以外不得有任何差異"

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    def test_no_m1b_line_no_note(self, how):
        """0 ≤ gap ≤ 2 → 本來就沒有景氣環境那一行 → 也不得憑空出現註記。"""
        assert NOTE not in _gac(1.0, _proxy("strong", how))


_ORIG_OP = {
    "strong": "• 🌐 【景氣環境】M1B-M2為正且強勁，資金行情啟動中，可積極持股。",
    "negative": "• 🌐 【景氣環境】M1B-M2為負，目前處於資金縮減期。",
}


def _op_comment(fake: _FakeST) -> str:
    hits = [t for _, t in fake.out if "【景氣環境】" in t]
    assert len(hits) == 1, f"即時操作建議文案卡應恰 1 張，實得 {len(hits)}"
    return hits[0]


class TestOpRecommendationSection:

    def test_harness_reaches_the_comment(self, run):
        fake = run.op(_real())
        assert run.calls_seen.get("get_macro_regime") == 1, "大盤格局替身沒被呼叫到 —— patch 失效"
        assert _ORIG_OP["strong"] in _op_comment(fake)

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", ["strong", "negative"])
    def test_proxy_reaches_the_card(self, run, scn, how):
        """L5 真的把 m1b_m2_info 帶進 L3 —— 畫面上的文案帶註記。"""
        card = _op_comment(run.op(_proxy(scn, how)))
        assert f"【景氣環境】M1B-M2{NOTE}為" in card, card

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    @pytest.mark.parametrize("scn", ["strong", "negative"])
    def test_non_proxy_is_byte_identical_to_before(self, run, scn, source):
        fake = run.op(_real(scn, source))
        assert _ORIG_OP[scn] in _op_comment(fake)
        assert NOTE not in fake.text

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", ["strong", "negative"])
    def test_only_difference_is_the_note(self, run, scn, how):
        """4 訊號共振計分、策略結論、年線乖離揭露：全部逐字相同。"""
        p = run.op(_proxy(scn, how)).out
        r = run.op(_real(scn)).out
        assert _strip_note(p) == r
        assert p != r


# ══════════════════════════════════════════════════════════════════════════
# ⑤ 系統說明書：ms1.json 的「📈 即時值」chip
# ══════════════════════════════════════════════════════════════════════════
def _edu_chips(fake: _FakeST) -> list[str]:
    return [t for _, t in fake.out if "📈 即時值與趨勢" in t]


class TestEduLiveValueChip:

    def test_harness_reaches_the_chip(self, run):
        chips = _edu_chips(run.edu(_real()))
        assert len(chips) == 1, f"只餵 M1B/M2 → 應只有 ms1.json 一張 chip，實得 {len(chips)}"
        assert ">3.10</span>" in chips[0], chips[0]      # 改動前實際輸出

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    @pytest.mark.parametrize("scn", sorted(_GAPS))
    def test_proxy_value_has_note(self, run, scn, how):
        chips = _edu_chips(run.edu(_proxy(scn, how)))
        m1b, m2 = _GAPS[scn]
        assert len(chips) == 1
        assert f">{m1b - m2:.2f}{NOTE}</span>" in chips[0], chips[0]

    @pytest.mark.parametrize("source", _REAL_SOURCES)
    def test_non_proxy_is_byte_identical_to_before(self, run, source):
        fake = run.edu(_real("strong", source))
        chips = _edu_chips(fake)
        assert len(chips) == 1 and ">3.10</span>" in chips[0], chips
        assert NOTE not in fake.text

    @pytest.mark.parametrize("how", sorted(_PROXY_KW))
    def test_only_difference_is_the_note(self, run, how):
        """整本說明書（含 Z 值顏色、趨勢圖說明、教學卡）逐字相同，差別只有註記。"""
        p = run.edu(_proxy("strong", how)).out
        r = run.edu(_real("strong")).out
        assert _strip_note(p) == r
        assert p != r
        assert sum(t.count(NOTE) for _, t in p) == 1, "註記只該貼在 ms1.json 那一個數字上"


# ══════════════════════════════════════════════════════════════════════════
# 沒有數字就沒有註記（代理源但 M1B 缺 → 不得出現孤零零的「（…代理估算）」）
# ══════════════════════════════════════════════════════════════════════════
_NO_NUMBER = _info(None, None, source=M1B_PROXY_SOURCE_LABEL)


class TestNoNoteWithoutANumber:

    def test_news_prompt_has_no_m1b_line_and_no_note(self, run):
        prompt, _ = run.news(_NO_NUMBER)
        assert "• M1B=" not in prompt and NOTE not in prompt

    def test_mid_falls_back_to_pending_without_note(self, run):
        fake = run.mid(_NO_NUMBER)
        assert "M1B/M2 數據載入後自動顯示資金動能判斷" in fake.text
        assert NOTE not in fake.text

    def test_op_has_no_note(self, run):
        assert NOTE not in run.op({"source": M1B_PROXY_SOURCE_LABEL}).text

    def test_edu_has_no_chip_and_no_note(self, run):
        fake = run.edu(_NO_NUMBER)
        assert _edu_chips(fake) == [] and NOTE not in fake.text


# ══════════════════════════════════════════════════════════════════════════
# K1：6 個檔不得自帶註記字面 —— 一律引 L0（AST：只看字串常數，註解天然排除）
# ══════════════════════════════════════════════════════════════════════════
class TestK1NoSelfAuthoredCopy:

    @pytest.mark.parametrize("rel", _TOUCHED)
    def test_note_literal_not_duplicated(self, rel):
        src = (_REPO / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        bad = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str) and NOTE in n.value]
        assert not bad, (f"{rel}: 第 {bad} 行自帶一份「{NOTE}」字面 —— K1 規定一律引 "
                         "`shared.macro_provenance`，不得複製（複製 = 第二個真相源）")


# ══════════════════════════════════════════════════════════════════════════
# slow lane：真 Streamlit（AppTest）render —— 確認註記真的長在畫面上
# （上面的 `_FakeST` 只證明「字串組對了」；這裡證明真 runtime 也照樣渲染出來）
# ══════════════════════════════════════════════════════════════════════════
_APP_TARGETS = {
    "cross_ai": ("from src.ui.tabs.macro.section_cross_ai import render_section_cross_ai\n"
                 "render_section_cross_ai({}, {})"),
    "mid": ("from src.ui.tabs.macro.section_mid import render_section_mid\n"
            "render_section_mid(False, {}, {}, {})"),
    "op": ("from src.ui.tabs.stock_sections.section_op_recommendation import "
           "render_op_recommendation_section\n"
           "render_op_recommendation_section('2330', 82.0, {'contracting': True}, "
           "5.0, 100.0, 55.0, 0, 0)"),
    # 第三個 commit
    "long": ("from src.ui.tabs.macro.section_long import render_section_long\n"
             "render_section_long(False, {}, {}, {}, {}, {}, {})"),
    "macro_v2": ("from src.ui.tabs.tab_macro_v2 import render_tab_macro_v2\n"
                 "render_tab_macro_v2()"),
}


def _app_markdown(target: str, info: dict) -> list[str]:
    """真 render 後的 markdown 文字 ＋ 所有 `st.dataframe` 儲存格（總經 v2 總表住在那裡）。

    同頁 §七 KPI 卡在代理時本來就多一行 D2 獨立警語（不是本批加的）—— 不論該版本
    Streamlit 把 caption 放進哪個集合，一律依具名開頭排除，差分才比得準。
    """
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    body = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import streamlit as st\n"
        f"st.session_state['m1b_m2_info'] = {info!r}\n"
        "st.session_state['macro_info'] = {'vix': {'current': 15.0}}\n"
        "st.session_state['cl_data'] = {'inst': {}}\n"
        f"{_APP_TARGETS[target]}\n"
    )
    at = AppTest.from_string(body, default_timeout=90)
    at.run()
    if at.exception:
        pytest.fail("render 有 uncaught exception:\n" + "\n".join(
            f"{e.type}: {str(e.value)[:300]}" for e in at.exception))
    out = [str(m.value) for m in at.markdown]
    assert out, "render 完全沒有 markdown 輸出 —— driver 沒跑到 section"
    for d in at.dataframe:
        out.extend(str(x) for x in d.value.astype(str).to_numpy().ravel())
    return [t for t in out if not t.startswith(_D2_PROXY_CAPTION_HEAD)]


@pytest.mark.slow
class TestRealStreamlitRender:

    @pytest.mark.parametrize("target", sorted(_APP_TARGETS))
    def test_proxy_note_rendered_and_only_difference(self, target):
        p = _app_markdown(target, _proxy("strong"))
        r = _app_markdown(target, _real("strong"))
        assert any(NOTE in t for t in p), f"{target}: 代理時畫面上找不到註記"
        assert not any(NOTE in t for t in r), f"{target}: 非代理卻出現註記"
        assert [t.replace(NOTE, "") for t in p] == r, f"{target}: 註記以外還有其他差異"

    def test_section7_card_itself_is_labelled(self):
        """§七 同頁 KPI 卡本來就有註記 → 上一條的「找得到註記」對 long 不夠具體，這裡點名那張卡。"""
        p = [t for t in _app_markdown("long", _proxy("strong")) if "🎯 策略3" in t and "M1B-M2=" in t]
        r = [t for t in _app_markdown("long", _real("strong")) if "🎯 策略3" in t and "M1B-M2=" in t]
        assert len(p) == len(r) == 1, (p, r)
        assert f"M1B-M2=+3.10%{NOTE} 正值" in p[0], p[0]
        assert f">{_ORIG_S7['strong']}</span>" in r[0], r[0]

    def test_macro_v2_table_and_bucket_summary_are_labelled(self):
        """總經 v2 真 render：總表儲存格與桶摘要「最差項」兩處都帶註記。"""
        p = _app_markdown("macro_v2", _proxy("strong"))
        want = f"{_ORIG_V2_VALUE['strong']}{NOTE}"
        assert want in p, "總表（st.dataframe）「目前值」沒有註記"
        assert any(f"M1B-M2 資金動能 {want}" in t for t in p), "桶摘要「最差項」沒有註記"
