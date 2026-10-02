"""SEC-2：今天／找標的／查一檔／憑什麼 四頁，把例外原文畫上畫面的出口一律先過 `scrub_secrets`。

背景：「💼 我的持股」已實證 secrets.toml 原文可經 `repr(e)` 上紅卡（批次 B，
`tests/test_v2_silent_fail_b11_hold_misc.py`）。本檔守其餘四頁的同型出口：

  頁 1 `page_today`：`_error_why`；市場位階卡的 `upstream_error_why`；狀態列／三欄摘要「位階」格
      （經 `tab_today.upstream_error_why`，秘密在交出去前洗）；L4 標籤載不進來的三個 facts ＋ `st.warning`；
      頁首舊報告畫不出來的 `st.error`；原地重抓的 `st.write` 進度與報告的失敗／逐來源明細。
  頁 2 `page_find`：`_error_why`；結果卡 `aux_errors`（缺貨／RS／跨季／位階／命中摘要的 `repr(e)`）；
      CSV 匯出的 `st.caption`；熱力圖／泡泡圖的 `st.error`。
  頁 3 `page_inspect`：`_error_why`；估值 `val.msg`（facts ＋ why）；籌碼 `miss_reason`（facts ＋ why）；
      獲利 `gap_why`；葉2 批次表「明細」。
  頁 5 `page_why`：`_error_why`；工程師版 Fetcher 監控表「錯誤」欄。

每個出口三件事：(a) 餵秘密 → 畫面字串不含秘密；(b) 一般訊息 → 與「拔掉清洗」的版本逐字相同；
(c) 突變：拔掉那一處清洗（`_mutant` 載一份改過的模組）→ 秘密回到畫面上（轉紅）。
"""
from __future__ import annotations

import contextlib
import functools
import importlib.util
import pathlib
import sys
import types
from unittest import mock

import pytest

import src.services.macro_refresh_service as RS
from shared.macro_buckets import BUCKET_DANGER_SPECS
from shared.secret_scrub import MASK, scrub_secrets
from shared.ui_state import UI_FAILED, UI_LIVE
from src.ui.views import page_find as PF
from src.ui.views import page_inspect as PI
from src.ui.views import page_today as PT
from src.ui.views import page_why as PW

_SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"


def _leak_cases() -> dict[str, tuple[BaseException, tuple[str, ...]]]:
    """(會被畫上畫面的例外, 洗完後 ⛔ 不得出現的片段)。每次呼叫都是新物件（可以拿去 raise）。"""
    return {
        # secrets.toml 解碼失敗：repr 帶出整份檔案原文（批次 B 的實證）
        "secrets_file": (UnicodeDecodeError("utf-8", b'client_secret = "S3CR3T_A"\n\xff\n', 28, 29,
                                            "invalid start byte"), ("S3CR3T_A", "client_secret")),
        # token 在 URL query
        "token": (RuntimeError("401 Client Error: Unauthorized for url: https://api.finmindtrade.com"
                               "/api/v4/data?dataset=TaiwanStockPrice&token=S3CR3T_B"), ("S3CR3T_B",)),
        # Sheet 網址（識別碼）
        "sheet_url": (RuntimeError(f"APIError: https://docs.google.com/spreadsheets/d/{_SHEET_ID}/edit"
                                   " is not shared"), (_SHEET_ID,)),
        # 檔案系統路徑（使用者名、目錄）。⚠️ `FileNotFoundError(2, msg, path)` 的 **repr 不含路徑**
        #    （只有 `str()` 有）—— 用單一引數的形狀，repr 才真的帶出路徑。
        "path": (FileNotFoundError("[Errno 2] No such file or directory: "
                                   "'/home/alice/app/.streamlit/secrets.toml'"), ("alice", ".streamlit")),
    }


_LEAK_IDS = sorted(_leak_cases())


def _leak(case: str) -> tuple[BaseException, str, tuple[str, ...]]:
    exc, gone = _leak_cases()[case]
    return exc, repr(exc), gone


#: 一般訊息（HTTP 狀態、代號、日期、百分比、中文說明）：⛔ 一個字都不能被動到。
_PLAIN_EXCS = {
    "http": lambda: RuntimeError("HTTPError 502"),
    "code": lambda: KeyError("2330"),
    "cn": lambda: TimeoutError("讀取逾時 20s：報酬 +12.5%，2026/09/26 14:30，元/股"),
    "quota": lambda: ValueError("quota: 60 per minute"),
    "conn": lambda: ConnectionError("HTTPSConnectionPool(host='api.finmindtrade.com', port=443): "
                                    "Read timed out. (read timeout=20)"),
}
_PLAIN_IDS = sorted(_PLAIN_EXCS)
#: 同一行兩個遮罩（Markdown 會把成對的 `***` 吃成粗斜體記號）。
_TWO_MASKS = RuntimeError("403 for url: https://x.googleapis.com/v1?key=AIzaSyABCDEFGHIJKLMN&token=zzz")


def _assert_clean(text: str, gone: tuple[str, ...]) -> None:
    for g in gone:
        assert g not in text, f"秘密片段 {g!r} 上了畫面：{text[:400]}"


def _assert_leaks(text: str, gone: tuple[str, ...]) -> None:
    assert any(g in text for g in gone), "突變版沒有漏 —— 這個突變點不承重？"


# ══════════════════════════════════════════════════════════════════
# 突變工具（同 `test_v2_silent_fail_b11_hold_misc._mutant`）
# ══════════════════════════════════════════════════════════════════
def _load_mutant(mod: types.ModuleType, pairs: tuple[tuple[str, str], ...]) -> types.ModuleType:
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_sec2_{mod.__name__.rsplit('.', 1)[-1]}_{abs(hash(pairs))}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


@functools.lru_cache(maxsize=None)
def _mutant(modname: str, *keys: str) -> types.ModuleType:
    mod = {"PT": PT, "PF": PF, "PI": PI, "PW": PW}[modname]
    return _load_mutant(mod, tuple(_MUT[modname][k] for k in keys))


def _bare(modname: str) -> types.ModuleType:
    """拔掉本批**全部**清洗的版本 —— 一般訊息的對照組（＝ 修前的行為）。"""
    return _mutant(modname, *sorted(_MUT[modname]))


_WHY_SCRUB = ("scrub_state_glyphs(scrub_secrets(error) if error else error)", "scrub_state_glyphs(error)")
_MUT: dict[str, dict[str, tuple[str, str]]] = {
    "PT": {
        "why": _WHY_SCRUB,
        "md": ('return scrub_secrets(text).replace(SECRET_MASK, "\\\\*" * len(SECRET_MASK))',
               "return str(text)"),
        "l4_thr": ('("門檻帶", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`")',
                   '("門檻帶", f"{L4_LABEL_UNAVAILABLE}`{l4_error}`")'),
        "l4_lamp": ('(0, ("燈號", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`"))',
                    '(0, ("燈號", f"{L4_LABEL_UNAVAILABLE}`{l4_error}`"))'),
        "l4_danger": ('(("燈號", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`"),)',
                      '(("燈號", f"{L4_LABEL_UNAVAILABLE}`{l4_error}`"),)'),
        "regime": ("upstream_error_why(scrub_secrets(regime_error))", "upstream_error_why(regime_error)"),
        "blocks": ("macro_error=scrub_secrets(_regime_err) or None", "macro_error=_regime_err or None"),
        "statusbar": ("build_status_bar_cards(_regime, error=scrub_secrets(_regime_err) or None)",
                      "build_status_bar_cards(_regime, error=_regime_err or None)"),
        "old_report": ("原始例外：`{scrub_secrets(repr(_e))}`", "原始例外：`{_e!r}`"),
        "l4_warn": ("`{scrub_secrets(_l4_err)}`", "`{_l4_err}`"),
        "on_event": ('_detail = _md_scrub(getattr(result, "detail", "") or "")',
                     '_detail = getattr(result, "detail", "") or ""'),
        "failures": ("{_md_scrub(_f)}", "{_f}"),
        "src_detail": ("{_md_scrub(_r.detail)}", "{_r.detail}"),
    },
    "PF": {
        "why": _WHY_SCRUB,
        "aux": ("_facts.extend((_k, scrub_secrets(_v)) for _k, _v in result.aux_errors)",
                "_facts.extend(result.aux_errors)"),
        "csv": ('_err = scrub_state_glyphs(scrub_secrets(repr(_e)))[0].replace("*", "\\\\*")\n'
                '        st.caption(',
                "_err = scrub_state_glyphs(repr(_e))[0]\n        st.caption("),
        "heat": ('_err = scrub_state_glyphs(scrub_secrets(repr(_e)))[0].replace("*", "\\\\*")\n'
                 '            st.error(\n                "🔴 熱力圖',
                 "_err = scrub_state_glyphs(repr(_e))[0]\n"
                 '            st.error(\n                "🔴 熱力圖'),
        "bubble": ('_err = scrub_state_glyphs(scrub_secrets(repr(_e)))[0].replace("*", "\\\\*")\n'
                   '            st.error(\n                "🔴 泡泡圖',
                   "_err = scrub_state_glyphs(repr(_e))[0]\n"
                   '            st.error(\n                "🔴 泡泡圖'),
    },
    "PI": {
        "why": _WHY_SCRUB,
        "msg_fact": ('("上游說明", scrub_secrets(val.msg))', '("上游說明", val.msg)'),
        "msg_why": ("scrub_state_glyphs(scrub_secrets(val.msg))", "scrub_state_glyphs(val.msg)"),
        "chips_fact": ('("上游說明", scrub_secrets(chips.miss_reason))', '("上游說明", chips.miss_reason)'),
        "chips_why": ("scrub_state_glyphs(scrub_secrets(chips.miss_reason))",
                      "scrub_state_glyphs(chips.miss_reason)"),
        "gap": ("scrub_state_glyphs(scrub_secrets(prof.gap_why))", "scrub_state_glyphs(prof.gap_why)"),
        "batch": ("scrub_state_glyphs(scrub_secrets(_r.error))", "scrub_state_glyphs(_r.error)"),
    },
    "PW": {
        "why": _WHY_SCRUB,
        "engineer": ('"錯誤": scrub_secrets(_p.error),', '"錯誤": _p.error or "",'),
    },
}


# ══════════════════════════════════════════════════════════════════
# 畫面字串的取法
# ══════════════════════════════════════════════════════════════════
def _tile_text(mod, tile) -> str:
    """頁 1 一張卡上所有看得到的字（卡本體 ＋ facts ＋ v2 卡面 HTML，含「▸ 詳細」）。"""
    return repr(tile) + mod.v2_card_html(tile)


def _built_text(mod, built) -> str:
    """頁 2／3／5 一張卡上所有看得到的字（卡本體 ＋ facts ＋ v2 卡面 HTML）。

    v2 卡面畫不出來時（例：估值灰卡的「為什麼」不是登記過的 L2 原句 → `KeyError`），
    production 走 `_render_one_v2` 的補救紅卡 —— 那張卡的 why 是 `_error_why(SRC_V2_MARKUP, repr(e))`，
    已由各頁 `_error_why` 的測試守住；這裡只記型別名（repr 帶物件位址，兩個模組版本比不齊）。
    """
    try:
        _html = mod.v2_card_html(*built)
    except Exception as _e:  # noqa: BLE001
        _html = f"<v2 補救紅卡：{type(_e).__name__}>"
    return repr(built) + _html


_SAY = ("error", "warning", "caption", "markdown", "write", "info", "success")


def _st_texts(fake) -> list[tuple[str, str]]:
    """假 `st` 收到的每一段**文字**（依呼叫順序；`st.dataframe` 另取）。"""
    out = []
    for c in fake.mock_calls:
        name = c[0].rsplit(".", 1)[-1]
        if name in _SAY and c[1] and isinstance(c[1][0], str):
            out.append((name, c[1][0]))
    return out


def _fake_st(session: dict | None = None):
    fake = mock.MagicMock(name="st")
    fake.session_state = dict(session or {})
    fake.tabs.side_effect = lambda labels: [mock.MagicMock() for _ in labels]
    return fake


def _flat_grid(items, cols=None):
    items = tuple(items)
    return [(items, [contextlib.nullcontext() for _ in items])] if items else []


# ══════════════════════════════════════════════════════════════════
# 頁 1 `page_today`
# ══════════════════════════════════════════════════════════════════
def _live_rec(spec) -> dict:
    return {"wired": True, "discriminative": True, "state": "ok", "value": float(spec.yellow),
            "reason": None, "hit_source": "T"}


def _pt_l4_texts(mod, l4_error: str) -> dict[str, str]:
    """L4 標籤載不進來的三個 facts 出口（燈號中文 ＋ 門檻帶）。"""
    _spec = next(s for s in BUCKET_DANGER_SPECS if mod.has_thresholds(s))
    _ind = mod.build_indicator_tile(_spec.key, _live_rec(_spec), requested=True, error="",
                                    band_label=None, thr_text=None, l4_error=l4_error)
    assert _ind.card.state == UI_LIVE
    _fx = dict(_ind.facts)
    _dz = mod._danger_tile(key="verdict.danger", label="指標危險度", danger=("yellow", "3/16"),
                           danger_error="", danger_requested=True, danger_source=mod.SRC_DANGER,
                           band_zh_color={}, l4_error=l4_error)
    assert _dz.card.state == UI_LIVE
    return {"l4_thr": _fx["門檻帶"], "l4_lamp": _fx["燈號"], "l4_danger": dict(_dz.facts)["燈號"]}


def _pt_verdict(mod, *, alloc_error: str = "", regime_error: str = "") -> dict[str, str]:
    tiles = mod.build_verdict_tiles(alloc=None, alloc_error=alloc_error, danger=None, danger_error="",
                                    danger_requested=False, regime=None, regime_error=regime_error)
    return {t.card.key: _tile_text(mod, t) for t in tiles}


def _pt_drive(mod, monkeypatch_, *, regime_error: str = "", l4_error: str = "",
              old_report_exc: BaseException | None = None) -> tuple[dict[str, str], list]:
    """跑一次整頁 render（無 Streamlit runtime）。回 `({card.key: 卡上文字}, st 收到的文字)`。"""
    with monkeypatch_.context() as monkeypatch:
        _drawn: list = []
        _session = {mod.SS_REFRESH_REPORT: object()} if old_report_exc is not None else {}
        fake = _fake_st(_session)
        monkeypatch.setattr(mod, "st", fake)
        monkeypatch.setattr(mod, "_inject_v2_css", lambda: None)
        monkeypatch.setattr(mod, "_render_update_form", lambda _s: None)
        monkeypatch.setattr(mod, "section_header", lambda *a, **k: None)
        monkeypatch.setattr(mod, "render_note", lambda *a, **k: None)
        monkeypatch.setattr(mod, "load_macro_readout", lambda _s: mod.MacroReadout(requested=False))
        monkeypatch.setattr(mod, "_load_l4_labels", lambda: (None, None, None, l4_error))
        monkeypatch.setattr(mod, "_load_allocation", lambda: (None, ""))
        monkeypatch.setattr(mod, "_load_regime", lambda: (None, regime_error))
        monkeypatch.setattr(mod, "_load_danger", lambda _r: (None, "", ""))
        monkeypatch.setattr(mod, "_load_key_alerts", lambda _s: (None, False, ""))
        monkeypatch.setattr(mod, "_load_lamp_directions", lambda _s=None: {})
        monkeypatch.setattr(mod, "_render_tiles", lambda tiles, cols=None: _drawn.extend(tiles))
        if old_report_exc is not None:
            def _boom(_r):
                raise old_report_exc
            monkeypatch.setattr(mod, "_render_refresh_report", _boom)
        mod.render_page_today()
        texts: dict[str, str] = {}
        for t in _drawn:
            texts[t.card.key] = texts.get(t.card.key, "") + _tile_text(mod, t)
        return texts, _st_texts(fake)


def _pt_report(mod, monkeypatch_, detail: str) -> list[tuple[str, str]]:
    """上一次更新的報告（頁首）：失敗段 ＋ 逐來源明細。"""
    with monkeypatch_.context() as monkeypatch:
        fake = _fake_st()
        monkeypatch.setattr(mod, "st", fake)
        rep = RS.MacroRefreshReport(
            mode=RS.MODE_WARM, started_at="2026-09-26 14:30", elapsed_s=1.5,
            sources=(RS.SourceResult(name="intl", ok=False, detail=detail),),
            steps=(RS.StepResult(name=RS.STEP_APPLY, ok=False, detail=detail),))
        mod._render_refresh_report(rep)
        return _st_texts(fake)


def _pt_on_event(mod, monkeypatch_, detail: str) -> list[tuple[str, str]]:
    """按下更新時 `st.status` 裡逐來源的進度列（`_on_event` → `st.write`）。"""
    with monkeypatch_.context() as monkeypatch:
        fake = _fake_st()
        monkeypatch.setattr(mod, "st", fake)

        def _refresh(*, mode, on_event):
            on_event("source", RS.SourceResult(name="intl", ok=False, detail=detail))
            return RS.MacroRefreshReport(mode=mode, started_at="2026-09-26 14:30", elapsed_s=1.0)
        monkeypatch.setattr(RS, "refresh_macro_now", _refresh)
        mod._run_refresh_now(RS.MODE_WARM)
        return [t for n, t in _st_texts(fake) if n == "write"]


def _join(pairs) -> str:
    return "\n".join(t for _n, t in pairs)


class TestPageToday:
    # ── `_error_why` ────────────────────────────────────────────────
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_error_why(self, case):
        _e, raw, gone = _leak(case)
        why = PT._error_why(PT.SRC_FIVE_BUCKET, raw)
        _assert_clean(why, gone)
        assert why == f"{PT.SRC_FIVE_BUCKET}拋出例外：{scrub_secrets(raw)}"

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_error_why_reaches_a_red_card(self, case):
        _e, raw, gone = _leak(case)
        _assert_clean(_pt_verdict(PT, alloc_error=raw)["verdict.exposure"], gone)

    # ── 市場位階卡（`upstream_error_why`）─────────────────────────────
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_regime_card(self, case):
        _e, raw, gone = _leak(case)
        _assert_clean(_pt_verdict(PT, regime_error=raw)["verdict.regime"], gone)

    # ── 整頁：狀態列「總經」＋ 三欄摘要「位階」＋ 位階卡 ＋ L4 `st.warning` ──────
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_page_render(self, case, monkeypatch):
        _e, raw, gone = _leak(case)
        cards, said = _pt_drive(PT, monkeypatch, regime_error=raw, l4_error=raw)
        for key in ("statusbar.macro", "summary.regime", "verdict.regime"):   # 三張卡吃同一個例外
            _assert_clean(cards[key], gone)
        assert cards["statusbar.macro"].count("拋出例外") >= 1, "前提：狀態列真的畫了紅態原文"
        _warn = [t for n, t in said if n == "warning" and PT.L4_LABEL_UNAVAILABLE in t]
        assert len(_warn) == 1
        _assert_clean(_warn[0], gone)
        for key, text in cards.items():
            if key.startswith("detail."):
                _assert_clean(text, gone)

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_old_report_error(self, case, monkeypatch):
        exc, _raw, gone = _leak(case)
        _c, said = _pt_drive(PT, monkeypatch, old_report_exc=exc)
        _err = [t for n, t in said if n == "error" and "原始例外" in t]
        assert len(_err) == 1
        _assert_clean(_err[0], gone)

    # ── L4 標籤載不進來的三個 facts ─────────────────────────────────
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_l4_facts(self, case):
        _e, raw, gone = _leak(case)
        for where, text in _pt_l4_texts(PT, raw).items():
            _assert_clean(text, gone)
            assert text.startswith(PT.L4_LABEL_UNAVAILABLE), where

    # ── 原地重抓：進度列 ＋ 報告 ─────────────────────────────────────
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_refresh_report(self, case, monkeypatch):
        _e, raw, gone = _leak(case)
        said = _pt_report(PT, monkeypatch, raw)
        _fail = [t for n, t in said if n == "error" and "取不到的來源" in t]
        _each = [t for n, t in said if n == "markdown" and "逐來源結果" in t]
        assert len(_fail) == 1 and len(_each) == 1
        _assert_clean(_fail[0], gone)
        _assert_clean(_each[0], gone)

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_refresh_progress(self, case, monkeypatch):
        _e, raw, gone = _leak(case)
        writes = _pt_on_event(PT, monkeypatch, raw)
        assert len(writes) == 1
        _assert_clean(writes[0], gone)

    def test_a_refresh_masks_are_markdown_escaped_but_bold_is_kept(self, monkeypatch):
        """遮罩 `***` 以 `\\*` 跳脫（不被吃成粗斜體）；報告自帶的 `**粗體**` ⛔ 不跳脫。"""
        detail = f"{repr(_TWO_MASKS)} —— **本報告的成敗判定因此不完整**"
        _fail = [t for n, t in _pt_report(PT, monkeypatch, detail) if n == "error"][0]
        assert "\\*\\*\\*" in _fail and "***" not in _fail.replace("\\*\\*\\*", "")
        assert "**本報告的成敗判定因此不完整**" in _fail
        assert "**這一輪有取不到的來源 / 跑不完的步驟**" in _fail

    # ── (b) 一般訊息：與修前（拔掉全部清洗）逐字相同 ───────────────────
    @pytest.mark.parametrize("plain", _PLAIN_IDS)
    def test_b_plain_messages_unchanged(self, plain, monkeypatch):
        raw = repr(_PLAIN_EXCS[plain]())
        bare = _bare("PT")
        assert PT._error_why(PT.SRC_FIVE_BUCKET, raw) == bare._error_why(bare.SRC_FIVE_BUCKET, raw)
        assert _pt_verdict(PT, alloc_error=raw, regime_error=raw) == _pt_verdict(
            bare, alloc_error=raw, regime_error=raw)
        assert _pt_l4_texts(PT, raw) == _pt_l4_texts(bare, raw)
        assert _pt_drive(PT, monkeypatch, regime_error=raw, l4_error=raw) == _pt_drive(
            bare, monkeypatch, regime_error=raw, l4_error=raw)
        assert _pt_drive(PT, monkeypatch, old_report_exc=_PLAIN_EXCS[plain]()) == _pt_drive(
            bare, monkeypatch, old_report_exc=_PLAIN_EXCS[plain]())
        detail = f"{raw} —— **本報告的成敗判定因此不完整**"
        assert _pt_report(PT, monkeypatch, detail) == _pt_report(bare, monkeypatch, detail)
        assert _pt_on_event(PT, monkeypatch, detail) == _pt_on_event(bare, monkeypatch, detail)

    def test_b_empty_error_is_still_the_no_message_text(self):
        assert PT._error_why(PT.SRC_FIVE_BUCKET, "") == f"{PT.SRC_FIVE_BUCKET}拋出例外：（上游沒有給訊息）"

    # ── (c) 突變：每個出口拔掉那一處清洗 → 秘密回到畫面 ────────────────
    def test_c_error_why(self):
        _e, raw, gone = _leak("secrets_file")
        m = _mutant("PT", "why")
        _assert_leaks(m._error_why(m.SRC_FIVE_BUCKET, raw), gone)
        _assert_leaks(_pt_verdict(m, alloc_error=raw)["verdict.exposure"], gone)

    def test_c_regime_card(self):
        _e, raw, gone = _leak("secrets_file")
        _assert_leaks(_pt_verdict(_mutant("PT", "regime"), regime_error=raw)["verdict.regime"], gone)

    @pytest.mark.parametrize("key,card", [("statusbar", "statusbar.macro"), ("blocks", "summary.regime")])
    def test_c_tab_today_handoff(self, key, card, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        cards, _s = _pt_drive(_mutant("PT", key), monkeypatch, regime_error=raw)
        _assert_leaks(cards[card], gone)

    def test_c_l4_warning(self, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        _c, said = _pt_drive(_mutant("PT", "l4_warn"), monkeypatch, l4_error=raw)
        _assert_leaks(_join(p for p in said if p[0] == "warning"), gone)

    def test_c_old_report_error(self, monkeypatch):
        exc, _raw, gone = _leak("secrets_file")
        _c, said = _pt_drive(_mutant("PT", "old_report"), monkeypatch, old_report_exc=exc)
        _assert_leaks(_join(p for p in said if p[0] == "error"), gone)

    @pytest.mark.parametrize("key", ["l4_thr", "l4_lamp", "l4_danger"])
    def test_c_l4_facts(self, key):
        _e, raw, gone = _leak("secrets_file")
        _assert_leaks(_pt_l4_texts(_mutant("PT", key), raw)[key], gone)

    def test_c_refresh_failures(self, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        said = _pt_report(_mutant("PT", "failures"), monkeypatch, raw)
        _assert_leaks(_join(p for p in said if p[0] == "error"), gone)
        _assert_clean(_join(p for p in said if p[0] == "markdown"), gone)

    def test_c_refresh_source_detail(self, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        said = _pt_report(_mutant("PT", "src_detail"), monkeypatch, raw)
        _assert_leaks(_join(p for p in said if p[0] == "markdown"), gone)
        _assert_clean(_join(p for p in said if p[0] == "error"), gone)

    def test_c_refresh_progress(self, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        m = _load_mutant(PT, (_MUT["PT"]["on_event"],))
        _assert_leaks(_join(("write", t) for t in _pt_on_event(m, monkeypatch, raw)), gone)

    def test_c_md_helper_without_escape_lets_markdown_eat_the_masks(self, monkeypatch):
        m = _load_mutant(PT, (('return scrub_secrets(text).replace(SECRET_MASK, "\\\\*" * len(SECRET_MASK))',
                               "return scrub_secrets(text)"),))
        _fail = [t for n, t in _pt_report(m, monkeypatch, repr(_TWO_MASKS)) if n == "error"][0]
        assert "\\*\\*\\*" not in _fail and MASK in _fail


# ══════════════════════════════════════════════════════════════════
# 頁 2 `page_find`
# ══════════════════════════════════════════════════════════════════
def _pf_cards(mod, raw: str) -> dict[str, str]:
    """所有吃例外字串的卡：熱力圖紅、泡泡圖紅、表單紅、結果卡（中止紅 ＋ live 的 aux facts）。"""
    _req = mod.ScreenRequest(submitted=True, factors=("shortage", "rs_leader"))
    _aux = (("缺貨", f"失敗，該因子不計入綜合分：{raw}"),
            ("總經位階", f"取不到，空頭濾網未套用：{raw}"),
            ("因子命中摘要", f"不可用：{raw}"))
    return {
        "heatmap": _built_text(mod, mod.build_heatmap_card(mod.HeatmapReadout(requested=True, error=raw))),
        "flow": _built_text(mod, mod.build_sector_flow_card(
            mod.SectorFlowReadout(requested=True, error=raw))),
        "form": _built_text(mod, (mod.build_form_unavailable_card(raw), ())),
        "aborted": _built_text(mod, mod.build_screen_result_card(
            mod.ScreenResult(requested=True, error=raw), _req)),
        "aux_live": _built_text(mod, mod.build_screen_result_card(
            mod.ScreenResult(requested=True, rows=3, survivors_n=10, aux_errors=_aux), _req)),
    }


class _BadFrame:
    def __init__(self, exc):
        self._exc = exc

    def to_csv(self, **_k):
        raise self._exc


def _pf_csv(mod, monkeypatch_, exc) -> list[tuple[str, str]]:
    with monkeypatch_.context() as monkeypatch:
        fake = _fake_st()
        monkeypatch.setattr(mod, "st", fake)
        monkeypatch.setattr(mod, "section_header", lambda *a, **k: None)
        monkeypatch.setattr(mod, "load_factor_labels", lambda: ({"缺貨": "shortage"}, ""))
        monkeypatch.setattr(mod, "_render_screen_form", lambda _l: False)
        monkeypatch.setattr(mod, "applied_screen_request", lambda _s: mod.ScreenRequest(submitted=True))
        monkeypatch.setattr(mod, "load_screen_result", lambda _r: mod.ScreenResult(
            requested=True, rows=1, survivors_n=1, df=_BadFrame(exc)))
        monkeypatch.setattr(mod, "_render_one", lambda *a, **k: None)
        mod._render_screen_leaf({})
        return [p for p in _st_texts(fake) if p[0] == "caption" and "CSV" in p[1]]


def _pf_map(mod, monkeypatch_, exc) -> list[tuple[str, str]]:
    with monkeypatch_.context() as monkeypatch:
        import src.ui.render.sector_flow_render as SFR
        fake = _fake_st()
        fake.button.return_value = False
        fake.plotly_chart.side_effect = exc
        monkeypatch.setattr(mod, "st", fake)
        monkeypatch.setattr(mod, "section_header", lambda *a, **k: None)
        monkeypatch.setattr(mod, "grid", _flat_grid)
        monkeypatch.setattr(mod, "map_requested", lambda _s: True)
        monkeypatch.setattr(mod, "load_heatmap", lambda *, requested: mod.HeatmapReadout(
            requested=True, figure=object(), sectors_n=1, fetched_n=1, complete=True, any_data=True))
        monkeypatch.setattr(mod, "load_sector_flow", lambda _s, *, requested: mod.SectorFlowReadout(
            requested=True, ok=True, sectors=({"sector": "半導體", "quadrant": "領漲"},),
            quadrant_counts=(("領漲", 1),)))
        monkeypatch.setattr(mod, "_render_one", lambda *a, **k: None)
        monkeypatch.setattr(SFR, "build_sector_flow_figure", lambda *a, **k: object())
        mod._render_map_leaf({})
        return [p for p in _st_texts(fake) if p[0] == "error"]


class TestPageFind:
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_error_why(self, case):
        _e, raw, gone = _leak(case)
        why = PF._error_why(PF.SRC_HEATMAP, raw)
        _assert_clean(why, gone)
        assert why == f"{PF.SRC_HEATMAP}拋出例外：{scrub_secrets(raw)}"

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_cards(self, case):
        _e, raw, gone = _leak(case)
        for key, text in _pf_cards(PF, raw).items():
            _assert_clean(text, gone)

    def test_a_aux_rows_are_on_the_live_card(self):
        _e, raw, gone = _leak("path")
        card, facts = PF.build_screen_result_card(
            PF.ScreenResult(requested=True, rows=3, survivors_n=10,
                            aux_errors=(("缺貨", f"失敗，該因子不計入綜合分：{raw}"),)),
            PF.ScreenRequest(submitted=True, factors=("rs_leader",)))
        assert card.state == UI_LIVE
        assert dict(facts)["缺貨"] == f"失敗，該因子不計入綜合分：{scrub_secrets(raw)}"
        assert "***/secrets.toml" in dict(facts)["缺貨"]

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_csv_caption(self, case, monkeypatch):
        exc, _raw, gone = _leak(case)
        said = _pf_csv(PF, monkeypatch, exc)
        assert len(said) == 1
        _assert_clean(said[0][1], gone)

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_heatmap_and_bubble_errors(self, case, monkeypatch):
        exc, _raw, gone = _leak(case)
        said = _pf_map(PF, monkeypatch, exc)
        assert [("熱力圖" in t, "泡泡圖" in t) for _n, t in said] == [(True, False), (False, True)]
        for _n, t in said:
            _assert_clean(t, gone)

    def test_a_markdown_exits_escape_the_masks(self, monkeypatch):
        """`st.caption`／`st.error` 吃 Markdown：遮罩 `***` 以 `\\*` 跳脫（同 L4 `station_cards`）。"""
        for text in [t for _n, t in _pf_csv(PF, monkeypatch, _TWO_MASKS)] + [
                t for _n, t in _pf_map(PF, monkeypatch, _TWO_MASKS)]:
            assert "key=\\*\\*\\*&token=\\*\\*\\*" in text, text

    @pytest.mark.parametrize("plain", _PLAIN_IDS)
    def test_b_plain_messages_unchanged(self, plain, monkeypatch):
        raw = repr(_PLAIN_EXCS[plain]())
        bare = _bare("PF")
        assert PF._error_why(PF.SRC_HEATMAP, raw) == bare._error_why(bare.SRC_HEATMAP, raw)
        assert _pf_cards(PF, raw) == _pf_cards(bare, raw)
        assert _pf_csv(PF, monkeypatch, _PLAIN_EXCS[plain]()) == _pf_csv(bare, monkeypatch, _PLAIN_EXCS[plain]())
        assert _pf_map(PF, monkeypatch, _PLAIN_EXCS[plain]()) == _pf_map(bare, monkeypatch, _PLAIN_EXCS[plain]())

    def test_c_error_why(self):
        _e, raw, gone = _leak("secrets_file")
        m = _mutant("PF", "why")
        _assert_leaks(m._error_why(m.SRC_HEATMAP, raw), gone)
        _assert_leaks(_pf_cards(m, raw)["heatmap"], gone)

    def test_c_aux(self):
        _e, raw, gone = _leak("secrets_file")
        m = _mutant("PF", "aux")
        _assert_leaks(_pf_cards(m, raw)["aux_live"], gone)

    def test_c_csv(self, monkeypatch):
        exc, _raw, gone = _leak("secrets_file")
        _assert_leaks(_join(_pf_csv(_mutant("PF", "csv"), monkeypatch, exc)), gone)

    @pytest.mark.parametrize("key,word", [("heat", "熱力圖"), ("bubble", "泡泡圖")])
    def test_c_map(self, key, word, monkeypatch):
        m = _mutant("PF", key)
        said = _pf_map(m, monkeypatch, _leak("secrets_file")[0])
        _gone = _leak("secrets_file")[2]
        _assert_leaks(_join(p for p in said if word in p[1]), _gone)
        _assert_clean(_join(p for p in said if word not in p[1]), _gone)


# ══════════════════════════════════════════════════════════════════
# 頁 3 `page_inspect`
# ══════════════════════════════════════════════════════════════════
def _pi_texts(mod, raw: str) -> dict[str, str]:
    _val_empty = mod.build_valuation_card(mod.ValuationReadout(
        requested=True, msg=raw, source="FinMind", years_n=5, price=100.0))
    _chips_empty = mod.build_chips_card(mod.ChipsView(
        requested=True, signal="⚫ 計算失敗", rows=120, days_loaded=120, miss_reason=raw))
    _prof = mod.build_profit_cards(mod.ProfitabilityReadout(requested=True, gap_why=raw))
    return {
        "kind_red": _built_text(mod, mod.build_kind_card(
            mod.KindVerdict(requested=True, code="2330", error=raw),
            mod.InspectRequest(submitted=True, ticker="2330"))),
        "val_red": _built_text(mod, mod.build_valuation_card(
            mod.ValuationReadout(requested=True, error=mod._error_why(mod.SRC_DIVIDENDS, raw)))),
        "msg_fact": dict(_val_empty[1])["上游說明"],
        "msg_why": _val_empty[0].note.why,
        "chips_fact": dict(_chips_empty[1])["上游說明"],
        "chips_why": _chips_empty[0].note.why,
        "gap": dict(_prof[0][1])["缺漏原因"],
        "cards": "".join(_built_text(mod, b) for b in (_val_empty, _chips_empty) + tuple(_prof)),
    }


def _pi_batch(mod, monkeypatch_, raw: str) -> str:
    with monkeypatch_.context() as monkeypatch:
        fake = _fake_st()
        monkeypatch.setattr(mod, "st", fake)
        monkeypatch.setattr(mod, "section_header", lambda *a, **k: None)
        monkeypatch.setattr(mod, "_render_batch_form", lambda: False)
        monkeypatch.setattr(mod, "applied_batch_request", lambda _s: mod.BatchRequest(
            submitted=True, tickers=("2330", "0056")))
        monkeypatch.setattr(mod, "load_batch_rows", lambda _r: mod.BatchReadout(requested=True, rows=(
            mod.BatchRow(code="2330", error=raw),
            mod.BatchRow(code="0056", kind="etf", kind_label="ETF", is_etf=True,
                         metrics=(("殖利率", "5.2%"),)))))
        monkeypatch.setattr(mod, "_render_one", lambda *a, **k: None)
        mod._render_batch_leaf({})
        frames = [c for c in fake.mock_calls if c[0].rsplit(".", 1)[-1] == "dataframe"]
        assert len(frames) == 1
        rows = {r["代碼"]: r for r in frames[0][1][0]}
        assert rows["2330"]["狀態"] == "失敗"
        return rows["2330"]["明細"]


class TestPageInspect:
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_error_why(self, case):
        _e, raw, gone = _leak(case)
        for verb in ("拋出例外", "回報失敗"):
            why = PI._error_why(PI.SRC_CHIPS, raw, verb=verb)
            _assert_clean(why, gone)
            assert why == f"{PI.SRC_CHIPS}{verb}：{scrub_secrets(raw)}"

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_cards(self, case):
        _e, raw, gone = _leak(case)
        for key, text in _pi_texts(PI, raw).items():
            _assert_clean(text, gone)

    def test_a_state_premises(self):
        """前提：估值／籌碼那兩張是**灰**態（走 `msg`／`miss_reason` 那一支 why），不是紅。"""
        _e, raw, _g = _leak("path")
        _v = PI.build_valuation_card(PI.ValuationReadout(
            requested=True, msg=raw, source="FinMind", years_n=5, price=100.0))
        _c = PI.build_chips_card(PI.ChipsView(
            requested=True, signal="⚫ 計算失敗", rows=120, days_loaded=120, miss_reason=raw))
        assert _v[0].state not in (UI_LIVE, UI_FAILED) and _c[0].state not in (UI_LIVE, UI_FAILED)
        assert "***/secrets.toml" in _v[0].note.why and "***/secrets.toml" in _c[0].note.why

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_batch_table(self, case, monkeypatch):
        _e, raw, gone = _leak(case)
        _assert_clean(_pi_batch(PI, monkeypatch, raw), gone)

    @pytest.mark.parametrize("plain", _PLAIN_IDS)
    def test_b_plain_messages_unchanged(self, plain, monkeypatch):
        raw = repr(_PLAIN_EXCS[plain]())
        bare = _bare("PI")
        assert PI._error_why(PI.SRC_CHIPS, raw) == bare._error_why(bare.SRC_CHIPS, raw)
        assert _pi_texts(PI, raw) == _pi_texts(bare, raw)
        assert _pi_batch(PI, monkeypatch, raw) == _pi_batch(bare, monkeypatch, raw)

    def test_b_l0_chips_reasons_unchanged(self):
        for reason in ("df資料不足", "df缺法人/量欄", "df法人欄全為0", "成交量為0"):
            assert _pi_texts(PI, reason)["chips_fact"] == reason

    def test_c_error_why(self):
        _e, raw, gone = _leak("secrets_file")
        m = _mutant("PI", "why")
        _assert_leaks(m._error_why(m.SRC_CHIPS, raw), gone)
        _assert_leaks(_pi_texts(m, raw)["kind_red"], gone)

    @pytest.mark.parametrize("key", ["msg_fact", "msg_why", "chips_fact", "chips_why", "gap"])
    def test_c_card_exits(self, key):
        _e, raw, gone = _leak("secrets_file")
        texts = _pi_texts(_mutant("PI", key), raw)
        _assert_leaks(texts[key], gone)
        for other in ("msg_fact", "msg_why", "chips_fact", "chips_why", "gap"):
            if other != key:
                _assert_clean(texts[other], gone)

    def test_c_batch(self, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        _assert_leaks(_pi_batch(_mutant("PI", "batch"), monkeypatch, raw), gone)


# ══════════════════════════════════════════════════════════════════
# 頁 5 `page_why`
# ══════════════════════════════════════════════════════════════════
def _pw_cards(mod, raw: str) -> dict[str, str]:
    _probe = mod.probe_from_entry("fetch_x", {"last_status": mod.STATUS_FAILED, "last_error": raw,
                                              "category": "macro"})
    return {
        "source": _built_text(mod, mod.build_source_card(_probe)),
        "qa": _built_text(mod, mod.build_qa_card(mod.QaReadout(asked=True, error=raw))),
    }


def _pw_engineer(mod, monkeypatch_, raw: str) -> str:
    with monkeypatch_.context() as monkeypatch:
        fake = _fake_st()
        fake.checkbox.return_value = True
        monkeypatch.setattr(mod, "st", fake)
        monkeypatch.setattr(mod, "_render_one", lambda *a, **k: None)
        monkeypatch.setattr(mod, "_render_row", lambda *a, **k: None)
        monkeypatch.setattr(mod, "load_sources", lambda: mod.SourceScan(scanned=True, probes=(
            mod.probe_from_entry("fetch_x", {"last_status": mod.STATUS_FAILED, "last_error": raw}),
            mod.probe_from_entry("fetch_y", {"last_status": mod.STATUS_OK}))))
        mod._render_engineer_block()
        frames = [c for c in fake.mock_calls if c[0].rsplit(".", 1)[-1] == "dataframe"]
        assert len(frames) == 1
        rows = {r["fetcher"]: r for r in frames[0][1][0]}
        assert rows["fetch_y"]["錯誤"] == ""
        return rows["fetch_x"]["錯誤"]


class TestPageWhy:
    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_error_why(self, case):
        _e, raw, gone = _leak(case)
        why = PW._error_why(PW.SRC_MONITOR, raw)
        _assert_clean(why, gone)
        assert why == f"{PW.SRC_MONITOR}拋出例外：{scrub_secrets(raw)}"

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_cards(self, case):
        _e, raw, gone = _leak(case)
        for key, text in _pw_cards(PW, raw).items():
            _assert_clean(text, gone)

    @pytest.mark.parametrize("case", _LEAK_IDS)
    def test_a_engineer_table(self, case, monkeypatch):
        _e, raw, gone = _leak(case)
        _assert_clean(_pw_engineer(PW, monkeypatch, raw), gone)

    def test_a_reason_is_l0_text_not_scrubbed(self):
        """`_clean_reason` 吃的是 L0 規格表的原因欄（常數文字）與本頁自組的契約漂移句 —— ⛔ 不洗。"""
        import inspect
        assert "scrub_secrets" not in inspect.getsource(PW._clean_reason)

    @pytest.mark.parametrize("plain", _PLAIN_IDS)
    def test_b_plain_messages_unchanged(self, plain, monkeypatch):
        raw = repr(_PLAIN_EXCS[plain]())
        bare = _bare("PW")
        assert PW._error_why(PW.SRC_MONITOR, raw) == bare._error_why(bare.SRC_MONITOR, raw)
        assert _pw_cards(PW, raw) == _pw_cards(bare, raw)
        assert _pw_engineer(PW, monkeypatch, raw) == _pw_engineer(bare, monkeypatch, raw) == raw

    def test_c_error_why(self):
        _e, raw, gone = _leak("secrets_file")
        m = _mutant("PW", "why")
        _assert_leaks(m._error_why(m.SRC_MONITOR, raw), gone)
        _assert_leaks(_pw_cards(m, raw)["source"], gone)
        _assert_leaks(_pw_cards(m, raw)["qa"], gone)

    def test_c_engineer(self, monkeypatch):
        _e, raw, gone = _leak("secrets_file")
        _assert_leaks(_pw_engineer(_mutant("PW", "engineer"), monkeypatch, raw), gone)


# ══════════════════════════════════════════════════════════════════
# 共通：遮罩沿用 `***`、⛔ 不新增任何使用者可見文案
# ══════════════════════════════════════════════════════════════════
def test_every_mutation_point_is_present_exactly_once():
    for modname, pairs in _MUT.items():
        mod = {"PT": PT, "PF": PF, "PI": PI, "PW": PW}[modname]
        src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        for key, (old, _new) in pairs.items():
            assert src.count(old) == 1, (modname, key)


def test_no_new_visible_words():
    """洗過的字串只會少字、多 `***`（與 L4 的 `\\*` 跳脫）—— ⛔ 不帶任何新說明文字。"""
    for case in _LEAK_IDS:
        _e, raw, _g = _leak(case)
        for out in (PT._error_why("", raw), PF._error_why("", raw), PI._error_why("", raw),
                    PW._error_why("", raw)):
            assert set(out.replace(MASK, "")) <= set("拋出例外：" + raw), out


# ══════════════════════════════════════════════════════════════════
# SEC-r8：`today` 反引號內的出口「⛔ 不跳脫遮罩」—— 行為斷言（原本只有錨點字串檢查）
# ══════════════════════════════════════════════════════════════════
#: 五個出口都把洗過的例外包在行內程式碼（反引號）裡。Markdown 在反引號內 ⛔ 不處理 `*`，
#: 所以這裡**不該**像 `_md_scrub` 那樣把遮罩跳成 `\*\*\*` —— 跳了反而會把反斜線字面印出來。
#: `test_every_mutation_point_is_present_exactly_once` 只證明那串原始碼還在；本段證明**畫出來的字**：
#: (1) 反引號內恰為 `scrub_secrets(raw)`；(2) 遮罩原樣 `***`、全部落在反引號內；(3) 沒有 `\*`。
_SEC_R8_RAW = repr(_TWO_MASKS)


def _assert_backtick_exit(text: str, raw: str) -> None:
    """出口字串以 `` `{scrub_secrets(raw)}` `` 收尾（前綴標籤本身可能也有反引號，只看最後一段）。"""
    want = scrub_secrets(raw)
    assert want.count(MASK) >= 2 and "`" not in want, "前提：樣本真的有兩個遮罩、且不含反引號"
    parts = text.split("`")
    assert len(parts) % 2 == 1 and parts[-1] == "", f"反引號不成對或不在結尾：{text!r}"
    assert parts[-2] == want, (parts[-2], want)
    assert "\\*" not in text, f"反引號內的遮罩被跳脫了（會把 \\* 字面印出來）：{text!r}"
    outside = "".join(parts[:-2][0::2])
    assert MASK not in outside, f"遮罩跑到反引號外（會被 Markdown 吃成粗斜體）：{text!r}"


def _pt_sec_r8_texts(mod, monkeypatch_) -> dict[str, str]:
    """五個反引號出口各自畫出的字。"""
    _c, said = _pt_drive(mod, monkeypatch_, l4_error=_SEC_R8_RAW)
    warn = [t for n, t in said if n == "warning" and mod.L4_LABEL_UNAVAILABLE in t]
    _c2, said2 = _pt_drive(mod, monkeypatch_, old_report_exc=RuntimeError(str(_TWO_MASKS)))
    err = [t for n, t in said2 if n == "error" and "原始例外" in t]
    assert len(warn) == 1 and len(err) == 1, (warn, err)
    return {"l4_warn": warn[0], "old_report": err[0], **_pt_l4_texts(mod, _SEC_R8_RAW)}


#: 把五個反引號出口改成 `_md_scrub`（整個「跳脫遮罩」的選擇翻過來）的突變。
_SEC_R8_MD_MUT = (
    ("原始例外：`{scrub_secrets(repr(_e))}`", "原始例外：`{_md_scrub(repr(_e))}`"),
    ('st.warning(f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(_l4_err)}`"',
     'st.warning(f"{L4_LABEL_UNAVAILABLE}`{_md_scrub(_l4_err)}`"'),
    ('("門檻帶", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`")',
     '("門檻帶", f"{L4_LABEL_UNAVAILABLE}`{_md_scrub(l4_error)}`")'),
    ('(0, ("燈號", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`"))',
     '(0, ("燈號", f"{L4_LABEL_UNAVAILABLE}`{_md_scrub(l4_error)}`"))'),
    ('(("燈號", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`"),)',
     '(("燈號", f"{L4_LABEL_UNAVAILABLE}`{_md_scrub(l4_error)}`"),)'),
)


class TestSecR8BacktickMasksNotEscaped:
    def test_each_backtick_exit_keeps_masks_literal_inside_backticks(self, monkeypatch):
        texts = _pt_sec_r8_texts(PT, monkeypatch)
        assert set(texts) == {"l4_warn", "old_report", "l4_thr", "l4_lamp", "l4_danger"}
        for where, text in texts.items():
            raw = repr(RuntimeError(str(_TWO_MASKS))) if where == "old_report" else _SEC_R8_RAW
            try:
                _assert_backtick_exit(text, raw)
            except AssertionError as e:
                raise AssertionError(f"{where}: {e}") from e

    @pytest.mark.parametrize("idx,where", [(0, "old_report"), (1, "l4_warn"), (2, "l4_thr"),
                                           (3, "l4_lamp"), (4, "l4_danger")])
    def test_c_escaping_inside_backticks_turns_red(self, idx, where, monkeypatch):
        """突變：該出口改走 `_md_scrub`（遮罩被跳成 `\\*`）→ 上一條的行為斷言必須抓到。"""
        m = _load_mutant(PT, (_SEC_R8_MD_MUT[idx],))
        text = _pt_sec_r8_texts(m, monkeypatch)[where]
        assert "\\*\\*\\*" in text, text
        with pytest.raises(AssertionError):
            raw = repr(RuntimeError(str(_TWO_MASKS))) if where == "old_report" else _SEC_R8_RAW
            _assert_backtick_exit(text, raw)
