"""tests/test_user_facing_copy_guard.py — 使用者可見文案不得混入開發者備忘（2026-08-25）

## 這個守衛在防哪一種病

v19.170 修過一次:`shared/macro_buckets.py` 的 `margin.note` 誤植了開發者備忘
(版本號、實測值、模組路徑 `shared/relative_thresholds.margin_leverage_ratio +
classify_by_pct_rank`),而該欄**原文渲染在五桶「🧩 籌碼」的指標明細卡上**,
實機驗證確認整段被印到畫面。

2026-08-25 全面盤點發現**那次只修了一條**。同一種病還躲在:
  · `EDU_GUIDE` 的 10 處(📖 系統說明書分頁逐字渲染)
  · `macro_buckets` 另外 3 個 spec 的 `note`

換句話說,靠「發現一條、修一條」是修不完的 —— 只要沒有機械守衛,
下一個人照樣會把備忘寫進使用者看得到的欄位,而且要等到有人盯著畫面才發現。

## 為什麼用「讀資料結構」而不是「掃整個檔案」

掃整檔會誤報:同一個檔案裡的 `source="SSOT:..."`、dict key、內部常數名
本來就是寫給開發者看的,它們不會被渲染。本檔改成**把模組 import 進來,
只掃真正會渲染出去的欄位**,精準且不需要維護白名單。

渲染路徑證據:
  · `EDU_GUIDE` 六個欄位全部渲染 —— `data_registry.render_edu_card_html()`
    逐欄 `_esc()` 後注入 HTML,呼叫點 `src/ui/tabs/tab_edu.py`
  · `DangerSpec.note` —— `shared/macro_buckets.py` 檔內自述
    「note 欄會**原文渲染在五桶「🧩 籌碼」的指標明細卡上給一般使用者看**」
  · `DangerSpec.unwired_reason` / `degraded_reason` —— 資料看板與總經 v2 明細

## 正確的修法(給未來踩到這個守衛的人)

把技術細節搬到**同一段的 `#` 註解**,渲染欄位只留使用者看得懂的話。
本檔掃的是資料結構的值,註解天然不在裡面,所以搬過去就會過。
不要為了讓測試變綠而把有用的警語整段刪掉 —— 「門檻正在失準」這件事
對使用者是有價值的,沒價值的是「v19.170 稽核實測 5,148 億」。
"""
from __future__ import annotations

import re

import pytest

from shared.macro_buckets import BUCKET_DANGER_SPECS
from src.data.core.data_registry import EDU_GUIDE

# ══════════════════════════════════════════════════════════════════
# 開發者備忘的特徵
# ══════════════════════════════════════════════════════════════════
#: 每條 = (regex, 人話說明)。命中任一條 → 這段文字不是寫給一般使用者的。
_DEV_MEMO_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r'\bv\d+\.\d+'), '版本號(如 v19.170)'),
    (re.compile(r'\b[\w.]+\.py\b'), '檔名(如 macro_buckets.py)'),
    (re.compile(r'\b(?:shared|src|infra|scripts|tests)/[\w/]+'), '模組路徑(如 shared/relative_thresholds)'),
    (re.compile(r'\b[a-z_]{3,}\.[a-z_]{3,}\('), '函式呼叫(如 classify_by_pct_rank()'),
    (re.compile(r'\b(?:SSOT|DESIGN|WONTFIX|TODO|FIXME)\b'), '內部標記(SSOT/DESIGN/TODO…)'),
    (re.compile(r'稽核|實測|舊文案|舊版教學|本次修掉'), '程式碼修改史(稽核/實測/舊文案…)'),
)

#: `EDU_GUIDE` 裡會被 `render_edu_card_html()` 渲染出去的欄位。
_EDU_RENDERED_FIELDS = (
    'meaning', 'how_to_read', 'pair_with',
    'historical_anchor', 'upstream', 'downstream',
)

#: `DangerSpec` 裡會渲染給使用者的欄位(`source` 等開發者欄位刻意不掃)。
_SPEC_RENDERED_FIELDS = ('note', 'unwired_reason', 'degraded_reason')

#: 已判讀為「不是備忘」的例外,格式 `<來源>|<命中的字面>`。
#: **刻意不用行號** —— 行號一重構就過期,等於保證會失效的資訊(CLAUDE.md §8.2.A.0 規則 1)。
_ALLOWED: frozenset[str] = frozenset()


def _flatten(value) -> list[str]:
    """把欄位值攤成字串清單(`how_to_read` 是 tuple list、`pair_with` 是 list)。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return []


def _scan(origin: str, text: str) -> list[tuple[str, str, str, str]]:
    """回傳 (origin, 命中字面, 說明, 原文) 清單。"""
    hits = []
    for pattern, why in _DEV_MEMO_PATTERNS:
        for m in pattern.findall(text):
            frag = m if isinstance(m, str) else str(m)
            if f'{origin}|{frag}' in _ALLOWED:
                continue
            hits.append((origin, frag, why, text))
    return hits


def _all_hits() -> list[tuple[str, str, str, str]]:
    hits: list[tuple[str, str, str, str]] = []
    for key, entry in EDU_GUIDE.items():
        for field in _EDU_RENDERED_FIELDS:
            for text in _flatten(entry.get(field)):
                hits.extend(_scan(f'EDU_GUIDE[{key!r}].{field}', text))
    for spec in BUCKET_DANGER_SPECS:
        for field in _SPEC_RENDERED_FIELDS:
            for text in _flatten(getattr(spec, field, '')):
                hits.extend(_scan(f'DangerSpec({spec.key!r}).{field}', text))
    return hits


# ══════════════════════════════════════════════════════════════════
# 守衛本身
# ══════════════════════════════════════════════════════════════════
def test_no_developer_memo_in_user_facing_copy():
    """使用者可見文案不得含版本號 / 檔名 / 模組路徑 / 函式呼叫 / 內部標記 / 修改史。"""
    hits = _all_hits()
    if not hits:
        return

    lines = ['', f'發現 {len(hits)} 處開發者備忘寫進了使用者看得到的文案:', '']
    for origin, frag, why, text in hits:
        lines.append(f'  ● {origin}')
        lines.append(f'    命中「{frag}」— {why}')
        lines.append(f'    原文:{text[:110]}{"…" if len(text) > 110 else ""}')
        lines.append('')
    lines += [
        '修法:把技術細節搬到同一段的 `#` 註解,渲染欄位只留使用者看得懂的話。',
        '（本守衛掃的是資料結構的值,註解不在裡面,搬過去就會過。）',
        '',
        '若確認某條是誤判,貼進本檔 `_ALLOWED`:',
    ] + [f"    '{o}|{f}'," for o, f, _, _ in hits]
    pytest.fail('\n'.join(lines))


# ══════════════════════════════════════════════════════════════════
# 守衛的守衛 —— 確認它真的抓得到,不是永遠綠燈
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('sample, expect_why', [
    ('v19.170 稽核實測 5,148 億', '版本號'),
    ('相對分位見 shared/relative_thresholds', '模組路徑'),
    ('見 shared/macro_buckets.py 的註解', '檔名'),
    ('走 shared.thresholds.classify_yield_zone(x)', '函式呼叫'),
    ('本欄 source=SSOT 標記', '內部標記'),
    ('舊文案只有紅綠兩段,已於本次修掉', '程式碼修改史'),
])
def test_guard_actually_catches_known_memo_shapes(sample, expect_why):
    """用真實踩過的字串當樣本 —— 全部來自 2026-08-25 盤點出的 13 條。"""
    hits = _scan('SAMPLE', sample)
    assert hits, f'守衛漏抓「{sample}」(應命中:{expect_why})'


@pytest.mark.parametrize('sample', [
    '2008 雷曼 89.5｜2020 疫情 82.7｜平時 12–18',
    '這兩條是絕對金額門檻,沒有隨市場總市值成長調整',
    '🟢 安全水位（🌍 總經的融資卡顯示綠）',
    '融資餘額 = 散戶向券商借錢買股的未還金額',
    '台灣 GDP 約 60% 來自出口',
    '看數字前請先確認 🔎 資料診斷頁的凍結偵測沒亮紅',
])
def test_guard_does_not_flag_legitimate_copy(sample):
    """反向:正常的使用者文案不得被誤判,否則守衛會逼人刪掉有用的話。"""
    hits = _scan('SAMPLE', sample)
    assert not hits, f'誤判「{sample}」→ {[(h[1], h[2]) for h in hits]}'


def test_scanned_surface_is_not_empty():
    """確認真的掃到東西 —— 欄位改名會讓守衛靜默失效,那是最糟的失敗模式。"""
    n_edu = sum(
        len(_flatten(e.get(f)))
        for e in EDU_GUIDE.values() for f in _EDU_RENDERED_FIELDS
    )
    n_spec = sum(
        len(_flatten(getattr(s, f, '')))
        for s in BUCKET_DANGER_SPECS for f in _SPEC_RENDERED_FIELDS
    )
    assert n_edu >= 100, f'EDU_GUIDE 掃描面過小({n_edu} 段) — 欄位名可能改了'
    assert n_spec >= 15, f'DangerSpec 掃描面過小({n_spec} 段) — 欄位名可能改了'
