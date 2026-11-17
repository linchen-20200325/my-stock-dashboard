"""Issue #1208 — ETF 經理人換手策略已取消並完整移除（2026-11-17 客戶裁示）的反向守衛。

客戶原文：「那換手策略就不考慮了 這個方式移除」。本檔把「移除」釘成可執行的契約，
任何一項被加回來（換手偵測 / 任期例外 / 新經理人建議 / 經理人抓取排程）即轉紅：

  A. 落後燈號：`classify_lag_verdict` 只吃 metrics，沒有任期輸入；同一份 metrics 必得同一結論。
  B. 弱勢度列：`compute_etf_weakness_row` 不抓經理人、列內無「經理人／任期」欄。
  C. UI：單檔 ETF 不再渲染 換手／新任／任期；健康度診斷不查經理人；組合頁無「新經理人」建議。
  D. 資料生產：`update_etf_managers.yml` 已刪、沒有任何 workflow 再跑經理人抓取或發布
     etf_managers.json；專用腳本與資料檔已刪；`publish_data_pr` 其他 job 的設定仍在。
  E. Mutation 守衛：repo 掃描禁止已移除符號／文案被重新引入；並以合成原始碼證明守衛本身會抓到。

全部零網路、零祕密值（價格 fetcher 以 monkeypatch 合成序列取代）。
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]

# 已移除、不得再出現在 production 程式碼（src/ shared/ scripts/ app*.py .github/）的符號
_REMOVED_SYMBOLS = (
    "track_etf_manager_change",
    "fetch_etf_manager",
    "_fetch_sitca_manager",
    "get_etf_manager_last_err",
    "_ETF_MANAGER_LAST_ERR",
    "ETF_MANAGER_TENURE_NEW_DAYS",
    "etf_manager_history",
    "update_etf_managers",
)
# 已移除、不得再出現在 production 字串常數裡的使用者可見換手／任期文案
_REMOVED_COPY = ("新經理人", "新任經理人", "經理人異動", "再給時間")
_REMOVED_FILES = (
    ".github/workflows/update_etf_managers.yml",
    "scripts/update_etf_managers.py",
    "src/data/etf/etf_managers.json",
    "src/data/etf/etf_manager_watchlist.json",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _prod_py_files():
    for base in ("src", "shared", "scripts"):
        for p in sorted((ROOT / base).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p
    for name in ("app.py", "app_ui2.py"):
        p = ROOT / name
        if p.exists():
            yield p


def _code_tokens(src: str) -> set[str]:
    """AST 層的識別字／屬性名／import 名（註解與字串不算）。"""
    out: set[str] = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.alias):
            out.add(n.name.split(".")[-1])
            if n.asname:
                out.add(n.asname)
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.update(n.module.split("."))
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.keyword) and n.arg:
            out.add(n.arg)
    return out


def _string_constants(src: str) -> list[str]:
    """AST 字串常數（含 f-string 片段），排除 module/function/class docstring。"""
    tree = ast.parse(src)
    docstrings: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(n, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


def removal_violations(rel: str, src: str) -> list[str]:
    """單檔掃描：回傳違規描述（空 = 合規）。E 段 mutation 測試直接餵合成原始碼。"""
    out: list[str] = []
    toks = _code_tokens(src)
    for sym in _REMOVED_SYMBOLS:
        if sym in toks:
            out.append(f"{rel}: 程式碼引用已移除符號 {sym}")
    for s in _string_constants(src):
        for phrase in _REMOVED_COPY:
            if phrase in s:
                out.append(f"{rel}: 字串常數含已移除文案 {phrase!r}: {s[:60]!r}")
        if "etf_managers.json" in s or "etf_manager_watchlist.json" in s:
            out.append(f"{rel}: 字串常數引用已刪資料檔: {s[:80]!r}")
    # classify_lag_verdict 不得再收任期／is_etf 參數
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef) and n.name == "classify_lag_verdict":
            names = [a.arg for a in n.args.args + n.args.kwonlyargs]
            if names != ["metrics"]:
                out.append(f"{rel}: classify_lag_verdict 參數應只有 metrics，實得 {names}")
        if isinstance(n, ast.Call):
            fn = n.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if fname == "classify_lag_verdict":
                kws = [k.arg for k in n.keywords]
                if kws or len(n.args) != 1:
                    out.append(f"{rel}: classify_lag_verdict 呼叫帶額外參數 {kws} / {len(n.args)} 位置參數")
    return out


# ════════════════════════════════════════════════════════════════════
# A. 落後燈號：無任期輸入、同 metrics → 同結論
# ════════════════════════════════════════════════════════════════════
def test_classify_lag_verdict_has_no_tenure_param():
    from src.compute.etf.asset_lag import classify_lag_verdict
    assert list(inspect.signature(classify_lag_verdict).parameters) == ["metrics"]
    m = {"down_ratio": 10, "up_ratio": 10, "quarter_lose_streak": 3}
    with pytest.raises(TypeError):
        classify_lag_verdict(m, tenure_days=30)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        classify_lag_verdict(m, is_etf=True)  # type: ignore[call-arg]


@pytest.mark.parametrize("streak", [0, 1, 2, 3, 6])
@pytest.mark.parametrize("down,up", [(10, 10), (80, 10), (10, 80), (80, 80)])
def test_same_metrics_same_verdict_and_no_tenure_copy(streak, down, up):
    from src.compute.etf.asset_lag import classify_lag_verdict
    m = {"down_ratio": down, "up_ratio": up, "quarter_lose_streak": streak}
    v1 = classify_lag_verdict(dict(m))
    v2 = classify_lag_verdict(dict(m))
    assert v1 == v2
    assert "再給時間" not in v1["動作建議"] and "經理人" not in v1["動作建議"]
    if streak >= 2:
        assert v1["燈號"].startswith("🚨")
        assert "0050" in v1["動作建議"]


def test_tenure_threshold_constant_removed():
    import shared.signal_thresholds as T
    assert not hasattr(T, "ETF_MANAGER_TENURE_NEW_DAYS")


# ════════════════════════════════════════════════════════════════════
# B. 弱勢度列：不抓經理人、無經理人／任期欄
# ════════════════════════════════════════════════════════════════════
def _synthetic_price(seed: int, drift: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2025-01-01", periods=260)
    close = 100 * np.cumprod(1 + drift + rng.normal(0, 0.01, len(idx)))
    return pd.DataFrame({"Close": close}, index=idx)


def test_weakness_row_has_no_manager_or_tenure_and_never_fetches_manager(monkeypatch):
    import src.compute.etf.etf_calc as C
    import src.data.etf.etf_fetch as F

    prices = {"00980A.TW": _synthetic_price(1, -0.002), "^TWII": _synthetic_price(2, 0.002)}
    monkeypatch.setattr(C, "fetch_etf_price", lambda t, period="1y": prices[t])
    # 若有人把經理人抓取加回來，這裡一定被呼叫到 → 立刻失敗（而不是發網路）
    for _name in ("fetch_etf_manager", "track_etf_manager_change"):
        assert not hasattr(F, _name), f"etf_fetch 不應再有 {_name}"
    try:
        C.compute_etf_weakness_row.clear()
    except Exception:
        pass
    row = C.compute_etf_weakness_row("00980A.TW", "合成主動式")
    assert "經理人" not in row and "任期" not in row
    assert row["主被動"] == "主動式"
    assert row["連敗季數"] is not None  # 指標有算出來（非 ⚪ 抓取失敗）
    from src.compute.etf.asset_lag import classify_lag_verdict
    m = C.calc_weakness_metrics(prices["00980A.TW"]["Close"].pct_change(),
                                prices["^TWII"]["Close"].pct_change())
    v = classify_lag_verdict(m)
    assert row["燈號"] == v["燈號"] and row["動作建議"] == v["動作建議"]


def test_weakness_table_display_cols_exclude_manager_and_tenure():
    tree = ast.parse(_read("src/ui/render/etf_render.py"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_render_weakness_table")
    assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
               and any(getattr(t, "id", "") == "_display_cols" for t in n.targets)]
    assert len(assigns) == 1
    cols = ast.literal_eval(assigns[0].value)
    assert "經理人" not in cols and "任期" not in cols
    assert {"燈號", "動作建議", "連敗季數"} <= set(cols)  # 其餘欄位保留


# ════════════════════════════════════════════════════════════════════
# C. UI：單檔不渲染換手／新任／任期；健康度不查經理人；組合頁無新經理人建議
# ════════════════════════════════════════════════════════════════════
def test_single_etf_tab_no_manager_block():
    src = _read("src/ui/etf/etf_tab_single.py")
    assert removal_violations("etf_tab_single.py", src) == []
    strings = _string_constants(src)
    for phrase in ("基金經理人", "任期", "🔁", "🆕"):
        assert not any(phrase in s for s in strings), f"單檔 ETF 頁仍渲染 {phrase!r}"
    # 其餘指標卡保留（價格／費用率／Beta／AUM／品質評等）
    for keep in ("內扣費用率", "Beta", "AUM"):
        assert any(keep in s for s in strings), f"{keep} 不應被誤刪"
    assert "compute_etf_quality" in _code_tokens(src)


def test_health_inspector_does_not_query_manager():
    src = _read("src/ui/pages/health_inspector.py")
    assert removal_violations("health_inspector.py", src) == []
    strings = _string_constants(src)
    assert not any("經理人" in s for s in strings), "健康度診斷不得再有經理人列／探測"
    # 經理人 regex 深度診斷直打 MoneyDJ Basic0001 的 URL 已移除
    assert not any("Basic0001" in s for s in strings)
    # 持股探測保留
    assert "fetch_etf_holdings" in _code_tokens(src)


def test_portfolio_and_render_no_new_manager_advice():
    for rel in ("src/ui/etf/etf_tab_portfolio.py", "src/ui/render/etf_render.py",
                "src/ui/etf/etf_dashboard.py", "src/services/watchlist_health_service.py",
                "src/compute/etf/etf_calc.py", "src/compute/etf/asset_lag.py"):
        src = _read(rel)
        assert removal_violations(rel, src) == [], rel
    strings = _string_constants(_read("src/ui/etf/etf_tab_portfolio.py"))
    assert not any("任期" in s for s in strings)


# ════════════════════════════════════════════════════════════════════
# D. 資料生產：workflow／腳本／資料檔已刪；無 workflow 再抓經理人；publish_data_pr 其他 job 完好
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("rel", _REMOVED_FILES)
def test_dedicated_files_removed(rel):
    assert not (ROOT / rel).exists(), f"{rel} 應已刪除（#1208）"


def test_no_workflow_runs_manager_fetch_or_publishes_manager_json():
    wf_dir = ROOT / ".github" / "workflows"
    wfs = sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")))
    assert wfs, "找不到任何 workflow（路徑錯誤會讓本守衛空轉）"
    bad = re.compile(r"update_etf_managers|etf_managers\.json|etf_manager_watchlist|etf-managers"
                     r"|fetch_etf_manager|track_etf_manager_change", re.IGNORECASE)
    for wf in wfs:
        text = wf.read_text(encoding="utf-8")
        hits = bad.findall(text)
        assert not hits, f"{wf.name} 仍引用 ETF 經理人抓取／發布：{hits}"


def _load_pdp():
    spec = importlib.util.spec_from_file_location("publish_data_pr_1208", ROOT / "scripts" / "publish_data_pr.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_publish_data_pr_manager_job_removed_other_jobs_intact():
    pdp = _load_pdp()
    assert "src/data/etf/etf_managers.json" not in pdp.VOLATILE_JSON_KEYS
    # 其他 data PR job 的揮發鍵登記保留
    for rel in ("data_cache/metadata.json", "data_cache/sector_flow/metadata.json",
                "data_cache/sector_flow/bubble_latest.json", "data_cache/sector_flow/industry_raw.json",
                "data_cache/macro_last_good/tw_pmi.json"):
        assert rel in pdp.VOLATILE_JSON_KEYS, rel
    # 其他 job 的實質判定行為不變
    a = json.dumps({"updated_at": "x", "last_error": None}).encode()
    b = json.dumps({"updated_at": "y", "last_error": None}).encode()
    c = json.dumps({"updated_at": "y", "last_error": "boom"}).encode()
    assert not pdp.json_substantive_change("data_cache/metadata.json", a, b)
    assert pdp.json_substantive_change("data_cache/metadata.json", a, c)
    # 仍在用 publish_data_pr 的 workflow 都還在（不是連帶清掉）
    users = [p.name for p in (ROOT / ".github" / "workflows").glob("*.yml")
             if "publish_data_pr.py" in p.read_text(encoding="utf-8")]
    assert {"update_macro_history.yml", "update_sector_flow.yml",
            "update_macro_forward_test.yml"} <= set(users)


# ════════════════════════════════════════════════════════════════════
# E. Mutation 守衛：全 repo production 碼不得重新引入；守衛本身對合成回歸必紅
# ════════════════════════════════════════════════════════════════════
def test_repo_wide_no_reintroduction():
    problems: list[str] = []
    for p in _prod_py_files():
        rel = p.relative_to(ROOT).as_posix()
        problems.extend(removal_violations(rel, p.read_text(encoding="utf-8")))
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("mutant", [
    # 換手偵測 caller 被加回 UI
    "from src.data.etf import fetch_etf_manager, track_etf_manager_change\n"
    "_chg = track_etf_manager_change('0050.TW', fetch_etf_manager('0050.TW'))\n",
    # 任期例外被加回燈號 SSOT
    "def classify_lag_verdict(metrics, *, is_etf=False, tenure_days=None):\n    return {}\n",
    # 呼叫端又傳任期
    "v = classify_lag_verdict(m, tenure_days=90)\n",
    # 新經理人建議文案被加回
    "msg = '⏳ 新經理人 <6 月，再給時間'\n",
    # 任期門檻常數被加回
    "ETF_MANAGER_TENURE_NEW_DAYS: int = 180\n",
    # 經理人資料檔被重新讀取
    "open('src/data/etf/etf_managers.json')\n",
])
def test_guard_catches_reintroduction(mutant):
    assert removal_violations("mutant.py", mutant), f"守衛沒抓到回歸：{mutant!r}"


def test_guard_does_not_flag_unrelated_code():
    ok = ("def classify_lag_verdict(metrics):\n    return {'燈號': '🟢', '動作建議': '續抱觀察'}\n"
          "v = classify_lag_verdict(m)\nfee = meta['manager_fee']\n")
    assert removal_violations("ok.py", ok) == []
