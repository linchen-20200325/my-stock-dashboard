"""shared/parse_helpers.py — 純函式輸入解析 helpers(L0 Shared,v18.302)

CLAUDE.md §8.3 灰區 — app.py 7,300 LOC 拆檔最小提取。
從 app.py:144 提取 `parse_stocks`(無 I/O 純函式,適合 L0)。

設計
----
- L0 純函式,無 I/O,無 streamlit / requests / pandas
- 接 str(user input),回 list[str](validated stock IDs)
- 純 regex 處理,無外部依賴
"""
from __future__ import annotations

import re


_STOCK_ID_PATTERN = re.compile(r'^\d{4,6}[A-Z]?$')
"""股票代號 SSOT regex:4-6 位數字,選 1 位大寫字母結尾
(e.g. 2330, 2330R, 00878, 6660C)。"""

_INPUT_SPLIT_PATTERN = re.compile(r'[,\s\n；，]+')
"""使用者輸入多檔分隔符:半形逗號 ',' / 全形逗號 '，'(U+FF0C) /
空白 / 換行 / 全形分號 '；'(U+FF1B)。對齊 app.py 原始 SSOT 行為。"""


def parse_stocks(raw: str) -> list[str]:
    """解析 user 輸入字串為股票代號清單。

    Parameters
    ----------
    raw : str
        user 輸入的多檔代號字串,任意分隔符(逗號 / 空白 / 換行 / 全形)。

    Returns
    -------
    list[str]
        合法股票代號清單(4-6 位數字,選 1 位大寫字母結尾)。
        非法輸入(空字串 / 不符 pattern)被過濾。順序保留。

    Examples
    --------
    >>> parse_stocks("2330, 2454, 00878")
    ['2330', '2454', '00878']
    >>> parse_stocks("2330\\n2454\\n6660C")
    ['2330', '2454', '6660C']
    >>> parse_stocks("abc, 2330, 12345678")  # abc 非法 + 12345678 過長
    ['2330']
    """
    if not raw:
        return []
    stocks = _INPUT_SPLIT_PATTERN.split(raw.strip())
    return [
        s.strip()
        for s in stocks
        if s.strip() and _STOCK_ID_PATTERN.match(s.strip())
    ]
