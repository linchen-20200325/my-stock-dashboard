"""OneBrain／Decision Digest 匿名離線示意（C-OB-USABLE；不是測試檔，不會被收集；**僅限 tests/ 使用**）。

執行：`python -m tests.onebrain_anon_demo [--scenario A|B|C|D|E|F|all] [--format text|json]`

═══ 這是什麼 ═══════════════════════════════════════════════════════════
把既有、已通過守衛的離線管線 `assemble_digest → build_rule_summary →（run_shadow + FakeProvider）`
用**匿名合成輸入**跑一遍，輸出人可讀文字（或機器對照 JSON）。每個情境分四區：
來源（coverage 的 source／資料日）／缺值（原因）／規則判斷（規則式摘要五段）／fallback（effective 與 Provider 是否被採用）。

═══ 這**不是**什麼（硬邊界）════════════════════════════════════════════
- ⛔ **不是** UI：UI2 的 OneBrain／Digest 位置仍是「⬜ 尚未提供」空殼；使用者在畫面上**看不到**這裡的任何輸出。
- ⛔ 不是 production caller：本檔放在 tests/（非 `test_` 開頭），不被任何 src／app／scripts import；
  Stage F Gate（`ALLOWED_CALLERS=∅`）仍關閉。
- ⛔ 零網路、零 Secrets、零時鐘（`generated_at` 為固定常數）、不讀真持股／Google Sheet／OAuth；
  只用 `FakeProvider`（離線）；不啟用任何真實 Provider／SDK／付費 API。
- ⛔ 不修改 Digest schema／詞彙／簽章；缺口如實呈現、不美化（見 `KNOWN_LIMITS`）。
- 輸入全是匿名合成資料（代號 T0..Tn、行動文字 `txt-…` 為示意識別字），**非真實持股、非投資建議**。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from typing import Any, Optional

from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import HoldingKey
from shared.fetch_outcome import FetchOutcome
from shared.freshness_policy import FreshnessStatus
from shared.onebrain_provider import ProviderErrorKind
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_assembly import AssembledDigest, EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp
from src.services.decision_digest_summary import build_rule_summary
from src.services.onebrain_shadow import run_shadow
from tests.onebrain_fake_provider import MODE_PAYLOAD, FakeProvider

BANNER = "示意：匿名合成輸入，非真實持股、非投資建議"
UI_DISCLAIMER = ("本輸出為離線 CLI 示意；UI2 的 OneBrain／Digest 位置仍是「⬜ 尚未提供」空殼，"
                 "使用者在畫面上看不到這些內容。")

#: 已知缺口（如實標示，不得美化；修法屬 Digest 詞彙／簽章變更，Gate-needed，本檔不動）。
LIMIT_STALE = ("注意：摘要字面未區分「過期」與「尚無輸入」（Digest v1 無缺值原因欄的已知缺口）；"
               "coverage 如實記為 stale。")
LIMIT_FETCH_FAILED = ("注意：摘要字面為「規則層未產出可引用依據」，未點出「抓取失敗」；"
                      "coverage 如實記為 fetch_failed（同屬 Digest v1 無缺值原因欄的已知缺口）。")
LIMIT_OMITTED = ("已知限制 OB-1-D3：摘要僅列 Top-{shown}，未揭露其餘 {omitted} 筆被省略的行動；"
                 "省略數只在 coverage 側車（total={total}／shown={shown}／omitted={omitted}）。")

SCENARIO_KEYS = ("A", "B", "C", "D", "E", "F")
SCENARIO_TITLES = {
    "A": "證據齊全（來源與資料日齊備）",
    "B": "零證據（全段無輸入）",
    "C": "macro 證據過期（coverage withheld=stale）",
    "D": "站內證據抓取失敗（FETCH_FAILED）",
    "E": "合格行動 7 筆（超過 Top-3 上限）",
    "F": "影子執行：Provider 逾時／垃圾輸出／回聲，使用者看到的結果不變",
}
SECTION_LABELS = {"market": "市場", "industry": "產業", "buy_and_hold": "存股",
                  "capital_gain": "資本利得", "actions": "本期行動"}

# ── 固定合成輸入（無時鐘、無隨機）─────────────────────────────────────────
_NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)           # 台北 2026-10-27 17:00
_ASOF = date(2026, 10, 26)
_MACRO_STAMP = SourceStamp("macro_state.json", _ASOF)
_STATION_STAMP = SourceStamp("dividend_station_service", _ASOF)
_CODES = ("add", "pause_add", "cut", "take_profit_force", "take_profit_partial", "add", "pause_add")


def _macro_state() -> dict:
    disclosure = RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(), sahm_status=None)
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disclosure}


def _fresh(stamp: SourceStamp) -> EvidenceInput:
    return EvidenceInput(stamp=stamp, freshness=FreshnessStatus.FRESH)


def _kwargs(n_candidates: int = 2, **over: Any) -> dict:
    tickers = [f"T{i}" for i in range(n_candidates)]
    rows = [{"代號": t, "held": True, "_action": _CODES[i % len(_CODES)],
             "建議動作": f"txt-{_CODES[i % len(_CODES)]}-{t}", "_detail": {}} for i, t in enumerate(tickers)]
    macro = _macro_state()
    kw: dict = dict(
        generated_at=_NOW, macro_state=macro, macro_evidence=_fresh(_MACRO_STAMP),
        allocation=build_allocation_decision(macro),
        station_rows=rows, station_evidence=_fresh(_STATION_STAMP),
        holdings_rows=[{"ticker": t, "name": f"n-{t}", "held": True} for t in tickers],
        holding_keys={t: HoldingKey("pf-demo", t) for t in tickers})
    kw.update(over)
    return kw


def _assemble(key: str) -> AssembledDigest:
    if key in ("A", "F"):
        return assemble_digest(**_kwargs(2))
    if key == "B":
        return assemble_digest(generated_at=_NOW)
    if key == "C":
        return assemble_digest(**_kwargs(2, macro_evidence=EvidenceInput(_MACRO_STAMP, FreshnessStatus.STALE)))
    if key == "D":
        return assemble_digest(**_kwargs(
            2, station_evidence=EvidenceInput(None, None, FetchOutcome.FETCH_FAILED)))
    if key == "E":
        return assemble_digest(**_kwargs(7))
    raise ValueError(f"未知情境：{key!r}（可用：{', '.join(SCENARIO_KEYS)}）")


# ── 報告（dict；文字與 JSON 都由它產生）──────────────────────────────────
def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d is not None else None


def _summary_block(a: AssembledDigest) -> dict:
    result = build_rule_summary(a.digest)
    lines = [{"section": k, "label": SECTION_LABELS.get(k, k), "sentences": list(ss)} for k, ss in result.lines]
    missing_marks = sum(1 for blk in lines for s in blk["sentences"] if s.startswith("⬜"))
    # 「資料不足／規則層未產出可引用依據」＝真缺值；「尚未定義／研究框架，未啟用」是功能尚未提供，分開呈現
    insufficient = [s for blk in lines for s in blk["sentences"]
                    if s.startswith("⬜") and ("資料不足" in s or "未產出可引用依據" in s)]
    return {"mode": result.mode.value, "state": result.state.value, "sections": lines,
            "missing_mark_lines": missing_marks, "insufficient_lines": insufficient}


def _notes(a: AssembledDigest) -> list:
    """如實揭露已知缺口：只在情境確實出現該現象時加註。"""
    cov, out = a.coverage, []
    if any(s.withheld_reason == "stale" for s in cov.segments):
        out.append(LIMIT_STALE)
    if any(s.withheld_reason == "fetch_failed" for s in cov.segments):
        out.append(LIMIT_FETCH_FAILED)
    if cov.actions_omitted_count:
        out.append(LIMIT_OMITTED.format(shown=cov.actions_shown, omitted=cov.actions_omitted_count,
                                        total=cov.actions_total_eligible))
    return out


def _fallback_plain() -> dict:
    return {"effective": "規則式摘要（rule_only）", "provider_used": False,
            "provider": "本情境未啟用 Provider（離線示意只展示規則層）"}


def _shadow_runs(a: AssembledDigest) -> list:
    rule_lines = build_rule_summary(a.digest).lines
    runs = []
    for label, provider in (("timeout（逾時）", FakeProvider("timeout")),
                            ("垃圾輸出（自由文字，非結構化草稿）",
                             FakeProvider(MODE_PAYLOAD, payload="（自由文字：非結構化草稿）")),
                            ("echo（回聲規則式草稿）", FakeProvider("echo"))):
        o = run_shadow(a.digest, provider)
        runs.append({
            "provider_mode": label,
            "error_kind": o.error_kind.value if isinstance(o.error_kind, ProviderErrorKind) else None,
            "shadow_accepted": o.shadow_accepted,
            "grounding_clean": None if o.grounding is None else o.grounding.clean,
            "effective_mode": o.effective.mode.value,
            "effective_equals_rule_summary": o.effective.lines == rule_lines,
            "provider_output_adopted": False,       # 設計：影子層永不採用 Provider 輸出
        })
    return runs


def run_scenario(key: str) -> dict:
    key = key.upper()
    a = _assemble(key)
    cov = a.coverage
    report = {
        "scenario": key, "title": SCENARIO_TITLES[key], "banner": BANNER, "ui_disclaimer": UI_DISCLAIMER,
        "sources": {
            "segments": [{"segment": s.segment, "used": s.used, "source": s.source, "as_of": _iso(s.as_of)}
                         for s in cov.segments],
            "actions": {"total": cov.actions_total_eligible, "shown": cov.actions_shown,
                        "omitted": cov.actions_omitted_count, "max": cov.actions_max},
            "is_complete": cov.is_complete,
        },
        "missing": {"withheld": [{"segment": s.segment, "reason": s.withheld_reason}
                                 for s in cov.segments if not s.used]},
        "rule_judgment": _summary_block(a),
        "notes": _notes(a),
        "fallback": _fallback_plain(),
    }
    report["missing"]["missing_mark_lines"] = report["rule_judgment"]["missing_mark_lines"]
    report["missing"]["insufficient_lines"] = report["rule_judgment"]["insufficient_lines"]
    if key == "F":
        report["fallback"] = {"effective": "規則式摘要（rule_only）", "provider_used": False,
                              "provider": "FakeProvider（離線）；Provider 輸出只被檢查、永遠不被採用",
                              "shadow_runs": _shadow_runs(a)}
    return report


# ── 文字輸出 ───────────────────────────────────────────────────────────
def _fmt(v: Any) -> str:
    return "未知（None，不是 0）" if v is None else str(v)


def render_text(r: dict) -> str:
    out = [f"{'═' * 60}", f"【{BANNER}】", f"情境 {r['scenario']}：{r['title']}", UI_DISCLAIMER,
           "行動文字 txt-… 為合成示意識別字，不是建議。", ""]
    src = r["sources"]
    out.append("① 來源（coverage：source／資料日）")
    for s in src["segments"]:
        mark = "採用" if s["used"] else "未採用"
        out.append(f"  - {s['segment']:<9}{mark}　source={s['source'] or '無'}　資料日={s['as_of'] or '無'}")
    a = src["actions"]
    out.append(f"  - 行動候選：total={_fmt(a['total'])}／shown={a['shown']}／omitted={_fmt(a['omitted'])}（上限 {a['max']}）"
               f"；is_complete={src['is_complete']}")
    out.append("")
    out.append("② 缺值（⬜ 無法判定／資料不足 與原因）")
    if r["missing"]["withheld"]:
        for w in r["missing"]["withheld"]:
            out.append(f"  - {w['segment']:<9}證據未採用，原因＝{w['reason']}")
    else:
        out.append("  - 四段證據皆採用，無證據被拒用")
    for line in r["missing"]["insufficient_lines"]:
        out.append(f"  - 摘要缺值句：{line}")
    out.append(f"  - 摘要內帶「⬜」的句子共 {r['missing']['missing_mark_lines']} 句（含「尚未定義」「研究框架，未啟用」）；明細見③")
    out.append("")
    rj = r["rule_judgment"]
    out.append(f"③ 規則判斷（規則式摘要五段；mode={rj['mode']}，state={rj['state']}）")
    for blk in rj["sections"]:
        out.append(f"  ▍{blk['label']}")
        out.extend(f"    {s}" for s in blk["sentences"])
    for n in r["notes"]:
        out.append(f"  ⚠ {n}")
    out.append("")
    fb = r["fallback"]
    out.append("④ fallback（使用者實際看到的是哪一份）")
    out.append(f"  - effective ＝ {fb['effective']}；Provider 輸出是否被採用：{'是' if fb['provider_used'] else '否'}")
    out.append(f"  - {fb['provider']}")
    for run in fb.get("shadow_runs", []):
        out.append(f"  · Provider={run['provider_mode']}：error_kind={run['error_kind']}，"
                   f"shadow_accepted={run['shadow_accepted']}，grounding_clean={run['grounding_clean']}，"
                   f"effective==規則式摘要：{'是' if run['effective_equals_rule_summary'] else '否'}，"
                   f"採用 Provider 輸出：{'是' if run['provider_output_adopted'] else '否'}")
    return "\n".join(out) + "\n"


def run(scenario: str = "all", fmt: str = "text") -> str:
    keys = SCENARIO_KEYS if scenario.lower() == "all" else (scenario.upper(),)
    reports = [run_scenario(k) for k in keys]
    if fmt == "json":
        return json.dumps(reports, ensure_ascii=False, indent=2) + "\n"
    if fmt == "text":
        return "\n".join(render_text(r) for r in reports)
    raise ValueError(f"未知輸出格式：{fmt!r}（text|json）")


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="OneBrain／Decision Digest 匿名離線示意（非 UI、非投資建議）")
    p.add_argument("--scenario", default="all", help="A|B|C|D|E|F|all（預設 all）")
    p.add_argument("--format", dest="fmt", default="text", choices=("text", "json"))
    args = p.parse_args(argv)
    try:
        sys.stdout.write(run(args.scenario, args.fmt))
    except ValueError as e:
        sys.stderr.write(f"錯誤：{e}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
