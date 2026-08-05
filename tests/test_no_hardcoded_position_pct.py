"""tests/test_no_hardcoded_position_pct.py — 守門：UI/Compute 不得再長出硬編碼持股百分比（v19.170）。

為什麼需要這道守門測試
----------------------
v19.170 P0-1 建立了「建議持股 SSOT」(`shared/allocation_decision` +
`src/services/allocation_service.get_allocation()`)，把全站 6 套互相矛盾的持股
建議收斂成一個數字。但**收斂是一次性動作，發散是持續性壓力**：

本輪光是人工重掃就又揪出 4 處沒人盯的殘留 ——
  - `src/compute/risk/risk_radar.py`  各分支 action 字串裡的「現金 30%+ / 倉位 60-70%」
  - `src/ui/tabs/macro/section_news_ai.py`  48px 巨字的「曝險 0%／現金 100%」
  - 兩支 LLM prompt 裡塞給模型的舊持股區間

終驗稽核的結論很直白：**沒有守門測試，下一版還會再長出「沒人盯的第 5、第 6 個
位置」**。人工重掃不可重複、不可規模化，故改成 CI 靜態掃描。

掃描範圍與規則
--------------
範圍：`src/ui/**/*.py` + `src/compute/**/*.py` + `app.py`
規則：持股語意關鍵詞後 12 字內出現 `\\d{1,3}%` 或 `\\d{1,2}成`
      （v19.170：不得跨越 `,，。（(` 與換行 —— 括號後是另一個語意單位）
      （v19.171：關鍵詞從「名詞型」擴充到「動詞／量詞型」；
        單位從只認 `%` 擴充到認台股口語「成」—— 見下方 `_PATTERN`）
排除：
  1. 註解行（`strip().startswith('#')`）—— 說明「原本寫死了什麼、為何改掉」是好事，
     不該被罰。
  2. docstring / 裸字串陳述式 —— 用 `ast` 取出所有 `Expr(Constant[str])` 節點的
     `lineno..end_lineno` 區間排除。刻意**不**用「偵測三引號」的字元掃描：那會誤殺
     `st.markdown('''…''')` 這種**真的會印到畫面**的多行字串（如
     `tab_stock.py` 的財報名詞表），而那正是本測試最該盯的東西。
  3. `_ALLOWED_FILES`：SSOT 本體 / 教學靜態表 / DEPRECATED 常數。
  4. `_KNOWN_DEBT`：已知待修但本輪未授權改動的檔（見該常數註解，應逐版縮小）。
  5. `_FALSE_POSITIVE_RE`：關鍵詞撞名但語意無關者（財報「現金佔總資產」、
     單筆交易「風險 1.5% 法」）。

⚠️ 新增白名單前請先想清楚：持股百分比**只能**來自 `get_allocation()` /
`get_allocation_sleeves()`。教學用途才放行，且必須在 STATE.md 登記。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# 掃描範圍：會被使用者看到（UI）或會產生給使用者看的字串（Compute）的地方。
# shared/ 不掃 —— 持股 SSOT 本體就住在那，掃了只會全是假陽性。
_SCAN_DIRS = ('src/ui', 'src/compute')
_SCAN_FILES = ('app.py',)

# 稽核用 regex：中文關鍵詞後 12 字內出現百分比。
# `[^,，。（(\n]` 限制不得跨子句/跨行/跨括號，避免「…現金…（下略 40 字）…20%」
# 這種語意上根本無關的遠距離誤判。
#
# v19.170 修正（本測試自身的 bug，不是 production 的問題）：
#   排除字元集補上 `（` 與 `(` —— **命中片段不得跨越括號吃進補充說明**。
#   根因：`建議持股 30%（風險 1.5% 法）` 原本會貪婪吃成 `持股 30%（風險 1.5%`，
#   於是被「風險 …% 法」那條假陽性規則整段誤殺，真違規反而逃逸
#   （見 test_false_positive_filter_does_not_swallow_real_violations）。
#   括號內是另一個語意單位，本來就不該被當成同一句持股宣告。
#   **只排開括號、不排收括號**：`（現金）30%` 這種真違規仍必須抓得到。
#
# v19.171 修正（**線上實機驗收抓到、本測試漏掉**的一整類寫法）：
#   實機頁面出現「建議降倉至30%以下」與同畫面 SSOT「最終建議持股 20%」矛盾，
#   但 CI 是綠的 —— 根因是原關鍵詞清單全是**名詞型**（持股／倉位／部位…），
#   而「降**倉**至30%」只有單字「倉」，不在 alternation 裡 → 整類逃逸。
#   修法：把 alternation 從「名詞型」擴充到「動詞／量詞型」。
#
#   為什麼是**擴充同一條 alternation**、而不是兩條 pattern 並集：
#     `_scan()` 的假陽性過濾、`break`、以及兩條 meta 測試全都建立在
#     「單一 `_PATTERN` + `group(0)` 命中片段」這個契約上。拆成兩條會讓
#     「命中片段」變成兩個來源，過濾規則得寫兩份、將來只改一份就是新的假綠燈。
#     兩者表達力完全等價（同樣的 12 字窗口、同樣的邊界字元集），故取較穩的一條。
#
#   關鍵詞取捨（**刻意不收 `加碼`／`減碼`**）：
#     - `減碼` 會誤殺 `etf_tab_grp_compare.py` 的殖利率分級
#       「5%~7%⚪中性 / 3%~5%🟡減碼」—— 那是殖利率門檻，不是持股水位。
#     - `減碼50%`（`section_when_buy_sell.py` 出場策略）是**相對**減碼一半，
#       不是宣告絕對持股水位，語意上不與 SSOT 競爭。
#     收進來只會逼出一堆白名單，反而稀釋這道守門的訊號品質。
#
#   單位擴充（v19.171，**線上實機驗收抓到的第二層逃逸**）：
#     `section_long.py:273` 寫的是 `'降倉至 3 成以下，等待 DXY 回落'` ——
#     「3 成」= 30%，是不折不扣的硬編碼持股水位，卻因為原本只比對 `%` 而全身而退。
#     台股口語 1 成 = 10%，故 `\d{1,2}\s*成` 與 `\d{1,3}\s*%` 並列為合法單位。
#
#     「成」的假陽性防線（**不靠事後白名單，靠 pattern 本身夠準**）：
#       (a) 前置關鍵詞 + 12 字窗口已先擋掉絕大多數 —— 光是「成」出現在檔案裡
#           完全不會命中，必須是「持股／降倉／水位…」後面緊接著「N 成」。
#       (b) 再加負向前瞻，排除「N + 成X」剛好連在一起的複合詞：
#           `成長／成交／成本／成立／成分／成份／成功／成果／成員／成熟／成型／
#            成人／成年／成效／成因／成語`。
#           真實案例：`etf_tab_smart.py:51` 的「3-3-3 成立年數」會被 `\d{1,2}\s*成`
#           命中（`3` + ` ` + `成`），雖然該行沒有前置關鍵詞、當下不會誤報，
#           但這類寫法隨時可能出現在有關鍵詞的句子裡，先擋起來成本近乎為零。
#       (c) 反之，「N 成」後面接「以下／以上／左右／水位／倉」等**真的在講水位**
#           的字都不在排除集合裡，仍然抓得到。
#     驗證（v19.171 實跑 ripgrep，範圍 = 本測試掃描範圍 src/ui + src/compute + app.py）：
#       - 裸 `\d{1,2}\s*成`：修前 src/ui 2 筆（`etf_tab_smart.py:51` 的
#         「3-3-3 成立年數」docstring + `section_long.py:273` 真違規）、
#         src/compute 與 app.py 各 0 筆。
#       - 加上關鍵詞前綴後：修前只剩 `section_long.py:273` 一筆真違規；
#         修後 0 筆（該行殘留的「3 成」只出現在說明**註解**裡，
#         `_scan()` 的 `startswith('#')` 規則本來就排除註解）。
_PATTERN = re.compile(
    r'('
    r'持股|曝險|倉位|部位|現金|股票型ETF|債券型ETF'   # 名詞型：直接宣告水位
    r'|降倉|減倉|加倉|清倉|滿倉|空手|水位|比重'        # 動詞／量詞型（v19.171 補）
    r')[^,，。（(\n]{0,12}'
    r'(?:'
    r'\d{1,3}\s*%'                                    # 百分比：30%
    r'|\d{1,2}\s*成(?![長交本立分份功果員熟型人年效因語])'  # 台股口語：3 成 = 30%（v19.171 補）
    r')'
)

# ── 白名單：允許出現硬編碼持股百分比的檔 ────────────────────────────
# 每一筆都必須有「為什麼這裡是合法的」的理由，不接受「因為它紅了」。
_ALLOWED_FILES: dict[str, str] = {
    'shared/allocation_decision.py':
        '持股 SSOT 本體 —— 全站唯一有資格定義持股區間的地方',
    'shared/position_throttle.py':
        '姿態油門帶（積極↔防守 → 百分比區間）的定義來源，餵給 SSOT 仲裁',
    'src/compute/risk/risk_control.py':
        '風控硬規則常數（現金下限 10% / 轉空降至 20%），屬 SSOT 的天花板輸入',
    'src/ui/tabs/tab_edu.py':
        '教學頁靜態對照表（M1B-M2 資金行情教材），不是對當下盤勢的建議',
    'src/ui/render/etf_render.py':
        'DEPRECATED 常數（MACRO_ALLOC）+ ETF 產業曝險上限文案，非個人持股建議',
}

# ── 已知技術債：暫時放行，但**必須逐版縮小** ──────────────────────
# 與 _ALLOWED_FILES 的差別：這裡的每一筆都是「該修，只是本輪沒授權動」。
# key = 相對路徑；value = 該行必須包含的簽章字串（比行號穩，重排不會誤紅）。
# 只要這些檔**新增**別的硬編碼持股 %，仍然會紅 —— 不是整檔免死金牌。
_KNOWN_DEBT: dict[str, tuple[str, ...]] = {
    # v4 否決權引擎（L2）的紅燈文案。目前由 `section_chips.py` 在 UI 邊界用
    # regex 把「建議持股 ≤20%」剝掉、只留敘事，畫面不會出現競爭數字；
    # 但字串本體仍是硬編碼，若有第二個 caller 直接印就會破功 → 記為債。
    'src/compute/strategy/v4_strategy_engine.py': ('建議持股 ≤20%',),
    # `get_defensive_allocation()` 的紅燈文案。此函式**零 production caller**
    # （已確認全 repo 無呼叫點，僅 __init__ 匯入模組），屬死碼；
    # 一旦有人接線就會多出第 7 套持股建議 → 記為債，建議下一版直接刪或改吃 SSOT。
    'src/compute/strategy/v5_modules.py': ('建議股票部位降至 20%',),
}

# ── 關鍵詞撞名、語意無關的假陽性 ───────────────────────────────────
# 比對對象是**命中的字串本身**（不是整行），避免「建議持股 20%（風險 1.5% 法）」
# 這種真違規因為同行有假陽性關鍵詞而被整行放過。
_FALSE_POSITIVE_RE: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r'現金\s*[^\n]{0,4}總資產'),
     '財報體質「現金佔總資產 >25%」(老師「氣長不長」框架) —— 是選股門檻，不是投組現金部位'),
    (re.compile(r'風險\s*[\d.]+\s*%'),
     '單筆交易風險上限「風險 1.5% 法」—— 分母是單筆可虧損金額，不是總持股比例'),
)


def _iter_scan_files():
    for _d in _SCAN_DIRS:
        yield from sorted((_REPO_ROOT / _d).rglob('*.py'))
    for _f in _SCAN_FILES:
        _p = _REPO_ROOT / _f
        if _p.exists():
            yield _p


def _docstring_lines(src: str, path: Path) -> set[int]:
    """回傳所有 docstring / 裸字串陳述式佔用的行號集合。

    `Expr(Constant[str])` 涵蓋 module/class/function docstring 與
    `signal_thresholds.py` 那種「賦值後接說明字串」的屬性 docstring。
    **不**涵蓋 `st.markdown('''…''')` —— 那是 `Expr(Call(...))`，字串只是引數，
    會真的渲染給使用者看，必須留在掃描範圍內。
    """
    try:
        _tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return set()   # 語法錯由 test_no_undefined_names 負責，這裡不重複報
    _lines: set[int] = set()
    for _node in ast.walk(_tree):
        if (isinstance(_node, ast.Expr)
                and isinstance(_node.value, ast.Constant)
                and isinstance(_node.value.value, str)):
            _lines.update(range(_node.lineno, (_node.end_lineno or _node.lineno) + 1))
    return _lines


def _scan(path: Path) -> list[str]:
    _rel = path.relative_to(_REPO_ROOT).as_posix()
    if _rel in _ALLOWED_FILES:
        return []
    _src = path.read_text(encoding='utf-8')
    _skip = _docstring_lines(_src, path)
    _debt = _KNOWN_DEBT.get(_rel, ())
    _hits: list[str] = []
    for _no, _line in enumerate(_src.splitlines(), start=1):
        if _no in _skip:
            continue
        _stripped = _line.strip()
        if _stripped.startswith('#'):
            continue
        if any(_sig in _line for _sig in _debt):
            continue
        for _m in _PATTERN.finditer(_line):
            _text = _m.group(0)
            if any(_fp.search(_text) for _fp, _ in _FALSE_POSITIVE_RE):
                continue
            _hits.append(f'{_rel}:{_no}: {_stripped}')
            break   # 一行報一次就夠，訊息別炸開
    return _hits


def test_no_hardcoded_position_pct_in_ui_or_compute():
    """全站唯一持股數字守門：UI / Compute 不得自行寫死持股百分比。

    §1 Fail Loud + SSOT：使用者在同一個畫面看到兩個不同的持股建議，
    比看到「資料未載入」更傷信任 —— 他不知道該信哪一個，也不知道系統算錯了沒。
    """
    _violations: list[str] = []
    for _f in _iter_scan_files():
        _violations.extend(_scan(_f))

    assert not _violations, (
        f'發現 {len(_violations)} 處硬編碼持股百分比（會與 🎚️ 建議持股油門 打架）：\n'
        + '\n'.join(_violations)
        + '\n\n持股百分比只能來自 get_allocation() / get_allocation_sleeves()；'
          '若為教學用途請加入白名單（_ALLOWED_FILES）並在 STATE.md 登記。'
    )


def test_pattern_actually_catches_a_known_bad_string():
    """反向驗證：守門 regex 真的抓得到違規樣式，不是永遠綠的空測試。

    沒有這條，未來有人手滑把 `_PATTERN` 改壞（例如漏掉關鍵詞），
    上面那個測試會變成「永遠通過」的假綠燈。

    v19.171：補上**動詞型**樣本。前 4 條在 v19.170 就是綠的，但線上實機
    仍印出「建議降倉至30%以下」—— 證明「反向驗證樣本」只涵蓋名詞型時，
    這條測試本身也是假綠燈。新樣本直接取自實機截圖與被修掉的原始碼。

    v19.171（第二層）：再補**「成」單位**樣本。`section_long.py:273` 的
    `'降倉至 3 成以下'` 語意上就是 30%，卻因為原 pattern 只認 `%` 而逃逸 ——
    同一個「反向驗證樣本不夠廣 → 假綠燈」的坑踩第二次。
    """
    _bad = [
        "st.markdown('建議持股 30-50%')",
        "_msg = f'曝險 0%／現金 100%'",
        "'倉位降至 60%'",
        "'建議股票部位降至 20%'",
        # ── v19.171 實機殘留樣式（動詞型）──────────────────────
        "'外資雙向避險，高機率隨即殺盤，建議降倉至30%以下'",   # section_chips
        "f'大盤空頭格局，{sid2} 無論評分多高，先降倉至20%以下'",  # op_recommendation
        "'現金水位拉到 40%'",
        "'股票比重壓到 25%'",
        # ── v19.171 實機殘留樣式（「成」單位，1 成 = 10%）──────────
        "'降倉至 3 成以下，等待 DXY 回落'",   # section_long:273（本版已修）
        "'降倉至3成以下'",                    # 無空白版
        "'現金水位拉到 4 成'",
        "'建議持股 5 成'",
        "'股票比重降到 2 成左右'",
    ]
    for _s in _bad:
        assert _PATTERN.search(_s), f'守門 regex 漏抓：{_s}'


def test_cheng_unit_does_not_match_compound_words():
    """「成」單位不得誤殺「成長／成交／成立／成本…」等複合詞（v19.171）。

    「成」是中文高頻字，數字緊接複合詞（`3-3-3 成立年數`、`近 5 成長動能`）
    在本 repo 真的存在。若沒有這道負向前瞻，這類寫法一旦出現在含
    「持股／現金／比重」的句子裡就會誤報，逼出一堆無意義白名單，
    反而稀釋這道守門的訊號品質（同 `_FALSE_POSITIVE_RE` 的設計理由）。
    """
    _ok = [
        "'3-3-3 成立年數（持股滿 3 年）'",     # etf_tab_smart.py:51 的實際寫法
        "'現金流量表看營收 5 成長動能'",
        "'持股集中度前 10 成交量占比'",
        "'部位管理的 3 成本結構'",
        "'比重最高的 5 成分股'",
    ]
    for _s in _ok:
        assert not _PATTERN.search(_s), f'「成」複合詞被誤判為持股水位：{_s}'


def test_false_positive_filter_does_not_swallow_real_violations():
    """假陽性過濾器只能放過語意無關者，不得順手放過真違規。

    v19.170：本測試曾經是紅的，根因在 `_PATTERN` 而非過濾器 —— 貪婪的
    `[^,，。\\n]{0,12}` 讓命中片段跨過 `（` 吃進「風險 1.5%」，於是整段被
    假陽性規則吃掉。修法是收緊 `_PATTERN` 的邊界（見該常數註解），
    而不是放寬假陽性規則：**過濾器只能因「命中片段本身語意無關」而放行，
    不能因為同一行還有別的東西就整條放掉。**
    """
    # 真違規：即使同行有「風險 1.5% 法」，`持股 30%` 仍必須被抓到。
    _m = [x.group(0) for x in _PATTERN.finditer('建議持股 30%（風險 1.5% 法）')]
    _kept = [t for t in _m
             if not any(fp.search(t) for fp, _ in _FALSE_POSITIVE_RE)]
    assert _kept, '真違規「持股 30%」被假陽性過濾器誤殺'
    # v19.170 順帶釘住邊界：命中片段必須剛好停在 `持股 30%`，不得吃進括號內容。
    assert _kept == ['持股 30%'], f'命中片段吃進了括號內的補充說明：{_kept}'
    # 假陽性：財報「現金佔總資產 >25%」必須被放過。
    _m2 = [x.group(0) for x in _PATTERN.finditer('現金佔總資產 >25%')]
    assert _m2, 'regex 應先命中，才輪得到過濾器'
    assert all(any(fp.search(t) for fp, _ in _FALSE_POSITIVE_RE) for t in _m2), \
        '財報「現金佔總資產」未被判為假陽性'


def test_whitelist_entries_all_exist():
    """白名單/技術債清單不得指向已不存在的檔（重構後留下的殭屍豁免最危險）。"""
    _missing = [_p for _p in (*_ALLOWED_FILES, *_KNOWN_DEBT)
                if not (_REPO_ROOT / _p).exists()]
    assert not _missing, f'白名單指向不存在的檔（請清理）：{_missing}'


def test_known_debt_signatures_still_present():
    """技術債簽章必須還在 —— 修好了就該從 `_KNOWN_DEBT` 移除，別留殭屍豁免。"""
    _stale: list[str] = []
    for _rel, _sigs in _KNOWN_DEBT.items():
        _src = (_REPO_ROOT / _rel).read_text(encoding='utf-8')
        _stale.extend(f'{_rel}: {_s!r}' for _s in _sigs if _s not in _src)
    assert not _stale, (
        '以下技術債簽章已不存在（可能已修好）→ 請從 _KNOWN_DEBT 移除：\n'
        + '\n'.join(_stale))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
