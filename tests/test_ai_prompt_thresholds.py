"""AI prompt 門檻守衛 — 餵給 LLM 的「怎麼判讀」不得寫死裸數字（CLAUDE.md §3.3 / §1）。

病史（本守衛存在的理由）
────────────────────────────────────────────────────────────────
2026-08-06 稽核發現 `src/ui/tabs/macro/section_news_ai.py` 的 `_ctx` 區塊
（送進 Gemini 的總經 context）每行都附「怎麼判讀」，但其中 6 條的門檻是
prompt 內手寫的裸數字，且與畫面燈號用的 `shared/macro_buckets` SSOT 不一致：

    外資期貨   prompt <-35000 強烈空頭  vs  SSOT 黃 -10000 / 紅 -20000
    VIX        prompt >28 / >35         vs  SSOT 黃 22 / 紅 30
    BIAS240    prompt >15 / <-10        vs  SSOT 黃 10 / 紅 20
    ADL 廣度   prompt >70 / <30         vs  SSOT 黃 50 / 紅 35
    PMI        prompt <48 製造業衰退     vs  SSOT 黃 50 / 紅 46
    CPI        prompt >3% 升息壓力       vs  SSOT 黃 3.5 / 紅 4.0

後果：系統畫面已亮 🔴、AI 卻依較寬的門檻說「還在安全區」。使用者會理所當然
以為兩者看的是同一套規則 —— 這是 §1「錯誤的數字比沒有數字更危險」的變形：
**錯誤的門檻比沒有門檻更危險**。同款在 `tab_stock_picker`（AI 報告說「過 5 關」
但 SSOT 早已改成 6）、`financial_health_engine`（AI 判讀規則 vs 純計算門檻兩份
複本）也各長了一次。

本檔釘死兩條規則
────────────────────────────────────────────────────────────────
  A. 指定的 prompt 建構點內，**字串字面**不得出現「比較語境的裸數字」
     （`>28`、`≤35000`、`低於 46`、`40–64`、`75 以上` …）。
     門檻一律用 f-string / `.format()` 插值 SSOT 常數。
  B. 指定的 prompt 建構點必須**實際引用**對應的 SSOT 常數名
     （防「把插值刪掉、改回寫死」與「常數 import 了卻沒用」）。

── 假陽性防護（本檔的設計重點）────────────────────────────────
本 session 已被「字串掃描式守衛」的假紅燈擋過三個回合（註解 / docstring 裡
出現同樣字面就誤判）。因此本守衛：
  • **完全用 `ast`，不做整檔字串比對** —— 註解在 AST 裡根本不存在，天生不可能
    誤判；本檔自己內文寫滿 `>28`、`<-35000` 也不會自我引爆（見
    `TestGuardItself::test_not_fooled_by_comments_and_docstrings`）。
  • **docstring 顯式排除**（module / function / class 的首個字串 Expr）。
  • **f-string 的插值段完全不看** —— 只掃 `JoinedStr` 裡的 `Constant` 片段，
    `f'（>{VIX_YELLOW}）'` 的 `>` 後面接的是 `FormattedValue`，不會被判違規。
  • **只掃指定的 prompt 建構點**（見 `_SITES`），不掃整個 repo、不掃 UI 顯示字串。
  • **自然邊界豁免**：`0`（正負號分界，如「OCF >0」）、`1`（Beta / Sharpe 的
    自然單位，如「>1 比大盤更激動」）、`100`（0~100 分數量表）不算門檻。
  • **數量詞豁免**：數字後接 句/字/點/則/檔/件/天/週/月/年/項/關… 視為計數
    （「2~3 句」「45 天發布延遲」），不是判讀門檻。
  • **判不準就不判**：非字面字串（變數 / 函式回傳值）一律放行，寧可漏也不製造假紅。
  • **失敗訊息印出 `檔:行` 與該行原文**，不是只說「有違規」。
  • 逃生口：違規行尾加 `# prompt-threshold-ok` 即豁免（只會讓紅變綠，不會製造紅）。

── 覆蓋範圍的誠實揭露（§1：不宣稱守衛做不到的事）──────────────
`_SITES` 是**白名單**，不是全 repo 掃描。`tab_stock.py` / `etf_tab_single.py`
這類「prompt 埋在千行 render 函式裡」的檔，只錨定實際組 prompt 的那幾個
賦值節點（`_rs_str2` / `_sections` …），**其餘 UI 顯示字串不在守衛範圍內**
（那些不會進 LLM，且硬掃必然大量假紅）。新增 prompt 建構點時請一併登錄
`_SITES`，否則守衛不會保護它。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO = _TESTS_DIR.parent

# 行尾豁免標記（白名單用途；只能讓紅變綠，無法製造假紅）
_PRAGMA = "# prompt-threshold-ok"


# ══════════════════════════════════════════════════════════════
# 受保護的 prompt 建構點（白名單）
#   calls   : 掃 `<name>.append(...)` 呼叫的所有引數子樹
#   assigns : 掃 `<name> = ...` 賦值右側子樹
#   funcs   : 掃該 function def 整個子樹
#   module  : 掃整個模組（僅適用於「整檔就是 prompt」的小檔）
#   requires: 規則 B —— 該 site 子樹內必須出現的 SSOT 常數 / helper 名
# ══════════════════════════════════════════════════════════════
_SITES: list[dict] = [
    {
        "path": "src/ui/tabs/macro/section_news_ai.py",
        "calls": ["_ctx"],
        "module_requires": [
            "danger_rule_text",                   # L3 共用：五桶門檻 → 判讀句
            "pcr_rule_text",                      # L3 共用：PCR 雙向門檻 → 判讀句
            "PCR_PERCENT_SCALE_MIN",              # §4.1 PCR 百分比/比值刻度判別
            "MACRO_VETO_FUTURES_NET_SHORT_LOTS",  # 外資期貨硬否決線 SSOT
        ],
    },
    {
        "path": "src/services/macro_state_locker.py",
        "assigns": ["_PROMPT_TEMPLATE"],
        "funcs_requires": {
            "_build_prompt": ["MACRO_EXPOSURE_NEUTRAL_MIN_PCT",
                              "MACRO_EXPOSURE_BULLISH_MIN_PCT"],
        },
    },
    {
        "path": "src/services/financial_health_engine.py",
        "assigns": ["_PROMPT_TEMPLATE"],
        "funcs_requires": {
            "analyze_financial_health": ["FH_CASH_RATIO_SAFE_PCT",
                                         "FH_CASH_RATIO_WATCH_PCT",
                                         "FH_DEBT_RATIO_EXCELLENT_PCT",
                                         "FH_DEBT_RATIO_PASS_PCT"],
        },
    },
    {"path": "src/services/ai_structured_summary.py", "module": True},
    {
        "path": "src/services/shortage_screener_service.py",
        "funcs": ["build_shortage_ai_prompt"],
        "funcs_requires": {
            "build_shortage_ai_prompt": ["SHORTAGE_TIER_STRONG_MIN",
                                         "SHORTAGE_TIER_MID_MIN"],
        },
    },
    {
        "path": "src/services/rs_leader_service.py",
        "funcs": ["build_rs_ai_prompt"],
        "funcs_requires": {
            "build_rs_ai_prompt": ["RS_SIGMA_LEAD_MIN", "RS_SIGMA_MILD_MIN",
                                   "RS_SIGMA_LAG_MAX"],
        },
    },
    {"path": "src/compute/notify/ai_judgment.py", "funcs": ["build_ai_judgment_prompt"]},
    {
        "path": "src/ui/tabs/tab_stock_picker.py",
        "funcs": ["_generate_ai_report"],
        "funcs_requires": {
            "_generate_ai_report": ["PICKER_S1_MIN_PASS", "PICKER_S2_MIN_PASS",
                                    "PICKER_S1_CONDITIONS", "PICKER_S2_CONDITIONS"],
        },
    },
    {
        "path": "src/ui/etf/etf_tab_ai.py",
        "funcs": ["_generate_report"],
        "funcs_requires": {"_generate_report": ["PORTFOLIO_STRESS_TEST_DROP_PCT"]},
    },
    {
        "path": "src/ui/etf/etf_tab_single.py",
        "assigns": ["_sections"],
        "assign_requires": {"_sections": ["KD_OVERBOUGHT_LEVEL", "KD_OVERSOLD_LEVEL"]},
    },
    {
        "path": "src/ui/tabs/tab_stock.py",
        "assigns": ["_sections_ai", "_rs_str2", "_lead_str2", "_sr_parts2"],
        # `_macro_lines2` 是個股 AI prompt 的宏觀背景段（v19.178 前自己寫了一套
        # 與總經 Tab、與畫面燈號都不同的門檻）；`_fund_str2` 是基本面段。
        "calls": ["_macro_lines2", "_fund_str2"],
        "module_requires": ["danger_rule_text"],
        "assign_requires": {
            "_rs_str2": ["STOCK_RS_STRONG_MIN", "STOCK_RS_NEUTRAL_MIN"],
            "_lead_str2": ["CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT",
                           "CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT"],
            "_sr_parts2": ["STOP_PROFIT_T1_PCT", "STOP_PROFIT_T2_PCT",
                           "STOP_LOSS_DEFAULT_PCT"],
        },
    },
    {
        "path": "src/ui/tabs/stock_grp_sections/section_ai_portfolio.py",
        "funcs": ["_build_portfolio_prompt"],
    },
]


# ══════════════════════════════════════════════════════════════
# 「比較語境的裸數字」辨識
# ══════════════════════════════════════════════════════════════

# ① 比較運算子 / 比較詞 後緊接數字：「>28」「≤ 35」「低於 46」
_CMP_RE = re.compile(
    r"(?:>=|<=|[<>＜＞≥≤≧≦]=?|超過|低於|高於|不足|少於|多於|達)\s*([+-]?\d+(?:\.\d+)?)")
# ② 數字後接「以上 / 以下」：「75 以上」「20% 以下」
_SUFFIX_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%?\s*(?:以上|以下|之上|之下)")
# ③ 區間寫法：「40–64」「23-31」「9~45」
_RANGE_RE = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)(?![\d.])")

# 自然邊界：不是「可調的門檻」，是數學/定義上的分界或量表端點
_NATURAL_BOUNDARIES = {0.0, 1.0, 100.0}

# 數量詞：數字後接這些字視為計數 / 時間長度（「2~3 句」「45 天」「8-12 秒」），非判讀門檻
#
# ⚠️ v19.178 修假陽性：原清單有「天週月年」卻**漏了「秒」**，於是
# `st.spinner('…（約 8-12 秒）…')` 這種**耗時估計**被判成寫死門檻。
# 受保護站點是以「函式」為單位掃描，函式內的 spinner / 進度文案也會被掃到，
# 所以時間單位必須豁免。
#
# 刻意**不加**「分」與「時」：
#   ・「分」在本專案是**分數單位**（「健康度 ≥70 分」「NDC 39 分」）——加了會製造
#     假陰性，讓真正的門檻漏掉。時間的「分鐘」請寫「分鐘」（首字為「分」仍會命中，
#     這是已知取捨：寧可多一次人工判讀，也不要漏掉分數門檻）。
#   ・「時」同理（「小時」vs「時間」歧義）。
_COUNT_UNIT_RE = re.compile(r"^\s*%?\s*[句字點則檔件次個天週月年秒名項關段行條筆檔]")


def _is_tunable(raw: str) -> bool:
    """這個數值是「可調門檻」還是「自然邊界」？自然邊界不算違規。"""
    try:
        return float(raw) not in _NATURAL_BOUNDARIES
    except ValueError:
        return False


def _followed_by_count_unit(text: str, idx: int) -> bool:
    """數字之後是否緊接數量詞（「2~3 句」「45 天」）→ 是計數不是門檻。"""
    return bool(_COUNT_UNIT_RE.match(text[idx:idx + 4]))


def _numeric_threshold_hits(text: str) -> list[str]:
    """回傳字串內「比較語境的裸數字」清單（已套用自然邊界 / 數量詞豁免）。"""
    hits: list[str] = []

    for m in _CMP_RE.finditer(text):
        if _is_tunable(m.group(1)) and not _followed_by_count_unit(text, m.end(1)):
            hits.append(m.group(0).strip())

    for m in _SUFFIX_RE.finditer(text):
        if _is_tunable(m.group(1)):
            hits.append(m.group(0).strip())

    for m in _RANGE_RE.finditer(text):
        # 數量詞判定看**整個區間的結尾**（「2~3 句」的「句」在 3 後面，不在 2 後面）
        if _followed_by_count_unit(text, m.end(2)):
            continue
        # 兩端只要有一端是可調門檻，就算門檻區間（「0~100 分」兩端皆自然邊界 → 放行）
        if _is_tunable(m.group(1)) or _is_tunable(m.group(2)):
            hits.append(m.group(0).strip())

    return hits


# ══════════════════════════════════════════════════════════════
# AST helpers
# ══════════════════════════════════════════════════════════════

def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """收集所有 docstring 的 Constant 節點 id（module / func / class 首個字串 Expr）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            out.add(id(first.value))
    return out


def _assign_targets(node: ast.AST) -> list[str]:
    """回傳賦值節點的目標名稱（只收單純 Name，Subscript/Attribute 一律略過）。"""
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return [node.target.id] if isinstance(node.target, ast.Name) else []
    return []


def _is_append_call(node: ast.AST, list_names: set[str]) -> bool:
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in list_names)


def _site_roots(tree: ast.AST, site: dict) -> list[ast.AST]:
    """依 site 設定挑出要掃描的子樹根節點。"""
    if site.get("module"):
        return [tree]
    roots: list[ast.AST] = []
    call_names = set(site.get("calls") or [])
    assign_names = set(site.get("assigns") or [])
    func_names = set(site.get("funcs") or [])
    for node in ast.walk(tree):
        if call_names and _is_append_call(node, call_names):
            roots.append(node)
        if assign_names and set(_assign_targets(node)) & assign_names:
            roots.append(node)
        if (func_names and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in func_names):
            roots.append(node)
    return roots


def _string_literals(root: ast.AST, doc_ids: set[int]):
    """走訪子樹，yield (lineno, 字串內容)。

    - f-string：只取 `JoinedStr` 內的 `Constant` 片段，插值段（FormattedValue）
      完全不看 → `f'（>{VIX_RED}）'` 不會被誤判。
    - docstring：顯式排除。
    - 非字串 Constant（數字 / bool）不看：本守衛只管「寫進 prompt 文字」的門檻。
    """
    for node in ast.walk(root):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if id(node) in doc_ids:
            continue
        yield getattr(node, "lineno", 0), node.value


def _names_used(root: ast.AST) -> set[str]:
    """子樹內出現過的識別字（Name.id / Attribute.attr / 關鍵字引數名 / import 別名）。

    `ast.alias` 一併收集**原名與別名**，讓白名單可以用「SSOT 的真名」登錄，
    不必跟著各檔的 `as _xxx` 短名走（短名一改守衛就假紅，那是最沒價值的紅燈）。
    """
    out: set[str] = set()
    for node in ast.walk(root):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            out.add(node.arg)
        elif isinstance(node, ast.alias):
            out.add(node.name.split(".")[-1])
            if node.asname:
                out.add(node.asname)
    return out


# ══════════════════════════════════════════════════════════════
# 單一 site 掃描
# ══════════════════════════════════════════════════════════════

def _scan_site(site: dict, repo: Path = None) -> list[str]:
    """回傳該 site 的規則 A 違規清單。找不到檔 → 回報為違規（避免改名後守衛靜默失效）。"""
    root_dir = repo or _REPO
    path = root_dir / site["path"]
    if not path.exists():
        return [f"{site['path']}: [SITE-MISSING] 受保護的 prompt 建構點檔案不存在，"
                f"請同步更新 _SITES 白名單"]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    doc_ids = _docstring_node_ids(tree)
    roots = _site_roots(tree, site)
    if not roots:
        return [f"{site['path']}: [ANCHOR-MISSING] 找不到錨點 "
                f"{site.get('calls') or site.get('assigns') or site.get('funcs')}，"
                f"守衛已失去保護目標（改名了？）"]

    found: list[str] = []
    seen: set[tuple] = set()
    for root in roots:
        for lineno, s in _string_literals(root, doc_ids):
            hits = _numeric_threshold_hits(s)
            if not hits:
                continue
            raw = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            if _PRAGMA in raw:          # 白名單：只會讓紅變綠
                continue
            key = (lineno, tuple(hits))
            if key in seen:
                continue
            seen.add(key)
            found.append(
                f"{site['path']}:{lineno}: [A/hardcoded-threshold] "
                f"prompt 內寫死門檻 {hits}\n      → {raw.strip()}")
    return found


def _scan_requires(site: dict, repo: Path = None) -> list[str]:
    """規則 B：指定 site 必須引用指定的 SSOT 常數名。"""
    root_dir = repo or _REPO
    path = root_dir / site["path"]
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[str] = []

    def _check(scope_desc: str, root: ast.AST, required: list[str]) -> None:
        used = _names_used(root)
        missing = [n for n in required if n not in used]
        if missing:
            out.append(f"{site['path']} [{scope_desc}]: "
                       f"[B/ssot-not-referenced] 未引用 SSOT 常數 {missing}"
                       f"（門檻可能又被寫死回 prompt 裡）")

    if site.get("module_requires"):
        _check("module", tree, site["module_requires"])

    for fname, required in (site.get("funcs_requires") or {}).items():
        node = next((n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name == fname), None)
        if node is None:
            out.append(f"{site['path']} [def {fname}]: [B/ANCHOR-MISSING] 函式不存在")
        else:
            _check(f"def {fname}", node, required)

    for aname, required in (site.get("assign_requires") or {}).items():
        nodes = [n for n in ast.walk(tree) if aname in _assign_targets(n)]
        if not nodes:
            out.append(f"{site['path']} [{aname}=]: [B/ANCHOR-MISSING] 賦值不存在")
            continue
        used: set[str] = set()
        for n in nodes:
            used |= _names_used(n)
        missing = [x for x in required if x not in used]
        if missing:
            out.append(f"{site['path']} [{aname}=]: "
                       f"[B/ssot-not-referenced] 未引用 SSOT 常數 {missing}")
    return out


_CACHE_A: list[str] = []
_CACHE_B: list[str] = []


def _violations_a() -> list[str]:
    if not _CACHE_A:
        for s in _SITES:
            _CACHE_A.extend(_scan_site(s))
        _CACHE_A.append("")     # sentinel：即使 0 違規也標記為已掃
    return [v for v in _CACHE_A if v]


def _violations_b() -> list[str]:
    if not _CACHE_B:
        for s in _SITES:
            _CACHE_B.extend(_scan_requires(s))
        _CACHE_B.append("")
    return [v for v in _CACHE_B if v]


# ══════════════════════════════════════════════════════════════
# 守衛本體
# ══════════════════════════════════════════════════════════════

def test_no_hardcoded_threshold_in_ai_prompt():
    """餵給 LLM 的 prompt 不得出現「比較語境的裸數字門檻」。"""
    bad = [v for v in _violations_a() if "[A/hardcoded-threshold]" in v]
    assert not bad, (
        "以下 prompt 建構點把判讀門檻寫死成裸數字（CLAUDE.md §3.3）。\n"
        "後果：SSOT 門檻改了、prompt 不會跟著改 → 畫面燈號與 AI 敘事給出相反結論\n"
        "（§1「錯誤的門檻比沒有門檻更危險」）。\n"
        "修法：改成 f-string / .format() 插值 SSOT 常數，例如\n"
        "      shared/macro_buckets.SPECS_BY_KEY['vix'].yellow / .red。\n"
        "刻意要與畫面燈號不同時：必須在 prompt 內明說「本門檻與畫面燈號不同，理由是…」，\n"
        "並在該行尾加 " + _PRAGMA + " 豁免；禁止靜默不一致。\n\n" + "\n".join(bad))


def test_prompt_sites_reference_ssot_constants():
    """指定 prompt 建構點必須實際引用 SSOT 常數（防插值被刪掉改回寫死）。"""
    bad = [v for v in _violations_b() if "[B/ssot-not-referenced]" in v]
    assert not bad, (
        "以下 prompt 建構點沒有引用它應該引用的 SSOT 常數。\n"
        "常見成因：有人把 f-string 插值改回寫死數字，import 卻忘了刪。\n\n"
        + "\n".join(bad))


def test_prompt_site_anchors_still_exist():
    """白名單錨點（檔 / 函式 / 變數名）必須存在，否則守衛會靜默失效。"""
    bad = [v for v in (_violations_a() + _violations_b())
           if "MISSING]" in v]
    assert not bad, (
        "以下受保護的 prompt 建構點錨點消失（檔案 / 函式 / 變數被改名或刪除）。\n"
        "守衛會因此靜默失效 —— 請同步更新本檔 _SITES。\n\n" + "\n".join(bad))


# ══════════════════════════════════════════════════════════════
# 五桶 SSOT 對帳 — 釘住「AI 判讀規則 = 畫面燈號規則」
# ══════════════════════════════════════════════════════════════

def test_danger_rule_text_matches_bucket_ssot():
    """`danger_rule_text()` 產生的門檻文字必須等於 DangerSpec 的值。

    這條比字串掃描更直接：它真的呼叫 helper，驗證吐出來的數字就是 SSOT 的數字。
    涵蓋總經 Tab（`section_news_ai._ctx`）與個股 Tab（`tab_stock._macro_lines2`）
    共用的 12 個 key —— 兩處共用同一個 helper，就不可能再各寫一套。
    """
    from shared.macro_buckets import SPECS_BY_KEY
    from src.services.ai_structured_summary import danger_rule_text

    for key in ("bias_240", "m1b_m2_gap", "foreign_net", "margin", "adl",
                "fut_net", "vix", "ndc_signal", "ism_pmi", "tw_export",
                "us_core_cpi", "us10y"):
        spec = SPECS_BY_KEY[key]
        text = danger_rule_text(key)
        for val in (spec.yellow, spec.red):
            rendered = f"{val:.{spec.decimals}f}"
            assert rendered in text, (
                f"{key}: 門檻 {rendered} 沒有出現在餵給 AI 的判讀句裡 → "
                f"AI 拿到的規則與畫面燈號不同。實際產出：{text}")
        if spec.direction == "band":
            for val in (spec.yellow_lo, spec.red_lo):
                rendered = f"{val:.{spec.decimals}f}"
                assert rendered in text, f"{key}: band 低側 {rendered} 缺漏：{text}"


def test_pcr_rule_uses_ratio_scale_not_percent():
    """PCR 判讀句必須用比值刻度（0.5~2.0），不可混入百分比刻度（50~200）。

    §4.1 量綱：`li_latest['選PCR']` 是 ×100 後的百分比刻度，SSOT 門檻是比值刻度。
    原 prompt 把 126.80 配上「>1.3 恐慌」= 100× 錯，LLM 必然讀成極度恐慌。
    """
    from src.config import MACRO_ALERT_RULES
    from src.services.ai_structured_summary import pcr_rule_text

    rule = next(r for r in MACRO_ALERT_RULES if r.get("key") == "pcr")
    text = pcr_rule_text()
    for field in ("yellow_above", "red_above", "yellow_below", "red_below"):
        val = rule[field]
        assert 0.0 < val < 10.0, (
            f"MACRO_ALERT_RULES['pcr'][{field}]={val} 不在比值刻度 → "
            f"SSOT 自己混了刻度，請先修 SSOT")
        assert f"{val:.1f}" in text, f"PCR 門檻 {val} 未出現在判讀句：{text}"


def test_percent_scale_min_is_shared_ssot():
    """PCR 百分比/比值刻度判別線必須是共用 SSOT，不得兩處各寫一個。

    用 AST 檢查 `macro_alert.py` 是否真的**引用**了常數（不是掃註解字面），
    避免「註解寫了 SSOT、程式碼還是 inline 10」這種假綠。
    """
    from shared.signal_thresholds import PCR_PERCENT_SCALE_MIN

    assert PCR_PERCENT_SCALE_MIN == 10.0, "SSOT 值被改動，請確認兩處消費端都跟上"

    path = _REPO / "src/data/macro/macro_alert.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert "PCR_PERCENT_SCALE_MIN" in _names_used(tree), (
        "macro_alert 的 PCR 刻度判別仍是 inline 數字，未收斂到 "
        "shared.signal_thresholds.PCR_PERCENT_SCALE_MIN")


# ══════════════════════════════════════════════════════════════
# 守衛的自我驗證 — 證明它抓得到真違規、且不被註解/docstring/插值騙
# (§6：守衛自己也要有「3 個最容易讓它出錯的輸入」)
#
# ⚠️ 本區塊刻意在字串 / 註解 / docstring 裡塞滿誘餌字面
#    （>28、<-35000、40–64、75 以上 …）。這些**必須**仍然綠燈 ——
#    只要下面任何一條變紅，就代表守衛退化成「字串掃描」了。
# ══════════════════════════════════════════════════════════════

def _scan_snippet(tmp_path: Path, code: str, site_extra: dict = None) -> list[str]:
    rel = "probe_prompt.py"
    (tmp_path / rel).write_text(code, encoding="utf-8")
    site = {"path": rel, "calls": ["_ctx"]}
    site.update(site_extra or {})
    return _scan_site(site, repo=tmp_path)


class TestGuardItself:
    """守衛自身行為驗證。誘餌字面：>28警戒、>35極度恐慌、<-35000強烈空頭、40–64、70 以上。"""

    def test_catches_the_original_regression(self, tmp_path):
        """把 2026-08-06 找到的原始違規原文餵回去，必須全部抓到。"""
        out = _scan_snippet(tmp_path, (
            "_ctx = []\n"
            "_ctx.append('• VIX 恐慌指數：x（>28警戒、>35極度恐慌）')\n"
            "_ctx.append('• 外資期貨淨口數：y（負=淨空單、<-35000強烈空頭信號）')\n"
            "_ctx.append('• ADR 廣度指標：z（>70市場健康、<30廣度不足）')\n"
            "_ctx.append('• 大盤年線乖離率：w（>15%偏貴、<-10%低估）')\n"
            "_ctx.append('• 台灣 PMI：p（>50擴張、<50收縮、<48製造業衰退）')\n"
            "_ctx.append('• 中度缺貨訊號（40–64）')\n"
            "_ctx.append('• RS 相對強度：75 以上算強勢')\n"
        ))
        assert len(out) == 7, f"應抓到 7 行違規，實得 {len(out)}：{out}"
        joined = "\n".join(out)
        for token in (">28", "<-35000", ">70", ">15", "<48", "40–64", "75 以上"):
            assert token in joined, f"訊息未指出違規字面 {token!r}：{joined}"
        assert "→ _ctx.append(" in joined, "失敗訊息必須印出命中位置的該行原文"

    def test_not_fooled_by_comments_and_docstrings(self, tmp_path):
        """假陽性防護①：註解 / docstring / 非 prompt 字串寫同樣字面，不得誤判。"""
        out = _scan_snippet(tmp_path, (
            '"""模組說明：原本寫 >28警戒、>35極度恐慌、<-35000 強烈空頭，已修正。"""\n'
            "# _ctx.append('VIX（>28警戒）')   ← 這行是註解\n"
            "NOTE = 'VIX 舊門檻 >28 / >35，新門檻見 SSOT'\n"
            "_ctx = []\n"
            "_ctx.append('• 這行沒有任何門檻數字')   # 錨點：確保守衛真的有掃到東西\n"
            "def f():\n"
            "    '''本函式曾用 >70市場健康、<30廣度不足。'''\n"
            "    other_list = []\n"
            "    other_list.append('ADR 廣度（>70健康、<30不足）')\n"
        ))
        assert out == [], f"註解/docstring/非受保護清單不該被判違規：{out}"

    def test_not_fooled_by_fstring_interpolation(self, tmp_path):
        """假陽性防護②：門檻用 f-string 插值 SSOT 常數 → 必須放行。"""
        out = _scan_snippet(tmp_path, (
            "VIX_Y, VIX_R = 22.0, 30.0\n"
            "_ctx = []\n"
            "_ctx.append(f'• VIX：{v}（≥{VIX_Y:.1f} 警戒、≥{VIX_R:.1f} 危險）')\n"
            "_ctx.append(f'• 外資期貨：{n} 口（≤{FUT_Y:.0f} 🟡、≤{FUT_R:.0f} 🔴）')\n"
        ))
        assert out == [], f"插值寫法被誤判：{out}"

    def test_natural_boundaries_and_counts_exempt(self, tmp_path):
        """假陽性防護③：自然邊界（>0 / >1 / 0~100）與數量詞（2~3 句）不得誤判。"""
        out = _scan_snippet(tmp_path, (
            "_ctx = []\n"
            "_ctx.append('• OCF：>0 真實獲利、≤0 黑字破產警戒')\n"
            "_ctx.append('• Beta：>1 比大盤更激動、<1 比較穩')\n"
            "_ctx.append('• 五力分析各 0~100 分')\n"
            "_ctx.append('• 每節用 2~3 句白話講；挑 1~3 件時事')\n"
            "_ctx.append('• 財報約 45 天發布延遲')\n"
            "_ctx.append('• 外資買賣超 >0 億=買超')\n"
            # v19.178 迴歸：spinner 的耗時估計曾被判成寫死門檻
            # （etf_tab_ai.py:260「約 8-12 秒」）——時間單位必須豁免。
            "st.spinner('AI 首席策略師生成戰情報告中（約 8-12 秒）...')\n"
            "st.spinner('批次抓取中（約 20-30 秒）…')\n"
        ))
        assert out == [], f"自然邊界/數量詞被誤判：{out}"

    def test_score_unit_still_caught(self, tmp_path):
        """假陽性防護的**反向**驗證：豁免時間單位不可順手放掉「分數」門檻。

        「分」與「秒」只差一個字，但語意完全不同 —— 前者是可調門檻
        （健康度 ≥70 分），後者是耗時。若哪天有人為了消紅燈把「分」也加進
        `_COUNT_UNIT_RE`，這條會當場紅，逼他改回來。
        """
        out = _scan_snippet(tmp_path, (
            "_ctx = []\n"
            "_ctx.append('• 健康度 ≥70 分才列入候選')\n"
        ))
        assert out, "分數門檻「≥70 分」必須被抓到，不可因時間單位豁免而漏放"
        assert "70" in "".join(out), f"訊息未指出違規字面 70：{out}"

    def test_pragma_allows_documented_exception(self, tmp_path):
        """刻意與畫面燈號不同時，可用 pragma 豁免（只讓紅變綠）。"""
        out = _scan_snippet(tmp_path, (
            "_ctx = []\n"
            "_ctx.append('• 硬否決線 <-35000 口（刻意比燈號嚴）')  "
            + _PRAGMA + "\n"
        ))
        assert out == [], f"{_PRAGMA} 白名單失效：{out}"

    def test_reports_missing_anchor(self, tmp_path):
        """錨點消失（變數改名）必須報錯，不可靜默通過。"""
        out = _scan_snippet(tmp_path, "other = []\nother.append('x')\n")
        assert any("ANCHOR-MISSING" in v for v in out), (
            f"錨點消失時守衛必須報錯（否則會靜默失效）：{out}")

    def test_requires_rule_detects_removed_ssot_reference(self, tmp_path):
        """規則 B：把插值改回寫死、常數沒被引用 → 必須報錯。"""
        rel = "probe_requires.py"
        (tmp_path / rel).write_text(
            "def build_x_prompt():\n"
            "    return '強訊號（分數≥65）'\n", encoding="utf-8")
        out = _scan_requires(
            {"path": rel,
             "funcs_requires": {"build_x_prompt": ["SHORTAGE_TIER_STRONG_MIN"]}},
            repo=tmp_path)
        assert any("[B/ssot-not-referenced]" in v for v in out), out
